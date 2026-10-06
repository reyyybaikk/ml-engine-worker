import os
import yaml
import pathlib
from decimal import Decimal
from typing import List, Dict, Any

from ..models.rule import Rule

# Load rules lazily at import time – if the file does not exist we just have an empty list.
RULES_PATH = pathlib.Path(__file__).parent.parent / "config" / "rules.yaml"
if RULES_PATH.exists():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []
    # Resolve placeholders like "{{PRICE_MIN}}" and cast to numeric if possible
    def _resolve(value):
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            env_key = value.strip("{} ")
            env_val = os.getenv(env_key)
            if env_val is not None:
                try:
                    return Decimal(env_val)
                except Exception:
                    return env_val
            return value
        # Try numeric conversion for plain strings
        if isinstance(value, str):
            try:
                return Decimal(value)
            except Exception:
                return value
        return value
    processed = []
    for r in raw:
        if isinstance(r, dict):
            conds = []
            for cond in r.get("conditions", []):
                cond["value"] = _resolve(cond.get("value"))
                conds.append(cond)
            r["conditions"] = conds
        processed.append(r)
    RULES: List[Rule] = [Rule(**r) for r in processed]
else:
    RULES = []

_operators = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}

def _coerce(val: Any, target: Any):
    """Convert both sides to Decimal when possible for safe numeric comparison."""
    try:
        return Decimal(val), Decimal(target)
    except Exception:
        # Fallback to original values (e.g., strings)
        return val, target

def evaluate_transaction_rules(payload: Dict[str, Any]) -> List[str]:
    """Return a list of anomaly_label strings whose rule matches the payload.
    The payload is expected to be a flat dict where keys correspond to the
    `field` values defined in the rules.
    """
    matched: List[str] = []
    for rule in RULES:
        ok = True
        for cond in rule.conditions:
            if cond.field not in payload:
                ok = False
                break
            val, target = _coerce(payload[cond.field], cond.value)
            op_func = _operators.get(cond.operator)
            if op_func is None or not op_func(val, target):
                ok = False
                break
        if ok:
            matched.append(rule.anomaly_label)
    return matched

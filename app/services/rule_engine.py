# file: app/services/rule_engine.py
"""Simple rule engine for ML Engine.
Loads rule definitions from `app/config/rules.yaml` (YAML) and evaluates a
payload dict (transaction fields) against those rules.
Returns a list of anomaly labels (empty if no rule matches).
"""

import yaml
import pathlib
from typing import List, Dict, Any

from ..models.rule import Rule

# Load rules lazily at import time – if the file does not exist we just have an empty list.
RULES_PATH = pathlib.Path(__file__).parent.parent / "config" / "rules.yaml"
if RULES_PATH.exists():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []
    RULES: List[Rule] = [Rule(**r) for r in raw]
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
    """Try numeric conversion; fall back to original values for string comparison."""
    try:
        return float(val), float(target)
    except Exception:
        return val, target

def evaluate_transaction_rules(payload: Dict[str, Any]) -> List[str]:
    """Return a list of `anomaly_label` strings whose rule matches the payload.
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

# file: app/services/rule_engine.py
"""Simple rule engine for ML Engine.
Loads rule definitions from `app/config/rules.yaml` (YAML) and evaluates a
payload dict (transaction fields) against those rules.
Returns a list of anomaly labels (empty if no rule matches).
"""

import os
import pathlib
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any

import yaml

from ..models.rule import Rule

# Load rules lazily at import time – if the file does not exist we just have an empty list.
RULES_PATH = pathlib.Path(__file__).parent.parent / "config" / "rules.yaml"
if RULES_PATH.exists():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []
    for rule in raw:
        for condition in rule.get("conditions", []):
            value = condition.get("value")
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                env_value = os.getenv(value[2:-2].strip())
                if env_value is not None:
                    try:
                        condition["value"] = Decimal(env_value)
                    except InvalidOperation:
                        condition["value"] = env_value
            elif isinstance(value, str):
                try:
                    condition["value"] = Decimal(value)
                except InvalidOperation:
                    pass
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
    """Convert numeric values to Decimal, preserving non-numeric values."""
    try:
        val_decimal = Decimal(str(val))
        if not val_decimal.is_finite():
            val_decimal = None
    except (InvalidOperation, TypeError, ValueError):
        val_decimal = None

    try:
        target_decimal = Decimal(str(target))
        if not target_decimal.is_finite():
            target_decimal = None
    except (InvalidOperation, TypeError, ValueError):
        target_decimal = None

    if val_decimal is not None and target_decimal is not None:
        return val_decimal, target_decimal
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
            target = cond.value
            if isinstance(target, str) and target in payload:
                target = payload[target]

            val, target = _coerce(payload[cond.field], target)
            op_func = _operators.get(cond.operator)
            if op_func is None:
                ok = False
                break
            if cond.operator in {">", "<", ">=", "<="} and not (
                isinstance(val, Decimal) and isinstance(target, Decimal)
            ):
                ok = False
                break
            try:
                if not op_func(val, target):
                    ok = False
                    break
            except (InvalidOperation, TypeError):
                ok = False
                break
        if ok:
            matched.append(rule.anomaly_label)
    return matched

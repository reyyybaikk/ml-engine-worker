# file: app/models/rule.py
"""Model definitions for rule‑based anomaly detection.
These Pydantic models are loaded from a YAML/JSON file at runtime.
"""

from pydantic import BaseModel, Field
from typing import List, Union

class Condition(BaseModel):
    """Single condition inside a rule.
    field: nama kolom di data transaksi (mis. "fuel_amount")
    operator: salah satu dari ">", "<", ">=", "<=", "==", "!="
    value: nilai yang akan dibandingkan, dapat berupa int, float, atau str.
    """
    field: str
    operator: str = Field(..., description="Operator comparison")
    value: Union[int, float, str]

class Rule(BaseModel):
    """Sebuah rule yang dapat menandai anomali.
    name: nama rule yang mudah dibaca
    description: penjelasan singkat rule
    conditions: list of Condition
    anomaly_label: label yang akan disimpan bila rule terpenuhi (default "ANOMALI")
    """
    name: str
    description: str = ""
    conditions: List[Condition]
    anomaly_label: str = Field("ANOMALI", description="Label anomali ketika rule cocok")

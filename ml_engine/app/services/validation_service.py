def validate_transaction_data(data: dict) -> bool:
    """
    Melakukan validasi terhadap data transaksi dan master kendaraan 
    yang ditarik dari database sebelum diproses oleh baseline engine.
    """
    if not data:
        raise ValueError("Data transaksi tidak boleh kosong atau bernilai None.")

    # 1. Validasi ID Transaksi
    transaction_id = data.get("id")
    if not transaction_id or not isinstance(transaction_id, int):
        raise ValueError(f"Invalid transaction_id: {transaction_id}. Harus berupa angka integer.")

    # 2. Validasi Jumlah BBM (Fuel Amount)
    fuel_amount = data.get("fuel_amount")
    if fuel_amount is None:
        raise ValueError(f"Transaction ID {transaction_id}: Kolom fuel_amount tidak ditemukan.")
    
    try:
        fuel_amount_float = float(fuel_amount)
    except (ValueError, TypeError):
        raise ValueError(f"Transaction ID {transaction_id}: fuel_amount harus berupa angka numerik.")
        
    if fuel_amount_float <= 0:
        raise ValueError(f"Transaction ID {transaction_id}: fuel_amount tidak boleh bernilai nol atau negatif ({fuel_amount_float}).")

    # 3. Validasi Kapasitas Tangki Kendaraan (Dari Data Master)
    tank_capacity = data.get("fuel_tank_capacity")
    if tank_capacity is None:
        print(f"[Python Validation Warning] Transaction ID {transaction_id}: Kapasitas tangki null di database, menggunakan default 50.0 Liter.")
        data["fuel_tank_capacity"] = 50.0
    else:
        try:
            tank_capacity_float = float(tank_capacity)
            if tank_capacity_float <= 0:
                print(f"[Python Validation Warning] Transaction ID {transaction_id}: Kapasitas tangki <= 0, menggunakan default 50.0 Liter.")
                data["fuel_tank_capacity"] = 50.0
        except (ValueError, TypeError):
            data["fuel_tank_capacity"] = 50.0

    print(f"[Python Validation] Data untuk Transaction ID {transaction_id} valid dan aman diproses.")
    return True

# ---------------------------------------------------------------------------
# Extended validation that checks numeric bounds (min/max) for fuel, cost, odometer.
# Returns (is_invalid, list_of_anomaly_labels, explanatory_note).
# ---------------------------------------------------------------------------
import os
from decimal import Decimal
from typing import List, Tuple

# Nilai ambang dapat disesuaikan lewat .env, bila tidak ada memakai default.
FUEL_AMOUNT_MIN = Decimal(os.getenv("FUEL_AMOUNT_MIN", "0.1"))   # liter
FUEL_AMOUNT_MAX = Decimal(os.getenv("FUEL_AMOUNT_MAX", "500.0")) # liter
COST_MIN       = Decimal(os.getenv("TOTAL_COST_MIN", "1000"))   # IDR
COST_MAX       = Decimal(os.getenv("TOTAL_COST_MAX", "1000000"))
ODOMETER_MIN   = Decimal(os.getenv("ODOMETER_MIN", "0"))
ODOMETER_MAX   = Decimal(os.getenv("ODOMETER_MAX", "10000000"))

def validate_transaction_input(payload: dict) -> Tuple[bool, List[str], str]:
    """Validate raw transaction fields against configurable bounds.
    Returns:
        (is_invalid, anomaly_labels, note)
    is_invalid – True bila ada pelanggaran.
    anomaly_labels – daftar label yang akan dimasukkan ke `rule_labels`.
    note – penjelasan singkat untuk log / notes.
    """
    labels: List[str] = []
    notes: List[str] = []

    # fuel_amount
    try:
        fuel = Decimal(float(payload.get("fuel_amount", 0)))
    except Exception:
        fuel = Decimal(0)

    # total_cost
    try:
        cost = Decimal(float(payload.get("total_cost", 0)))
    except Exception:
        cost = Decimal(0)

    # odometer
    try:
        odo = Decimal(float(payload.get("odometer", 0)))
    except Exception:
        odo = Decimal(0)

    # ----- bound checks -----
    if fuel < FUEL_AMOUNT_MIN:
        labels.append("ANOMALI_FUEL_TOO_SMALL")
        notes.append(f"fuel_amount {fuel} < min {FUEL_AMOUNT_MIN}")

    if fuel > FUEL_AMOUNT_MAX:
        labels.append("ANOMALI_FUEL_TOO_LARGE")
        notes.append(f"fuel_amount {fuel} > max {FUEL_AMOUNT_MAX}")

    if cost < COST_MIN:
        labels.append("ANOMALI_COST_TOO_SMALL")
        notes.append(f"total_cost {cost} < min {COST_MIN}")

    if cost > COST_MAX:
        labels.append("ANOMALI_COST_TOO_LARGE")
        notes.append(f"total_cost {cost} > max {COST_MAX}")

    if odo < ODOMETER_MIN:
        labels.append("ANOMALI_ODOMETER_TOO_SMALL")
        notes.append(f"odometer {odo} < min {ODOMETER_MIN}")

    if odo > ODOMETER_MAX:
        labels.append("ANOMALI_ODOMETER_TOO_LARGE")
        notes.append(f"odometer {odo} > max {ODOMETER_MAX}")

    is_invalid = len(labels) > 0
    note_str = "; ".join(notes) if notes else ""
    return is_invalid, labels, note_str
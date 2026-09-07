def extract_features(transaction_data: dict) -> dict:
    """
    Melakukan ekstraksi fitur (feature engineering) dari data transaksi dan master kendaraan.
    Termasuk fitur dari OCR Nota: liters, total_cost, fuel_type, dan cross-validation nota vs form input.
    """
    if not transaction_data:
        raise ValueError("Data transaksi tidak tersedia untuk feature engineering.")

    # Ambil data dasar dari transaksi & master kendaraan
    fuel_amount = float(transaction_data.get("fuel_amount", 0))
    total_cost = float(transaction_data.get("total_cost", 0))
    tank_capacity = float(transaction_data.get("fuel_tank_capacity", 0))
    odometer_input = float(transaction_data.get("odometer", 0))
    consumption_rate = float(transaction_data.get("fuel_consumption_rate") or 0)
    fuel_type_input = str(transaction_data.get("fuel_type") or "").strip()

    # Ambil data hasil OCR Nota (bisa None jika OCR gagal)
    ocr_liters = transaction_data.get("ocr_liters")           # float atau None
    ocr_total_cost = transaction_data.get("ocr_total_cost")   # float atau None
    ocr_fuel_type = transaction_data.get("ocr_fuel_type")     # str atau None

    # 1. Hitung Harga per Liter (Cost per Liter)
    cost_per_liter = 0.0
    if fuel_amount > 0:
        cost_per_liter = total_cost / fuel_amount

    # 2. Hitung Rasio Penggunaan Kapasitas Tangki (Tank Fill Ratio)
    tank_fill_ratio = 0.0
    if tank_capacity > 0:
        tank_fill_ratio = (fuel_amount / tank_capacity) * 100

    # 3. Selisih liter OCR vs input manual driver (cross-validation struk vs form)
    ocr_vs_input_liter_diff = None
    if ocr_liters is not None and fuel_amount > 0:
        ocr_vs_input_liter_diff = abs(float(ocr_liters) - fuel_amount)

    # 4. Selisih harga OCR vs input manual driver (cross-validation struk vs form)
    ocr_vs_input_cost_diff = None
    if ocr_total_cost is not None and total_cost > 0:
        ocr_vs_input_cost_diff = abs(float(ocr_total_cost) - total_cost)

    features = {
        "transaction_id": transaction_data.get("id"),
        # Fitur dasar
        "fuel_amount": fuel_amount,
        "total_cost": total_cost,
        "odometer": odometer_input,
        "fuel_tank_capacity": tank_capacity,
        "fuel_consumption_rate": consumption_rate,
        "fuel_type": fuel_type_input,
        "cost_per_liter": round(cost_per_liter, 2),
        "tank_fill_ratio": round(tank_fill_ratio, 2),
        # Fitur dari OCR Nota
        "ocr_vs_input_liter_diff": round(ocr_vs_input_liter_diff, 2) if ocr_vs_input_liter_diff is not None else None,
        "ocr_vs_input_cost_diff": round(ocr_vs_input_cost_diff, 2) if ocr_vs_input_cost_diff is not None else None,
        # Data OCR mentah (diteruskan untuk rule engine)
        "ocr_liters": ocr_liters,
        "ocr_total_cost": ocr_total_cost,
        "ocr_fuel_type": ocr_fuel_type,
        # Fitur Anti-Fraud Duplikasi
        "duplicate_receipt_tx_id": transaction_data.get("duplicate_receipt_tx_id"),
    }

    print(f"[Python Feature Engineering] Fitur berhasil diekstrak untuk Transaction ID {features['transaction_id']}.")
    return features
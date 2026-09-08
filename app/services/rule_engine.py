import os
from dotenv import load_dotenv

load_dotenv()

# Batas harga dari .env (configurable, tidak hardcode)
PRICE_MIN = float(os.getenv("OCR_PRICE_MIN", 5000))
PRICE_MAX = float(os.getenv("OCR_PRICE_MAX", 20000))


def evaluate_transaction_rules(preprocessed_data: dict) -> dict:
    """
    Mengevaluasi data transaksi menggunakan aturan bisnis:
    
    Rule 1: Anomali Kapasitas Tangki — liter isi > kapasitas tangki
    Rule 2: Anomali Harga per Liter — harga di luar kisaran wajar
    Rule 3: Anomali Selisih Liter — liter di struk vs input manual berbeda signifikan
    Rule 4: Deteksi Nota Duplikat — nota yang sama digunakan berulang
    """
    if not preprocessed_data:
        raise ValueError("Data preprocessing kosong, tidak dapat menjalankan rule engine.")

    transaction_id = preprocessed_data.get("transaction_id")
    fuel_amount = preprocessed_data.get("fuel_amount", 0.0)
    total_cost = preprocessed_data.get("total_cost", 0.0)
    tank_capacity = preprocessed_data.get("fuel_tank_capacity", 0.0)
    cost_per_liter = preprocessed_data.get("cost_per_liter", 0.0)

    # OCR Differences
    ocr_vs_input_liter_diff = preprocessed_data.get("ocr_vs_input_liter_diff")
    ocr_vs_input_cost_diff = preprocessed_data.get("ocr_vs_input_cost_diff")
    ocr_vs_input_odo_diff = preprocessed_data.get("ocr_vs_input_odo_before_diff")

    # Raw Odometer Values
    odo_input = preprocessed_data.get("odometer", 0)
    ocr_odo_after = preprocessed_data.get("ocr_odo_after")

    is_anomaly = False
    anomaly_score = 0.0
    reasons = []

    # ─────────────────────────────────────────────────────────────
    # RULE 1: Validasi Kapasitas Tangki Fisik
    # ─────────────────────────────────────────────────────────────
    if tank_capacity > 0 and fuel_amount > tank_capacity:
        is_anomaly = True
        anomaly_score = 1.0
        reasons.append(
            f"[Rule 1] Jumlah BBM ({fuel_amount} L) melebihi kapasitas maksimal tangki ({tank_capacity} L)."
        )

    # ─────────────────────────────────────────────────────────────
    # RULE 2: Validasi Harga per Liter
    # ─────────────────────────────────────────────────────────────
    if cost_per_liter > 0:
        if cost_per_liter < PRICE_MIN:
            is_anomaly = True
            anomaly_score = max(anomaly_score, 0.7)
            reasons.append(
                f"[Rule 2] Harga per liter terlalu murah (Rp {cost_per_liter:,.0f})."
            )
        elif cost_per_liter > PRICE_MAX:
            is_anomaly = True
            anomaly_score = max(anomaly_score, 0.8)
            reasons.append(
                f"[Rule 2] Harga per liter terlalu mahal (Rp {cost_per_liter:,.0f})."
            )

    # ─────────────────────────────────────────────────────────────
    # RULE 3: Konsistensi OCR Nota vs Input Manual
    # ─────────────────────────────────────────────────────────────
    if ocr_vs_input_liter_diff is not None:
        tolerance = fuel_amount * 0.10
        if ocr_vs_input_liter_diff > tolerance:
            is_anomaly = True
            anomaly_score = max(anomaly_score, 0.85)
            ocr_liter_val = preprocessed_data.get("ocr_liters")
            reasons.append(
                f"[Rule 3] Selisih liter Nota ({ocr_liter_val} L) vs Input ({fuel_amount} L) tidak wajar."
            )

    if ocr_vs_input_cost_diff is not None:
        tolerance_cost = max(total_cost * 0.10, 5000.0)
        if ocr_vs_input_cost_diff > tolerance_cost:
            is_anomaly = True
            anomaly_score = max(anomaly_score, 0.85)
            ocr_cost_val = preprocessed_data.get("ocr_total_cost") or 0.0
            reasons.append(
                f"[Rule 4] Selisih biaya Nota (Rp {ocr_cost_val:,.0f}) vs Input (Rp {total_cost:,.0f}) tidak wajar."
            )

    # ─────────────────────────────────────────────────────────────
    # RULE 5: Validasi Odometer (Input vs OCR)
    # ─────────────────────────────────────────────────────────────
    if ocr_vs_input_odo_diff is not None:
        if ocr_vs_input_odo_diff > 100: # Toleransi 100 KM untuk kesalahan OCR kecil
            is_anomaly = True
            anomaly_score = max(anomaly_score, 0.9)
            ocr_odo_val = preprocessed_data.get("ocr_odo_before")
            reasons.append(
                f"[Rule 5] Odometer dashboard ({ocr_odo_val}) berbeda jauh dengan input ({odo_input})."
            )

    # ─────────────────────────────────────────────────────────────
    # RULE 6: Deteksi Nota Duplikat (Anti-Fraud)
    # ─────────────────────────────────────────────────────────────
    duplicate_receipt_tx_id = preprocessed_data.get("duplicate_receipt_tx_id")
    if duplicate_receipt_tx_id:
        is_anomaly = True
        anomaly_score = 1.0
        reasons.append(
            f"[Rule 6 - Anti Fraud] Foto nota identik dengan Transaksi #{duplicate_receipt_tx_id} (DUPLIKAT)."
        )

    # Jika tidak ada pelanggaran aturan
    if not reasons:
        reasons.append("NORMAL")

    result = {
        "transaction_id": transaction_id,
        "is_anomaly": is_anomaly,
        "anomaly_score": round(anomaly_score, 2),
        "detection_engine": "rule_based_v3_full_ocr",
        "notes": " | ".join(reasons)
    }

    print(f"[Python Rule Engine] Evaluasi selesai. Transaction ID {transaction_id}. Anomali: {is_anomaly}")
    return result

    # Jika tidak ada pelanggaran aturan
    if not reasons:
        reasons.append("NORMAL")

    result = {
        "transaction_id": transaction_id,
        "is_anomaly": is_anomaly,
        "anomaly_score": round(anomaly_score, 2),
        "detection_engine": "rule_based_v2_with_ocr",
        "notes": " | ".join(reasons)
    }

    print(f"[Python Rule Engine] Evaluasi selesai untuk Transaction ID {transaction_id}. Anomali: {is_anomaly}")
    return result

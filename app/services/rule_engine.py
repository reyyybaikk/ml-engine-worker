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
    ocr_vs_input_liter_diff = preprocessed_data.get("ocr_vs_input_liter_diff")  # None jika OCR gagal
    ocr_vs_input_cost_diff = preprocessed_data.get("ocr_vs_input_cost_diff")    # None jika OCR gagal

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
                f"[Rule 2] Harga per liter terlalu murah/tidak wajar (Rp {cost_per_liter:,.0f})."
            )
        elif cost_per_liter > PRICE_MAX:
            is_anomaly = True
            anomaly_score = max(anomaly_score, 0.8)
            reasons.append(
                f"[Rule 2] Harga per liter terlalu mahal/tidak wajar (Rp {cost_per_liter:,.0f})."
            )

    # ─────────────────────────────────────────────────────────────
    # RULE 3: Cross-validation Liter & Harga Struk (OCR) vs Input Manual
    # ─────────────────────────────────────────────────────────────
    if ocr_vs_input_liter_diff is not None and fuel_amount > 0:
        tolerance = fuel_amount * 0.10 # Toleransi 10% untuk OCR nota
        if ocr_vs_input_liter_diff > tolerance:
            is_anomaly = True
            anomaly_score = max(anomaly_score, 0.85)
            ocr_liter_val = preprocessed_data.get("ocr_liters")
            reasons.append(
                f"[Rule 3] Selisih liter antara struk OCR ({ocr_liter_val} L) dan input manual ({fuel_amount} L) "
                f"terlalu besar ({ocr_vs_input_liter_diff:.2f} L)."
            )

    if ocr_vs_input_cost_diff is not None and total_cost > 0:
        tolerance_cost = max(total_cost * 0.10, 5000.0)
        if ocr_vs_input_cost_diff > tolerance_cost:
            is_anomaly = True
            anomaly_score = max(anomaly_score, 0.85)
            ocr_cost_val = preprocessed_data.get("ocr_total_cost") or 0.0
            reasons.append(
                f"[Rule 4] Selisih total biaya nota OCR (Rp {ocr_cost_val:,.0f}) dengan input manual (Rp {total_cost:,.0f}) "
                f"tidak wajar."
            )

    # ─────────────────────────────────────────────────────────────
    # RULE 5: Deteksi Penggunaan Nota Duplikat / Bekas (Anti-Fraud)
    # ─────────────────────────────────────────────────────────────
    duplicate_receipt_tx_id = preprocessed_data.get("duplicate_receipt_tx_id")
    if duplicate_receipt_tx_id:
        is_anomaly = True
        anomaly_score = 1.0
        reasons.append(
            f"[Rule 5 - Anti Fraud] Foto nota ini identik dengan Transaksi ID #{duplicate_receipt_tx_id} (DUPLIKAT)."
        )

    # Jika tidak ada pelanggaran aturan
    if not reasons:
        reasons.append("Transaksi normal, sesuai dengan semua batasan fisik dan standar operasional.")

    result = {
        "transaction_id": transaction_id,
        "is_anomaly": is_anomaly,
        "anomaly_score": round(anomaly_score, 2),
        "detection_engine": "rule_based_v2_with_ocr",
        "notes": " | ".join(reasons)
    }

    print(f"[Python Rule Engine] Evaluasi selesai untuk Transaction ID {transaction_id}. Anomali: {is_anomaly}")
    return result

    # Jika tidak ada pelanggaran aturan
    if not reasons:
        reasons.append("Transaksi normal, sesuai dengan semua batasan fisik dan standar operasional.")

    result = {
        "transaction_id": transaction_id,
        "is_anomaly": is_anomaly,
        "anomaly_score": round(anomaly_score, 2),
        "detection_engine": "rule_based_v2_with_ocr",
        "notes": " | ".join(reasons)
    }

    print(f"[Python Rule Engine] Evaluasi selesai untuk Transaction ID {transaction_id}. Anomali: {is_anomaly}")
    return result

"""
Feedback Learning Service (Human-In-The-Loop Active Learning)
Layanan ini secara otomatis memanfaatkan data tabel `fuel_transactions`:
- `admin_feedback_is_anomaly` (Ground Truth Admin)
- `admin_feedback_notes`
Untuk melakukan kalibrasi toleransi ambang batas (thresholds) dan mencegah False Positive berulang.
"""

from decimal import Decimal
from typing import Dict, Any
from ..config.db_client import get_db_connection

# Cache memori untuk penyesuaian dinamis (dapat di-refresh tanpa restart server)
_DYNAMIC_CALIBRATION_CACHE = {
    "odo_diff_threshold": Decimal("500"),  # Default toleransi odometer
    "liter_diff_threshold": Decimal("0.15"),  # Default toleransi liter struk (15%)
    "cost_diff_threshold": Decimal("0.15"),   # Default toleransi harga struk (15%)
    "learned_from_feedbacks": 0
}


def load_feedback_calibration() -> Dict[str, Any]:
    """
    Menganalisis riwayat umpan balik admin dari PostgreSQL:
    1. Menghitung tingkat False Positive (Admin menandai False saat ML menebak True)
    2. Jika admin sering memvalidasi bahwa selisih pembacaan OCR adalah wajar,
       maka toleransi ambang batas dinaikkan secara adaptif.
    """
    global _DYNAMIC_CALIBRATION_CACHE
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Ambil data transaksi yang sudah diverifikasi oleh admin
            cur.execute("""
                SELECT 
                    ml_is_anomaly, 
                    admin_feedback_is_anomaly, 
                    ocr_vs_input_odo_before_diff,
                    rule_labels
                FROM fuel_transactions
                WHERE admin_feedback_is_anomaly IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 200;
            """)
            feedbacks = cur.fetchall()

            if not feedbacks:
                return _DYNAMIC_CALIBRATION_CACHE

            false_positives_odo = 0
            max_tolerated_odo_diff = Decimal("500")

            for fb in feedbacks:
                ml_flag = fb.get("ml_is_anomaly")
                admin_flag = fb.get("admin_feedback_is_anomaly")
                odo_diff = fb.get("ocr_vs_input_odo_before_diff")

                # Kasus False Positive: ML mendeteksi anomali, tapi Admin memvalidasi NORMAL
                if ml_flag is True and admin_flag is False:
                    false_positives_odo += 1
                    if odo_diff and Decimal(str(odo_diff)) > max_tolerated_odo_diff:
                        # Naikkan batas jika deviasi tersebut dianggap wajar oleh admin
                        max_tolerated_odo_diff = min(Decimal("1500"), Decimal(str(odo_diff)) + Decimal("50"))

            # Update cache kalibrasi
            _DYNAMIC_CALIBRATION_CACHE["odo_diff_threshold"] = max_tolerated_odo_diff
            _DYNAMIC_CALIBRATION_CACHE["learned_from_feedbacks"] = len(feedbacks)
            
            print(f"[Active Learning] Terkalibrasi dari {len(feedbacks)} feedback admin. "
                  f"Threshold Odometer diadaptasi menjadi: {max_tolerated_odo_diff} km.")

            return _DYNAMIC_CALIBRATION_CACHE
    except Exception as e:
        print(f"[Active Learning Error] Gagal memuat kalibrasi feedback: {e}")
        return _DYNAMIC_CALIBRATION_CACHE
    finally:
        if conn:
            conn.close()


def should_override_anomaly_by_feedback(tx_dict: dict, rule_labels: list) -> tuple[bool, str]:
    """
    Mengecek apakah transaksi saat ini telah dikoreksi oleh Admin sebagai *normal*.
    - Jika admin menandai `admin_feedback_is_anomaly` = false, semua label anomali yang dihasilkan
      oleh rule engine akan di‑override, terlepas dari nilai deviasi.
    - Selain itu, tetap mempertahankan logika toleransi odometer berbasis feedback
      historis (threshold adaptif).
    Mengembalikan tuple `(is_overridden, note)`.
    """
    # 1. Jika admin secara eksplisit menolak anomali, override langsung
    admin_flag = tx_dict.get("admin_feedback_is_anomaly")
    if admin_flag is not None and admin_flag is False:
        return True, "Admin feedback: transaction marked as normal, overriding all anomaly labels."

    # 2. Pastikan cache kalibrasi terbaru untuk tolerant‑threshold logic
    calib = load_feedback_calibration()

    # 3. Pengecekan False Positive Odometer OCR berbasis toleransi adaptif
    if "ANOMALI_OCR_ODOMETER" in rule_labels:
        odo_diff = tx_dict.get("ocr_vs_input_odo_before_diff")
        if odo_diff is not None:
            odo_diff_dec = Decimal(str(odo_diff))
            if odo_diff_dec <= calib["odo_diff_threshold"]:
                return True, f"Auto-corrected: Deviasi OCR odometer ({odo_diff_dec} km) ditoleransi berdasarkan riwayat feedback admin."

    return False, ""

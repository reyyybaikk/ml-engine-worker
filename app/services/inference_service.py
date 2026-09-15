import os
import json
from app.config.db_client import get_db_connection
from app.services.validation_service import validate_transaction_data
from app.services.feature_service import extract_features
from app.preprocessing.preprocessing_service import preprocess_features
from app.services.rule_engine import evaluate_transaction_rules
from app.services.ocr_service import read_odometer, read_receipt
from app.services.notification_service import send_anomaly_notification

def run_inference_for_transaction(transaction_id: int) -> dict:
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # 1. Ambil data transaksi, data kendaraan, dan KONTAK ADMIN WILAYAH
        # Menggunakan pencarian fleksibel agar 'UL BANJARMASIN' cocok dengan 'Banjarmasin'
        query_current = """
            SELECT 
                ft.*,
                v.fuel_tank_capacity, v.fuel_consumption_rate as target_rate, v.license_plate, v.ul_nd,
                u.full_name AS driver_name, u.whatsapp_number AS driver_whatsapp,
                rc.admin_whatsapp AS regional_admin_phone
            FROM fuel_transactions ft
            JOIN vehicles v ON ft.vehicle_id = v.id
            JOIN users u ON ft.driver_id = u.id
            LEFT JOIN region_contacts rc ON
                LOWER(REPLACE(v.ul_nd, 'UL ', '')) = LOWER(REPLACE(rc.ul_nd, 'UL ', ''))
            WHERE ft.id = %s;
        """
        cursor.execute(query_current, (transaction_id,))
        tx_dict = cursor.fetchone()

        if not tx_dict:
            raise ValueError(f"Transaction ID {transaction_id} tidak ditemukan.")

        # 2. Ambil Stand Odo dari transaksi SEBELUMNYA untuk menghitung efisiensi (Baseline)
        query_prev = """
            SELECT odometer FROM fuel_transactions
            WHERE vehicle_id = %s AND id < %s
            ORDER BY id DESC LIMIT 1;
        """
        cursor.execute(query_prev, (tx_dict['vehicle_id'], transaction_id))
        prev_tx = cursor.fetchone()
        last_odo = prev_tx['odometer'] if prev_tx else tx_dict['odometer']

        # 3. Jalankan Full ML/Rule Pipeline
        # a. Feature Engineering (Menggabungkan data input & OCR)
        features = extract_features(tx_dict)

        # b. Preprocessing (Normalisasi data)
        preprocessed = preprocess_features(features)

        # c. Rule Engine Evaluation (Tangki, Harga, OCR Match, Fraud)
        rule_results = evaluate_transaction_rules(preprocessed)

        # 4. Perhitungan Konsumsi BBM Riil (Baseline Efficiency Rule)
        distance = float(tx_dict['odometer']) - float(last_odo)
        fuel_amount = float(tx_dict['fuel_amount'])
        real_consumption = distance / fuel_amount if fuel_amount > 0 else 0
        target_rate = float(tx_dict['target_rate'] or 0)

        # Cek Anomali Efisiensi (Boros)
        efficiency_anomaly = real_consumption < target_rate and distance > 0

        # 5. Konsolidasi Hasil (Gabungkan Rule Engine + Efficiency Check)
        is_anomaly = rule_results["is_anomaly"] or efficiency_anomaly

        # Gabungkan catatan
        final_notes = rule_results["notes"]
        if efficiency_anomaly:
            eff_note = f"[Rule: Efisiensi] Konsumsi riil {real_consumption:.2f} km/l < Target {target_rate} km/l."
            final_notes = f"{eff_note} | {final_notes}" if final_notes != "NORMAL" else eff_note

        anomaly_score = max(rule_results["anomaly_score"], 1.0 if efficiency_anomaly else 0.0)

        # 6. Simpan hasil akhir ke database
        cursor.execute("""
            UPDATE fuel_transactions
            SET ml_is_anomaly = %s,
                ml_anomaly_score = %s,
                real_fuel_consumption = %s,
                notes = %s,
                status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            is_anomaly,
            anomaly_score,
            real_consumption,
            final_notes,
            "REVIEW" if is_anomaly else "COMPLETED",
            transaction_id
        ))
        connection.commit()

        # 7. Siapkan Response & Kirim Notifikasi jika Anomali
        result = {
            "transaction_id": transaction_id,
            "is_anomaly": is_anomaly,
            "anomaly_score": anomaly_score,
            "notes": final_notes,
            "transaction_full": tx_dict
        }

        if is_anomaly:
            print(f"[ML Engine] ANOMALI KRITIS TERDETEKSI pada TX #{transaction_id}!")
            send_anomaly_notification(tx_dict, result)

        return result

    except Exception as e:
        if connection: connection.rollback()
        print(f"[ML Error] {e}")
        raise e
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

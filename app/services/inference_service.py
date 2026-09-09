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

        # 1. Ambil data transaksi saat ini
        query_current = """
            SELECT 
                ft.*,
                v.fuel_tank_capacity, v.fuel_consumption_rate as target_rate, v.license_plate,
                u.full_name AS driver_name, u.whatsapp_number AS driver_whatsapp
            FROM fuel_transactions ft
            JOIN vehicles v ON ft.vehicle_id = v.id
            JOIN users u ON ft.driver_id = u.id
            WHERE ft.id = %s;
        """
        cursor.execute(query_current, (transaction_id,))
        tx_dict = cursor.fetchone()

        if not tx_dict:
            raise ValueError(f"Transaction ID {transaction_id} tidak ditemukan.")

        # 2. Ambil Stand Odo dari transaksi SEBELUMNYA (Last Filling)
        query_prev = """
            SELECT odometer FROM fuel_transactions
            WHERE vehicle_id = %s AND id < %s
            ORDER BY id DESC LIMIT 1;
        """
        cursor.execute(query_prev, (tx_dict['vehicle_id'], transaction_id))
        prev_tx = cursor.fetchone()

        last_odo = prev_tx['odometer'] if prev_tx else tx_dict['odometer'] # Fallback ke odo sekarang jika data pertama

        # 3. Hitung Konsumsi BBM Riil
        distance = float(tx_dict['odometer']) - float(last_odo)
        fuel_amount = float(tx_dict['fuel_amount'])

        # Hindari pembagian dengan nol
        real_consumption = distance / fuel_amount if fuel_amount > 0 else 0
        target_rate = float(tx_dict['target_rate'] or 0)

        # Tentukan Status Anomali (Jika konsumsi lebih boros/kecil dari target km/liter)
        is_anomaly = real_consumption < target_rate and distance > 0
        status_label = "ANOMALI" if is_anomaly else "NORMAL"

        notes = f"Jarak: {distance} km | Konsumsi: {real_consumption:.2f} km/l | Target: {target_rate} km/l"
        if is_anomaly:
            notes = f"[BOROS] {notes}"

        # 4. Simpan hasil ke database Supabase
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
            1.0 if is_anomaly else 0.0,
            real_consumption,
            notes,
            "REVIEW" if is_anomaly else "COMPLETED",
            transaction_id
        ))
        connection.commit()

        # 5. Kirim WhatsApp jika Anomali
        result = {
            "is_anomaly": is_anomaly,
            "anomaly_score": 1.0 if is_anomaly else 0.0,
            "notes": notes,
            "transaction_full": tx_dict
        }

        if is_anomaly:
            print(f"[ML Engine] Anomali terdeteksi! Mengirim WA ke Admin dan Driver...")
            send_anomaly_notification(tx_dict, result)

        return result

    except Exception as e:
        if connection: connection.rollback()
        print(f"[ML Error] {e}")
        raise e
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

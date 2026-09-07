import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi Fonnte API
FONNTE_API_URL = "https://api.fonnte.com/send"
WA_API_KEY = os.getenv("WA_API_KEY", "")
WA_ADMIN_PHONE = os.getenv("WA_ADMIN_PHONE", "")


def send_anomaly_notification(transaction: dict, inference_result: dict) -> bool:
    """
    Mengirim notifikasi WhatsApp ke admin jika anomali terdeteksi.
    
    Args:
        transaction: Data transaksi dari PostgreSQL (driver_name, license_plate, dll)
        inference_result: Hasil analisis ML (is_anomaly, anomaly_score, notes)
    
    Returns:
        True jika berhasil dikirim, False jika gagal.
    """
    if not WA_API_KEY or WA_API_KEY == "GANTI_DENGAN_TOKEN_FONNTE_ANDA":
        print("[WA Notification] ⚠️  WA_API_KEY belum dikonfigurasi di .env, notifikasi dilewati.")
        return False

    if not WA_ADMIN_PHONE:
        print("[WA Notification] ⚠️  WA_ADMIN_PHONE belum dikonfigurasi di .env, notifikasi dilewati.")
        return False

    message = _format_anomaly_message(transaction, inference_result)

    try:
        response = requests.post(
            FONNTE_API_URL,
            headers={"Authorization": WA_API_KEY},
            data={
                "target": WA_ADMIN_PHONE,
                "message": message,
                "countryCode": "62"  # Indonesia
            },
            timeout=10  # Timeout 10 detik agar worker tidak hang
        )

        if response.status_code == 200:
            resp_json = response.json()
            if resp_json.get("status"):
                print(f"[WA Notification] ✅ Notifikasi anomali berhasil dikirim ke {WA_ADMIN_PHONE}")
                return True
            else:
                print(f"[WA Notification] ❌ Fonnte menolak pesan: {resp_json}")
                return False
        else:
            print(f"[WA Notification] ❌ HTTP Error {response.status_code}: {response.text}")
            return False

    except requests.Timeout:
        print("[WA Notification] ❌ Timeout saat menghubungi Fonnte API.")
        return False
    except Exception as e:
        print(f"[WA Notification] ❌ Error tidak terduga: {e}")
        return False


def _format_anomaly_message(transaction: dict, inference_result: dict) -> str:
    """
    Membuat format pesan WhatsApp yang informatif untuk admin.
    """
    transaction_id = transaction.get("id", "?")
    driver_name = transaction.get("driver_name", "Tidak diketahui")
    license_plate = transaction.get("license_plate", "?")
    fuel_amount = transaction.get("fuel_amount", "?")
    total_cost = transaction.get("total_cost", "?")
    odometer = transaction.get("odometer", "?")
    filling_source = transaction.get("filling_source", "?")
    created_at = transaction.get("created_at", datetime.now())
    anomaly_score = inference_result.get("anomaly_score", 0)
    reasons = inference_result.get("notes", "-")

    # Format tanggal Indonesia
    if isinstance(created_at, datetime):
        date_str = created_at.strftime("%d %B %Y, %H:%M WIB")
    else:
        date_str = str(created_at)

    # Format harga Rupiah
    try:
        cost_formatted = f"Rp {int(float(total_cost)):,}".replace(",", ".")
    except Exception:
        cost_formatted = str(total_cost)

    message = f"""🚨 *ALERT: ANOMALI BBM TERDETEKSI*

📋 *Detail Transaksi #{ transaction_id }*
👤 Driver  : {driver_name}
🚗 Kendaraan: {license_plate}
📅 Tanggal : {date_str}
⛽ BBM     : {fuel_amount} liter ({filling_source})
💰 Total   : {cost_formatted}
🛣️ Odometer: {odometer} km

⚠️ *Hasil Analisis ML*
Skor Anomali : {anomaly_score:.2f} / 1.00
Alasan       : {reasons}

🔍 Mohon segera verifikasi transaksi ini melalui Dashboard Admin.

_Pesan otomatis dari Fuel Monitoring System_"""

    return message

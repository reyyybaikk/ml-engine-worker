import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from ..config.db_client import get_db_connection

load_dotenv()

FONNTE_API_URL = "https://app.whacenter.com/api/send"

def _load_wa_config():
    """Return WA configuration (admin phone, device ID) from environment.
    API key is not used — Whacenter only needs device ID.
    """
    return (
        os.getenv("WA_ADMIN_PHONE", ""),
        os.getenv("WA_DEVICE_ID", "whacenter"),
    )

def _get_region_admin_phone(region_name: str) -> str:
    """Fetch the WhatsApp admin phone for the given region from `region_contacts` table.
    Returns empty string if not found or on DB error.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Bersihkan prefix 'Unit Layanan ' agar cocok dengan database jika ditulis tanpa prefix
            clean_region = region_name.replace("Unit Layanan ", "").strip()
            # Gunakan ILIKE agar pencocokan case-insensitive dan toleran terhadap teks
            cur.execute(
                "SELECT admin_whatsapp FROM region_contacts WHERE ul_nd ILIKE %s LIMIT 1",
                (f"%{clean_region}%",)
            )
            row = cur.fetchone()
            if row:
                return row.get("admin_whatsapp", "") if isinstance(row, dict) else row[0]
            return ""
    except Exception as e:
        print(f"[DB Error] Gagal ambil admin WA untuk region {region_name}: {e}")
        return ""

def send_anomaly_notification(transaction: dict, inference_result: dict) -> bool:
    """Send WhatsApp notification ONLY to the region-specific admin when anomaly detected.
    The admin phone is fetched from `region_contacts` table based on the transaction's region.
    If not found, it falls back to the default WA_ADMIN_PHONE.
    """
    # Load WA configuration (admin phone & device ID) at runtime
    WA_ADMIN_PHONE, _ = _load_wa_config()

    # Resolve admin phone number
    admin_phone = ""
    region = transaction.get("region") or transaction.get("region_name")
    
    if region:
        admin_phone = _get_region_admin_phone(region)
        if admin_phone:
            print(f"[WA Info] Mengirim notifikasi ke Admin Region: {region} ({admin_phone})")
            
    if not admin_phone:
        print(f"[WA Info] Admin region '{region}' tidak ada, menggunakan Admin Pusat/Default.")
        admin_phone = WA_ADMIN_PHONE

    if not admin_phone:
        print("[WA Error] Tidak ada nomor admin yang bisa dihubungi (region maupun default).")
        return False

    message = _format_anomaly_message(transaction, inference_result)

    # 1. Send ONLY to Admin
    admin_success = _send_to_target(admin_phone, message)

    return admin_success

def _send_to_target(target: str, message: str) -> bool:
    if not target:
        return False
    # Load device ID at runtime
    _, device_id = _load_wa_config()
    try:
        # Whacenter API expects form-data with device_id, number, and message
        payload = {
            "device_id": device_id,
            "number": target,
            "message": message,
        }
        response = requests.post(
            FONNTE_API_URL,
            data=payload,
            timeout=10,
        )
        # Log status and body for troubleshooting
        print(f"[WA Debug] Sent to {target}, status={response.status_code}, body={response.text[:200]}")
        if response.status_code != 200:
            print(f"[WA Error] Gagal kirim ke {target}: status {response.status_code}, response={response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"[WA Error] Gagal kirim ke {target}: {e}")
        return False

def _format_anomaly_message(transaction: dict, inference_result: dict) -> str:
    driver_name = transaction.get("driver_name", "Tidak diketahui")
    license_plate = transaction.get("license_plate", "?")
    fuel_amount = transaction.get("fuel_amount", "?")
    odometer = transaction.get("odometer", "?")
    reasons = inference_result.get("notes", "-")

    message = (
        f"🚨 *ALERT: ANOMALI BBM TERDETEKSI*\n\n"
        f"👤 Driver  : {driver_name}\n"
        f"🚗 Kendaraan: {license_plate}\n"
        f"⛽ BBM     : {fuel_amount} liter\n"
        f"🛣️ Odometer: {odometer} km\n\n"
        f"⚠️ *Hasil Analisis*\n{reasons}\n\n"
        f"🔍 Segera verifikasi transaksi ini di Dashboard Admin."
    )
    return message

import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from ..config.db_client import get_db_connection

load_dotenv()

FONNTE_API_URL = "https://app.whacenter.com/api/send"

def _load_wa_config():
    """Return WA configuration (admin phone and device ID) from environment.
    API key is not required for notification on Railway.
    """
    return (
        os.getenv("WA_ADMIN_PHONE", ""),
        os.getenv("WA_DEVICE_ID", "whacenter"),
    )

def _get_region_admin_phone(region_name: str) -> str:
    """Fetch the WhatsApp admin phone for the given region from `region_contact` table.
    Returns empty string if not found or on DB error.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT admin_whatsapp FROM region_contacts WHERE ul_nd = %s LIMIT 1",
                (region_name,)
            )
            row = cur.fetchone()
            return row[0] if row else ""
    except Exception as e:
        print(f"[DB Error] Gagal ambil admin WA untuk region {region_name}: {e}")
        return ""

def send_anomaly_notification(transaction: dict, inference_result: dict) -> bool:
    """Send WhatsApp notification to admin (region‑specific) and driver when anomaly detected.
    The admin phone is resolved in order:
    1. Region‑specific phone from `region_contact` table (if `region`/`region_name` present).
    2. Fallback to `WA_ADMIN_PHONE` env variable.
    """
    # If no API key is set, we can still attempt sending using deviceId only (some APIs allow it).
    # Load WA configuration at runtime
    WA_API_KEY, WA_ADMIN_PHONE, WA_DEVICE_ID = _load_wa_config()
    if not WA_API_KEY:
        print("[WA] API Key belum ada, akan tetap kirim menggunakan deviceId.")
        # Continue without Authorization header
        # Note: This may fail if the API requires the key.


    # Resolve admin phone number
    admin_phone = ""
    region = transaction.get("region") or transaction.get("region_name")
    if region:
        admin_phone = _get_region_admin_phone(region)
    if not admin_phone:
        admin_phone = WA_ADMIN_PHONE

    message = _format_anomaly_message(transaction, inference_result)

    # 1. Send to Admin (region‑specific if available)
    admin_success = _send_to_target(admin_phone, message)

    # 2. Send to Driver (if phone available)
    driver_phone = transaction.get("driver_whatsapp")
    driver_success = False
    if driver_phone:
        driver_message = (
            f"Halo *{transaction.get('driver_name', 'Driver')}*,\n\n"
            f"Terdeteksi pemborosan penggunaan BBM pada kendaraan {transaction.get('license_plate', '-')}.\n\n"
            f"{inference_result.get('notes', '-')}")
        driver_success = _send_to_target(driver_phone, driver_message)

    return admin_success or driver_success

def _send_to_target(target: str, message: str) -> bool:
    if not target:
        return False
    # Load WA configuration at runtime
    api_key, _, device_id = _load_wa_config()
    headers = {} if not api_key else {"Authorization": api_key}
    try:
        response = requests.post(
            FONNTE_API_URL,
            headers=headers,
            data={
                "target": target,
                "message": message,
                "countryCode": "62",
                "deviceId": device_id,
            },
            timeout=10,
        )
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

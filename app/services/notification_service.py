import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi WHACenter (WhatsApp Gateway Berbayar)
WHACENTER_API_URL = "https://app.whacenter.com/api/send"
WA_DEVICE_ID = os.getenv("WA_DEVICE_ID", "")
WA_SUPER_ADMIN_PHONE = os.getenv("WA_ADMIN_PHONE", "") # Fallback jika admin wilayah tidak ada

def send_anomaly_notification(transaction: dict, inference_result: dict) -> bool:
    """
    Mengirim notifikasi WhatsApp ke Admin Wilayah (berdasarkan UL)
    DAN Driver jika anomali terdeteksi.
    """
    if not WA_DEVICE_ID:
        print("[WA] WHACenter Device ID belum ada di .env.")
        return False

    message = _format_anomaly_message(transaction, inference_result)

    # 1. Tentukan Target Admin (Utamakan Admin Wilayah / UL)
    admin_target = transaction.get("regional_admin_phone") or WA_SUPER_ADMIN_PHONE

    admin_success = False
    if admin_target:
        print(f"[WA] Mengirim notifikasi ke Admin Wilayah: {admin_target} (UL: {transaction.get('ul_nd')})")
        admin_success = _send_to_target(admin_target, message)
    else:
        print("[WA Warning] Tidak ada nomor Admin Wilayah maupun Super Admin untuk dikirimi notifikasi.")

    # 2. Kirim ke Driver
    driver_phone = transaction.get("driver_whatsapp")
    driver_success = False
    if driver_phone:
        driver_message = f"Halo *{transaction.get('driver_name')}*,\n\nTerdeteksi pemborosan penggunaan BBM pada kendaraan {transaction.get('license_plate')}.\n\n{inference_result.get('notes')}\n\nMohon gunakan BBM secara bijak sesuai standar perusahaan."
        driver_success = _send_to_target(driver_phone, driver_message)

    return admin_success or driver_success

def _send_to_target(target: str, message: str) -> bool:
    """
    Fungsi internal untuk mengirim pesan via WHACenter API.
    """
    if not target: return False
    try:
        # WHACenter menggunakan parameter device_id, number, dan message
        payload = {
            "device_id": WA_DEVICE_ID,
            "number": target,
            "message": message
        }

        response = requests.post(
            WHACENTER_API_URL,
            data=payload,
            timeout=15
        )

        result_json = response.json()
        if result_json.get("status") is True:
            print(f"[WA Success] Pesan terkirim ke {target}.")
            return True
        else:
            print(f"[WA Failed] Gagal kirim ke {target}: {result_json.get('message')}")
            return False

    except Exception as e:
        print(f"[WA Error] Kesalahan koneksi WHACenter ke {target}: {e}")
        return False

def _format_anomaly_message(transaction: dict, inference_result: dict) -> str:
    transaction_id = transaction.get("id", "?")
    driver_name = transaction.get("driver_name", "Tidak diketahui")
    license_plate = transaction.get("license_plate", "?")
    fuel_amount = transaction.get("fuel_amount", "?")
    odometer = transaction.get("odometer", "?")
    reasons = inference_result.get("notes", "-")

    message = f"""🚨 *ALERT: ANOMALI BBM TERDETEKSI*

👤 Driver  : {driver_name}
🚗 Kendaraan: {license_plate}
⛽ BBM     : {fuel_amount} liter
🛣️ Odometer: {odometer} km

⚠️ *Hasil Analisis*
{reasons}

🔍 Segera verifikasi transaksi ini di Dashboard Admin."""
    return message

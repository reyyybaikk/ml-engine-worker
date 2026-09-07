import os
from app.config.db_client import get_db_connection
from app.services.validation_service import validate_transaction_data
from app.services.feature_service import extract_features
from app.preprocessing.preprocessing_service import preprocess_features
from app.services.rule_engine import evaluate_transaction_rules
from app.services.ocr_service import read_odometer, read_receipt

# Base path folder uploads backend
UPLOADS_BASE_PATH = os.getenv("UPLOADS_BASE_PATH", "../backend/uploads/")


def _resolve_photo_path(filename: str) -> str | None:
    """Mengubah nama file menjadi absolute path yang dapat dibaca OCR."""
    if not filename:
        return None
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename
    
    # 1. Coba path dari env / default relative
    candidate1 = os.path.join(UPLOADS_BASE_PATH, filename)
    if os.path.exists(candidate1):
        return os.path.abspath(candidate1)
    
    # 2. Coba path absolute berdasarkan root proyek
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidate2 = os.path.abspath(os.path.join(current_dir, "../../../backend/uploads", filename))
    if os.path.exists(candidate2):
        return candidate2

    return candidate1


def run_inference_for_transaction(transaction_id: int) -> dict:
    """
    Menjalankan seluruh pipeline inference untuk sebuah transaction_id:
    1. Mengambil data transaksi & master kendaraan dari PostgreSQL.
    2. Validasi input.
    3. OCR foto odometer sebelum, foto struk, foto odometer sesudah.
    4. Ekstraksi fitur (termasuk fitur OCR).
    5. Preprocessing data.
    6. Evaluasi Rule Engine (Anomaly Detection).
    
    Returns: dict hasil inference lengkap termasuk data transaksi untuk notifikasi WA.
    """
    connection = None
    cursor = None
    try:
        # 1. Buka koneksi database PostgreSQL
        connection = get_db_connection()
        cursor = connection.cursor()

        # Query gabungkan data transaksi + master kendaraan (termasuk binary foto BYTEA)
        query = """
            SELECT 
                ft.id,
                ft.vehicle_id,
                ft.driver_id,
                ft.fuel_amount,
                ft.total_cost,
                ft.odometer,
                ft.filling_source,
                ft.fuel_type,
                ft.odometer_photo_data,
                ft.receipt_photo_data,
                ft.odometer_after_photo_data,
                ft.receipt_photo_hash,
                ft.created_at,
                v.fuel_tank_capacity,
                v.fuel_consumption_rate,
                v.license_plate,
                u.full_name AS driver_name
            FROM fuel_transactions ft
            JOIN vehicles v ON ft.vehicle_id = v.id
            JOIN users u ON ft.driver_id = u.id
            WHERE ft.id = %s;
        """
        cursor.execute(query, (transaction_id,))
        transaction_data = cursor.fetchone()

        if not transaction_data:
            raise ValueError(f"Transaction ID {transaction_id} tidak ditemukan di database atau relasi kendaraan invalid.")

        # Konversi RealDictRow ke dictionary biasa
        tx_dict = dict(transaction_data)

        # Cek apakah hash nota sudah pernah ada di transaksi sebelumnya (Anti-Fraud)
        receipt_hash = tx_dict.get("receipt_photo_hash")
        duplicate_receipt_tx_id = None
        if receipt_hash:
            cursor.execute(
                "SELECT id FROM fuel_transactions WHERE receipt_photo_hash = %s AND id != %s ORDER BY id ASC LIMIT 1;",
                (receipt_hash, transaction_id)
            )
            dup = cursor.fetchone()
            if dup:
                duplicate_receipt_tx_id = dup["id"] if isinstance(dup, dict) else dup[0]

        tx_dict["duplicate_receipt_tx_id"] = duplicate_receipt_tx_id

        # 2. Input Validation
        validate_transaction_data(tx_dict)

        # 3. OCR — hanya baca foto struk/nota SPBU (Odometer tidak perlu di-OCR)
        receipt_input = tx_dict.get("receipt_photo_data")

        print(f"[Python Inference] Memulai OCR Nota/Struk untuk Transaction ID {transaction_id}...")
        ocr_receipt = read_receipt(receipt_input)

        # Merge hasil OCR ke dalam data transaksi
        tx_dict["ocr_liters"] = ocr_receipt.get("liters") if ocr_receipt else None
        tx_dict["ocr_total_cost"] = ocr_receipt.get("total_cost") if ocr_receipt else None
        tx_dict["ocr_fuel_type"] = ocr_receipt.get("fuel_type") if ocr_receipt else None
        tx_dict["ocr_receipt_data"] = ocr_receipt  # Simpan raw untuk DB

        print(f"[Python Inference] OCR Nota selesai — Struk: {ocr_receipt}")

        # 4. Feature Engineering
        features = extract_features(tx_dict)

        # 5. Data Preprocessing
        preprocessed = preprocess_features(features)

        # 6. Rule Engine Evaluation (Inference Prediction)
        inference_result = evaluate_transaction_rules(preprocessed)

        # Tambahkan data transaksi lengkap ke result agar fuel_worker bisa kirim WA
        inference_result["transaction_full"] = tx_dict
        inference_result["ocr_receipt_data"] = ocr_receipt

        print(f"[Python Inference] Berhasil menyelesaikan analisis untuk Transaction ID {transaction_id}.")
        return inference_result

    except Exception as e:
        print(f"[Python Inference Error] Gagal memproses Transaction ID {transaction_id}: {e}")
        raise e
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
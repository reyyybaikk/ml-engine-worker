import json
import time
import redis
from app.config.redis_client import redis_client
from app.config.db_client import get_db_connection
from app.services.inference_service import run_inference_for_transaction

def save_inference_result_to_db(result: dict):
    """
    Menyimpan hasil analisis anomali dari Inference Engine kembali ke PostgreSQL.
    Mengupdate kolom 'notes' pada tabel fuel_transactions.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        transaction_id = result.get("transaction_id")
        is_anomaly = result.get("is_anomaly")
        anomaly_score = result.get("anomaly_score")
        notes = result.get("notes")

        # Format teks catatan hasil analisis AI/Baseline Engine
        status_label = "ANOMALI TERDETEKSI" if is_anomaly else "NORMAL"
        updated_notes = f"[{status_label}] Skor: {anomaly_score} | {notes}"

        query = """
            UPDATE fuel_transactions 
            SET notes = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s;
        """
        cursor.execute(query, (updated_notes, transaction_id))
        connection.commit()
        print(f"[Python Worker] Berhasil memperbarui database untuk Transaction ID {transaction_id} (Status: {status_label}).")

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"[Python Worker DB Error] Gagal menyimpan hasil ke database: {e}")
        raise e
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def start_worker():
    """
    Fungsi utama worker yang berjalan secara terus-menerus (infinite loop)
    mendengarkan antrean dari Redis key 'fuel_queue'.
    """
    print("==================================================")
    print("[Python Worker] 🚀 Memulai Anomaly Detection Worker...")
    print("[Python Worker] Menunggu job baru dari Redis ('fuel_queue')...")
    print("==================================================")

    last_heartbeat = time.time()
    while True:
        try:
            # Heartbeat setiap 30 detik (lebih sering agar kita tahu worker hidup)
            if time.time() - last_heartbeat > 30:
                print(f"[Python Worker] Heartbeat: Menunggu di antrean 'fuel_queue' (Status Redis: {redis_client.ping()})...", flush=True)
                last_heartbeat = time.time()

            result = redis_client.brpop("fuel_queue", timeout=10)
            
            if result:
                queue_name, raw_data = result
                print(f"[Python Worker] 📥 RAW DATA DITERIMA: {raw_data}", flush=True)

                job_payload = json.loads(raw_data)
                transaction_id = job_payload.get("transactionId")

                job_payload = json.loads(raw_data)
                transaction_id = job_payload.get("transactionId")

                print(f"\n[Python Worker] 📥 MENERIMA JOB! Transaction ID: {transaction_id}", flush=True)

                # 1. Jalankan Inference Pipeline
                inference_result = run_inference_for_transaction(transaction_id)

                # 2. Simpan Hasil ke PostgreSQL
                save_inference_result_to_db(inference_result)

                print(f"[Python Worker] ✅ Job Transaction ID {transaction_id} selesai diproses.", flush=True)

        except KeyboardInterrupt:
            print("\n[Python Worker] Worker dihentikan.", flush=True)
            break
        except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError):
            continue
        except Exception as e:
            print(f"[Python Worker Error] Terjadi kesalahan kritis: {str(e)}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    start_worker()
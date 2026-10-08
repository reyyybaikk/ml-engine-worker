# file: app/workers/fuel_worker.py
"""Fuel analysis worker.
This module provides two entry points:
- ``process_one_job()`` – pulls **one** job from Redis, runs inference, stores the result, and returns ``True`` if a job was processed.
- ``start_worker()`` – an infinite loop used for local development. It repeatedly calls ``process_one_job`` and prints heart‑beats.
Both functions reuse the shared ``redis_client`` and PostgreSQL connection utilities.
"""

import json
import time
import redis
from app.config.redis_client import redis_client
from app.config.db_client import get_db_connection
from app.services.inference_service import run_inference_for_transaction
from fastapi import FastAPI, HTTPException
import uvicorn

app = FastAPI(title="ML Engine Worker", version="1.0.0")


def _normalize_transaction_id(payload):
    """Normalizes a Redis BullMQ payload into an integer transaction_id."""
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], dict):
            payload = payload["data"]
        for key in ("transactionId", "transaction_id"):
            if key in payload:
                payload = payload[key]
                break
        else:
            payload = None

    if payload is None:
        return None

    try:
        return int(payload)
    except (TypeError, ValueError):
        raise ValueError(f"Unsupported payload format received from Redis: {payload}")


def save_inference_result_to_db(result: dict) -> None:
    """Persist inference result back to the ``fuel_transactions`` table.
    The function updates the ``notes`` column with a human‑readable status label
    and stores the anomaly flag/score.
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

        if transaction_id is None:
            raise ValueError("Transaction ID tidak ditemukan pada hasil inference")

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
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def process_one_job() -> bool:
    """Fetch **one** job from Redis, run the inference pipeline, and store the result.
    Returns ``True`` when a job was processed, ``False`` when the queue was empty.
    """
    try:
        # Directly read from BullMQ waiting queue (no fallback to legacy fuel_queue).
        result = redis_client.brpop('bull:fuel-analysis-queue:wait', timeout=5)
        if not result:
            return False
        queue_name, job_id = result
        redis_client.delete('fuel_queue')
        print(f"[Python Worker] 📥 DATA DITERIMA dari {queue_name}: job id {job_id}", flush=True)

        job_key = f"bull:fuel-analysis-queue:{job_id}"
        job_data_json = redis_client.hget(job_key, 'data')
        if not job_data_json:
            print(f"[Python Worker] ❗️ Tidak dapat menemukan data job {job_id} di Redis, lewati.", flush=True)
            return False

        job_dict = json.loads(job_data_json)
        payload = job_dict.get('data', job_dict) if isinstance(job_dict, dict) else job_dict

        try:
            transaction_id = _normalize_transaction_id(payload)
        except ValueError:
            print(f"[Python Worker] ⚠️ Payload tidak valid untuk job {job_id}, lewati.", flush=True)
            return False

        if transaction_id is None:
            print(f"[Python Worker] ⚠️ Payload tidak mengandung transactionId, lewati.", flush=True)
            return False

        print(f"\n[Python Worker] 📥 MENERIMA JOB! Transaction ID: {transaction_id}", flush=True)

        max_checks = 12
        try:
            for attempt in range(max_checks):
                try:
                    inference_result = run_inference_for_transaction(transaction_id)
                    break
                except ValueError:
                    if attempt < max_checks - 1:
                        wait_sec = 10
                        print(f"[Python Worker] ⚠️ Transaction {transaction_id} belum ada di DB, menunggu {wait_sec} detik... (coba {attempt+1}/{max_checks})", flush=True)
                        time.sleep(wait_sec)
                    else:
                        raise
        except ValueError:
            print(f"[Python Worker] ⚠️ Transaction {transaction_id} belum ada di DB setelah {max_checks} percobaan, menghentikan job.", flush=True)
            return False
        except Exception as e:
            print(f"[Python Worker] ❗️ Gagal proses transaction {transaction_id}: {e}", flush=True)
            return False

        save_inference_result_to_db(inference_result)
        print(f"[Python Worker] ✅ Job Transaction ID {transaction_id} selesai diproses.", flush=True)
        time.sleep(0.2)
        return True
    except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError):
        # Transient connectivity issue – let the caller decide to retry later.
        return False
    except Exception as e:
        print(f"[Python Worker Error] Terjadi kesalahan kritis: {str(e)}", flush=True)
        time.sleep(2)
        return False


def start_worker() -> None:
    """Local development loop that continuously calls ``process_one_job``.
    Prints a heartbeat every 30 seconds so you can see the process is alive.
    """
    # Clear any stale jobs from both legacy simple queue and BullMQ waiting list
    try:
        redis_client.delete('fuel_queue')
        redis_client.delete('bull:fuel-analysis-queue:wait')
        print("[Python Worker] ✅ Cleared stale queues on startup.", flush=True)
    except Exception as e:
        print(f"[Python Worker] ⚠️ Failed to clear queues on startup: {e}", flush=True)

    print("==================================================")
    print("[Python Worker] 🚀 Memulai Anomaly Detection Worker...")
    print("[Python Worker] Menunggu job baru dari Redis ('fuel_queue') atau BullMQ...")
    print("==================================================")
    last_heartbeat = time.time()
    while True:
        try:
            # Heartbeat every 30 seconds.
            if time.time() - last_heartbeat > 30:
                print(f"[Python Worker] Heartbeat: Menunggu di antrean... (Status Redis: {redis_client.ping()})...", flush=True)
                last_heartbeat = time.time()

            processed = process_one_job()
            if not processed:
                # No job – simply continue; heartbeat will fire later.
                continue
        except KeyboardInterrupt:
            print("\n[Python Worker] Worker dihentikan.", flush=True)
            break
        except Exception as e:
            print(f"[Python Worker Fatal] {str(e)}", flush=True)
            time.sleep(2)

@app.get("/healthz")
async def healthz():
    """Simple health‑check used by Railway or external monitoring."""
    try:
        redis_client.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-job")
async def run_job(payload: dict):
    """Trigger a single job manually (debug purpose)."""
    transaction_id = payload.get("transactionId")
    if not transaction_id:
        raise HTTPException(status_code=400, detail="transactionId wajib ada")
    result = run_inference_for_transaction(int(transaction_id))
    save_inference_result_to_db(result)
    return {"status": "processed", "transactionId": transaction_id}

if __name__ == "__main__":
    start_worker()
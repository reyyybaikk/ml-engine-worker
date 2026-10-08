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
        print(f"[Python Worker] 📥 DATA DITERIMA dari {queue_name}: job id {job_id}", flush=True)
        # Retrieve the actual job payload stored in a hash key
        job_key = f"bull:fuel-analysis-queue:{job_id}"
        job_data_json = redis_client.hget(job_key, 'data')
        if not job_data_json:
            print(f"[Python Worker] ❗️ Tidak dapat menemukan data job {job_id} di Redis, lewati.", flush=True)
            return False
        # Parse the stored job JSON. BullMQ stores the entire job object; the actual payload is under the 'data' field.
        job_dict = json.loads(job_data_json)
        if isinstance(job_dict, dict) and 'data' in job_dict:
            payload = job_dict['data']
        else:
            payload = job_dict
        # BullMQ may wrap the payload inside a "data" field or send a raw integer ID.
        if isinstance(payload, dict):
            if "data" in payload and isinstance(payload["data"], dict):
                transaction_id = payload["data"].get("transactionId")
            else:
                transaction_id = payload.get("transactionId")
        elif isinstance(payload, int):
            transaction_id = payload
        else:
            raise ValueError("Unsupported payload format received from Redis")
        # Validate that we actually got a transaction ID
        if not transaction_id:
            print(f"[Python Worker] ⚠️ Payload tidak mengandung transactionId, lewati.", flush=True)
            return False

        print(f"\n[Python Worker] 📥 MENERIMA JOB! Transaction ID: {transaction_id}", flush=True)

        try:
            # Try inference, polling if transaction not yet present.
            max_checks = 12
            for attempt in range(max_checks):
                try:
                    inference_result = run_inference_for_transaction(transaction_id)
                    break  # success
                except ValueError:
                    if attempt < max_checks - 1:
                        wait_sec = 10
                        print(f"[Python Worker] ⚠️ Transaction {transaction_id} belum ada di DB, menunggu {wait_sec} detik... (coba {attempt+1}/{max_checks})", flush=True)
                        time.sleep(wait_sec)
                    else:
                        raise  # will be caught by outer except ValueError
        except ValueError:
            # After retries still not found – give up on this job to avoid endless loop.
            print(f"[Python Worker] ⚠️ Transaction {transaction_id} belum ada di DB setelah {max_checks} percobaan, menghentikan job.", flush=True)
            # No re‑queue; job will be dropped.
            return False
        except Exception as e:
            # Other unexpected errors – log and abort this job.
            print(f"[Python Worker] ❗️ Gagal proses transaction {transaction_id}: {e}", flush=True)
            return False
        except Exception as e:
            # Other unexpected errors – log and abort this job.
            print(f"[Python Worker] ❗️ Gagal proses transaction {transaction_id}: {e}", flush=True)
            return False
        else:
            save_inference_result_to_db(inference_result)
            print(f"[Python Worker] ✅ Job Transaction ID {transaction_id} selesai diproses.", flush=True)
        # Light rate‑limit to respect Upstash quota.
        time.sleep(0.2)
        return True
    except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as e:
        print(f"[Python Worker Redis Error] Gagal membaca antrean BullMQ: {e}", flush=True)
        return False
    except Exception as e:
        print(f"[Python Worker Error] Terjadi kesalahan kritis: {str(e)}", flush=True)
        time.sleep(2)
        return False


def start_worker() -> None:
    """Local development loop that continuously calls ``process_one_job``.
    Prints a heartbeat every 30 seconds so you can see the process is alive.
    """
    print("==================================================")
    print("[Python Worker] 🚀 Memulai Anomaly Detection Worker...")
    print("[Python Worker] Menunggu job baru dari antrean BullMQ 'fuel-analysis-queue'...", flush=True)
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
from fastapi import FastAPI, HTTPException
from .services.inference_service import run_inference_for_transaction

app = FastAPI(title="Fuel ML Engine", version="1.0.0")

@app.post("/detect")
async def detect(payload: dict):
    """Endpoint yang dipanggil oleh backend untuk mengecek anomali.
    Payload minimal harus berisi `transactionId` (integer).
    """
    try:
        transaction_id = payload.get("transactionId")
        if transaction_id is None:
            raise ValueError("transactionId wajib ada di payload")
        transaction_id = int(transaction_id)
        result = run_inference_for_transaction(transaction_id)
        return {"anomaly": result["is_anomaly"], "score": result["anomaly_score"], "notes": result["notes"]}
    except Exception as e:
        # FastAPI akan mengubah ini menjadi response JSON dengan status 500
        raise HTTPException(status_code=500, detail=str(e))

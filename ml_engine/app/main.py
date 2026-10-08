from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .services.inference_service import run_inference_for_transaction

app = FastAPI(title="Fuel ML Engine", version="1.0.0")


class DetectRequest(BaseModel):
    transactionId: int = Field(..., gt=0)

    @field_validator("transactionId")
    @classmethod
    def validate_transaction_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("transactionId harus lebih besar dari 0")
        return int(value)


@app.post("/detect")
async def detect(payload: DetectRequest):
    """Endpoint yang dipanggil oleh backend untuk mengecek anomali.
    Payload minimal harus berisi `transactionId` (integer).
    """
    try:
        result = run_inference_for_transaction(payload.transactionId)
        return {
            "anomaly": result["is_anomaly"],
            "score": result["anomaly_score"],
            "notes": result["notes"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

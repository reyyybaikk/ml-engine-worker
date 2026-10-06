from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import re
import joblib
import os
import logging

# Import service inference untuk validasi transaksi
from app.services.inference_service import run_inference_for_transaction

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml_engine")

app = FastAPI()

# Middleware ASGI murni untuk menormalkan URL double-slash (//validate/ → /validate/)
class NormalizeSlashMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "/")
            normalized = re.sub(r'/+', '/', path)
            if normalized != path:
                scope["path"] = normalized
        return await self.app(scope, receive, send)

app.add_middleware(NormalizeSlashMiddleware)


# Root endpoint
@app.get("/")
async def root():
    return {"status": "ok", "message": "ML engine is alive"}

# Lazy model loading (global variable)
model = None
MODEL_PATH = os.getenv('MODEL_PATH', 'model.pkl')

def load_model():
    global model
    if model is None:
        if os.path.exists(MODEL_PATH):
            model = joblib.load(MODEL_PATH)
            logger.info("Model loaded from %s", MODEL_PATH)
        else:
            logger.warning("Model file not found at %s, using fallback rules", MODEL_PATH)
            model = None
    return model

# Optional API‑key auth (header X-API-KEY)
def get_api_key(x_api_key: str = Header(None)):
    expected = os.getenv('ML_API_KEY')
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_api_key

# Health‑check endpoint
@app.get("/healthz")
async def healthz():
    status = {"ml_engine": "up"}
    # DB check
    try:
        from app.config.db_client import get_db_connection
        conn = get_db_connection()
        conn.close()
        status["database"] = "up"
    except Exception as e:
        logger.error("DB health check failed: %s", e)
        status["database"] = "down"
    # Redis check
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        r = redis.Redis.from_url(redis_url)
        r.ping()
        status["redis"] = "up"
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        status["redis"] = "down"
    return status

# Validator endpoint – dipanggil backend setelah transaksi dibuat
@app.get("/validate/{transaction_id}")
@app.get("//validate/{transaction_id}")
async def validate_transaction(transaction_id: int, api_key: str = Depends(get_api_key)):
    try:
        load_model()  # pastikan model ter‑load (atau fallback)
        result = run_inference_for_transaction(transaction_id)
        return result
    except Exception as e:
        logger.exception("Error saat validasi transaksi %s", transaction_id)
        raise HTTPException(status_code=500, detail=str(e))

# Model schema untuk endpoint detect (demo)
class Transaction(BaseModel):
    transactionId: int
    amount: float
    fuelType: str
    # add other fields as needed

# Endpoint /detect tetap ada untuk demo atau test manual
@app.post("/detect")
async def detect_anomaly(tx: Transaction):
    logger.info("Menerima transaksi ID: %s, Amount: %s, Fuel: %s", tx.transactionId, tx.amount, tx.fuelType)
    # Gunakan fallback rule bila model belum tersedia
    if load_model() is None:
        anomaly = tx.amount > 1000
        logger.info("Hasil Prediksi (Fallback): %s", anomaly)
        return {"anomaly": anomaly, "transactionId": tx.transactionId}
    try:
        pred = model.predict([[tx.amount]])[0]
        anomaly = bool(pred)
        logger.info("Hasil Prediksi (Model): %s", anomaly)
        return {"anomaly": anomaly, "transactionId": tx.transactionId}
    except Exception as e:
        logger.exception("Error ML Engine pada detect")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os



app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok", "message": "ML engine is alive"}

# Load a dummy model (replace with actual model path)
MODEL_PATH = os.getenv('MODEL_PATH', 'model.pkl')
if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
else:
    model = None  # fallback for development/testing

class Transaction(BaseModel):
    transactionId: int
    amount: float
    fuelType: str
    # add other fields as needed

@app.post("/detect")
async def detect_anomaly(tx: Transaction):
    print(f"📥 Menerima transaksi ID: {tx.transactionId}, Amount: {tx.amount}, Fuel: {tx.fuelType}")
    
    if model is None:
        # Simple rule: amount > 1000 is considered anomaly for demo
        anomaly = tx.amount > 1000
        print(f"🤖 Hasil Prediksi (Fallback): {anomaly}")
        return {"anomaly": anomaly, "transactionId": tx.transactionId}
    
    # Assume model expects a feature vector; adapt as needed
    try:
        # Example: model expects [amount]
        pred = model.predict([[tx.amount]])[0]
        anomaly = bool(pred)
        print(f"🤖 Hasil Prediksi (Model): {anomaly}")
        return {"anomaly": anomaly, "transactionId": tx.transactionId}
    except Exception as e:
        print(f"❌ Error ML Engine: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# file: api/index.py
import os
from mangum import Mangum
from app.main import app   # FastAPI instance defined di app/main.py

# Opsional: buat endpoint root untuk health‑check
@app.get("/", include_in_schema=False)
async def health_check():
    return {"status": "ok"}

# Mangum meng‑wrap FastAPI sehingga Vercel dapat mengeksekusi ASGI
handler = Mangum(app)
# ini
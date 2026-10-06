# file: api/worker.py
"""Vercel cron worker endpoint.
This function is invoked by Vercel every minute (as configured in vercel.json).
It calls `process_one_job()` from the main worker module, which pulls a single
job from Redis, runs inference, stores the result in PostgreSQL, and returns a
status JSON. All `print` statements are captured by Vercel function logs.
"""

from fastapi import FastAPI, HTTPException
from mangum import Mangum

# Import the helper that processes exactly one job.
from app.workers.fuel_worker import process_one_job

app = FastAPI(title="Fuel Worker Cron")

@app.post("/run-worker")
async def run_worker():
    """Endpoint called by Vercel cron.
    Returns ``{"processed": true}`` when a job was handled, otherwise
    ``{"processed": false}``.
    """
    try:
        processed = process_one_job()
        return {"status": "ok", "processed": processed}
    except Exception as e:
        # Raising HTTPException makes the error appear in Vercel logs.
        raise HTTPException(status_code=500, detail=str(e))

# Export the ASGI handler for Vercel.
handler = Mangum(app)

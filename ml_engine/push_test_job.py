# file: push_test_job.py
"""Push a test job onto the Redis queue that the worker consumes.
This script re‑uses the same connection logic as the worker via
`app.config.redis_client.redis_client`, ensuring TLS handling and
environment‑variable parsing are identical.
"""
import json
from app.config.redis_client import redis_client

# Build a simple payload – ganti `transactionId` ke ID yang ada di DB Anda
payload = {"transactionId": 1}

# Push ke antrian yang dipantau worker (`fuel_queue`)
redis_client.lpush("fuel_queue", json.dumps(payload))
print("[push_test_job] Job dikirim ke fuel_queue")
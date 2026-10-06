# file: check_redis_url.py
import os
from dotenv import load_dotenv

load_dotenv()
print("REDIS_URL =", os.getenv("REDIS_URL"))
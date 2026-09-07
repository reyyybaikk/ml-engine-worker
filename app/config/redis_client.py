import os
import redis
from dotenv import load_dotenv

# Memuat konfigurasi dari file .env di ml-engine
load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

def get_redis_client():
    """
    Membuat satu instance koneksi Redis yang dapat di-reuse (Connection Reuse)
    tanpa socket_timeout yang mengganggu fungsi blocking (brpop).
    """
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            decode_responses=True,  # Agar hasil pembacaan berupa string, bukan bytes
            retry_on_timeout=True
        )
        
        # Lakukan tes koneksi awal (PING)
        client.ping()
        print(f"[Python Redis] Berhasil terhubung ke server Redis di {REDIS_HOST}:{REDIS_PORT}")
        return client
        
    except Exception as e:
        print(f"[Python Redis Error] Gagal terhubung ke server Redis: {e}")
        raise e

# Ekspor instance tunggal untuk digunakan di seluruh modul Python
redis_client = get_redis_client()
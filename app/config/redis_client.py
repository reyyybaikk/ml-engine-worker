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
    Membuat satu instance koneksi Redis yang dapat di-reuse.
    Mendukung koneksi via REDIS_URL (Railway/Render) atau host/port individual.
    """
    try:
        redis_url = os.getenv("REDIS_URL")

        if redis_url:
            # Menggunakan URL lengkap jika tersedia (biasanya di Railway)
            client = redis.from_url(
                redis_url,
                decode_responses=True,
                retry_on_timeout=True
            )
            print(f"[Python Redis] Berhasil terhubung menggunakan REDIS_URL")
        else:
            # Fallback ke konfigurasi host/port satuan
            client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD if REDIS_PASSWORD else None,
                decode_responses=True,
                retry_on_timeout=True
            )
            print(f"[Python Redis] Berhasil terhubung ke server Redis di {REDIS_HOST}:{REDIS_PORT}")
        
        # Lakukan tes koneksi awal (PING)
        client.ping()
        return client
        
    except Exception as e:
        print(f"[Python Redis Error] Gagal terhubung ke server Redis: {e}")
        raise e

# Ekspor instance tunggal untuk digunakan di seluruh modul Python
redis_client = get_redis_client()
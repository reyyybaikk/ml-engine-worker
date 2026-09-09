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
            # 1. Bersihkan dari tanda kutip jika ada (penting di Railway/Render)
            redis_url = redis_url.strip('"').strip("'")

            # 2. Pastikan URL memiliki skema rediss:// untuk SSL Upstash
            if not redis_url.startswith(("redis://", "rediss://", "unix://")):
                redis_url = f"rediss://{redis_url}"

            print(f"[Python Redis] Mencoba terhubung ke host: {redis_url.split('@')[-1]}")

            client = redis.from_url(
                redis_url,
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30,
                socket_connect_timeout=10,
                ssl_cert_reqs=None
            )
        else:
            print(f"[Python Redis] WARNING: REDIS_URL tidak ditemukan. Menggunakan fallback {REDIS_HOST}:{REDIS_PORT}")
            client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD if REDIS_PASSWORD else None,
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30,
                socket_keepalive=True
            )

        # Lakukan tes koneksi awal (PING)
        client.ping()
        return client
        
    except Exception as e:
        print(f"[Python Redis Error] Gagal terhubung ke server Redis: {e}")
        raise e

# Ekspor instance tunggal untuk digunakan di seluruh modul Python
redis_client = get_redis_client()
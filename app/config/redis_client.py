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
            # Pastikan URL memiliki skema redis:// agar tidak ValueError
            if not redis_url.startswith(("redis://", "rediss://", "unix://")):
                print(f"[Python Redis] WARNING: REDIS_URL tidak memiliki skema. Menambahkan awalan 'redis://'")
                redis_url = f"redis://{redis_url}"

            print(f"[Python Redis] Menghubungkan menggunakan REDIS_URL...")
            client = redis.from_url(
                redis_url,
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30,  # Ping tiap 30 detik agar koneksi tetap hidup
                socket_connect_timeout=10,
                socket_keepalive=True      # Menjaga TCP socket tidak idle
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
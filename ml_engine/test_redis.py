from app.config.redis_client import redis_client

if __name__ == "__main__":
    try:
        # Menguji perintah PING ke Redis
        response = redis_client.ping()
        print(f"Uji Koneksi Redis Berhasil! Respon server: {response}")
    except Exception as e:
        print(f"Uji Koneksi Redis Gagal: {e}")
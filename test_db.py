from app.config.db_client import get_db_connection

if __name__ == "__main__":
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Lakukan query sederhana untuk tes
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print(f"Uji Koneksi PostgreSQL Berhasil! Waktu server database: {result['now']}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Uji Koneksi PostgreSQL Gagal: {e}")
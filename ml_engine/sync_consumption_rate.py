import os
import csv
import re
from app.config.db_client import get_db_connection

def clean_plate(plate):
    if not plate: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', str(plate)).upper()

def parse_consumption_rate(text):
    """
    Mengubah format "8 - 10" menjadi rata-rata (9.0)
    """
    if not text: return 0.0
    # Mencari semua angka dalam teks
    nums = re.findall(r'(\d+)', str(text))
    if len(nums) == 2:
        # Jika ada dua angka (range), ambil rata-ratanya
        return (float(nums[0]) + float(nums[1])) / 2
    elif len(nums) == 1:
        # Jika hanya satu angka, ambil angka tersebut
        return float(nums[0])
    return 0.0

def sync_consumption():
    data_dir = r"D:\monitoring-bbm-upkal2\fuel-monitoring-system\backend\data"
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]

    vehicles_data = []
    print(f"🔍 Memproses ulang CSV untuk data konsumsi BBM di {data_dir}...")

    for file in csv_files:
        path = os.path.join(data_dir, file)
        with open(path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            for row in rows[3:]:
                if len(row) < 6 or not row[1]: continue

                plate = clean_plate(row[1])
                # Kolom ke-6 (index 5) adalah KONSUMSI BBM / L
                raw_rate = row[5]
                avg_rate = parse_consumption_rate(raw_rate)

                if plate and avg_rate > 0:
                    vehicles_data.append({
                        'plate': plate,
                        'rate': avg_rate
                    })

    print(f"📊 Menemukan {len(vehicles_data)} data konsumsi untuk diperbarui.")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        updated_count = 0
        for v in vehicles_data:
            query = """
                UPDATE vehicles
                SET fuel_consumption_rate = %s
                WHERE REPLACE(license_plate, ' ', '') = %s
            """
            cursor.execute(query, (v['rate'], v['plate']))
            if cursor.rowcount > 0:
                updated_count += 1

        conn.commit()
        print(f"✅ Berhasil memperbarui fuel_consumption_rate untuk {updated_count} kendaraan.")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    sync_consumption()

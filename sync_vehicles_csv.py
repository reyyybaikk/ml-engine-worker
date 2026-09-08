import os
import csv
import re
from app.config.db_client import get_db_connection

def clean_plate(plate):
    if not plate: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', str(plate)).upper()

def extract_capacity(text):
    if not text: return 0.0
    match = re.search(r'(\d+)', str(text))
    return float(match.group(1)) if match else 0.0

def sync_data():
    data_dir = r"D:\monitoring-bbm-upkal2\fuel-monitoring-system\backend\data"
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]

    vehicles_to_update = []

    print(f"🔍 Mencari data di {data_dir}...")

    for file in csv_files:
        path = os.path.join(data_dir, file)
        with open(path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Skip headers (berdasarkan head -n 20 sebelumnya, data mulai dari baris ke-4)
            rows = list(reader)
            for row in rows[3:]: # Mulai dari baris ke-4
                if len(row) < 5 or not row[1]: continue

                plate = clean_plate(row[1])
                v_type = row[2].strip()
                capacity = extract_capacity(row[3])
                fuel_type = row[4].strip()

                if plate:
                    vehicles_to_update.append({
                        'plate': plate,
                        'type': v_type,
                        'capacity': capacity,
                        'fuel': fuel_type
                    })

    print(f"📊 Menemukan {len(vehicles_to_update)} kendaraan unik di CSV.")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        updated_count = 0
        for v in vehicles_to_update:
            # Query update berdasarkan plat nomor (regex matching agar lebih fleksibel)
            # Kita bandingkan plat nomor tanpa spasi
            query = """
                UPDATE vehicles
                SET fuel_tank_capacity = %s,
                    fuel_type = %s,
                    vehicle_type = %s
                WHERE REPLACE(license_plate, ' ', '') = %s
            """
            cursor.execute(query, (v['capacity'], v['fuel'], v['type'], v['plate']))
            if cursor.rowcount > 0:
                updated_count += 1

        conn.commit()
        print(f"✅ Berhasil memperbarui {updated_count} kendaraan di Supabase.")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error saat update database: {e}")

if __name__ == "__main__":
    sync_data()

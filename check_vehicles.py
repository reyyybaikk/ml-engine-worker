from app.config.db_client import get_db_connection
import json

def check_vehicles():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch some vehicles to compare
        cursor.execute("SELECT license_plate, vehicle_type, fuel_tank_capacity, fuel_type FROM vehicles LIMIT 5")
        vehicles = cursor.fetchall()

        print("Current data in Supabase (first 5):")
        for v in vehicles:
            print(f"Plate: {v['license_plate']}, Type: {v['vehicle_type']}, Capacity: {v['fuel_tank_capacity']}, Fuel: {v['fuel_type']}")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_vehicles()

from app.services.feature_service import extract_features

if __name__ == "__main__":
    print("--- Menguji Feature Engineering ---")
    sample_data = {
        "id": 202,
        "fuel_amount": 40.0,
        "total_cost": 400000.0,
        "fuel_tank_capacity": 65.0
    }
    
    try:
        extracted = extract_features(sample_data)
        print("Hasil Ekstraksi Fitur:")
        for key, value in extracted.items():
            print(f" - {key}: {value}")
        print("Feature Engineering Test: BERHASIL")
    except Exception as e:
        print(f"Feature Engineering Test: GAGAL -> {e}")
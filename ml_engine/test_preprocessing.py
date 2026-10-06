from app.preprocessing.preprocessing_service import preprocess_features

if __name__ == "__main__":
    print("--- Menguji Data Preprocessing ---")
    
    # Simulasi data mentah fitur yang memiliki potensi nilai tidak lengkap / None
    raw_extracted_features = {
        "transaction_id": 303,
        "fuel_amount": 50.0,
        "total_cost": None,  # Simulasi data kosong/None dari database
        "fuel_tank_capacity": 65.0,
        "cost_per_liter": 0.0,
        "tank_fill_ratio": 76.92
    }
    
    try:
        clean_data = preprocess_features(raw_extracted_features)
        print("Hasil Preprocessing Data:")
        for key, value in clean_data.items():
            print(f" - {key}: {value} (Tipe: {type(value).__name__})")
        print("Preprocessing Test: BERHASIL")
    except Exception as e:
        print(f"Preprocessing Test: GAGAL -> {e}")
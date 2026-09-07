from app.services.validation_service import validate_transaction_data

if __name__ == "__main__":
    print("--- Menguji Validasi Data (Skenario Normal) ---")
    valid_data = {
        "id": 101,
        "fuel_amount": 45.0,
        "fuel_tank_capacity": 65.0
    }
    try:
        validate_transaction_data(valid_data)
        print("Skenario Normal: BERHASIL\n")
    except Exception as e:
        print(f"Skenario Normal: GAGAL -> {e}\n")

    print("--- Menguji Validasi Data (Skenario Error: Liter Negatif) ---")
    invalid_data = {
        "id": 102,
        "fuel_amount": -5.0,
        "fuel_tank_capacity": 65.0
    }
    try:
        validate_transaction_data(invalid_data)
    except ValueError as e:
        print(f"Skenario Error tertangkap dengan sukses: {e}")
        print("Skenario Error: BERHASIL")
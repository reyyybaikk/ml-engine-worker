def validate_transaction_data(data: dict) -> bool:
    """
    Melakukan validasi terhadap data transaksi dan master kendaraan 
    yang ditarik dari database sebelum diproses oleh baseline engine.
    """
    if not data:
        raise ValueError("Data transaksi tidak boleh kosong atau bernilai None.")

    # 1. Validasi ID Transaksi
    transaction_id = data.get("id")
    if not transaction_id or not isinstance(transaction_id, int):
        raise ValueError(f"Invalid transaction_id: {transaction_id}. Harus berupa angka integer.")

    # 2. Validasi Jumlah BBM (Fuel Amount)
    fuel_amount = data.get("fuel_amount")
    if fuel_amount is None:
        raise ValueError(f"Transaction ID {transaction_id}: Kolom fuel_amount tidak ditemukan.")
    
    try:
        fuel_amount_float = float(fuel_amount)
    except (ValueError, TypeError):
        raise ValueError(f"Transaction ID {transaction_id}: fuel_amount harus berupa angka numerik.")
        
    if fuel_amount_float <= 0:
        raise ValueError(f"Transaction ID {transaction_id}: fuel_amount tidak boleh bernilai nol atau negatif ({fuel_amount_float}).")

    # 3. Validasi Kapasitas Tangki Kendaraan (Dari Data Master)
    tank_capacity = data.get("fuel_tank_capacity")
    if tank_capacity is None:
        print(f"[Python Validation Warning] Transaction ID {transaction_id}: Kapasitas tangki null di database, menggunakan default 50.0 Liter.")
        data["fuel_tank_capacity"] = 50.0
    else:
        try:
            tank_capacity_float = float(tank_capacity)
            if tank_capacity_float <= 0:
                print(f"[Python Validation Warning] Transaction ID {transaction_id}: Kapasitas tangki <= 0, menggunakan default 50.0 Liter.")
                data["fuel_tank_capacity"] = 50.0
        except (ValueError, TypeError):
            data["fuel_tank_capacity"] = 50.0

    print(f"[Python Validation] Data untuk Transaction ID {transaction_id} valid dan aman diproses.")
    return True
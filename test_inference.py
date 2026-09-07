from app.services.inference_service import run_inference_for_transaction

if __name__ == "__main__":
    print("--- Menguji Inference Engine Pipeline ---")
    
    # Ganti angka di bawah ini dengan ID transaksi asli yang ada di database PostgreSQL Anda
    test_transaction_id = 1  
    
    try:
        result = run_inference_for_transaction(test_transaction_id)
        print("\nHasil Akhir Inference Engine:")
        for key, val in result.items():
            print(f" - {key}: {val}")
        print("Inference Engine Test: BERHASIL")
    except Exception as e:
        print(f"Inference Engine Test: GAGAL -> {e}")
        print("(Tips: Pastikan ID transaksi yang diuji benar-benar ada di tabel fuel_transactions database Anda).")
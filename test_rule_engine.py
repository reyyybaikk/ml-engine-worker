from app.services.rule_engine import evaluate_transaction_rules

if __name__ == "__main__":
    print("--- Menguji Rule Engine (Skenario Normal) ---")
    normal_data = {
        "transaction_id": 401,
        "fuel_amount": 40.0,
        "fuel_tank_capacity": 65.0,
        "cost_per_liter": 10000.0
    }
    res_normal = evaluate_transaction_rules(normal_data)
    print(f"Hasil: {res_normal}\n")

    print("--- Menguji Rule Engine (Skenario Anomali: Melebihi Tangki) ---")
    anomaly_data = {
        "transaction_id": 402,
        "fuel_amount": 80.0,  # Mengisi 80 liter padahal tangki max 65 liter
        "fuel_tank_capacity": 65.0,
        "cost_per_liter": 10000.0
    }
    res_anomaly = evaluate_transaction_rules(anomaly_data)
    print(f"Hasil: {res_anomaly}")
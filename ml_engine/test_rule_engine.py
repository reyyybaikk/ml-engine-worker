from app.services.rule_engine import evaluate_transaction_rules
from decimal import Decimal
import unittest


class RuleEngineRegressionTests(unittest.TestCase):
    def test_tank_capacity_rule_resolves_numeric_field_reference(self):
        result = evaluate_transaction_rules({
            "fuel_amount": Decimal("80.00"),
            "fuel_tank_capacity": Decimal("65.00"),
        })

        self.assertIn("ANOMALI_FUEL_HIGH", result)

    def test_unresolved_threshold_does_not_raise_type_error(self):
        result = evaluate_transaction_rules({
            "fuel_amount": Decimal("40.00"),
            "fuel_tank_capacity": Decimal("65.00"),
            "cost_per_liter": Decimal("10000.00"),
        })

        self.assertIsInstance(result, list)

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
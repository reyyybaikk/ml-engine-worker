import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

# -------------------------------------------------
# 1. Siapkan data (contoh sederhana). Ganti dengan data riil bila tersedia.
# -------------------------------------------------
# Contoh data: amount (numeric) dan is_anomaly (target)
# Kami hanya menggunakan `amount` sebagai satu‑satu fitur karena payload
# yang dikirim oleh worker hanya berisi amount dan fuelType (string).
# Jika ingin menambah fitur lain, sesuaikan endpoint ML Engine.

data = pd.DataFrame({
    "amount": [500, 1500, 2000, 300, 8000, 120, 50, 2500, 4000, 700],
    "is_anomaly": [0, 1, 1, 0, 1, 0, 0, 1, 1, 0]
})

X = data[["amount"]]  # hanya satu fitur
y = data["is_anomaly"]

# -------------------------------------------------
# 2. Split data dan latih model
# -------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# -------------------------------------------------
# 3. Simpan model ke file model.pkl
# -------------------------------------------------
joblib.dump(model, "model.pkl")
print("✅ Model telah disimpan ke model.pkl")

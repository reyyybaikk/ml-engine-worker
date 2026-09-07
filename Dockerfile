# Gunakan image Python berbasis Debian (slim) agar bisa install Tesseract
FROM python:3.11-slim

# Install Tesseract OCR, dependencies image, dan data bahasa
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ind \
    libtesseract-dev \
    libpq-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Tentukan direktori kerja
WORKDIR /app

# Copy requirements dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh source code ml-engine
COPY . .

# Jalankan worker sebagai modul
# Render akan mendeteksi CMD ini untuk menjalankan service
CMD ["python", "-m", "app.workers.fuel_worker"]

FROM python:3.11-slim

# Install OS dependencies (Tesseract OCR, PostgreSQL client libs, build tools)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ind \
    libtesseract-dev \
    libpq-dev \
    gcc \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (everything in this folder)
COPY . .

# Environment defaults – dapat di‑override lewat Railway UI
ENV PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# Jalankan FastAPI dengan uvicorn
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port 8000 & python -m app.workers.fuel_worker"]

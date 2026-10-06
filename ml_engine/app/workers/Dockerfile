FROM python:3.11-slim

# Install OS dependencies needed for the worker (same as ML Engine)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ind \
    libtesseract-dev \
    libpq-dev \
    gcc \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the requirements (shared with ml_engine) – assume they are at repository root
COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the worker package
COPY . .

# Expose port for FastAPI health endpoint (choose 8080)
EXPOSE 8080

# Run the worker as a FastAPI server; use uvicorn to serve the app defined in fuel_worker.py
CMD ["uvicorn", "workers.fuel_worker:app", "--host", "0.0.0.0", "--port", "8080"]

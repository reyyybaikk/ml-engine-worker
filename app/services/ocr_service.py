import os
import io
import re
import requests
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance

# Konfigurasi path Tesseract (Otomatis mendeteksi OS)
if os.name == 'nt':  # Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Di Linux (Render/Docker), Tesseract biasanya ada di /usr/bin/tesseract yang sudah masuk PATH


def _preprocess_image(image_input, force_landscape=False) -> Image.Image:
    """
    Melakukan preprocessing gambar agar kualitas OCR lebih baik:
    - Auto rotate (jika ada EXIF orientation atau force_landscape)
    - Grayscale
    - Contrast enhancement & Unsharp Masking
    Mendukung: bytes, filepath, atau URL.
    """
    if isinstance(image_input, (bytes, memoryview, bytearray)):
        img = Image.open(io.BytesIO(bytes(image_input)))
    elif isinstance(image_input, str) and image_input.startswith("http"):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        response = requests.get(image_input, headers=headers, stream=True, timeout=15)
        response.raise_for_status()
        img = Image.open(response.raw)
    else:
        img = Image.open(image_input)

    # Tangani rotasi EXIF dari kamera HP driver jika ada
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Auto-Rotate if Portrait but Odometer target (dashboard biasanya horizontal)
    if force_landscape and img.height > img.width:
        img = img.rotate(-90, expand=True)

    img = img.convert('L') # Grayscale
    img = ImageEnhance.Contrast(img).enhance(2.2)       # Tingkatkan kontras
    img = img.filter(ImageFilter.SHARPEN)               # Sharpen edge teks
    return img


def read_odometer(image_input) -> int | None:
    """
    Membaca angka odometer dari foto dashboard kendaraan.
    Menerapkan normalisasi karakter digital (S->5, B->8, O->0) dan multi-PSM parsing.
    """
    if not image_input:
        return None

    try:
        img = _preprocess_image(image_input, force_landscape=True)
        # Coba PSM 6 (uniform block of text) dan fallback PSM 11 (sparse text) jika perlu
        config = '--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(img, config=config, lang='eng')

        val = _parse_odometer_text(raw_text)
        if val is None:
            config_sparse = '--oem 3 --psm 11'
            raw_text_sparse = pytesseract.image_to_string(img, config=config_sparse, lang='eng')
            val = _parse_odometer_text(raw_text_sparse)

        print(f"[OCR Odometer] Detected Value: {val}")
        return val
    except Exception as e:
        print(f"[OCR Odometer Error] {e}")
        return None


def _parse_odometer_text(text: str) -> int | None:
    """
    Logika ekstraksi angka odometer dengan normalisasi karakter dan pencarian label.
    """
    if not text:
        return None

    lines = text.split("\n")
    candidates = []

    normalization_map = {
        'S': '5', 's': '5',
        'G': '6', 'g': '6',
        'B': '8', 'b': '8',
        'Z': '2', 'z': '2',
        'O': '0', 'o': '0', 'D': '0',
        'I': '1', 'l': '1', '|': '1', '!': '1'
    }

    odo_keywords = ["ODO", "TOTAL", "KM", "KILOMETER", "DISTANCE", "RANGE"]

    for line in lines:
        upper_line = line.upper().strip()
        if not upper_line:
            continue

        has_odo_kw = any(k in upper_line for k in odo_keywords)

        # 1. Cari angka yang langsung mengikuti keyword ODO/KM
        kw_match = re.search(r'(?:ODO|KM|TOTAL)\s*[:.\-]?\s*(\d{3,7})', upper_line)
        if kw_match:
            cand = int(kw_match.group(1))
            if cand not in [2024, 2025, 2026, 2027]:
                return cand

        # 2. Terapkan normalisasi karakter digital
        normalized = "".join([normalization_map.get(c, c) for c in upper_line])

        # Cari deretan angka 4-7 digit
        matches = re.findall(r'(\d{4,7})', normalized)
        for match in matches:
            num = int(match)
            if num in [2024, 2025, 2026, 2027]:
                continue # Abaikan tahun kalender

            if has_odo_kw:
                return num # Sangat yakin jika sebaris dengan keyword ODO

            candidates.append(num)

    # Heuristik: Jika tidak ada label spesifik, ambil angka wajar terbesar (odometer > trip A/B)
    if candidates:
        # Filter nilai odometer wajar (misal 500 s/d 999.999 km)
        reasonable = [c for c in candidates if 500 <= c <= 999999]
        if reasonable:
            return max(reasonable)
        return max(candidates)
    return None


def read_receipt(image_input) -> dict | None:
    """
    Membaca struk BBM (SPBU resmi Pertamina, struk print POS mini, atau kuitansi manual/eceran):
    - liters: jumlah liter BBM
    - total_cost: total harga
    - fuel_type: jenis BBM (Pertalite, Pertamax, Biosolar, Solar, Dexlite, dll)
    """
    if not image_input:
        return None

    try:
        img = _preprocess_image(image_input)
        config = '--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(img, config=config, lang='ind+eng')

        print(f"[OCR Receipt] Raw text sample:\n{raw_text[:300]}...")

        extracted = _parse_receipt_text(raw_text)

        # Fallback jika tidak menemukan liter atau total_cost: coba PSM 4/11
        if not extracted.get('liters') and not extracted.get('total_cost'):
            raw_text_sparse = pytesseract.image_to_string(img, config='--oem 3 --psm 4', lang='ind+eng')
            extracted_sparse = _parse_receipt_text(raw_text_sparse)
            if extracted_sparse.get('liters') or extracted_sparse.get('total_cost'):
                extracted = extracted_sparse

        print(f"[OCR Receipt] Extracted Result: {extracted}")
        return extracted
    except Exception as e:
        print(f"[OCR Receipt Error] {e}")
        return None


def _parse_receipt_text(text: str) -> dict:
    """
    Mem-parsing teks struk BBM dengan regex cerdas untuk SPBU dan Eceran/Kuitansi.
    """
    result = {
        'liters': None,
        'total_cost': None,
        'fuel_type': None
    }

    if not text:
        return result

    text_lower = text.lower()

    # 1. Fuel Type (Mencakup SPBU & Eceran umum)
    fuel_type_map = [
        ('pertamina dex', 'Pertamina Dex'),
        ('pertadex', 'Pertamina Dex'),
        ('pertamax turbo', 'Pertamax Turbo'),
        ('turbo', 'Pertamax Turbo'),
        ('dexlite', 'Dexlite'),
        ('dex', 'Dexlite'),
        ('biosolar', 'Biosolar'),
        ('bio solar', 'Biosolar'),
        ('solar', 'Biosolar'),
        ('pertamax', 'Pertamax'),
        ('pertalite', 'Pertalite'),
        ('premium', 'Premium'),
        ('bensin', 'Pertalite'),  # Eceran sering menyebut "bensin"
    ]
    for keyword, fuel_name in fuel_type_map:
        if re.search(rf'\b{re.escape(keyword)}\b', text_lower):
            result['fuel_type'] = fuel_name
            break

    # 2. Liters (Mendukung titik, koma, spasi, format SPBU & tulisan Eceran)
    liter_patterns = [
        # Contoh: Volume : 25.50 L, Qty: 10,00 Ltr, Jumlah Liter: 15
        r'(?:volume|vol|jumlah\s*liter|liter|qty|ltr|isi)\s*[:;=\-]?\s*(\d+[.,]\d{1,3})',
        r'(\d+[.,]\d{1,3})\s*(?:[lL](?:iter|tr)?)\b',
        # Eceran/nota format bulat: "5 liter", "10 ltr", "Vol: 10"
        r'(?:volume|vol|qty|ltr|liter)\s*[:;=\-]?\s*(\d{1,3})\b',
        r'\b(\d{1,3})\s*(?:liter|ltr|lt)\b',
    ]
    for pattern in liter_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).replace(',', '.')
            try:
                l_val = float(raw_val)
                if 0.5 <= l_val <= 500: # Batas liter masuk akal
                    result['liters'] = round(l_val, 2)
                    break
            except ValueError:
                pass

    # 3. Total Cost (SPBU, Eceran, Format Kuitansi: Total, Jumlah Bayar, Rp 50.000)
    cost_patterns = [
        # Contoh: Total Bayar: Rp 250.000, Total : 150000, Grand Total: 75.000
        r'(?:total\s*(?:biaya|bayar|harga|pembayaran)?|jumlah\s*(?:bayar|rp|uang)?|grand\s*total|tunai|cash|tagihan)\s*[:;=\-]?\s*(?:[Rr][pP]\.?\s*)?([\d.,]{4,})',
        # Format Rp langsung diikuti nominal besar (>= 4 digit angka): "Rp. 50.000", "Rp100000"
        r'(?:[Rr][pP]\.?\s*)([\d.,]{4,})',
        # Format "Total: 50000"
        r'[tT]otal\s*[:;=\-]?\s*([\d.,]{4,})',
    ]
    for pattern in cost_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Bersihkan tanda baca titik/koma ribuan
            raw_val = re.sub(r'[^\d]', '', match.group(1))
            try:
                val = float(raw_val)
                # Filter nominal yang wajar untuk transaksi BBM kendaraan dinas/operasional
                if 5000 <= val <= 10000000:
                    result['total_cost'] = val
                    break
            except ValueError:
                pass
        if result['total_cost']:
            break

    return result

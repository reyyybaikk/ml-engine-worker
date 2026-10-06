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
    Melakukan preprocessing gambar agar kualitas OCR lebih baik.
    Mendukung: bytes, filepath, atau URL.
    """
    if isinstance(image_input, (bytes, memoryview, bytearray)):
        img = Image.open(io.BytesIO(bytes(image_input)))
    elif isinstance(image_input, str) and image_input.startswith("http"):
        response = requests.get(image_input, stream=True)
        img = Image.open(response.raw)
    else:
        img = Image.open(image_input)

    # Auto-Rotate if Portrait but Odometer target
    if force_landscape and img.height > img.width:
        img = img.rotate(-90, expand=True)

    img = img.convert('L') # Grayscale
    img = ImageEnhance.Contrast(img).enhance(2.0)       # Tingkatkan kontras
    img = img.filter(ImageFilter.SHARPEN)               # Sharpen
    return img


def read_odometer(image_input) -> int | None:
    """
    Membaca angka odometer dari foto dashboard kendaraan.
    Menerapkan normalisasi karakter (S->5, B->8) dan heuristik angka terbesar.
    """
    if not image_input:
        return None

    try:
        img = _preprocess_image(image_input, force_landscape=True)
        config = '--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(img, config=config, lang='eng')

        print(f"[OCR Odometer] Raw text:\n{raw_text}")

        return _parse_odometer_text(raw_text)
    except Exception as e:
        print(f"[OCR Odometer Error] {e}")
        return None


def _parse_odometer_text(text: str) -> int | None:
    """
    Logika ekstraksi angka odometer dengan normalisasi karakter.
    """
    lines = text.split("\n")
    candidates = []

    # Normalisasi mirip logika Android
    normalization_map = {
        'S': '5', 'G': '6', 'B': '8', 'Z': '2', 'O': '0', 'o': '0', 'I': '1', 'l': '1'
    }

    odo_keywords = ["ODO", "TOTAL", "KM", "RANGE"]

    for line in lines:
        upper_line = line.upper()
        # Terapkan normalisasi karakter digital
        normalized = "".join([normalization_map.get(c, c) for c in upper_line])

        # Cari deretan angka 4-7 digit
        matches = re.findall(r'(\d{4,7})', normalized)
        for match in matches:
            num = int(match)
            if num in [2025, 2026]: continue # Abaikan tahun

            # Jika ada keyword pendukung, prioritaskan
            if any(k in upper_line for k in odo_keywords):
                return num

            candidates.append(num)

    # Heuristik: Ambil angka terbesar (biasanya Odometer > Trip/Clock)
    if candidates:
        return max(candidates)
    return None


def read_receipt(image_input) -> dict | None:
    """
    Membaca struk BBM (SPBU/ECERAN) untuk mengekstrak:
    - liters: jumlah liter BBM
    - total_cost: total harga
    - fuel_type: jenis BBM (Pertalite, Pertamax, Biosolar, dll)
    """
    if not image_input:
        return None

    try:
        img = _preprocess_image(image_input)
        config = '--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(img, config=config, lang='ind+eng')

        print(f"[OCR Receipt] Raw text:\n{raw_text}")

        extracted = _parse_receipt_text(raw_text)
        return extracted
    except Exception as e:
        print(f"[OCR Receipt Error] {e}")
        return None


def _parse_receipt_text(text: str) -> dict:
    """
    Mem-parsing raw text OCR dari struk BBM.
    """
    result = {
        'liters': None,
        'total_cost': None,
        'fuel_type': None
    }

    text_lower = text.lower()

    # 1. Fuel Type
    fuel_type_map = [
        ('pertamina dex', 'Pertamina Dex'),
        ('pertadex', 'Pertamina Dex'),
        ('dexlite', 'Dexlite'),
        ('biosolar', 'Biosolar'),
        ('bio solar', 'Biosolar'),
        ('pertamax', 'Pertamax'),
        ('pertalite', 'Pertalite'),
        ('solar', 'Biosolar'),
    ]
    for keyword, fuel_name in fuel_type_map:
        if keyword in text_lower:
            result['fuel_type'] = fuel_name
            break

    # 2. Liters
    liter_patterns = [
        r'(?:volume|jumlah|liter|qty|vol|ltr)\s*[:;=\-]?\s*(\d+[.,]\d+)',
        r'(\d+[.,]\d+)\s*[lL](?:iter|tr)?',
        r'(?:volume|jumlah|liter|qty|vol|ltr)\s*[:;=\-]?\s*(\d+)',
    ]
    for pattern in liter_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).replace(',', '.')
            try:
                result['liters'] = float(raw_val)
                break
            except ValueError: pass

    # 3. Total Cost
    cost_patterns = [
        r'(?:total\s*(?:biaya|biava|harga|bayar)?|jumlah\s*bayar|grand\s*total|tunai|cash|rp)\s*[:;=\-]?\s*(?:[Rr][pP]\.?)?\s*([\d.,]{4,})',
        r'[tT]otal\s*[:;=\-]?\s*[Rr][pP]\.?\s*([\d.,]+)',
    ]
    for pattern in cost_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_val = re.sub(r'[^\d]', '', match.group(1))
            try:
                val = float(raw_val)
                if val >= 1000:
                    result['total_cost'] = val
                    break
            except ValueError: pass

    return result

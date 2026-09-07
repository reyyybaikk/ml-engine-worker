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


def _preprocess_image(image_input) -> Image.Image:
    """
    Melakukan preprocessing gambar agar kualitas OCR lebih baik.
    Mendukung: bytes, filepath, atau URL.
    """
    if isinstance(image_input, (bytes, memoryview, bytearray)):
        img = Image.open(io.BytesIO(bytes(image_input))).convert('L')
    elif isinstance(image_input, str) and image_input.startswith("http"):
        # Download gambar dari URL (Supabase Storage)
        response = requests.get(image_input, stream=True)
        img = Image.open(response.raw).convert('L')
    else:
        img = Image.open(image_input).convert('L')

    img = ImageEnhance.Contrast(img).enhance(2.0)       # Tingkatkan kontras
    img = img.filter(ImageFilter.SHARPEN)               # Sharpen
    return img


def read_odometer(image_input) -> int | None:
    """
    [DEPRECATED] Membaca angka odometer dari foto odometer kendaraan.
    Fungsi ini dinonaktifkan karena akurasi OCR pada layar odometer sering tidak stabil.
    Validasi dialihkan ke input manual driver.
    """
    print("[OCR Odometer] SKIPPED: Odometer OCR is currently disabled.")
    return None


def read_receipt(image_input) -> dict | None:
    """
    Membaca struk BBM (SPBU/ECERAN) untuk mengekstrak:
    - liters: jumlah liter BBM
    - total_cost: total harga
    - fuel_type: jenis BBM (Pertalite, Pertamax, Biosolar, dll)
    
    Mengembalikan dict atau None jika gagal.
    """
    if not image_input:
        return None
    if isinstance(image_input, str) and not os.path.exists(image_input):
        print(f"[OCR Receipt] File tidak ditemukan: {image_input}")
        return None

    try:
        img = _preprocess_image(image_input)

        # Mode PSM 6: asumsikan blok teks (cocok untuk struk)
        config = '--oem 3 --psm 6'
        raw_text = pytesseract.image_to_string(img, config=config, lang='ind+eng')

        print(f"[OCR Receipt] Raw text dari struk:\n{raw_text}")

        extracted = _parse_receipt_text(raw_text)
        print(f"[OCR Receipt] Hasil ekstraksi: {extracted}")
        return extracted

    except Exception as e:
        print(f"[OCR Receipt Error] Gagal memproses struk: {e}")
        return None


def _parse_receipt_text(text: str) -> dict:
    """
    Mem-parsing raw text OCR dari struk BBM.
    Mencari pola: jumlah liter, total harga, dan nama BBM.
    """
    result = {
        'liters': None,
        'total_cost': None,
        'fuel_type': None
    }

    # Normalisasi teks: lowercase untuk matching
    text_lower = text.lower()

    # 1. Cari jenis BBM (urutan prioritas dari yang paling spesifik)
    fuel_type_map = [
        ('pertamina dex', 'Pertamina Dex'),
        ('pertadex', 'Pertamina Dex'),
        ('dexlite', 'Dexlite'),
        ('biosolar', 'Biosolar'),
        ('bio solar', 'Biosolar'),
        ('pertamax', 'Pertamax'),
        ('pertalite', 'Pertalite'),
    ]
    for keyword, fuel_name in fuel_type_map:
        if keyword in text_lower:
            result['fuel_type'] = fuel_name
            break

    # 2. Cari jumlah liter — pola: "Volume: 12.50", "12,50 L", "Jumlah: 12", dll.
    liter_patterns = [
        r'(?:volume|jumlah|liter|qty|vol)\s*[:;=\-]?\s*(\d+[.,]\d+)',
        r'(\d+[.,]\d+)\s*[lL](?:iter|tr)?',
        r'(?:volume|jumlah|liter|qty|vol)\s*[:;=\-]?\s*(\d+)',
        r'(\d+)\s*[lL](?:iter|tr)\b',
    ]
    for pattern in liter_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).replace(',', '.')
            try:
                result['liters'] = float(raw_val)
                break
            except ValueError:
                pass

    # 3. Cari total harga — pola: "TOTAL BIAYA ; Rp 160,000", "Tunai Rp 160,000", "Total: Rp 150.000", dll.
    cost_patterns = [
        r'(?:total\s*(?:biaya|biava|harga|bayar)?|jumlah\s*bayar|grand\s*total|tunai|tunas|cash)\s*[:;=\-]?\s*(?:[Rr][pP]\.?)?\s*([\d.,]{4,})',
        r'[tT]otal\s*[:;=\-]?\s*[Rr][pP]\.?\s*([\d.,]+)',
        r'(?<!\/liter\s)(?<!\/liter\s:\s)[Rr][pP]\.?\s*([\d.,]{5,})',
        r'[tT]otal\s*[:;=\-]?\s*([\d.]{5,})',
    ]
    for pattern in cost_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Ambil digit numerik
            raw_val = re.sub(r'[^\d]', '', match.group(1))
            try:
                val = float(raw_val)
                if val >= 1000:  # Nominal harga minimal wajar (bukan tanggal/nomor struk)
                    result['total_cost'] = val
                    break
            except ValueError:
                pass

    return result

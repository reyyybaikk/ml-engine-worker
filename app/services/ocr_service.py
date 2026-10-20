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


def read_odometer(image_input, expected_value: int | None = None) -> int | None:
    """
    Membaca angka odometer dari foto dashboard kendaraan.
    Menerapkan multi-PSM parsing dan pembobotan berbasis label ODO serta expected_value (input manual/history).
    """
    if not image_input:
        return None

    try:
        # Coba orientasi asli terlebih dahulu (karena foto HP biasanya sudah vertikal atau sesuai EXIF)
        img_original = _preprocess_image(image_input, force_landscape=False)
        configs = ['--oem 3 --psm 6', '--oem 3 --psm 11', '--oem 3 --psm 4']
        
        all_texts = []
        for cfg in configs:
            txt = pytesseract.image_to_string(img_original, config=cfg, lang='eng')
            all_texts.append(txt)

        # Jika belum ada hasil meyakinkan, coba versi landscape
        val = _parse_odometer_text("\n".join(all_texts), expected_value)
        if val is None:
            img_land = _preprocess_image(image_input, force_landscape=True)
            txt_land = pytesseract.image_to_string(img_land, config='--oem 3 --psm 6', lang='eng')
            val = _parse_odometer_text(txt_land, expected_value)

        print(f"[OCR Odometer] Detected Value: {val} (Expected: {expected_value})")
        return val
    except Exception as e:
        print(f"[OCR Odometer Error] {e}")
        return None


def _parse_odometer_text(text: str, expected_value: int | None = None) -> int | None:
    """
    Logika ekstraksi angka odometer dengan normalisasi karakter, deteksi label,
    serta contextual distance matching jika expected_value diberikan.
    """
    if not text:
        return None

    lines = text.split("\n")
    candidates_with_label = []
    general_candidates = []

    normalization_map = {
        'S': '5', 's': '5',
        'G': '6', 'g': '6',
        'B': '8', 'b': '8',
        'Z': '2', 'z': '2',
        'O': '0', 'o': '0', 'D': '0',
        'I': '1', 'l': '1', '|': '1', '!': '1'
    }

    odo_keywords = ["ODO", "TOTAL", "KM", "KILOMETER", "DISTANCE"]
    location_keywords = [
        "JL", "JALAN", "KEC", "KECAMATAN", "KAB", "KABUPATEN", 
        "KOTA", "PROV", "PROVINSI", "INDONESIA", "DESA", "KELURAHAN",
        "LAT", "LONG", "ALT", "GPS"
    ]

    for line in lines:
        upper_line = line.upper().strip()
        if not upper_line:
            continue

        # Abaikan baris watermark lokasi
        if any(re.search(rf'\b{re.escape(lk)}\b', upper_line) for lk in location_keywords):
            continue

        has_odo_kw = any(k in upper_line for k in odo_keywords)

        # 1. Cari angka yang sebaris langsung setelah keyword ODO/KM/TOTAL
        kw_match = re.search(r'(?:ODO|TOTAL|KM)\s*[:.\-]?\s*(\d{2,7})', upper_line)
        if kw_match:
            cand = int(kw_match.group(1))
            if cand not in [2024, 2025, 2026, 2027]:
                candidates_with_label.append(cand)

        # 2. Terapkan normalisasi karakter digital
        normalized = "".join([normalization_map.get(c, c) for c in upper_line])
        matches = re.findall(r'(\d{3,7})', normalized)
        for match in matches:
            num = int(match)
            if num in [2024, 2025, 2026, 2027]:
                continue
            if has_odo_kw:
                candidates_with_label.append(num)
            else:
                general_candidates.append(num)

    # Prioritas 1: Jika ada kandidat dengan label ODO/TOTAL/KM
    if candidates_with_label:
        if expected_value is not None:
            # Pilih kandidat berlabel yang paling dekat dengan expected_value
            return min(candidates_with_label, key=lambda c: abs(c - expected_value))
        return max(candidates_with_label)

    # Prioritas 2: Jika tidak ada label ODO, gunakan expected_value untuk mencocokkan angka yang paling relevan
    if general_candidates:
        valid_cands = [c for c in general_candidates if 100 <= c <= 999999]
        if valid_cands:
            if expected_value is not None:
                # Jika ada angka yang selisihnya wajar (< 30% atau < 1000 km dari expected)
                closest = min(valid_cands, key=lambda c: abs(c - expected_value))
                if abs(closest - expected_value) <= max(1000, expected_value * 0.3):
                    return closest
            return max(valid_cands)

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
            if extracted_sparse.get('liters') or extracted_sparse.get('total_cost') or extracted_sparse.get('fuel_type'):
                extracted = extracted_sparse

        print(f"[OCR Receipt] Extracted Result: {extracted}")
        return extracted
    except Exception as e:
        print(f"[OCR Receipt Error] {e}")
        return None


def _parse_receipt_text(text: str) -> dict:
    """
    Mem-parsing teks struk BBM dengan regex cerdas dan toleran terhadap typo/noise Tesseract.
    """
    result = {
        'liters': None,
        'total_cost': None,
        'fuel_type': None
    }

    if not text:
        return result

    text_lower = text.lower()

    # 1. Fuel Type (Termasuk variasi typo umum OCR seperti Pertaite, Pertalit, dll)
    fuel_type_map = [
        (r'\b(pertamina\s*dex|pertadex)\b', 'Pertamina Dex'),
        (r'\b(pertamax\s*turbo|turbo)\b', 'Pertamax Turbo'),
        (r'\b(dexlite|dex)\b', 'Dexlite'),
        (r'\b(biosolar|bio\s*solar|b-solar|biosolr)\b', 'Biosolar'),
        (r'\b(solar)\b', 'Biosolar'),
        (r'\b(pertamax|pertamaxx)\b', 'Pertamax'),
        (r'\b(pertalite|pertaite|pertalit|petalite)\b', 'Pertalite'),
        (r'\b(premium)\b', 'Premium'),
        (r'\b(bensin)\b', 'Pertalite'),  # Eceran sering menyebut "bensin"
    ]
    for pattern, fuel_name in fuel_type_map:
        if re.search(pattern, text_lower):
            result['fuel_type'] = fuel_name
            break

    # 2. Liters (Mendukung titik, koma, spasi, simbol petik ', tanda hubung, dll)
    liter_patterns = [
        # Format: "Jumlah liter ' 10", "Volume : 25.50 L", "Jumlah Liter: 15", "Qty: 10,00"
        r'(?:volume|vol|jumlah\s*liter|liter|qty|ltr|isi)[\s\'":;=\-]*(\d+[.,]\d{1,3})',
        r'(\d+[.,]\d{1,3})\s*(?:[lL](?:iter|tr)?)\b',
        # Format angka bulat: "Jumlah liter ' 10", "Vol: 10", "5 liter"
        r'(?:volume|vol|jumlah\s*liter|liter|qty|ltr|isi)[\s\'":;=\-]*(\d{1,3})\b',
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

    # 3. Total Cost (Format SPBU, Eceran, "Jumlah bei 10.000", "Total Bayar Rp 50.000", dll)
    cost_patterns = [
        # Menangani typo seperti "Jumlah bei", "Jumlah beli", "Total bayar", "Grand Total"
        r'(?:total\s*(?:biaya|bayar|harga|pembayaran|bei|beli)?|jumlah\s*(?:bayar|rp|uang|bei|beli)?|grand\s*total|tunai|cash|tagihan)[\s\'":;=\-]*(?:[Rr][pP]\.?\s*)?([\d.,]{3,})',
        # Format Rp langsung: "Rp. 50.000", "Rp100000"
        r'(?:[Rr][pP]\.?\s*)([\d.,]{4,})',
        # Format umum: "Total: 50000"
        r'[tT]otal[\s\'":;=\-]*([\d.,]{4,})',
    ]
    for pattern in cost_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            cleaned = match.group(1).strip()
            # Bersihkan tanda baca titik/koma ribuan
            raw_digits = re.sub(r'[^\d]', '', cleaned)
            try:
                val = float(raw_digits)
                # Filter nominal yang wajar untuk transaksi BBM (Rp 5.000 s/d Rp 10.000.000)
                if 5000 <= val <= 10000000:
                    result['total_cost'] = val
                    break
            except ValueError:
                pass
        if result['total_cost']:
            break

    return result

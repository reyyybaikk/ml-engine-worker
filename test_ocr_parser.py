from app.services.ocr_service import _parse_receipt_text, _parse_odometer_text

sample_receipt = """
a dl, hnmad Yan oo oo”
sr —
| | Waktu: 04/04/2025 10:73:45 oo O |
7 Jenis BBM - Pertaite oo”
3 Harga/liter =i“
7 Jumlah liter ' 10
4 Jumlah bei 10.000
pln. 09:14:22 | 20/10/2026 ear
7 Jl. Pangeran Hidayatullah No.22, Loktabat Utara, gee | |
Kec. Banjarbaru Utara, Kota Banjar Baru, ae | ;
Kalimantan S...
"""

receipt_res = _parse_receipt_text(sample_receipt)
print("Parsed Receipt:", receipt_res)

sample_odo_gps = """
TRIP A 14.2
ODO 1312
Jl. Pangeran Hidayatullah No.22, Loktabat Utara, Kec. Banjarbaru Utara, Kota Banjar Baru, Kalimantan Selatan 70714
"""
odo_res = _parse_odometer_text(sample_odo_gps)
print("Parsed Odometer with GPS Watermark:", odo_res)

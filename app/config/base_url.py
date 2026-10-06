import os
from urllib.parse import urljoin

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip('/')

def build_validate_url(transaction_id: int) -> str:
    """Membuat URL yang benar untuk endpoint /validate/<id>.
    Menggunakan urljoin agar tidak menghasilkan //validate.
    """
    path = f"/validate/{transaction_id}"
    # urljoin memastikan satu slash antara BASE_URL dan path
    return urljoin(f"{BASE_URL}/", path)

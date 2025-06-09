import os
import sqlite3
import requests
from contextlib import contextmanager

DATABASE_PATH = "data/Chinook.db"
CHINOOK_URL = "https://storage.googleapis.com/benchmarks-artifacts/chinook/Chinook.db"

def ensure_data_directory():
    """Ensure the data directory exists"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

def download_chinook_db(db_path="data/Chinook.db"):
    """Download the Chinook database file"""
    response = requests.get(CHINOOK_URL)
    if response.status_code == 200:
        ensure_data_directory()
        with open(db_path, "wb") as file:
            file.write(response.content)
        print(f"File downloaded and saved as {db_path}")
    else:
        raise RuntimeError(f"Failed to download database. Status code: {response.status_code}")

@contextmanager
def get_db_connection():
    """Get a database connection with context management"""
    if not os.path.exists(DATABASE_PATH):
        ensure_data_directory()
        download_chinook_db()
    
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()
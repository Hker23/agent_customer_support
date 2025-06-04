import sqlite3
import requests
from pathlib import Path
from typing import Optional
from threading import Lock

class DatabaseManager:
    _instance = None
    _lock = Lock()
    _conn_pool = []
    _max_connections = 5
    db_path = "chinook.db"

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Download database if it doesn't exist."""
        if not Path(self.db_path).exists():
            print("Downloading database...")
            url = "https://storage.googleapis.com/benchmarks-artifacts/chinook/Chinook.db"
            response = requests.get(url)
            if response.status_code == 200:
                with open(self.db_path, "wb") as file:
                    file.write(response.content)
                print("Database downloaded successfully")
            else:
                raise Exception(f"Failed to download database: {response.status_code}")
        else:
            print("Database already exists")

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool or create a new one."""
        with self._lock:
            if self._conn_pool:
                return self._conn_pool.pop()
            return sqlite3.connect(self.db_path, check_same_thread=False)

    def return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        with self._lock:
            if len(self._conn_pool) < self._max_connections:
                self._conn_pool.append(conn)
            else:
                conn.close()

    def execute_query(self, query: str, params: tuple = None) -> list:
        """Execute a query and return results."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            return results
        finally:
            self.return_connection(conn)

# Global instance
db_manager = DatabaseManager() 
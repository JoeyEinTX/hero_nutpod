"""SQLite interface for the sensor_readings table (Section 5.3 schema).

Lives in the same nutflix.db file as the events table; SQLite handles the
concurrent access between the motion service process (which writes) and the
dashboard process (which reads).

Each value column is nullable: a partial sensor failure may produce only
some of (temperature_c, humidity_percent, pressure_hpa). NULL means
"we don't know" rather than "zero".
"""
import sqlite3
import threading
from datetime import datetime


SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    device_name TEXT NOT NULL,
    temperature_c REAL,
    humidity_percent REAL,
    pressure_hpa REAL
);
"""


class SensorLog:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        # check_same_thread=False is safe because every access is serialized
        # by self._lock.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def insert_reading(self, device_name, temperature_c, humidity_percent,
                       pressure_hpa, timestamp=None):
        ts = timestamp or datetime.now().isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO sensor_readings "
                "(timestamp, device_name, temperature_c, humidity_percent, "
                "pressure_hpa) VALUES (?, ?, ?, ?, ?)",
                (ts, device_name, temperature_c, humidity_percent, pressure_hpa),
            )
            self._conn.commit()
            return cur.lastrowid

    def query_recent_readings(self, limit=50):
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, timestamp, device_name, temperature_c, "
                "humidity_percent, pressure_hpa "
                "FROM sensor_readings ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return cur.fetchall()

    def latest_reading(self):
        rows = self.query_recent_readings(limit=1)
        return rows[0] if rows else None

    def close(self):
        with self._lock:
            self._conn.close()

"""SQLite event log per Section 5.2.

Single `events` table. Created on first run if missing. One EventLog instance
is shared across the camera worker threads; access is serialized via an
internal lock so the underlying sqlite3 connection (which is single-threaded
by default) stays consistent.

Stored paths are relative to the repository root (e.g.
`output/snapshots/Hero_NestCam_2026-05-15_08-12-04.jpg`).
"""
import sqlite3
import threading
from datetime import datetime


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    device_name TEXT NOT NULL,
    camera_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    snapshot_path TEXT,
    clip_path TEXT,
    tags TEXT
);
"""


class EventLog:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        # check_same_thread=False is safe because every access is serialized
        # by self._lock; the camera worker threads never touch the connection
        # concurrently.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def insert_motion_event(self, device_name, camera_name, snapshot_path, clip_path, timestamp=None):
        return self._insert(
            timestamp or _now_iso(),
            device_name,
            camera_name,
            "motion",
            snapshot_path,
            clip_path,
        )

    def insert_heartbeat_event(self, device_name, camera_name, snapshot_path, timestamp=None):
        return self._insert(
            timestamp or _now_iso(),
            device_name,
            camera_name,
            "heartbeat",
            snapshot_path,
            None,
        )

    def query_recent_events(self, limit=50):
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, timestamp, device_name, camera_name, event_type, "
                "snapshot_path, clip_path, tags "
                "FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return cur.fetchall()

    def event_type_for_snapshot(self, snapshot_path):
        """Return the event_type for a given snapshot path, or None if not found.

        Used by the retention script to decide which retention window applies
        to a given .jpg.
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT event_type FROM events WHERE snapshot_path = ? LIMIT 1",
                (str(snapshot_path),),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def get_event_by_id(self, event_id):
        """Return one event row, or None. Used by the dashboard detail page."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, timestamp, device_name, camera_name, event_type, "
                "snapshot_path, clip_path, tags "
                "FROM events WHERE id = ?",
                (int(event_id),),
            )
            return cur.fetchone()

    def query_events_page(self, limit, offset, camera_filter=None):
        """Paginated event list for the dashboard /events view.

        camera_filter is a lowercase config key ('nestcam' / 'crittercam') or
        None for all cameras. Stored camera_name uses the PascalCase display
        name, so we case-insensitive match on it.
        """
        with self._lock:
            if camera_filter:
                cur = self._conn.execute(
                    "SELECT id, timestamp, device_name, camera_name, event_type, "
                    "snapshot_path, clip_path, tags "
                    "FROM events WHERE LOWER(camera_name) = ? "
                    "ORDER BY id DESC LIMIT ? OFFSET ?",
                    (camera_filter.lower(), int(limit), int(offset)),
                )
            else:
                cur = self._conn.execute(
                    "SELECT id, timestamp, device_name, camera_name, event_type, "
                    "snapshot_path, clip_path, tags "
                    "FROM events ORDER BY id DESC LIMIT ? OFFSET ?",
                    (int(limit), int(offset)),
                )
            return cur.fetchall()

    def count_events(self, camera_filter=None):
        with self._lock:
            if camera_filter:
                cur = self._conn.execute(
                    "SELECT COUNT(*) FROM events WHERE LOWER(camera_name) = ?",
                    (camera_filter.lower(),),
                )
            else:
                cur = self._conn.execute("SELECT COUNT(*) FROM events")
            return cur.fetchone()[0]

    def latest_heartbeat(self, camera_name):
        """Return the timestamp of the latest heartbeat for the given camera,
        or None. Used by the /status page."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT timestamp FROM events "
                "WHERE event_type = 'heartbeat' AND camera_name = ? "
                "ORDER BY id DESC LIMIT 1",
                (camera_name,),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def update_paths(self, event_id, snapshot_path, clip_path):
        """Rewrite snapshot_path and clip_path for one event. Used after a
        keeper move (or reverse). NULL is preserved when the corresponding
        file didn't exist."""
        with self._lock:
            self._conn.execute(
                "UPDATE events SET snapshot_path = ?, clip_path = ? "
                "WHERE id = ?",
                (snapshot_path, clip_path, int(event_id)),
            )
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    def _insert(self, timestamp, device_name, camera_name, event_type, snapshot_path, clip_path):
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events "
                "(timestamp, device_name, camera_name, event_type, "
                "snapshot_path, clip_path, tags) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    timestamp,
                    device_name,
                    camera_name,
                    event_type,
                    snapshot_path,
                    clip_path,
                    "",
                ),
            )
            self._conn.commit()
            return cur.lastrowid


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")

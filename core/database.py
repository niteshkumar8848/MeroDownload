import json
import os
import sqlite3
import threading
from typing import Any


class DatabaseManager:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    platform TEXT,
                    format TEXT,
                    quality TEXT,
                    status TEXT,
                    filepath TEXT,
                    size_bytes INTEGER,
                    duration INTEGER,
                    thumbnail_url TEXT,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    error_message TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            self.conn.commit()

    def add_download(self, payload: dict[str, Any]) -> int:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO downloads (
                    url, title, platform, format, quality, status, filepath,
                    size_bytes, duration, thumbnail_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("url"),
                    payload.get("title"),
                    payload.get("platform"),
                    payload.get("format"),
                    payload.get("quality"),
                    payload.get("status", "QUEUED"),
                    payload.get("filepath"),
                    payload.get("size_bytes"),
                    payload.get("duration"),
                    payload.get("thumbnail_url"),
                ),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def update_download(self, download_id: int, fields: dict[str, Any]) -> None:
        if not fields:
            return
        keys = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [download_id]
        with self.lock:
            self.conn.execute(f"UPDATE downloads SET {keys} WHERE id = ?", values)
            self.conn.commit()

    def update_status(self, download_id: int, status: str, error_message: str = "") -> None:
        fields = {"status": status, "error_message": error_message}
        if status == "COMPLETED":
            fields["completed_at"] = "CURRENT_TIMESTAMP"
            with self.lock:
                self.conn.execute(
                    """
                    UPDATE downloads
                    SET status = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, error_message, download_id),
                )
                self.conn.commit()
            return
        self.update_download(download_id, fields)

    def get_history(self, search: str = "", sort_by: str = "Date") -> list[dict[str, Any]]:
        sort_map = {
            "Date": "COALESCE(completed_at, added_at) DESC",
            "Size": "size_bytes DESC",
            "Platform": "platform ASC",
        }
        order = sort_map.get(sort_by, sort_map["Date"])
        query = "SELECT * FROM downloads WHERE status = 'COMPLETED'"
        params: list[Any] = []
        if search:
            query += " AND title LIKE ?"
            params.append(f"%{search}%")
        query += f" ORDER BY {order}"
        with self.lock:
            rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_downloads(self, statuses: list[str] | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM downloads"
        params: list[Any] = []
        if statuses:
            placeholders = ",".join("?" * len(statuses))
            query += f" WHERE status IN ({placeholders})"
            params.extend(statuses)
        query += " ORDER BY id DESC"
        with self.lock:
            rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def delete_record(self, download_id: int) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM downloads WHERE id = ?", (download_id,)).fetchone()
            if not row:
                return None
            self.conn.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
            self.conn.commit()
            return dict(row)

    def has_duplicate(self, url: str, fmt: str, quality: str) -> bool:
        with self.lock:
            row = self.conn.execute(
                """
                SELECT id FROM downloads
                WHERE url = ? AND format = ? AND quality = ? AND status = 'COMPLETED'
                LIMIT 1
                """,
                (url, fmt, quality),
            ).fetchone()
        return row is not None

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.lock:
            row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]

    def set_setting(self, key: str, value: Any) -> None:
        encoded = json.dumps(value)
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO settings(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, encoded),
            )
            self.conn.commit()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

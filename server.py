from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import psycopg
except ImportError:  # pragma: no cover - available only when DATABASE_URL is configured
    psycopg = None


BASE_DIR = Path(__file__).resolve().parent
PHOTOS_DIR = BASE_DIR / "photos"
SQLITE_FILE = BASE_DIR / "memorial.db"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DATA_LOCK = threading.Lock()


class DataStore:
    def init(self) -> None:
        raise NotImplementedError

    def get_count(self) -> int:
        raise NotImplementedError

    def increment_count(self) -> int:
        raise NotImplementedError

    def get_messages(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def add_message(self, name: str, message: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class SQLiteStore(DataStore):
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gratitude_counter (
                    counter_key TEXT PRIMARY KEY,
                    count_value INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memorial_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO gratitude_counter (counter_key, count_value)
                VALUES ('thanks', 0)
                """
            )
            connection.commit()

    def get_count(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT count_value FROM gratitude_counter WHERE counter_key = 'thanks'"
            ).fetchone()
        return int(row["count_value"] if row else 0)

    def increment_count(self) -> int:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE gratitude_counter
                SET count_value = count_value + 1
                WHERE counter_key = 'thanks'
                """
            )
            row = connection.execute(
                "SELECT count_value FROM gratitude_counter WHERE counter_key = 'thanks'"
            ).fetchone()
            connection.commit()
        return int(row["count_value"] if row else 0)

    def get_messages(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT name, message, created_at
                FROM memorial_messages
                ORDER BY id DESC
                LIMIT 100
                """
            ).fetchall()
        return [
            {
                "name": row["name"],
                "message": row["message"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def add_message(self, name: str, message: str) -> list[dict[str, Any]]:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memorial_messages (name, message, created_at)
                VALUES (?, ?, ?)
                """,
                (name, message, created_at),
            )
            connection.commit()
        return self.get_messages()


class PostgresStore(DataStore):
    def __init__(self, database_url: str):
        if psycopg is None:
            raise RuntimeError("psycopg is required when DATABASE_URL is set.")
        self.database_url = database_url

    def connect(self):
        return psycopg.connect(self.database_url)

    def init(self) -> None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS gratitude_counter (
                        counter_key TEXT PRIMARY KEY,
                        count_value INTEGER NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memorial_messages (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO gratitude_counter (counter_key, count_value)
                    VALUES ('thanks', 0)
                    ON CONFLICT (counter_key) DO NOTHING
                    """
                )
            connection.commit()

    def get_count(self) -> int:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count_value FROM gratitude_counter WHERE counter_key = 'thanks'"
                )
                row = cursor.fetchone()
        return int(row[0] if row else 0)

    def increment_count(self) -> int:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE gratitude_counter
                    SET count_value = count_value + 1
                    WHERE counter_key = 'thanks'
                    RETURNING count_value
                    """
                )
                row = cursor.fetchone()
            connection.commit()
        return int(row[0] if row else 0)

    def get_messages(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT name, message, created_at
                    FROM memorial_messages
                    ORDER BY id DESC
                    LIMIT 100
                    """
                )
                rows = cursor.fetchall()
        return [
            {
                "name": row[0],
                "message": row[1],
                "createdAt": row[2].isoformat(),
            }
            for row in rows
        ]

    def add_message(self, name: str, message: str) -> list[dict[str, Any]]:
        created_at = datetime.now(timezone.utc)
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO memorial_messages (name, message, created_at)
                    VALUES (%s, %s, %s)
                    """,
                    (name, message, created_at),
                )
            connection.commit()
        return self.get_messages()


def build_store() -> DataStore:
    if DATABASE_URL:
        return PostgresStore(DATABASE_URL)
    return SQLiteStore(SQLITE_FILE)


STORE = build_store()


def list_photos() -> list[dict[str, str]]:
    if not PHOTOS_DIR.exists():
        return []

    photos = []
    for path in sorted(PHOTOS_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            continue
        photos.append({"name": path.name, "url": f"/photos/{path.name}"})
    return photos


class MemorialHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def end_headers(self) -> None:
        if self.path.startswith("/api/"):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/thanks":
            self.send_json({"count": STORE.get_count()})
            return

        if path == "/api/messages":
            self.send_json({"messages": STORE.get_messages()})
            return

        if path == "/api/photos":
            self.send_json({"photos": list_photos()})
            return

        if path == "/api/status":
            self.send_json({"status": "ok", "storage": "postgres" if DATABASE_URL else "sqlite"})
            return

        if path == "/":
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/thanks":
            self.handle_thanks_post()
            return

        if path == "/api/messages":
            self.handle_message_post()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def handle_thanks_post(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length:
            self.rfile.read(content_length)

        with DATA_LOCK:
            count = STORE.increment_count()

        self.send_json({"count": count}, status=HTTPStatus.CREATED)

    def handle_message_post(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        name = str(payload.get("name", "")).strip()
        message = str(payload.get("message", "")).strip()

        if not name or not message:
            self.send_error(HTTPStatus.BAD_REQUEST, "Name and message are required")
            return

        with DATA_LOCK:
            messages = STORE.add_message(name[:60], message[:500])

        self.send_json({"messages": messages}, status=HTTPStatus.CREATED)

    def log_message(self, format: str, *args) -> None:
        return

    def send_error(self, code, message=None, explain=None):
        try:
            status = HTTPStatus(code)
        except ValueError:
            status = HTTPStatus.INTERNAL_SERVER_ERROR

        self.send_json({"error": message or status.phrase}, status=status)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    STORE.init()
    PHOTOS_DIR.mkdir(exist_ok=True)

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), MemorialHandler)
    print(f"Serving memorial site at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

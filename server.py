from __future__ import annotations

import json
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "thanks-data.json"
PHOTOS_DIR = BASE_DIR / "photos"
DATA_LOCK = threading.Lock()
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def read_data() -> dict:
    if not DATA_FILE.exists():
        return {"count": 0, "messages": []}

    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"count": 0, "messages": []}

    return {
        "count": int(payload.get("count", 0)),
        "messages": list(payload.get("messages", [])),
    }


def write_data(payload: dict) -> None:
    DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def list_photos() -> list[dict]:
    if not PHOTOS_DIR.exists():
        return []

    photos = []
    for path in sorted(PHOTOS_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            continue
        photos.append(
            {
                "name": path.name,
                "url": f"/photos/{path.name}",
            }
        )

    return photos


class MemorialHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/thanks":
            self.send_json({"count": read_data()["count"]})
            return

        if path == "/api/messages":
            self.send_json({"messages": read_data()["messages"]})
            return

        if path == "/api/photos":
            self.send_json({"photos": list_photos()})
            return

        if path == "/api/status":
            self.send_json({"status": "ok"})
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
            data = read_data()
            data["count"] = int(data.get("count", 0)) + 1
            write_data(data)

        self.send_json({"count": data["count"]}, status=HTTPStatus.CREATED)

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

        remark = {
            "name": name[:60],
            "message": message[:500],
            "createdAt": datetime.now().astimezone().isoformat(),
        }

        with DATA_LOCK:
            data = read_data()
            messages = list(data.get("messages", []))
            messages.insert(0, remark)
            data["messages"] = messages[:100]
            write_data(data)

        self.send_json({"messages": data["messages"]}, status=HTTPStatus.CREATED)

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
    if not DATA_FILE.exists():
        write_data({"count": 0, "messages": []})
    PHOTOS_DIR.mkdir(exist_ok=True)

    server = ThreadingHTTPServer(("127.0.0.1", 8000), MemorialHandler)
    print("Serving memorial site at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()

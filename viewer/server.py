"""Local HTTP server for the viewer (stdlib only). Binds to 127.0.0.1.   python scripts/serve_viewer.py [--port 8765]"""
from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from viewer import data

HERE = Path(__file__).resolve().parent
_collection = None
_lock = threading.Lock()


def _col():
    global _collection
    with _lock:
        if _collection is None:
            import chromadb
            import yaml

            cfg = yaml.safe_load((data.ROOT / "config.yaml").read_text())
            _collection = chromadb.PersistentClient(path=str(data.ROOT / cfg["kb"]["chroma_dir"])).get_collection(cfg["kb"]["collection"])
        return _collection


class Handler(BaseHTTPRequestHandler):
    runs_dir: Path | None = None

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        try:
            if path in ("/", "/index.html"):
                return self._send(200, (HERE / "index.html").read_bytes(), "text/html")
            if path == "/api/runs":
                return self._json(data.list_runs(self.runs_dir))
            m = re.fullmatch(r"/api/run/([\w-]+)", path)
            if m:
                return self._json(data.load_run(m.group(1), self.runs_dir))
            if path == "/api/report":
                return self._json(data.report_bundle())
            m = re.fullmatch(r"/api/chunk/(.+)", path)
            if m:
                info = data.chunk_info(m.group(1), _col())
                return self._json(info) if info else self._json({"error": "chunk not found"}, 404)
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        self._json({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/api/approve":
            return self._json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            b = json.loads(self.rfile.read(min(n, 20000)) or b"{}")
            res = data.approve(b["run_id"], b["hash"], b["decision"], str(b.get("by", "")), str(b.get("note", "")), self.runs_dir)
            self._json(res)
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self._json({"error": str(e)}, 400)


def make_server(port: int = 8765, runs_dir: Path | None = None) -> ThreadingHTTPServer:
    h = type("H", (Handler,), {"runs_dir": runs_dir})
    return ThreadingHTTPServer(("127.0.0.1", port), h)

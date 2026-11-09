"""One command: local timeline and report viewer.   python scripts/serve_viewer.py [--port 8765]

Reads audit/runs/*, report/* and the KB. Makes no model calls and needs no API key. Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from viewer.server import make_server  # noqa: E402


def main(argv: list[str]) -> int:
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    srv = make_server(port)
    url = f"http://127.0.0.1:{port}/"
    print(f"Viewer running at {url}  (Ctrl+C to stop)")
    if "--no-browser" not in argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

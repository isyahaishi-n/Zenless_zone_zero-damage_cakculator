"""Launcher untuk container/PaaS (jalur A) — TIDAK mengubah server.py.

Bedanya dengan `python server.py` cuma:
- bind ke 0.0.0.0 (server.py default 127.0.0.1 -> tidak bisa diakses dari luar container)
- hormati env $PORT (konvensi Fly.io / Render / Railway / Heroku) lalu fallback argv
- $HOST opsional (default 0.0.0.0)

Handler, routing, dan seluruh logika tetap milik server.py.
"""
from __future__ import annotations

import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import server as zzz  # noqa: E402


def main() -> None:
    port = int(os.environ.get("PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    zzz.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"ZZZ Showcase server running at http://{host}:{port}", flush=True)
    print("Endpoints: /api/monsters, POST /api/calc, POST /api/rotation, "
          "POST /api/team-rotation, /img/monster/<slug>", flush=True)
    ThreadingHTTPServer((host, port), zzz.Handler).serve_forever()


if __name__ == "__main__":
    main()

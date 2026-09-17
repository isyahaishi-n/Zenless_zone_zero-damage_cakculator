"""Entrypoint Vercel — jalur all-in-one (WSGI).

Vercel Python runtime memanggil `app(environ, start_response)`. File ini TIDAK
menduplikasi logika aplikasi: ia memanggil `server.Handler` (server.py) apa
adanya lewat shim WSGI, jadi paritas dengan `python server.py` 100% sama.

Yang wajib beda di serverless:
- FS read-only kecuali /tmp  -> cache gambar (.imgcache) dipindah ke /tmp.
- Tidak ada proses panjang   -> `serve_forever()` tidak dipakai; tiap request
  ditangani langsung, context (CALC_CONTEXT) tetap ke-cache in-process selama
  instance hidup.

Routing: request apa pun yang masuk ke fungsi ini dipetakan ke do_GET/do_POST
server.py (lihat docstring server.py untuk daftar endpoint).
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.parse
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BUNDLE = _HERE / "_bundle"  # hasil `deploy/vercel_stage.py` (jalur Vercel)
ROOT = _BUNDLE if (_BUNDLE / "server.py").is_file() else _HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # supaya `import server` (dan modul lain) jalan

# CWD di Vercel = project root, sedangkan damage_calc.py / core_skill_lookup.py
# membaca `data/...` dan `dumps/loadouts.json` pakai path relatif-CWD.
# chdir ke ROOT bikin semua loader (bundel maupun fallback lokal) selalu benar.
os.chdir(ROOT)

import server as zzz  # noqa: E402  (butuh sys.path di atas)

# --- 1) cache gambar -> /tmp (Vercel: FS read-only kecuali /tmp) -------------
_CACHE_ROOT = Path("/tmp/zzz-cache") if Path("/tmp").is_dir() else zzz.CACHE_DIR
try:
    _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
except OSError:  # FS read-only dan /tmp tidak ada -> pakai default (mode lokal)
    _CACHE_ROOT = zzz.CACHE_DIR
zzz.CACHE_DIR = _CACHE_ROOT
zzz.MONSTER_CACHE_DIR = _CACHE_ROOT / "monster"

# --- 2) seed icon-slug monster (hindari probe CDN per instance dingin) --------
# resolve_icon_slug() HEAD-probe CDN (timeout 15 s, cache in-memory saja);
# seed hasil `deploy/build_icon_seed.py` bikin resolve instan tanpa jaringan.
# NB: server.py me-import monster_data secara lazy di dalam fungsi, jadi kita
# import modulnya di sini sendiri (class-level patch tetap berlaku untuk itu).
_ICON_SEED: dict = {}
_SEED_FILE = ROOT / "data" / "mapped" / "monster_icon_slugs.json"


def _icon_seed() -> dict:
    global _ICON_SEED
    if not _ICON_SEED:
        try:
            data = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _ICON_SEED = data.get("slugs", {})
        except Exception:
            _ICON_SEED = {}
    return _ICON_SEED


import monster_data as _monster_data  # noqa: E402  (modul murah; tabel di-load saat MonsterDB())

_orig_resolve_icon_slug = _monster_data.MonsterDB.resolve_icon_slug


def _resolve_icon_slug(self, codename: str):
    seed = _icon_seed()
    if codename in seed:
        self._icon_slug_cache[codename] = seed[codename]
        return seed[codename]
    return _orig_resolve_icon_slug(self, codename)


_monster_data.MonsterDB.resolve_icon_slug = _resolve_icon_slug


class _EnvironHeaders:

    def __init__(self, environ: dict) -> None:
        self._e = environ

    def get(self, key: str, default=None):
        k = key.upper().replace("-", "_")
        if k in ("CONTENT_LENGTH", "CONTENT_TYPE"):
            return self._e.get(k, default)
        return self._e.get("HTTP_" + k, default)


class _WSGIHandler(zzz.Handler):
    """server.Handler dengan socket diganti buffer in-memory.

    `super().__init__` sengaja TIDAK dipanggil: BaseHTTPRequestHandler.__init__
    akan langsung menangani socket dan masuk loop handle_one_request().
    """

    def __init__(self, environ: dict) -> None:
        self.environ = environ
        self.command = environ.get("REQUEST_METHOD", "GET")
        # vercel.json me-rewrite semua path ke `/api/index?__zzz_path=<asli>`,
        # jadi PATH_INFO = "/api/index" — path asli diambil dari param itu.
        qs = environ.get("QUERY_STRING", "")
        params = urllib.parse.parse_qs(qs, keep_blank_values=True)
        self.path = environ.get("PATH_INFO", "/") or "/"
        if "__zzz_path" in params:
            self.path = params["__zzz_path"][0]
            rest = {k: v for k, v in params.items() if k != "__zzz_path"}
            if rest:
                self.path += "?" + urllib.parse.urlencode(
                    [(k, v) for k, vs in rest.items() for v in vs])
        elif qs:
            self.path += "?" + qs
        self.request_version = environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        self.client_address = (environ.get("REMOTE_ADDR", "0.0.0.0"), 0)
        self.headers = _EnvironHeaders(environ)
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        stream = environ.get("wsgi.input")
        self.rfile = io.BytesIO(stream.read(length) if (stream and length) else b"")
        self.wfile = io.BytesIO()
        self._status = 200
        self._reason = ""
        self._out_headers: list = []

    # ---- API yg dipakai server.Handler._send() ----
    def send_response(self, code, message=None) -> None:
        self._status = int(code)
        self._reason = message or ""

    def send_response_only(self, code, message=None) -> None:
        self.send_response(code, message)

    def send_header(self, keyword, value) -> None:
        self._out_headers.append((str(keyword), str(value)))

    def end_headers(self) -> None:
        pass  # tidak ada socket


_REASONS = {
    200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found",
    405: "Method Not Allowed", 500: "Internal Server Error",
    502: "Bad Gateway", 504: "Gateway Timeout",
}


def app(environ, start_response):
    """WSGI entrypoint (dipanggil Vercel Python runtime)."""
    handler = _WSGIHandler(environ)
    try:
        if handler.command == "POST":
            handler.do_POST()
        else:
            handler.do_GET()
    except BrokenPipeError:
        pass

    body = handler.wfile.getvalue()
    headers = handler._out_headers
    if not any(k.lower() == "content-length" for k, _ in headers):
        headers.append(("Content-Length", str(len(body))))
    if not any(k.lower() == "content-type" for k, _ in headers):
        headers.append(("Content-Type", "text/plain; charset=utf-8"))

    status = handler._status or 500
    reason = handler._reason or _REASONS.get(status, "OK")
    start_response(f"{status} {reason}", headers)
    return [body]


# Alias supaya aman kalau runtime mencari nama lain.
application = app
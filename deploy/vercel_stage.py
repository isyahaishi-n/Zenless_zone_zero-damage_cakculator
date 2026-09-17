"""Stage file runtime ke `api/_bundle/` — dijalankan sebagai `buildCommand` Vercel.

Kenapa ada: Vercel membundel Function dari file di sekitar entrypoint (`api/`),
bukan seluruh repo. Daripada bergantung pada konfigurasi bundling yang bisa
berubah, kita SALIN yang dibutuhkan `server.py` ke dalam `api/_bundle/` saat
build, lalu `api/index.py` menganggap `api/_bundle/` sebagai root-nya.

Di lokal script ini juga jalan (`python deploy/vercel_stage.py`) untuk menguji
jalur yang sama persis dengan yang dijalankan Vercel. Hasil staging sudah
di-gitignore (`api/_bundle/`) — jangan di-commit (≈120 MB).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BUNDLE = BASE_DIR / "api" / "_bundle"

# Modul python yang di-import server.py (langsung atau lewat zzz_enka_stat_calc_multichar)
RUNTIME_FILES = [
    "server.py",
    "damage_calc.py",
    "monster_data.py",
    "skill_lookup.py",
    "core_skill_lookup.py",
    "field_map.py",
    "zzz_enka_stat_calc_multichar.py",
]
# Data & asset yang dipakai saat request (server.py menurunkan path dari __file__)
RUNTIME_DIRS = ["data", "dumps", "site"]

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def main() -> int:
    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    BUNDLE.mkdir(parents=True)

    missing = []
    for name in RUNTIME_FILES:
        src = BASE_DIR / name
        if not src.is_file():
            missing.append(name)
            continue
        shutil.copy2(src, BUNDLE / name)

    for name in RUNTIME_DIRS:
        src = BASE_DIR / name
        if not src.is_dir():
            missing.append(name + "/")
            continue
        shutil.copytree(src, BUNDLE / name, ignore=IGNORE, dirs_exist_ok=True)

    if missing:
        print("!! file runtime tidak ketemu: %s" % ", ".join(missing), file=sys.stderr)
        return 1

    total = sum(f.stat().st_size for f in BUNDLE.rglob("*") if f.is_file())
    print("staged %d file, %.1f MB -> %s"
          % (sum(1 for f in BUNDLE.rglob("*") if f.is_file()), total / 1e6,
             BUNDLE.relative_to(BASE_DIR)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

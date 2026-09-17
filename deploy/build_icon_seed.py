"""Generate `data/mapped/monster_icon_slugs.json` — seed hasil resolve icon.

Kenapa perlu: `MonsterDB.resolve_icon_slug()` probe CDN (HEAD) per codename
dengan timeout 15 s dan cache-nya hanya in-memory. Di hosting serverless
(Vercel Functions) instance dingin tanpa cache akan memprosem ulang semua
monster saat `GET /api/monsters` — bisa melebihi `maxDuration`. Seed ini
di-commit sehingga resolve langsung dari file, tanpa jaringan.

Jalankan ulang kalau daftar monster/CDN berubah: `python deploy/build_icon_seed.py`
Shortcut: kalau `.imgcache/monster/<slug>.cache` sudah ada, tidak perlu probe.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

OUT = BASE / "data" / "mapped" / "monster_icon_slugs.json"
MON_CACHE = BASE / ".imgcache" / "monster"
CDN_BASE = "https://static.nanoka.cc/assets/zzz/"
PROBE_TIMEOUT = 6


def head_ok(cand: str) -> bool:
    req = urllib.request.Request(CDN_BASE + cand + ".webp", method="HEAD",
                                 headers={"User-Agent": "ZZZDamageCalc/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as resp:
            return resp.status == 200
    except Exception:
        return False


def main() -> int:
    import monster_data as md

    db = md.MonsterDB(str(BASE))
    suffixes = getattr(md, "_CARD_SUFFIXES", ())
    slugs: dict[str, str | None] = {}
    names = sorted(set(db._codename_by_cfg.values()))
    t0 = time.time()
    for codename in names:
        stem = codename[len("Monster_"):] if codename.startswith("Monster_") else codename
        candidates = [codename]
        for s in suffixes:
            if stem.endswith(s) and len(stem) > len(s):
                cand = codename[: -len(s)].rstrip("_")
                if cand != codename and cand not in candidates:
                    candidates.append(cand)
        slug = None
        for cand in candidates:
            if (MON_CACHE / (cand + ".cache")).is_file() or head_ok(cand):
                slug = cand
                break
        slugs[codename] = slug
    resolved = sum(1 for v in slugs.values() if v)
    payload = {
        "note": "Seed icon-slug monster (CDN nanoka). Regenerate: python deploy/build_icon_seed.py",
        "generated_epoch": int(time.time()),
        "resolved": resolved,
        "total": len(slugs),
        "slugs": dict(sorted(slugs.items())),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("seed: %d/%d resolved dalam %.1fs -> %s"
          % (resolved, len(slugs), time.time() - t0, OUT.relative_to(BASE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

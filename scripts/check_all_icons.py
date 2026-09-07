#!/usr/bin/env python3
"""Check every icon referenced by the game data through the local server.

Run the server first:  python server.py 8787
Then:                  python check_all_icons.py 8787

Each icon is requested via /ui/zzz/ so the disk cache gets warmed too.
"""
import json
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data"


def collect_icons():
    av = json.loads((BASE / "avatars.json").read_text(encoding="utf-8"))
    wp = json.loads((BASE / "weapons.json").read_text(encoding="utf-8"))
    eq = json.loads((BASE / "equipments.json").read_text(encoding="utf-8"))
    icons = {}
    for aid, v in av.items():
        if v.get("CircleIcon"):
            icons[v["CircleIcon"]] = f"avatar {aid}"
    for wid, v in wp.items():
        if v.get("ImagePath"):
            icons[v["ImagePath"]] = f"weapon {wid}"
    for sid, s in eq.get("Suits", {}).items():
        if s.get("Icon"):
            icons[s["Icon"]] = f"suit {sid}"
    return icons


def check_one(base, path, label):
    url = base + urllib.parse.quote(path)
    req = urllib.request.Request(url, headers={"User-Agent": "icon-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            n = len(resp.read())
            return (path, label, resp.status, n)
    except Exception as e:
        return (path, label, getattr(e, "code", str(e)), 0)


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "8787"
    base = f"http://127.0.0.1:{port}"
    icons = collect_icons()
    print(f"Checking {len(icons)} icons against {base} ...")
    bad = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(check_one, base, p, l) for p, l in icons.items()]
        for i, f in enumerate(futs, 1):
            path, label, code, size = f.result()
            if code == 200 and size > 0:
                print(f"OK   [{i:>3}/{len(icons)}] {path} ({size//1024} KB)  <- {label}")
            else:
                print(f"FAIL [{i:>3}/{len(icons)}] {path}  HTTP {code}  <- {label}")
                bad.append((path, code))
    print()
    if bad:
        print(f"{len(bad)} broken icon(s):")
        for p, c in bad:
            print(f"  {p}  (HTTP {c})")
        sys.exit(1)
    print(f"All {len(icons)} icons OK - cache warmed.")


if __name__ == "__main__":
    main()

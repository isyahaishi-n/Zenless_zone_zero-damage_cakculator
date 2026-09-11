#!/usr/bin/env python3
"""Local server for the ZZZ Enka showcase viewer + damage calculator.

Endpoints:
  GET /                  -> site/index.html
  GET /static/<file>     -> site assets
  GET /api/data          -> combined game data (avatars, weapons, discs, locale, ...)
  GET /api/uid/<uid>     -> proxies https://enka.network/api/zzz/uid/<uid>
  GET /api/local         -> bundled sample showcase (dumps/1303558818.json)
  GET /api/monsters      -> list monster utk picker (name/class/RES/icon; icon slug pre-resolved)
  POST /api/calc         -> hitung stat panel + damage per skill utk 1 karakter showcase
                            body: {"showcase": <enka json>, "avatar_id": 1091,
                                   "enemy": "Tyrfing", "enemy_level": 60,
                                   "stunned": false}
  GET /img/monster/<slug>-> proxy monster card WebP dari static.nanoka.cc (disk-cached)
  GET /ui/zzz/<file>     -> proxies https://enka.network/ui/zzz/<file> (disk-cached)

Stdlib only - no dependencies.
"""
from __future__ import annotations

import json
import mimetypes
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / "site"
CACHE_DIR = BASE_DIR / ".imgcache"
MONSTER_CACHE_DIR = CACHE_DIR / "monster"
SAMPLE = BASE_DIR / "dumps" / "1303558818.json"
ENKA_API = "https://enka.network/api/zzz/uid/"
ENKA_UI = "https://enka.network/ui/zzz/"
NANOKA_ASSET = "https://static.nanoka.cc/assets/zzz/"
UA = {"User-Agent": "Mozilla/5.0 (zzz-showcase-local/1.0)"}

CALC_CONTEXT = None  # lazy: loaded once (all game data + mapped files + skill index)
MONSTER_DB = None
MONSTER_LIST = None  # lazy: pre-resolved list for /api/monsters

# --- obfuscated template tables -------------------------------------------
TB_ROOT_KEY = "MLOEFHJHCID"

WEAPON_LEVEL_FIELDS = {
    "APDCBEGPHJO": "Rarity",
    "GJGMIBEOBHP": "Level",
    "EOMOGNMMOEJ": "EnhanceRate",
}
WEAPON_STAR_FIELDS = {
    "APDCBEGPHJO": "Rarity",
    "LMBCLMNIJNA": "BreakLevel",
    "EENDAEFLEJO": "StarRate",
    "IIPAHNFIJOH": "RandRate",
}
EQUIPMENT_LEVEL_FIELDS = {
    "APDCBEGPHJO": "Rarity",
    "GJGMIBEOBHP": "Level",
    "EOMOGNMMOEJ": "EnhanceRate",
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_template_table(path: Path, field_map: dict) -> list[dict]:
    raw = load_json(path)
    rows = raw[TB_ROOT_KEY] if isinstance(raw, dict) and TB_ROOT_KEY in raw else raw
    out = []
    for row in rows:
        out.append({name: int(row[key]) for key, name in field_map.items() if key in row})
    return out


def build_game_data() -> dict:
    return {
        "avatars": load_json(BASE_DIR / "data" / "avatars.json"),
        "weapons": load_json(BASE_DIR / "data" / "weapons.json"),
        "equipments": load_json(BASE_DIR / "data" / "equipments.json"),
        "locale": load_json(BASE_DIR / "data" / "locale_en.json"),
        "mindscapes": load_json(BASE_DIR / "data" / "mindscapes.json"),
        "mindscapeProps": load_json(BASE_DIR / "data" / "mindscape_props.json"),
        "driveDiscSets": load_json(BASE_DIR / "data" / "mapped" / "drive_disc_mapped.json"),
        "weaponLevels": load_template_table(BASE_DIR / "data" / "WeaponLevelTemplateTb.json", WEAPON_LEVEL_FIELDS),
        "weaponStars": load_template_table(BASE_DIR / "data" / "WeaponStarTemplateTb.json", WEAPON_STAR_FIELDS),
        "equipmentLevels": load_template_table(BASE_DIR / "data" / "EquipmentLevelTemplateTb.json", EQUIPMENT_LEVEL_FIELDS),
    }


GAME_DATA = None  # populated lazily on first /api/data request


def fetch(url: str, timeout: int = 25) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "application/octet-stream")


# --------------------------------------------------------------------------
# Damage calculator wiring (run.py components, loaded once)
# --------------------------------------------------------------------------

def build_calc_context() -> dict:
    """Load semua data pendukung kalkulator sekali (lazy, sekali per proses)."""
    global CALC_CONTEXT, MONSTER_DB
    if CALC_CONTEXT is not None:
        return CALC_CONTEXT
    import zzz_enka_stat_calc_multichar as calc
    import damage_calc as dc
    import monster_data
    import skill_lookup  # noqa: F401  (dipakai calc.load_skill_data)

    MONSTER_DB = monster_data.MonsterDB(BASE_DIR)
    ctx = {
        "calc": calc, "dc": dc, "monster_db": MONSTER_DB,
        "weapons": calc.load_json(BASE_DIR / "data" / "weapons.json"),
        "equipments": calc.load_json(BASE_DIR / "data" / "equipments.json"),
        "avatars": calc.load_json(BASE_DIR / "data" / "avatars.json"),
        "locale": calc.load_json(BASE_DIR / "data" / "locale_en.json"),
        "wl": calc.load_template_table(BASE_DIR / "data" / "WeaponLevelTemplateTb.json", calc.WEAPON_LEVEL_FIELDS),
        "ws": calc.load_template_table(BASE_DIR / "data" / "WeaponStarTemplateTb.json", calc.WEAPON_STAR_FIELDS),
        "el": calc.load_template_table(BASE_DIR / "data" / "EquipmentLevelTemplateTb.json", calc.EQUIPMENT_LEVEL_FIELDS),
        "skill_index": None, "name_map": None, "textmap": None,
        "wengines": dc.load_wengine_passives(str(BASE_DIR / "data" / "mapped" / "wengine_passive_mapped.json")),
        "sets": dc.load_drive_disc_sets(str(BASE_DIR / "data" / "mapped" / "drive_disc_mapped.json")),
        "mindscapes": dc.load_mindscapes(str(BASE_DIR / "data" / "mapped" / "mindscape_mapped.json")),
    }
    skill_index, name_map, textmap = calc.load_skill_data(BASE_DIR)
    ctx["skill_index"], ctx["name_map"], ctx["textmap"] = skill_index, name_map, textmap
    CALC_CONTEXT = ctx
    return ctx


def calculate_avatar(api_showcase: dict, avatar_id: int, enemy_name: str,
                     enemy_level: int = 60, stunned: bool = False) -> dict:
    """Full pipeline untuk satu karakter dari showcase Enka -> JSON untuk UI."""
    ctx = build_calc_context()
    calc, dc = ctx["calc"], ctx["dc"]
    db = ctx["monster_db"]

    avatars_list = api_showcase.get("PlayerInfo", {}).get("ShowcaseDetail", {}).get("AvatarList", [])
    avatar = next((a for a in avatars_list if int(a["Id"]) == avatar_id), None)
    if avatar is None:
        raise LookupError(f"avatar {avatar_id} tidak ada di showcase")

    m = db.resolve(enemy_name, level=enemy_level)  # LookupError kalau nama invalid
    enemy = dc.EnemyStats(def_val=m["def_val"], res_pct=m["res_pct"],
                          stun_taken_pct=m["stun_taken_pct"])

    snap = calc.compute_avatar_snapshot(
        avatar, avatar_id, ctx["avatars"], ctx["weapons"], ctx["equipments"],
        ctx["wl"], ctx["ws"], ctx["el"],
        ctx["skill_index"], ctx["name_map"], ctx["textmap"], ctx["locale"],
    )
    rows = compute_all_damage_standalone(snap, enemy, stunned)

    # toggles aktif utk transparency UI
    toggles = []
    for t in _last_toggles:
        toggles.append({
            "source": t.source,
            "source_name": t.source_name,
            "stat": t.stat,
            "value": t.value,
            "unit": t.unit,
            "condition": t.condition_text,
            "enabled": bool(t.enabled),
            "mode": t.mode,
        })

    return {
        "avatar": {
            "name": snap["name"], "level": snap["level"], "element": snap["element"],
            "profession": snap["profession"], "mindscape": snap["mindscape"],
            "core": snap.get("core", 0),
        },
        "stats": snap["stats"],
        "weapon": snap.get("weapon"),
        "set4pc": snap.get("set4pc", []),
        "toggles": toggles,
        "enemy": {
            "name": m["name"], "level": m["level"],
            "rank": m["rank"], "size": m["size"], "faction": m["faction"],
            "rarity": m["rarity"], "icon_url": m["icon_url"],
            "def_val": m["def_val"], "hp_val": m["hp_val"],
            "res_pct": m["res_pct"], "stun_taken_pct": m["stun_taken_pct"],
        },
        "stunned": stunned,
        "rows": rows,
    }


# re-implement compute_all_damage (run.py) supaya server gak import run.py
# (run.py punya arg parsing side-effect minimal, tapi lebih bersih standalone)
_last_toggles = []


def compute_all_damage_standalone(snapshot: dict, enemy, stunned: bool = False) -> list:
    ctx = build_calc_context()
    dc = ctx["dc"]
    stats = snapshot["stats"]
    weapon = snapshot["weapon"]

    toggles = []
    if weapon.get("id"):
        toggles += dc.build_wengine_toggles(ctx["wengines"], weapon_id=weapon["id"],
                                            phase=weapon.get("phase", 1))
    for set_name in snapshot.get("set4pc", []):
        toggles += dc.build_set4pc_toggles(ctx["sets"], set_name=set_name)
    toggles += dc.build_mindscape_toggles(ctx["mindscapes"], avatar_id=snapshot["avatar_id"],
                                           mindscape_rank=snapshot.get("mindscape", 0))
    dc.evaluate_thresholds(toggles, panel=stats)

    _last_toggles.clear()
    _last_toggles.extend(toggles)

    results = []
    for skill_idx, skill_data in snapshot.get("skills", {}).items():
        mods = dc.aggregate_modifiers(toggles, skill_type=skill_data["label"])
        for hit in skill_data["hits"]:
            if hit["is_hidden"]:
                continue
            r = dc.compute_final_damage(
                atk_panel=stats["ATK"],
                skill_mult_pct=hit["damage_pct"],
                crit_dmg_panel_pct=stats.get("CRIT DMG", 0.0),
                enemy=enemy,
                element=snapshot.get("element", "Physical"),
                pen_ratio_pct=stats.get("PEN Ratio", 0.0),
                pen_flat=stats.get("PEN", 0.0),
                mods=mods,
                enemy_stunned=stunned,
            )
            results.append({
                "skill": skill_data["label"],
                "hit": hit["name"],
                "damage_pct": hit["damage_pct"],
                "daze_pct": hit.get("daze_pct", 0.0),
                "non_crit": r["non_crit"],
                "crit": r["crit"],
                "stun_non_crit": r["non_crit"] * (1 + enemy.stun_taken_pct),
            })
    return results


def build_monster_list() -> list:
    """List semua monster utk picker UI — icon slug di-pre-resolve sekali."""
    global MONSTER_LIST
    if MONSTER_LIST is not None:
        return MONSTER_LIST
    ctx = build_calc_context()
    db = ctx["monster_db"]
    out = []
    for name in db.list_names():
        m = db.resolve(name, level=60)  # level dummy; UI kirim level sendiri
        out.append({
            "name": m["name"], "codename": m["codename"],
            "rank": m["rank"], "size": m["size"], "faction": m["faction"],
            "rarity": m["rarity"], "icon_url": m["icon_url"],
            "res_pct": m["res_pct"],
        })
    # sort: boss dulu (rarity desc), lalu alfabetis
    order = {"MainStoryBoss": 0, "Boss": 1, "Elite": 2, "LittleMonster": 3, None: 4}
    out.sort(key=lambda x: (order.get(x["rank"], 4), -(x["rarity"] or 0), x["name"]))
    MONSTER_LIST = out
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "ZZZShowcase/1.0"

    # ---- helpers ----
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self._send(200, path.read_bytes(), ctype, {"Cache-Control": "max-age=60"})

    def log_message(self, fmt, *args) -> None:
        pass  # keep the console quiet

    # ---- routes ----
    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                self._send_file(SITE_DIR / "index.html")

            elif path.startswith("/static/"):
                rel = path[len("/static/"):]
                target = (SITE_DIR / "static" / rel).resolve()
                if not str(target).startswith(str(SITE_DIR.resolve())):
                    self._send(403, b"Forbidden", "text/plain; charset=utf-8")
                    return
                self._send_file(target)

            elif path == "/api/data":
                global GAME_DATA
                if GAME_DATA is None:
                    GAME_DATA = build_game_data()
                self._send_json(GAME_DATA)

            elif path == "/api/local":
                if SAMPLE.is_file():
                    self._send(200, SAMPLE.read_bytes(), "application/json; charset=utf-8")
                else:
                    self._send_json({"error": "no bundled sample"}, 404)

            elif path == "/api/monsters":
                self._send_json({"monsters": build_monster_list()})

            elif path.startswith("/img/monster/"):
                slug = urllib.parse.unquote(path[len("/img/monster/"):])
                if not re.fullmatch(r"[\w.\-]+", slug):
                    self._send(403, b"Forbidden", "text/plain; charset=utf-8")
                    return
                MONSTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache = MONSTER_CACHE_DIR / (slug + ".cache")
                if cache.is_file():
                    self._send(200, cache.read_bytes(), "image/webp",
                               {"Cache-Control": "max-age=86400"})
                    return
                try:
                    body, ctype = fetch(NANOKA_ASSET + slug)
                    cache.write_bytes(body)
                    self._send(200, body, ctype, {"Cache-Control": "max-age=86400"})
                except Exception:
                    self._send(404, b"Image not found", "text/plain; charset=utf-8")

            elif path.startswith("/api/uid/"):
                uid = path[len("/api/uid/"):]
                if not re.fullmatch(r"\d{6,12}", uid):
                    self._send_json({"error": "Invalid UID"}, 400)
                    return
                try:
                    body, ctype = fetch(ENKA_API + uid)
                    self._send(200, body, ctype)
                except urllib.error.HTTPError as e:
                    msg = {404: "Player not found (check UID / showcase visibility)"}.get(
                        e.code, f"Enka returned HTTP {e.code}"
                    )
                    self._send(e.code, json.dumps({"error": msg}).encode("utf-8"), "application/json; charset=utf-8")
                except Exception as e:
                    self._send_json({"error": f"Could not reach enka.network: {e}"}, 502)

            elif path.startswith("/ui/zzz/"):
                name = urllib.parse.unquote(path[len("/ui/zzz/"):])
                if ".." in name or "/" in name or "\\" in name or not re.fullmatch(r"[\w.\-&(),+'! ]+", name):
                    self._send(403, b"Forbidden", "text/plain; charset=utf-8")
                    return
                cache = CACHE_DIR / name
                if cache.is_file():
                    ctype = mimetypes.guess_type(str(cache))[0] or "image/png"
                    self._send(200, cache.read_bytes(), ctype, {"Cache-Control": "max-age=86400"})
                    return
                try:
                    body, ctype = fetch(ENKA_UI + name)
                    CACHE_DIR.mkdir(exist_ok=True)
                    cache.write_bytes(body)
                    self._send(200, body, ctype, {"Cache-Control": "max-age=86400"})
                except Exception:
                    self._send(404, b"Image not found", "text/plain; charset=utf-8")

            else:
                self._send(404, b"Not found", "text/plain; charset=utf-8")

        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                self._send_json({"error": str(e)}, 500)
            except Exception:
                pass

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        try:
            if path != "/api/calc":
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            showcase = payload.get("showcase")
            avatar_id = payload.get("avatar_id")
            enemy = payload.get("enemy", "Tyrfing")
            enemy_level = int(payload.get("enemy_level", 60))
            stunned = bool(payload.get("stunned", False))
            if not showcase or avatar_id is None:
                self._send_json({"error": "body butuh 'showcase' dan 'avatar_id'"}, 400)
                return
            result = calculate_avatar(showcase, int(avatar_id), str(enemy),
                                       enemy_level=enemy_level, stunned=stunned)
            self._send_json(result)
        except LookupError as e:
            self._send_json({"error": str(e)}, 404)
        except KeyError as e:
            self._send_json({"error": f"missing data: {e}"}, 400)
        except Exception as e:
            try:
                self._send_json({"error": str(e)}, 500)
            except Exception:
                pass


def main() -> None:
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    CACHE_DIR.mkdir(exist_ok=True)
    print(f"ZZZ Showcase server running at http://localhost:{port}")
    print("Endpoints: /api/monsters, POST /api/calc, /img/monster/<slug>")
    print("Press Ctrl+C to stop.")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
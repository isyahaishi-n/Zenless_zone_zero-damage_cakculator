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
                                   "stunned": false,
                                   "specials": {"disorder": [...],
                                                "polarity": [...],
                                                "vortex": [...]},  # opsional
                                   "toggle_overrides": {toggle_id: bool}} # opsional
                            -> response nambah field `special` (baris
                               Disorder/Polarity/Vortex per instance, item 5)
                               + `toggles[].id` (checkbox buff, item 12)
  POST /api/rotation     -> hitung rotasi penuh (normal/stun + disorder/polarity/
                            vortex) utk 1 karakter (item 7/10)
                            body: {"showcase": ..., "avatar_id": 1091,
                                   "enemy": "Tyrfing", "enemy_level": 60,
                                   "rotation": {time, normal, stun, ...},
                                   "toggle_overrides": {...}}  # opsional
                            -> {report, toggles, avatar, enemy}
  POST /api/team-rotation-> agregasi rotasi beberapa slot (item 11) — buff
                            lintas-slot (item 6) BELUM termasuk
                            body: {"showcase": ..., "enemy": "Tyrfing",
                                   "rotations": {avatar_id: rotation, ...}}
                            -> {total, dps, distribution, slots[], skipped[]}
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


def _prepare_avatar(api_showcase: dict, avatar_id: int, enemy_name: str,
                    enemy_level: int):
    """Resolve ctx + snapshot + enemy utk satu avatar (dipakai /api/calc &
    /api/rotation). Return (ctx, dc, snap, enemy, monster)."""
    ctx = build_calc_context()
    calc, dc = ctx["calc"], ctx["dc"]
    db = ctx["monster_db"]

    avatars_list = api_showcase.get("PlayerInfo", {}).get("ShowcaseDetail", {}).get("AvatarList", [])
    avatar = next((a for a in avatars_list if int(a["Id"]) == avatar_id), None)
    if avatar is None:
        raise LookupError(f"avatar {avatar_id} tidak ada di showcase")

    m = db.resolve(enemy_name, level=enemy_level)  # LookupError kalau nama invalid
    enemy = dc.EnemyStats(def_val=m["def_val"], res_pct=m["res_pct"],
                          stun_taken_pct=m["stun_taken_pct"],
                          daze_res_pct=m["daze_res_pct"],
                          buildup_res_pct=m["buildup_res_pct"])

    snap = calc.compute_avatar_snapshot(
        avatar, avatar_id, ctx["avatars"], ctx["weapons"], ctx["equipments"],
        ctx["wl"], ctx["ws"], ctx["el"],
        ctx["skill_index"], ctx["name_map"], ctx["textmap"], ctx["locale"],
    )
    return ctx, dc, snap, enemy, m


def _toggles_payload(dc, toggles: list) -> list:
    """ToggleEntry -> JSON utk UI (termasuk `id` utk override item 12)."""
    return [{
        "id": dc.toggle_id(t),
        "source": t.source,
        "source_name": t.source_name,
        "stat": t.stat,
        "value": t.value,
        "unit": t.unit,
        "condition": t.condition_text,
        "enabled": bool(t.enabled),
        "mode": t.mode,
        "skill_types": list(t.skill_types),
        "elements": list(t.elements),
        "stacks": t.stacks,
        "stacks_max": t.stacks_max,
        "needs_review": bool(t.needs_review),
    } for t in toggles]


def calculate_avatar(api_showcase: dict, avatar_id: int, enemy_name: str,
                     enemy_level: int = 60, stunned: bool = False,
                     specials: dict | None = None,
                     toggle_overrides: dict | None = None) -> dict:
    """Full pipeline untuk satu karakter dari showcase Enka -> JSON untuk UI.

    `specials` opsional = {"disorder": [...], "polarity": [...], "vortex": [...]}
    (item 5) — list spec per instance; hasilnya dikembalikan di field `special`
    (per-instance, `total` = damage x count). Tanpa auto-deteksi: trigger harus
    dikirim eksplisit oleh UI.
    """
    ctx, dc, snap, enemy, m = _prepare_avatar(
        api_showcase, avatar_id, enemy_name, enemy_level)
    rows = compute_all_damage_standalone(snap, enemy, stunned, toggle_overrides)
    special_rows = _compute_special_rows(dc, snap, enemy, specials)
    toggles = _toggles_payload(dc, _last_toggles)

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
        "special": special_rows,
    }


_SPECIAL_KINDS = ("disorder", "polarity", "vortex")


def _compute_special_rows(dc, snapshot: dict, enemy, specials: dict | None) -> list:
    """Baris sintetis Disorder/Polarity/Vortex (item 5) utk UI.

    Tiap spec dihitung lewat `dc.build_special_rows` (chain formula sama dgn
    rotasi) satu per satu supaya satu elemen invalid tidak menggagalkan
    seluruh request — baris error dikembalikan dgn `error` terisi.
    Toggle diambil dari `_last_toggles` yang barusan diisi
    compute_all_damage. Return list {kind, element, base_pct, count, damage,
    total, error}.
    """
    if not specials:
        return []
    out = []
    for kind in _SPECIAL_KINDS:
        for spec in specials.get(kind) or []:
            element = spec.get("element") or snapshot.get("element")
            count = float(spec.get("count", 1) or 0)
            try:
                raw = dc.build_special_rows(snapshot, enemy, _last_toggles, {kind: [spec]})
                r = raw[0]
            except (KeyError, ValueError) as e:
                out.append({
                    "kind": kind, "element": element, "base_pct": 0.0,
                    "count": count, "damage": 0.0, "total": 0.0,
                    "error": str(e),
                })
                continue
            damage = float(r.get("non_crit", 0.0))
            out.append({
                "kind": kind,
                "element": r.get("hit_element"),
                "base_pct": float(r.get("damage_pct", 0.0)),
                "count": float(r.get("count", 1) or 0),
                "damage": damage,
                "total": damage * float(r.get("count", 1) or 0),
                "error": None,
            })
    return out


# re-implement compute_all_damage (run.py) supaya server gak import run.py
# (run.py punya arg parsing side-effect minimal, tapi lebih bersih standalone)
# Versi lama diduplikasi bug run.py (tanpa CR/elemen per-hit); sekarang
# delegasi ke damage_calc.compute_all_damage shared.
_last_toggles = []


def compute_all_damage_standalone(snapshot: dict, enemy, stunned: bool = False,
                                  toggle_overrides: dict | None = None) -> list:
    ctx = build_calc_context()
    dc = ctx["dc"]
    rows, toggles = dc.compute_all_damage(
        snapshot, enemy, ctx["wengines"], ctx["sets"], ctx["mindscapes"],
        enemy_stunned=stunned, toggle_overrides=toggle_overrides,
    )
    _last_toggles.clear()
    _last_toggles.extend(toggles)
    return [{
        "skill": r["skill_label"],
        "skill_category": r.get("skill_category"),
        "hit": r["hit_name"],
        "hit_id": r.get("hit_id"),
        "element": r["hit_element"],
        "damage_pct": r["damage_pct"],
        "daze_pct": r.get("daze_pct", 0.0),
        "buildup_pct": r.get("buildup_pct", 0.0),
        "non_crit": r["non_crit"],
        "crit": r["crit"],
        "expected": r.get("expected"),
        "stun_non_crit": r["non_crit"] * (1 + enemy.stun_taken_pct),
        "daze": r.get("daze", 0.0),
        "buildup": r.get("buildup", 0.0),
        "anomaly_tick": bool(r.get("anomaly_tick")),
    } for r in rows]


def calculate_rotation(api_showcase: dict, avatar_id: int, enemy_name: str,
                       rotation: dict, enemy_level: int = 60,
                       toggle_overrides: dict | None = None) -> dict:
    """Rotasi penuh (item 7) utk satu karakter -> report + toggles (item 10).

    `rotation` = dict format `rotations/*.json` (time, normal/stun, repeat,
    rotation_mult, disorder/polarity/vortex). Error resolusi hit
    (`LookupError` dari normalize/resolve) dibiarkan naik -> HTTP 404/400.
    """
    ctx, dc, snap, enemy, _m = _prepare_avatar(
        api_showcase, avatar_id, enemy_name, enemy_level)
    report, toggles = dc.compute_rotation(
        snap, enemy, ctx["wengines"], ctx["sets"], ctx["mindscapes"],
        rotation, toggle_overrides=toggle_overrides)
    report["avatar_id"] = avatar_id
    report["toggles_enabled"] = sum(1 for t in toggles if t.enabled)
    return {
        "report": report,
        "toggles": _toggles_payload(dc, toggles),
        "avatar": {
            "name": snap["name"], "level": snap["level"],
            "element": snap["element"], "profession": snap["profession"],
            "mindscape": snap["mindscape"], "core": snap.get("core", 0),
        },
        "enemy": {
            "name": _m["name"], "level": _m["level"],
            "def_val": _m["def_val"], "stun_taken_pct": _m["stun_taken_pct"],
        },
    }


def calculate_team_rotation(api_showcase: dict, enemy_name: str,
                            rotations: dict, enemy_level: int = 60,
                            toggle_overrides: dict | None = None) -> dict:
    """Agregasi rotasi beberapa slot (item 11) -> total/DPS/distribusi tim.

    `rotations` = {avatar_id: rotation_dict} (format sama `rotations/*.json`,
    key = avatar id string/int). Slot yang tidak ada di showcase di-skip
    dengan catatan di `skipped`.

    CATATAN: ini agregasi murni per-slot — buff LINTAS SLOT (Team Buffs,
    item 6) belum dimodelkan, jadi angka tiap slot tidak saling
    mempengaruhi.
    """
    if not isinstance(rotations, dict) or not rotations:
        raise ValueError("body butuh 'rotations' (dict avatar_id -> rotation)")

    ctx = build_calc_context()
    dc = ctx["dc"]
    per_slot = []
    skipped = []
    for aid_raw, rot in rotations.items():
        try:
            aid = int(aid_raw)
        except (TypeError, ValueError):
            skipped.append(str(aid_raw))
            continue
        try:
            res = calculate_rotation(api_showcase, aid, enemy_name, rot or {},
                                     enemy_level=enemy_level,
                                     toggle_overrides=toggle_overrides)
        except LookupError as e:
            skipped.append({"avatar_id": aid, "reason": str(e)[:120]})
            continue
        rep = res["report"]
        per_slot.append({
            "avatar_id": aid,
            "name": rep.get("avatar"),
            "time": rep["time"],
            "total": rep["total"],
            "dps": rep["dps"],
            "total_daze": rep["total_daze"],
            "total_buildup": rep["total_buildup"],
            "distribution": rep["distribution"],
        })

    if not per_slot:
        raise ValueError("tidak ada slot valid untuk dihitung (cek 'rotations')")

    team_time = max(s["time"] for s in per_slot) or 0.0
    total = sum(s["total"] for s in per_slot)
    total_daze = sum(s["total_daze"] for s in per_slot)
    total_buildup = sum(s["total_buildup"] for s in per_slot)

    agg = {}
    for s in per_slot:
        for d in s["distribution"]:
            c = d["category"]
            row = agg.setdefault(c, {"category": c, "damage": 0.0, "non_crit": 0.0,
                                     "crit": 0.0, "daze": 0.0, "buildup": 0.0})
            for k in ("damage", "non_crit", "crit", "daze", "buildup"):
                row[k] += d.get(k, 0.0)

    distribution = []
    for c in dc.DISTRIBUTION_CATEGORIES:
        row = agg.get(c)
        if not row:
            continue
        row = dict(row)
        row["pct"] = (row["damage"] / total * 100.0) if total else 0.0
        distribution.append(row)

    times = sorted({s["time"] for s in per_slot})
    return {
        "time": team_time,
        "times": times,
        "time_mismatch": len(times) > 1,
        "total": total,
        "dps": (total / team_time) if team_time else 0.0,
        "total_daze": total_daze,
        "total_buildup": total_buildup,
        "distribution": distribution,
        "slots": per_slot,
        "skipped": skipped,
    }


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
            if path not in ("/api/calc", "/api/rotation", "/api/team-rotation"):
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            showcase = payload.get("showcase")
            avatar_id = payload.get("avatar_id")
            enemy = payload.get("enemy", "Tyrfing")
            enemy_level = int(payload.get("enemy_level", 60))
            toggle_overrides = payload.get("toggle_overrides") or None
            if not showcase or (avatar_id is None and path != "/api/team-rotation"):
                self._send_json({"error": "body butuh 'showcase' dan 'avatar_id'"}, 400)
                return
            if path == "/api/team-rotation":
                rotations = payload.get("rotations")
                if not isinstance(rotations, dict):
                    self._send_json({"error": "body butuh 'rotations' (dict)"}, 400)
                    return
                self._send_json(calculate_team_rotation(
                    showcase, str(enemy), rotations,
                    enemy_level=enemy_level, toggle_overrides=toggle_overrides))
                return
            if path == "/api/rotation":
                rotation = payload.get("rotation")
                if not isinstance(rotation, dict):
                    self._send_json({"error": "body butuh 'rotation' (dict)"}, 400)
                    return
                self._send_json(calculate_rotation(
                    showcase, int(avatar_id), str(enemy), rotation,
                    enemy_level=enemy_level, toggle_overrides=toggle_overrides))
                return
            stunned = bool(payload.get("stunned", False))
            specials = payload.get("specials") or None
            result = calculate_avatar(showcase, int(avatar_id), str(enemy),
                                       enemy_level=enemy_level, stunned=stunned,
                                       specials=specials,
                                       toggle_overrides=toggle_overrides)
            self._send_json(result)
        except LookupError as e:
            self._send_json({"error": str(e)}, 404)
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)
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
    print("Endpoints: /api/monsters, POST /api/calc, POST /api/rotation, POST /api/team-rotation, /img/monster/<slug>")
    print("Press Ctrl+C to stop.")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
"""
run.py — pipeline lengkap: UID -> fetch Enka -> stat panel -> damage per skill.

Nyambungin 3 komponen yang sebelumnya terpisah (harus dijalanin manual satu-
satu lewat file):
    1. Fetch Enka (baru, logic dari fetch.py lama)
    2. zzz_enka_stat_calc_multichar.py -- compute_avatar_snapshot() (reuse,
       import langsung, bukan subprocess/file)
    3. damage_calc.py -- build_*_toggles() + compute_final_damage() (reuse)

Slot musuh (get_enemy_stats) sekarang baca dari data Monster asli via
monster_data.MonsterDB (TextMap + MonsterConfig + MonsterSub + LevelCurve),
field mapping verified terhadap Genshin-Optimizer/zzz-hakushin-data
(635/643 row exact; lihat docstring monster_data.py).

Usage:
    python run.py <uid> [--enemy "Tyrfing"] [--enemy-level 60] [--stunned]
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import zzz_enka_stat_calc_multichar as calc
import damage_calc as dc
import monster_data


# ---------------------------------------------------------------------------
# 1. Fetch Enka
# ---------------------------------------------------------------------------

ENKA_BASE_URL = "https://enka.network/api/zzz/uid/{uid}/"
HEADERS = {"User-Agent": "ZZZDamageCalc/1.0 (contact: your_email_or_discord)"}


def fetch_player_data(uid: str, retries: int = 3, delay: float = 2.0) -> dict:
    url = ENKA_BASE_URL.format(uid=uid)
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 424:
                raise RuntimeError(
                    f"UID {uid}: showcase unavailable (HTTP 424). Player harus buka "
                    "halaman detail karakter in-game dulu + showcase enabled."
                )
            elif e.code == 404:
                raise RuntimeError(f"UID {uid}: nggak ketemu (HTTP 404). Cek lagi UID-nya.")
            elif e.code == 429:
                if attempt < retries:
                    time.sleep(delay)
                    continue
                raise RuntimeError("Rate limited (HTTP 429). Coba lagi nanti.")
            else:
                raise RuntimeError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")
    raise RuntimeError("Gagal fetch setelah retry.")


# ---------------------------------------------------------------------------
# 2. Slot musuh — data Monster asli via monster_data.MonsterDB
# ---------------------------------------------------------------------------
#
# Field mapping MonsterSubTemplateTb sudah verified independen (korelasi 622
# monster dengan zzz-hakushin-data, 635/643 exact — detail di
# monster_data.py). Signature get_enemy_stats tetap sama seperti desain awal:
# (enemy_key) -> dc.EnemyStats; caller tidak perlu berubah.

_MONSTER_DB: monster_data.MonsterDB | None = None


def _get_monster_db() -> monster_data.MonsterDB:
    global _MONSTER_DB
    if _MONSTER_DB is None:
        _MONSTER_DB = monster_data.MonsterDB(Path(__file__).resolve().parent)
    return _MONSTER_DB


def get_enemy_stats(enemy_key: str, level: int = 60) -> dc.EnemyStats:
    """Slot musuh. Resolve nama -> stat dari data Monster asli.

    Raise LookupError (pesan jelas + saran nama) kalau nama tidak ada.
    Caller (compute_all_damage / main) tidak perlu berubah.
    """
    db = _get_monster_db()
    m = db.resolve(enemy_key, level=level)
    return dc.EnemyStats(
        def_val=m["def_val"],
        res_pct=m["res_pct"],
        stun_taken_pct=m["stun_taken_pct"],
        daze_res_pct=m["daze_res_pct"],
        buildup_res_pct=m["buildup_res_pct"],
    )


# ---------------------------------------------------------------------------
# 3. Gabungin stat panel + toggle -> damage per skill
# (implementasi shared di damage_calc.compute_all_damage — run.py cuma
#  delegasi supaya bugfix formula/args cukup sekali di satu tempat)
# ---------------------------------------------------------------------------

def compute_all_damage(snapshot: dict, enemy: dc.EnemyStats,
                       wengines: dict, sets: dict, mindscapes: dict,
                       enemy_stunned: bool = False) -> list:
    """Untuk satu avatar snapshot (dari compute_avatar_snapshot), hitung
    damage tiap hit non-hidden di semua skill, pakai toggle conditional
    yang otomatis ke-enable (unconditional + threshold yang lolos).
    """
    results, _toggles = dc.compute_all_damage(
        snapshot, enemy, wengines, sets, mindscapes,
        enemy_stunned=enemy_stunned)
    return results


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="UID -> stat panel -> damage per skill")
    parser.add_argument("uid", help="UID Enka (atau path profile JSON lokal dengan --profile)")
    parser.add_argument("--profile", action="store_true",
                        help="Argumen uid = path file JSON profile Enka lokal "
                             "(mis. dumps/1303558818.json), tanpa fetch.")
    parser.add_argument("--enemy", default="Tyrfing",
                        help="Nama musuh dari data Monster (default: Tyrfing). "
                             "Case-insensitive, mis. 'Haytor', 'The Defector'.")
    parser.add_argument("--enemy-level", type=int, default=60,
                        help="Level musuh buat scaling DEF/HP (default: 60)")
    parser.add_argument("--stunned", action="store_true",
                        help="Musuh dalam kondisi stun (aktifkan Stun Modifier: "
                             "damage x (1 + StunDamageTaken musuh))")
    parser.add_argument("--list-enemies", action="store_true",
                        help="Tampilkan daftar nama musuh yang tersedia lalu keluar")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent

    if args.list_enemies:
        db = monster_data.MonsterDB(base_dir)
        names = db.list_names()
        print(f"{len(names)} musuh tersedia:")
        for n in names:
            print(f"  {n}")
        return

    print(f"[1] {'Load profile lokal' if args.profile else 'Fetching UID ' + args.uid + ' dari Enka'}...")
    try:
        if args.profile:
            p = Path(args.uid)
            if not p.is_absolute():
                p = base_dir / p
            api = json.loads(p.read_text(encoding="utf-8"))
        else:
            api = fetch_player_data(args.uid)
    except (RuntimeError, FileNotFoundError) as e:
        sys.exit(f"Error: {e}")
    showcase = api["PlayerInfo"]["ShowcaseDetail"]
    avatars_list = showcase.get("AvatarList", [])
    if not avatars_list:
        sys.exit(f"UID {args.uid}: showcase kosong (0 karakter). "
                 "Player harus set karakter di showcase dulu.")
    print(f"    {len(avatars_list)} karakter di-showcase.")

    print("[2] Load data pendukung...")
    weapons = calc.load_json(base_dir / "data" / "weapons.json")
    equipments = calc.load_json(base_dir / "data" / "equipments.json")
    avatars = calc.load_json(base_dir / "data" / "avatars.json")
    locale_path = base_dir / "data" / "locale_en.json"
    loc = calc.load_json(locale_path) if locale_path.exists() else {}
    wl = calc.load_template_table(base_dir / "data" / "WeaponLevelTemplateTb.json", calc.WEAPON_LEVEL_FIELDS)
    ws = calc.load_template_table(base_dir / "data" / "WeaponStarTemplateTb.json", calc.WEAPON_STAR_FIELDS)
    el = calc.load_template_table(base_dir / "data" / "EquipmentLevelTemplateTb.json", calc.EQUIPMENT_LEVEL_FIELDS)
    skill_index, name_map, textmap = calc.load_skill_data(base_dir)

    wengines = dc.load_wengine_passives(str(base_dir / "data" / "mapped" / "wengine_passive_mapped.json"))
    sets = dc.load_drive_disc_sets(str(base_dir / "data" / "mapped" / "drive_disc_mapped.json"))
    mindscapes = dc.load_mindscapes(str(base_dir / "data" / "mapped" / "mindscape_mapped.json"))

    try:
        enemy = get_enemy_stats(args.enemy, level=args.enemy_level)
    except (ValueError, LookupError) as e:
        sys.exit(f"Error: {e}")
    db = _get_monster_db()
    m = db.resolve(args.enemy, level=args.enemy_level)
    weak = ", ".join(f"{e} {v*100:+.0f}%" for e, v in m["res_pct"].items() if v)
    print(f"    Musuh: {m['name']} Lv.{m['level']} (DEF={enemy.def_val:.2f}, "
          f"HP={m['hp_val']:.0f}, StunDmgTaken +{m['stun_taken_pct']*100:.0f}%)")
    if weak:
        print(f"    RES: {weak}")

    for avatar in avatars_list:
        avatar_id = int(avatar["Id"])
        snapshot = calc.compute_avatar_snapshot(
            avatar, avatar_id, avatars, weapons, equipments, wl, ws, el,
            skill_index, name_map, textmap, loc,
        )

        print()
        print("=" * 62)
        print(f"{snapshot['name']}  Lv.{snapshot['level']}  "
              f"[{snapshot['element']} {snapshot['profession']}]  M{snapshot['mindscape']}")
        stats = snapshot["stats"]
        print(f"  ATK {stats['ATK']:.0f} | CRIT Rate {stats.get('CRIT Rate', 0):.1f}% | "
              f"CRIT DMG {stats.get('CRIT DMG', 0):.1f}%")

        damage_rows = compute_all_damage(snapshot, enemy, wengines, sets, mindscapes,
                                         enemy_stunned=args.stunned)
        if not damage_rows:
            print("  (nggak ada weapon/skill data buat dihitung -- karakter tanpa gear?)")
            continue

        stun_note = " [STUNNED]" if args.stunned else ""
        print(f"  -- Damage vs {m['name']} Lv.{m['level']}{stun_note} --")
        for r in damage_rows:
            # Daze-only hit (damage base 0, daze > 0 di skill data asli):
            # tampilkan daze final (Impact_combat x dazeMV% x (1-DazeRES)
            # x (1+ΣDaze%)), bukan damage 0.0 yang menyesatkan.
            if r.get("anomaly_tick"):
                print(f"    {r['skill_label']:20s} {r['hit_name']:35s} [{r['hit_element']:8s}]"
                      f"  per-tick {r['damage_pct']:6.1f}%  ->  non-crit {r['non_crit']:8.1f}"
                      f"  (AP-scaled; tick count = rotasi)")
            elif r["damage_pct"] <= 0 and r.get("daze_pct", 0) > 0:
                print(f"    {r['skill_label']:20s} {r['hit_name']:35s} "
                      f"(daze-only)  daze {r['daze_pct']:7.1f}%  "
                      f"->  daze {r.get('daze', 0.0):8.1f}")
            else:
                elem = r.get("hit_element") or snapshot.get("element", "?")
                extras = ""
                if r.get("daze_pct", 0) > 0:
                    extras += f"  daze {r.get('daze', 0.0):7.1f}"
                if r.get("buildup_pct", 0) > 0:
                    extras += f"  buildup {r.get('buildup', 0.0):7.1f}"
                print(f"    {r['skill_label']:20s} {r['hit_name']:35s} [{elem:8s}]"
                      f"{r['damage_pct']:7.1f}%  ->  non-crit {r['non_crit']:8.1f}  "
                      f"crit {r['crit']:8.1f}  exp {r.get('expected', r['non_crit']):8.1f}"
                      f"{extras}")


if __name__ == "__main__":
    main()

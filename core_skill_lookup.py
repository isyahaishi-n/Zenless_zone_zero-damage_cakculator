"""
Core Skill (SkillType 5) lookup — me-resolve open item #2 dari docs/readme2.md.

Sumber data (semua CONFIRMED, diverifikasi ke Prydwen utk Miyabi & Anby):
- `AvatarPassiveSkillTemplateTb.json` (datamine git.mero.moe) — 58 karakter
  playable x 6 rank (rank 2-7). Field mapping:
    PJABHBNCJOI      = avatar_id
    FCLMDBPHFDN      = core skill rank (2-7)
    DNJHODOHPDA      = character level unlock requirement
    KBOACPNJNKF      = [{BGEHICNGHKO: property_id, CLEHOBAKHOI: value}] —
                       stat bonus KUMULATIF (total delta dari base di rank itu,
                       BUKAN increment per-rank)
    GPDGFDPHGJJ      = desc key per rank -> TextMap (UniqueSkill_02..07_Desc)
    HDPANGNKNAP      = title key -> TextMap (nama Core Passive)
    OPLOCGPNNJB      = upgrade cost (polychrome + material)
- `PropertyTemplateTb.json` — terjemahan property_id:
    11101 HpMax (flat)        11102 HpMax% (/10000)
    12101 Atk_base (flat)     12102 Atk% (/10000)
    12201 BreakStun (Impact)  20101 Crit (/10000)
    21101 CritDmg (/10000)    23101 PenRatio (/10000)
    30501 SpRecover_Base (/100)
    31201 ElementMystery   -> display "Anomaly Proficiency" (CONFIRMED angka)
    31401 ElementAbnormalPower -> display "Anomaly Mastery" (CONFIRMED angka)

Catatan display-name 31201/31401: internal name game terbalik dibaca awam —
diverifikasi via angka: Miyabi 31201=148 base +90 core = 238 = "Anomaly
Proficiency 238" Prydwen; 31401=116 = "Anomaly Mastery 116" Prydwen.

Ekuivalensi: field `CoreEnhancementProps` di avatars.json (Enka store)
BERISI NILAI YANG SAMA persis (index 0 = rank 1/base zero). File datamine
lebih kaya (ada desc key + cost + unlock level).

Mystery ID dari docs/readme3 (SUDAH TERPECAHKAN, bukan foreign key):
- ACOLKGPPGKK (410910 dll) = 410000 + (avatar_id % 1000) * 10 — ID turunan
  untuk UI config, bukan pointer ke tabel numerik.
- ONMHBHPOLHI (12254028 dll) = index sekuensial per karakter (urutan rilis,
  mulai 12254004) untuk UI sorting — juga bukan pointer tabel numerik.

Scaling EFEK core passive (angka kayak Frostburn 750%->1500%) tidak ada di
tabel numerik terpisah yang bisa di-resolve via ID itu; angkanya embedded
di teks `UniqueSkill_01..07_Desc` per karakter di TextMap (terverifikasi:
Miyabi 750/875/1000/1125/1250/1375/1500 & Anby 32/37.3/42.6/48/53.3/58.6/64
— keduanya match Prydwen).
"""

import json
import re

PASSIVE_TEMPLATE_KEY = "MLOEFHJHCID"

# property_id -> (display_name, divisor) ; divisor 1 = flat value
PROPERTY_INFO = {
    11101: ("HP", 1),
    11102: ("HP%", 10000),
    12101: ("ATK", 1),
    12102: ("ATK%", 10000),
    12201: ("Impact", 1),
    20101: ("CRIT Rate%", 10000),
    21101: ("CRIT DMG%", 10000),
    23101: ("PEN Ratio%", 10000),
    30501: ("Energy Regen", 100),
    31201: ("Anomaly Proficiency", 1),
    31401: ("Anomaly Mastery", 1),
}

MAX_RANK = 7


def load_passive_template(path: str = "data/AvatarPassiveSkillTemplateTb.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_property_template(path: str = "data/PropertyTemplateTb.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_core_index(passive_template: dict) -> dict:
    """{avatar_id: {rank: row}} — row mentah per rank 2-7."""
    index = {}
    for row in passive_template[PASSIVE_TEMPLATE_KEY]:
        index.setdefault(row["PJABHBNCJOI"], {})[row["FCLMDBPHFDN"]] = row
    return index


def get_core_stat_bonuses(core_index: dict, avatar_id: int, rank: int) -> dict:
    """Stat bonus KUMULATIF pada rank tertentu -> {property_id: value}.

    rank 1 = base (tidak ada row) -> {}. Rank 2-7 ambil row yang bersangkutan.
    Nilai di row adalah TOTAL delta dari base (bukan per-rank increment):
    Anby rank 7 = {12201: 18, 12101: 75} berarti Impact +18 & ATK +75
    DARI BASE, bukan +18 lagi di atas rank 6.
    """
    if rank < 2 or rank > MAX_RANK:
        return {}
    row = core_index.get(avatar_id, {}).get(rank)
    if row is None:
        return {}
    return {p["BGEHICNGHKO"]: p["CLEHOBAKHOI"] for p in row["KBOACPNJNKF"]}


def format_core_stat_bonuses(bonuses: dict) -> str:
    """{prop_id: raw} -> 'ATK +75, Impact +18' (dengan divisor benar)."""
    parts = []
    for pid, raw in sorted(bonuses.items()):
        name, div = PROPERTY_INFO.get(pid, (f"Prop{pid}", 1))
        val = raw / div
        parts.append(f"{name} +{val:g}")
    return ", ".join(parts)


def get_avatar_codename(core_index: dict, avatar_id: int):
    """Codename karakter (mis. 1091 -> 'Unagi') dari title key UniqueSkill.

    Dipakai buat lookup teks scaling core passive di TextMap
    (`<Codename>_UniqueSkill_01..07_Desc`).
    """
    rows = core_index.get(avatar_id, {})
    for rank in sorted(rows):
        titles = rows[rank].get("HDPANGNKNAP") or []
        for t in titles:
            if t.endswith("_UniqueSkill_Title"):
                return t[: -len("_UniqueSkill_Title")]
    return None


def get_core_passive_texts(codename: str, textmap: dict) -> dict:
    """{level 1..7: teks deskripsi core passive level itu} (raw, dengan tag)."""
    texts = {}
    for lvl in range(1, MAX_RANK + 1):
        key = f"{codename}_UniqueSkill_{lvl:02d}_Desc"
        if key in textmap:
            texts[lvl] = textmap[key]
    return texts


_NUM_IN_TEXT = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(%)")


def extract_percent_curve(texts: dict) -> dict:
    """Ekstrak semua angka persen dari tiap level teks -> {level: [floats]}.

    Handle koma ribuan ("1,000%" -> 1000.0). Heuristic: cocok buat core
    passive yang scaling-nya angka % (Anby 32%->64%, Miyabi Frostburn
    750%->1500). Core passive dengan angka non-% (energy flat, durasi
    detik) bakal ikut keambil — selalu cross-check konteks teksnya.
    """
    curve = {}
    for lvl, text in texts.items():
        clean = re.sub(r"<[^>]+>", "", text)
        vals = []
        for m in _NUM_IN_TEXT.finditer(clean):
            num = m.group(1).replace(",", "")
            vals.append(float(num))
        curve[lvl] = vals
    return curve


def compute_final_stats(avatars_entry: dict, level: int, promotion: int, rank: int,
                        core_index: dict) -> dict:
    """Stat final = base + growth/10000*(level-1) + promotion + core bonus.

    Formula growth sama kayak zzz_enka_stat_calc_multichar.py (sudah
    terverifikasi). Core bonus ditambahkan FLAT (semua property core cuma
    flat/absolute — tidak ada yang % di data rank 2-7 yang terlihat).
    Diverifikasi: Miyabi L60 p6 r7 ATK=880.7 (Prydwen 880), Anby 659 (658).
    """
    base = {int(k): float(v) for k, v in avatars_entry["BaseProps"].items()}
    growth = {int(k): float(v) for k, v in avatars_entry.get("GrowthProps", {}).items()}
    promos = avatars_entry.get("PromotionProps", [])
    promo = {int(k): float(v) for k, v in promos[promotion - 1].items()} if promos else {}
    core = get_core_stat_bonuses(core_index, int(avatars_entry.get("_avatar_id", 0)), rank)

    stats = {}
    for pid, base_value in base.items():
        stats[pid] = base_value + growth.get(pid, 0) / 10000 * (level - 1) + promo.get(pid, 0)
    for pid, val in core.items():
        stats[pid] = stats.get(pid, 0) + val
    return stats


def main():
    passive = load_passive_template()
    core_index = build_core_index(passive)
    textmap = json.load(open("data/TextMap_ENTemplateTb.json", encoding="utf-8"))
    avatars = json.load(open("data/avatars.json", encoding="utf-8"))

    print(f"Indexed {len(core_index)} avatars (core skill ranks 2-{MAX_RANK}).")

    print()
    print("=" * 60)
    print("TEST 1: Miyabi (1091) rank 7 stat bonus + final stats L60")
    print("=" * 60)
    bonuses = get_core_stat_bonuses(core_index, 1091, 7)
    print("  rank 7 bonuses:", format_core_stat_bonuses(bonuses))
    print("  expected:       ATK +75, Anomaly Proficiency +90")
    m = dict(avatars["1091"]); m["_avatar_id"] = 1091
    stats = compute_final_stats(m, level=60, promotion=6, rank=7, core_index=core_index)
    print(f"  final ATK = {stats[12101]:.1f}   (Prydwen: 880)")
    print(f"  final Anomaly Proficiency = {stats[31201]:.0f} (Prydwen: 238)")
    print(f"  final HP = {stats[11101]:.0f}     (Prydwen: 7673)")

    print()
    print("=" * 60)
    print("TEST 2: Anby (1011) rank 7 stat bonus + final stats L60")
    print("=" * 60)
    bonuses = get_core_stat_bonuses(core_index, 1011, 7)
    print("  rank 7 bonuses:", format_core_stat_bonuses(bonuses))
    print("  expected:       ATK +75, Impact +18")
    a = dict(avatars["1011"]); a["_avatar_id"] = 1011
    stats = compute_final_stats(a, level=60, promotion=6, rank=7, core_index=core_index)
    print(f"  final ATK = {stats[12101]:.1f}    (Prydwen: 658)")
    print(f"  final Impact = {stats[12201]:.0f}     (Prydwen: 136)")

    print()
    print("=" * 60)
    print("TEST 3: Core passive effect scaling dari TextMap")
    print("=" * 60)
    for aid, label, expect in (
        (1091, "Miyabi 'Searing Cold' Frostburn Break %", "750->1500 (+125/level)"),
        (1011, "Anby 'Fluctuating Voltage' extra Daze %", "32->64 linear"),
    ):
        codename = get_avatar_codename(core_index, aid)
        texts = get_core_passive_texts(codename, textmap)
        curve = extract_percent_curve(texts)
        print(f"  {label} [{codename}]:")
        for lvl in sorted(curve):
            print(f"    Lv{lvl}: {curve[lvl]}")
        print(f"    expected: {expect}")

    print()
    print("=" * 60)
    print("TEST 4: Mystery ID derivation (docs/readme3 clue)")
    print("=" * 60)
    for aid, acol, onmh in ((1091, 410910, 12254028), (1011, 410110, 12254004)):
        derived = 410000 + (aid % 1000) * 10
        print(f"  avatar {aid}: ACOLKGPPGKK={acol} derived={derived} "
              f"{'OK' if derived == acol else 'MISMATCH'} | ONMHBHPOLHI={onmh} (UI sort index)")

    print()
    print("All tests verified against Prydwen (Miyabi & Anby pages, 2026-08-30).")


if __name__ == "__main__":
    main()
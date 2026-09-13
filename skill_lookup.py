"""
Skill multiplier lookup — Tahap 1, 2 & 4 dari plan wiring damage calculator.

Tahap 1: Index semua baris AvatarSkillTemplateTb.json per (avatar_id, skill_type).
Tahap 2: Given (avatar_id, skill_type, level), hitung Damage%/Daze% tiap hit
          di bawah skill_type itu, pake formula yang udah diverifikasi:
              Damage(level) = IKAABAIDFAO + (level-1) * DGHHKAHHIPM
              Daze(level)   = OMFJHOLBIKA + (level-1) * KICLLNBEAEN
Tahap 4: Nama skill bahasa Inggris via dua mekanisme:
          a) EXPLICIT (utama, baru): parse field KLPLBBJABBL di baris
             PDJMFJOFNEF==1 AvatarSkillDesTemplateTb.json -- berisi referensi
             eksplisit "{Skill:<hit_id>, Prop:1001/1002}" yang menautkan hit
             row ke section title. Coverage 91.4% hit playable. Ini resolve
             7 karakter anomali grouping (1031, 1041, ..., 1551).
          b) HEURISTIC (fallback): grouping sekuensial N-hit-per-nama.

SkillType (GLENCFMNKMF) per README hasil decode:
    0 = Basic Attack
    1 = Special Attack (EX)
    2 = Dodge
    3 = Chain Attack + Ultimate (dua hit row terpisah, satu level number)
    5 = Core Skill
    6 = Assist
"""

import json
import re
from collections import defaultdict

SKILL_TYPE_NAMES = {
    0: "Basic Attack",
    1: "Special Attack",
    2: "Dodge",
    3: "Chain Attack / Ultimate",
    5: "Core Skill",
    6: "Assist",
}


def load_skill_template(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_skill_index(skill_template: dict) -> dict:
    """Tahap 1: {avatar_id: {skill_type: [row, row, ...]}}

    avatar_id diambil dari 4 digit pertama DALBKGGEJEF (skill ID), yang
    sudah dikonfirmasi cocok sama Avatar ID di avatars.json (contoh: 1011xxx -> Anby).
    """
    index = defaultdict(lambda: defaultdict(list))
    rows = skill_template["MLOEFHJHCID"]

    for row in rows:
        skill_id = row["DALBKGGEJEF"]
        avatar_id = int(str(skill_id)[:4])
        skill_type = row["GLENCFMNKMF"]
        index[avatar_id][skill_type].append(row)

    return index


def compute_damage(row: dict, level: int) -> float:
    """Damage(level) = IKAABAIDFAO + (level-1)*DGHHKAHHIPM, in percent."""
    base = row["IKAABAIDFAO"]
    growth = row["DGHHKAHHIPM"]
    return (base + (level - 1) * growth) / 100


def compute_daze(row: dict, level: int) -> float:
    """Daze(level) = OMFJHOLBIKA + (level-1)*KICLLNBEAEN, in percent."""
    base = row["OMFJHOLBIKA"]
    growth = row["KICLLNBEAEN"]
    return (base + (level - 1) * growth) / 100


# Elemen damage per sub-skill dari SkillListConfigTemplateTb (OGIJGDFBEAD).
# 0 = tanpa damage (daze-only, mis. Defensive Assist parry).
SKILL_LIST_ELEMENT_FIELD = "OGIJGDFBEAD"
SKILL_LIST_ELEMENT_NAMES = {
    200: "Physical", 201: "Fire", 202: "Ice", 203: "Electric",
    204: "Wind", 205: "Ether", 300: "Lumen", 0: None,
}


def build_skill_element_map(skill_list_rows: list, textmap: dict = None) -> dict:
    """Dua map elemen per sub-skill, dinilai dari judul row UI
    SkillListConfigTemplateTb (judul = nama sub-skill persis seperti nama
    hit dari AvatarSkillDesTemplateTb):

    return (exact, base):
      exact["Basic Attack: Kazahana (1st and 2nd hit)"] = "Physical"
      base ["Basic Attack: Kazahana"] = elemen hit PERTAMA yang disebut
        annotation ("1st and 2nd hit" -> hit-1) — dipakai ketika nama hit
        tidak memuat annotation (data AvatarSkillDes memang polos).

    Diverifikasi GT docs/wengine.md: Kazahana hit-1 Miyabi = Physical
    (row UI 1091001 elem 200); hit 3+ = Ice (row 1091002 elem 202).

    Kalau textmap None, map kosong (caller fallback ke elemen karakter).
    """
    if textmap is None:
        return {}, {}
    exact, base = {}, {}
    for r in skill_list_rows:
        elem = SKILL_LIST_ELEMENT_NAMES.get(r.get(SKILL_LIST_ELEMENT_FIELD))
        if elem is None:
            continue
        title = resolve_title(r.get("CLHJEHADMKO") or "", textmap).strip()
        if not title:
            continue
        exact[title] = elem
        stripped, first, last = _strip_hit_annotation(title)
        if stripped:
            key = (stripped, first, last)
            # simpan rentang per nama dasar; multiple row = multiple rentang
            base.setdefault(stripped, []).append((first, last, elem))
    return exact, base


_NUM_WORDS = {
    "1st": 0, "2nd": 1, "3rd": 2, "4th": 3, "5th": 4, "6th": 5,
    "7th": 6, "8th": 7, "9th": 8,
}


def _strip_hit_annotation(title: str):
    """Parse anotasi hit di judul UI -> (base, first_idx0, last_idx0).
    'Basic Attack: Kazahana (1st and 2nd hit)' -> ('Basic Attack: Kazahana', 0, 1)
    'Basic Attack: Shimotsuki' -> ('Basic Attack: Shimotsuki', None, None)
    """
    m = re.match(r"^(.*?)\s*\(([^)]*?)\s*hit(?:s)?\)\s*$", title, re.IGNORECASE)
    if not m:
        return title.strip(), None, None
    base = m.group(1).strip()
    nums = re.findall(r"(\d+)(?:st|nd|rd|th)?", m.group(2), re.IGNORECASE)
    if not nums:
        return base, None, None
    idx = [_NUM_WORDS.get(f"{n}{'st' if n == '1' else 'nd' if n == '2' else 'rd' if n == '3' else 'th'}",
                          int(n) - 1) for n in nums]
    return base, idx[0], idx[-1]


# Normalisasi nama elemen internal game (ElementTypes avatars.json /
# SkillListConfig) ke nama kanonik yang dipakai stat panel ("Ice DMG"),
# monster RES (monster_data.ELEMENTS), dan scope toggle mapped files.
CANONICAL_ELEMENTS = ("Physical", "Fire", "Ice", "Electric", "Ether", "Wind", "Lumen")
ELEMENT_ALIASES = {
    "Elec": "Electric",
    "Electric": "Electric",
    "Physics": "Physical",
    "Physical": "Physical",
    "Fire": "Fire",
    "Ice": "Ice",
    "Ether": "Ether",
    "Wind": "Wind",
    "Lumen": "Lumen",
    # Elemen komposit: karakter memakai varian yang dianggap sebagai elemen dasar
    # (Miyabi "FireFrost" -> Ice, Yixuan "AuricEther" -> Ether).
    "FireFrost": "Ice",
    "AuricEther": "Ether",
}


def normalize_element(raw: str) -> str:
    """'Elec' -> 'Electric', 'Physics' -> 'Physical', 'FireFrost' -> 'Ice',
    dst. Input tidak dikenal dikembalikan apa adanya (caller bertanggung
    jawab memberi fallback, mis. 'Physical')."""
    if not raw:
        return "Physical"
    return ELEMENT_ALIASES.get(raw, raw)


# Klasifikasi granular per-hit dari prefix nama hit (nama explicit dari
# AvatarSkillDes). SkillType gabungan (Dodge = Dash + Counter, Assist =
# Quick/Defensive/Follow-Up) dipecah supaya scope toggle mapped files
# ('Dash Attack', 'Dodge Counter', 'Quick Assist', ...) bisa match per hit.
HIT_NAME_PREFIX_TO_SKILL_TYPE = (
    ("Dash Attack", "Dash Attack"),
    ("Dodge Counter", "Dodge Counter"),
    ("Quick Assist", "Quick Assist"),
    ("Defensive Assist", "Defensive Assist"),
    ("Assist Follow-Up", "Assist Follow-Up"),
    ("Chain Attack", "Chain Attack"),
    ("Ultimate", "Ultimate"),
    ("EX Special Attack", "EX Special Attack"),
    ("Special Attack", "Special Attack"),
    ("Basic Attack", "Basic Attack"),
)


def skill_type_of_hit(hit_name: str, fallback: str) -> str:
    """Label skill-type granular untuk satu hit, dari prefix nama hit.
    Fallback = label skill-type gabungan (mis. 'Dodge'). Nama hit None
    (hidden) atau tanpa prefix dikenal -> fallback."""
    if not hit_name:
        return fallback
    for prefix, label in HIT_NAME_PREFIX_TO_SKILL_TYPE:
        if hit_name.startswith(prefix):
            return label
    return fallback


def element_of_hit(hit_name: str, hit_element_map: tuple, hit_seq_index: int,
                   fallback: str) -> str:
    """Elemen satu hit dari (exact, ranges) hasil build_skill_element_map.

    `hit_seq_index` = index hit (0-based) dalam sekuens hit bernama sama
    (nama 'Basic Attack: Kazahana' dipakai beberapa hit berurutan; UI
    menyebut rentang '1st and 2nd hit' = Physical, '3rd, 4th, and 5th
    hit' = Ice -- GT docs/wengine.md: D1 1086 & D2 1183 Physical).

    Urutan resolusi: judul exact > rentang yang memuat index > fallback
    (elemen karakter). Konservatif: hit di luar rentang yang diketahui
    tidak dikarang elemennya.
    """
    if not hit_name or not hit_element_map:
        return fallback
    exact, ranges = hit_element_map
    if hit_name in exact:
        return exact[hit_name]
    base = hit_name
    seq_idx = hit_seq_index
    m = re.match(r"^(.*?)\s*\(hit (\d+)/(\d+)\)$", hit_name)
    if m:
        base = m.group(1)
        seq_idx = int(m.group(2)) - 1
    for first, last, elem in ranges.get(base, ()):
        if first is None:
            return elem
        if first <= seq_idx <= last:
            return elem
    return fallback


def get_skill_multipliers(index: dict, avatar_id: int, skill_type: int, level: int) -> list:
    """Returns a list of {hit_id, damage_pct, daze_pct} for every hit row
    under this avatar's skill_type, at the given level.

    Baris dengan IKAABAIDFAO=0 DAN OMFJHOLBIKA=0 di-skip -- itu slot
    placeholder/nggak kepake (dikonfirmasi lewat Miyabi SkillType 3:
    2 dari 6 baris kosong total di semua field, bukan hit sungguhan).
    """
    rows = index.get(avatar_id, {}).get(skill_type, [])
    results = []
    for row in rows:
        if row["IKAABAIDFAO"] == 0 and row["OMFJHOLBIKA"] == 0:
            continue
        results.append({
            "hit_id": row["DALBKGGEJEF"],
            "damage_pct": compute_damage(row, level),
            "daze_pct": compute_daze(row, level),
        })
    return results


def load_locs(path: str, lang: str = "en") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get(lang, {})


def load_textmap(path: str = "data/TextMap_ENTemplateTb.json") -> dict:
    """Load TextMap EN (flat dict {text_key: english_text}, ~411k entries).

    Key-nya langsung string deskriptif kayak 'Anbi_Skill_Normal_Title' --
    sama persis dengan isi LECKPHICFOA/DLADMENPFPD di skill template.

    Kalau `TextMap_ENOverwriteTemplateTb.json` ada di folder yang sama,
    entri-nya di-merge di atas (overwrite menang — itu tabel supplement
    buat key yang belum ada di TextMap utama, mis.
    'Remielle_Skill_FinishEx_Title').
    """
    import os
    with open(path, "r", encoding="utf-8") as f:
        textmap = json.load(f)
    overwrite_path = os.path.join(os.path.dirname(path) or ".", "data/TextMap_ENOverwriteTemplateTb.json")
    if os.path.exists(overwrite_path):
        with open(overwrite_path, "r", encoding="utf-8") as f:
            textmap.update(json.load(f))
    return textmap


# Referensi "{Skill:<id>, Prop:<prop>}" di field KLPLBBJABBL
_SKILL_REF_PATTERN = re.compile(r"\{Skill:(\d+),\s*Prop:(\d+)\}")


def build_explicit_name_map(des_template: dict) -> dict:
    """Tahap 4 (explicit): {hit_id: [title_key, ...]} dari KLPLBBJABBL.

    Struktur AvatarSkillDesTemplateTb.json punya 2 lapis baris:
    - PDJMFJOFNEF==0: entri skill "lengkap" (LECKPHICFOA=title key,
      DLADMENPFPD=desc key) -- dipakai get_skill_names().
    - PDJMFJOFNEF==1: baris property untuk display in-game. Baris dengan
      DLADMENPFPD berakhiran '_Title' dan KLPLBBJABBL kosong = header
      section; baris berikutnya dengan KLPLBBJABBL berisi referensi
      eksplisit "{Skill:1091027, Prop:1001}" (Prop 1001=DamageRatio,
      1002=BreakStunRatio) menautkan hit_id ke section title itu.

    Hit yang TIDAK pernah direferensikan = hit tersembunyi (follow-up /
    varian enhance internal yang nggak ditampilkan di UI game) -- contoh:
    1031107-13 (Billy EX Special volley varian), 1091035 (Miyabi, 720%
    konstan). Untuk itu name=None tapi multiplier tetap valid.

    7 hit ter-map ke >1 title (varian enhance yang shared, mis.
    Astra Singing Exit/Perfect) -- disimpan semua, urutan kemunculan.
    """
    hit_titles = defaultdict(list)
    current_title = None
    for row in des_template["MLOEFHJHCID"]:
        if row.get("PDJMFJOFNEF") != 1:
            continue
        desc_key = row.get("DLADMENPFPD") or ""
        if desc_key.endswith("_Title") and not row.get("KLPLBBJABBL"):
            current_title = desc_key
            continue
        for skill_id, _prop in _SKILL_REF_PATTERN.findall(row.get("KLPLBBJABBL") or ""):
            titles = hit_titles[int(skill_id)]
            if current_title not in titles:
                titles.append(current_title)
    return dict(hit_titles)


def resolve_title(title_key: str, textmap: dict) -> str:
    """Title key -> English text; fallback ke key mentah kalau ga ketemu."""
    return textmap.get(title_key, title_key)


def get_skill_names(des_template: dict, avatar_id: int, skill_type: int) -> list:
    """Tahap 4 (partial): nama sub-skill non-kosong di bawah avatar+skill_type.
    Cuma reliable kalau jumlah nama == jumlah hit row (contoh: SkillType 3
    selalu 2 nama = Chain Attack + Ultimate). Untuk skill_type dengan hit
    row lebih banyak dari nama (misal Basic Attack 11 hit vs 2 nama), ini
    TIDAK dijamin urutannya cocok 1:1 ke hit row — masih perlu decode field
    lain (PDJMFJOFNEF/ACOLKGPPGKK/ONMHBHPOLHI) buat presisi penuh.
    """
    rows = des_template["MLOEFHJHCID"]
    names = [
        r["LECKPHICFOA"] for r in rows
        if r["PJABHBNCJOI"] == avatar_id and r["GLENCFMNKMF"] == skill_type
        and r["LECKPHICFOA"]
    ]
    return names


def compute_damage_output(index: dict, avatar_id: int, skill_type: int, level: int,
                           atk: float, des_template: dict = None, loc: dict = None,
                           name_map: dict = None, textmap: dict = None) -> list:
    """Tahap 3: gabungin multiplier ke ATK final -> raw damage per hit.
    Tahap 4: kasih nama.

    Prioritas naming:
    1. EXPLICIT name_map (dari build_explicit_name_map) + textmap --
       referensi eksplisit KLPLBBJABBL, coverage 91.4% hit playable.
       Ini juga yang resolve 7 karakter anomali grouping.
    2. HEURISTIC lama: kalau jumlah_hit % jumlah_nama == 0, grup hit
       berurutan ke tiap nama (inferensi, hanya reliable untuk kasus
       1 hit/nama).
    3. name=None -- hit tersembunyi / nggak bisa dipastikan. Angka
       multiplier tetap valid.

    Hit tanpa referensi eksplisis diberi flag is_hidden=True (follow-up
    internal yang tidak tampil di UI game).
    """
    multipliers = get_skill_multipliers(index, avatar_id, skill_type, level)

    # --- explicit naming ---
    explicit_names = {}
    if name_map is not None:
        for i, m in enumerate(multipliers):
            titles = name_map.get(m["hit_id"])
            if titles:
                if textmap is not None:
                    explicit_names[i] = " / ".join(resolve_title(t, textmap) for t in titles)
                else:
                    explicit_names[i] = " / ".join(titles)

    # --- heuristic fallback (hanya untuk hit yang belum kena explicit) ---
    heuristic_names = {}
    hits_per_name = 1
    if des_template is not None:
        candidate_names = get_skill_names(des_template, avatar_id, skill_type)
        unnamed_count = len(multipliers) - len(explicit_names)
        if candidate_names and unnamed_count > 0 and unnamed_count % len(candidate_names) == 0:
            hits_per_name = unnamed_count // len(candidate_names)
            unnamed_idx = 0
            for i, m in enumerate(multipliers):
                if i in explicit_names:
                    continue
                name_idx = unnamed_idx // hits_per_name
                hit_in_group = unnamed_idx % hits_per_name
                key = candidate_names[name_idx]
                base_name = loc.get(key, key) if loc is not None else key
                heuristic_names[i] = (
                    base_name if hits_per_name == 1
                    else f"{base_name} (hit {hit_in_group + 1}/{hits_per_name})"
                )
                unnamed_idx += 1

    results = []
    for i, m in enumerate(multipliers):
        if i in explicit_names:
            name, is_hidden = explicit_names[i], False
        elif i in heuristic_names:
            name, is_hidden = heuristic_names[i], False
        else:
            name, is_hidden = None, True
        results.append({
            "hit_id": m["hit_id"],
            "name": name,
            "is_hidden": is_hidden,
            "damage_pct": m["damage_pct"],
            "daze_pct": m["daze_pct"],
            "raw_damage": atk * m["damage_pct"] / 100,
        })
    return results


def classify_hidden_hits(skill_template: dict = None, des_template: dict = None,
                         avatars: dict = None) -> list:
    """Klasifikasi struktural semua hidden hits playable (lihat hidden_hits_report.md).

    Return list of dict: {avatar_id, hit_id, skill_type, dmg_base, dmg_growth,
    daze_base, daze_growth, category, dupe_of}.
    Kategori:
      - fixed_pct_proc    : growth=0, dmg>0  -> proc mechanic (angka konstan,
                            scaling stat non-ATK umumnya: Sheer Force/AP/boar ATK)
      - dupe_no_daze_proc : damage curve identik hit visible tapi daze 0
                            (pola "special instance ... does not cause Daze")
      - daze_only_variant : dmg=0, daze>0
      - dupe_variant      : damage curve identik hit visible (varian enhance)
      - unique_hidden     : lainnya (varian enhanced / combo extension)
    """
    if skill_template is None:
        skill_template = load_skill_template("data/AvatarSkillTemplateTb.json")
    if des_template is None:
        des_template = load_skill_template("data/AvatarSkillDesTemplateTb.json")
    if avatars is None:
        with open("data/avatars.json", "r", encoding="utf-8") as f:
            avatars = json.load(f)
    playable = set(int(k) for k in avatars.keys())

    refed = set()
    for row in des_template["MLOEFHJHCID"]:
        if row.get("PDJMFJOFNEF") != 1:
            continue
        dk = row.get("DLADMENPFPD") or ""
        if dk.endswith("_Title") and not row.get("KLPLBBJABBL"):
            continue
        refed.update(int(x[0]) for x in _SKILL_REF_PATTERN.findall(row.get("KLPLBBJABBL") or ""))

    by_char_type = defaultdict(list)
    for r in skill_template["MLOEFHJHCID"]:
        by_char_type[(int(str(r["DALBKGGEJEF"])[:4]), r["GLENCFMNKMF"])].append(r)

    out = []
    for r in skill_template["MLOEFHJHCID"]:
        hid = r["DALBKGGEJEF"]
        aid = int(str(hid)[:4])
        if aid not in playable or hid in refed:
            continue
        db, dg, dzb, dzg = (r["IKAABAIDFAO"], r["DGHHKAHHIPM"],
                            r["OMFJHOLBIKA"], r["KICLLNBEAEN"])
        if db == 0 and dzb == 0 and dg == 0 and dzg == 0:
            continue  # placeholder kosong, bukan hit
        sibs = [v for v in by_char_type[(aid, r["GLENCFMNKMF"])] if v["DALBKGGEJEF"] in refed]
        dupe = next((v for v in sibs
                     if v["IKAABAIDFAO"] == db and v["DGHHKAHHIPM"] == dg
                     and (db, dg) != (0, 0)), None)
        if db == 0 and dzb > 0:
            cat, dup = "daze_only_variant", None
        elif dupe is not None and dzb == 0:
            cat, dup = "dupe_no_daze_proc", dupe["DALBKGGEJEF"]
        elif dg == 0 and db > 0:
            cat, dup = "fixed_pct_proc", None
        elif dupe is not None:
            cat, dup = "dupe_variant", dupe["DALBKGGEJEF"]
        else:
            cat, dup = "unique_hidden", None
        out.append({
            "avatar_id": aid, "hit_id": hid, "skill_type": r["GLENCFMNKMF"],
            "dmg_base_pct": db / 100, "dmg_growth_pct": dg / 100,
            "daze_base_pct": dzb / 100, "daze_growth_pct": dzg / 100,
            "category": cat, "dupe_of": dup,
        })
    return sorted(out, key=lambda x: (x["avatar_id"], x["hit_id"]))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="skill lookup tests / hidden hit classification")
    parser.add_argument("--classify-hidden", action="store_true",
                        help="Klasifikasi struktural semua hidden hits playable")
    args = parser.parse_args()

    if args.classify_hidden:
        rows = classify_hidden_hits()
        counts = defaultdict(int)
        for r in rows:
            counts[r["category"]] += 1
        print(f"Total hidden hits: {len(rows)} di {len(set(r['avatar_id'] for r in rows))} karakter")
        for cat, n in sorted(counts.items()):
            print(f"  {cat}: {n}")
        print()
        for r in rows:
            dup = f" (dupe of visible {r['dupe_of']})" if r["dupe_of"] else ""
            print(f"  {r['avatar_id']} type {r['skill_type']}: hit {r['hit_id']} "
                  f"dmg {r['dmg_base_pct']:g}% gr {r['dmg_growth_pct']:g}% "
                  f"daze {r['daze_base_pct']:g}% -> {r['category']}{dup}")
        return

    skill_template = load_skill_template("data/AvatarSkillTemplateTb.json")
    index = build_skill_index(skill_template)
    des_template = load_skill_template("data/AvatarSkillDesTemplateTb.json")
    name_map = build_explicit_name_map(des_template)
    textmap = load_textmap()

    print(f"Indexed {len(index)} avatars, explicit name map: {len(name_map)} hit ids.")

    print()
    print("=" * 60)
    print("TEST 1: Anby (1011), SkillType 3 (Chain Attack / Ultimate), Level 12")
    print("=" * 60)
    results = compute_damage_output(index, avatar_id=1011, skill_type=3, level=12,
                                    atk=2000, name_map=name_map, textmap=textmap)
    for r in results:
        print(f"  {r['name']}: DMG {r['damage_pct']:.1f}%  |  Daze {r['daze_pct']:.1f}%")
    print("Expected (verified ke Prydwen):")
    print("  Chain Attack: DMG 1085.8%  |  Daze 216.0%")
    print("  Ultimate:     DMG 3026.2%  |  Daze 1487.7%")

    print()
    print("=" * 60)
    print("TEST 2: Miyabi (1091) charge attack (Shimotsuki), Level 1 vs 12")
    print("=" * 60)
    for lvl in (1, 12):
        results = get_skill_multipliers(index, avatar_id=1091, skill_type=0, level=lvl)
        print(f"  Level {lvl}:")
        for r in results:
            titles = name_map.get(r["hit_id"])
            name = resolve_title(titles[0], textmap) if titles else "(hidden)"
            print(f"    {r['hit_id']}  {name:45s} DMG {r['damage_pct']:7.1f}%  Daze {r['daze_pct']:7.1f}%")
    print("Expected (verified ke wiki):")
    print("  1091027 Charge Lv.1: LV1 454.7%  / LV12 910.1%")
    print("  1091028 Charge Lv.2: LV1 858.1%  / LV12 1717.2%")
    print("  1091029 Charge Lv.3: LV1 2141.1% / LV12 4282.8%")

    print()
    print("=" * 60)
    print("TEST 3: Anomali grouping 1551 (7 hit / 2 nama basic attack), Lv 12")
    print("=" * 60)
    results = compute_damage_output(index, avatar_id=1551, skill_type=0, level=12,
                                    atk=2000, name_map=name_map, textmap=textmap)
    for r in results:
        hidden = " [HIDDEN]" if r["is_hidden"] else ""
        print(f"  {r['hit_id']}  {str(r['name']):50s} DMG {r['damage_pct']:7.1f}%{hidden}")
    print("  -> anomali lama (7 % 2 != 0) sekarang ter-resolve explicit:")

    print()
    print("=" * 60)
    print("TEST 4: Hidden hits Billy (1031) EX Special, Lv 12")
    print("=" * 60)
    results = compute_damage_output(index, avatar_id=1031, skill_type=1, level=12,
                                    atk=2000, name_map=name_map, textmap=textmap)
    for r in results:
        hidden = " [HIDDEN]" if r["is_hidden"] else ""
        print(f"  {r['hit_id']}  {str(r['name']):50s} DMG {r['damage_pct']:7.1f}%{hidden}")


if __name__ == "__main__":
    main()

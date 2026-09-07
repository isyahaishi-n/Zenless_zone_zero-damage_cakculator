"""
W-Engine passive generator — regenerasi `wengine_passive_mapped.json` dari
teks mentah, BUKAN hardcode/trust file lama.

Latar (bug 2026-08-31): file lama punya efek fabricated — contoh Fusion
Compiler (14118) dikasih efek "crit_rate 10%" yang dicopy dari weapon lain,
padahal teks aslinya cuma 2 efek (ATK +12..24% & AP +25..50). Key teks
(title/desc key) file lama reliable; effects tidak.

Metodologi (anti-fabrication):
1. Sumber angka SATU-SATUNYA: teks `Weapon_TalentDes_<id>0X` per phase
   (1-5) dari `WeaponTalentTemplateTb.json` (desc key = POLEJGCKKFI),
   di-resolve via TextMap EN + merge ENOverwrite.
2. Kalimat di-align antar phase pakai skeleton (angka -> '#'); skeleton
   identik di 5 phase memvalidasi struktur, lalu slot angka per kalimat
   jadi curve `values_p1_to_p5`.
3. Klasifikasi efek via pattern regex atas kalimat (stat up, DMG bonus,
   Daze, ignore DEF/RES, energy, dsb). Kalimat ber-angka yang tidak cocok
   pattern efek DAN tidak habis di-strip sebagai mekanik (durasi/stack/
   cooldown/threshold) -> effect_type "unparsed" + needs_review.
4. Setiap effect membawa `evidence_p1` (kalimat phase-1 persis) — audit
   bisa crosscheck angka ke teks kapan pun. Invariant: semua nilai curve
   HARUS muncul sebagai angka di teks phase terkait (dicek di audit()).

Field mapping WeaponTalentTemplateTb (dari file lokal, 475 rows):
    COEEBFOBGND = weapon id   (match key weapons.json)
    APAEMLCPFID = talent level/phase 1-5 (S1-S5)
    CLCDDKNHEMN = title key   (Weapon_TalentTitle_<id>)
    POLEJGCKKFI = desc key    (Weapon_TalentDes_<8id0X>)
    NFKHOOCEDEH = list param text id
    CBFOFEECIGH = boolean flags
(Catatan: wengine.md menukar judul/desc — kebenaran dari isi file:
CLCDDKNHEMN berisi ...Title..., POLEJGCKKFI berisi ...Des... .)
"""

import json
import re
import sys
from pathlib import Path

# Path relatif ke root repo (script ini jalan dari scripts/, data di ../data/)
_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_FILE = str(_ROOT / "data" / "WeaponTalentTemplateTb.json")
TEXTMAP_FILE = str(_ROOT / "data" / "TextMap_ENTemplateTb.json")
OVERWRITE_FILE = str(_ROOT / "data" / "TextMap_ENOverwriteTemplateTb.json")
WEAPONS_FILE = str(_ROOT / "data" / "weapons.json")
OUT_FILE = str(_ROOT / "data" / "mapped" / "wengine_passive_mapped.json")

ROWS_KEY = "MLOEFHJHCID"

NUM = r"\d+(?:\.\d+)?"
SEC = r"(?:s|sec|secs|second|seconds)\b"

# ---------------------------------------------------------------- text utils

_TAG_RE = re.compile(r"<[^>]+>")


def clean_text(t: str) -> str:
    t = _TAG_RE.sub("", t)
    t = t.replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", t).strip()


def skeleton(s: str) -> str:
    """Angka -> '#', dipakai buat align kalimat antar phase."""
    return re.sub(NUM, "#", s)


_SENT_SPLIT_RE = re.compile(r"(?<=[.;])\s+(?=[A-Z\[])")
_NUM_TOKEN_RE = re.compile(NUM)


def split_sentences(text: str):
    parts = _SENT_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def num_tokens(text: str):
    return _NUM_TOKEN_RE.findall(text)


def load_textmap():
    tm = json.load(open(TEXTMAP_FILE, encoding="utf-8"))
    ov = json.load(open(OVERWRITE_FILE, encoding="utf-8"))
    tm.update(ov)
    return tm


# ------------------------------------------------------- mechanics detection

_DURATION_RES = [
    re.compile(r"(?:for|lasting|lasts?|last)\s+(" + NUM + r")\s*" + SEC),
    re.compile(r"(" + NUM + r")\s*more\s+seconds"),
]
_STACKS_RES = [
    re.compile(r"up\s+to\s+(\d+)\s+times"),
    re.compile(r"stacks?\s+up\s+to\s+(\d+)\s+times"),
    re.compile(r"up\s+to\s+a\s+maximum\s+of\s+(\d+)\s+stacks"),
]
_COOLDOWN_RES = [
    re.compile(r"once\s+every\s+(" + NUM + r")\s*" + SEC),
    re.compile(r"trigger\s+once\s+every\s+(" + NUM + r")\s*" + SEC),
    re.compile(r"once\s+per\s+(" + NUM + r")\s*" + SEC),
]


def mech_duration(s):
    for rx in _DURATION_RES:
        m = rx.search(s)
        if m:
            return float(m.group(1))
    return None


def mech_stacks(s):
    best = None
    for rx in _STACKS_RES:
        m = rx.search(s)
        if m:
            v = int(m.group(1))
            best = v if best is None else max(best, v)
    return best


def mech_cooldown(s):
    for rx in _COOLDOWN_RES:
        m = rx.search(s)
        if m:
            return float(m.group(1))
    return None


# Frasa mekanik ber-angka yang TIDAK adalah nilai efek — di-strip sebelum
# memutuskan sebuah kalimat "unparsed". Semua frasa harus mengkonsumsi
# angka di dalamnya.
_MECH_STRIP_RES = [
    re.compile(r"(?:once\s+)?every\s+" + NUM + r"\s*" + SEC),          # cooldown / tick
    re.compile(r"every\s+" + NUM + r"\s+Energy"),                       # per-N-energy threshold
    re.compile(r"(?:for|lasting|lasts?|last)\s+" + NUM + r"\s*" + SEC),# duration
    re.compile(NUM + r"\s*more\s+seconds"),
    re.compile(r"gain\s+" + NUM + r"\s*s\b"),                           # gain 10s of buff
    re.compile(NUM + r"\s*s\s+of\s+(?:a\s+|this\s+)?buff"),             # 3s of a buff
    re.compile(r"maximum\s+of\s+" + NUM + r"\s*" + SEC),                # up to max 30s
    re.compile(r"up\s+to\s+(?:a\s+maximum\s+of\s+)?\d+\s+(?:times|stacks)"),
    re.compile(r"stacks?\s+up\s+to\s+\d+"),
    re.compile(r"up\s+to\s+\d+\s+stacks"),
    re.compile(r"gains?\s+\d+\s+(?:[A-Za-z-]+\s+)?stacks?\b(?:\s+of\s+(?:a\s+|the\s+)?[A-Za-z-]+)*"),
    re.compile(r"grants?\s+(?:the\s+equipper\s+)?\d+\s+(?:[A-Za-z-]+\s+)?stacks?\b(?:\s+of\s+(?:a\s+|the\s+)?[A-Za-z-]+)*"),
    re.compile(r"provid\w+\s+(?:at\s+most\s+|up\s+to\s+)?\d+\s+stacks?"),
    re.compile(r"(?:With|At)\s+(?:all\s+)?\d+\s+stacks"),
    re.compile(r"(?:greater|no\s+lower|higher)\s+than(?:\s+or\s+equal\s+to)?\s+" + NUM),
    re.compile(r"no\s+lower\s+than\s+" + NUM),
    re.compile(r"at\s+least\s+" + NUM + r"\s+Energy"),
    re.compile(r"\d+\s+or\s+more\s+Energy"),
    re.compile(r"one\s+of\s+three"),
    re.compile(r"below\s+" + NUM + r"%"),
    re.compile(r"falls\s+to\s+" + NUM + r"%"),
]


def strip_mechanics(sentence: str, extra_res=()) -> str:
    """Hilangkan semua frasa mekanik ber-angka (iteratif sampai stabil).

    extra_res: regex tambahan (mis. pattern mekanik mindscape) yang juga
    di-strip — dipakai modul mindscape_passive_gen.
    """
    s = sentence
    res = list(_MECH_STRIP_RES) + list(extra_res)
    while True:
        s2 = s
        for rx in res:
            s2 = rx.sub(" ", s2)
        s2 = re.sub(r"\s+", " ", s2).strip()
        if s2 == s:
            return s2
        s = s2


# ---------------------------------------------------------- effect patterns

ELEMENTS = ["Physical", "Fire", "Ice", "Electric", "Ether", "Wind"]
SKILL_TYPES = [
    "Basic Attack", "Basic Attacks", "Dash Attack", "Dash Attacks",
    "Dodge Counter", "EX Special Attack", "EX Special Attacks",
    "Special Attack", "Special Attacks", "Chain Attack", "Chain Attacks",
    "Ultimate", "Ultimates", "Assist Attack", "Assist Attacks",
    "Assist Follow-Up", "Aftershock", "Quick Assist", "Perfect Assist",
]

# (display name, regex fragment) — urutan = prioritas match
STAT_FRAGMENTS = [
    ("Max HP", r"Max\s+HP"),
    ("CRIT DMG", r"CRIT\s+DMG"),
    ("CRIT Rate", r"CRIT\s+Rate"),
    ("Anomaly Proficiency", r"Anomaly\s+Proficiency"),
    ("Anomaly Mastery", r"Anomaly\s+Mastery"),
    ("Energy Generation Rate", r"Energy\s+Generation\s+Rate"),
    ("Energy Regen", r"Energy\s+Regen"),
    ("Anomaly Buildup Rate", r"Anomaly\s+Buildup(?:\s+Rate)?"),
    ("Sheer Force", r"Sheer\s+Force"),
    ("Impact", r"Impact"),
    ("ATK", r"ATK"),
    ("HP", r"(?<!Max\s)HP"),
    ("DEF", r"\bDEF\b"),
    ("PEN", r"\bPEN\b"),
]

_BY_OPT = r"by\s*(?:an\s+additional\s+|a\s+further\s+)?"


def stat_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def detect_scope(sentence: str):
    elem = [e for e in ELEMENTS if e in sentence]
    skills = sorted({s for s in SKILL_TYPES if s in sentence})
    return elem, skills


def make_condition(sentence: str, prev_sentence: str = None):
    """Kondisi trigger = clause pembuka subordinat, else always.

    Kalau kalimat diawali "Each stack(s) ..." dan kalimat sebelumnya punya
    trigger, warisi trigger itu (buff-nya diaktifkan trigger sebelumnya).
    """
    m = re.match(
        r"((?:At|With)\s+(?:all\s+)?\d+\s+stacks[^,]*|"
        r"(?:When|While|Upon|Whenever|After|If|Launching|Landing|Dealing|"
        r"Using|Accumulating|On entering)[^,]*),",
        sentence,
    )
    if m:
        return {"type": "toggle", "label": m.group(1).strip()}
    # trigger tanpa koma: "Launching an EX Special Attack generates ..." /
    # "Accumulating Anomaly Buildup increases ..." /
    # "EX Special Attacks inflict ..." (subjek = skill scope)
    m = re.match(
        r"^((?:(?:When|While|Upon|Whenever|After|If|Launching|Landing|"
        r"Dealing|Using|Accumulating|On entering)\b[^,.;]{3,80}?|"
        r"[A-Z][\w\s'-]{2,60}?(?:Attacks?|Counter|Ultimates?)))\s+"
        r"(?:generates?|increases?|inflicts?|deals?|gains?|applies?|"
        r"consumes?|grants?|triggers?|reduces?)\b",
        sentence,
    )
    if m:
        return {"type": "toggle", "label": m.group(1).strip()}
    if re.match(r"(?:Each|Per)\s+stack", sentence) and prev_sentence:
        prev = make_condition(prev_sentence)
        if prev["type"] == "toggle":
            return {"type": "toggle",
                    "label": prev["label"] + " (per stack)"}
    # trailing "when ..." (mis. "... by 25% when hitting from behind")
    m = re.search(r",?\s+when\s+([a-z][^,.;]{3,70})\.?$", sentence)
    if m:
        return {"type": "toggle", "label": "when " + m.group(1).strip()}
    return {"type": "always", "label": "Always"}


def _patterns():
    pats = []

    def add(name, rx, builder):
        pats.append((name, rx, builder))

    # debuff DMG musuh ("reduces the attacker's DMG by 6%")
    add("enemy_dmg_down",
        re.compile(r"reduces[^,.;]{0,60}?DMG[^,.;]{0,40}?\bby\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "enemy_dmg_down", "unit": "percent"})
    # DMG taken reduction ("Reduces DMG taken by 7.5%" / "take 7.5% less DMG")
    add("dmg_taken_down",
        re.compile(r"(?:DMG\s+taken\s+by\s*(?P<val>" + NUM + r")\s*%"
                   r"|takes?\s+(?P<val2>" + NUM + r")\s*%\s+less\s+DMG)"),
        lambda m, s: {"effect_type": "dmg_taken_down", "unit": "percent"})
    # miasma ("10% less Miasma Contamination")
    add("miasma_down",
        re.compile(r"(?P<val>" + NUM + r")\s*%\s*less\s+Miasma"),
        lambda m, s: {"effect_type": "miasma_reduction", "unit": "percent"})

    # stat up: "<stat> ... by N[%|/s]"
    for stat, frag in STAT_FRAGMENTS:
        rx = re.compile(
            frag + r"[^,.;]{0,80}?" + _BY_OPT + r"(?P<val>" + NUM + r")\s*(?P<unit>%|/s)?"
        )
        add("stat_" + stat_slug(stat), rx,
            (lambda st: (lambda m, s: {
                "effect_type": "stat", "stat": st,
                "unit": {"%": "percent", "/s": "per_second"}.get(
                    m.group("unit"), "flat"),
            }))(stat))
    # prefix-stat: "gain 30% additional CRIT DMG" / "additional 10% ATK"
    add("stat_prefix",
        re.compile(
            r"(?:(?P<val>" + NUM + r")\s*%\s*(?:additional|increased)\s+"
            r"|(?:additional|increased)\s+(?P<val2>" + NUM + r")\s*%\s*)"
            r"(?P<stat>CRIT\s+DMG|CRIT\s+Rate|Max\s+HP|Impact|ATK|DEF)\b"
        ),
        lambda m, s: {"effect_type": "stat", "stat": m.group("stat").replace(" ", " "),
                      "unit": "percent"})
    # flat/percent grant: "gain 10% ATK" / "gain 60 Anomaly Proficiency"
    add("stat_grant",
        re.compile(
            r"gains?\s+(?P<val>" + NUM + r")\s*(?P<pct>%?)\s*"
            r"(?P<stat>CRIT\s+DMG|CRIT\s+Rate|Max\s+HP|Impact|ATK|DEF"
            r"|Anomaly\s+Proficiency|Anomaly\s+Mastery|Sheer\s+Force)\b"
        ),
        lambda m, s: {"effect_type": "stat", "stat": m.group("stat"),
                      "unit": "percent" if m.group("pct") == "%" else "flat"})
    # DMG bonus
    add("dmg_up",
        re.compile(
            r"(?:\bDMG[^,.;]{0,80}?\b" + _BY_OPT + r"(?P<val>" + NUM + r")\s*%"
            r"|\bdeals?\s+(?:an\s+additional\s+)?(?P<val2>" + NUM + r")\s*%\s*"
            r"(?:more\s+|increased\s+)?DMG"
            r"|\bgains?\s+(?P<val3>" + NUM + r")\s*%\s*"
            r"(?:more\s+|increased\s+|additional\s+)+"
            r"(?:(?:Anomaly|Physical|Fire|Ice|Electric|Ether|Wind|Disorder)\s+)?"
            r"DMG(?:\s+dealt)?\b)"
        ),
        lambda m, s: {"effect_type": "damage_bonus", "unit": "percent"})
    # Daze: "10% more Daze" / "Daze ... increases by N%" (incl. "inflicted by")
    add("daze_up",
        re.compile(
            r"(?P<val>" + NUM + r")\s*%\s*more\s+Daze"
            r"|Daze[^.;%]{0,120}?\bby\s*(?:an\s+additional\s+)?"
            r"(?P<val2>" + NUM + r")\s*%"
        ),
        lambda m, s: {"effect_type": "daze_bonus", "unit": "percent"})
    # ignore DEF / RES (per elemen + generic)
    add("ignore_def",
        re.compile(r"ignor(?:e|es|ing)\s*(?P<val>" + NUM + r")\s*%\s*of[^,.;]{0,50}?\bDEF\b"),
        lambda m, s: {"effect_type": "def_ignore", "unit": "percent"})
    for elem in ELEMENTS:
        add("ignore_res_" + elem.lower(),
            re.compile(r"ignor(?:e|es|ing)\s*(?P<val>" + NUM + r")\s*%\s*of[^,.;]{0,50}?\b"
                       + elem + r"\s+RES"),
            (lambda e: (lambda m, s: {
                "effect_type": "res_ignore", "element": e, "unit": "percent",
            }))(elem))
    add("ignore_res_any",
        re.compile(r"ignor(?:e|es|ing)\s*(?P<val>" + NUM + r")\s*%\s*of[^,.;]{0,50}?\bRES"),
        lambda m, s: {"effect_type": "res_ignore", "element": None,
                      "unit": "percent"})
    # DEF shred ("target's DEF is reduced by 25%")
    add("def_shred",
        re.compile(r"DEF\s+is\s+reduced\s+by\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "def_shred", "unit": "percent"})
    # energy gain flat
    add("energy_flat",
        re.compile(r"(?:generates?|gains?)\s*(?P<val>" + NUM + r")\s*Energy"),
        lambda m, s: {"effect_type": "energy_flat", "unit": "energy"})
    # decibel slash-list ("generates 20/25.5/30/35 more Decibels")
    add("decibels",
        re.compile(r"(?P<val>\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)+)\s*more\s+Decibels"),
        lambda m, s: {"effect_type": "decibel_bonus", "unit": "decibels",
                      "multi": True})
    # additional DMG ("200% of ATK as DMG" / "600% of ... DEF as additional DMG")
    add("additional_dmg",
        re.compile(
            r"(?P<val>" + NUM + r")\s*%\s*of\s+(?:the\s+equipper's\s+)?"
            r"(?P<stat>ATK|DEF)\s+as\s+(?:additional\s+)?DMG"
        ),
        lambda m, s: {"effect_type": "additional_dmg", "scale_stat": m.group("stat"),
                      "unit": "percent"})
    # extension of previous effect ("this effect is further increased by 6%")
    add("bonus_extension",
        re.compile(
            r"(?:effect|bonus)(?:\s+is)?\s+(?:further\s+)?increased\s+by\s*"
            r"(?:an\s+additional\s+)?(?P<val>" + NUM + r")\s*%"
        ),
        lambda m, s: {"effect_type": "bonus_extension", "unit": "percent"})
    # ramp cap ("up to a maximum additional increase of 10.2%")
    add("ramp_cap",
        re.compile(r"maximum\s+additional\s+increase\s+of\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "ramp_cap", "unit": "percent"})
    # shield value up
    add("shield_up",
        re.compile(r"Shield\s+value[^,.;]{0,60}?increases\s+by\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "shield_bonus", "unit": "percent"})
    return pats


PATTERNS = _patterns()


def _match_value(m):
    for k in ("val", "val2", "val3"):
        try:
            v = m.group(k)
        except (IndexError, KeyError):
            v = None
        if v is not None:
            return v
    return None


def extract_sentence_effects(sentence: str, patterns=None):
    """Semua match pattern di satu kalimat, urut posisi, tanpa duplikat.

    patterns: list (name, rx, builder) — default PATTERNS modul ini.
    Modul mindscape_passive_gen memakai gabungan pattern-nya sendiri
    dulu (lebih spesifik) lalu pattern weapon.
    """
    if patterns is None:
        patterns = PATTERNS
    out = []
    for name, rx, builder in patterns:
        for m in rx.finditer(sentence):
            val = _match_value(m)
            if val is None:
                continue
            out.append({
                "pattern": name,
                "start": m.start(),
                "end": m.end(),
                "val_str": val,
                "extra": builder(m, sentence),
            })
    out.sort(key=lambda e: (e["start"], -(e["end"])))
    kept = []
    for e in out:
        dup = False
        for k in kept:
            span_contained = k["start"] <= e["start"] and e["end"] <= k["end"]
            same_val_overlap = (
                k["val_str"] == e["val_str"]
                and e["start"] < k["end"] and k["start"] < e["end"]
            )
            if span_contained or same_val_overlap:
                dup = True
                break
        if not dup:
            kept.append(e)
    return kept


def parse_weapon(texts_by_phase: dict):
    """texts_by_phase: {1..5: clean text} -> (effects, weapon_flags)."""
    segs = {p: split_sentences(t) for p, t in texts_by_phase.items()}
    counts = {p: len(s) for p, s in segs.items()}
    aligned = len(set(counts.values())) == 1 and all(
        skeleton(segs[p][j]) == skeleton(segs[1][j])
        for p in segs for j in range(len(segs[p]))
    )

    matches = {}  # (sent_idx, ordinal) -> {phase: match}
    for p, sentences in segs.items():
        for j, sent in enumerate(sentences):
            for ord_, m in enumerate(extract_sentence_effects(sent)):
                matches.setdefault((j, ord_), {})[p] = m

    effects = []
    for (j, ord_), by_phase in sorted(matches.items()):
        sent1 = segs[1][j]
        phases_present = sorted(by_phase)
        vals = {p: by_phase[p]["val_str"] for p in phases_present}

        # pattern yang sama di semua phase — kalau berbeda, pairing antar
        # phase patut dicurigai -> needs_review
        pattern_names = {by_phase[p]["pattern"] for p in phases_present}
        pattern_consistent = len(pattern_names) == 1

        m1 = by_phase.get(1)
        extra = dict(m1["extra"]) if m1 else {}
        multi = extra.pop("multi", False)

        curve_ok = len(phases_present) == 5
        if multi:
            values = [[float(x) for x in vals[p].split("/")]
                      if p in vals else [] for p in range(1, 6)]
        else:
            values = [float(vals[p]) if p in vals else None
                      for p in range(1, 6)]

        scales = curve_ok and len({repr(v) for v in values}) > 1

        effect = {
            "key": (stat_slug(extra["stat"]) if extra.get("stat")
                    else extra.get("effect_type", "unparsed")),
            "effect_type": extra.get("effect_type", "unparsed"),
            "condition": make_condition(sent1, segs[1][j - 1] if j > 0 else None),
            "values_p1_to_p5": values,
            "scales_with_phase": scales,
            "evidence_p1": sent1,
            "evidence_key_p1": None,  # diisi caller
        }
        for k, v in extra.items():
            if k != "effect_type":
                effect[k] = v
        elem, skills = detect_scope(sent1)
        if elem:
            effect["elements"] = elem
        if skills:
            effect["skill_types"] = skills
        for mk, mv in (
            ("duration_seconds", mech_duration(sent1)),
            ("stacks_max", mech_stacks(sent1)),
            ("cooldown_seconds", mech_cooldown(sent1)),
        ):
            if mv is not None:
                effect[mk] = mv
        if not curve_ok:
            effect["needs_review"] = True
            effect["review_reason"] = "effect match missing in some phases"
        elif not pattern_consistent:
            effect["needs_review"] = True
            effect["review_reason"] = (
                "effect matched by different patterns across phases: "
                + ", ".join(sorted(pattern_names))
            )
        effects.append(effect)

    # key unik per weapon
    seen = {}
    for e in effects:
        base = e["key"]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            e["key"] = f"{base}_{seen[base]}"

    # kalimat ber-angka yang tidak menghasilkan efek dan tidak habis sebagai
    # frasa mekanik -> unparsed (explicit, bukan dikira-kira)
    for j, sent in enumerate(segs[1]):
        has_match = any(k[0] == j for k in matches)
        if has_match:
            continue
        leftover = strip_mechanics(sent)
        if num_tokens(leftover):
            effects.append({
                "key": "unparsed",
                "effect_type": "unparsed",
                "condition": make_condition(sent),
                "values_p1_to_p5": None,
                "scales_with_phase": False,
                "evidence_p1": sent,
                "evidence_key_p1": None,
                "needs_review": True,
                "review_reason": "no effect pattern matched this numeric clause",
            })

    # skeleton alignment antar phase hanya FLAG informasi (drift teks kosmetik
    # seperti "and" vs "/" antar phase itu benar di data); jaminan keras ada
    # di per-slot: pattern konsisten + match hadir di 5 phase.
    flags = {
        "phases_aligned": aligned,
        "needs_review": any(e.get("needs_review") for e in effects),
    }
    return effects, flags


def main():
    tm = load_textmap()
    template = json.load(open(TEMPLATE_FILE, encoding="utf-8"))[ROWS_KEY]
    weapons = json.load(open(WEAPONS_FILE, encoding="utf-8"))

    rows = {}
    for r in template:
        rows.setdefault(r["COEEBFOBGND"], {})[r["APAEMLCPFID"]] = r

    out_weapons = []
    n_review = 0
    n_unparsed = 0
    for wid in sorted(rows):
        meta = weapons[str(wid)]
        name = tm.get(meta["ItemName"], f"<unresolved:{meta['ItemName']}>")

        phase_keys = []
        texts = {}
        for p in range(1, 6):
            r = rows[wid][p]
            desc_key = r["POLEJGCKKFI"]
            phase_keys.append({
                "phase": p,
                "title_key": r["CLCDDKNHEMN"],
                "description_key": desc_key,
            })
            texts[p] = clean_text(tm.get(desc_key, ""))

        effects, flags = parse_weapon(texts)
        for e in effects:
            e["evidence_key_p1"] = phase_keys[0]["description_key"]
            if e["effect_type"] == "unparsed":
                n_unparsed += 1
        if flags["needs_review"]:
            n_review += 1

        out_weapons.append({
            "id": wid,
            "name": name,
            "rarity": meta["Rarity"],
            "profession": meta["ProfessionType"],
            "passive": {
                "title": tm.get(rows[wid][1]["CLCDDKNHEMN"], ""),
                "mapped": not flags["needs_review"],
                "phases_aligned": flags["phases_aligned"],
                "needs_review": flags["needs_review"],
                "effects": effects,
                "phase_keys": phase_keys,
                "raw_texts": {str(p): texts[p] for p in range(1, 6)},
            },
        })

    doc = {
        "schema_version": 2,
        "purpose": "W-Engine passive mapping for the ZZZ damage calculator",
        "generated_by": "wengine_passive_gen.py",
        "generation_policy": (
            "ALL effect values are extracted mechanically from the raw "
            "Weapon_TalentDes_* text of the same weapon id (phases 1-5), "
            "aligned by number-normalized sentence skeletons. No values are "
            "hardcoded or copied between weapons. Every effect carries "
            "evidence_p1 (exact phase-1 sentence) + evidence_key_p1 (TextMap "
            "key); raw_texts holds all five phase texts for re-derivation. "
            "Numeric clauses that no pattern matched are kept as "
            "effect_type='unparsed' with needs_review=true."
        ),
        "local_dataset": {
            "weapon_count": len(out_weapons),
            "source_files": [TEMPLATE_FILE, TEXTMAP_FILE, OVERWRITE_FILE,
                             WEAPONS_FILE],
            "template_source_schema": {
                "template_file": TEMPLATE_FILE,
                "weapon_id_field": "COEEBFOBGND",
                "phase_field": "APAEMLCPFID",
                "title_key_field": "CLCDDKNHEMN",
                "description_key_field": "POLEJGCKKFI",
                "param_ids_field": "NFKHOOCEDEH",
                "boolean_flags_field": "CBFOFEECIGH",
                "phase_range": [1, 5],
            },
            "effect_mapped_count": sum(
                1 for w in out_weapons if w["passive"]["mapped"]),
            "needs_effect_review_count": n_review,
            "unparsed_effect_count": n_unparsed,
        },
        "weapons": out_weapons,
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_FILE}: {len(out_weapons)} weapons, "
          f"{n_review} needs_review, {n_unparsed} unparsed effects")


# ------------------------------------------------------------------- audit

def audit():
    """Invariant anti-fabrication + ground-truth checks."""
    doc = json.load(open(OUT_FILE, encoding="utf-8"))
    ok = True

    # invariant: setiap nilai curve muncul di teks phase terkait
    bad = 0
    for w in doc["weapons"]:
        raw = w["passive"]["raw_texts"]
        for e in w["passive"]["effects"]:
            vals = e.get("values_p1_to_p5")
            if not vals:
                continue
            for i, v in enumerate(vals):
                toks = num_tokens(raw[str(i + 1)])
                vv = v if isinstance(v, list) else [v]
                for x in vv:
                    if x is None:
                        continue
                    if not any(float(t) == float(x) for t in toks):
                        bad += 1
                        print(f"  FABRICATED VALUE: weapon {w['id']} "
                              f"effect {e['key']} p{i+1} value {x} "
                              f"not in text")
    if bad == 0:
        print(f"[OK] all curve values verified present in their own phase "
              f"text ({len(doc['weapons'])} weapons)")
    else:
        ok = False
        print(f"[FAIL] {bad} values not found in source text")

    # ground truth 1: Fusion Compiler — kasus kalibrasi wengine.md
    fc = next(w for w in doc["weapons"] if w["id"] == 14118)
    eff = fc["passive"]["effects"]
    atk = next(e for e in eff if e["effect_type"] == "stat"
               and e.get("stat") == "ATK")
    ap = next(e for e in eff if e["effect_type"] == "stat"
              and e.get("stat") == "Anomaly Proficiency")
    for label, passed in (
        ("no fabricated crit_rate",
         not any(e["effect_type"] == "stat" and e.get("stat") == "CRIT Rate"
                 for e in eff)),
        ("FC ATK curve",
         atk["values_p1_to_p5"] == [12.0, 15.0, 18.0, 21.0, 24.0]),
        ("FC AP curve",
         ap["values_p1_to_p5"] == [25.0, 31.0, 37.0, 43.0, 50.0]),
        ("FC AP stacks=3 duration=8s",
         ap.get("stacks_max") == 3 and ap.get("duration_seconds") == 8.0),
    ):
        print(f"  [{'OK' if passed else 'FAIL'}] 14118 {label}")
        ok &= passed

    # ground truth 2: [Lunar] Pleniluna curve
    lp = next(w for w in doc["weapons"] if w["id"] == 12001)
    e0 = lp["passive"]["effects"][0]
    passed = e0["values_p1_to_p5"] == [12.0, 14.0, 16.0, 18.0, 20.0]
    print(f"  [{'OK' if passed else 'FAIL'}] 12001 curve "
          f"{e0['values_p1_to_p5']}")
    ok &= passed

    # completeness: phase keys utuh & teks non-kosong
    for w in doc["weapons"]:
        pk = w["passive"]["phase_keys"]
        assert len(pk) == 5 and [k["phase"] for k in pk] == [1, 2, 3, 4, 5]
        for p in range(1, 6):
            assert w["passive"]["raw_texts"][str(p)], \
                f"weapon {w['id']} phase {p} text empty"
    print("  [OK] all 95 weapons: 5 phase keys + non-empty raw texts")

    print("AUDIT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    main()
    sys.exit(audit())

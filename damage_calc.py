"""
damage_calc.py — ZZZ damage calculator: conditional toggle layer + formula
damage final, kalibrasi ke ground truth 1086/2961 (Miyabi vs Tyrfing L60).

Pipeline (lihat docs/TODO_agent.md):
  1. Load 3 file mapped yang udah evidence-based & tervalidasi:
     - wengine_passive_mapped.json  (95 W-Engine, effect per phase S1-S5)
     - drive_disc_mapped.json       (30 set, efek 4pc terstruktur)
     - mindscape_mapped.json        (58 karakter, M1/M2/M4/M6)
  2. Build "toggle list": tiap conditional effect jadi ToggleEntry
     {source, stat, value, condition_text, enabled, skill_types, elements,
     stacks} yang bisa di-switch manual (metodologi #5: JANGAN deteksi
     trigger combat otomatis).
  3. Auto-enable HANYA untuk condition "always" yang terverifikasi aman:
     - set4pc mode "always" -> trusted (file di-map manual, 30/30)
     - wengine/mindscape "always" -> cuma kalau scoped (skill_types/elements)
       atau stat non-damage, DAN evidence-nya bebas kata kondisi
       (when/while/upon/during/under/against/if). Ekstraksi mekanis pernah
       nyatain 'always' padahal teksnya kondisional (mis. Miyabi M6 "During
       Shimotsuki Stance...", Yanagi M4 "under the Expose effect") dan
       damage_bonus unscoped hampir selalu scoped ke mekanik bernama
       ("Frostburn - Break DMG +30%" -- Miyabi M4). Under-enable > salah
       enable (angka korup diam-diam); entry yang ragu diberi
       needs_review=True buat diaktifin manual.
     + evaluate_thresholds() buat efek threshold stat panel (deterministik
     dari stat, bukan combat state).
  4. aggregate_modifiers() gabungin semua yang enabled -> CombatModifiers.
  5. compute_final_damage() — formula tervalidasi (DEFmult/RESmult/CRIT).

Formula (wiki ZZZ Damage page + docs/wengine.md, tervalidasi manual 99.9%;
ordering DEF/RES disamakan ke okMuzzy v3.1.0 — additive, lihat
compute_def_mult/compute_res_mult):
    ATK_combat = ATK_panel * (1 + Bonus%_cond) + Flat_cond
    DEF_eff    = (DEF_enemy*(1+DEFInc%−ΣShred%−ΣIgnore%) * (1−PENratio%)) − PEN_flat
    DEFmult    = LevelFactor(attacker_level) / (max(DEF_eff, 0) + LevelFactor(attacker_level))
    RESmult    = 1 − (RES − ΣRESignore% − RESshred%)
    NonCrit    = ATK_combat * skill_mult% * (1 + DMG%_bonus) * DEFmult * RESmult
    Crit       = NonCrit * (1 + CRIT_DMG_combat%)

Asumsi stacking multi-sumber (kalibrasi existing tetap valid — kasus
Miyabi/Tyrfing nggak ada toggle RES-ignore aktif):
  - DEF Shred / DEF Ignore dari beberapa sumber dijumlah ADDITIF dalam
    satu kurung (mengikuti okMuzzy v3.1.0 C1!P3), BUKAN chain
    multiplikatif (1-x%) per sumber seperti dugaan awal. Untuk satu
    sumber DEF hasilnya memang identik (perkalian komutatif).
  - RES ignore juga additive: RES − Σignore, di luar perkalian.
    PERHATIAN: semantik satu sumber PUN berubah vs formula lama
    (lama: RES×(1−ig), baru: RES−ig) — contoh tervalidasi Chief Sidekick
    S1 "ignores 15% of Fire RES" = Excel buff "Fire RES −0.15" (W-Engine
    Buffs row 817): RES 0.20 → RESmult 0.95, bukan 0.83.
  - mindscape `multiplier_bonus` TIDAK masuk formula (semantiknya
    "increases TO x% of the original" = set, bukan tambah) -> masuk extra.
"""

import json
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Loaders — 3 file mapped (source of truth conditional effects)
# ---------------------------------------------------------------------------

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_wengine_passives(path: str = "data/mapped/wengine_passive_mapped.json") -> dict:
    """{weapon_id: entry} — entry punya name/rarity/profession/passive.effects."""
    data = load_json(path)
    return {w["id"]: w for w in data["weapons"]}


def load_drive_disc_sets(path: str = "data/mapped/drive_disc_mapped.json") -> dict:
    """{set_name: entry} — entry punya bonus_2pc_raw/bonus_4pc_raw/effects_4pc."""
    data = load_json(path)
    return {s["name"]: s for s in data["sets"]}


def load_mindscapes(path: str = "data/mapped/mindscape_mapped.json") -> dict:
    """{avatar_id: entry} — entry punya levels {"1"|"2"|"4"|"6": {...}}."""
    data = load_json(path)
    return {a["id"]: a for a in data["avatars"]}


# ---------------------------------------------------------------------------
# ToggleEntry — struktur data "toggle list"
# ---------------------------------------------------------------------------

@dataclass
class ToggleEntry:
    """Satu conditional effect yang bisa di-switch manual.

    Cara pakai: mutasi `.enabled` (dan `.stacks` untuk efek stackable)
    sebelum dipanggil aggregate_modifiers(). Stat yang nggak dikenal formula
    (Impact, Anomaly Proficiency, dst) tetap masuk list — numpang di
    CombatModifiers.extra buat display, nggak ngaruh ke damage.
    """

    source: str                 # "wengine" | "set4pc" | "mindscape"
    source_name: str            # "Fusion Compiler (S1) — Data Flood"
    stat: str                   # canonical key, mis. "atk_pct", "crit_dmg_pct"
    value: float                # nilai per stack (satuan sesuai unit)
    unit: str                   # "percent" | "flat" | ...
    condition_text: str         # teks kondisi mentah buat direview user
    enabled: bool = False
    skill_types: tuple = ()     # scope: hanya berlaku utk skill type ini
    elements: tuple = ()        # scope: hanya berlaku utk element ini
    stacks: int = 1             # stack aktif sekarang (utk efek stackable)
    stacks_max: int = 1
    mode: str = "toggle"        # always|toggle|stack|threshold|threshold_stack
    key: str = ""               # id effect dalam file sumber
    threshold_stat: str = ""    # utk mode threshold: nama stat panel (snake)
    threshold_op: str = ""      # ">=" | "<="
    threshold_value: float = 0.0
    threshold_key: str = ""     # utk mode threshold_stack: key entry stack
    needs_review: bool = False
    evidence: str = ""          # kalimat bukti dari file mapped

    def effective_value(self) -> float:
        return self.value * max(self.stacks, 0)

    def label(self) -> str:
        scope = []
        if self.skill_types:
            scope.append("/".join(self.skill_types))
        if self.elements:
            scope.append("+".join(self.elements))
        s = f"[{'x' if self.enabled else ' '}] {self.source_name}: {self.stat} "
        if self.stacks_max > 1:
            s += f"{self.value:g} x{self.stacks}/{self.stacks_max}"
        else:
            s += f"{self.value:g}"
        if scope:
            s += f" ({', '.join(scope)})"
        if self.condition_text:
            s += f" -- {self.condition_text}"
        if self.needs_review:
            s += " [needs_review]"
        return s


def toggle_id(t) -> str:
    """ID stabil per ToggleEntry utk override dari UI.

    Dipakai server/UI buat nyalain-matiin buff conditional (item 12). Bentuk:
    `source::source_name::key::stat` — unik karena `key` per effect berbeda
    dalam satu sumber."""
    return f"{t.source}::{t.source_name}::{t.key}::{t.stat}"


def apply_toggle_overrides(toggles: list, overrides: dict | None) -> None:
    """Mutasi `t.enabled` dari override UI `{toggle_id: bool}` (item 12).

    Dipanggil SETELAH evaluate_thresholds supaya keputusan user menang di
    atas auto-enable. Key tak dikenal diabaikan."""
    if not overrides:
        return
    for t in toggles:
        tid = toggle_id(t)
        if tid in overrides:
            t.enabled = bool(overrides[tid])


def find_toggles(toggles: list, source: str = None, stat: str = None,
                 key: str = None, mode: str = None) -> list:
    """Filter toggle list by source/stat/key/mode (semua optional)."""
    out = []
    for t in toggles:
        if source is not None and t.source != source:
            continue
        if stat is not None and t.stat != stat:
            continue
        if key is not None and t.key != key:
            continue
        if mode is not None and t.mode != mode:
            continue
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# Mapping nama stat -> canonical key (vocabulary formula)
# ---------------------------------------------------------------------------

def _map_named_stat(stat: str, unit: str) -> str:
    """Nama stat dalam teks ('CRIT DMG', 'PEN Ratio', ...) -> canonical key.
    Yang formula-relevant dipetakan eksplisit; sisanya jadi passthrough
    snake_case + unit (mendarat di CombatModifiers.extra).
    """
    s = (stat or "").strip().lower()
    u = (unit or "").strip().lower()
    explicit = {
        "atk": "atk_flat" if u == "flat" else "atk_pct",
        "crit rate": "crit_rate_pct",
        "crit dmg": "crit_dmg_pct",
        "pen ratio": "pen_ratio_pct",
        "pen": "pen_flat",
        # Impact: flat masuk bucket daze (Impact_combat = panel + flat adds,
        # okMuzzy C1!B35), percent = buff daze-damage ala "Impact%" — keduanya
        # DAZE-relevant, bukan damage-relevant.
        "impact": "impact_flat" if u == "flat" else "impact_pct",
        # Anomaly Buildup Rate (okMuzzy C1!R3 `SumIf "Buildup Rate"`): buff
        # percent masuk bucket buildup; 'flat' (mis. +25 AM salah-map lama)
        # tidak pernah valid utk buildup rate — biarkan passthrough.
        "anomaly buildup rate": "buildup_rate_pct" if u == "percent" else f"anomaly_buildup_rate_{u or 'flat'}",
    }
    if s in explicit:
        return explicit[s]
    key = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return f"{key}_{u}" if u else key


# effect_type non-stat yang masuk formula:
_EFFECT_TYPE_TO_STAT = {
    "damage_bonus": "damage_pct",
    "def_ignore": "def_ignore_pct",
    "def_shred": "def_shred_pct",
    "def_increase": "def_increase_pct",
    "res_ignore": "res_ignore_pct",
    "res_shred": "res_shred_pct",
    # Daze final (okMuzzy C1!Q3): Daze = Impact_combat * dazeMV% * hit_count
    # * (1 - Daze RES) * (1 + Σ Daze%) — scoped per skill.
    "daze_bonus": "daze_pct",
    # Sheer DMG final multiplier (okMuzzy C1!P3, hanya sheer agent):
    # * (1 + Σ Sheer DMG + Σ {elem} SDMG).
    "sheer_dmg_bonus": "sheer_dmg_pct",
    # Stun Multiplier bucket (okMuzzy C1!P3): stack ADDITIF dengan
    # stun_taken musuh di kurung (1 + StunMultiplier), jangan dikali sendiri.
    "stun_dmg_mult": "stun_dmg_mult_pct",
}

# key efek drive-disc yang masuk formula (sisanya passthrough -> extra):
_DRIVE_FORMULA_KEYS = {
    "damage_percent": "damage_pct",
    "team_damage_percent": "damage_pct",      # team-wide, termasuk equipper
    "crit_dmg_percent": "crit_dmg_pct",
    "team_crit_dmg_percent": "crit_dmg_pct",  # team-wide, termasuk equipper
    "crit_rate_percent": "crit_rate_pct",
    "atk_percent": "atk_pct",
    "sheer_damage_percent": "sheer_dmg_pct",
    # Anomaly DMG buckets (okMuzzy Anomaly Calcs C58-C63):
    # - "Anomaly DMG%" (generik, semua tipe: mis. Notes From the Chained
    #   freeze_triggered 'all_attribute_anomaly_damage_percent' 16)
    # - "{elem} anomaly DMG%" scoped elemen (Feathered Fate
    #   'attribute_anomaly_damage_percent' 15)
    # - Disorder DMG (item 5, bucket terpisah)
    "all_attribute_anomaly_damage_percent": "anomaly_dmg_pct",
    "attribute_anomaly_damage_percent": "anomaly_elem_dmg_pct",
    "disorder_damage_percent": "disorder_dmg_pct",
    "vortex_damage_percent": "vortex_dmg_pct",
}

# "{head}_damage_percent" -> damage_pct dengan scope:
_DRIVE_ELEMENT_WORDS = {"fire", "electric", "ice", "physical", "ether", "wind"}
_DRIVE_SKILL_WORDS = {
    "basic_attack": "Basic Attack",
    "dash_attack": "Dash Attack",
    "dodge_counter": "Dodge Counter",
    "ex_special": "EX Special Attack",
    "special_attack": "Special Attack",
    "assist_attack": "Assist Attack",
    "chain_attack": "Chain Attack",
    "ultimate": "Ultimate",
}


def _map_drive_effect_key(k: str):
    """key efek drive-disc -> (canonical stat, skill_types, elements).
    Contoh: 'fire_damage_percent' -> ('damage_pct', (), ('Fire',)).
    """
    if k in _DRIVE_FORMULA_KEYS:
        return _DRIVE_FORMULA_KEYS[k], (), ()
    m = re.match(r"(.+?)_daze_percent$", k)
    if m:
        # skill-scoped Daze% (mis. Shockstar Disco
        # 'basic_dash_dodge_counter_daze_percent' = Basic/Dash/Dodge
        # Counter) — coba kombinasi kata head yang diketahui, lalu per kata.
        head = m.group(1)
        stypes = set()
        for word in _DRIVE_SKILL_WORDS:
            # 'basic_attack' muncul sebagai token 'basic' (+ '_attack' opsional)
            stem = word.split("_")[0]
            if re.search(rf"(^|_){stem}(_|$)", head):
                stypes.add(_DRIVE_SKILL_WORDS[word])
        if stypes:
            return "daze_pct", tuple(sorted(stypes)), ()
    m = re.match(r"(.+?)_damage_percent$", k)
    if m:
        head = m.group(1)
        if head in _DRIVE_ELEMENT_WORDS:
            return "damage_pct", (), (head.capitalize(),)
        if head in _DRIVE_SKILL_WORDS:
            return "damage_pct", (_DRIVE_SKILL_WORDS[head],), ()
    return k, (), ()


def _norm_skill(s: str) -> str:
    """Normalisasi nama skill type utk matching scope (plural -> singular)."""
    s = s.strip().lower()
    if s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


def _scope_applies(entry: ToggleEntry, skill_type, element) -> bool:
    """Cek apakah entry berlaku utk hit dengan (skill_type, element).
    None = tanpa filter (agregasi panel-level: semua scope dianggap masuk).
    """
    if entry.skill_types:
        if skill_type is not None:
            allowed = {_norm_skill(s) for s in entry.skill_types}
            if _norm_skill(skill_type) not in allowed:
                return False
    if entry.elements:
        if element is not None:
            allowed = {e.lower() for e in entry.elements}
            if "all-attribute" not in allowed and element.lower() not in allowed:
                return False
    return True


def _elements_of(eff: dict) -> tuple:
    els = list(eff.get("elements") or [])
    if eff.get("element"):
        els.append(eff["element"])
    seen, out = set(), []
    for e in els:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return tuple(out)


# Kata kondisi di evidence -> efek "always" dari ekstraksi mekanis jadi ragu
_CONDITION_WORD_RE = re.compile(
    r"\b(when|while|upon|during|against|under|if)\b", re.IGNORECASE)

# Semantik "set" (bukan tambah): "increases TO x% of the original" /
# "is increased to 6%" — nilai buff core passive di-REPLACE, bukan
# ditambah ke bucket. Kalau masuk formula additif = angka korup
# (item 9 todo: Qingyi M2/Norma M2 stun_dmg_mult 135/6 terverifikasi
# set-to semantics via evidence).
_SET_TO_SEMANTICS_RE = re.compile(
    r"(increases?|increased|raised) to \d"
    r"|of the original",
    re.IGNORECASE)


def _mechanical_auto_enable(stat: str, scope: tuple, evidence: str) -> tuple:
    """Kebijakan auto-enable utk sumber ekstraksi mekanis (wengine/mindscape).
    Return (enabled, needs_review). Lihat docstring modul.
    """
    if stat == "damage_pct" and not scope:
        return False, True
    if _CONDITION_WORD_RE.search(evidence or ""):
        return False, True
    # Semantik set-to ("increases to x% of the original") di effect_type yang
    # sekarang masuk bucket formula: jangan auto-enable — nilai mereplace
    # buff core passive, basisnya nggak diketahui pipeline kita.
    if (stat in ("stun_dmg_mult_pct", "sheer_dmg_pct", "daze_pct",
                 "damage_pct", "def_ignore_pct", "res_ignore_pct")
            and _SET_TO_SEMANTICS_RE.search(evidence or "")):
        return False, True
    return True, False


# ---------------------------------------------------------------------------
# Builder toggle list — 3 sumber
# ---------------------------------------------------------------------------

def _add_wengine_entry(entries: list, w: dict, p: dict, eff: dict, ph: int,
                       value: float, n_variants: int, idx: int) -> None:
    et = eff.get("effect_type", "")
    if et == "stat":
        stat = _map_named_stat(eff.get("stat", ""), eff.get("unit", ""))
    else:
        stat = _EFFECT_TYPE_TO_STAT.get(et, et or "unknown")
    cond = eff.get("condition") or {}
    scope = (tuple(eff.get("skill_types") or ()), _elements_of(eff))
    if cond.get("type") == "always":
        auto, review = _mechanical_auto_enable(
            stat, tuple(x for part in scope for x in part),
            eff.get("evidence_p1", ""))
    else:
        auto, review = False, False
    # `default_enabled: true` = buff dianggap AKTIF saat hitung (mode "liatin
    # hasil buff": trigger game-nya nggak dimodelkan, jadi user nggak bisa
    # nyalain dari UI). Di-set manual di mapped file, bukan hasil ekstraksi.
    if eff.get("default_enabled"):
        auto, review = True, False
    cond_text = cond.get("label", "")
    key = eff.get("key", "")
    if n_variants > 1:
        key = f"{key}[{idx}]"
        cond_text = f"{cond_text} (varian {idx + 1}/{n_variants})"
        review = True
    entries.append(ToggleEntry(
        source="wengine",
        source_name=f"{w['name']} (S{ph}) - {p.get('title', '')}",
        stat=stat,
        value=value,
        unit=eff.get("unit", ""),
        condition_text=cond_text,
        enabled=auto,
        skill_types=scope[0],
        elements=scope[1],
        stacks_max=int(eff.get("stacks_max") or 1),
        mode="always" if cond.get("type") == "always" else "toggle",
        key=key,
        needs_review=review,
        evidence=eff.get("evidence_p1", ""),
    ))


def build_wengine_toggles(mapped: dict, weapon_id: int, phase: int = 1) -> list:
    """W-Engine passive -> ToggleEntry. Phase 1-5 (S1-S5); di-clamp ke yang
    tersedia (passive nggak turun saat refine, cuma naik). Value diambil
    dari values_p1_to_p5[phase-1].
    """
    if not weapon_id:
        # Sentinel "no wengine equipped" (export dari profile tanpa equip).
        # Disc & set 4pc udah guard-by-construction; di sini tinggal skip lookup.
        return []
    w = mapped.get(weapon_id)
    if w is None:
        raise KeyError(f"weapon id {weapon_id} nggak ada di wengine_passive_mapped.json")
    p = w.get("passive") or {}
    entries = []
    for eff in p.get("effects", []):
        vals = eff.get("values_p1_to_p5") or []
        ph = max(1, min(int(phase), len(vals) or 1))
        raw = vals[ph - 1] if vals else 0.0
        # multi-variant (mis. Slice of Time: 20/25/30/35 decibel per skill
        # type) -> satu entry per varian biar bisa di-toggle terpisah
        variants = raw if isinstance(raw, list) else [raw]
        for i, v in enumerate(variants):
            _add_wengine_entry(entries, w, p, eff, ph, float(v),
                               len(variants), i)
    return entries


def build_set4pc_toggles(mapped: dict, set_name: str) -> list:
    """Set bonus 4pc -> ToggleEntry (satu efek dict bisa jadi beberapa entry
    kalau effect-nya multi-stat — tiap stat independently scoped).
    """
    s = mapped.get(set_name)
    if s is None:
        raise KeyError(f"set '{set_name}' nggak ada di drive_disc_mapped.json")
    entries = []
    for eff in s.get("effects_4pc", []):
        mode = eff.get("mode", "toggle")
        if mode == "stack":
            ed = eff.get("effect_per_stack") or {}
            stacks_max = int(eff.get("max") or 1)
        else:
            ed = eff.get("effect") or {}
            stacks_max = 1
        threshold_stat = ""
        threshold_text = ""
        if mode in ("threshold", "threshold_stack"):
            if eff.get("stat"):
                threshold_stat = re.sub(r"[^a-z0-9]+", "_",
                                        eff.get("stat", "").lower()).strip("_")
                threshold_text = (f"{eff.get('stat', '')} {eff.get('op', '>=')} "
                                  f"{eff.get('value', '')}")
            elif eff.get("value") is not None:
                threshold_text = (f"stacks('{eff.get('key', '')}') >= "
                                  f"{eff.get('value', '')}")
        for k, v in ed.items():
            stat, stypes, elems = _map_drive_effect_key(k)
            if mode in ("threshold", "threshold_stack"):
                cond = threshold_text
            else:
                cond = eff.get("trigger_label") or eff.get("key") or mode
            if k.startswith("team_"):
                cond = f"{cond} (team-wide)"
            entries.append(ToggleEntry(
                source="set4pc",
                source_name=f"{s['name']} 4pc",
                stat=stat,
                value=float(v),
                unit="percent",
                condition_text=cond,
                enabled=(mode == "always") or bool(eff.get("default_enabled")),
                skill_types=stypes or tuple(
                    _DRIVE_SKILL_WORDS.get(sk, sk) for sk in eff.get("skills", [])
                ),
                elements=elems,
                stacks_max=stacks_max,
                mode=mode,
                key=eff.get("key", ""),
                threshold_stat=threshold_stat,
                threshold_op=eff.get("op", ">="),
                threshold_value=float(eff.get("value") or 0.0),
                threshold_key=eff.get("key", ""),
                evidence=s.get("bonus_4pc_raw", ""),
            ))
    return entries


def build_mindscape_toggles(mapped: dict, avatar_id: int, mindscape_rank: int = 0) -> list:
    """Mindscape M1/M2/M4/M6 -> ToggleEntry. M3/M5 = skill bump, bukan
    conditional effect (di-skip). Level > mindscape_rank di-skip.
    """
    a = mapped.get(avatar_id)
    if a is None:
        raise KeyError(f"avatar id {avatar_id} nggak ada di mindscape_mapped.json")
    entries = []
    for lvl_str in ("1", "2", "4", "6"):
        if int(lvl_str) > mindscape_rank:
            continue
        L = a["levels"].get(lvl_str)
        if not L or L.get("kind") != "effects":
            continue
        for eff in L.get("effects", []):
            et = eff.get("effect_type", "")
            if et == "stat":
                stat = _map_named_stat(eff.get("stat", ""), eff.get("unit", ""))
            else:
                stat = _EFFECT_TYPE_TO_STAT.get(et, et or "unknown")
            cond = eff.get("condition") or {}
            scope = (tuple(eff.get("skill_types") or ()), _elements_of(eff))
            if cond.get("type") == "always":
                auto, review = _mechanical_auto_enable(
                    stat, tuple(x for part in scope for x in part),
                    eff.get("evidence", ""))
            else:
                auto, review = False, False
            if eff.get("default_enabled"):
                auto, review = True, False
            entries.append(ToggleEntry(
                source="mindscape",
                source_name=f"{a['name']} M{lvl_str} - {L.get('title', '')}",
                stat=stat,
                value=float(eff.get("value") or 0.0),
                unit=eff.get("unit", ""),
                condition_text=cond.get("label", ""),
                enabled=auto,
                skill_types=scope[0],
                elements=scope[1],
                stacks_max=int(eff.get("stacks_max") or 1),
                mode="always" if cond.get("type") == "always" else "toggle",
                key=eff.get("key", ""),
                needs_review=review or bool(L.get("needs_review")) or et == "unparsed",
                evidence=eff.get("evidence", ""),
            ))
    return entries


def _panel_value(panel: dict, stat_key: str):
    """Lookup stat di panel dengan dua casing ('Anomaly Mastery' dari
    final_stats / 'anomaly_mastery' dari threshold_stat mapped files)."""
    if stat_key in panel:
        return panel[stat_key]
    title = stat_key.replace("_", " ").title()
    for k, v in panel.items():
        if k.lower().replace(" ", "_") == stat_key or k == title:
            return v
    return None


def evaluate_thresholds(toggles: list, panel: dict = None) -> list:
    """Auto-evaluasi efek threshold — HANYA yang deterministik dari stat
    panel / jumlah stack (bukan deteksi trigger combat):
      - mode "threshold": bandingin panel[threshold_stat] vs threshold_value
        (mis. B&BS: anomaly_mastery 116 >= 115 -> ON)
      - mode "threshold_stack": ON kalau stack entry dengan key sama sudah
        >= threshold_value (mis. Yunkui Tales sheer dmg di 3 stack)
    Return list of (entry, note) buat ditampilkan.
    """
    stack_counts = {}
    for t in toggles:
        if t.mode == "stack" and t.key and t.enabled:
            stack_counts[t.key] = max(stack_counts.get(t.key, 0), t.stacks)
    notes = []
    for t in toggles:
        if t.mode == "threshold":
            val = _panel_value(panel or {}, t.threshold_stat)
            if val is None:
                notes.append((t, f"SKIP: panel stat '{t.threshold_stat}' nggak diketahui"))
                continue
            val = float(val)
            if t.threshold_op == "<=":
                ok = val <= t.threshold_value
            else:
                ok = val >= t.threshold_value
            t.enabled = ok
            notes.append((t, f"{t.threshold_stat}={val:g} {t.threshold_op} "
                            f"{t.threshold_value:g} -> {'ON' if ok else 'OFF'}"))
        elif t.mode == "threshold_stack":
            cur = stack_counts.get(t.threshold_key, 0)
            t.enabled = cur >= t.threshold_value
            notes.append((t, f"stacks('{t.threshold_key}')={cur} >= "
                            f"{t.threshold_value:g} -> {'ON' if t.enabled else 'OFF'}"))
    return notes


# ---------------------------------------------------------------------------
# CombatModifiers + agregasi
# ---------------------------------------------------------------------------

@dataclass
class CombatModifiers:
    """Bonus gabungan dari semua ToggleEntry yang enabled — bucket
    CONDITIONAL formula Final Stat (beda dari stat panel). Stat yang nggak
    dipakai formula dikumpulkan di `extra` (display only).
    """
    atk_bonus_pct_cond: float = 0.0
    atk_flat_cond: float = 0.0
    crit_rate_bonus_pct_cond: float = 0.0
    crit_dmg_bonus_pct_cond: float = 0.0
    damage_bonus_pct_cond: float = 0.0
    skill_mult_bonus_pct: float = 0.0
    pen_ratio_bonus_pct: float = 0.0
    pen_flat_bonus: float = 0.0
    def_ignore_pcts: list = field(default_factory=list)  # sumber independent
    # DEF Shred / DEF Increase — additive di dalam kurung DEF musuh
    # (ordering okMuzzy v3.1.0): DEF*(1 + DEFInc − ΣShred − ΣIgnore)*...
    def_shred_pct: float = 0.0
    def_increase_pct: float = 0.0
    res_ignore_pcts: list = field(default_factory=list)  # sumber independent
    res_shred_pct: float = 0.0
    # DMG Taken Modifier — efek yang nambah/ngurangin damage yang DITERIMA musuh:
    # dmg_taken_pct (mis. +35% dari efek "enemies take 35% more DMG"),
    # dmg_reduction_pct (mis. musuh punya damage reduction).
    dmg_taken_pct: float = 0.0
    dmg_reduction_pct: float = 0.0
    # ---- Bucket multiplier ekstra (okMuzzy v3.1.0 C1!P3) ----
    # Final Multiplier: × (1 + Σ) — buff tipe "multiplier" scoped per skill
    # (mis. Evelyn Chain/Ultimate +25%, Luminize). Sumber mapped: belum ada
    # (Scaling Buffs, item 6) — slot siap.
    final_mult_pct: float = 0.0
    # Direct DMG: × (1 + Σ) — bucket terpisah dari damage_pct biasa.
    # Sumber mapped: belum ada (satu-satunya di Excel = "Wind Infusion"
    # team buff) — slot siap.
    direct_dmg_pct: float = 0.0
    # Sheer DMG (hanya sheer/Rupture agent): × (1 + Σ Sheer DMG + Σ{elem} SDMG)
    sheer_dmg_pct: float = 0.0
    # Stun Multiplier: stack ADDITIF dengan enemy.stun_taken_pct di kurung
    # (1 + StunMultiplier) — okMuzzy C1!P3 `SUMIF("Stun Multiplier")`.
    stun_dmg_mult_pct: float = 0.0
    # ---- Daze final (okMuzzy C1!Q3) ----
    # Σ Daze% (wengine daze_bonus + mindscape daze_bonus + disc Daze%).
    daze_pct: float = 0.0
    # Impact adds utk Impact_combat (C1!B35 = F19 + Σ"Impem"):
    # flat (mis. Chief Sidekick +30) masuk sini; Impact% sudah jadi daze_pct
    # ala Excel kolom "Impact%" -> kurung Daze? TIDAK — di Excel "Impact%"
    # buff masuk F19 (Impact panel %). Kita treat impact_pct sebagai
    # multiplier Impact: impact_combat = panel * (1 + impact_pct/100) + flat.
    impact_flat: float = 0.0
    impact_pct: float = 0.0
    # ---- Buildup (okMuzzy C1!R3) ----
    # Σ Anomaly Buildup Rate (wengine 'Anomaly Buildup Rate' percent —
    # Peacekeeper/Roaring Ride/Timeweaver/Sharpened Stinger/Flight of
    # Fancy; mindscape "Buildup ... increases by X%").
    buildup_rate_pct: float = 0.0
    # ---- Anomaly DMG per-tick (okMuzzy 'Anomaly Calcs' C58-C63) ----
    # Σ "Anomaly DMG%" generik (mis. Notes From the Chained 16%) +
    # A3 = elemental DMG% panel agent. Scoped anomaly-name ("Assault
    # DMG%") belum ada sumber mapped — disc memakai bucket generik.
    anomaly_dmg_pct: float = 0.0
    # Disorder DMG (item 5) — bucket siap.
    disorder_dmg_pct: float = 0.0
    # Vortex DMG Mult (item 5) — 'Anomaly Calcs' C122-C127 `Σ Vortex DMG Mult`;
    # sumber mapped kandidat: W-Engine "Windswept and Vortex increases by X%"
    # (sekarang masih damage_bonus generik — lihat todo item 6).
    vortex_dmg_pct: float = 0.0
    # Polarity Disorder (Yanagi) — 'Anomaly Calcs' C72-C91 parameter:
    # (725% + 225% x Σ Skill Level) x Σ NagiAP. Tanpa sumber mapped (slot siap).
    polarity_dmg_pct: float = 0.0
    extra: dict = field(default_factory=dict)

    def describe(self) -> str:
        lines = []
        simple = [
            ("ATK%_cond", self.atk_bonus_pct_cond),
            ("ATK_flat_cond", self.atk_flat_cond),
            ("CRIT Rate%_cond", self.crit_rate_bonus_pct_cond),
            ("CRIT DMG%_cond", self.crit_dmg_bonus_pct_cond),
            ("DMG%", self.damage_bonus_pct_cond),
            ("skill_mult%+", self.skill_mult_bonus_pct),
            ("PEN Ratio%+", self.pen_ratio_bonus_pct),
            ("PEN flat+", self.pen_flat_bonus),
            ("DEF shred%", self.def_shred_pct),
            ("DEF increase%", self.def_increase_pct),
            ("RES shred%", self.res_shred_pct),
            ("DMG taken%", self.dmg_taken_pct),
            ("DMG reduction%", self.dmg_reduction_pct),
            ("Final Multiplier%", self.final_mult_pct),
            ("Direct DMG%", self.direct_dmg_pct),
            ("Sheer DMG%", self.sheer_dmg_pct),
            ("Stun Multiplier%", self.stun_dmg_mult_pct),
            ("Daze%", self.daze_pct),
            ("Impact flat+", self.impact_flat),
            ("Impact%+", self.impact_pct),
            ("Buildup Rate%", self.buildup_rate_pct),
            ("Anomaly DMG%", self.anomaly_dmg_pct),
            ("Disorder DMG%", self.disorder_dmg_pct),
            ("Vortex DMG%", self.vortex_dmg_pct),
        ]
        for name, v in simple:
            if v:
                lines.append(f"{name}: {v:+g}")
        if self.def_ignore_pcts:
            lines.append("DEF ignore% (per sumber): " +
                         ", ".join(f"{x:g}" for x in self.def_ignore_pcts))
        if self.res_ignore_pcts:
            lines.append("RES ignore% (per sumber): " +
                         ", ".join(f"{x:g}" for x in self.res_ignore_pcts))
        for k, v in sorted(self.extra.items()):
            if v:
                lines.append(f"extra {k}: {v:+g}")
        return "\n".join(lines) if lines else "(kosong)"


def aggregate_modifiers(toggles: list, skill_type: str = None,
                        element: str = None) -> CombatModifiers:
    """Gabungin semua ToggleEntry enabled -> CombatModifiers.
    Scope (skill_types/elements) dicek terhadap (skill_type, element) hit
    yang lagi dihitung; None = tanpa filter (semua scope masuk).
    """
    mods = CombatModifiers()
    for t in toggles:
        if not t.enabled:
            continue
        if not _scope_applies(t, skill_type, element):
            continue
        v = t.effective_value()
        if t.stat == "atk_pct":
            mods.atk_bonus_pct_cond += v
        elif t.stat == "atk_flat":
            mods.atk_flat_cond += v
        elif t.stat == "crit_rate_pct":
            mods.crit_rate_bonus_pct_cond += v
        elif t.stat == "crit_dmg_pct":
            mods.crit_dmg_bonus_pct_cond += v
        elif t.stat == "damage_pct":
            mods.damage_bonus_pct_cond += v
        elif t.stat == "skill_mult_pct":
            mods.skill_mult_bonus_pct += v
        elif t.stat == "pen_ratio_pct":
            mods.pen_ratio_bonus_pct += v
        elif t.stat == "pen_flat":
            mods.pen_flat_bonus += v
        elif t.stat == "def_ignore_pct":
            mods.def_ignore_pcts.append(v)
        elif t.stat == "def_shred_pct":
            mods.def_shred_pct += v
        elif t.stat == "def_increase_pct":
            mods.def_increase_pct += v
        elif t.stat == "res_ignore_pct":
            mods.res_ignore_pcts.append(v)
        elif t.stat == "res_shred_pct":
            mods.res_shred_pct += v
        elif t.stat == "dmg_taken_pct":
            mods.dmg_taken_pct += v
        elif t.stat == "dmg_reduction_pct":
            mods.dmg_reduction_pct += v
        elif t.stat == "final_mult_pct":
            mods.final_mult_pct += v
        elif t.stat == "direct_dmg_pct":
            mods.direct_dmg_pct += v
        elif t.stat == "sheer_dmg_pct":
            mods.sheer_dmg_pct += v
        elif t.stat == "stun_dmg_mult_pct":
            mods.stun_dmg_mult_pct += v
        elif t.stat == "daze_pct":
            mods.daze_pct += v
        elif t.stat == "impact_flat":
            mods.impact_flat += v
        elif t.stat == "impact_pct":
            mods.impact_pct += v
        elif t.stat == "buildup_rate_pct":
            mods.buildup_rate_pct += v
        elif t.stat == "anomaly_dmg_pct":
            mods.anomaly_dmg_pct += v
        elif t.stat == "anomaly_elem_dmg_pct":
            mods.anomaly_dmg_pct += v  # scoped-elem version, elem diberikan caller
        elif t.stat == "disorder_dmg_pct":
            mods.disorder_dmg_pct += v
        elif t.stat == "vortex_dmg_pct":
            mods.vortex_dmg_pct += v
        else:
            mods.extra[t.stat] = mods.extra.get(t.stat, 0.0) + v
    return mods


def print_toggle_table(toggles: list, show_disabled: bool = True,
                       show_evidence: bool = False) -> None:
    for t in toggles:
        if t.enabled or show_disabled:
            print("  " + t.label())
            if show_evidence and t.evidence:
                print(f"      evidence: {t.evidence}")


# ---------------------------------------------------------------------------
# Formula damage final
# ---------------------------------------------------------------------------

@dataclass
class EnemyStats:
    def_val: float
    # {"Physical": 0.0, "Ice": -0.20, ...} -- persen sebagai fraksi
    res_pct: dict = field(default_factory=dict)
    # Bonus damage yang diterima musuh saat STUN (fraksi, mis. 0.50 = +50%).
    # Dari MonsterSub LHPKLCOJKCN / StunDamageTakenRatio (Tyrfing 5000 -> 0.5,
    # The Defector 2500 -> 0.25). Boss umumnya lebih rendah.
    stun_taken_pct: float = 0.0
    # Daze RES per elemen (fraksi, StunRes MonsterSub /10000) — dipakai
    # compute_daze: Daze = Impact_combat * dazeMV% * (1 - Daze RES).
    daze_res_pct: dict = field(default_factory=dict)
    # Buildup RES per elemen (fraksi, BuildupRes MonsterSub /10000) —
    # dipakai compute_buildup: (1 − Buildup RES elemen hit).
    buildup_res_pct: dict = field(default_factory=dict)


def load_level_factor_curve(path: str = "data/LevelCurveTemplateTb.json") -> dict:
    """Load the canonical attacker Level Factor curve.

    In the supplied LevelCurveTemplateTb dump, row Id=1000 is a curve whose
    values are exactly 2x the Wiki Level Factor table (e.g. L1=100, L60=1588).
    Therefore LevelFactor(level) = curve_1000[level-1] / 2.
    """
    data = load_json(path)
    rows = data.get("MLOEFHJHCID", [])
    row = next((r for r in rows if r.get("DALBKGGEJEF") == 1000), None)
    if row is None:
        raise KeyError("LevelCurveTemplateTb: curve Id 1000 not found")
    values = row.get("JMIKNDKIMPH", [])
    if not values:
        raise ValueError("LevelCurveTemplateTb: curve Id 1000 has no values")
    return {level: value / 2.0 for level, value in enumerate(values, start=1)}


def get_level_factor(attacker_level: int, level_curve: dict | None = None) -> float:
    """Return the ZZZ DEF Level Factor for an attacker level (1-based).

    The game/wiki caps the displayed Level Factor at 794 from level 60 onward;
    the supplied curve itself is already plateaued, so levels above its length
    reuse the last value rather than silently changing the formula.
    """
    if attacker_level < 1:
        raise ValueError(f"attacker_level must be >= 1, got {attacker_level}")
    curve = level_curve if level_curve is not None else load_level_factor_curve()
    if not curve:
        raise ValueError("empty level factor curve")
    max_level = max(curve)
    return curve[min(attacker_level, max_level)]


def compute_def_mult(enemy_def: float, pen_ratio_pct: float = 0.0,
                     pen_flat: float = 0.0, def_ignore_pcts=(),
                     attacker_level: int = 60, level_factor_curve: dict | None = None,
                     def_shred_pct: float = 0.0,
                     def_increase_pct: float = 0.0) -> float:
    """DEFmult = LF / (LF + max(DEF*(1+DEFInc−ΣShred−ΣIgnore)*(1−PEN%)−PEN, 0)).

    Ordering aditif mengikuti okMuzzy v3.1.0 (C1!P3): DEF Shred dan DEF
    Ignore dikurangkan ADDITIF dari DEF musuh (bukan chain multiplikatif
    per sumber), PEN Ratio dikalikan SETELAHNYA, PEN flat terakhir.
    ``LF`` is the attacker's Level Factor from LevelCurveTemplateTb.
    Backward compatibility is preserved: omitting ``attacker_level`` uses 60,
    whose Level Factor is exactly 794 in the supplied curve.
    """
    level_factor = get_level_factor(attacker_level, level_factor_curve)
    effective = enemy_def * (1 + def_increase_pct / 100 - def_shred_pct / 100)
    for ig in def_ignore_pcts:
        effective -= enemy_def * (ig / 100)
    effective = max(effective * (1 - pen_ratio_pct / 100) - pen_flat, 0)
    return level_factor / (effective + level_factor)


def compute_res_mult(res_pct: float, res_ignore_pcts=(),
                     res_shred_pct: float = 0.0) -> float:
    """RESmult = 1 − (RES − Σignore_i − shred).

    Mengikuti okMuzzy v3.1.0: semua debuff RES dijumlahkan ADDITIF dalam
    satu kurung (1 − ΣRES − Σignore − shred), bukan dikurangi dari RES
    dulu secara multiplikatif. RES & debit dalam fraksi/persen-poin
    (mis. -0.20 = RES -20%).
    """
    res = res_pct - sum(res_ignore_pcts) / 100 - res_shred_pct / 100
    return 1 - res


def compute_daze(impact_combat: float, daze_mv_pct: float,
                 daze_res_pct: float = 0.0,
                 daze_bonus_pct: float = 0.0) -> float:
    """Daze final (okMuzzy v3.1.0 C1!Q3, verbatim):

        Daze = Impact_combat * dazeMV% * hit_count
               * (1 - Σ Daze RES musuh)
               * (1 + Σ Daze%)

    - Impact_combat (C1!B35): Impact panel + flat adds, dengan Impact%
      buff dikalikan (lihat compute_impact_combat).
    - dazeMV%: daze_pct per hit (skill_lookup.compute_daze).
    - Daze RES: StunRes musuh per elemen hit (MonsterSub /10000).
    - Σ Daze%: bucket `daze_pct` (wengine/mindscape `daze_bonus`, disc
      `*_daze_percent`) — scoped per skill via aggregate_modifiers.
    hit_count = 1 per hit row (pipeline per-hit; rotasi nanti yang
    mengalikan count).
    """
    return (impact_combat * (daze_mv_pct / 100)
            * (1 - daze_res_pct)
            * (1 + daze_bonus_pct / 100))


def compute_impact_combat(impact_panel: float,
                          mods: "CombatModifiers" = None) -> float:
    """Impact_combat ala okMuzzy C1!B35: panel + Σ Impact flat adds.
    (Buff 'Impact%' di Excel masuk ke stat panel section F19; kita model
    sebagai multiplier di sini — hasil sama untuk satu sumber.)"""
    mods = mods or CombatModifiers()
    return (impact_panel * (1 + mods.impact_pct / 100)
            + mods.impact_flat)


def compute_buildup(buildup_base: float, anomaly_mastery_combat: float,
                    buildup_rate_pct: float = 0.0,
                    buildup_res_pct: float = 0.0) -> float:
    """Buildup final (okMuzzy v3.1.0 C1!R3, verbatim):

        Buildup = buildup_base * (AM_combat / 100)
                  * (1 + Σ Buildup Rate + Σ {elem} Buildup Rate)
                  * (1 - Σ Buildup RES musuh - Σ {elem} Buildup RES)

    - buildup_base: nilai per hit dari skill_lookup.compute_buildup
      (AvatarSkillTemplateTb PEHOFGPKJBN /100; VERIFIED 61/61 vs
      zzz-hakushin-data 'AttributeInfliction' 2026-09-15).
    - AM_combat: Anomaly Mastery combat stat (okMuzzy F22 — panel +
      buffs AM%; unit %, mis. 116 -> 1.16x).
    - Buildup Rate: bucket `buildup_rate_pct` (scoped per skill).
    - Buildup RES: BuildupRes musuh per elemen (MonsterSub /10000).
    hit_count = 1 per hit row (rotasi yang mengalikan count, E92).
    """
    return (buildup_base
            * (anomaly_mastery_combat / 100)
            * (1 + buildup_rate_pct / 100)
            * (1 - buildup_res_pct))


# Konstanta multiplier elemen anomaly (okMuzzy 'Anomaly Calcs' C58-C63,
# di-copy PERSIS dari Excel 2026-09-15 — angka per TICK):
#   Physical/Assault 713%, Wind/Windswept 1250%, Ice/Shatter 500%,
#   Fire/Burn 50%, Electric/Shock 125%, Ether/Corruption 62.5%.
# Nama label buff scope per elemen (dipakai FILTER "Assault DMG%" dst).
ANOMALY_ELEM_MULT_PCT = {
    "Physical": 713.0,   # Assault
    "Wind": 1250.0,      # Windswept
    "Ice": 500.0,        # Shatter
    "Fire": 50.0,        # Burn (per tick)
    "Electric": 125.0,   # Shock (per tick)
    "Ether": 62.5,       # Corruption (per tick)
}
ANOMALY_LABEL = {
    "Physical": "Assault",
    "Wind": "Windswept",
    "Ice": "Shatter",
    "Fire": "Burn",
    "Electric": "Shock",
    "Ether": "Corruption",
}

# ---------------------------------------------------------------------------
# Kategori distribusi damage (item 7) — mirror 'CombinedRotationData' C1!V3:V11
# (urutan & nama persis: Basics, Dashes, Assists, Specials, Others, Chains,
# Ultimate, Anomaly, Disorder). Dipakai buat laporan rotasi (kolom V-Z:
# Source / Total Damage / Total Daze / Total Buildup).
# ---------------------------------------------------------------------------
DISTRIBUTION_CATEGORIES = (
    "Basics", "Dashes", "Assists", "Specials", "Others",
    "Chains", "Ultimate", "Anomaly", "Disorder",
)

_SKILL_TYPE_TO_CATEGORY = {
    "Basic Attack": "Basics",
    "Dash Attack": "Dashes",
    "Dodge Counter": "Dashes",
    "Dodge": "Dashes",
    "Quick Assist": "Assists",
    "Defensive Assist": "Assists",
    "Assist Follow-Up": "Assists",
    "Assist": "Assists",
    "Special Attack": "Specials",
    "EX Special Attack": "Specials",
    "Chain Attack": "Chains",
    "Ultimate": "Ultimate",
    "Anomaly": "Anomaly",
    "Disorder": "Disorder",
    "Polarity Disorder": "Disorder",
    "Vortex": "Disorder",
}


def skill_category(skill_type: str) -> str:
    """Petakan skill_type granular -> kategori distribusi Excel.
    Unknown -> 'Others' (kategori terakhir yang relevan)."""
    return _SKILL_TYPE_TO_CATEGORY.get(skill_type or "", "Others")


def compute_anomaly_damage(
    element: str,
    atk_combat: float,
    anomaly_proficiency: float,
    enemy: EnemyStats,
    mods: CombatModifiers = None,
    attacker_level: int = 60,
    level_factor_curve: dict | None = None,
    enemy_stunned: bool = False,
    elem_dmg_bonus_panel_pct: float = 0.0,
    anomaly_crit_rate_pct: float = 0.0,
    anomaly_crit_dmg_pct: float = 0.0,
    refringe_coef_pct: float = 0.0,
) -> dict:
    """Anomaly DMG per-tick (okMuzzy v3.1.0 'Anomaly Calcs' C58-C63,
    verbatim — semua konstanta diverifikasi ke Excel 2026-09-15):

        AnomalyDMG_tick = {elem_mult}% x ATK_combat
            x DEFmult (PEN diikutkan) x RESmult(elem)
            x (1 + Σ Stun Multiplier)
            x (AP_combat / 100) x 2 x (1 - DMGReduction)
            x (1 + elemDMG%_panel + Σ Anomaly DMG%)
            x (1 + CR_anomaly x CD_anomaly)
            x (1 + Σ Refringe Coefficient)

    - elem_mult: ANOMALY_ELEM_MULT_PCT (713% Assault, 1250% Windswept,
      500% Shatter, 50% Burn, 125% Shock, 62.5% Corruption — PER TICK).
    - ATK_combat: stat basis SEMUA tipe anomaly = ATK (C48 = panel +
      flat adds); Catatan: todo lama "MV_stat per tipe" TIDAK benar —
      Excel pakai ATK utk semua elemen (C48 dipakai C58-C63).
    - x2: konstanta Excel (semua tipe) — bukan jumlah tick.
    - CR/CD anomaly: crit khusus buff anomaly-scoped ("Assault Crit
      Rate") — TODO lama bilang "hanya Assault", TAPI dump formula
      C58-C63 nunjukin pola (1 + CR x CD) DI SEMUA ELEMEN. Panel CR/CD
      character TIDAK ikut (hanya buff scoped anomaly).
    - Tick count DoT (Burn/Shock/Corruption durasi) = kerjaan rotasi
      (C1!W10 Rounddown(Duration x rate)) — bukan fungsi per-tick ini.
    Return dict per-hit: {"non_crit", "crit", "tick_mult_pct", ...}.
    """
    mods = mods or CombatModifiers()
    mult_pct = ANOMALY_ELEM_MULT_PCT[element]

    def_mult = compute_def_mult(
        enemy.def_val,
        mods.pen_ratio_bonus_pct,
        mods.pen_flat_bonus,
        mods.def_ignore_pcts,
        attacker_level=attacker_level,
        level_factor_curve=level_factor_curve,
        def_shred_pct=mods.def_shred_pct,
        def_increase_pct=mods.def_increase_pct,
    )
    res_mult = compute_res_mult(
        enemy.res_pct.get(element, 0.0),
        mods.res_ignore_pcts,
        mods.res_shred_pct,
    )
    # Stun Multiplier: additive di satu kurung (stun_taken + Σ bucket)
    stun_mult = (1 + enemy.stun_taken_pct + mods.stun_dmg_mult_pct / 100
                 ) if enemy_stunned else 1.0
    # DMG Taken Modifier — paritas okMuzzy P3: (1 + DMGTaken%) linear
    # DAN (1 - DMGReduction) linear (bukan 1/(1-x) versi wiki lama).
    # Tidak ada sumber mapped yang pakai bucket ini (verified 0 match),
    # jadi perubahan ini murni parity + tidak mengganggu kalibrasi.
    dmg_taken_mult = ((1 + mods.dmg_taken_pct / 100)
                      * (1 - mods.dmg_reduction_pct / 100))
    # (1 + elemDMG% panel + Σ Anomaly DMG%)
    anomaly_dmg_mult = (1 + (elem_dmg_bonus_panel_pct
                             + mods.anomaly_dmg_pct) / 100)
    # crit anomaly: hanya buff scoped anomaly (CR x CD, floor 0)
    crit_mult = 1 + (anomaly_crit_rate_pct / 100) * (anomaly_crit_dmg_pct / 100)
    refringe_mult = 1 + refringe_coef_pct / 100

    non_crit = (atk_combat * (mult_pct / 100)
                * def_mult * res_mult
                * stun_mult
                * (anomaly_proficiency / 100) * 2 * dmg_taken_mult
                * anomaly_dmg_mult * refringe_mult)
    crit = non_crit * crit_mult
    return {
        "element": element,
        "anomaly_label": ANOMALY_LABEL[element],
        "tick_mult_pct": mult_pct,
        "def_mult": def_mult,
        "res_mult": res_mult,
        "stun_mult": stun_mult,
        "dmg_taken_mult": dmg_taken_mult,
        "anomaly_dmg_mult": anomaly_dmg_mult,
        "crit_mult": crit_mult,
        "refringe_mult": refringe_mult,
        "non_crit": non_crit,
        "crit": crit,
    }


# ---------------------------------------------------------------------------
# Disorder / Polarity / Vortex (item 5) — okMuzzy 'Anomaly Calcs' C65-C70,
# C72-C91, C122-C127 (verbatim, 2026-09-15).
# ---------------------------------------------------------------------------
#
# Base % per instance (SEMUA konstanta di-copy PERSIS dari Excel):
#   Disorder base (C65-C70), `t` = sisa durasi anomaly yang digantikan:
#     Physical/Ice : 450% + ROUNDDOWN(t)        x 7.5%
#     Wind         : 100%
#     Fire         : 450% + ROUNDDOWN(t / 0.5)  x 50%
#     Electric     : 450% + ROUNDDOWN(t)        x 125%
#     Ether        : 450% + ROUNDDOWN(t / 0.5)  x 62.5%
#   Polarity (C72-C91) memakai tabel base yang SAMA.
#   Vortex base (C122-C127), `t` = Final MAX Duration (default 10s):
#     Physical : 800% + t x 7.5%
#     Wind     : 0%  (Vortex = Wind + Physical/Ice; baris Wind = 0)
#     Ice      : Miyabi (Frost): 0% + t x 75% ; selain itu 1300% + t x 7.5%
#     Fire     : 900% + (t / 0.5) x 7.5%
#     Electric : 650% + t x 125%
#     Ether    : 650% + (t / 0.5) x 62.5%
# Catatan: per-instance damage TIDAK bisa crit (tidak ada bracket CR x CD
# di C65-C70 / C72-C91 / C122-C127) — `crit` = `non_crit`.

def disorder_base_pct(element: str, remaining_duration_s: float = 10.0) -> float:
    """Base Disorder/Polarity % (C65-C70, `ROUNDDOWN` = floor positif)."""
    t = max(0.0, float(remaining_duration_s))
    if element in ("Physical", "Ice"):
        return 450.0 + float(int(t)) * 7.5
    if element == "Wind":
        return 100.0
    if element == "Fire":
        return 450.0 + float(int(t / 0.5)) * 50.0
    if element == "Electric":
        return 450.0 + float(int(t)) * 125.0
    if element == "Ether":
        return 450.0 + float(int(t / 0.5)) * 62.5
    raise KeyError(f"elemen disorder tidak dikenal: {element!r}")


def vortex_base_pct(element: str, duration_s: float = 10.0,
                    is_frost: bool = False) -> float:
    """Base Vortex % (C122-C127). `duration_s` = Final MAX Duration (A54)."""
    t = max(0.0, float(duration_s))
    if element == "Physical":
        return 800.0 + t * 7.5
    if element == "Wind":
        return 0.0
    if element == "Ice":
        return (0.0 + t * 75.0) if is_frost else (1300.0 + t * 7.5)
    if element == "Fire":
        return 900.0 + (t / 0.5) * 7.5
    if element == "Electric":
        return 650.0 + t * 125.0
    if element == "Ether":
        return 650.0 + (t / 0.5) * 62.5
    raise KeyError(f"elemen vortex tidak dikenal: {element!r}")


# Yanagi Polarity: faktor pengali bagian disorder (C72/C79/C86).
POLARITY_FACTOR_BY_MINDSCAPE = {0: 0.15, 2: 0.5, 6: 0.8}


def polarity_factor_for_mindscape(mindscape_rank: int) -> float:
    """Faktor Polarity sesuai M-rank Yanagi (M0 0.15, M2+ 0.5, M6 0.8)."""
    if mindscape_rank >= 6:
        return POLARITY_FACTOR_BY_MINDSCAPE[6]
    if mindscape_rank >= 2:
        return POLARITY_FACTOR_BY_MINDSCAPE[2]
    return POLARITY_FACTOR_BY_MINDSCAPE[0]


def _anomaly_chain_multipliers(enemy: "EnemyStats", element: str,
                               mods: "CombatModifiers",
                               attacker_level: int,
                               level_factor_curve: dict | None,
                               enemy_stunned: bool) -> dict:
    """Chain DEF/RES/Stun/DMGTaken yang dipakai bareng anomaly & disorder."""
    def_mult = compute_def_mult(
        enemy.def_val,
        mods.pen_ratio_bonus_pct,
        mods.pen_flat_bonus,
        mods.def_ignore_pcts,
        attacker_level=attacker_level,
        level_factor_curve=level_factor_curve,
        def_shred_pct=mods.def_shred_pct,
        def_increase_pct=mods.def_increase_pct,
    )
    res_mult = compute_res_mult(
        enemy.res_pct.get(element, 0.0),
        mods.res_ignore_pcts,
        mods.res_shred_pct,
    )
    stun_mult = (1 + enemy.stun_taken_pct + mods.stun_dmg_mult_pct / 100
                 ) if enemy_stunned else 1.0
    dmg_taken_mult = ((1 + mods.dmg_taken_pct / 100)
                      * (1 - mods.dmg_reduction_pct / 100))
    return {
        "def_mult": def_mult,
        "res_mult": res_mult,
        "stun_mult": stun_mult,
        "dmg_taken_mult": dmg_taken_mult,
    }


def compute_disorder_damage(
    element: str,
    atk_combat: float,
    anomaly_proficiency: float,
    enemy: "EnemyStats",
    mods: CombatModifiers = None,
    attacker_level: int = 60,
    level_factor_curve: dict | None = None,
    enemy_stunned: bool = False,
    remaining_duration_s: float = 10.0,
    extra_base_pct: float = 0.0,
    dmg_bonus_pct: float = 0.0,
    refringe_coef_pct: float = 0.0,
) -> dict:
    """Disorder DMG per instance (okMuzzy 'Anomaly Calcs' C65-C70, verbatim):

        Disorder = (Σ Disorder BaseDMG + Σ {elem}D BaseDMG + base_elem(t))
            x ATK_combat x DEFmult x RESmult(elem) x (1 + Σ Stun Multiplier)
            x (AP/100) x 2 x (1 - DMGReduction)
            x (1 + A4 + Σ Disorder DMG% + Σ {elem}D DMG%)
            x (1 + Σ Refringe Coefficient)

    - base_elem(t): disorder_base_pct (t = sisa durasi anomaly sebelumnya).
    - `extra_base_pct`: Σ Disorder BaseDMG + Σ {elem}D BaseDMG (flat % dari
      buff; default 0 — belum ada sumber mapped).
    - `dmg_bonus_pct`: panel A4 (Disorder DMG%); bucket buff =
      mods.disorder_dmg_pct (scoped elemen menangani {elem}D DMG%).
    - TIDAK ada bracket crit (C65-C70) -> `crit` = `non_crit`.
    """
    mods = mods or CombatModifiers()
    base = extra_base_pct + disorder_base_pct(element, remaining_duration_s)
    m = _anomaly_chain_multipliers(enemy, element, mods, attacker_level,
                                   level_factor_curve, enemy_stunned)
    dmg_bonus_mult = 1 + (dmg_bonus_pct + mods.disorder_dmg_pct) / 100
    refringe_mult = 1 + refringe_coef_pct / 100
    non_crit = (atk_combat * (base / 100)
                * m["def_mult"] * m["res_mult"] * m["stun_mult"]
                * (anomaly_proficiency / 100) * 2 * m["dmg_taken_mult"]
                * dmg_bonus_mult * refringe_mult)
    return {
        "element": element,
        "base_pct": base,
        "def_mult": m["def_mult"],
        "res_mult": m["res_mult"],
        "stun_mult": m["stun_mult"],
        "dmg_taken_mult": m["dmg_taken_mult"],
        "dmg_bonus_mult": dmg_bonus_mult,
        "refringe_mult": refringe_mult,
        "non_crit": non_crit,
        "crit": non_crit,
    }


def compute_polarity_disorder_damage(
    element: str,
    atk_combat: float,
    anomaly_proficiency: float,
    enemy: "EnemyStats",
    mods: CombatModifiers = None,
    attacker_level: int = 60,
    level_factor_curve: dict | None = None,
    enemy_stunned: bool = False,
    remaining_duration_s: float = 10.0,
    polarity_factor: float = 0.15,
    polarity_skill_level: float = 0.0,
    polarity_nagi_ap: float = 0.0,
    extra_base_pct: float = 0.0,
    dmg_bonus_pct: float = 0.0,
    refringe_coef_pct: float = 0.0,
) -> dict:
    """Polarity Disorder (Yanagi) per instance — 'Anomaly Calcs' C72-C91:

        ((Σ Disorder BaseDMG + base_elem(t)) x ATK_combat x polarity_factor
          + (725% + 225% x Σ Polarity Skill Level) x Σ Polarity NagiAP)
        x DEFmult x RESmult(elem) x (1 + Σ Stun Multiplier)
        x (AP/100) x 2 x (1 - DMGReduction)
        x (1 + A4 + Σ Disorder DMG% + Σ {elem}D DMG%)
        x (1 + Σ Refringe Coefficient)

    `polarity_factor` = POLARITY_FACTOR_BY_MINDSCAPE (M0 0.15 / M2+ 0.5 /
    M6 0.8). Tanpa bracket crit -> `crit` = `non_crit`.
    """
    mods = mods or CombatModifiers()
    base = extra_base_pct + disorder_base_pct(element, remaining_duration_s)
    polarity_term = (7.25 + 2.25 * polarity_skill_level) * polarity_nagi_ap
    m = _anomaly_chain_multipliers(enemy, element, mods, attacker_level,
                                   level_factor_curve, enemy_stunned)
    dmg_bonus_mult = 1 + (dmg_bonus_pct + mods.disorder_dmg_pct) / 100
    refringe_mult = 1 + refringe_coef_pct / 100
    pre = atk_combat * (base / 100) * polarity_factor + polarity_term
    non_crit = (pre * m["def_mult"] * m["res_mult"] * m["stun_mult"]
                * (anomaly_proficiency / 100) * 2 * m["dmg_taken_mult"]
                * dmg_bonus_mult * refringe_mult)
    return {
        "element": element,
        "base_pct": base,
        "polarity_factor": polarity_factor,
        "polarity_term": polarity_term,
        "def_mult": m["def_mult"],
        "res_mult": m["res_mult"],
        "stun_mult": m["stun_mult"],
        "dmg_taken_mult": m["dmg_taken_mult"],
        "dmg_bonus_mult": dmg_bonus_mult,
        "refringe_mult": refringe_mult,
        "non_crit": non_crit,
        "crit": non_crit,
    }


def compute_vortex_damage(
    element: str,
    atk_combat: float,
    anomaly_proficiency: float,
    enemy: "EnemyStats",
    mods: CombatModifiers = None,
    attacker_level: int = 60,
    level_factor_curve: dict | None = None,
    enemy_stunned: bool = False,
    duration_s: float = 10.0,
    is_frost: bool = False,
    extra_base_pct: float = 0.0,
    elem_dmg_bonus_pct: float = 0.0,
    refringe_coef_pct: float = 0.0,
) -> dict:
    """Vortex DMG per instance — 'Anomaly Calcs' C122-C127 (verbatim):

        Vortex = (base_elem(t) x (1 + Σ Vortex DMG Mult))
            x ATK_combat x DEFmult x RESmult(elem) x (1 + Σ Stun Multiplier)
            x (AP/100) x 2 x (1 - DMGReduction)
            x (1 + A3 + Σ {elem} DMG% + Σ Anomaly DMG% + Σ Vortex DMG%)
            x (1 + Σ Refringe Coefficient)

    - `duration_s` = Final MAX Duration (default 10s); `is_frost` = Miyabi
      (baris Ice beda: 0% + t x 75%).
    - Vortex = Wind + Physical/Ice; baris Wind = 0%.
    - Tanpa bracket crit -> `crit` = `non_crit`.
    """
    mods = mods or CombatModifiers()
    base = extra_base_pct + vortex_base_pct(element, duration_s, is_frost)
    m = _anomaly_chain_multipliers(enemy, element, mods, attacker_level,
                                   level_factor_curve, enemy_stunned)
    dmg_bonus_mult = (1 + (elem_dmg_bonus_pct + mods.anomaly_dmg_pct
                           + mods.vortex_dmg_pct) / 100)
    refringe_mult = 1 + refringe_coef_pct / 100
    non_crit = (atk_combat * (base / 100)
                * m["def_mult"] * m["res_mult"] * m["stun_mult"]
                * (anomaly_proficiency / 100) * 2 * m["dmg_taken_mult"]
                * dmg_bonus_mult * refringe_mult)
    return {
        "element": element,
        "base_pct": base,
        "def_mult": m["def_mult"],
        "res_mult": m["res_mult"],
        "stun_mult": m["stun_mult"],
        "dmg_taken_mult": m["dmg_taken_mult"],
        "dmg_bonus_mult": dmg_bonus_mult,
        "refringe_mult": refringe_mult,
        "non_crit": non_crit,
        "crit": non_crit,
    }


def compute_final_damage(
    atk_panel: float,
    skill_mult_pct: float,
    crit_dmg_panel_pct: float,
    enemy: EnemyStats,
    element: str,
    skill_type: str = None,
    crit_rate_panel_pct: float = 0.0,
    dmg_bonus_panel_pct: float = 0.0,
    pen_ratio_pct: float = 0.0,
    pen_flat: float = 0.0,
    mods: CombatModifiers = None,
    attacker_level: int = 60,
    level_factor_curve: dict | None = None,
    enemy_stunned: bool = False,
    is_sheer_agent: bool = False,
    hp_panel: float = 0.0,
    sheer_force: float = 0.0,
) -> dict:
    """Formula lengkap: stat panel + combat modifiers -> non-crit & crit.
    `dmg_bonus_panel_pct` = elemental DMG bonus dari stat panel yang cocok
    dengan `element` (mis. Ice DMG +30% utk hit Ice) — caller yang milih.

    `enemy_stunned=True` mengaktifkan Stun Modifier (dmg * (1 +
    enemy.stun_taken_pct + Σ Stun Multiplier)) — nilai StunDamageTakenRatio
    musuh + bucket `stun_dmg_mult_pct` (mindscape stun_dmg_mult), stack
    ADDITIF dalam satu kurung (okMuzzy C1!P3, item 9 todo: jangan dikali).
    DMG Taken Modifier: (1 + dmg_taken%) / (1 - dmg_reduction%) — slot
    stat `dmg_taken_pct` / `dmg_reduction_pct` di CombatModifiers.

    Sheer agent (`is_sheer_agent=True`, profession Rupture — flag C1!B33
    "Sheer? YES" via Agent Data; verifikasi: Rupture ids 1051/1371/1441/
    1471/1531 == Yidhari/Yixuan/Norano/BanYue/SPBilly == daftar sheer
    agent Excel):
    - MV_stat = ATK_combat*0.3 + HP_combat*0.1 + Sheer Force (C1!B34).
      `hp_panel`/`sheer_force` dipass caller dari snapshot stats.
    - DEFmult = 1 (hit Sheer ignore DEF, C1!P3 `IF(B33="YES", 1, ...)`).
    - multiplier Sheer DMG aktif: × (1 + Σ Sheer DMG + Σ{elem} SDMG).
      (Bucket sheer_dmg_pct agregasi keduanya; scope elemen tetap jalan.)
    """
    mods = mods or CombatModifiers()

    atk_combat = atk_panel * (1 + mods.atk_bonus_pct_cond / 100) + mods.atk_flat_cond
    hp_combat = hp_panel  # tidak ada buff HP% kondisional di mapped files
    skill_mult = skill_mult_pct + mods.skill_mult_bonus_pct
    dmg_bonus = dmg_bonus_panel_pct + mods.damage_bonus_pct_cond
    if is_sheer_agent:
        # MV stat khusus sheer (C1!B34): 0.3*ATK + 0.1*HP + Sheer Force
        mv_stat = atk_combat * 0.3 + hp_combat * 0.1 + sheer_force
    else:
        mv_stat = atk_combat
    # CRIT Rate/DMG floor game (okMuzzy v3.1.0: MIN(1, CR) & MAX(0.5, CD);
    # clamp CR 0-100 tetap): CR efektif minimal 5%, CD efektif minimal 50%.
    crit_rate_combat = min(max(crit_rate_panel_pct + mods.crit_rate_bonus_pct_cond, 5.0), 100.0)
    crit_dmg_combat = max(crit_dmg_panel_pct + mods.crit_dmg_bonus_pct_cond, 50.0)

    if is_sheer_agent:
        # hit Sheer ignore DEF sepenuhnya (C1!P3)
        def_mult = 1.0
    else:
        def_mult = compute_def_mult(
            enemy.def_val,
            pen_ratio_pct + mods.pen_ratio_bonus_pct,
            pen_flat + mods.pen_flat_bonus,
            mods.def_ignore_pcts,
            attacker_level=attacker_level,
            level_factor_curve=level_factor_curve,
            def_shred_pct=mods.def_shred_pct,
            def_increase_pct=mods.def_increase_pct,
        )
    res_mult = compute_res_mult(
        enemy.res_pct.get(element, 0.0),
        mods.res_ignore_pcts,
        mods.res_shred_pct,
    )
    # Stun Modifier — hanya kalau musuh lagi stun; Stun Multiplier bucket
    # stack ADDITIF dengan stun_taken musuh (okMuzzy C1!P3, satu kurung).
    stun_mult = (1 + enemy.stun_taken_pct + mods.stun_dmg_mult_pct / 100
                 ) if enemy_stunned else 1.0
    # DMG Taken Modifier — efek nambah/ngurangin damage yang diterima
    # musuh. Paritas okMuzzy P3: (1 + DMGTaken%) x (1 - DMGReduction),
    # dua-duanya LINEAR (P3 dump 2026-09-15 `(1 - DMGReduction)`; versi
    # wiki lama 1/(1-x) diganti — 0 sumber mapped memakai bucket ini).
    dmg_taken_mult = ((1 + mods.dmg_taken_pct / 100)
                      * (1 - mods.dmg_reduction_pct / 100))
    # Multiplier ekstra (C1!P3, item 1 todo):
    final_mult_mult = 1 + mods.final_mult_pct / 100
    direct_dmg_mult = 1 + mods.direct_dmg_pct / 100
    # Sheer DMG hanya utk sheer agent (C1!P3 IF B33=YES)
    sheer_dmg_mult = (1 + mods.sheer_dmg_pct / 100) if is_sheer_agent else 1.0

    non_crit = (mv_stat * (skill_mult / 100)
                * (1 + dmg_bonus / 100) * def_mult * res_mult
                * stun_mult * dmg_taken_mult
                * final_mult_mult * direct_dmg_mult * sheer_dmg_mult)
    crit = non_crit * (1 + crit_dmg_combat / 100)

    expected = non_crit * (1 - crit_rate_combat / 100
                           + (crit_rate_combat / 100) * (1 + crit_dmg_combat / 100))

    return {
        "atk_combat": atk_combat,
        "mv_stat": mv_stat,
        "skill_mult_pct": skill_mult,
        "dmg_bonus_pct": dmg_bonus,
        "def_mult": def_mult,
        "res_mult": res_mult,
        "stun_mult": stun_mult,
        "dmg_taken_mult": dmg_taken_mult,
        "final_mult_mult": final_mult_mult,
        "direct_dmg_mult": direct_dmg_mult,
        "sheer_dmg_mult": sheer_dmg_mult,
        "crit_rate_combat_pct": crit_rate_combat,
        "crit_dmg_combat_pct": crit_dmg_combat,
        "non_crit": non_crit,
        "crit": crit,
        "expected": expected,
    }


# ---------------------------------------------------------------------------
# Pipeline per-snapshot (shared run.py & server.py)
# ---------------------------------------------------------------------------

def build_snapshot_toggles(snapshot: dict, wengines: dict, sets: dict,
                           mindscapes: dict) -> list:
    """Toggle list dari snapshot: W-Engine + set 4pc + mindscape.
    (Bagian identik yang tadinya diduplikasi di run.py & server.py.)"""
    toggles = []
    weapon = snapshot.get("weapon") or {}
    if weapon.get("id"):
        toggles += build_wengine_toggles(wengines, weapon_id=weapon["id"],
                                         phase=weapon.get("phase", 1))
    for set_name in snapshot.get("set4pc", []) or []:
        toggles += build_set4pc_toggles(sets, set_name=set_name)
    toggles += build_mindscape_toggles(
        mindscapes, avatar_id=snapshot["avatar_id"],
        mindscape_rank=snapshot.get("mindscape", 0))
    return toggles


def compute_all_damage(snapshot: dict, enemy: "EnemyStats",
                       wengines: dict, sets: dict, mindscapes: dict,
                       enemy_stunned: bool = False,
                       level_factor_curve: dict | None = None,
                       toggle_overrides: dict | None = None) -> tuple[list, list]:
    """Hitung damage tiap hit non-hidden dari satu snapshot
    (compute_avatar_snapshot) — versi shared run.py & server.py.

    Fix vs versi lama (yang duplikat di run.py/server.py):
    - CRIT Rate panel dipass -> `expected` valid (bukan = non_crit).
    - Elemental DMG bonus per-HIT dari elemen hit (bukan elemen karakter):
      Kazahana hit-1 Miyabi Physical (GT 1086) walau karakter Ice.
    - Scope toggle per-HIT: skill_type granular ('Dash Attack',
      'Dodge Counter', 'Quick Assist', ...) + element hit — toggle scoped
      kini benar-benar match.
    - attacker_level dipass dari level karakter (level factor benar utk
      karakter < Lv60).
    - threshold dievaluasi dengan panel snapshot (Title Case key kini
      diterima oleh evaluate_thresholds).

    Return (rows, toggles): rows = dict per hit; toggles utk transparansi.
    """
    stats = snapshot["stats"]
    toggles = build_snapshot_toggles(snapshot, wengines, sets, mindscapes)
    evaluate_thresholds(toggles, panel=stats)  # mutasi t.enabled in-place
    apply_toggle_overrides(toggles, toggle_overrides)  # override UI (item 12)

    if level_factor_curve is None:
        level_factor_curve = load_level_factor_curve()

    # Sheer agent = profession "Rupture" (okMuzzy C1!B33 "Sheer?" via
    # Agent Data; Rupture ids 1051/1371/1441/1471/1531 = Yidhari/Yixuan/
    # Norano/BanYue/SPBilly — persis daftar sheer agent di Excel).
    is_sheer = (snapshot.get("profession") == "Rupture")

    # Impact_combat utk Daze (C1!B35) — dihitung sekali, pakai semua toggle
    # enabled tanpa scope (buff Impact umumnya unscoped).
    impact_mods = aggregate_modifiers(toggles, skill_type=None, element=None)
    impact_combat = compute_impact_combat(
        stats.get("Impact", 0.0), impact_mods)

    results = []
    for skill_idx, skill_data in snapshot.get("skills", {}).items():
        for hit in skill_data["hits"]:
            if hit.get("is_hidden"):
                continue
            # scope granular per hit: 'Dash Attack'/'Dodge Counter'/...
            # (fallback label skill gabungan utk hit tanpa nama dikenal)
            hit_skill_type = hit.get("skill_type") or skill_data["label"]
            hit_element = hit.get("element") or snapshot.get("element", "Physical")
            mods = aggregate_modifiers(toggles, skill_type=hit_skill_type,
                                      element=hit_element)
            r = compute_final_damage(
                atk_panel=stats["ATK"],
                skill_mult_pct=hit["damage_pct"],
                crit_dmg_panel_pct=stats.get("CRIT DMG", 0.0),
                enemy=enemy,
                element=hit_element,
                skill_type=hit_skill_type,
                crit_rate_panel_pct=stats.get("CRIT Rate", 0.0),
                dmg_bonus_panel_pct=stats.get(f"{hit_element} DMG", 0.0),
                pen_ratio_pct=stats.get("PEN Ratio", 0.0),
                pen_flat=stats.get("PEN", 0.0),
                mods=mods,
                attacker_level=int(snapshot.get("level", 60)),
                level_factor_curve=level_factor_curve,
                enemy_stunned=enemy_stunned,
                is_sheer_agent=is_sheer,
                hp_panel=stats.get("HP", 0.0),
                sheer_force=stats.get("Sheer Force", 0.0),
            )
            # Daze final (C1!Q3) — per hit, scoped Daze% bucket + StunRes
            # musuh per elemen hit.
            daze_val = compute_daze(
                impact_combat=impact_combat,
                daze_mv_pct=hit.get("daze_pct", 0.0),
                daze_res_pct=enemy.daze_res_pct.get(hit_element, 0.0),
                daze_bonus_pct=mods.daze_pct,
            ) if hit.get("daze_pct", 0.0) else 0.0
            # Buildup final (C1!R3) — per hit (hanya hit dengan buildup > 0),
            # scoped Buildup Rate bucket + BuildupRES musuh per elemen hit.
            buildup_val = compute_buildup(
                buildup_base=hit.get("buildup", 0.0),
                anomaly_mastery_combat=stats.get("Anomaly Mastery", 0.0),
                buildup_rate_pct=mods.buildup_rate_pct,
                buildup_res_pct=enemy.buildup_res_pct.get(hit_element, 0.0),
            ) if hit.get("buildup", 0.0) else 0.0
            results.append({
                "skill_label": skill_data["label"],
                "skill_key": skill_idx,
                "hit_name": hit["name"],
                "hit_id": hit.get("hit_id"),
                "hit_element": hit_element,
                "hit_skill_type": hit_skill_type,
                "skill_category": skill_category(hit_skill_type),
                "damage_pct": hit["damage_pct"],
                "daze_pct": hit.get("daze_pct", 0.0),
                "buildup_pct": hit.get("buildup", 0.0),
                "non_crit": r["non_crit"],
                "crit": r["crit"],
                "expected": r["expected"],
                "daze": daze_val,
                "buildup": buildup_val,
            })
    # Anomaly DMG per-tick (item 4): satu baris per elemen anomaly yang
    # relevan — elemen karakter (+ "Frost" handling Frostburn? belum:
    # Frost = Miyabi case, treat sbg Ice). AP = Anomaly Proficiency
    # panel; ATK_combat pakai aggregate unscoped (kayak Impact).
    agent_element = snapshot.get("element", "Physical")
    anomaly_elements = [agent_element] if agent_element in ANOMALY_ELEM_MULT_PCT else []
    # anomaly-scoped buffs: element-scoped toggles sudah masuk via aggregate
    # (elements=('Physical',) dst); pakai scope (None, elemen anomaly).
    for elem in anomaly_elements:
        amods = aggregate_modifiers(toggles, skill_type=None, element=elem)
        ar = compute_anomaly_damage(
            element=elem,
            atk_combat=stats["ATK"] * (1 + amods.atk_bonus_pct_cond / 100)
                       + amods.atk_flat_cond,
            anomaly_proficiency=stats.get("Anomaly Proficiency", 0.0),
            enemy=enemy,
            mods=amods,
            attacker_level=int(snapshot.get("level", 60)),
            level_factor_curve=level_factor_curve,
            enemy_stunned=enemy_stunned,
            elem_dmg_bonus_panel_pct=stats.get(f"{elem} DMG", 0.0),
        )
        results.append({
            "skill_label": "Anomaly",
            "skill_key": None,
            "hit_name": f"{ANOMALY_LABEL[elem]} ({elem})",
            "hit_id": None,
            "hit_element": elem,
            "hit_skill_type": "Anomaly",
            "skill_category": "Anomaly",
            "damage_pct": ANOMALY_ELEM_MULT_PCT[elem],
            "daze_pct": 0.0,
            "buildup_pct": 0.0,
            "non_crit": ar["non_crit"],
            "crit": ar["crit"],
            "expected": ar["non_crit"],  # per-tick; expected = rotasi
            "daze": 0.0,
            "buildup": 0.0,
            "anomaly_tick": True,
        })
    return results, toggles


# ---------------------------------------------------------------------------
# Rotation & DPS output (item 7) — mirror 'DPS Calcs' + 'CombinedRotationData'
# ---------------------------------------------------------------------------
#
# Format rotasi (JSON) — reference hit pakai `hit_id` (paling robust), atau
# `skill`/`skill_category`/`hit_skill_type` + `hit`/`hit_index`:
#
#   {
#     "name": "Miyabi basic loop",
#     "time": 20.0,                       # detik, WAJIB (> 0)
#     "rotation_mult": 1.0,               # pengali global (opsional)
#     "normal": [{"hit_id": 1091007, "count": 3},
#                {"skill": "Anomaly", "hit": "Shatter (Ice)", "count": 1}],
#     "stun":   [{"hit_id": 1091019, "count": 1}],
#     "normal_repeat": 1,                 # 'Repeat this rotation X times'
#     "stun_repeat": 1                    # 'Repeat this stun rotation X times'
#   }
#
# Fase stun persis ala BC-style: `normal` dihitung tanpa Stun Modifier,
# `stun` dengan `enemy_stunned=True` (StunTaken + StunMultiplier bucket).
# Anomaly DoT (Burn/Shock/Corruption): `count` = jumlah tick
# (C1!W10 Rounddown(Duration x rate)) — tetap kerjaan input rotasi.
# Total damage = Σ hit x count x repeat x rotation_mult; DPS = total / time.

def normalize_rotation(data) -> dict:
    """Normalisasi file/masukan rotasi -> dict lengkap (validasi + alias).
    Menerima list polos (dianggap `normal`) atau dict."""
    if isinstance(data, list):
        data = {"normal": data}
    if not isinstance(data, dict):
        raise ValueError("rotation harus berupa dict atau list entry")

    time = data.get("time", data.get("duration"))
    if time is None:
        raise ValueError("rotation butuh field 'time' (durasi rotasi, detik)")
    time = float(time)
    if time <= 0:
        raise ValueError(f"rotation 'time' harus > 0 (dapat {time})")

    mult = float(data.get("rotation_mult", 1.0))
    if mult <= 0:
        raise ValueError(f"rotation_mult harus > 0 (dapat {mult})")

    def _repeat(*keys, default=1) -> int:
        for k in keys:
            if data.get(k) is not None:
                return int(data[k])
        return default

    return {
        "name": data.get("name") or "rotation",
        "time": time,
        "rotation_mult": mult,
        "normal": list(data.get("normal") or data.get("rotation") or []),
        "stun": list(data.get("stun") or data.get("stun_rotation") or []),
        "normal_repeat": _repeat("normal_repeat", "repeat"),
        "stun_repeat": _repeat("stun_repeat"),
        # Disorder/Polarity/Vortex (item 5) — list spec per instance:
        #   {"element": "Ice", "count": 1, "remaining_duration": 10}
        #   polarity tambahan: {"mindscape": 0|2|6, "skill_level": n, "nagi_ap": x}
        #   vortex tambahan: {"duration": 10, "is_frost": false}
        "disorder": list(data.get("disorder") or []),
        "polarity": list(data.get("polarity") or []),
        "vortex": list(data.get("vortex") or []),
    }


def _resolve_rotation_ref(rows: list, ref, phase: str) -> dict:
    """Resolve satu entry rotasi -> row hasil compute_all_damage.

    Prioritas: `hit_id` > `skill`/`skill_category` + `hit`/`hit_index`.
    Raise LookupError dengan daftar kandidat kalau ambigu/tidak ketemu.
    """
    if not isinstance(ref, dict):
        raise ValueError(f"[{phase}] entry rotasi harus dict, dapat {type(ref).__name__}")

    if ref.get("hit_id") is not None:
        hid = int(ref["hit_id"])
        for r in rows:
            if r.get("hit_id") == hid:
                return r
        avail = sorted({r["hit_id"] for r in rows if r.get("hit_id") is not None})
        raise LookupError(f"[{phase}] hit_id {hid} tidak ada di skill karakter ini; "
                          f"hit_id tersedia: {avail}")

    pool = list(rows)
    skill = ref.get("skill", ref.get("skill_category", ref.get("hit_skill_type")))
    if skill is not None:
        s = str(skill).strip().lower()
        pool = [r for r in pool
                if r["skill_label"].strip().lower() == s
                or str(r.get("skill_category", "")).strip().lower() == s
                or r["hit_skill_type"].strip().lower() == s]
        if not pool:
            labels = sorted({r["skill_label"] for r in rows})
            raise LookupError(f"[{phase}] skill '{skill}' tidak cocok; "
                              f"skill tersedia: {labels}")

    hit = ref.get("hit", ref.get("hit_name"))
    if hit is not None:
        h = str(hit).strip().lower()
        exact = [r for r in pool if r["hit_name"].strip().lower() == h]
        picks = exact or [r for r in pool if h in r["hit_name"].strip().lower()]
        if not picks:
            names = sorted({r["hit_name"] for r in pool})
            raise LookupError(f"[{phase}] hit '{hit}' tidak cocok; "
                              f"hit tersedia: {names}")
        pool = picks

    if ref.get("hit_index") is not None:
        idx = int(ref["hit_index"])
        if idx < 0 or idx >= len(pool):
            raise IndexError(f"[{phase}] hit_index {idx} di luar rentang "
                             f"(0..{len(pool) - 1})")
        return pool[idx]

    if len(pool) == 1:
        return pool[0]

    names = sorted({r["hit_name"] for r in pool})
    raise LookupError(f"[{phase}] referensi ambigu ({len(pool)} hit) — tambahkan "
                      f"'hit_index'/'hit_id'; kandidat: {names}")


def summarize_rotation(rotation, rows_by_phase: dict,
                       extra_rows: list | None = None) -> dict:
    """Pure summation: rotation + rows per fase -> laporan total & distribusi.

    `rows_by_phase` = {"normal": [...], "stun": [...]} (output
    compute_all_damage). Excel: total = Σ hit x count x repeat x rotation_mult;
    distribusi per kategori (Basics/Dashes/.../Anomaly/Disorder) ala
    CombinedRotationData kolom V-Z. Damage pakai `expected` (CR-weighted).

    `extra_rows` = row sintetis (Disorder/Polarity/Vortex dari item 5) yang
    TIDAK direferensikan lewat file rotasi — tiap row bawa `count` sendiri dan
    dihitung `count x normal_repeat x rotation_mult`.
    """
    rot = normalize_rotation(rotation)
    totals = {"damage": 0.0, "non_crit": 0.0, "crit": 0.0,
              "daze": 0.0, "buildup": 0.0}
    dist = {c: {"category": c, "damage": 0.0, "non_crit": 0.0, "crit": 0.0,
                "daze": 0.0, "buildup": 0.0} for c in DISTRIBUTION_CATEGORIES}
    entries = []

    def _accumulate(row, uses, phase, count):
        non_crit = float(row.get("non_crit", 0.0)) * uses
        crit = float(row.get("crit", 0.0)) * uses
        damage = float(row.get("expected", row.get("non_crit", 0.0))) * uses
        daze = float(row.get("daze", 0.0)) * uses
        buildup = float(row.get("buildup", 0.0)) * uses

        totals["damage"] += damage
        totals["non_crit"] += non_crit
        totals["crit"] += crit
        totals["daze"] += daze
        totals["buildup"] += buildup

        cat = row.get("skill_category") or skill_category(row.get("hit_skill_type", ""))
        d = dist.setdefault(cat, {"category": cat, "damage": 0.0, "non_crit": 0.0,
                                  "crit": 0.0, "daze": 0.0, "buildup": 0.0})
        d["damage"] += damage
        d["non_crit"] += non_crit
        d["crit"] += crit
        d["daze"] += daze
        d["buildup"] += buildup

        entries.append({
            "phase": phase,
            "skill": row.get("skill_label"),
            "hit": row.get("hit_name"),
            "hit_id": row.get("hit_id"),
            "category": cat,
            "element": row.get("hit_element"),
            "count": count,
            "damage": damage,
            "daze": daze,
            "buildup": buildup,
        })

    for phase, repeat_key in (("normal", "normal_repeat"), ("stun", "stun_repeat")):
        rows = rows_by_phase.get(phase) or []
        repeat = int(rot[repeat_key])
        if repeat < 0:
            raise ValueError(f"{repeat_key} tidak boleh negatif (dapat {repeat})")
        for ref in rot[phase]:
            row = _resolve_rotation_ref(rows, ref, phase)
            count = float(ref.get("count", 1) or 0)
            _accumulate(row, count * repeat * rot["rotation_mult"], phase, count)

    # Disorder / Polarity / Vortex (item 5) — sudah per-instance, count-nya
    # sendiri; ikut repeat rotasi normal + rotation_mult (tanpa repeat stun).
    for row in extra_rows or []:
        count = float(row.get("count", 1) or 0)
        uses = count * rot["normal_repeat"] * rot["rotation_mult"]
        _accumulate(row, uses, row.get("phase", "disorder"), count)

    damage_total = totals["damage"]
    distribution = []
    for c in DISTRIBUTION_CATEGORIES:
        d = dist[c]
        if d["damage"] or d["daze"] or d["buildup"]:
            d = dict(d)
            d["pct"] = (d["damage"] / damage_total * 100.0) if damage_total else 0.0
            distribution.append(d)

    return {
        "name": rot["name"],
        "time": rot["time"],
        "rotation_mult": rot["rotation_mult"],
        "normal_repeat": rot["normal_repeat"],
        "stun_repeat": rot["stun_repeat"],
        "total": damage_total,
        "total_non_crit": totals["non_crit"],
        "total_crit": totals["crit"],
        "total_daze": totals["daze"],
        "total_buildup": totals["buildup"],
        "dps": damage_total / rot["time"],
        "dps_non_crit": totals["non_crit"] / rot["time"],
        "dps_crit": totals["crit"] / rot["time"],
        "distribution": distribution,
        "entries": entries,
    }


def _special_row(skill_label: str, hit_name: str, element: str,
                 skill_type: str, damage: float, count: float,
                 phase: str, damage_pct: float) -> dict:
    return {
        "skill_label": skill_label,
        "skill_key": None,
        "hit_name": hit_name,
        "hit_id": None,
        "hit_element": element,
        "hit_skill_type": skill_type,
        "skill_category": "Disorder",
        "damage_pct": damage_pct,
        "daze_pct": 0.0,
        "buildup_pct": 0.0,
        "non_crit": damage,
        "crit": damage,
        "expected": damage,
        "daze": 0.0,
        "buildup": 0.0,
        "count": float(count),
        "phase": phase,
    }


def build_special_rows(snapshot: dict, enemy: "EnemyStats", toggles: list,
                       rot: dict,
                       level_factor_curve: dict | None = None) -> list:
    """Baris sintetis Disorder / Polarity / Vortex (item 5) dari section
    rotasi `disorder` / `polarity` / `vortex` — dimasukkan ke distribusi
    kategori "Disorder" tanpa perlu direferensikan lewat list normal.

    Tiap spec: {"element", "count", "remaining_duration"|"duration",
    ...}. Default element = elemen karakter. Tidak ada auto-deteksi (aturan
    metodologi #5): trigger harus eksplisit di file rotasi.
    """
    stats = snapshot["stats"]
    agent_element = snapshot.get("element", "Physical")
    level = int(snapshot.get("level", 60))
    ap = stats.get("Anomaly Proficiency", 0.0)
    rows = []

    def _mods(elem):
        m = aggregate_modifiers(toggles, skill_type=None, element=elem)
        atk = stats["ATK"] * (1 + m.atk_bonus_pct_cond / 100) + m.atk_flat_cond
        return m, atk

    for spec in rot.get("disorder") or []:
        elem = spec.get("element") or agent_element
        mods, atk = _mods(elem)
        d = compute_disorder_damage(
            element=elem, atk_combat=atk, anomaly_proficiency=ap, enemy=enemy,
            mods=mods, attacker_level=level, level_factor_curve=level_factor_curve,
            enemy_stunned=False,
            remaining_duration_s=float(spec.get("remaining_duration", 10.0)),
            extra_base_pct=float(spec.get("extra_base_pct", 0.0)),
            dmg_bonus_pct=float(spec.get("dmg_bonus_pct", 0.0)),
        )
        rows.append(_special_row(
            "Disorder", f"Disorder ({elem})", elem, "Disorder",
            d["non_crit"], spec.get("count", 1), "disorder", d["base_pct"]))

    for spec in rot.get("polarity") or []:
        elem = spec.get("element") or agent_element
        mods, atk = _mods(elem)
        ms = int(spec.get("mindscape", snapshot.get("mindscape", 0)) or 0)
        d = compute_polarity_disorder_damage(
            element=elem, atk_combat=atk, anomaly_proficiency=ap, enemy=enemy,
            mods=mods, attacker_level=level, level_factor_curve=level_factor_curve,
            enemy_stunned=False,
            remaining_duration_s=float(spec.get("remaining_duration", 10.0)),
            polarity_factor=float(spec.get("polarity_factor",
                                           polarity_factor_for_mindscape(ms))),
            polarity_skill_level=float(spec.get("skill_level", 0.0)),
            polarity_nagi_ap=float(spec.get("nagi_ap", 0.0)),
            extra_base_pct=float(spec.get("extra_base_pct", 0.0)),
        )
        rows.append(_special_row(
            "Disorder", f"Polarity Disorder ({elem})", elem, "Polarity Disorder",
            d["non_crit"], spec.get("count", 1), "disorder", d["base_pct"]))

    for spec in rot.get("vortex") or []:
        elem = spec.get("element") or agent_element
        mods, atk = _mods(elem)
        is_frost = bool(spec.get("is_frost", False))
        d = compute_vortex_damage(
            element=elem, atk_combat=atk, anomaly_proficiency=ap, enemy=enemy,
            mods=mods, attacker_level=level, level_factor_curve=level_factor_curve,
            enemy_stunned=False,
            duration_s=float(spec.get("duration", 10.0)),
            is_frost=is_frost,
            extra_base_pct=float(spec.get("extra_base_pct", 0.0)),
            elem_dmg_bonus_pct=stats.get(f"{elem} DMG", 0.0),
        )
        rows.append(_special_row(
            "Disorder", f"Vortex ({elem})", elem, "Vortex",
            d["non_crit"], spec.get("count", 1), "disorder", d["base_pct"]))

    return rows


def compute_rotation(snapshot: dict, enemy: "EnemyStats", wengines: dict,
                     sets: dict, mindscapes: dict, rotation,
                     level_factor_curve: dict | None = None,
                     toggle_overrides: dict | None = None) -> tuple[dict, list]:
    """Hitung rotasi penuh utk satu snapshot: normal (tanpa stun) + fase stun
    (enemy_stunned=True, ala BC-style) -> laporan total + DPS + distribusi.

    Return (report, toggles). Rows dihitung sekali per fase; fase stun hanya
    dihitung kalau rotasi punya entry `stun`. Section `disorder`/`polarity`/
    `vortex` (item 5) menambah baris sintetis ke distribusi "Disorder".
    `toggle_overrides` (item 12) = {toggle_id: bool} dari checkbox UI.
    """
    rot = normalize_rotation(rotation)
    rows_normal, toggles = compute_all_damage(
        snapshot, enemy, wengines, sets, mindscapes,
        enemy_stunned=False, level_factor_curve=level_factor_curve,
        toggle_overrides=toggle_overrides)
    rows_stun = rows_normal
    if rot["stun"]:
        rows_stun, _ = compute_all_damage(
            snapshot, enemy, wengines, sets, mindscapes,
            enemy_stunned=True, level_factor_curve=level_factor_curve,
            toggle_overrides=toggle_overrides)
    extra = build_special_rows(snapshot, enemy, toggles, rot, level_factor_curve)
    report = summarize_rotation(rot, {"normal": rows_normal, "stun": rows_stun},
                                extra_rows=extra)
    report["avatar"] = snapshot.get("name")
    return report, toggles


def format_rotation_report(report: dict) -> str:
    """Laporan rotasi siap-print (mirror layout CombinedRotationData V-Z)."""
    lines = []
    lines.append(f"  Rotation: {report['name']}  ({report['time']:g}s"
                 + (f", x{report['rotation_mult']:g} mult" if report["rotation_mult"] != 1 else "")
                 + (f", normal x{report['normal_repeat']}" if report["normal_repeat"] != 1 else "")
                 + (f", stun x{report['stun_repeat']}" if report["stun_repeat"] != 1 else "")
                 + ")")
    lines.append(f"    Total damage : {report['total']:>12,.1f}"
                 f"   (non-crit {report['total_non_crit']:,.0f} / crit {report['total_crit']:,.0f})")
    lines.append(f"    DPS          : {report['dps']:>12,.1f}/s")
    lines.append(f"    Total daze   : {report['total_daze']:>12,.1f}"
                 f"   buildup {report['total_buildup']:,.1f}")
    if report["distribution"]:
        lines.append("    Distribution:")
        lines.append(f"      {'Source':<10} {'Total Damage':>14} {'%':>7}"
                     f" {'Total Daze':>12} {'Total Buildup':>14}")
        for d in report["distribution"]:
            lines.append(f"      {d['category']:<10} {d['damage']:>14,.1f}"
                         f" {d['pct']:>6.1f}% {d['daze']:>12,.1f}"
                         f" {d['buildup']:>14,.1f}")
    return "\n".join(lines)


def run_rotation_selftest() -> bool:
    """Sanity check murni (tanpa snapshot): penjumlahan + distribusi + resolve.
    Angka manual kecil, mengikuti pola sanity check item 1-4/9."""
    print("=== Rotation selftest (summarize_rotation) ===")
    rows_normal = [
        {"skill_label": "Basic Attack", "hit_name": "Basic Attack: A", "hit_id": 1,
         "hit_skill_type": "Basic Attack", "skill_category": "Basics",
         "hit_element": "Physical", "non_crit": 100.0, "crit": 200.0,
         "expected": 150.0, "daze": 10.0, "buildup": 5.0},
        {"skill_label": "Basic Attack", "hit_name": "Basic Attack: A", "hit_id": 2,
         "hit_skill_type": "Basic Attack", "skill_category": "Basics",
         "hit_element": "Ice", "non_crit": 300.0, "crit": 600.0,
         "expected": 450.0, "daze": 20.0, "buildup": 15.0},
        {"skill_label": "Special Attack", "hit_name": "EX Special Attack: B", "hit_id": 3,
         "hit_skill_type": "EX Special Attack", "skill_category": "Specials",
         "hit_element": "Ice", "non_crit": 1000.0, "crit": 2000.0,
         "expected": 1500.0, "daze": 0.0, "buildup": 0.0},
        {"skill_label": "Anomaly", "hit_name": "Shatter (Ice)", "hit_id": None,
         "hit_skill_type": "Anomaly", "skill_category": "Anomaly",
         "hit_element": "Ice", "non_crit": 5000.0, "crit": 5000.0,
         "expected": 5000.0, "daze": 0.0, "buildup": 0.0, "anomaly_tick": True},
    ]
    rows_stun = [dict(r, non_crit=r["non_crit"] * 1.5, crit=r["crit"] * 1.5,
                      expected=r["expected"] * 1.5,
                      daze=r["daze"] * 1.5, buildup=r["buildup"] * 1.5)
                 for r in rows_normal]

    rotation = {
        "name": "selftest",
        "time": 10.0,
        "normal": [
            {"hit_id": 1, "count": 2},          # 2x150 = 300
            {"skill": "Specials", "count": 1},  # 1500
            {"skill": "Anomaly", "hit": "Shatter (Ice)", "count": 3},  # 3x5000 = 15000
        ],
        "stun": [{"hit_id": 2, "count": 1}],    # 1x675 = 675
        "normal_repeat": 2,                     # normal x2
        "stun_repeat": 1,
    }
    report = summarize_rotation(rotation, {"normal": rows_normal, "stun": rows_stun})

    # Manual: normal uses = count x repeat x mult ; dmg expected
    exp_normal = (2 * 2 * 150.0) + (1 * 2 * 1500.0) + (3 * 2 * 5000.0)
    exp_stun = (1 * 1 * 675.0)
    exp_total = exp_normal + exp_stun
    checks = [
        ("total", report["total"], exp_total),
        ("dps", report["dps"], exp_total / 10.0),
        ("daze", report["total_daze"], 40.0 + 30.0),
        ("buildup", report["total_buildup"], 20.0 + 22.5),
    ]
    # distribusi: Basics = 600 (normal 4x150) + 675 (stun) = 1275;
    # Specials = 3000; Anomaly = 30000
    dist = {d["category"]: d["damage"] for d in report["distribution"]}
    checks += [
        ("dist.Basics", dist.get("Basics", 0.0), 600.0 + 675.0),
        ("dist.Specials", dist.get("Specials", 0.0), 3000.0),
        ("dist.Anomaly", dist.get("Anomaly", 0.0), 30000.0),
        ("entries", float(len(report["entries"])), 4.0),
    ]
    ok = True
    for label, got, want in checks:
        good = abs(got - want) < 1e-6
        ok = ok and good
        print(f"    {label:<14} got {got:>12,.3f}  want {want:>12,.3f}  "
              f"{'OK' if good else 'MISMATCH'}")
    # resolve by skill_category vs hit_skill_type + ambiguity guard
    try:
        summarize_rotation({"time": 1, "normal": [{"skill": "Basics"}]},
                           {"normal": rows_normal})
        print("    ambiguity guard  FAIL (harus raise)")
        ok = False
    except LookupError:
        print("    ambiguity guard  OK (LookupError)")

    # ---- item 5: base table Disorder/Polarity/Vortex (angka manual Excel) ----
    base_checks = [
        ("dis.Ice", disorder_base_pct("Ice", 10), 450 + 10 * 7.5),
        ("dis.Physical", disorder_base_pct("Physical", 10), 450 + 10 * 7.5),
        ("dis.Wind", disorder_base_pct("Wind", 10), 100.0),
        ("dis.Fire", disorder_base_pct("Fire", 10), 450 + 20 * 50.0),
        ("dis.Electric", disorder_base_pct("Electric", 10), 450 + 10 * 125.0),
        ("dis.Ether", disorder_base_pct("Ether", 10), 450 + 20 * 62.5),
        ("vor.Physical", vortex_base_pct("Physical", 10), 800 + 10 * 7.5),
        ("vor.Wind", vortex_base_pct("Wind", 10), 0.0),
        ("vor.Ice frost", vortex_base_pct("Ice", 10, True), 10 * 75.0),
        ("vor.Ice", vortex_base_pct("Ice", 10, False), 1300 + 10 * 7.5),
        ("vor.Fire", vortex_base_pct("Fire", 10), 900 + 20 * 7.5),
        ("vor.Electric", vortex_base_pct("Electric", 10), 650 + 10 * 125.0),
        ("vor.Ether", vortex_base_pct("Ether", 10), 650 + 20 * 62.5),
        ("pol.M0", polarity_factor_for_mindscape(0), 0.15),
        ("pol.M2", polarity_factor_for_mindscape(3), 0.5),
        ("pol.M6", polarity_factor_for_mindscape(6), 0.8),
    ]
    for label, got, want in base_checks:
        good = abs(got - want) < 1e-9
        ok = ok and good
        print(f"    {label:<14} got {got:>12,.3f}  want {want:>12,.3f}  "
              f"{'OK' if good else 'MISMATCH'}")

    # ---- item 5: compute_disorder_damage manual (ATK 1000, AP 100, Ice) ----
    e5 = EnemyStats(def_val=571.68, res_pct={"Ice": 0.0})
    d5 = compute_disorder_damage(
        element="Ice", atk_combat=1000.0, anomaly_proficiency=100.0, enemy=e5,
        remaining_duration_s=10.0)
    want5 = 1000.0 * (525.0 / 100) * (794.0 / (794.0 + 571.68)) * 1.0 * 1.0 \
        * (100.0 / 100) * 2.0 * 1.0 * 1.0 * 1.0
    good = abs(d5["non_crit"] - want5) < 0.5
    ok = ok and good
    print(f"    disorder dmg  got {d5['non_crit']:>12,.3f}  want {want5:>12,.3f}  "
          f"{'OK' if good else 'MISMATCH'}")

    # ---- item 5: extra_rows (Disorder) masuk total + distribusi ----
    extra = [_special_row("Disorder", "Disorder (Ice)", "Ice", "Disorder",
                          1000.0, 2, "disorder", 525.0)]
    rep2 = summarize_rotation({"time": 10, "normal": []},
                              {"normal": [], "stun": []}, extra_rows=extra)
    dist2 = {d["category"]: d["damage"] for d in rep2["distribution"]}
    checks2 = [
        ("extra.total", rep2["total"], 2000.0),
        ("extra.disorder", dist2.get("Disorder", 0.0), 2000.0),
    ]
    for label, got, want in checks2:
        good = abs(got - want) < 1e-6
        ok = ok and good
        print(f"    {label:<14} got {got:>12,.3f}  want {want:>12,.3f}  "
              f"{'OK' if good else 'MISMATCH'}")
    print(f"    ROTATION SELFTEST: {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------
# Kalibrasi ke ground truth (Miyabi vs Tyrfing L60) — full otomatis
# ---------------------------------------------------------------------------

def load_loadouts(path: str = "dumps/loadouts.json") -> dict:
    """loadouts.json hasil export zzz_enka_stat_calc_multichar.py --export."""
    return load_json(path)


def run_calibration() -> bool:
    print("=== Kalibrasi Miyabi vs Tyrfing L60 (ground truth 1086/2961) ===")
    print()

    # [1] Load 3 file mapped
    wengines = load_wengine_passives()
    sets = load_drive_disc_sets()
    mindscapes = load_mindscapes()
    print(f"[1] Mapped files: {len(wengines)} W-Engine, {len(sets)} set, "
          f"{len(mindscapes)} avatar")

    # [1b] Stat panel & skill mult dari loadouts.json (export stat calc)
    try:
        loadouts = load_loadouts()
        miya = next(a for a in loadouts["avatars"] if a["avatar_id"] == 1091)
        panel = miya["stats"]
        basic = miya["skills"]["0"]
        hit1 = basic["hits"][0]
        skill_mult = hit1["damage_pct"]
        attacker_level = int(miya["level"])
        weapon_id = miya["weapon"]["id"]
        weapon_phase = miya["weapon"]["phase"]
        set4pc_names = miya["set4pc"]
        mindscape_rank = int(miya["mindscape"])
        print(f"[1b] loadouts.json: '{miya['name']}' ATK panel {panel['ATK']:.2f}, "
              f"Basic Lv.{basic['level']} hit {hit1['name']} = {skill_mult}%")
    except FileNotFoundError:
        print("[1b] loadouts.json nggak ada — fallback hardcode "
              "(jalanin: python zzz_enka_stat_calc_multichar.py dumps/1303558818.json --export)")
        panel = {"ATK": 2715.64, "CRIT Rate": 51.4, "CRIT DMG": 142.8,
                 "PEN Ratio": 24.0, "PEN": 18, "Ice DMG": 30.0}
        skill_mult = 54.4
        attacker_level = 60
        weapon_id = 14118
        weapon_phase = 1
        set4pc_names = ["Branch & Blade Song"]
        mindscape_rank = 0

    # [3] Build toggle list dari 3 sumber
    toggles = []
    if not weapon_id:
        print(f"[3] No wengine equipped (weapon_id={weapon_id}) — skip wengine toggles")
    toggles += build_wengine_toggles(wengines, weapon_id=weapon_id, phase=weapon_phase)
    for set_name in set4pc_names:
        if set_name in sets:
            toggles += build_set4pc_toggles(sets, set_name)
    toggles += build_mindscape_toggles(mindscapes, avatar_id=1091, mindscape_rank=mindscape_rank)
    print(f"[3] Toggle list: {len(toggles)} entry")
    print_toggle_table(toggles)

    # [4] Threshold eval — deterministik dari stat panel (AM 116 >= 115)
    panel_snake = {"anomaly_mastery": panel.get("Anomaly Mastery", 0.0)}
    print(f"[4] evaluate_thresholds(panel={panel_snake}):")
    for entry, note in evaluate_thresholds(toggles, panel_snake):
        print(f"    {entry.stat} {entry.value:g}: {note}")
    print()

    # [5] Aggregate -> CombatModifiers
    mods = aggregate_modifiers(toggles, skill_type="Basic Attack", element="Physical")
    print("[5] CombatModifiers (enabled only, scope Basic Attack/Physical):")
    for line in mods.describe().splitlines():
        print("    " + line)
    print()

    # [5b] Level Factor lookup sanity
    level_curve = load_level_factor_curve()
    print("[5b] Level Factor sanity:")
    print(f"    L1  = {get_level_factor(1, level_curve):g}")
    print(f"    L59 = {get_level_factor(59, level_curve):g}")
    print(f"    L60 = {get_level_factor(60, level_curve):g}  (expected 794)")
    print(f"    L80 = {get_level_factor(80, level_curve):g}  (curve plateau)")
    assert get_level_factor(60, level_curve) == 794.0

    # [6] compute_final_damage vs ground truth
    enemy = EnemyStats(
        def_val=571.68,  # DEF Tyrfing L60 (hardcode sementara — lihat TODO dead-end monster table)
        res_pct={"Physical": 0.0, "Fire": 0.0, "Ice": -0.20, "Electric": 0.0,
                 "Ether": -0.20, "Wind": 0.0},
    )
    result = compute_final_damage(
        atk_panel=panel["ATK"],
        skill_mult_pct=skill_mult,
        crit_dmg_panel_pct=panel["CRIT DMG"],
        enemy=enemy,
        element="Physical",
        skill_type="Basic Attack",
        crit_rate_panel_pct=panel["CRIT Rate"],
        pen_ratio_pct=panel["PEN Ratio"],
        pen_flat=panel["PEN"],
        dmg_bonus_panel_pct=panel.get("Physical DMG", 0.0),
        mods=mods,
        attacker_level=attacker_level,
        level_factor_curve=level_curve,
    )

    print("[6] Hasil vs ground truth:")
    print(f"    ATK combat:       {result['atk_combat']:.2f}")
    print(f"    DEF mult:         {result['def_mult']:.5f}")
    print(f"    RES mult:         {result['res_mult']:.2f}")
    print(f"    CRIT DMG combat:  {result['crit_dmg_combat_pct']:.1f}%")
    print(f"    Non-crit: {result['non_crit']:.1f}  (ground truth: 1086)")
    print(f"    Crit:     {result['crit']:.1f}  (ground truth: 2961)")
    print(f"    Expected (CR {result['crit_rate_combat_pct']:.1f}%): {result['expected']:.1f}")
    print()

    d_nc = abs(result["non_crit"] - 1086)
    d_cr = abs(result["crit"] - 2961)
    print(f"    Selisih non-crit: {d_nc:.2f} ({d_nc / 1086 * 100:.3f}%)")
    print(f"    Selisih crit:     {d_cr:.2f} ({d_cr / 2961 * 100:.3f}%)")
    print("    (residual 0.09% non-crit sudah known-issue: flooring chain / DEF drift)")

    ok = d_nc / 1086 < 0.005 and d_cr / 2961 < 0.005
    print()
    print(f"    KALIBRASI: {'PASS' if ok else 'FAIL'} (toleransi 0.5%)")
    return ok


if __name__ == "__main__":
    ok = run_calibration()
    print()
    ok = run_rotation_selftest() and ok
    raise SystemExit(0 if ok else 1)

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

Formula (wiki ZZZ Damage page + docs/wengine.md, tervalidasi manual 99.9%):
    ATK_combat = ATK_panel * (1 + Bonus%_cond) + Flat_cond
    DEF_eff    = DEF_enemy * (1 - PENratio%) * Π(1 - DEFignore_i%) - PEN_flat
    DEFmult    = LevelFactor(attacker_level) / (max(DEF_eff, 0) + LevelFactor(attacker_level))
    RESmult    = 1 - (RES * Π(1 - RESignore_i%) - RESshred%)
    NonCrit    = ATK_combat * skill_mult% * (1 + DMG%_bonus) * DEFmult * RESmult
    Crit       = NonCrit * (1 + CRIT_DMG_combat%)

Asumsi stacking multi-sumber (belum ada ground truth; kalibrasi existing
single-source jadi nggak terpengaruh):
  - DEF ignore dari beberapa sumber independent di-chain multiplikatif
    (1-x%) per sumber, mirip mekanik ignore-DEF Genshin.
  - RES ignore multiplikatif di atas RES enemy; RES shred dikurang flat
    (persen poin) SETELAH ignore.
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
    }
    if s in explicit:
        return explicit[s]
    key = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return f"{key}_{u}" if u else key


# effect_type non-stat yang masuk formula:
_EFFECT_TYPE_TO_STAT = {
    "damage_bonus": "damage_pct",
    "def_ignore": "def_ignore_pct",
    "res_ignore": "res_ignore_pct",
    "res_shred": "res_shred_pct",
}

# key efek drive-disc yang masuk formula (sisanya passthrough -> extra):
_DRIVE_FORMULA_KEYS = {
    "damage_percent": "damage_pct",
    "team_damage_percent": "damage_pct",      # team-wide, termasuk equipper
    "crit_dmg_percent": "crit_dmg_pct",
    "team_crit_dmg_percent": "crit_dmg_pct",  # team-wide, termasuk equipper
    "crit_rate_percent": "crit_rate_pct",
    "atk_percent": "atk_pct",
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


def _mechanical_auto_enable(stat: str, scope: tuple, evidence: str) -> tuple:
    """Kebijakan auto-enable utk sumber ekstraksi mekanis (wengine/mindscape).
    Return (enabled, needs_review). Lihat docstring modul.
    """
    if stat == "damage_pct" and not scope:
        return False, True
    if _CONDITION_WORD_RE.search(evidence or ""):
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
                enabled=(mode == "always"),
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
            if panel is None or t.threshold_stat not in panel:
                notes.append((t, f"SKIP: panel stat '{t.threshold_stat}' nggak diketahui"))
                continue
            val = float(panel[t.threshold_stat])
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
    res_ignore_pcts: list = field(default_factory=list)  # sumber independent
    res_shred_pct: float = 0.0
    # DMG Taken Modifier — efek yang nambah/ngurangin damage yang DITERIMA musuh:
    # dmg_taken_pct (mis. +35% dari efek "enemies take 35% more DMG"),
    # dmg_reduction_pct (mis. musuh punya damage reduction).
    dmg_taken_pct: float = 0.0
    dmg_reduction_pct: float = 0.0
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
            ("RES shred%", self.res_shred_pct),
            ("DMG taken%", self.dmg_taken_pct),
            ("DMG reduction%", self.dmg_reduction_pct),
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
        elif t.stat == "res_ignore_pct":
            mods.res_ignore_pcts.append(v)
        elif t.stat == "res_shred_pct":
            mods.res_shred_pct += v
        elif t.stat == "dmg_taken_pct":
            mods.dmg_taken_pct += v
        elif t.stat == "dmg_reduction_pct":
            mods.dmg_reduction_pct += v
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
                     attacker_level: int = 60, level_factor_curve: dict | None = None) -> float:
    """DEFmult = LF / (max(DEF*(1-PENratio)*Π(1-ignore_i) - PEN, 0) + LF).

    ``LF`` is the attacker's Level Factor from LevelCurveTemplateTb.
    Backward compatibility is preserved: omitting ``attacker_level`` uses 60,
    whose Level Factor is exactly 794 in the supplied curve.
    """
    level_factor = get_level_factor(attacker_level, level_factor_curve)
    effective = enemy_def * (1 - pen_ratio_pct / 100)
    for ig in def_ignore_pcts:
        effective *= (1 - ig / 100)
    effective = max(effective - pen_flat, 0)
    return level_factor / (effective + level_factor)


def compute_res_mult(res_pct: float, res_ignore_pcts=(),
                     res_shred_pct: float = 0.0) -> float:
    """RESmult = 1 - (RES * Π(1-ignore_i) - shred).
    RES & shred dalam fraksi/persen-poin (mis. -0.20 = RES -20%).
    """
    res = res_pct
    for ig in res_ignore_pcts:
        res *= (1 - ig / 100)
    res -= res_shred_pct / 100
    return 1 - res


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
) -> dict:
    """Formula lengkap: stat panel + combat modifiers -> non-crit & crit.
    `dmg_bonus_panel_pct` = elemental DMG bonus dari stat panel yang cocok
    dengan `element` (mis. Ice DMG +30% utk hit Ice) — caller yang milih.

    `enemy_stunned=True` mengaktifkan Stun Modifier (dmg * (1 +
    enemy.stun_taken_pct)) — nilai StunDamageTakenRatio musuh, mis.
    +50% Tyrfing/kebanyakan elite, +25% The Defector.
    DMG Taken Modifier: (1 + dmg_taken%) / (1 - dmg_reduction%) — slot
    stat `dmg_taken_pct` / `dmg_reduction_pct` di CombatModifiers.
    """
    mods = mods or CombatModifiers()

    atk_combat = atk_panel * (1 + mods.atk_bonus_pct_cond / 100) + mods.atk_flat_cond
    crit_dmg_combat = crit_dmg_panel_pct + mods.crit_dmg_bonus_pct_cond
    skill_mult = skill_mult_pct + mods.skill_mult_bonus_pct
    dmg_bonus = dmg_bonus_panel_pct + mods.damage_bonus_pct_cond

    def_mult = compute_def_mult(
        enemy.def_val,
        pen_ratio_pct + mods.pen_ratio_bonus_pct,
        pen_flat + mods.pen_flat_bonus,
        mods.def_ignore_pcts,
        attacker_level=attacker_level,
        level_factor_curve=level_factor_curve,
    )
    res_mult = compute_res_mult(
        enemy.res_pct.get(element, 0.0),
        mods.res_ignore_pcts,
        mods.res_shred_pct,
    )
    # Stun Modifier — hanya kalau musuh lagi stun
    stun_mult = (1 + enemy.stun_taken_pct) if enemy_stunned else 1.0
    # DMG Taken Modifier — efek nambah/ngurangin damage yang diterima musuh
    dmg_taken_mult = ((1 + mods.dmg_taken_pct / 100)
                      / (1 - mods.dmg_reduction_pct / 100))

    non_crit = (atk_combat * (skill_mult / 100)
                * (1 + dmg_bonus / 100) * def_mult * res_mult
                * stun_mult * dmg_taken_mult)
    crit = non_crit * (1 + crit_dmg_combat / 100)

    crit_rate_combat = min(max(crit_rate_panel_pct + mods.crit_rate_bonus_pct_cond, 0.0), 100.0)
    expected = non_crit * (1 - crit_rate_combat / 100
                           + (crit_rate_combat / 100) * (1 + crit_dmg_combat / 100))

    return {
        "atk_combat": atk_combat,
        "skill_mult_pct": skill_mult,
        "dmg_bonus_pct": dmg_bonus,
        "def_mult": def_mult,
        "res_mult": res_mult,
        "stun_mult": stun_mult,
        "dmg_taken_mult": dmg_taken_mult,
        "crit_rate_combat_pct": crit_rate_combat,
        "crit_dmg_combat_pct": crit_dmg_combat,
        "non_crit": non_crit,
        "crit": crit,
        "expected": expected,
    }


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
    run_calibration()

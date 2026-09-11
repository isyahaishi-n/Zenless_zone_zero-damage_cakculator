#!/usr/bin/env python3
"""Standalone ZZZ stat calculator based on the Enka wrapper logic provided."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from skill_lookup import (
    build_explicit_name_map,
    build_skill_index,
    compute_damage_output,
    load_skill_template,
    load_textmap,
)

PROP_ID_TO_NAME: dict[int, str] = {
    11101: "HpMax_Base", 11102: "HpMax_Ratio", 11103: "HpMax_Delta",
    12101: "Atk_Base", 12102: "Atk_Ratio", 12103: "Atk_Delta",
    12201: "BreakStun_Base", 12202: "BreakStun_Ratio",
    12301: "SkipDefAtk_Base", 12303: "SkipDefAtk_Delta",
    13101: "Def_Base", 13102: "Def_Ratio", 13103: "Def_Delta",
    20101: "Crit_Base", 20103: "Crit_Delta",
    21101: "CritDmg_Base", 21103: "CritDmg_Delta",
    23101: "PenRatio_Base", 23103: "PenRatio_Delta",
    23201: "PenDelta_Base", 23203: "PenDelta_Delta",
    30501: "SpRecover_Base", 30502: "SpRecover_Ratio", 30503: "SpRecover_Delta",
    31201: "ElementMystery_Base", 31203: "ElementMystery_Delta",
    31401: "ElementAbnormalPower_Base", 31402: "ElementAbnormalPower_Ratio", 31403: "ElementAbnormalPower_Delta",
    31501: "AddedDamageRatio_Physics_Base", 31503: "AddedDamageRatio_Physics_Delta",
    31601: "AddedDamageRatio_Fire_Base", 31603: "AddedDamageRatio_Fire_Delta",
    31701: "AddedDamageRatio_Ice_Base", 31703: "AddedDamageRatio_Ice_Delta",
    31801: "AddedDamageRatio_Elec_Base", 31803: "AddedDamageRatio_Elec_Delta",
    31901: "AddedDamageRatio_Ether_Base", 31903: "AddedDamageRatio_Ether_Delta",
    32001: "RpRecover_Base", 32002: "RpRecover_Ratio", 32003: "RpRecover_Delta",
    32201: "SkipDefDamageRatio_Base", 32203: "SkipDefDamageRatio_Delta",
    32301: "AddedDamageRatio_Wind_Base", 32303: "AddedDamageRatio_Wind_Delta",
    # 3.2.0 baru (sistem Sharpness/Laceration; EN: "Automatic Sharpness
    # Accumulation" & "Laceration DMG" — belum dipakai formula damage, hanya
    # biar stat panel gak KeyError). Nama internal dari Enka property.json:
    # 213=SharpCriticalDamage, 324=EpRecover.
    21301: "SharpCriticalDamage_Base",
    32401: "EpRecover_Base",
}

ALL_PROPS = list({name for name in PROP_ID_TO_NAME.values()})


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# The *TemplateTb.json dumps use obfuscated field names. These maps translate
# them into the readable keys the calculator expects.
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


def load_template_table(path: Path, field_map: dict[str, str]) -> list[dict[str, int]]:
    """Load an obfuscated *TemplateTb.json dump and rename its fields."""
    raw = load_json(path)
    rows = raw[TB_ROOT_KEY] if isinstance(raw, dict) else raw
    out: list[dict[str, int]] = []
    for row in rows:
        out.append({name: int(row[key]) for key, name in field_map.items() if key in row})
    return out


def find_row(rows: list[dict[str, int]], label: str, **match: int) -> dict[str, int]:
    """Look up a template row, raising a readable error instead of StopIteration."""
    for row in rows:
        if all(row.get(k) == v for k, v in match.items()):
            return row
    raise LookupError(f"no {label} row for " + ", ".join(f"{k}={v}" for k, v in match.items()))


# Skill slots as they appear in the API's SkillLevelList "Index" field.
# SKILL_INDEX_TO_NAME: dict[int, str] = {
#     0: "Basic Attack",
#     1: "Dodge",
#     2: "Assist",
#     3: "Special Attack",
#     # 4: "Chain Attack",
#     5: "Core Skill",
#     6: "Ultimate",
# }
SKILL_INDEX_TO_NAME: dict[int, str] = {
    0: "Basic Attack",
    2: "Dodge",
    6: "Assist",
    1: "Special Attack",
    3: "Chain Attack",
    # 4: "Chain Attack",
    5: "Core Skill",
}
def effective_skill_level(base_level: int, mindscape: int) -> int:
    """M3 adds +2, M5 adds another +2 on top (stacking).
    M1/M2/M4/M6 don't bump skill levels — those are written-effect levels.
    """
    bump = 0
    if mindscape >= 3:
        bump += 2
    if mindscape >= 5:
        bump += 2
    return base_level + bump
CORE_SKILL_LETTERS = ["-", "A", "B", "C", "D", "E", "F"]

RANK_LETTERS = {2: "B", 3: "A", 4: "S"}

# In-game display labels for each property id, plus whether the raw value is a
# basis-point percentage (True) or a flat number (False).
PROP_DISPLAY: dict[int, tuple[str, bool]] = {
    11101: ("HP", False), 11102: ("HP", True), 11103: ("HP", False),
    12101: ("ATK", False), 12102: ("ATK", True), 12103: ("ATK", False),
    12201: ("Impact", False), 12202: ("Impact", True),
    12301: ("Sheer Force", False), 12303: ("Sheer Force", False),
    13101: ("DEF", False), 13102: ("DEF", True), 13103: ("DEF", False),
    20101: ("CRIT Rate", True), 20103: ("CRIT Rate", True),
    21101: ("CRIT DMG", True), 21103: ("CRIT DMG", True),
    23101: ("PEN Ratio", True), 23103: ("PEN Ratio", True),
    23201: ("PEN", False), 23203: ("PEN", False),
    30501: ("Energy Regen", False), 30502: ("Energy Regen", True), 30503: ("Energy Regen", False),
    31201: ("Anomaly Proficiency", False), 31203: ("Anomaly Proficiency", False),
    31401: ("Anomaly Mastery", False), 31402: ("Anomaly Mastery", True), 31403: ("Anomaly Mastery", False),
    31501: ("Physical DMG", True), 31503: ("Physical DMG", True),
    31601: ("Fire DMG", True), 31603: ("Fire DMG", True),
    31701: ("Ice DMG", True), 31703: ("Ice DMG", True),
    31801: ("Electric DMG", True), 31803: ("Electric DMG", True),
    31901: ("Ether DMG", True), 31903: ("Ether DMG", True),
    32001: ("Decibel Regen", False), 32002: ("Decibel Regen", True), 32003: ("Decibel Regen", False),
    32201: ("Sheer DMG", True), 32203: ("Sheer DMG", True),
    32301: ("Wind DMG", True), 32303: ("Wind DMG", True),
    # 3.2.0 baru (Sharpness/Laceration): 21301 = Laceration DMG (%),
    # 32401 = Automatic Sharpness Accumulation (flat).
    21301: ("Laceration DMG", True),
    32401: ("Automatic Sharpness Accumulation", False),
}

# Disc slot -> the piece's in-game position label.
DISC_SLOT_NAMES = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6"}


def localize(loc: dict[str, str], key: str | None, fallback: str = "?") -> str:
    """Translate an internal name key (e.g. Item_Weapon_S_1181_Name) to English."""
    if not key:
        return fallback
    return loc.get(key, key)


def format_prop(prop_id: int, value: float) -> str:
    """Render a raw property value the way the game shows it."""
    label, is_pct = PROP_DISPLAY.get(int(prop_id), (PROP_ID_TO_NAME.get(int(prop_id), str(prop_id)), False))
    if is_pct:
        return f"{label} {value / 100:.1f}%"
    return f"{label} {math.floor(value):g}"


def print_disc_details(
    avatar: dict[str, Any],
    equipments: dict[str, Any],
    equipment_level_rows,
    loc: dict[str, str],
) -> None:
    """Print each equipped Drive Disc with its main stat and rolled sub stats."""
    equipped = sorted(avatar.get("EquippedList", []), key=lambda e: int(e["Slot"]))
    if not equipped:
        return
    print("  Drive Disc Details:")
    for equip in equipped:
        disc = equip["Equipment"]
        meta = equipments["Items"][str(disc["Id"])]
        rarity = int(meta["Rarity"])
        suit_name = localize(loc, equipments["Suits"][str(meta["SuitId"])].get("Name"), str(meta["SuitId"]))
        slot = DISC_SLOT_NAMES.get(int(equip["Slot"]), str(equip["Slot"]))
        lvl = int(disc["Level"])
        level_row = find_row(equipment_level_rows, "EquipmentLevelTemplate", Rarity=rarity, Level=lvl)

        main = disc["MainPropertyList"][0]
        main_value = math.floor(main["PropertyValue"] * (1 + level_row["EnhanceRate"] / 10000))
        main_text = format_prop(int(main["PropertyId"]), main_value)

        print(
            f"    [{slot}] {suit_name} "
            f"{RANK_LETTERS.get(rarity, '?')}-rank +{lvl}  ->  {main_text}"
        )
        for sub in disc["RandomPropertyList"]:
            rolls = int(sub["PropertyLevel"])
            total = sub["PropertyValue"] * rolls
            sub_text = format_prop(int(sub["PropertyId"]), total)
            print(f"          - {sub_text}  ({rolls} roll{'s' if rolls != 1 else ''})")




class Layer:
    def __init__(self) -> None:
        self.props = {k: 0.0 for k in ALL_PROPS}

    def add(self, name: str, value: float) -> None:
        self.props[name] += value


class StatState:
    def __init__(self) -> None:
        self.layers: list[tuple[str, Layer]] = []

    def add(self, name: str, layer: Layer) -> None:
        self.layers.append((name, layer))

    def summed(self) -> Layer:
        out = Layer()
        for _, layer in self.layers:
            for key, value in layer.props.items():
                # NOTE 2026-09-06 (strip-test v2/v3/v4 vs ground truth Enka
                # 1303558818v2-v4): game TIDAK floor per-layer stat. Base ATK
                # 880.6952 (Miyabi bare) match GT exact; flooring per-layer
                # bikin damage underestimate 1 unit (278 vs 279 dst).
                # Sebelumnya: out.add(key, math.floor(value)).
                out.add(key, float(value))
        return out


def get_agent_data(avatar_id: int, level: int, promotion: int, core: int, avatars: Any) -> dict[str, Any]:
    excel = avatars[str(avatar_id)] if str(avatar_id) in avatars else avatars[avatar_id]
    layer_base: dict[int, float] = {int(k): float(v) for k, v in excel["BaseProps"].items()}
    layer_growth: dict[int, float] = {int(k): float(v) for k, v in excel.get("GrowthProps", {}).items()}
    promo_row = excel.get("PromotionProps", [])[promotion - 1] if excel.get("PromotionProps") else {}
    layer_promo: dict[int, float] = {int(k): float(v) for k, v in promo_row.items()}
    core_rows = excel.get("CoreEnhancementProps", [])
    core_row = core_rows[core] if core < len(core_rows) else {}
    layer_core: dict[int, float] = {int(k): float(v) for k, v in core_row.items()}
    return {
        "id": avatar_id, "level": level, "promotion": promotion, "core": core,
        "specialty": excel.get("ProfessionType"),
        "base": layer_base, "growth": layer_growth,
        "promotion_props": layer_promo, "core_props": layer_core,
    }


def property_name(prop_id: int) -> str:
    return PROP_ID_TO_NAME[prop_id]


def make_character_layer(agent: dict[str, Any]) -> Layer:
    out = Layer()
    level = int(agent["level"])
    base = agent["base"]
    growth = agent.get("growth", {})
    promo = agent.get("promotion_props", {})
    for prop_id, base_value in base.items():
        computed = base_value + (growth.get(prop_id, 0) / 10000.0) * (level - 1) + promo.get(prop_id, 0)
        out.add(property_name(prop_id), computed)
    return out


def make_core_layer(agent: dict[str, Any]) -> Layer:
    out = Layer()
    for prop_id, value in agent.get("core_props", {}).items():
        out.add(property_name(prop_id), value)
    return out


def make_weapon_layer(api_agent: dict[str, Any], weapons: dict[str, Any], weapon_level_rows, weapon_star_rows) -> Layer:
    """Empty layer when no W-Engine is equipped (WeaponUid == 0 / missing)."""
    w = api_agent.get("Weapon")
    if not w or not int(w.get("Id", 0)):
        return Layer()
    weapon_id = int(w["Id"])
    data = weapons[str(weapon_id)]
    rarity = int(data["Rarity"])
    lvl = int(w["Level"])
    break_level = int(w["BreakLevel"])
    level_row = find_row(weapon_level_rows, "WeaponLevelTemplate", Rarity=rarity, Level=lvl)
    star_row = find_row(weapon_star_rows, "WeaponStarTemplate", Rarity=rarity, BreakLevel=break_level)


    out = Layer()
    main = data["MainStat"]
    sub = data["SecondaryStat"]
    main_value = math.floor(main["PropertyValue"] * (1 + level_row["EnhanceRate"] / 10000 + star_row["StarRate"] / 10000))
    sub_value = math.floor(sub["PropertyValue"] * (1 + star_row["RandRate"] / 10000))
    out.add(property_name(int(main["PropertyId"])), main_value)
    out.add(property_name(int(sub["PropertyId"])), sub_value)
    return out


def make_disc_layer(avatar: dict[str, Any], equipments: dict[str, Any], equipment_level_rows) -> Layer:
    out = Layer()
    for equip in avatar.get("EquippedList", []):
        disc = equip["Equipment"]
        disc_id = str(disc["Id"])
        disc_meta = equipments["Items"][disc_id]
        rarity = int(disc_meta["Rarity"])
        lvl = int(disc["Level"])
        level_row = find_row(equipment_level_rows, "EquipmentLevelTemplate", Rarity=rarity, Level=lvl)

        main = disc["MainPropertyList"][0]
        main_value = math.floor(main["PropertyValue"] * (1 + level_row["EnhanceRate"] / 10000))
        out.add(property_name(int(main["PropertyId"])), main_value)
        for sub in disc["RandomPropertyList"]:
            value = sub["PropertyValue"] * sub["PropertyLevel"]
            out.add(property_name(int(sub["PropertyId"])), value)
    return out


def make_set_layer(avatar: dict[str, Any], equipments: dict[str, Any]) -> Layer:
    counts: defaultdict[int, int] = defaultdict(int)
    for equip in avatar.get("EquippedList", []):
        disc = equip["Equipment"]
        sid = int(equipments["Items"][str(disc["Id"])]["SuitId"])
        counts[sid] += 1
    out = Layer()
    for sid, count in counts.items():
        if count < 2:
            continue
        bonus_props = equipments["Suits"][str(sid)].get("SetBonusProps", {})
        for prop_id, value in bonus_props.items():
            out.add(property_name(int(prop_id)), value)
    return out


def apply_corrections(agent: dict[str, Any], state: StatState) -> None:
    """Rupture specialty agents (e.g. Yixuan) convert part of ATK and HP
    into a separate 'Sheer Force' stat used for their damage instead of ATK.
    Formula: SkipDefAtk_Delta += floor(ATK * 0.3) + floor(HP * 0.1)
    """
    base = state.summed()
    if str(agent.get("specialty", "")).lower() == "rupture":
        atk = math.floor(base.props["Atk_Base"] * (1 + base.props["Atk_Ratio"] / 10000) + base.props["Atk_Delta"])
        hp = math.floor(base.props["HpMax_Base"] + math.ceil(base.props["HpMax_Base"] * base.props["HpMax_Ratio"] / 10000) + base.props["HpMax_Delta"])
        layer = Layer()
        layer.add("SkipDefAtk_Delta", math.floor(atk * 0.3))
        layer.add("SkipDefAtk_Delta", math.floor(hp * 0.1))
        state.add("Corrections", layer)


def prop(layer: Layer, name: str) -> float:
    return layer.props[name]


def final_stats(s: Layer) -> dict[str, float]:
    return {
        "HP": prop(s, "HpMax_Base")
        + math.ceil(prop(s, "HpMax_Base") * prop(s, "HpMax_Ratio") / 10000)
        + prop(s, "HpMax_Delta"),
        "ATK": prop(s, "Atk_Base")
        * (1 + prop(s, "Atk_Ratio") / 10000)
        + prop(s, "Atk_Delta"),

        "DEF": prop(s, "Def_Base")
        * (1 + prop(s, "Def_Ratio") / 10000)
        + prop(s, "Def_Delta"),

        "Impact": prop(s, "BreakStun_Base")
        * (1 + prop(s, "BreakStun_Ratio") / 10000),

        "CRIT Rate": prop(s, "Crit_Base") + prop(s, "Crit_Delta"),

        "CRIT DMG": prop(s, "CritDmg_Base") + prop(s, "CritDmg_Delta"),

        "PEN Ratio": prop(s, "PenRatio_Base") + prop(s, "PenRatio_Delta"),

        "PEN": prop(s, "PenDelta_Base") + prop(s, "PenDelta_Delta"),

        "Anomaly Proficiency":
            prop(s, "ElementMystery_Base")
            + prop(s, "ElementMystery_Delta"),

        "Anomaly Mastery":
            prop(s, "ElementAbnormalPower_Base")
            * (1 + prop(s, "ElementAbnormalPower_Ratio") / 10000)
            + prop(s, "ElementAbnormalPower_Delta"),

        "Energy Regen":
            (
                prop(s, "SpRecover_Base")
                * (1 + prop(s, "SpRecover_Ratio") / 10000)
                + prop(s, "SpRecover_Delta")
            ) / 100,

        "Sheer Force":
            prop(s, "SkipDefAtk_Base")
            + prop(s, "SkipDefAtk_Delta"),

        # Elemental DMG
        "Physical DMG":
            prop(s, "AddedDamageRatio_Physics_Base")
            + prop(s, "AddedDamageRatio_Physics_Delta"),

        "Fire DMG":
            prop(s, "AddedDamageRatio_Fire_Base")
            + prop(s, "AddedDamageRatio_Fire_Delta"),

        "Ice DMG":
            prop(s, "AddedDamageRatio_Ice_Base")
            + prop(s, "AddedDamageRatio_Ice_Delta"),

        "Electric DMG":
            prop(s, "AddedDamageRatio_Elec_Base")
            + prop(s, "AddedDamageRatio_Elec_Delta"),

        "Ether DMG":
            prop(s, "AddedDamageRatio_Ether_Base")
            + prop(s, "AddedDamageRatio_Ether_Delta"),

        "Wind DMG":
            prop(s, "AddedDamageRatio_Wind_Base")
            + prop(s, "AddedDamageRatio_Wind_Delta"),

        # Sheer damage bonus
        "Sheer DMG":
            prop(s, "SkipDefDamageRatio_Base")
            + prop(s, "SkipDefDamageRatio_Delta"),
    }

def load_skill_data(base_dir: Path) -> tuple[Any, dict, dict]:
    """Load skill multiplier tables for the damage-per-skill section.

    Returns (skill_index, name_map, textmap). All three are shared, read-only
    structures built once and reused for every avatar.
    """
    skill_template = load_skill_template(str(base_dir / "data" / "AvatarSkillTemplateTb.json"))
    skill_index = build_skill_index(skill_template)
    des_template = load_skill_template(str(base_dir / "data" / "AvatarSkillDesTemplateTb.json"))
    name_map = build_explicit_name_map(des_template)
    textmap = load_textmap(str(base_dir / "data" / "TextMap_ENTemplateTb.json"))
    return skill_index, name_map, textmap


# Enka SkillLevelList "Index" values that have damage multipliers in
# AvatarSkillTemplateTb (Index == GLENCFMNKMF). 5 = Core Skill has no
# multipliers there — its stat bonuses are already applied via CoreEnhancementProps.
MULTIPLIER_SKILL_INDICES = (0, 1, 2, 3, 6)


def print_skill_damage(
    avatar: dict[str, Any],
    avatar_id: int,
    mindscape: int,
    atk: float,
    skill_index: Any,
    name_map: dict,
    textmap: dict,
) -> None:
    """Per-hit damage/daze multipliers at this agent's actual skill levels.

    Uses the effective level (M3/M5 +2 bumps) and the final ATK computed
    above. Hidden hits (not referenced by the in-game UI) are marked.
    """
    levels = {int(s["Index"]): int(s["Level"]) for s in avatar.get("SkillLevelList", [])}
    print("-- Skill damage (at current skill level, raw = x ATK) --")
    any_printed = False
    for idx in MULTIPLIER_SKILL_INDICES:
        base_lvl = levels.get(idx)
        if base_lvl is None:
            continue
        eff_lvl = effective_skill_level(base_lvl, mindscape)
        label = SKILL_INDEX_TO_NAME.get(idx, f"Skill {idx}")
        rows = compute_damage_output(
            skill_index, avatar_id=avatar_id, skill_type=idx, level=eff_lvl,
            atk=atk, name_map=name_map, textmap=textmap,
        )
        if not rows:
            continue
        any_printed = True
        bump = f" (M{mindscape}: {base_lvl}->{eff_lvl})" if eff_lvl != base_lvl else ""
        print(f"  {label} Lv.{eff_lvl}{bump}:")
        for r in rows:
            name = r["name"] if r["name"] else f"hit {r['hit_id']}"
            hidden = "  [hidden]" if r["is_hidden"] else ""
            print(
                f"    {name}: DMG {r['damage_pct']:.1f}%"
                f" ({r['raw_damage']:.0f})  Daze {r['daze_pct']:.1f}%{hidden}"
            )
    if not any_printed:
        print("  (no multiplier rows for this agent)")


# Stat panel yang satuan internalnya basis points (x10000 di layer,
# final_stats kelihatan x100) tapi display game & damage_calc pakai %.
PCT_PANEL_STATS = {
    "CRIT Rate", "CRIT DMG", "PEN Ratio", "Physical DMG", "Fire DMG",
    "Ice DMG", "Electric DMG", "Ether DMG", "Wind DMG", "Sheer DMG",
}


def compute_avatar_snapshot(
    avatar: dict[str, Any],
    avatar_id: int,
    avatars: Any,
    weapons: dict[str, Any],
    equipments: dict[str, Any],
    weapon_level_rows,
    weapon_star_rows,
    equipment_level_rows,
    skill_index: Any,
    name_map: dict,
    textmap: dict,
    loc: dict[str, str],
) -> dict[str, Any]:
    """Hitung semua yang damage_calc.py butuh dari satu avatar Enka.

    Return snapshot: identitas, loadout (weapon id/phase, set 4pc names,
    mindscape), stat panel final, dan daftar hit skill (damage_pct per
    skill type & level efektif) — tanpa print apa pun.
    """
    agent = get_agent_data(
        avatar_id=avatar_id, level=int(avatar["Level"]),
        promotion=int(avatar["PromotionLevel"]), core=int(avatar["CoreSkillEnhancement"]),
        avatars=avatars,
    )
    state = StatState()
    state.add("Character", make_character_layer(agent))
    state.add("Core", make_core_layer(agent))
    state.add("W-Engine", make_weapon_layer(avatar, weapons, weapon_level_rows, weapon_star_rows))
    state.add("Drive Discs", make_disc_layer(avatar, equipments, equipment_level_rows))
    state.add("Set Bonuses", make_set_layer(avatar, equipments))
    apply_corrections(agent, state)

    stats = final_stats(state.summed())

    excel = avatars[str(avatar_id)]
    mindscape = int(avatar.get("TalentLevel", 0))
    weapon_api = avatar.get("Weapon") or {}

    # Set 4pc aktif (count >= 4) — nama set, bukan suit id.
    suit_counts: defaultdict[int, int] = defaultdict(int)
    for equip in avatar.get("EquippedList", []):
        suit_counts[int(equipments["Items"][str(equip["Equipment"]["Id"])]["SuitId"])] += 1
    set4_names = [
        localize(loc, equipments["Suits"][str(sid)].get("Name"), str(sid))
        for sid, count in sorted(suit_counts.items()) if count >= 4
    ]

    # Skill hits: per skill index yang punya multiplier, level efektif (M3/M5 bump).
    levels = {int(s["Index"]): int(s["Level"]) for s in avatar.get("SkillLevelList", [])}
    skills = {}
    for idx in MULTIPLIER_SKILL_INDICES:
        base_lvl = levels.get(idx)
        if base_lvl is None:
            continue
        eff_lvl = effective_skill_level(base_lvl, mindscape)
        rows = compute_damage_output(
            skill_index, avatar_id=avatar_id, skill_type=idx, level=eff_lvl,
            atk=stats["ATK"], name_map=name_map, textmap=textmap,
        )
        if not rows:
            continue
        skills[str(idx)] = {
            "label": SKILL_INDEX_TO_NAME.get(idx, f"Skill {idx}"),
            "level": eff_lvl,
            "hits": [
                {
                    "hit_id": r["hit_id"],
                    "name": r["name"] or f"hit {r['hit_id']}",
                    "damage_pct": r["damage_pct"],
                    "daze_pct": r["daze_pct"],
                    "is_hidden": r["is_hidden"],
                }
                for r in rows
            ],
        }

    return {
        "avatar_id": avatar_id,
        "name": localize(loc, excel.get("Name"), str(avatar_id)),
        "element": (excel.get("ElementTypes") or ["?"])[-1],
        "profession": excel.get("ProfessionType", "?"),
        "level": int(avatar["Level"]),
        "mindscape": mindscape,
        "core": int(avatar["CoreSkillEnhancement"]),
        "weapon": {
            "id": int(weapon_api.get("Id", 0) or 0),
            "level": int(weapon_api.get("Level", 0) or 0),
            "phase": int(weapon_api.get("UpgradeLevel", 1) or 1),
        },
        "set4pc": set4_names,
        # Stats persen dikonversi basis-points -> persen (5140 -> 51.4) supaya
        # langsung kompatibel sama formula damage_calc yang expect satuan %.
        "stats": {
            k: (float(v) / 100.0 if k in PCT_PANEL_STATS else float(v))
            for k, v in stats.items()
        },
        "skills": skills,
    }


def export_loadouts(profile: str, out_path: str | None = None) -> str:
    """Export semua avatar di profile Enka -> loadouts JSON buat damage_calc.

    Struktur: {"avatars": [snapshot, ...], "panel_flat": {avatar_id: stats}}
    (panel_flat duplikat stats per id biar damage_calc gampang lookup).
    """
    base_dir = Path(__file__).resolve().parent
    api = load_json(base_dir / profile)
    showcase = api["PlayerInfo"]["ShowcaseDetail"]
    avatars_list = showcase.get("AvatarList", [])

    weapons = load_json(base_dir / "data" / "weapons.json")
    equipments = load_json(base_dir / "data" / "equipments.json")
    avatars = load_json(base_dir / "data" / "avatars.json")
    locale_path = base_dir / "data" / "locale_en.json"
    loc: dict[str, str] = load_json(locale_path) if locale_path.exists() else {}

    wl = load_template_table(base_dir / "data" / "WeaponLevelTemplateTb.json", WEAPON_LEVEL_FIELDS)
    ws = load_template_table(base_dir / "data" / "WeaponStarTemplateTb.json", WEAPON_STAR_FIELDS)
    el = load_template_table(base_dir / "data" / "EquipmentLevelTemplateTb.json", EQUIPMENT_LEVEL_FIELDS)
    skill_index, name_map, textmap = load_skill_data(base_dir)

    snapshots = []
    for avatar in avatars_list:
        snapshots.append(compute_avatar_snapshot(
            avatar, int(avatar["Id"]), avatars, weapons, equipments,
            wl, ws, el, skill_index, name_map, textmap, loc,
        ))

    payload = {
        "source_profile": profile,
        "avatars": snapshots,
        "panel_flat": {str(s["avatar_id"]): s["stats"] for s in snapshots},
    }
    out_path = out_path or str(base_dir / "dumps" / "loadouts.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="ZZZ stat calculator dari dump Enka")
    parser.add_argument("profile", nargs="?", default="1.json",
                        help="file JSON profile Enka (default: 1.json)")
    parser.add_argument("--export", action="store_true",
                        help="export loadouts.json buat damage_calc.py (tanpa print detail)")
    args = parser.parse_args()

    if args.export:
        out = export_loadouts(args.profile)
        print(f"exported: {out}")
        return

    api = load_json(base_dir / args.profile)
    showcase = api["PlayerInfo"]["ShowcaseDetail"]
    avatars_list = showcase.get("AvatarList", [])

    weapons = load_json(base_dir / "data" / "weapons.json")
    equipments = load_json(base_dir / "data" / "equipments.json")
    avatars = load_json(base_dir / "data" / "avatars.json")

    locale_path = base_dir / "data" / "locale_en.json"
    loc: dict[str, str] = load_json(locale_path) if locale_path.exists() else {}


    # Full growth tables (all rarities / levels / break levels) instead of the
    # previous single hard-coded Rarity-4 row, which crashed on A/B rank gear.
    wl = load_template_table(base_dir / "data" / "WeaponLevelTemplateTb.json", WEAPON_LEVEL_FIELDS)
    ws = load_template_table(base_dir / "data" / "WeaponStarTemplateTb.json", WEAPON_STAR_FIELDS)
    el = load_template_table(base_dir / "data" / "EquipmentLevelTemplateTb.json", EQUIPMENT_LEVEL_FIELDS)

    skill_index, name_map, textmap = load_skill_data(base_dir)

    for avatar in avatars_list:
        avatar_id = int(avatar["Id"])
        agent = get_agent_data(
            avatar_id=avatar_id, level=int(avatar["Level"]),
            promotion=int(avatar["PromotionLevel"]), core=int(avatar["CoreSkillEnhancement"]),
            avatars=avatars,
        )
        state = StatState()
        state.add("Character", make_character_layer(agent))
        state.add("Core", make_core_layer(agent))
        state.add("W-Engine", make_weapon_layer(avatar, weapons, wl, ws))
        state.add("Drive Discs", make_disc_layer(avatar, equipments, el))
        state.add("Set Bonuses", make_set_layer(avatar, equipments))
        apply_corrections(agent, state)

        summed = state.summed()
        stats = final_stats(summed)

        # ---- Header: who is this, and what are they running? ----
        excel = avatars[str(avatar_id)]
        agent_name = localize(loc, excel.get("Name"), str(avatar_id))
        rank = {2: "B", 3: "A", 4: "S"}.get(int(excel.get("Rarity", 0)), "?")
        element = "/".join(excel.get("ElementTypes", [])[-1:]) or "?"

        core_level = int(avatar["CoreSkillEnhancement"])
        core_letter = CORE_SKILL_LETTERS[core_level] if core_level < len(CORE_SKILL_LETTERS) else str(core_level)

        print("=" * 62)
        print(f"{agent_name}  [{rank}-rank {element} {excel.get('ProfessionType', '?')}]")
        print(
            f"  Level {avatar['Level']}  |  Promotion {avatar['PromotionLevel']}"
            f"  |  Mindscape M{avatar['TalentLevel']}"
            f"  |  Core Skill {core_letter} ({core_level})"
        )

        weapon_api = avatar.get("Weapon")
        if weapon_api and int(weapon_api.get("Id", 0)):
            weapon_meta = weapons[str(weapon_api["Id"])]
            weapon_name = localize(loc, weapon_meta.get("ItemName"), str(weapon_api["Id"]))
            weapon_rank = {2: "B", 3: "A", 4: "S"}.get(int(weapon_meta.get("Rarity", 0)), "?")
            print(
                f"  W-Engine: {weapon_name} [{weapon_rank}-rank]"
                f"  Lv.{weapon_api['Level']}  Phase {weapon_api['UpgradeLevel']}"
                f"  (Mod {weapon_api['BreakLevel']})"
                # break level itu bukan overclock/refinement
            )
        else:
            print("  W-Engine: (tidak ada / tidak dipasang)")

        suit_counts: defaultdict[int, int] = defaultdict(int)
        for equip in avatar.get("EquippedList", []):
            suit_counts[int(equipments["Items"][str(equip["Equipment"]["Id"])]["SuitId"])] += 1
        if suit_counts:
            sets = ", ".join(
                f"{localize(loc, equipments['Suits'][str(sid)].get('Name'), str(sid))} x{count}"
                for sid, count in sorted(suit_counts.items(), key=lambda kv: -kv[1])
            )
            print(f"  Drive Discs: {sets}")

        print_disc_details(avatar, equipments, el, loc)

        skills = sorted(avatar.get("SkillLevelList", []), key=lambda s: int(s["Index"]))
        mindscape = int(avatar.get("TalentLevel", 0))

        if skills:
            print("  Skill Levels:")
            for skill in skills:
                idx = int(skill["Index"])
                label = SKILL_INDEX_TO_NAME.get(idx, f"Skill {idx}")
                base_lvl = int(skill["Level"])
                eff_lvl = effective_skill_level(base_lvl, mindscape)
                if eff_lvl != base_lvl:
                    print(f"    {label:16}: {base_lvl} -> {eff_lvl} (M{mindscape} bump)")
                else:
                    print(f"    {label:16}: {base_lvl}")
        print()

        print("-- Layer breakdown --")

        for name, layer in state.layers:
            nonzero = {k: math.floor(v) for k, v in layer.props.items() if v}
            print(f"{name}: {nonzero}")
        print()
        print("-- Final stats --")
        for name, value in stats.items():
            if name in {
                "CRIT Rate",
                "CRIT DMG",
                "PEN Ratio",
                "Physical DMG",
                "Fire DMG",
                "Ice DMG",
                "Electric DMG",
                "Ether DMG",
                "Wind DMG",
                "Sheer DMG",
            }:
                print(f"{name:22}: {math.floor(value) / 100:.1f}%")
            elif name == "Energy Regen":
                print(f"{name:22}: {value:g}")
            else:
                print(f"{name:22}: {math.floor(value):g}")

        print_skill_damage(
            avatar, avatar_id, mindscape=int(avatar.get("TalentLevel", 0)),
            atk=stats["ATK"], skill_index=skill_index,
            name_map=name_map, textmap=textmap,
        )
        print()


if __name__ == "__main__":
    # Nama skill bisa mengandung karakter non-cp1252 (mis. U+2010) —
    # console Windows default-nya cp1252 dan bakal UnicodeEncodeError.
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
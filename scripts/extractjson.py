"""
Stage 1 — Mindscape bonus CANDIDATE extractor.

Scans m.json (output of extract_mindscapes.py) and pulls out every numeric
value (percentages and flat numbers) found in each Mindscape's description,
along with the surrounding text as context, and a best-guess "likely stat"
tag based on nearby keywords.

This does NOT produce ready-to-use calculator data — natural language is too
varied to reliably auto-detect target (self/squad), trigger condition, and
duration. It produces a REVIEW FILE: one row per number found, so a human
only has to fill in/confirm the remaining fields instead of re-reading every
description from scratch.

Usage:
    python extract_mindscape_candidates.py m.json
    python extract_mindscape_candidates.py m.json --character Alice
    python extract_mindscape_candidates.py m.json --out candidates.json
"""

import argparse
import json
import re

# Order matters: more specific phrases first, so e.g. "CRIT DMG" doesn't get
# swallowed by a generic "DMG" match.
STAT_KEYWORDS = [
    ("CRIT Rate", "critRate"),
    ("CRIT DMG", "critDamage"),
    ("Physical RES", "physicalResIgnore"),
    ("Physical DMG", "physicalDmgBonus"),
    ("Fire DMG", "fireDmgBonus"),
    ("Ice DMG", "iceDmgBonus"),
    ("Electric DMG", "electricDmgBonus"),
    ("Ether DMG", "etherDmgBonus"),
    ("Assault DMG", "assaultDmgBonus"),
    ("Disorder DMG", "disorderDmgBonus"),
    ("Anomaly Proficiency", "anomalyProficiency"),
    ("Anomaly Mastery", "anomalyMastery"),
    ("Anomaly Buildup", "anomalyBuildup"),
    ("PEN Ratio", "penRate"),
    ("Energy Generation Rate", "energyRegen"),
    ("Energy Regen", "energyRegen"),
    ("Max HP", "hp"),
    ("DEF", "defReduction"),  # usually "target's DEF is reduced" -> enemy DEF shred
    ("ATK", "attack"),
    ("Daze", "daze"),
    ("Shield", "shield"),
    ("DMG", "genericDmgBonus"),  # fallback, catches plain "DMG increases by X%"
]

# Matches: 15%  |  3,300%  |  20 %  |  1,000 (flat number, no %)
NUMBER_RE = re.compile(
    r'(?P<value>\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?P<percent>%)?'
)

# Patterns that mean "this number is timing/trigger metadata, not a stat
# value" — checked using the text immediately around the match.
DURATION_RE = re.compile(r'^\s*s\b')                       # "30s"
COOLDOWN_CONTEXT_RE = re.compile(r'(once per|every)\s*$', re.IGNORECASE)
TRIGGER_COUNT_RE = re.compile(r'^\s*times?\b', re.IGNORECASE)

CONTEXT_WINDOW = 60  # characters of context before/after each match


def classify_number_role(desc: str, match) -> str:
    """Returns 'duration', 'cooldown', 'trigger_count', or 'value'."""
    after = desc[match.end():match.end() + 5]
    before = desc[max(0, match.start() - 12):match.start()]

    if DURATION_RE.match(after):
        return "duration"
    if COOLDOWN_CONTEXT_RE.search(before):
        return "cooldown"
    if TRIGGER_COUNT_RE.match(after):
        return "trigger_count"
    return "value"


def guess_stat(context: str):
    for phrase, tag in STAT_KEYWORDS:
        if phrase.lower() in context.lower():
            return tag
    return None


def extract_candidates(mindscapes: dict, only_character: str = None) -> list:
    candidates = []
    names = sorted(mindscapes.keys())
    if only_character:
        names = [n for n in names if n.lower() == only_character.lower()]

    for name in names:
        for level_str, entry in sorted(mindscapes[name].items(), key=lambda kv: int(kv[0])):
            level = int(level_str)
            desc = entry.get("desc", "")
            title = entry.get("title", "")

            if entry.get("odd_level_skill_bump") and desc.strip() in ("", "PlaceHolder"):
                # These levels have no numeric text to extract — they're the
                # standard "+2 to five skill types" bump, not text-described.
                candidates.append({
                    "character": name,
                    "level": level,
                    "title": title,
                    "type": "skill_level_bump",
                    "value": 2,
                    "note": "Basic Attack/Dodge/Assist/Special Attack/Chain Attack Lv. +2",
                    "needs_review": False,
                })
                continue

            for m in NUMBER_RE.finditer(desc):
                value_str = m.group("value").replace(",", "")
                is_percent = m.group("percent") is not None
                value = float(value_str) if "." in value_str else int(value_str)

                role = classify_number_role(desc, m)
                if role != "value":
                    # Timing/trigger metadata, not a stat bonus — skip from
                    # the main review list entirely (not useful for layer math).
                    continue

                # Skip tiny numbers that are almost never a real bonus value
                # on their own (e.g. "3-stage") unless they're a percent,
                # which is almost always meaningful.
                if not is_percent and value < 3:
                    continue

                start = max(0, m.start() - CONTEXT_WINDOW)
                end = min(len(desc), m.end() + CONTEXT_WINDOW)
                context = desc[start:end].replace("\n", " ")

                candidates.append({
                    "character": name,
                    "level": level,
                    "title": title,
                    "type": "percent_bonus" if is_percent else "flat_bonus",
                    "value": value,
                    "likely_stat": guess_stat(context),
                    "context": context.strip(),
                    "target": None,       # fill in manually: "self" / "squad" / "enemy"
                    "condition": None,    # fill in manually: when it applies
                    "duration_s": None,   # fill in manually if temporary
                    "needs_review": True,
                })

    return candidates


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", help="Path to m.json (extract_mindscapes.py output)")
    p.add_argument("--character", default=None, help="Only process this character")
    p.add_argument("--out", default="candidates.json", help="Output path (default: candidates.json)")
    args = p.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        mindscapes = json.load(f)

    candidates = extract_candidates(mindscapes, only_character=args.character)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)

    review_count = sum(1 for c in candidates if c.get("needs_review"))
    print(f"Extracted {len(candidates)} candidate entries "
          f"({review_count} need manual review, {len(candidates) - review_count} auto-resolved).")
    print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
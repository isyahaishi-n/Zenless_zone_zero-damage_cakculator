"""
Extract Mindscape (in-game "Talent") data for ALL characters from a ZZZ
text-map / localization JSON file (e.g. locs.json or a TextMap_*.json dump).

Pattern (same for every character, only the leading name differs):
    <Name>_Talent_01_Title
    <Name>_Talent_01_Desc_01          <- combat effect text (even levels only)
    <Name>_Talent_01_Desc_01_Realign  <- same text, with real line breaks
    <Name>_Talent_01_Desc_02          <- flavor/story text (skipped by default)
    ... through _Talent_06_...

Odd Mindscape levels (M1, M3, M5) that show "PlaceHolder" for Desc_01 are NOT
missing data — in ZZZ, odd Mindscape levels don't get written effect text at
all; they just grant a flat "+2" to Basic Attack / Dodge / Assist / Special
Attack / Chain Attack skill levels. This script reports that explicitly
instead of printing "PlaceHolder".

Usage:
    python extract_mindscapes.py locs.json
    python extract_mindscapes.py locs.json --lang en
    python extract_mindscapes.py locs.json --character Alice
    python extract_mindscapes.py locs.json --out mindscapes.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict

TALENT_KEY_RE = re.compile(
    r'^(?P<name>[A-Za-z]+)_Talent_(?P<level>\d{2})_(?P<field>Title|Desc_01_Realign|Desc_01|Desc_02)$'
)

COLOR_TAG_RE = re.compile(r'</?color(=#?[0-9A-Fa-f]+)?>')


def clean_text(text: str) -> str:
    """Strip ZZZ's rich-text color tags."""
    return COLOR_TAG_RE.sub('', text)


def load_entries(path: str, lang: str) -> dict:
    """Load the flat {key: text} table, handling both a lang-wrapped file
    (e.g. locs.json: {"en": {...}, "ja": {...}}) and a flat file.
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict) and lang in data and isinstance(data[lang], dict):
        return data[lang]
    # Fall back: maybe it's already flat, or the requested lang isn't a top
    # level key — search one level down for any dict that looks like text.
    if isinstance(data, dict) and all(isinstance(v, str) for v in data.values() if v is not None):
        return data
    for key, value in data.items() if isinstance(data, dict) else []:
        if isinstance(value, dict) and all(isinstance(v, str) for v in value.values() if v is not None):
            print(f"Note: '{lang}' not found at top level; using '{key}' instead.",
                  file=sys.stderr)
            return value
    raise ValueError(
        f"Could not find a flat text table for lang='{lang}' in {path}. "
        "Pass --lang to pick a different language key, or check the file structure."
    )


def extract_mindscapes(entries: dict) -> dict:
    """Returns {character_name: {level_int: {"title":.., "desc":.., "odd": bool}}}"""
    raw = defaultdict(lambda: defaultdict(dict))

    for key, text in entries.items():
        if text is None:
            continue
        m = TALENT_KEY_RE.match(key)
        if not m:
            continue
        name = m.group('name')
        level = int(m.group('level'))
        field = m.group('field')
        raw[name][level][field] = text

    result = {}
    for name, levels in raw.items():
        char_out = {}
        for level, fields in sorted(levels.items()):
            title = fields.get('Title', '')
            # Prefer the Realign variant (has real line breaks) over the
            # run-on Desc_01 if both are present.
            desc_raw = fields.get('Desc_01_Realign') or fields.get('Desc_01', '')
            desc_clean = clean_text(desc_raw) if desc_raw else ''

            is_odd = (level % 2 == 1)

            char_out[level] = {
                'title': clean_text(title),
                'desc': desc_clean,
                'odd_level_skill_bump': is_odd,
            }
        result[name] = char_out
    return result


def print_report(mindscapes: dict, only_character: str = None) -> None:
    names = sorted(mindscapes.keys())
    if only_character:
        names = [n for n in names if n.lower() == only_character.lower()]
        if not names:
            print(f"No character named '{only_character}' found.")
            return

    for name in names:
        print("=" * 70)
        print(f"{name.upper()} — MINDSCAPE (M1–M6)")
        print("=" * 70)
        for level in range(1, 7):
            entry = mindscapes[name].get(level)
            if not entry:
                continue
            print(f"\nM{level}: {entry['title']}")
            print("-" * 40)
            print(entry['desc'])
        print()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", help="Path to the text-map JSON (e.g. locs.json)")
    p.add_argument("--lang", default="en", help="Language key to read (default: en)")
    p.add_argument("--character", default=None, help="Only show this character (case-insensitive)")
    p.add_argument("--out", default=None, help="Optional path to save the extracted data as JSON")
    args = p.parse_args()

    entries = load_entries(args.file, args.lang)
    mindscapes = extract_mindscapes(entries)

    if not mindscapes:
        print("No <Name>_Talent_XX_... keys found in this file. "
              "Double-check this is the right text-map file.", file=sys.stderr)
        sys.exit(1)

    print_report(mindscapes, only_character=args.character)
    print(f"\n({len(mindscapes)} characters found total: "
          f"{', '.join(sorted(mindscapes.keys()))})")

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            # JSON keys must be strings — convert level ints to strings for output
            serializable = {
                name: {str(lvl): data for lvl, data in levels.items()}
                for name, levels in mindscapes.items()
            }
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        print(f"Saved full extracted data to {args.out}")


if __name__ == "__main__":
    main()
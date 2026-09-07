import re

js = open('enka_zzz_tooltip.js', encoding='utf-8', errors='ignore').read()

# Find all /ui/zzz/ asset references
assets = sorted(set(re.findall(r'/ui/zzz/[A-Za-z0-9_]+\.(?:png|webp)', js)))
print(f"Asset refs found: {len(assets)}")
for a in assets:
    print(" ", a)

# Find element/profession icon patterns
print("\n--- Element/Profession patterns ---")
elem = sorted(set(re.findall(r'["\']([A-Za-z]*(?:Element|Profession|Attribute)[A-Za-z]*)["\']', js)))
for e in elem[:50]:
    print(" ", e)

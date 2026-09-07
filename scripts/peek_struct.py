import json

with open('data/avatars.json', encoding='utf-8') as f:
    avatars = json.load(f)

elems = set()
profs = set()
for a in avatars.values():
    for e in a.get('ElementTypes', []):
        elems.add(e)
    profs.add(a.get('ProfessionType'))

print("Elements:", sorted(elems))
print("Professions:", sorted(profs))
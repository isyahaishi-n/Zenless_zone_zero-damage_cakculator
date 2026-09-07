import urllib.request

base = 'https://enka.network/ui/zzz/'
candidates = [
    # Element icons
    'IconElementFire.png', 'IconFire.png', 'Fire.png', 'IconAttrFire.png',
    'IconElementPhys.png', 'IconPhys.png', 'Phys.png',
    'IconElementElec.png', 'IconElec.png', 'Elec.png',
    'IconElementIce.png', 'IconIce.png', 'Ice.png',
    'IconElementEther.png', 'IconEther.png', 'Ether.png',
    # Profession icons
    'IconProfessionAttack.png', 'IconAttack.png', 'Attack.png',
    'IconProfessionStun.png', 'IconStun.png', 'Stun.png',
    'IconProfessionAnomaly.png', 'IconAnomaly.png', 'Anomaly.png',
    'IconProfessionSupport.png', 'IconSupport.png', 'Support.png',
    'IconProfessionDefense.png', 'IconDefense.png', 'Defense.png',
    'IconProfessionRupture.png', 'IconRupture.png', 'Rupture.png',
    # Rarity
    'ItemRarityS.png', 'ItemRarityA.png', 'ItemRarityB.png',
    # Mindscape
    'IconMindscape.png',
    # Element icon variations
    'IconFire1.png', 'IconFire2.png', 'IconFire3.png',
    'IconElementFire1.png', 'IconElementFire2.png',
    'IconRoleElementFire.png',
    'ElementFire.png', 'ElementalFire.png',
    'IconBurn.png', 'IconFrozen.png', 'IconShock.png', 'IconCorruption.png', 'IconAssault.png',
    'IconAttributeFire.png', 'IconAttrFire1.png',
    'FireIcon.png', 'Icon_Fire.png',
    'iconfire.png', 'icon_fire.png',
    'IconElementalFire.png', 'IconElementTypeFire.png',
    'IconDamageFire.png', 'IconDmgFire.png',
    'IconResFire.png',
    'IconTypeFire.png', 'IconTypeAttack.png',
    # Stat icons
    'IconHp.png', 'IconAtk.png', 'IconDef.png', 'IconCrit.png', 'IconCritDmg.png',
    'IconPropertyHp.png', 'IconStatHp.png',
    # Skill icons
    'IconSkillNormal.png', 'IconSkillSpecial.png', 'IconSkillUltimate.png', 'IconSkillDodge.png', 'IconSkillChain.png',
    'IconRoleSkillKeyNormal.png',
]

for name in candidates:
    url = base + name
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"OK  {resp.status}  {name}")
    except Exception as e:
        print(f"--  {name}")
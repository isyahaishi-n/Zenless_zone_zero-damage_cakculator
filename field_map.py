"""
field_map.py — Peta field code obfuscated per versi data (single source of truth).

Patch 3.2.0 (2026-09-10, commit ZenlessData 1965421b16a9) RE-OBFUSCATED semua
field name: root key `MLOEFHJHCID` -> `IAEFFFFLKNB`, dan seluruh field code
per tabel berubah total. Mapping di file ini hasil korrelasi otomatis
old<->new (row-value signature match + ID join voting) dan diverifikasi
manual ke ground truth:

  - MonsterSub: Tyrfing DEF=36, HP=1123, StunTaken=5000, 6 field RES -2000 —
    semua match persis lewat mapping baru.
  - AvatarSkill: Miyabi 1091027/1091028 base dmg 45470/85810 & growth
    4140/7810 match persis.
  - MonsterConfig: Tyrfing codename `Monster_ClaymoreGrey` resolvable, type
    `Monster` OK.
  - WeaponTalent/WeaponLevel/WeaponStar/EquipmentLevel/LevelCurve/MonsterUpgrade:
    vote 100% semua row.

Verifikasi formula tetap lewat kalibrasi damage_calc.py (Tahap 4 UPDATE.md).
Kalau patch berikutnya re-obfuscate lagi: regenerate mapping dengan metode
yang sama (lihat metode di TODO_agent2.md "field re-map korrelasi") lalu
update tabel FIELD_MAP_320 di bawah.
"""

# Format: TABLE -> {old_field(3.1.0): new_field(3.2.0)}
# Field lama dipertahankan sebagai key supaya semua kode existing (yang pakai
# nama 3.1.0) tetap jalan tanpa diedit; akses data baru lewat konstanta ini.

ROOT_KEY_OLD = "MLOEFHJHCID"
ROOT_KEY_NEW = "IAEFFFFLKNB"

FIELD_MAP_320 = {
    # --- dipakai skill_lookup.py / zzz_enka_stat_calc_multichar.py ---
    "AvatarSkillTemplateTb": {
        "DALBKGGEJEF": "PFOAJKNPCHL",   # skill/hit id
        "GLENCFMNKMF": "NDGEGNEGKFF",   # skill type (0 basic..6 assist)
        "IKAABAIDFAO": "BALHEIIFHLN",   # damage base %
        "DGHHKAHHIPM": "KBEFIIEFCGH",   # damage growth %/level
        "OMFJHOLBIKA": "PLEPHHBDMGD",   # daze base %
        "KICLLNBEAEN": "BJCBBHKLCLB",   # daze growth %/level
    },
    # --- dipakai skill_lookup.py (explicit name map) ---
    "AvatarSkillDesTemplateTb": {
        "DALBKGGEJEF": "PFOAJKNPCHL",
        "ACOLKGPPGKK": "IBHPGDINFNF",  # derived UI id (410xxx)
        "BBOJJFEDGEP": "LGGNCLOGDFI",
        "DLADMENPFPD": "KGLIAHOGMIO",  # desc key
        "FADGEADKNII": "CFNBANBGBFF",
        "GLENCFMNKMF": "NDGEGNEGKFF",  # skill type
        "KLPLBBJABBL": "OKCGOIHCKPA",  # "{Skill:id, Prop:1001}" explicit ref
        "LECKPHICFOA": "FLLDOEFBOMB",  # title key
        "ONMHBHPOLHI": "LADHMECGJPO",  # UI sort index
        "PDJMFJOFNEF": "FHNDNMJKPJL",  # 0=skill entry, 1=property row
        "PJABHBNCJOI": "PBNPPFFJCGN",  # avatar id
    },
    # --- dipakai core_skill_lookup.py ---
    "AvatarPassiveSkillTemplateTb": {
        "DALBKGGEJEF": "PFOAJKNPCHL",
        "PJABHBNCJOI": "PBNPPFFJCGN",  # avatar id
        "FCLMDBPHFDN": "JGMJENCFCFD",  # core rank 2-7
        "DNJHODOHPDA": "HPFIDMADNGO",  # unlock level
        "KBOACPNJNKF": "AIDOLEKPFCP",  # [{prop id, value}] list
        "BGEHICNGHKO": "CNCEKNHEHIP",  # nested: property id (di dalam KBOACPNJNKF rows)
        "CLEHOBAKHOI": "CPKDEBLNOMN",  # nested: value
        "GPDGFDPHGJJ": "PBDNBKCOBFI",  # desc keys per rank
        "HDPANGNKNAP": "ADMHHFAIKJG",  # title keys
        "OPLOCGPNNJB": "HHACGOPKMGD",  # upgrade cost
    },
    # --- dipakai scripts/wengine_passive_gen.py ---
    "WeaponTalentTemplateTb": {
        "APAEMLCPFID": "MGBBDLDBNKK",  # phase/level 1-5
        "CBFOFEECIGH": "JDBHBJCNBCH",
        "CLCDDKNHEMN": "HIFIJCJHFDG",  # title key
        "COEEBFOBGND": "HGFJOGONPJG",  # talent id
        "NFKHOOCEDEH": "BFCEHLJGCED",  # des id list
        "POLEJGCKKFI": "FMIFFHCNGCP",  # desc key
    },
    # --- dipakai scripts/mindscape_passive_gen.py ---
    "AvatarTalentTemplateTb": {
        "PJABHBNCJOI": "PBNPPFFJCGN",  # avatar id
        "PPAGKJLLCIM": "EKHEGOHEOLN",  # talent desc key
        "PADNNKFLNLG": "ECOLPBLBHMK",  # title key
        "EHEONBCLBAG": "IEPODKDOOCN",
        "CKPJDLGIAHO": "KDKBOLHEJDB",  # realign key
        "DPBEEACCGDC": "KDELABPMGLM",
        "PJBKBALOBEH": "LIBGEDCAION",
        "FIBBJMHGNIK": "BEJEGLJIMGA",
        "OKHILPNCLKH": "GJPPGNDGOGL",
        "GFPKLHKBGKG": "BJNNDDAONGE",  # [{prop,value}] list
        # nested prop/value (nama 3.1.0 dari file lama):
        "IKGGLEKBEPJ": "HJOEBMMFOMB",  # nested: property id
        "CLEHOBAKHOI": "CPKDEBLNOMN",  # nested: value
    },
    # --- dipakai monster_data.py ---
    "MonsterConfigTemplateTb": {
        "DALBKGGEJEF": "PFOAJKNPCHL",   # config id
        "NDJJEKDIHNN": "KOHFPMHGOOL",   # "Monster"
        "GELOADGCCFN": "DDNBBJKLOKK",   # codename (TextMap key)
    },
    "MonsterSubTemplateTb": {
        "DALBKGGEJEF": "PFOAJKNPCHL",   # sub row id
        "EBIKJFJOKGP": "FGOEKBADEOG",   # config link id
        "AOIJDIEHABK": "MOLBAPLLFNJ",   # DEF base
        "LPKOMILKOKG": "NCNEAEPHDHE",   # HP base
        "LHPKLCOJKCN": "DHJOMKKMPEC",   # StunDamageTakenRatio /10000
        # DamageRes per element /10000
        "ACOFKCMKDOJ": "FKBMEOPJBMO",   # Physical
        "FHKIMGJHOOM": "KOEFPBDADKH",   # Fire
        "DAHICMDLIDB": "IMBBMNLCMKD",   # Ice
        "GOCPMKOMLLA": "BKIDJHCFADF",   # Electric
        "EPCAKNEIANN": "EJKPKNFKJAB",   # Ether
        "MLNILAMPKDE": "OGOJAOIJDJE",   # Wind
        # BuildupRes per element
        "HEEFNBCGGGG": "KKDGMHOKNOA",   # Physical
        "NFILPFLNIPC": "PIGGCPCDIDO",   # Fire
        "DDMBIHOALHL": "JDCDIILPKBJ",   # Ice
        "BLNPNJIDME": "BIJKACMOCJO",   # Electric
        "PMGFNHIKHBD": "OJNOPLDGDBO",   # Ether
        "JFABMBIMGNA": "OEEHDMJOODI",   # Wind
        # StunRes per element
        "PHCJFMBBDJC": "FAACBMNHODI",   # Physical
        "PGGMCKBGCGL": "BFMPFKMENEP",   # Fire
        "GDLJANCPPPM": "NONBKCNBJAF",   # Ice
        "CHODLLFEEPK": "MHOAMPLFHNF",   # Electric
        "FPIFENJCHJH": "PHIIHLNGNLD",   # Ether
        "KOFJJDEIGAB": "IPMJHOKMPDP",   # Wind
    },
    "MonsterUpgradeTemplateTb": {
        "CINIMCIAICO": "BIEAEJDNEID",
        "FIMGJKPCKFO": "NFFBNPDFBNG",  # upgraded sub id
    },
    # --- dipakai damage_calc.py / zzz_enka_stat_calc_multichar.py ---
    "LevelCurveTemplateTb": {
        "DALBKGGEJEF": "PFOAJKNPCHL",   # curve id (1000 = level factor x2)
        "JMIKNDKIMPH": "MGGFIPIOEMO",   # [L1..L60] values
    },
    "WeaponLevelTemplateTb": {
        "APDCBEGPHJO": "CECLEKPMEJB",   # rarity
        "GJGMIBEOBHP": "MPBONOJLLPF",   # level
        "EOMOGNMMOEJ": "DPKJPJNGJEK",   # enhance rate
    },
    "WeaponStarTemplateTb": {
        "APDCBEGPHJO": "CECLEKPMEJB",   # rarity
        "LMBCLMNIJNA": "EDIOFIDLPPF",   # break level (ambig dgn JGLBPGJGIFA; semua value 0 -> aman utk kode: hanya dipakai sbg kolom kosong)
        "EENDAEFLEJO": "PFPPMCPKOEE",   # star rate
        "IIPAHNFIJOH": "PFMPCAJKLBE",   # rand rate
    },
    "EquipmentLevelTemplateTb": {
        "APDCBEGPHJO": "CECLEKPMEJB",   # rarity
        "GJGMIBEOBHP": "MPBONOJLLPF",   # level
        "EOMOGNMMOEJ": "DPKJPJNGJEK",   # enhance rate
    },
}


def map_table(table_name: str, old_fields: dict) -> dict:
    """Konversi {old_field: readable_name} versi 3.1.0 -> versi 3.2.0.

    Dipakai loader yang punya field_map {obf_name: readable}: balikin dict
    baru dengan key obf_name 3.2.0 supaya bisa dipakai ke file data baru.
    """
    t = FIELD_MAP_320.get(table_name, {})
    return {t.get(k, k): v for k, v in old_fields.items()}


def remap_rows(rows: list, table_name: str) -> list:
    """Rename field name baris data 3.2.0 -> nama 3.1.0 (kode lama tetap jalan).

    Return list dict baru; field yang gak ada di mapping dibiarkan apa adanya.
    """
    t = FIELD_MAP_320.get(table_name)
    if not t:
        return rows
    inv = {v: k for k, v in t.items()}
    out = []
    for r in rows:
        out.append({inv.get(k, k): v for k, v in r.items()})
    return out

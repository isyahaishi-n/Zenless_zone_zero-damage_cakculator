python zzz_enka_stat_calc_multichar.py 1303558818.json --export   →  loadouts.json
python damage_calc.py                                              →  kalibrasi auto dari loadouts
# ZZZ Skill Data — Laporan Dekode Field Obfuscated

Laporan lengkap hasil reverse-engineering field-field obfuscated (nama acak) pada dump
data skill Zenless Zone Zero dari repo [ZenlessData](https://git.mero.moe/dimbreath/ZenlessData)
(`FileCfg/*.json`, versi game 3.1.0). Semua dekode sudah **diverifikasi silang** dengan
wiki biligame (nilai in-game Anby & Jane cocok 100%, termasuk scaling level 1-16) dan
cache data hakush.in (`Genshin-Optimizer/zzz-hakushin-data`) yang memuat nama field asli.

---

## Daftar File

| File | Rows | Isi |
|---|---|---|
| `AvatarSkillTemplateTb.json` | 1467 | Statistik per sub-skill (nilai LV1 + growth per level) |
| `AvatarSkillLevelTemplateTb.json` | 3886 | Syarat & biaya upgrade skill per level |
| `AvatarSkillDesTemplateTb.json` | 4133 | Mapping teks judul/deskripsi/statistik skill |
| `SkillListConfigTemplateTb.json` | 774 | Urutan & ikon daftar skill di UI |
| `SkillPropertyTemplateTb.json` | 3 | Definisi properti statistik skill |
| `AvatarSkillRecoTemplateTb.json` | 61 | Prioritas rekomendasi upgrade skill |
| `AvatarSkillInfoTemplateTb.json` | 32 | Info "Special Technique" karakter |

Semua file berformat `{ "MLOEFHJHCID": [ ...rows ] }` — root key tunggal berisi array row.

---

## 1. AvatarSkillTemplateTb — Statistik Skill

**Struktur ID:** `DALBKGGEJEF = AvatarId × 10000 + nomor urut sub-skill`
(bukan per-level! satu row = satu sub-skill, berisi nilai LV1 dan pertumbuhan per level)

Contoh Anby (1011): `1011001`–`1011016` = basic hit 1–4, branch (落雷), special,
EX special, dash attack, dodge counter, chain attack, ultimate, quick assist,
parry light/heavy/continuous, assist follow-up.

### Field mapping

| Field obfuscated | Nama asli | Tipe | Arti |
|---|---|---|---|
| `DALBKGGEJEF` | Id | int | ID unik sub-skill |
| `GLENCFMNKMF` | SkillType | enum | 0=Basic, 1=Special/EX, 2=Dodge, 3=Chain+Ultimate, 5=Core, 6=Assist |
| `EFAHDHGKKBK` | — | int | Selalu 0 (tidak terpakai) |
| `IKAABAIDFAO` | **DamagePercentage** | int | DMG multiplier LV1 (basis point; ÷100 → persen) |
| `DGHHKAHHIPM` | **DamagePercentageGrowth** | int | Tambahan DMG% per level (÷100) |
| `OMFJHOLBIKA` | **StunRatio** | int | Daze multiplier LV1 (÷100 → persen) |
| `KICLLNBEAEN` | **StunRatioGrowth** | int | Tambahan Daze% per level (÷100) |
| `ECHPKCNANMI` | **SpRecovery** | int | Energi (SP) yang dipulihkan per hit (÷10000); 0 untuk Special/EX/Chain/Ult |
| `KAGFAENFDCH` | **AttributeInfliction** | int | Anomaly buildup per hit (÷100); hanya signifikan untuk karakter Anomaly |
| `BLGOMFMHNKA` | **FeverRecovery** | int | Gain gauge Decibel/DAU (÷10000); 0 untuk Ultimate & parry |
| `LNPEPHCOHLJ` | **EtherPurify** | int | Nilai purifikasi ether (internal, tidak tampil in-game) |
| `NHLLFIKAMMH` | — | string | Nama curve attenuasi jarak (`DistanceAttenuation_Curve_01` dll.) |
| `DBJAIPEPGAJ` | — | int[] | ID efek/ability terkait |
| `KCLOCHEFIDA` … `NEPNFECLJAD` (11 field) | — | int | Hampir selalu 0; hanya kasus khusus tertentu |

### Formula scaling level

```
Damage(level) = IKAABAIDFAO + (level − 1) × DGHHKAHHIPM
Daze(level)   = OMFJHOLBIKA + (level − 1) × KICLLNBEAEN
```

Hasil dibagi 100 untuk mendapatkan persen (basis point per 1%).

### Contoh verifikasi (Anby 1011)

| Skill | Field | LV1 | Growth | LV12 (hitung) | Wiki | Cocok |
|---|---|---|---|---|---|---|
| Basic hit 1 DMG | IKA/DGH | 3120 (31.2%) | 290 | 3120+11×290 = 6310 → **63.1%** | 63.1% | ✓ |
| Basic hit 4 DMG | IKA/DGH | 23910 (239.1%) | 2180 | **478.9%** | 478.9% | ✓ |
| Branch 落雷 DMG | IKA/DGH | 32860 (328.6%) | 2990 | **657.5%** | 657.5% | ✓ |
| EX Special DMG | IKA/DGH | 58300 (583%) | 5300 | **1166%** | 1166% | ✓ |
| Ultimate DMG | IKA/DGH | 151260 (1512.6%) | 13760 | **3026.2%** | 3026.2% | ✓ |
| Basic hit 1 Daze | OMF/KIC | 1560 (15.6%) | 80 | **24.4%** | 24.4% | ✓ |
| Parry heavy Daze | OMF/KIC | 31170 (311.7%) | 1420 | **467.9%** | 467.9% | ✓ |

Verifikasi Jane (1261, karakter Anomaly): basic hit 1 DMG 3610 = 36.1% ✓,
ultimate DMG 147060 = 1470.6% ✓, ultimate daze 18650 = 186.5% ✓.

### Catatan khusus

- **Parry rows** (`IKA=0`, hanya daze): `LNPEPHCOHLJ` konstan lintas karakter —
  36664 (light), 41664 (heavy), 11664 (continuous).
- **Karakter Anomaly**: `KAGFAENFDCH` (AttributeInfliction) besar — mis. Jane EX Special
  47396 → 473.96 anomaly buildup per hit.
- **SpRecovery/ECH** hanya di type 0 (basic), 2 (dodge), dan sebagian 6 (assist);
  selalu 0 untuk EX/Chain/Ultimate (skill berbasis energi tidak menghasilkan energi).
- `DGH` juga memenuhi `ceil(IKA/110)×10` pada 1403/1467 row — ini bukan identitas
  sebenarnya (hanya korelasi desain), gunakan formula growth di atas.

---

## 2. AvatarSkillLevelTemplateTb — Upgrade Skill

**Struktur ID:** `DALBKGGEJEF = AvatarId × 10000 + SkillType × 100 + Level`

### Field mapping

| Field obfuscated | Nama asli | Arti |
|---|---|---|
| `DALBKGGEJEF` | Id | ID unik level skill |
| `PJABHBNCJOI` | AvatarId | ID karakter (1011 = Anby, dst.) |
| `GLENCFMNKMF` | SkillType | 0=Basic, 1=Special, 2=Dodge, 3=Chain, 5=Core, 6=Assist — **cocok dengan `SkillLevelList[].Index` dari Enka API** |
| `BPGFLKCMDLD` | Level | Level skill (1–12 untuk skill normal, 1–7 untuk Core) |
| `DACKFLGFKLD` | RequiredLevel | Level karakter minimum (gate; 0 untuk Core) |
| `PBLDEBCEGAG` | MaterialList | Biaya upgrade: array `{IKGGLEKBEPJ: ItemId, CLEHOBAKHOI: Qty}` |
| `KNFOMEOFNBA` | CoreSkillProps | Efek Core Skill per level (hanya type 5) — array ID property |
| `EJJCLHAFDOI` | — | Parameter core kondisional (42 row saja) |
| `OJGBEGFINAE` | — | ID terkait parameter kondisional |
| `EBLKGCCLDLP` | — | Nilai parameter kondisional |

### Item ID biaya (terverifikasi via ItemTemplateTb)

| ItemId | Item |
|---|---|
| `10` | Dennies (gold) |
| `100113` | Basic skill chip tier 1 (rarity 1) |
| `100123` | Advanced skill chip tier 2 (rarity 2) |
| `100133` | Specialized skill chip tier 3 (rarity 3) |
| `100941` | 「Hamster Cage」 Passive Accessory (biaya level 12, qty 1) |

Pola biaya Anby (per karakter sama pola, nilai bervariasi):
- Lv2: 3000 dennies + 3× chip T1 · Lv6: 18000 + 6× chip T2 · Lv11: 135000 + 15× chip T3 + 1 hamster cage
- Level skill max = 12 (16 dengan Mindscape M3/M6 +2, tidak ada row tersendiri)

### Core Skill (type 5)

Level 1–7, tanpa gate level & tanpa biaya material di tabel ini (biaya core berbeda).
`KNFOMEOFNBA` berisi ID property yang diaktifkan, mis. Anby:
`[11011201…11011207]` = scaling passive per level, `11011301` = paket stat core A–F.
Field `EJJCLHAFDOI/OJGBEGFINAE/EBLKGCCLDLP` hanya terisi untuk karakter dengan
efek core kondisional/kustom (Ben, Yidhari, YiXuan, Norano, BanYue, SPBilly).

---

## 3. File Pendukung

### SkillPropertyTemplateTb — defininisi properti statistik

| Field | Arti |
|---|---|
| `DALBKGGEJEF` | PropertyId: **1001 = SkillDamageRate, 1002 = SkillStunRatio, 1003 = SkillSpRecovery** |
| `JDGMFLANFNL` | Nama internal properti |
| `BLPLOAHJCEI` | Divisor (10000) |
| `GAEGFAIGDBF` | Format string (`{0:0.#%}`) |
| `ODPGEJOMDPF` | Sort order |

### AvatarSkillDesTemplateTb — mapping teks skill

**Struktur ID:** `AvatarId × 100000 + seq`

| Field | Arti |
|---|---|
| `PJABHBNCJOI` | AvatarId |
| `PDJMFJOFNEF` | 0 = baris skill (judul/deskripsi), 1 = baris statistik (DMG/Daze) |
| `GLENCFMNKMF` | SkillType (sama enum seperti di atas) |
| `LECKPHICFOA` | TextMap key judul skill (mis. `Anbi_Skill_Normal_Title`) |
| `DLADMENPFPD` | TextMap key deskripsi skill |
| `KLPLBBJABBL` | Referensi nilai statistik: `{Skill:1011001, Prop:1001}` → ambil nilai dari AvatarSkillTemplateTb skill 1011001, properti DMG (1001) atau Daze (1002) |
| `ACOLKGPPGKK` / `ONMHBHPOLHI` | ID resource untuk baris Core Skill |
| `BBOJJFEDGEP` | TextMap key override |

Prop 1001 = 1088 row (DMG), Prop 1002 = 1231 row (Daze). Baris parry hanya punya
Prop 1002 (daze saja, tanpa damage).

### SkillListConfigTemplateTb — konfigurasi UI daftar skill

| Field | Arti |
|---|---|
| `CINMBBKGILM` | ID = `AvatarId × 10000 + urutan UI` |
| `CLHJEHADMKO` / `FBMEAFKBCPC` | TextMap key judul / konten (input icon) |
| `PJABHBNCJOI` | AvatarId |
| `OGIJGDFBEAD` | **Elemen damage**: 200=Fisik, 201=Api, 202=Es, 203=Listrik, 204=Angin, 205=Ether, 300=Lumen, 0=tanpa damage |
| `IHJMGLIMLLA` | Varian input: 101=dasar, 102=branch/enhanced (hold), 103=varian lain |
| `FADGEADKNII` | Daftar sub-skill terkait (hanya 12 row) |
| `DOINEEONCDN` | Flag tampilan |

### AvatarSkillRecoTemplateTb — rekomendasi prioritas upgrade

| Field | Arti |
|---|---|
| `DALBKGGEJEF` | `AvatarId × 10000 + varian` |
| `PJABHBNCJOI` | AvatarId |
| `FEKECMPGBBC` | Prioritas 1 (urutan SkillType) |
| `GMENHLFOMNF` | Prioritas 2 |
| `CCBJCPFBOMI` | Prioritas 3 |
| `HAIAJNHEHAD` | Semua skill yang bisa di-upgrade |

Contoh Anby: `[5,1]` → `[0,3]` → `[2,6]` = Core & Special dulu, lalu Basic & Chain,
lalu Dodge & Assist.

### AvatarSkillInfoTemplateTb — Special Technique

| Field | Arti |
|---|---|
| `DALBKGGEJEF` | Row ID |
| `PJABHBNCJOI` | AvatarId |
| `FLBOFCCCNHL` | TextMap popup ID → key `PopUp_Title_999XXXX` / `PopUp_Content_999XXXX` (mis. 9992542 = Miyabi "Silent Frost Fall") |
| `CLDKOIOKGKO` | Gelombang rilis/kelompok (3 atau 4; **bukan rarity** — rarity ada di `avatars.json`) |

---

## 4. Cara Pakai (contoh)

```python
import json

sk = json.load(open("AvatarSkillTemplateTb.json", encoding="utf-8"))["MLOEFHJHCID"]
by_id = {r["DALBKGGEJEF"]: r for r in sk}

def skill_damage(skill_id: int, level: int) -> float:
    """DMG multiplier dalam persen, mis. 63.1"""
    r = by_id[skill_id]
    return (r["IKAABAIDFAO"] + (level - 1) * r["DGHHKAHHIPM"]) / 100

def skill_daze(skill_id: int, level: int) -> float:
    """Daze multiplier dalam persen, mis. 24.4"""
    r = by_id[skill_id]
    return (r["OMFJHOLBIKA"] + (level - 1) * r["KICLLNBEAEN"]) / 100

# Anby ultimate LV12 → 3026.2
print(skill_damage(1011011, 12))
```

Mendapatkan level skill karakter dari data Enka (`SkillLevelList`):
`Index` ↔ `GLENCFMNKMF` (SkillType), lalu cari row `AvatarSkillTemplateTb`
sesuai urutan sub-skill dan terapkan formula di atas.

### Pipeline lengkap: `run.py` (UID Enka -> stat panel -> damage)

`run.py` nyambungin seluruh pipeline dalam satu perintah: fetch data player
dari enka.network, hitung stat panel tiap karakter showcase, lalu damage
tiap hit skill vs musuh pilihan.

```bash
python run.py <uid>                          # musuh default: Tyrfing Lv.60
python run.py <uid> --enemy Haytor            # 207 monster tersedia by name
python run.py <uid> --enemy "The Defector" --enemy-level 60
python run.py <uid> --stunned                 # aktifkan Stun Modifier
python run.py <uid> --list-enemies            # daftar nama musuh
```

Stat musuh (DEF/HP/RES per elemen/StunDmgTaken) dibaca dari data Monster
asli via `monster_data.py` (TextMap + MonsterConfig + MonsterSub +
LevelCurve; field mapping terverifikasi terhadap
Genshin-Optimizer/zzz-hakushin-data, 635/643 row exact — detail mapping
field di docstring `monster_data.py`).

**PENTING — jalanin dari root folder repo.** `run.py` butuh banyak file
JSON pendukung di folder yang sama (`weapons.json`, `equipments.json`,
`avatars.json`, `wengine_passive_mapped.json`, `drive_disc_mapped.json`,
`mindscape_mapped.json`, `locale_en.json`, plus tabel template
`*TemplateTb.json`) — semuanya sudah ada di repo, tapi hanya ke-load
benar kalau current directory = root repo:

```bash
cd /path/ke/booger_aidszzz
python run.py 1303558818
```

Catatan output:
- Hit dengan `damage 0%` tapi daze besar (mis. *Defensive Assist:
  Drifting Petals*) ditandai `(daze-only)` — memang 0 damage di data
  skill asli, daze-only by design.
- Karakter showcase tanpa weapon/gear tidak crash; kalau tidak ada
  skill data pun, muncul pesan jelas.
- `--stunned` mengalikan damage dengan (1 + StunDamageTakenRatio musuh)
  — mis. Tyrfing +50%, The Defector +25%.

---

## 5. Sumber Verifikasi

1. **Wiki biligame** (zh) — halaman 安比 (Anby) & 简 (Jane): semua nilai DMG/Daze
   LV1–16 cocok 100% dengan hasil dekode.
   - https://wiki.biligame.com/zzz/安比
2. **Genshin-Optimizer/zzz-hakushin-data** (cache hakush.in) — file karakter berisi
   nama field asli: `Main`, `Growth`, `DamagePercentage`, `DamagePercentageGrowth`,
   `StunRatio`, `StunRatioGrowth`, `SpRecovery`, `FeverRecovery`,
   `AttributeInfliction`, `EtherPurify`, `AttackData` — nilai identik dengan dump.
   - https://github.com/Genshin-Optimizer/zzz-hakushin-data
3. **ItemTemplateTb.json** (repo ZenlessData) — dekode ItemId biaya upgrade.
4. **TextMap_ENTemplateTb.json** (lokal) — key teks skill, popup Special Technique,
   dan label `*_Property_*_Desc_Dmg/Stun_*` ("DMG Multiplier" / "Daze Multiplier").
em_Weapon_','EquipmentSuit_'))},open('locale_en.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)"
```

old readme
python zzz_enka_stat_calc_multichar.py --api 1303558818.json --avatars avatars.json

Add `--with-conditional` to also count Mindscape buffs that need a combat trigger.

## Web viewer

The same calculator is also available as a local web app (stdlib only, no npm deps):

```
python server.py            # http://localhost:8787
python server.py 9000       # custom port
```

- Enter any in-game UID to fetch the live showcase from enka.network (proxied server-side),
  or click **Load sample** to view the bundled `1303558818.json`.
- Agent cards show computed final stats (identical math to the Python script),
  W-Engine and drive-disc detail, mindscape nodes and skill levels.
- Game data (`avatars.json`, `weapons.json`, `equipments.json`, locale, level tables)
  is served from `/api/data`; Enka images are proxied via `/ui/zzz/...` and disk-cached
  in `.imgcache/`.
- `node test_calc.js` verifies the JS stat engine against the Python reference output.

## Output

For every agent in the showcase the script prints:

- Name, rank / element / specialty, Level, Promotion, Mindscape (M0-M6), Core Skill (A-F)
- Equipped W-Engine: name, rank, level, phase, mod level
- Drive Disc set summary plus per-slot detail (set name, rank, +level, main stat, each sub stat with roll count)
- Unlocked Mindscape nodes, each tagged `[in stats]`, `[conditional - not in stats]`, `[not in stats]`, or `(skill Lv. +2)`
- Skill levels as reported by Enka, plus a footnote for the odd-Mindscape bonus (see below)

- Layer breakdown (Character / Core / Mindscape / W-Engine / Drive Discs / Set Bonuses / Corrections) and the final stat sheet

## Mindscapes

`mindscapes.json` (built by `extract.py` from the EN text map) is **display text only** -
`title` / `desc` / `odd_level_skill_bump`, no property ids. Agent lookup uses the
`avatars.json` name suffix, e.g. `Avatar_Male_Size03_PanYinhu` -> `PanYinhu`.

Descriptions are deliberately **not** regex-parsed: of 174 even-level entries only 14
lack a conditional keyword, so most effects are combat-state buffs, damage multipliers,
RES ignores or stat-scaling conversions rather than stat-sheet numbers.

Instead, the numbers the calculator applies live in `mindscape_props.json`:

```json
"1091": { "2": { "props": { "20103": 1500 }, "unconditional": false,
                 "note": "CRIT Rate +15% upon entering the battlefield" } }
```

`unconditional: true` is always counted; `false` needs `--with-conditional`. Empty
`props` plus a `note` records effects that cannot be expressed as a flat stat. Odd
Mindscape levels are never added to the stat layer - they only change skill levels,
not the stat sheet.

## Skill levels: known limitation

Enka's `SkillLevelList` is the **only** source of skill levels available. Neither the
local `avatars.json` nor Enka's upstream copy ships per-agent *base* skill levels
(both expose only `BaseProps` / `GrowthProps` / `PromotionProps` /
`CoreEnhancementProps`). Two consequences:

1. **Chain Attack is missing.** Index 4 is absent from `SkillLevelList` for every
   avatar in the payload, at every Mindscape level. It is printed as
   `n/a  (not included in the Enka payload)` rather than silently skipped.
2. **The M1/M3/M5 `+2` bump cannot be split out.** An earlier version printed
   `12  (base 6 +6 from M1/M3/M5)`, which assumed the API numbers already contain
   the bump. That assumption is not supported by the data: avatar `1091` is at **M0**
   - so it has no bump at all - yet already reports Basic Attack 12 / Special Attack
   12, the trained cap. Reconstructing a "base" by subtracting the bump would invent
   numbers. The script now prints the API values verbatim and notes the bump
   separately.

Getting true `base + 2 x count(M1,M3,M5)` values needs a skill-level table from a
different data source (e.g. a game `Avatar*SkillTemplateTb` dump); there is no way to
derive them from this payload.



## Data files


| File | Purpose |
| --- | --- |
| `1303558818.json` | Enka showcase payload (agents, W-Engines, Drive Discs) |
| `avatars.json` | Agent metadata: BaseProps / GrowthProps / PromotionProps / CoreEnhancementProps |
| `weapons.json` | W-Engine metadata: Rarity, MainStat, SecondaryStat |
| `equipments.json` | Drive Disc items + suit set bonuses |
| `WeaponLevelTemplateTb.json` | W-Engine level enhance rates (rarity 2-4, Lv 0-60) |
| `WeaponStarTemplateTb.json` | W-Engine mod/star rates (rarity 2-4, BreakLevel 0-5) |
| `EquipmentLevelTemplateTb.json` | Drive Disc level enhance rates (R2 -> +9, R3 -> +12, R4 -> +15) |
| `locale_en.json` | English names for agents / W-Engines / disc sets |
| `mindscapes.json` | Mindscape display text (title / desc), produced by `extract.py` |
| `mindscape_props.json` | Machine-readable Mindscape stat effects consumed by the Mindscape layer |


The `*TemplateTb.json` dumps store rows under the root key `MLOEFHJHCID` with
obfuscated field names. The script de-obfuscates them via the maps at the top of
`zzz_enka_stat_calc_multichar.py`:

```
APDCBEGPHJO = Rarity        GJGMIBEOBHP = Level
EOMOGNMMOEJ = EnhanceRate   LMBCLMNIJNA = BreakLevel
EENDAEFLEJO = StarRate      IIPAHNFIJOH = RandRate
```

Refresh `locale_en.json` (names only) with:

```
python -c "import urllib.request,json;d=json.load(urllib.request.urlopen('https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/zzz/locs.json'))['en'];json.dump({k:v for k,v in d.items() if k.startswith(('Avatar_','Item_Weapon_','EquipmentSuit_'))},open('locale_en.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)"
```

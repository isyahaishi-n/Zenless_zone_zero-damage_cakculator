# ZZZ Skill Multiplier Data — Progress Report

Laporan ini buat AI agent yang lanjutin kerjaan reverse-engineering data skill
ZZZ dari file datamine `git.mero.moe/dimbreath/ZenlessData`. Semua klaim di
bawah ini **CONFIRMED** (diverifikasi ke wiki Prydwen/data resmi) kecuali
ditandai eksplisit sebagai **INFERRED** (dugaan dari pola, belum tervalidasi
penuh).

## File yang relevan

- `AvatarSkillTemplateTb.json` — data multiplier per hit/skill (CONFIRMED)
- `AvatarSkillLevelTemplateTb.json` — cost upgrade skill per level (bukan multiplier)
- `AvatarSkillDesTemplateTb.json` — nama/title skill (per avatar+skill_type, bukan per hit)
  - **UPDATE**: baris `PDJMFJOFNEF==1` berisi mapping EKSPLISIT hit→nama
    via field `KLPLBBJABBL` (lihat section baru di bawah)
- `avatars.json` — base stat karakter (Enka store format, sudah dipakai di `verify.py`)
- `TextMap_ENTemplateTb.json` — **SUDAH ADA di environment** (411k entri, flat
  dict `{text_key: english}`). Key-nya langsung string deskriptif kayak
  `Anbi_Skill_Normal_Title` -> "Basic Attack: Turbo Volt". Open item #1
  (resolve nama skill ke English) SELESAI.
- `locs.json` — file ini SUDAH TIDAK ADA lagi di environment. Kalau perlu,
  pakai `TextMap_ENTemplateTb.json` (superset, lebih lengkap).

## Field mapping — `AvatarSkillTemplateTb.json`

Struktur: `{"MLOEFHJHCID": [ {row}, {row}, ... ]}`

| Field obfuscated | Arti (CONFIRMED) |
|---|---|
| `DALBKGGEJEF` | Skill/hit ID. 4 digit pertama = Avatar ID |
| `GLENCFMNKMF` | SkillType (lihat enum di bawah) |
| `IKAABAIDFAO` | Damage% di Level 1 (basis point, /100 = persen) |
| `DGHHKAHHIPM` | Damage% growth per level |
| `OMFJHOLBIKA` | Daze% di Level 1 |
| `KICLLNBEAEN` | Daze% growth per level |
| `ECHPKCNANMI` | SpRecovery |
| `KAGFAENFDCH` | AttributeInfliction (Anomaly buildup) |
| `BLGOMFMHNKA` | FeverRecovery (Decibel gain) |

**Formula (CONFIRMED, diverifikasi ke Prydwen untuk Anby & Miyabi):**
```
Damage(level) = (IKAABAIDFAO + (level-1) * DGHHKAHHIPM) / 100   -> persen
Daze(level)   = (OMFJHOLBIKA + (level-1) * KICLLNBEAEN) / 100   -> persen
```

**Baris placeholder (CONFIRMED):** kalau `IKAABAIDFAO == 0 AND OMFJHOLBIKA == 0`,
itu slot kosong/nggak dipakai, HARUS di-skip. Dikonfirmasi lewat Miyabi
SkillType 3: 2 dari 6 baris kosong total di semua field.

## SkillType enum (`GLENCFMNKMF`) — CONFIRMED

| Value | Arti |
|---|---|
| 0 | Basic Attack |
| 1 | Special Attack (EX) |
| 2 | Dodge |
| 3 | Chain Attack + Ultimate (2 sub-skill beda kurva, 1 angka level yang sama) |
| 5 | Core Skill — **TIDAK ADA di file ini**, sistemnya beda (pakai `CoreSkillEnhancement`, bukan level biasa). Sumber datanya belum ketemu. |
| 6 | Assist |

Catatan penting soal SkillType 3: in-game/wiki nyebutnya "Chain Attack" dan
"Ultimate" itu 2 nama berbeda, tapi keduanya level-up bareng (1 baris cost di
`AvatarSkillLevelTemplateTb.json`). "Ultimate" itu SECARA RESMI sub-varian
dari kategori "Chain Attack" (Primary Type tetap Chain Attack, Secondary Type
"Ultimate") — bukan skill terpisah dengan slot level sendiri.

## Grouping hit -> nama skill — TERATASI via explicit mapping (CONFIRMED)

### Field `KLPLBBJABBL` = referensi eksplisit hit→section title (CONFIRMED)

Struktur `AvatarSkillDesTemplateTb.json` punya 2 lapis baris:
- `PDJMFJOFNEF==0`: entri skill lengkap (LECKPHICFOA=title key, DLADMENPFPD=desc key)
- `PDJMFJOFNEF==1`: baris property display in-game. Baris dengan
  `DLADMENPFPD` berakhiran `_Title` + `KLPLBBJABBL` kosong = **header
  section**; baris berikutnya punya `KLPLBBJABBL` berisi referensi
  eksplisit seperti `{Skill:1091027, Prop:1001}` yang menautkan hit_id
  (`DALBKGGEJEF` di `AvatarSkillTemplateTb.json`) ke section title itu.

Prop yang muncul (CONFIRMED, distribusi di seluruh file): `1001` =
DamageRatio (1131 refs), `1002` = BreakStunRatio/Daze (1274 refs).
Ada juga pola gabung `{{Skill:A, Prop:X} + {Skill:B, Prop:X}}` untuk
property yang di game ditampilin sebagai jumlah beberapa hit (mis. Chain
Attack Miyabi = 1091015+1091016+1091017).

**Coverage (dihitung atas semua hit non-placeholder karakter playable):**
91.4% (1261/1380) hit punya nama eksplisit via mapping ini.

### Heuristic lama sekarang cuma fallback

Heuristic "kalau `jumlah_hit % jumlah_nama == 0`, grup hit berurutan"
masih ada di kode sebagai fallback untuk hit tanpa referensi eksplisit,
tapi PRIMARY path sekarang explicit mapping. Cross-check lama (58 karakter,
SkillType 3): 51/58 pembagian bulat, 7 anomali — **semua 7 anomali itu
sekarang TERATASI oleh explicit mapping**:

- `1551`: 7 hit / 2 nama — ternyata "Basic Attack: Emberglow" (3 hit) +
  "Basic Attack: Celestial Light" (4 hit), dua basic attack mode beda.
  Heuristic sequential gagal karena 7 % 2 != 0, explicit mapping benar.
- `1031` (Billy): 13 hit di SkillType 1 — 7 di antaranya hit tersembunyi
  (volley varian EX Special, nilai dmg duplikat dari hit utama).

### Hit tersembunyi (hidden hits) — temuan baru, CONFIRMED via pola

Hit yang TIDAK pernah direferensikan `KLPLBBJABBL` = hit internal yang
NGGAK ditampilkan di UI game (follow-up, varian enhance, proc terpasif).
Cocok dengan `SkillListConfigTemplateTb.json` (daftar skill yang tampil
di UI) — hidden hits memang bukan entri di sana.

**Klasifikasi (diteliti via cross-check 3 karakter dengan pola sama:
Miyabi/1091, Seed/1461, Cissia/1521):**

1. **Varian proc "does not cause Daze" (CONFIRMED utk Cissia)** — dupe
   persis dari hit visible (damage curve identik) tapi `OMFJHOLBIKA=0`.
   Bukti teks M4/M6 Cissia: "triggers 1 special instance of Corrode Bone
   ... **This Corrode Bone does not cause Daze**" — persis matching row
   `1521022` (dupe `1521019` Corrode Bone 126.8%, daze 155.1% -> 0).
   Hanya 3 karakter playable yang punya pola daze=0 dupe ini:
   `1091006` (Miyabi, dupe hit-3 Kazahana), `1461011` (Seed, dupe
   Downfall Second Form), `1521022` (Cissia, dupe Corrode Bone).
   Trigger persis Miyabi/Seed belum ketemu di teks (INFERRED).

2. **Proc damage multiplier FIXED / konstan semua level** —
   `DGHHKAHHIPM=0` (zero growth) karena proc TIDAK ikut level skill.
   Identitas persisnya beda-beda per karakter dan NYARINYA SUSAH:
   - Miyabi `1091035` (720%): DUGAAN LAMA "Frostburn - Break" SUDAH
     DITOLAK (lihat section Miyabi di bawah — 720 != 750 verified
     Prydwen). Masih unknown.
   - Cissia `1521021` (1000%, daze 0, anom 0): kemungkinan "Umbral
     Venom Flourish" (burst proc 4x Corrode Bone) — INFERRED.
   - Seed `1461021` (495%, daze 0, anom 0): proc murni — unknown.
   - Billy `1031107-13`: duplikat nilai `1031103-06`, varian tersembunyi
     EX Special.

   PELAJARAN: angka fixed% di AvatarSkillTemplateTb TIDAK selalu cocok
   dengan teks mekanik karakter — angka core passive/mechanic unik
   disimpan di tabel lain (belum ketemu, lihat open item #2).

Miyabi basic combo ternyata bernama "Basic Attack: Kazahana" (5 hit),
terpisah dari charge "Basic Attack: Shimotsuki".

Di kode, hit ini diberi flag `is_hidden=True` + `name=None`. Angka
multiplernya tetap valid (dipakai game secara internal) — buat damage
calculator DPS-realistis, hidden hits proc JANGAN dihitung sebagai bagian
combo normal; hitung terpisah dengan trigger rate-nya masing-masing.

### Hit multi-title (7 kasus, CONFIRMED)

7 hit ter-map ke >1 section title (varian enhance yang share hit row):
mis. Astra `1311005` (Singing/Singing Exit/Singing Perfect), Caesar
`1071015` (ExSpecial_01/02), Evelyn `1321016` (ExQTE/ExQTE_02).
Kode menyimpan semua title, digabung dengan " / ".

## Temuan penting: sistem non-combo (charge-based) — CONFIRMED utk Miyabi

Basic Attack Miyabi BUKAN 5-hit combo linear biasa — itu sistem
**"Shimotsuki Stance"**: 3 charge level (One/Two/Three Slash), tiap charge
level = 1 baris terpisah di `AvatarSkillTemplateTb.json`, magnitude JAUH
lebih besar dari baris combo biasa.

Hit ID yang cocok (SkillType 0, Miyabi/1091), tervalidasi ke wiki persis:
- `1091027` = Charge Lv.1 Slash (LV1: 454.7% / LV12: 910.1%)
- `1091028` = Charge Lv.2 Slash (LV1: 858.1% / LV12: 1717.2%)
- `1091029` = Charge Lv.3 Slash (LV1: 2141.1% / LV12: 4282.8%)

**UPDATE (via explicit mapping):** 13 baris SkillType 0 Miyabi sekarang
semua teridentifikasi:
- `1091001-005` = "Basic Attack: Kazahana" (combo normal 5 hit)
- `1091027-029` = "Basic Attack: Shimotsuki" (3 charge level)
- `1091006` (62.8%, daze 0) = hidden hit — tidak direferensikan UI
- `1091035` (720.0% konstan semua level) = hidden hit — TAPI identitas
  "Frostburn - Break 720%" DITOLAK setelah verifikasi Prydwen: Core Passive
  "Searing Cold" Lv.1 = 750% (match teks `Unagi_UniqueSkill_01_Desc`),
  bukan 720%. Sumber numerik Core Passive = tabel lain via ID `410910` /
  `12254028` (field ACOLKGPPGKK/ONMHBHPOLHI di baris SkillType 5 des
  template) — tabel itu BELUM ada di environment. Fungsi sebenarnya
  `1091035` masih unknown.

**Implikasi buat agent lanjutan:** JANGAN asumsikan semua karakter punya
struktur Basic Attack yang sama (N-hit combo sekuensial). Ada kemungkinan
banyak karakter lain juga punya sistem non-standar (charge, stance, toggle,
dll) yang butuh identifikasi manual per karakter via wiki cross-check,
sama kayak kasus Miyabi ini.

## Source of truth kalau ada konflik data

Kalau angka dari `AvatarSkillTemplateTb.json` beda sama wiki: **PERCAYA JSON**
(langsung dari game files), BUKAN wiki biligame — sudah ada 1 kasus konkret
di mana wiki biligame salah (growth Ultimate Anby: wiki bilang 136.6%,
JSON+Prydwen bilang 137.6%, JSON+Prydwen yang benar).

## Kode yang udah jadi

`skill_lookup.py` — berisi:
- `build_skill_index()` — index semua hit row per (avatar_id, skill_type)
- `compute_damage()` / `compute_daze()` — formula scaling per level
- `get_skill_multipliers()` — lookup + filter placeholder rows
- `get_skill_names()` — ambil nama non-kosong dari `AvatarSkillDesTemplateTb.json`
  (baris PDJMFJOFNEF==0)
- `build_explicit_name_map()` — **BARU**: parse `KLPLBBJABBL` jadi
  `{hit_id: [title_key, ...]}` (explicit mapping, 91.4% coverage playable)
- `load_textmap()` — load `TextMap_ENTemplateTb.json`, resolve title key ->
  English
- `compute_damage_output()` — gabungin ke ATK final -> raw damage, naming
  via explicit mapping (primary) + heuristic sequential (fallback), flag
  `is_hidden` untuk hit tanpa referensi
- `main()` — 4 test verifikasi otomatis (Anby Chain/Ultimate, Miyabi
  charge Lv1+Lv12, anomali 1551, hidden hits Billy)

Verifikasi terakhir (semua PASS, angka persis match):
- Anby SkillType 3 Lv12: Chain 1085.8%/216.0%, Ultimate 3026.2%/1487.7%
- Miyabi charge 1091027/28/29: LV1 454.7%/858.1%/2141.1%,
  LV12 910.1%/1717.2%/4282.8%
- 1551: Emberglow (3 hit) + Celestial Light (4 hit) resolve benar

## Yang belum dikerjakan / open items

1. ~~**Nama skill belum resolve ke teks Inggris**~~ — SELESAI via
   `TextMap_ENTemplateTb.json` + `build_explicit_name_map()`.
2. **Core Skill (SkillType 5)** — SELESAI (sesi 2026-08-30, lihat
   `core_skill_lookup.py` + readme3.md). Ringkasan:
   - Sumber: `AvatarPassiveSkillTemplateTb.json` (di-download dari
     git.mero.moe — curl.exe works, catatan lama "fetch tool gagal" obsolete).
     58 karakter x 6 rank (2-7). Ekuivalen persis dengan
     `CoreEnhancementProps` di avatars.json (Enka).
   - Stat bonus per rank = field `KBOACPNJNKF`, KUMULATIF (Anby rank 7:
     Impact +18, ATK +75; Miyabi rank 7: Anomaly Proficiency +90, ATK +75).
   - Property ID via `PropertyTemplateTb.json`: 12101=ATK flat, 12201=Impact,
     20101=CRIT Rate(/10000), 21101=CRIT DMG(/10000), 23101=PEN(/10000),
     30501=Energy Regen(/100), 31201="Anomaly Proficiency" display,
     31401="Anomaly Mastery" display (nama internal terbalik dari intuisi —
     diverifikasi via angka Prydwen di 2 karakter).
   - Scaling efek = teks `<Codename>_UniqueSkill_01..07_Desc` (TextMap).
   - ID lama `410910`/`12254028` ternyata BUKAN foreign key: ACOLKGPPGKK =
     410000+(avatar_id%1000)*10 (derived UI), ONMHBHPOLHI = UI sort index.
   - Terverifikasi Prydwen (Miyabi & Anby): final stats + curve efek semua
     match (Miyabi ATK 880.7/880, Frostburn 750→1500; Anby ATK 659/658,
     Impact 136/136, Daze 32→64).
3. ~~**7 karakter anomali grouping**~~ — SELESAI, teratasi explicit mapping.
4. **Karakter dengan sistem non-combo** (kayak Miyabi Shimotsuki Stance) —
   explicit mapping sekarang mengidentifikasi charge hit (1091027-29 =
   "Basic Attack: Shimotsuki"), tapi DETEKSI OTOMATIS "sistem non-standar"
   belum ada. Sinyal yang bisa dipakai: hit basic attack dengan magnitude
   jauh lebih besar + nama section beda dari combo normal.
5. **CRIT/RES/DMG Bonus belum masuk formula damage final** — scope
   `compute_damage()` sekarang cuma `multiplier% x ATK`, belum termasuk CRIT
   Rate/DMG, enemy RES, dll. Itu formula damage yang lebih besar, function
   terpisah, belum dikerjakan.
6. **Data musuh (RES per elemen)** — belum ada sama sekali. Kemungkinan ada
   di `bosses.json` dari repo `zzz_calculator-main` yang pernah di-cek
   sebelumnya (belum diproses).
7. **Hit tersembunyi (hidden hits)** — udah ke-flag dan ke-nomor, tapi makna
   gameplay-nya (kapan hit itu ke-trigger) belum diidentifikasi. Perlu
   cross-check ke data `AvatarSkillInfoTemplateTb.json` /
   `AvatarSkillRecoTemplateTb.json` yang belum dieksplor.

## Metodologi verifikasi yang dipakai (buat konsistensi ke depan)

1. Ambil angka dari raw JSON, hitung pakai formula
2. Cross-check ke Prydwen (bukan wiki biligame — pernah kebukti salah sekali)
3. Kalau nggak match, cek dulu apakah itu masalah field mapping, formula,
   atau cuma versi data yang beda (patch lag)
4. Jangan generalize pola dari 1 karakter — selalu cross-check minimal ke
   2-3 karakter yang strukturnya beda sebelum anggap itu rule universal
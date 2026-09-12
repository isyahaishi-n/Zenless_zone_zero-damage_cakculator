# TODO — ZZZ Damage Calculator (untuk AI agent lanjutan)

Konteks lengkap ada di `SKILL_DATA_PROGRESS.md` (a.k.a `readme2.md`). File ini
cuma daftar kerjaan aktif, bukan dokumentasi temuan.

## 🔴 Sedang dikerjakan — (kosong, lihat open items)

## 🟡 Open items lain

- [ ] **Fungsi gameplay hidden hits** — kapan hit tersembunyi (kayak
      `1091006`, `1091035`, Billy `1031107-113`) ke-trigger di actual combat.
      Kemungkinan besar jawabannya ada di `AbilityConfigTemplateTb.json`
      (2478 rows, sudah ter-download lokal) — engine ability config dengan
      referensi string kayak "AbyssS2_Artifact_1339701", ada mention
      "Unagi"/"Anbi". Belum dieksplor, ini rabbit hole.
- [ ] **Formula damage final** — CRIT Rate/DMG, enemy RES, dll belum masuk.
      Raw damage per hit (`multiplier% x ATK`) SUDAH jalan di stat calc.
- [ ] **Data musuh (RES per elemen)** — cek `bosses.json` dari
      `zzz_calculator-main.zip` yang udah pernah diliat sebelumnya, belum
      diproses ke format yang kepake.

## 🟢 Selesai (jangan dikerjain ulang)

- [x] **Regenerasi `wengine_passive_mapped.json` dari teks mentah** (2026-08-31):
      file lama (schema v1) punya effects fabricated — contoh Fusion
      Compiler (14118) dikasih "crit_rate 10%" yang dicopy dari weapon
      lain; teks aslinya cuma ATK +12..24% & AP +25..50. Generator baru
      `wengine_passive_gen.py`: semua angka diekstrak mekanis dari
      `Weapon_TalentDes_*` phase 1-5 (TextMap + ENOverwrite merge),
      di-align antar phase via skeleton, tiap effect bawa `evidence_p1`
      + `raw_texts` p1-p5 (auditable). Audit invariant: setiap nilai
      curve HARUS muncul di teks phase-nya (anti-fabrication) — 95/95
      weapon PASS, 0 needs_review, 0 unparsed. Field title/desc key di
      `wengine.md` sebelumnya kebalik — sudah dikoreksi.
- [x] **Wire skill multipliers ke `zzz_enka_stat_calc_multichar.py`**
      (2026-08-30): section baru `-- Skill damage --` per avatar —
      nama EN per hit (explicit mapping + TextMap + Overwrite merge),
      DMG%/Daze% di level skill aktual (termasuk bump M3/M5), raw damage
      pakai ATK final. Enka `SkillLevelList.Index` == `GLENCFMNKMF`
      (0/1/2/3/6; 5=Core di-skip, stat bonus-nya sudah lewat
      CoreEnhancementProps). CATATAN: di Windows console WAJIB
      `python -X utf8` (ada nama skill non-ASCII; tanpa itu stdout
      berhenti diam-diam di tengah avatar).
- [x] **Merge TextMap Overwrite** — `skill_lookup.load_textmap()` sekarang
      auto-merge `TextMap_ENOverwriteTemplateTb.json` (257 entri supplement;
      tanpa ini keys kayak `Remielle_Skill_FinishEx_Title` unresolved).

- [x] **Core Skill (SkillType 5) numeric table — SELESAI** (2026-08-30):
  - [x] `AvatarPassiveSkillTemplateTb.json` ter-download (58 karakter x 6 rank).
        Field mapping lengkap + property ID translation di docstring
        `core_skill_lookup.py`.
  - [x] ID `410910`/`12254028` BUKAN foreign key ke tabel numerik:
        `ACOLKGPPGKK = 410000 + (avatar_id % 1000) * 10` (derived UI ID),
        `ONMHBHPOLHI` = index sekuensial urutan rilis utk UI sorting.
  - [x] Stat bonus per rank = `KBOACPNJNKF` (KUMULATIF, bukan increment).
        Ekuivalen persis dengan `CoreEnhancementProps` di avatars.json (Enka).
  - [x] Scaling efek core passive = teks `<Codename>_UniqueSkill_01..07_Desc`
        di TextMap (angka embedded di teks, match Prydwen utk Miyabi & Anby).
  - [x] Verifikasi Prydwen: Miyabi ATK 880.7/880, AnomProf 238/238, Anby
        ATK 659/658, Impact 136/136, HP 7500.7/7500, DEF 612.6/612 — semua
        match. Frostburn curve 750→1500 (+125/lvl) & Anby Daze 32→64 match.
  - [x] Modul `core_skill_lookup.py` + 4 test otomatis (semua PASS).
- [x] Field mapping `AvatarSkillTemplateTb.json` (formula damage/daze)
- [x] Explicit name mapping via `KLPLBBJABBL` (91.4% coverage, 58 karakter playable)
- [x] Hidden hit detection (flag `is_hidden`, angka tetap valid)
- [x] 7 karakter anomali grouping — semua ter-resolve
- [x] `TextMap_ENTemplateTb.json` resolve ke nama Inggris — semua tervalidasi
      (Kazahana, Shimotsuki, Emberglow, Celestial Light, dll — cocok 100%)
- [x] Mindscape M3/M5 skill-level bump logic (+2 per tingkat, stacking)
- [x] Semua 4 test case di `skill_lookup.py` PASS

## Catatan metodologi (jangan dilanggar)

1. Source of truth kalau ada konflik: **JSON mentah**, bukan wiki biligame
   (pernah kebukti salah sekali — growth Ultimate Anby).
2. Selalu cross-check ke **Prydwen**, bukan biligame.
3. Jangan generalize pola dari 1 karakter — validasi ke minimal 2-3 karakter
   struktur beda dulu sebelum dianggap rule universal.
4. **UPDATE 2026-08-30**: `curl.exe` BISA akses `git.mero.moe` langsung dari
   environment (catatan lama soal fetch tool gagal sudah obsolete):
   ```
   curl.exe -s -o <file>.json "https://git.mero.moe/dimbreath/ZenlessData/raw/branch/master/FileCfg/<NamaFile>.json"
   ```
   Listing semua 1654 file bisa via Gitea API:
   `https://git.mero.moe/api/v1/repos/dimbreath/ZenlessData/contents/FileCfg`
   (contoh hasil: `filecfg_list.json` lokal).
5. File datamine yang sekarang ada lokal (hasil sesi ini):
   `AvatarPassiveSkillTemplateTb.json`, `AvatarPassiveSkillDesTemplateTb.json`,
   `AvatarPassiveDescTemplateTb.json`, `AbilityPropertyTemplateTb.json`,
   `AbilityConfigTemplateTb.json`, `BuffLevelCoefTemplateTb.json`,
   `PropertyTemplateTb.json`.

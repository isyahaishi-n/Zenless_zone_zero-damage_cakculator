# TODO — ZZZ Damage Calculator (untuk AI agent lanjutan)

Update terbaru 2026-09-06: **SEMUA item prioritas utama file ini SELESAI.**
Monster stat (DEF/HP/RES/StunTaken) di-crack via korelasi massal
zzz-hakushin-data & terintegrasi (`monster_data.py`, 207 monster by name).
Hidden hits (119 hit / 40 karakter) terklasifikasi lengkap + 3 identitas
CONFIRMED (`hidden_hits_report.md`). Konteks lengkap: `readme2.md` /
`wengine.md` / `hidden_hits_report.md` / `NEXT_STEPS.md`.

## ⚠️ PERINGATAN KRITIS — field name fabrication dari agent lain

**Kejadian nyata**: pesan (ngaku hasil analisis, sitasi link
`utm_source=chatgpt.com`) ngasih 8 field name buat HP/DEF/6-RES Tyrfing.
**SEMUA field name itu TIDAK ADA** di file JSON asli waktu dicek langsung.
Field code APAPUN yang disebut di chat **HARUS di-cross-check dulu ke file
JSON asli** (`field_name in row.keys()`) SEBELUM dipakai. Jangan asumsikan
field code valid cuma karena angkanya masuk akal.

Ada juga file `4301286813178527909.json` (FileCfg, ID numerik 19-digit
gaya GUID) yang diupload TANPA clue asal — dicek, ID-nya **tidak muncul**
di manapun di row Tyrfing (`900011096`). **JANGAN dipakai** sampai ada
bukti ini beneran di-reference dari row Tyrfing atau tabel terkait.

**Metodologi yang terbukti works (2026-09-05)**: korelasi massal dengan
Genshin-Optimizer/zzz-hakushin-data (field un-obfuscated). Join by ID,
hitung match count per pasangan field — mapping benar menang dengan
margin jelas (635/643 exact). Pakai teknik ini sebelum nyerah ke
"dead end". Detail: `monster_data.py` docstring + `TODO_agent.md`
catatan metodologi #7.

## 🔴 Prioritas utama — decode Monster stat — SELESAI 2026-09-05

- [x] **DEF** — `AOIJDIEHABK` × curve1000(L)/100. Tyrfing L60 = 571.68
      (ground truth exact). Dipakai `damage_calc.py` via data asli.
- [x] **HP** — `LPKOMILKOKG` × curve1002(L)/100. Tyrfing L60 =
      51702.92 ≈ 51703 (ground truth exact, terverifikasi independen
      via korelasi 622 monster hakushin — bukan klaim fabricated).
      Tetap benar bahwa HP tidak masuk formula damage per-hit.
- [x] **RES per elemen** — SEMUA 18 field terdecode (6 elemen × 3 jenis:
      Damage/Buildup/Stun Res). Misteri "6 field -2000" terpecahkan:
      itu 2 elemen × 3 jenis RES (Tyrfing: Ice{3} + Ether{3}), BUKAN
      weak ke 6 elemen. Mapping verified 635/643 row via korelasi
      hakushin — terdokumentasi di `monster_data.py`.
      - DamageRes: Phys `ACOFKCMKDOJ`, Fire `FHKIMGJHOOM`, Ice
        `DAHICMDLIDB`, Elec `GOCPMKOMLLA`, Ether `EPCAKNEIANN`,
        Wind `MLNILAMPKDE`
- [x] **Bonus: StunDamageTakenRatio** — `LHPKLCOJKCN`/10000 (Tyrfing
      5000 = +50% = "StunMult 150%" GT; The Defector 2500 = +25%).
      Sudah dipakai Stun Modifier di `compute_final_damage()`
      (`enemy_stunned` param, `run.py --stunned`).
- [x] **Generalize ke musuh lain** — `monster_data.MonsterDB` resolve
      207 monster by name (case-insensitive) via chain
      `OfficialName_Monster_<Codename>` -> config -> sub. CLI:
      `python run.py <uid> --enemy "Haytor" --enemy-level 60`.
      Heuristik varian: exclude hasil upgrade
      (MonsterUpgradeTemplateTb kolom `FIMGJKPCKFO`) + prefix `199`
      (scene/test).

## 🟢 Selesai & tervalidasi (jangan dikerjain ulang)

- [x] Stat panel karakter, skill multiplier, W-Engine passive, set 4pc,
      Mindscape M1/M2/M4/M6 — semua evidence-based
- [x] `damage_calc.py` fungsional, lolos kalibrasi (residual non-crit
      0.064%, crit 0.009%)
- [x] Formula damage CONFIRMED match wiki resmi
      (`zenless-zone-zero.fandom.com/wiki/Damage`)
- [x] Level Factor generality — lookup dinamis dari
      `LevelCurveTemplateTb.json` (curve 1000/2, plateau L60+)
- [x] Cara nemuin Monster mana pun dari nama publik — `monster_data.py`
- [x] **DEF Monster** — confirmed & dipakai, presisi `571.68`
- [x] **HP Monster** — confirmed (51703 exact) & di-resolve `MonsterDB`
- [x] **RES per elemen** — confirmed 18 field, dipakai `get_enemy_stats()`
- [x] Konfirmasi: **HP musuh tidak masuk formula damage per-hit**
- [x] **Stun Modifier + DMG Taken Modifier** — diimplementasi & unit
      tested (2026-09-05)
- [x] **Hidden hits terklasifikasi** (2026-09-06): 119 hit / 40 karakter
      -> 5 kategori struktural (`skill_lookup.py --classify-hidden`):
      70 unique_hidden, 26 fixed_pct_proc, 19 dupe_variant,
      3 dupe_no_daze_proc, 1 daze_only. 3 identitas CONFIRMED via teks
      official exact-match: Lucy `1151027` (M6 boar 300%), Trigger
      `1361023` (M4 Disconnect 200% ATK + 120% Impact-daze), Banyue
      `1471030` (M6 600% Sheer Force). Laporan: `hidden_hits_report.md`.

## Open items lain (prioritas rendah, nggak blocking)

- [ ] **Identifikasi 70 unique_hidden + verifikasi kandidat inferensi**
      (Vivian Abloom 55%, Jane Salchow 60/600%, Cissia Umbral Venom
      Flourish 1000%, Seed 495%, **Miyabi `1091035` 720% — masih total
      unknown**, gak muncul di teks manapun). Butuh anchor gameplay
      (video/wiki per karakter) — data-only sudah mentok. Detail lead
      per hit: `hidden_hits_report.md`.
      Catatan metodologi baru: AbilityConfigTemplateTb row-numbering
      TIDAK align dengan TextMap talent numbering (Lucy_Talent_04 row
      berisi variabel M6) — jangan percaya nama row AbilityConfig tanpa
      cross-check teks.
      Catatan implementasi: proc fixed TIDAK selalu skala ATK (boar
      ATK / Sheer Force / Anomaly Proficiency) — kalau mau ditampilkan
      sebagai proc opsional, perlu stat basis + toggle manual.
- [x] ~~Residual kalibrasi 0.064%~~ — **SOLVED 2026-09-06 via strip-test
      user** (`1303558818v2`–`v4`: bare/disc-only/wengine-only vs Tyrfing
      L60, 8 angka GT): (1) game TIDAK floor stat per-layer — v3 bare
      membuktikan ATK 880.6952 exact (bukan 880); `StatState.summed()`
      diperbaiki (hapus `math.floor` per layer), panel 2715.64 → 2716.69,
      **residual 0.064% → 0.025%** (selisih 0.27 dari GT 1086); (2)
      formula DEF/PEN tervalidasi di 3 titik PEN berbeda (0/0, 0/18,
      24/0); (3) passive W-Engine S1 +12% tervalidasi (v4); (4) display
      damage = round(raw) — 7/8 titik D exact; (5) sisa off-by-one (full
      D2 1184 vs 1183, v4 C2 1075 anomali) = noise sample, bukan bias
      sistematis. Kalibrasi PASS. Detail: `wengine.md` "STRIP-TEST".

## Catatan metodologi (jangan dilanggar)

1. Source of truth kalau ada konflik: **JSON mentah**, bukan wiki biligame
2. Selalu cross-check ke **Prydwen** atau **wiki fandom resmi**, bukan
   biligame, bukan honeyhunterworld via hasil ChatGPT search
3. Jangan generalize pola dari 1 karakter/monster — validasi ke minimal
   2-3 dulu
4. **Verifikasi ulang APAPUN dari agent lain** sebelum dipercaya — field
   code HARUS dicek `in row.keys()` dulu. File yang diupload tanpa
   provenance/clue asal-usul JANGAN dipakai sampai ada bukti keterkaitan
5. Untuk conditional effects: pakai TOGGLE MANUAL (`enabled: bool`),
   JANGAN coba deteksi trigger otomatis
6. Formula damage sudah dikonfirmasi match wiki resmi — cross-check dulu
   sebelum ubah lagi
7. **HP musuh tidak dibutuhkan untuk kalkulasi damage per-hit** — jangan
   treat sebagai blocker prioritas tinggi
8. **Display-data source (UI/SkillList/Param table hakushin dsb.) gak
   akan pernah berisi hidden hits** — by design. Buat identifikasi
   hidden hits, satu-satunya sumber data-only = teks talent/mindscape
   (`Talent_0X_Desc` / `UniqueSkill_XX_Desc` / `*_Upgrade_Desc` di
   ENOverwrite) dicocokkan ke angka fixed proc; sisanya butuh gameplay
   anchor eksternal.

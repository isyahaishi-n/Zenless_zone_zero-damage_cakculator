# Hidden Hits — Laporan Investigasi Lengkap (2026-09-06)

Investigasi item "Fungsi gameplay hidden hits" dari `TODO_agent2.md` / `readme3.md`.
**119 hidden hits di 40 karakter playable** — semua sudah diklasifikasikan struktural,
3 teridentifikasi penuh via teks official, sisanya punya kategori + kandidat inferensi.

## Rekap definisi

Hidden hit = row `AvatarSkillTemplateTb.json` yang TIDAK pernah direferensikan
`KLPLBBJABBL` di `AvatarSkillDesTemplateTb.json` (UI display formula), bukan row
kosong-total. Multiplier damage/daze-nya tetap valid (dipakai engine internal).

## Metodologi (yang dicoba, supaya gak diulang)

1. **Hakushin character data** (Genshin-Optimizer/zzz-hakushin-data, 60 file):
   - `SkillList` = daftar UI doang (12 entri/karakter — sama kayak visible).
   - `Skill.Description[].Param[]` = display formula per hit — **0 dari 119 hidden
     hits muncul** (by design: hidden = tidak pernah di-display).
   - Kesimpulan: display-data source apapun TIDAK akan berisi hidden hits.
2. **AbilityConfigTemplateTb.json lokal** (2478 rows): punya `AS_*` server
   variables per ability (Talent/UniqueSkill/ExQTE/ChargeAttack). MASALAH:
   numbering row TIDAK selalu align dengan TextMap talent numbering (contoh:
   `Lucy_Talent_04` row berisi `AS_Attack05SkillDamageRatio:3.0` padahal teks
   M4 Lucy = CRIT DMG +10%; yang match teks M6 Lucy = boar 300%). Berguna buat
   cross-check angka, TIDAK bisa dipakai sendirian buat ID trigger.
3. **Teks TextMap** (`Talent_0X_Desc`, `UniqueSkill_XX_Desc`,
   `Skill_*_Upgrade_Desc` di ENOverwrite): sumber identifikasi TERBAIK —
   pola "dealing DMG equal to X% of ..." bisa dicocokkan ke angka fixed proc.

## Klasifikasi struktural 119 hits (final)

| Kategori | Jumlah | Definisi | Implikasi kalkulator |
|---|---|---|---|
| `unique_hidden` | 70 | damage curve unik, tampil di engine internal (varian enhanced, combo tambahan) | per-hit valid, trigger per karakter — perlu inferensi manual |
| `fixed_pct_proc` | 26 | `DGHHKAHHIPM=0` (growth 0) → damage % KONSTAN semua level skill | proc mechanic (talent/M-core), TIDAK ikut level skill — scaling stat lain (ATK/Sheer Force/AP) |
| `dupe_variant` | 19 | damage curve IDENTIK dengan hit visible (varian enhance yang share multiplier) | tidak perlu dihitung terpisah — sudah terwakili hit visible-nya |
| `dupe_no_daze_proc` | 3 | dupe visible TAPI `OMFJHOLBIKA=0` → proc "does not cause Daze" (pola Cissia M4 "special instance ... does not cause Daze") | proc bonus tanpa daze — hit tambahan di atas combo normal |
| `daze_only_variant` | 1 | `IKAABAIDFAO=0`, daze besar (1471028 Banyue) | murni daze, bukan damage |

## Identitas TERIDENTIFIKASI (teks exact-match, CONFIRMED)

| Hit | Karakter | Angka | Identitas | Sumber teks |
|---|---|---|---|---|
| `1151027` | Lucy | 300% fixed, daze 41.7% | **M6 proc**: "guard boar drop from the sky ... explosion, dealing Fire DMG equal to 300% of the guard boar's ATK" (saat ally EX Special dalam Cheer On) | `Lucy_Talent_06_Desc_01` |
| `1361023` | Trigger | 200% fixed, daze 120% | **M4 "Disconnect"**: "dealing additional DMG equal to 200% of Trigger's ATK and inflict Daze equal to 120% of Trigger's Impact" — **daze 120% match persis field** (daze base 12000) | `Trigger_Talent_04_Desc_01` |
| `1471030` | Banyue | 600% fixed, daze 0 | **M6 proc**: "deals Fire DMG equal to 600% of his Sheer Force" (saat Crushing Peaks dalam Vidyaraja) — **scaling Sheer Force, BUKAN ATK** | `BanYue_Talent_06_Desc_01` |

Catatan penting: Lucy `1151027` juga match row AbilityConfig `Lucy_Talent_04` →
`AS_Attack05SkillDamageRatio:3.0` (300%) — bukti numbering AbilityConfig
bergeser relatif ke TextMap talent (row "Talent_04" menyimpan variabel M6).
**Jangan percaya nama row AbilityConfig tanpa cross-check teks.**

## Kandidat inferensi kuat (angka match tapi trigger belum 100% pasti)

- `1331020` Vivian 55% fixed — teks `Vivian_UniqueSkill_XX_Desc` "Abloom"
  menyebut scaling per 10 AP (bukan fixed ATK); 55% perlu verifikasi lanjut.
- `1261028`/`1261029` Jane 60%/600% fixed (daze 0) — Jane M6 = 1600% AP
  (Anomaly Proficiency, bukan 600%); 60/600 kemungkinan komponen Salchow Jump
  Finishing Move (teks `JaneDoe_Skill_Branch_Upgrade_Desc` tanpa angka).
  Jane `Talent_03`/`Talent_05` textMap utama = "PlaceHolder" — data teks
  belum lengkap.
- `1521021` Cissia 1000% fixed (daze 0) — teks M6 "Umbral Venom Flourish"
  burst (4x Corrode Bone) — dugaan lama `readme2.md`, masih INFERRED.
- `1461021` Seed 495% fixed (daze 0) — proc murni, unknown.
- `1091035` Miyabi 720% fixed — **MASIH UNKNOWN**. Dugaan "Frostburn Break"
  sudah DITOLAK (Searing Cold = 750-1500%, verified Prydwen). 720% tidak
  muncul di teks manapun (TextMap/ENOverwrite) maupun AbilityConfig Miyabi.
  Kemungkinan besar internal stance/charge mechanic tanpa teks display.

## Temuan struktural tambahan

- Fixed proc (26 hit) TIDAK selalu skala ATK: Lucy boar = "boar's ATK"
  (stat boar, bukan Lucy), Banyue = Sheer Force, Jane M6 = Anomaly Proficiency.
  → `compute_final_damage()` perlu tahu stat basis proc kalau mau akurat;
  multiplier % doang tidak cukup untuk proc-proc ini.
- Pola pasangan assist Miyabi `1091033`/`1091034` (dmg sama 170.5%+15.5%/lvl,
  daze beda 170.5% vs 852.5%) = varian assist kondisi berbeda (normal vs
  enhanced), sama kayak pola dupe di karakter lain.
- `1021018` (Anby, type 2/Dodge) hidden: 223% dmg — varian Dodge Counter
  enhanced (Anby punya Dodge Counter berantai) — INFERRED.

## Daftar lengkap 119 hit per kategori

(dmg dalam % base L1, gr = growth %/level, daze dalam % base L1)

### fixed_pct_proc (26) — angka konstan semua level
```
1051 Yidhari   1051022  dmg 275    daze 0
1061 Corin     1061032  dmg 140.4  daze 108
1091 Miyabi    1091035  dmg 720    daze 44      <- unknown identity
1151 Lucy      1151027  dmg 300    daze 41.7    <- M6 boar explosion CONFIRMED
1221 Yanagi    1221027  dmg 1440   daze 0
1241 ZhuYuan   1241027  dmg 880    daze 0
1261 Jane      1261028  dmg 60     daze 0
1261 Jane      1261029  dmg 600    daze 0       <- kandidat Salchow/proc AP
1331 Vivian    1331020  dmg 55     daze 0       <- kandidat Abloom
1341 Zhao      1341021  dmg 953.4  daze 52.3
1341 Zhao      1341022  dmg 5.5     daze 0
1361 Trigger   1361023  dmg 200    daze 120     <- M4 Disconnect CONFIRMED
1371 Yixuan    1371027  dmg 1200   daze 374.1
1391 JuFufu    1391021  dmg 720    daze 245
1401 Alice     1401022  dmg 720.5  daze 346.5
1411 Yuzuha    1411025  dmg 600    daze 0
1411 Yuzuha    1411026  dmg 381.4  daze 146.7
1431 YeShunguang 1431036 dmg 1000  daze 0
1451 Lucia     1451025  dmg 883.8  daze 256.8
1461 Seed      1461021  dmg 495    daze 0
1471 Banyue    1471030  dmg 600    daze 0       <- M6 Sheer Force CONFIRMED
1501 Aria      1501023  dmg 777    daze 298.9
1521 Cissia    1521020  dmg 450    daze 0
1521 Cissia    1521021  dmg 1000   daze 0       <- kandidat Umbral Venom Flourish
1531 BillySP   1531005  dmg 212.7  daze 77.8
1531 BillySP   1531022  dmg 1200   daze 150
```

### dupe_no_daze_proc (3) — pola "special instance ... does not cause Daze"
```
1091 Miyabi    1091006  = dupe hit-3 Kazahana (62.8%), daze 0   [trigger INFERRED]
1461 Seed      1461011  = dupe Downfall 2nd form (989.4%), daze 0 [trigger INFERRED]
1521 Cissia    1521022  = dupe Corrode Bone (126.8%), daze 0     [M4 Decidedness CONFIRMED via teks]
```

### daze_only_variant (1)
```
1471 Banyue    1471028  dmg 0  daze 95.3 (+growth)
```

### dupe_variant (19) — varian enhanced share multiplier hit visible
```
1031 Billy   1031111/12 = dupe 1031104, 1031113 = dupe 1031106 (EX volley varian)
1081 Ellen?  1081005/06 = dupe 1081004
1111 ( Soldier11 ) 1111005 = dupe 1111001
1131 ( Soldier0Anby ) 1131025 = dupe 1131026
1151 Lucy   1151007 = dupe 1151008, 1151011 = dupe 1151012
1181 Grace? 1181016 = dupe 1181005, 1181017 = dupe 1181006
1221 Yanagi 1221026 = dupe 1221023
1241 ZhuYuan 1241009 = dupe 1241006, 1241013 = dupe 1241010
1311 Astra? 1311007 = dupe 1311006
1321 Evelyn? 1321022 = dupe 1321003
1341 Zhao  1341007 = dupe 1341006, 1341024 = dupe 1341023
1361 Trigger 1361021 = dupe 1361008
```

### unique_hidden (70) — damage curve unik, trigger per karakter (lihat output
`skill_lookup.py --classify-hidden` untuk daftar live; ringkasan di file ini tidak
mengulang 70 baris — mayoritas varian enhanced/combo extension tiap karakter).

## Implikasi buat damage calculator

1. **Jangan hitung hidden hits sebagai bagian combo normal** (sudah kebijakan
   lama, `is_hidden` di-skip `run.py` — tetap benar).
2. Proc fixed (26) + no-daze (3) + daze-only (1) = 30 hit yang punya MAKA
   gameplay jelas; kalau mau ditampilkan sebagai "proc opsional", perlu:
   - tahu stat basis (ATK / Sheer Force / AP / boar ATK) — dari teks
   - toggle manual per proc (aturan metodologi #5: JANGAN auto-detect trigger)
3. `dupe_variant` (19) aman diabaikan total (terwakili hit visible).
4. Sisanya `unique_hidden` (70) butuh investigasi per-karakter (gameplay
   video/wiki per karakter) — kerjaan manual, rendah prioritas kalkulator.

## Status item TODO

- [x] Klasifikasi struktural lengkap 119/119 (5 kategori)
- [x] 3 identitas CONFIRMED via teks official exact-match
- [x] Metodologi identifikasi terdokumentasi (teks pattern + AbilityConfig
      numbering caveat)
- [x] Kategorisasi otomatis di `skill_lookup.py` (`classify_hidden_hits()`)
- [ ] Identifikasi 70 unique_hidden — per karakter, butuh sumber gameplay
      (di luar data-only; open, rendah prioritas)
- [ ] Verifikasi kandidat Vivian/Jane/Cissia/Seed/Miyabi — butuh anchor
      gameplay tambahan

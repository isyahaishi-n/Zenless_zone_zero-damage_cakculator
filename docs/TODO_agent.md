# TODO — ZZZ Damage Calculator (untuk AI agent lanjutan)

Update terbaru 2026-09-05: `damage_calc.py` lolos kalibrasi + PUNYA
Stun/DMG Taken modifier. Formula dikonfirmasi cocok ke halaman resmi
wiki (`zenless-zone-zero.fandom.com/wiki/Damage`). **Monster data
(DEF/HP/RES/Stun) SEMUA sudah di-crack & terintegrasi** via korelasi
massal zzz-hakushin-data — lihat `monster_data.py` & `NEXT_STEPS.md`.
File ini cuma daftar kerjaan aktif — konteks lengkap ada di
`SKILL_DATA_PROGRESS.md` / `readme3.md` / `wengine.md`.

## 🔴 Prioritas utama — Level Factor generality — SELESAI

~~konstanta `794` hardcode~~ sudah jadi lookup dinamis:
`load_level_factor_curve()` (curve Id 1000 / 2, plateau di L60+),
`get_level_factor(attacker_level)`, dipakai `compute_def_mult()`
via param `attacker_level`. Sanity check kalibrasi: L60 = 794 persis
(`assert` di `run_calibration()`). Level Curve juga sudah dipakai
buat HP monster (curve 1002) — lihat `monster_data.py`.

## 🟡 Sudah dicoba, dead end — jangan diulang tanpa clue baru

- [x] ~~Cari data Monster (DEF/RES Tyrfing) di MonsterConfigTemplateTb.json
      + MonsterSubTemplateTb.json~~ — BUKAN dead end lagi! TERPECAHKAN
      2026-09-05 lewat metodologi baru: korelasi massal 622 monster
      dengan Genshin-Optimizer/zzz-hakushin-data (field un-obfuscated),
      join by `EBIKJFJOKGP`. 635/643 row exact. Semua field DEF/HP/
      RES/StunTaken + mapping 18 field RES (6 elemen × 3 jenis)
      terdokumentasi di `monster_data.py`. `KNOWN_ENEMIES` hardcode
      di `run.py` SUDAH DIGANTI dengan `monster_data.MonsterDB`
      (signature `get_enemy_stats` tetap).
      Detail temuan:
      - "6 field -2000" = 2 elemen × 3 jenis RES (Dmg/Buildup/Stun)
        — Tyrfing weak Ice+Ether, bukan 6 elemen.
      - DEF Tyrfing 571.68 & HP 51703 & StunDmgTaken +50% = ground
        truth exact dari data asli.

## 🟢 Selesai & tervalidasi (jangan dikerjain ulang)

- [x] Stat panel karakter (base+gear+set 2pc+W-Engine stat+Core Skill)
- [x] Skill multiplier (formula+naming 91.4%+hidden hit flag)
- [x] W-Engine passive (`wengine_passive_mapped.json`) — fabrication lama
      sudah fixed, 73 effect re-verified, 0 mismatch nyata
- [x] Set 4pc (`drive_disc_mapped.json`) — 30/30 suit, teks mentah
      disertakan
- [x] Mindscape M1/M2/M4/M6 (`mindscape_mapped.json`) — 58 karakter,
      evidence-based
- [x] **`damage_calc.py` — SELESAI dan LOLOS kalibrasi**:
  - Loader 3 file mapped, generic (terima weapon_id/set_name/avatar_id
    sebagai parameter, bukan hardcode)
  - Toggle list auto-generate dari 3 sumber, auto-enable unconditional,
    auto-evaluate threshold (mis. Anomaly Mastery >= 115)
  - `compute_final_damage()` — formula CONFIRMED match wiki resmi
    (DEF Mult identik 100%, RES Mult sudah punya slot res_ignore_pcts +
    res_shred_pct meski belum di-exercise di kalibrasi)
  - Tes generalisasi ke kombinasi lain (weapon phase 3, set Thorned Rose,
    Anby M3) — SEMUA match ke sumber independen (wiki table Thorned Rose
    persis cocok)
  - Kalibrasi Miyabi vs Tyrfing: selisih 0.03-0.08% (PASS, toleransi 0.5%)
  - **[2026-09-05] Stun Modifier** — `enemy_stunned` param + `EnemyStats.
    stun_taken_pct` (dari StunDamageTakenRatio monster; unit tested
    1.5x exact buat Tyrfing, +25% The Defector)
  - **[2026-09-05] DMG Taken Modifier** — slot `dmg_taken_pct` /
    `dmg_reduction_pct` di CombatModifiers, formula
    `(1+taken%)/(1-reduction%)` (unit tested 1.6875 exact)
  - **[2026-09-05] Level Factor lookup dinamis** — bukan 794 hardcode

## Open items lain (prioritas rendah, nggak blocking)

- [ ] Fungsi gameplay hidden hits (119 hit di 40 karakter) — kapan mereka
      trigger di combat asli. Lead: `1091035` Miyabi kemungkinan
      "Frostburn - Break" (scaling ke Core Skill level, verified
      750%->1500% linear +130%/level Core Lv1->Lv7), tapi baru 1 dari 119.
      (Catatan baru: cek dulu apakah hidden hit itu daze-only — pola
      damage base 0 + daze besar banyak ketemu pas investigasi
      Defensive Assist; lihat TODO_run_py.md.)
- [x] ~~Residual kalibrasi 0.09% (1085 vs 1086 ground truth)~~ —
      terkonfirmasi 2026-09-05 BUKAN dari DEF (DEF asli 571.68 memberi
      residual identik 0.064%/0.009%). Sumber: flooring chain ATK panel
      Miyabi. Dalam toleransi; ngekejar butuh reverse rounding per-layer
      stat calc — ROI rendah, skip saja.

## Catatan metodologi (jangan dilanggar)

1. Source of truth kalau ada konflik: **JSON mentah**, bukan wiki biligame
2. Selalu cross-check ke **Prydwen** atau **wiki fandom resmi**
   (zenless-zone-zero.fandom.com), bukan biligame
3. Jangan generalize pola dari 1 karakter — validasi ke minimal 2-3
   karakter struktur beda dulu
4. **Verifikasi ulang file "mapped" apapun** yang di-generate agent lain
   sebelum dipercaya — pernah ketemu fabrication (W-Engine CRIT Rate 10%
   dicopy dari weapon lain, ditandain `mapped: true` padahal salah).
   Cross-check ke raw text/JSON dulu.
5. Untuk conditional effects (W-Engine passive, set 4pc, mindscape):
   pakai TOGGLE MANUAL (`enabled: bool`), JANGAN coba deteksi trigger
   otomatis — di luar scope (butuh simulasi combat real-time).
6. **Formula damage sudah dikonfirmasi match wiki resmi** — kalau ada
   penyesuaian formula ke depan, cross-check dulu ke
   `zenless-zone-zero.fandom.com/wiki/Damage` sebelum ubah, jangan
   asumsi dari kalibrasi 1 kasus doang.
7. **[BARU 2026-09-05] Metodologi crack field obfuscated yang terbukti
   works**: korelasi massal dengan zzz-hakushin-data (repo
   Genshin-Optimizer, field un-obfuscated). Join by ID field yang
   sama-sama muncul di kedua dump, lalu hitung match count per pasangan
   field (field lokal × field hakushin) — mapping yang benar menang
   dengan margin jelas (635/643 vs noise ~random). Pakai teknik ini
   kalau ketemu field obfuscated lain yang perlu di-crack, sebelum
   nyerah ke "dead end".

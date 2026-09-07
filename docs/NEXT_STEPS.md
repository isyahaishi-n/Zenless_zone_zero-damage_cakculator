# NEXT STEPS — Setelah `run.py` selesai

Dokumen ini isinya kerjaan yang nunggu SETELAH `TODO_run_py.md` beres.
`run.py` confirmed jalan end-to-end (termasuk fetch Enka beneran —
403 problem di sandbox udah gak terjadi, tested 2026-09-05).

Status update besar 2026-09-05 (lihat "Yang udah kelar" di bawah):
Monster data (HP + RES) SUDAH DI-CRACK & terintegrasi, Stun/DMG Taken
modifier SUDAH diimplementasi. Item prioritas 1 & 4 dari dokumen ini
SUDAH SELESAI.

## ⚠️ Aturan wajib (berlaku terus, dari awal proyek)

Field code APAPUN yang disebut siapapun (user, agent lain, laporan)
**HARUS di-cross-check dulu ke file JSON asli** (`field_name in
row.keys()`) SEBELUM dipakai/dipercaya. Riwayat: pernah ketemu field
name W-Engine yang fabricated (CRIT Rate 10% ditandain `mapped: true`
padahal salah), dan 8 field code Monster data yang fabricated total.
Jangan ulangi kesalahan itu. (Metodologi yang berhasil 2026-09-05:
korelasi massal vs zzz-hakushin-data — 622 monster join, 635/643
row exact. Lihat `monster_data.py` docstring.)

## 1. ~~Selesaikan data Monster (HP + RES per elemen)~~ — SELESAI 2026-09-05

SEMUA terkonfirmasi independen via korelasi massal dengan
Genshin-Optimizer/zzz-hakushin-data (293 file monster, field
un-obfuscated, join by `EBIKJFJOKGP` == hakushin MonsterInfo key):

- **DEF** — `AOIJDIEHABK` (L1 base) × curve1000(L)/100.
  Tyrfing: 36 × 15.88 = **571.68** (ground truth exact).
- **HP** — `LPKOMILKOKG` (L1 base) × curve1002(L)/100.
  Tyrfing: 1123 × 46.04 = **51702.92 ≈ 51703** (ground truth exact).
  Catatan tetap berlaku: HP nggak dipakai formula damage per-hit,
  cuma relevan buat time-to-kill.
- **RES per elemen** — 18 field = 6 elemen × 3 jenis
  (DamageRes / BuildupRes / StunRes), semuanya /10000:
  - Damage: Phys `ACOFKCMKDOJ`, Fire `FHKIMGJHOOM`, Ice `DAHICMDLIDB`,
    Elec `GOCPMKOMLLA`, Ether `EPCAKNEIANN`, Wind `MLNILAMPKDE`
  - Buildup: Phys `HEEFNBCGGGG`, Fire `NFILPFLNIPC`, Ice `DDMBIHOALHL`,
    Elec `BLNPNLJIDME`, Ether `PMGFNHIKHBD`, Wind `JFABMBIMGNA`
  - Stun: Phys `PHCJFMBBDJC`, Fire `PGGMCKBGCGL`, Ice `GDLJANCPPPM`,
    Elec `CHODLLFEEPK`, Ether `FPIFENJCHJH`, Wind `KOFJJDEIGAB`
- **Misteri "6 field -2000" TERPECAHKAN**: itu BUKAN weak ke 6 elemen —
  itu **2 elemen × 3 jenis RES** (Tyrfing: Ice{Dmg,Buildup,Stun} +
  Ether{Dmg,Buildup,Stun}, masing-masing -2000). Game selalu set
  ketiga jenis identik buat weakness. Kontradiksi semu yang dulu
  ("kebanyakan boss weak 2 elemen doang") ternyata konsisten.
- **StunDamageTakenRatio** — `LHPKLCOJKCN`/10000 (Tyrfing 5000 → +50%
  = "StunMult 150%" di ground truth wengine.md; The Defector 2500 → +25%).
- **Varian monster**: sub row prefix `90001...` = varian combat normal;
  hasil upgrade (di kolom `FIMGJKPCKFO` MonsterUpgradeTemplateTb) &
  prefix `199...` (scene/test) dikecualikan resolver.
- **Generalisasi musuh LAIN**: SUDAH otomatis — `monster_data.MonsterDB`
  resolve 207 monster by name (case-insensitive). Chain
  `OfficialName_Monster_<Codename>` -> config -> sub udah jalan
  generik, bukan cuma Tyrfing.
- Match rate korelasi: 635/643 sub row exact (DEF/RES/StunTaken),
  8 sisanya version drift (mis. `900011011`, sub id 4/5/10 test rows).
- **Implementasi**: `monster_data.py` (MonsterDB + resolver), dipakai
  `run.py` via `get_enemy_stats()` (signature tetap, sesuai desain).

## 4. ~~Modifier damage tambahan~~ — SELESAI 2026-09-05

Kedua modifier dari dokumen formula resmi SUDAH diimplementasi di
`damage_calc.py` `compute_final_damage()`:
- **Stun Modifier** — param baru `enemy_stunned: bool`; kalau True,
  damage × (1 + `EnemyStats.stun_taken_pct`) — nilai per-musuh dari
  StunDamageTakenRatio (dari data Monster asli, bukan hardcode
  100%/50%). CLI: `python run.py <uid> --stunned`.
- **DMG Taken Modifier** — slot `dmg_taken_pct` / `dmg_reduction_pct`
  di `CombatModifiers` (aggregate dari stat `dmg_taken_pct` /
  `dmg_reduction_pct` di mapped files), formula
  `(1 + DMG_Taken%) / (1 - DMG_Reduction%)`. Belum ada efek mapped
  yang pakai stat ini (verified: 0 match di 3 file mapped), tapi
  slotnya siap begitu ada (mis. W-Engine "enemies take X% more DMG").
- Kalibrasi Miyabi vs Tyrfing tetap PASS (0.064%/0.009%) — backward
  compatible (default `enemy_stunned=False`).
- Unit tested: stun ratio 1.5 exact utk Tyrfing, dmg-taken mult
  1.35/0.8 = 1.6875 exact.

## 2. Residual kalibrasi (kecil, prioritas rendah) — SUDAH DICEK

Setelah DEF diganti data asli (571.68): residual non-crit 0.064%,
crit 0.009% — SAMA PERSIS dengan sebelumnya, jadi TERKONFIRMASI
sumbernya BUKAN DEF. Sumbernya flooring chain di kalkulasi ATK panel
Miyabi (base stat + gear rounding di beberapa layer), bukan formula
damage. Dalam toleransi 0.5% (PASS); ngekejar 0.064% butuh reverse
rounding per-layer stat calc — ROI rendah.

## 3. Hidden hits — fungsi gameplay-nya — MASIH OPEN (prioritas rendah)

119 hit di 40 karakter yang nggak punya referensi nama eksplisit
(lihat `SKILL_DATA_PROGRESS.md` / `readme3.md` buat list lengkap).
Angka damage/daze-nya valid, tapi belum jelas KAPAN mereka trigger di
combat asli. Progress: `1091035` (Miyabi) kemungkinan "Frostburn -
Break" (verified scaling ke Core Skill level). Baru 1 dari 119 yang
punya lead solid.

Catatan baru 2026-09-05: dari investigasi Defensive Assist (lihat
`TODO_run_py.md`), pola "daze-only hit" (damage base 0, daze besar)
juga mungkin relevan buat sebagian hidden hits — cek dulu apakah
hidden hit itu cuma daze-only sebelum dihabiskan waktu cari
trigger-nya.

## 5. UI/Frontend (kalau mau dilanjutin) — MASIH OPEN

Ada track terpisah dari awal project ini: kalkulator berbasis
TypeScript/Next.js (`zzz-calculator` fork) yang sempat di-integrasiin
sama Enka import buat stat panel doang (bukan damage). Kalau mau
nyambungin `damage_calc.py` (Python) ke situ, perlu either:
  (a) port logic Python ke TypeScript, atau
  (b) bikin API kecil (Python backend, panggil dari frontend TS)
Belum ada keputusan/progress ke arah ini, murni masih ide terbuka.
Sekarang ada data monster asli + stun modifier, port TS-nya juga
tinggal ikutin `monster_data.py` + formula `compute_final_damage()`.

## Prioritas relatif (update 2026-09-05)

Item 1 (Monster RES) & 4 (Stun/DMG Taken) SELESAI. Yang tersisa:
**(3) hidden hits** (rendah prioritas, kerjaan manual) -> **(5) UI**
(scope besar, keputusan arsitektur dulu). Tidak ada blocker lain.

# W-Engine Passive & Conditional Bonus — Kenapa script bilang 969 padahal in-game 1086

Dokumen konteks buat AI agent lanjutan. Cerita lengkap kenapa output damage
simulasi pertama MELESAT dari angka in-game, dan apa saja yang harus
dimodelkan supaya match. Ditemukan 2026-08-30 saat kalibrasi formula damage.

Worklist aktif proyek tetap di `readme3.md` / `readme4.md`-successor;
dokumen ini fokus ke konteks W-Engine passive + bonus conditional.

## Kasus kalibrasi (ground truth dari user, simpan jangan buang)

Miyabi (dump `1303558818.json` — build persis seperti output
`zzz_enka_stat_calc_multichar.py`) lawan **Tyrfing level 60** (HP 51,703 /
ATK 573 / DEF 572 / Daze 942 / Stun DMG Mult 150% / RES: Phys 0%, Ice −20%,
Ether −20%, lainnya 0%):

- Hit pertama "Basic Attack: Kazahana" (mult 54.4%, **Physical**):
  **non-crit 1086, crit 2961**
- Hit kedua "Basic Attack: Kazahana" (mult 59.3%, Physical) — ditambahkan
  2026-09-06 buat investigasi residual:
  **non-crit 1183, crit 3227**

### STRIP-TEST (2026-09-06, `1303558818v2`–`v4`) — RESIDUAL TERPECAHKAN

User melakukan strip-and-requip (logis: lepas disc & W-Engine, cek damage,
equip ulang satu per satu) vs Tyrfing L60, slash 1 & 2:

| Konfigurasi | ATK | PEN% | PEN | CD | D1/C1 | D2/C2 GT |
|---|---|---|---|---|---|---|
| v3 bare (no disc, no wengine) | 880.6952 | 0 | 0 | 50% | 279/418 | 304/456 |
| v2 disc only | 1683.85 | 0 | 18 | 172.8% | 540/1471 | 588/1604 |
| v4 wengine only (passive +12%) | 1752.86 | 24 | 0 | 50% | 616/924 | 672/1075* |
| full (cache lama) | 3042.69 | 24 | 18 | 172.8% | 1086/2961 | 1183/3227 |

(*) C2 v4 (1075) tidak cocok model manapun — kemungkinan ada proc/Shatter
pas sampling atau salah baca; C1 (924) exact. Tidak dipakai buat fit.

**Hasil analisis (grid + window analitik, model D = round(raw)):**

1. **Game TIDAK floor stat per-layer.** v3 bare membuktikan langsung:
   ATK 880.6952 (exact, tanpa floor) → D1=279 ✓ D2=304 ✓; kalo di-floor
   (880) → 278/303 ✗. Jadi `StatState.summed()` yang `math.floor` per
   layer itu SALAH vs game — sudah diperbaiki (commit terpisah): panel
   sekarang 2716.69, damage 1085.73, **residual turun 0.064% → 0.025%**
   (selisih non-crit 0.27).
2. **Validasi formula DEF & PEN via isolasi**: v3 (PEN 0/0) → DEFmult
   794/(571.68+794)=0.5815 ✓; v2 (PEN flat 18 dari disc 32742 sub
   `23203` 9×2) → 794/(571.68−18+794)=0.5892 ✓; v4 (PEN 24% dari
   W-Engine secondary) → 794/(571.68×0.76+794)=0.6462 ✓. Formula
   `compute_def_mult` terkonfirmasi di 3 titik PEN berbeda.
3. **W-Engine passive S1 +12% ATK tervalidasi** (v4: 1564.6952×1.12 =
   1752.86 → 616/672 exact). BreakLevel=5 di Enka = star 5 (main stat
   684), BUKAN phase passive (phase tetap 1 → +12%).
4. **Display damage = round(raw)** (bukan floor): terkonfirmasi di 7/8
   titik D. Crit number: tidak ada model rounding tunggal (floor/round/
   ceil dari raw atau dari D) yang konsisten di semua config; cm window
   per-config minta CD efektif 50.18–50.42% (v3) dan 172.72–172.74%
   (v2/full) vs teoritis 50/172.8 — deviasi kecil tidak seragam arah →
   indikasi noise display di angka crit. Non-crit solid.
5. Sisa mismatch: full D2 1184 vs 1183 (off-by-one di satu titik dari
   8) dan v4 C2 — keduanya konsisten dengan noise/proc minor di sample
   itu, bukan systematic bias (D lain 7/7 exact).

Pipeline post-fix: **kalibrasi PASS, selisih non-crit 0.27 (0.025%),
crit 0.87 (0.029%)** — sebelumnya 0.064%/0.009%.

Komposisi ATK panel (verifikasi layer, semua exact):
base 127 + growth 7.6728×59 + promo 226 = **805.6952** | core 75 flat |
weapon main 684 (floor dari 684.02) | disc Atk_Ratio 5100 units (51%) |
disc Atk_Delta 354 | set 2pc: tidak ada ATK →
exact = (805.6952+75+684)×1.51+354 = 2716.69; pipeline lama (floor per
layer) = 2715.64 — sumber residual utama, sudah diperbaiki.

## Kronologi discrepancy

| Tahap | Non-crit | Crit | Masalah |
|---|---|---|---|
| Simulasi awal (ATK stat calc = 2715) | 969 | 2351 | W-Engine passive & set 4pc conditional tidak dimodelkan |
| + Fusion Compiler S1 passive (+12% ATK) | **1085** | — | selisih 0.09% (flooring / DEF drift) |
| + B&BS 4pc conditional (+30% CRIT DMG) | **1085** | **2961 EXACT** | ✓ |

## Akar masalah #1 — W-Engine passive tidak dimodelkan SAMA SEKALI

`zzz_enka_stat_calc_multichar.py` (`make_weapon_layer`) cuma menghitung
MainStat + SecondaryStat W-Engine. **Passive-nya diabaikan total.**

Padahal Fusion Compiler (weapon 14118) S1 passive = **"Increases ATK by
12%"** — always-on, langsung ngefek ke semua damage.

Sumber data passive (semua lokal):
- `WeaponTalentTemplateTb.json` — 475 rows, field:
  `COEEBFOBGND` = weapon id (match key di `weapons.json`),
  `APAEMLCPFID` = level talent (1-5 = phase/mod S1-S5),
  `CLCDDKNHEMN` = title key, `POLEJGCKKFI` = desc key
  (CORRECTED 2026-08-31: versi awal dokumen ini menukar keduanya;
  kebenaran dari isi file — CLCDDKNHEMN berisi `...Title_...`,
  POLEJGCKKFI berisi `...Des_...`),
  `NFKHOOCEDEH` = list ID teks parameter.
- Teks via TextMap (`Weapon_TalentDes_*`).
- Level passive yang aktif ditentukan phase weapon dari API dump
  (`UpgradeLevel` field di avatar Weapon — sudah ada di script).

Verifikasi math: ATK stat calc 2715.64 × 1.12 = 3041.5
→ non-crit = 3041.5 × 54.4% × DEFmult(0.6558) = **1085** (in-game 1086).

⚠️ Passive masuk bucket **CONDITIONAL** formula Final Stat (wiki, halaman
Stats):
```
FinalStat = (Base × (1 + Bonus%_uncond) + Flat_uncond)
            × (1 + Bonus%_cond) + Flat_cond
```
"% ATK dari passive W-Engine" dikali SETELAH bucket unconditional — jadi
EFSEKNYA bukan sekadar `Atk_Ratio += 1200` di layer stat (secara angka
untuk kasus ini kebetulan sama, tapi beda struktur kalau ada interaksi
dengan bonus % lain; ikuti formula wiki).

## Akar masalah #2 — Set bonus 4pc conditional tidak ada di data Enka

`equipments.json` (Enka store) per suit HANYA berisi `SetBonusProps`
bonus **2pc** (statis, sudah dimodelkan `make_set_layer`).
Bonus **4pc** tidak ada sama sekali di file itu.

Sumber teks 4pc: TextMap pattern `EquipmentSuit_<suitid>_4_des`
(30 suit, semua terbaca; 2pc di `..._2_des`).

Kasus Miyabi — Branch & Blade Song (suit 32700) 4pc:
> "When Anomaly Mastery exceeds or equals 115 points, the equipper's CRIT
> DMG increases by 30%. When any squad member applies Freeze or triggers
> Shatter, the equipper's CRIT Rate increases by 12%, lasting 15s."

Miyabi Anomaly Mastery = 116 (≥115 ✓ selalu aktif utk build ini) →
CRIT DMG 142.8% + 30% = 172.8% → crit = 1085 × (1 + 1.728) = **2961 EXACT**.

(Bagian +12% CRIT Rate on Freeze/Shatter itu conditional combat-state —
untuk hit pertama rotasi belum aktif, tidak dipakai di angka 2961.)

## Implikasi buat damage calculator

1. **ATK "combat" ≠ ATK stat calc.** Stat calc = stat panel (bonus
   unconditional). Damage harus pakai ATK combat = stat panel × (1 +
   passive%_cond) + flat_cond. Angka panel 2715 itu benar sebagai panel;
   yang salah adalah memakainya langsung untuk damage.
2. **CRIT DMG "combat" juga beda** (+30% dari 4pc B&BS di build ini).
   Crit multiplier pakai 172.8%, bukan 142.8%.
3. Setiap W-Engine signature punya passive unik — sebagian besar bukan
   stat flat tapi efek combat (stack, cooldown, conditional). Untuk MVP:
   model yang stat-sederhana dulu (regex "Increases ATK by X%"), sisanya
   manual per weapon yang kepakai di build user.
4. Set 4pc: model per-suit yang dipakai dulu (B&BS). Kalau mau lengkap,
   mapping manual 30 suit ke efek terstruktur (teksnya cuma 30 entri).
5. Formula DEF mult & RES mult sudah benar (wiki fandom Damage page):
   `DEFmult = 794 / (max(DEF×(1−PENratio) − PEN, 0) + 794)` untuk
   attacker L60+; `RESmult = 1 − RES`.
6. Sisa selisih 1085 vs 1086 (0.09%): kandidat (a) flooring chain damage
   di game — perlu tahu di stage mana di-floor; (b) DEF Tyrfing drift
   antara wiki & patch (DEF ~570-571 memberi 1086 persis). Cek monster
   table di datamine (`curl.exe` bisa akses git.mero.moe, lihat
   metodologi readme3) — sesuai metodologi JSON > wiki.

## Data mentah kalibrasi (biar gampang di-reproduce)

```
Tyrfing L60: HP 51,703 | ATK 573 | DEF 572 | Daze 942 | StunMult 150%
             RES: Phys 0 / Fire 0 / Ice −20 / Elec 0 / Ether −20 / Wind 0
Miyabi stat panel (script): ATK 2715.64 | CRIT 51.4% | CD 142.8% |
             Ice DMG +30% | PEN Ratio 24% | PEN 18 | AM 116 | AnomProf 301
Fusion Compiler S1: +12% ATK (passive, bucket conditional)
B&BS 4pc: AM≥115 → +30% CRIT DMG (aktif, AM 116)
Kazahana hit-1: 54.4% Physical, Lv.12
DEFmult = 794 / (572×0.76 − 18 + 794) = 0.65583
non-crit = 3041.5 × 0.544 × 0.65583 = 1085.4  (in-game 1086)
crit     = 1085.4 × 2.728 = 2961.1           (in-game 2961) ✓
```

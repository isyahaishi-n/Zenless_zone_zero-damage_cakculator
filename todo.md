# TODO — Paritas Formula okMuzzy v3.1.0

Hasil audit formula Excel (`misc/[v3.1.0] okMuzzy's ZZZ Calculator.xlsx`,
sheet `C1`/`BC1`–`C3` kolom P, `Anomaly Calcs`, `DPS Calcs`,
`W-Engine Buffs`) vs `damage_calc.py`, 2026-09-14.

## Selesai (2026-09-15 #2) — item 3 + 4

- [x] **Item 3: Buildup** (`compute_buildup`, C1!R3 verbatim):
  `buildup_base × (AM_combat/100) × (1+Σ Buildup Rate) × (1−Buildup RES)`.
  - **Blocker selesai**: field buildup = `PEHOFGPKJBN` (AvatarSkillTb),
    VERIFIED via korelasi zzz-hakushin-data (aturan NEXT_STEPS.md):
    61/61 row exact (Anby/Miyabi/Jane) — `PEHOFGPKJBN` ==
    'AttributeInfliction'. Bonus mapping juga verified 61/61:
    `AKFLKECDEPG`=SpRecovery(energy), `NFCOCPMBCKO`=FeverRecovery
    (decibel, kolom T), `KEFHOIFIDBN`=EtherPurify. Buildup TIDAK
    per-level (nilai tunggal — konsisten kolom M Excel tanpa growth).
    skill_lookup.compute_buildup + snapshot `hits[].buildup`.
  - Buildup RES per elemen: `EnemyStats.buildup_res_pct` dari
    BuildupRes MonsterSub. **Fix typo**: Electric field
    `BLNPNJIDME` (2 N — docstring lama 3 N salah, 0/1792 row;
    fixed, verifikasi 1792/1792 row punya 18 field RES lengkap).
  - Bucket `buildup_rate_pct`: wengine 'Anomaly Buildup Rate'
    (Peacekeeper/Roaring Ride/Timeweaver/Sharpened Stinger/Flight of
    Fancy — scoped skill jalan, Peacekeeper EX-only verified) +
    mindscape "Buildup ... increases by X%".
  - **Data fix**: [Magnetic Storm] Alpha/Bravo di
    wengine_passive_mapped.json salah stat ('Anomaly Buildup Rate'
    padahal evidence = AM/AP +25 flat) — di-patch ke stat benar +
    needs_review (evidence = source of truth).
  - Verifikasi numerik: Miyabi Kazahana hit-3 Ice buildup base 62.9 ×
    AM 1.16 × BuildupRES-weak 1.2 = 87.56 ✓ (display 87.6).
  - Output `buildup` per hit di run.py + server API.
- [x] **Item 4: Anomaly DMG per-tick** (`compute_anomaly_damage`,
      'Anomaly Calcs' C58-C63 verbatim):
  - Konstanta elemen PER TICK di-copy persis dari Excel:
    Physical/Assault **713%**, Wind/Windswept **1250%**, Ice/Shatter
    **500%**, Fire/Burn **50%**, Electric/Shock **125%**,
    Ether/Corruption **62.5%**.
  - Chain: `{mult}% × ATK_combat × DEFmult × RESmult × (1+ΣStunMult
    additive) × (AP/100) × 2 × (1−DMGReduction) × (1+elemDMG%_panel +
    ΣAnomalyDMG%) × (1+CR_anom×CD_anom) × (1+ΣRefringe)`.
  - KOREKSI vs dugaan awal todo: (a) MV_stat = ATK untuk SEMUA elemen
    (C48 shared, bukan per-tipe AP/Impact/PEN); (b) crit multiplier
    `(1+CR×CD)` ada di SEMUA elemen (C58-C63 semua), bukan cuma
    Assault — tapi pakai buff anomaly-scoped, BUKAN panel CR/CD
    karakter; (c) `×2` konstanta semua tipe.
  - Bucket `anomaly_dmg_pct` (disc `all_attribute/attribute_anomaly_
    damage_percent` — Notes From the Chained 16% verified) +
    `disorder_dmg_pct` (siap utk item 5).
  - Integrasi: baris "Anomaly {label} ({elem})" per elemen karakter di
    compute_all_damage + run.py + server API. Verifikasi numerik:
    Miyabi Shatter 5.0×ATK_combat(×1.12 FC S1)×def 794/(794+571.68)×
    RES 1.2×AP 2.38×2 == 29098.96 ✓ (display 29099.0).
  - Tick count DoT (Burn/Shock/Corruption, C1!W10 `Rounddown(Duration×
    rate)` — Fire/Ether ×2, Electric ×1) = kerjaan rotasi (item 7);
    durasi input default 10s (A49).
  - **Paritas fix dmgtaken**: P3 Excel `(1−DMGReduction)` LINEAR —
    compute_final_damage lama pakai 1/(1−x) versi wiki; diganti
    linear `(1+taken)×(1−reduction)` (0 sumber mapped terpakai,
    kalibrasi GT tetap PASS).
- [x] Kalibrasi GT 1086/2961 tetap PASS (0.025%/0.029%) + regresi
      penuh S1-S13 (bucket, sheer, daze, buildup, anomaly) PASS.

## Selesai (2026-09-15) — item 1 + 2 + 9

- [x] **Item 1: Bucket multiplier ekstra** (`compute_final_damage`,
      semua verbatim dari dump formula C1!P3):
  - [x] Final Multiplier `× (1+Σ)`: bucket `final_mult_pct` (scoped per
        skill via aggregate). Sumber mapped: belum ada — sumber Excel =
        Evelyn Scaling Buffs 0.25 (item 6). Slot siap.
  - [x] Direct DMG `× (1+Σ)`: bucket `direct_dmg_pct`. Sumber mapped:
        TIDAK ADA yang cocok (satu-satunya Excel = team buff "Wind
        Infusion" 0.1; `passive_amplification` dicek = semua semantik
        "increases TO x% of original" = set, bukan direct). Slot siap.
  - [x] Sheer DMG `× (1+Σ Sheer DMG + Σ{elem} SDMG)`: bucket
        `sheer_dmg_pct` (wengine/mindscape sheer + disc
        `sheer_damage_percent` ala Yunkui Tales threshold_stack 10%).
        Gated `is_sheer_agent` (profession == "Rupture": ids
        1051/1371/1441/1471/1531 == Yidhari/Yixuan/Norano/BanYue/SPBilly
        == daftar sheer agent Excel Agent Data — verifikasi silang).
  - [x] Sheer MV stat (C1!B34): `ATK_combat*0.3 + HP*0.1 + SheerForce`
        via param `hp_panel`/`sheer_force` dari snapshot stats.
        Verifikasi numerik: Yixuan hit1 Cirrus Strike — manual
        6954.22 == output 6954.2 (MV 5077.26 = 2249.9*0.3 + 18642.9*0.1
        + 2538).
  - [x] Sheer ignore DEF (C1!P3 `IF(B33="YES", 1, ...)`): DEFmult = 1
        utk sheer agent. RESmult TETAP jalan (P3 apply RES ke sheer).
- [x] **Item 2: Daze final** (C1!Q3): `compute_daze` =
      `Impact_combat × dazeMV% × (1 − Daze RES) × (1 + Σ Daze%)`.
  - Impact_combat (C1!B35): `compute_impact_combat` = panel × (1+Impact%)
    + flat (Chief Sidekick +30 flat → `impact_flat`; Impact% wengine →
    `impact_pct`).
  - Daze% bucket `daze_pct`: wengine/mindscape `daze_bonus` (10+13
    entry) + disc `*_daze_percent`; scope per skill jalan (Shockstar
    Disco `basic_dash_dodge_counter_daze_percent` → Basic/Dash/Dodge
    Counter ON, Chain/Ultimate OFF — fix `_map_drive_effect_key`).
  - Daze RES per elemen: `EnemyStats.daze_res_pct` dari StunRes
    MonsterSub (/10000, monster_data.resolve). Tyrfing: Ice/Ether
    −20% → ×1.2 daze.
  - Output `daze` per hit di run.py + server API (`/api/calc` rows).
    Verifikasi numerik: Miyabi hit1 dazeMV 21.2%, Impact 86 →
    86 × 21.2% = 18.232 ✓.
- [x] **Item 9: Review data mapped vs bucket baru**:
  - `stun_dmg_mult` (6 mindscape) = Stun Multiplier bucket Excel —
    stack ADDITIF dengan stun_taken musuh di SATU kurung
    `(1 + StunTaken + Σ StunMultiplier)` (C1!P3), BUKAN dikali. Sudah
    diimplementasi + sanity check rasio 1.75/1.5 (Lighter M2 +25% on
    Tyrfing +50%).
    ⚠️ Qingyi M2 (135) & Norma M2 (6) ternyata semantik SET ("increases
    TO x% of the original") — guard baru `_SET_TO_SEMANTICS_RE` di
    `_mechanical_auto_enable` biar tidak auto-enable (needs_review);
    Lighter/Ju Fufu/Roxy/Dialyn M2 = "BY" semantics, aman.
  - `damage_taken_down`/`enemy_dmg_down` (wengine) = DEFENSIVE player-
    side ("Reduces DMG taken by equipper" / "reduces attacker's DMG"),
    BUKAN `(1−DMGReduction)` Excel (enemy-side damage reduction) →
    tetap passthrough `extra`. Tidak berubah.
  - `original_multiplier`/`multiplier_bonus` = "TO x%" (set) — tetap
    excluded dari formula (keputusan lama, terkonfirmasi benar).
    Catatan: Promeia M2 "multiplier of Abloom increases by 120%" &
    Remielle M4 "DMG multiplier increased by an additional 12%" &
    Astra M6 "multiplier ... increase to 200%" — semantik BY vs TO
    bercampur; mapping ulang = kerjaan item 8 (procs/anomaly).
  - `unparsed` (70 entry) triase: 19 resource/state (Charge/Vortex
    stacks, decibel, dll), ~36 stack-mechanic + charge counter,
    13 multiplier/rate (kandidat Final Multiplier/anomaly rate —
    item 4/8), 1 damage-bonus, 1 damage-dealing proc (item 8).

## Selesai (2026-09-14)

- [x] Ordering DEF additif ala Excel: `DEF×(1+DEFInc−ΣShred−ΣIgnore)×(1−PEN%)−PENflat`
      (`compute_def_mult`, damage_calc.py). Multi-source ignore = jumlah
      flat poin, bukan chain multiplikatif.
- [x] Bucket baru `def_shred_pct` + `def_increase_pct` di `CombatModifiers`
      (agregasi + `_EFFECT_TYPE_TO_STAT` + `describe`).
- [x] RES additive ala Excel: `1 − (RES − Σignore − Σshred)`.
      Terverifikasi ke `W-Engine Buffs` row 817: Chief Sidekick
      "ignores 15% of Fire RES" dimasukkan okMuzzy sebagai buff
      `Fire RES −0.15` di kurung additive C1 (bukan `RES×(1−15%)`).
- [x] Kalibrasi GT 1086/2961 tetap PASS (0.025%/0.029%).

## 1. ~~Bucket multiplier ekstra~~ — SELESAI 2026-09-15 (lihat atas)

## 2. ~~Daze final~~ — SELESAI 2026-09-15 (lihat atas)

Daze floor/enlightened equivalent — cek apakah game punya cap daze
per hit (Excel tidak; skip dulu).

## 3. ~~Buildup~~ — SELESAI 2026-09-15 (lihat atas)

`energy_flat`/`decibel_bonus` (kolom S/T Excel) → bonus nyusul
(resource: AKFLKECDEPG/NFCOCPMBCKO sudah ter-decode & verified,
tinggal pasang di snapshot hits + tampilan).

## 4. ~~Anomaly DMG per-tick~~ — SELESAI 2026-09-15 (lihat atas)

Slot stat `anomaly_proficiency` panel terverifikasi benar
(AP 238 → ×2.38 di Shatter numeric check 29099.0).

## 5. Disorder / Polarity / Vortex (±1 hari)

- [ ] Disorder DMG = f(2 elemen ter-trigger): formula di C1 baris
      152+ & CombinedRotationData — perlu baca detail multiplier
      disorder (Excel punya "Disorder Bonus" 250% Yanagi C1!F38,
      "Expected Disorder Damage" E54 array).
- [ ] Polarity Disorder (Yanagi M4) & Vortex (Wind+Physical/Ice) —
      hitung dari tick count 2 anomaly di rotasi (butuh pipeline
      rotasi dulu, item 7).

## 6. Team buffs + uptime (proyek mapping, MINGGUAN)

Excel: sheet `Team Buffs` (~1400 row) + uptime-weighted scaling
(`Scaling Buffs`) + burst-phase (BC sheets) + buff lintas slot.
- [ ] Desain format `team_buffs_mapped.json` (mirror 3 file mapped
      existing: evidence + condition + scope + stacks).
- [ ] Mapping manual per karakter (kayak mindscape: 1 entry per buff,
      evidence wajib). Prioritas: karakter meta team buffer dulu
      (Astra Yao, Lucy, Caesar, Evelyn, Trigger, Hugo, Yixuan).
- [ ] Integrasi uptime-weighted: `buff × uptime` (toggle uptime 0–1),
      burst vs sustained phase.
- [ ] Buff enemy-side: DEFIncrease (buff DEF musuh udah ada bucket-nya),
      enemy_dmg_down (1 entry wengine) → mapping.

## 7. Rotation & DPS output (±0.5 hari setelah team buffs)

- [ ] Format rotasi: list [(skill_idx, hit_idx, count)] — Excel pakai
      nama skill (QUERY starts-with); kita bisa pakai hit_id langsung
      (lebih robust).
- [ ] Total damage = Σ hit × count × rotation_mult; DPS = total/time.
- [ ] Fase stun terpisah (BC-style): rotasi normal + rotasi stun
      (enemy_stunned=True) + repeat ×N masing-masing.
- [ ] CLI `run.py --rotation file.json` + output distribusi per skill
      type (mirror CombinedRotationData kolom V–AA).

## 8. Proc library per karakter (proyek mapping, MINGGUAN)

Excel C1 baris ~130–215: special follow-up damage yang trigger dari
isi rotasi (~85 entry). Contoh: Astra M6 Tone Cluster, Evelyn M6
Lunalux Garrote, Vivian/Yuzuha/Nangong Yu/Promeia Abloom, Yixuan M1/M2,
Sunna Cat's Gaze, Cissia Corrode Bone, Remielle Luminize, dll.
- [ ] Format `procs_mapped.json` per avatar: trigger (regex skill
      name / event), stat basis, multiplier per M-rank.
- [ ] Evaluasi proc saat menjumlah rotasi (butuh item 7).

## 9. ~~Review data mapped existing vs bucket formula baru~~ — SELESAI 2026-09-15 (lihat atas)

## Catatan metode (aturan lama tetap berlaku)

- Semua konstanta/field WAJIB diverifikasi ke sumber asli (Excel cell
  atau JSON dump) sebelum dipakai — jangan dari ingatan/pesan chat.
- Setiap item formula baru → tambah sanity check angka Excel kecil
  (kayak `test_calc` pattern) + kalibrasi GT tetap PASS.
- Sanity checks item 1+2+9 2026-09-15 (script inline, angka manual
  dari dump formula Excel): final/direct mult, sheer MV/def-ignore,
  stun additive ratio, daze, impact combat, scope daze disc,
  threshold_stack sheer, GT kalibrasi PASS 0.025%/0.029%.
- urutan kerja yang disarankan: ~~1 → 2 → 9 → 3 → 4 →~~ 7 → 5 → 6 → 8
  (item 1, 2, 9 selesai 2026-09-15; item 3, 4 selesai 2026-09-15 #2).
  Regresi penuh S1-S13 + GT kalibrasi PASS setelah tiap item.

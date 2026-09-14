# TODO — Paritas Formula okMuzzy v3.1.0

Hasil audit formula Excel (`misc/[v3.1.0] okMuzzy's ZZZ Calculator.xlsx`,
sheet `C1`/`BC1`–`C3` kolom P, `Anomaly Calcs`, `DPS Calcs`,
`W-Engine Buffs`) vs `damage_calc.py`, 2026-09-14.

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

## 1. Bucket multiplier ekstra (cepat, ±1–2 jam)

Excel punya 3 multiplier tambahan di chain damage yang belum ada di
`compute_final_damage`:

- [ ] **Final Multiplier**: `× (1 + Σ Final Multiplier)` — buff tipe
      "multiplier" (mis. Luminize `×(1+Multiplier)`), scoped per skill.
- [ ] **Direct DMG**: `× (1 + Σ Direct DMG)` — bucket stat terpisah dari
      `damage_pct` biasa (jarang; cek sumber di file mapped mana yang
      cocok — mungkin `passive_amplification`).
- [ ] **Sheer DMG** (Yixuan): `× (1 + Σ Sheer DMG + Σ {elem} SDMG)`.
      Data: `sheer_dmg_bonus` (1 entry, mindscape_mapped.json Yixuan)
      + wengine `Sol Exuvia`(?). Plus stat MV khusus:
      `MV_stat = ATK×0.3 + HP×0.1 + SheerForce` (C1!B34) — butuh flag
      "sheer agent" di snapshot.
- [ ] **Sheer ignore DEF**: hit Sheer → DEFmult = 1 (C1!P3
      `IF($B$33="YES", 1, 794/(794+...))`). Toggle via elemen/flag hit.

## 2. Daze final (±2–3 jam, resource lengkap)

- [ ] `Daze = Impact_combat × dazeMV% × hit_count × (1 − Daze RES musuh)
       × (1 + Σ Daze%)` (C1 kolom Q).
      Resource semua ada: Impact panel (zzz_enka...:395), `daze_pct`
      per hit (skill_lookup.py), Daze/Stun RES per elemen
      (monster_data.py — StunRes fields udah ter-decode),
      `daze_bonus` (10 wengine + 13 mindscape), Daze RES toggle.
      Sekarang `daze_pct` cuma ditampilkan mentah (run.py "daze-only").
- [ ] Daze floor/enlightened equivalent — cek apakah game punya cap
      daze per hit (Excel tidak; skip dulu).

## 3. Buildup (±3–4 jam + decode 1 field)

- [ ] `Buildup = buildup_base × (1 + Σ Buildup Rate) × (1 − Buildup RES)
       × hit_count` (C1 kolom R).
      **Blocker data**: base buildup per hit BELUM didecode dari
      `AvatarSkillTemplateTb.json` (skill_lookup.py baru ekstrak
      Damage `EJOKBBJBLIL/KHGLLHLJOPH` & Daze `OMFJHOLBIKA/KICLLNBEAEN`).
      Perlu cari field buildup (pola obfuscated 4-huruf+3-huruf,
      verifikasi vs zzz-hakushin-data — aturan di docs/NEXT_STEPS.md).
      Buildup RES musuh per elemen SUDAH ada (BuildupRes fields).
      `energy_flat`/`decibel_bonus` (kolom S/T) → bonus nyusul.

## 4. Anomaly DMG per-tick (±1 hari, resource hampir lengkap)

Formula `Anomaly Calcs` row 58+ (per elemen):
```
AnomalyDMG = elem_mult × MV_stat × DEFmult × RESmult
             × (1 + Σ StunMultiplier) × (AP/100) × 2 × (1−DMGReduction)
             × (1 + Σ Anomaly DMG% + Σ {elem} DMG)
             × (1 + CR_crit_only × CD_crit_only)   # hanya Assault
             × (1 + Σ Refringe Coefficient)
```
- [ ] Hardcode konstanta elemen dari Excel (Anomaly Calcs row 58–63):
      Physical/Assault 713%, Wind 1250%, Fire 500%×2 ticks (lihat
      `Rounddown(Duration×2)` C1!W10), Ice 500%?, Electric 125%?,
      Ether 62.5%? — **angka final WAJIB di-copy persis dari Excel**,
      jangan dari ingatan.
- [ ] MV_stat per tipe anomaly (Anomaly Calcs B1): ATK (Assault/Burn?),
      AP (Shock/Burn?), Impact, PEN — lookup per elemen.
- [ ] Crit khusus Assault (`(1+CR)×(1+CD)` hanya Physical).
- [ ] Durasi DoT (Burn/Shock): tick = `Rounddown(Duration × rate)`,
      duration default 10s, input CLI.
- [ ] Slot stat `anomaly_proficiency` panel udah ada di snapshot
      (`Anomaly Proficiency`), tapi perlu dipastikan PCT konversi benar.

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

## 9. Review data mapped existing vs bucket formula baru

- [ ] `damage_taken_down` + `enemy_dmg_down` (wengine) → seharusnya
      masuk `dmg_reduction_pct`/`dmg_taken_pct`? Cek evidence &
      semantics vs Excel `(1−DMGReduction)`.
- [ ] `stun_dmg_mult` (6 mindscape) → cek apakah = Stun Multiplier
      bucket Excel (`SumIf "Stun Multiplier"` C1) — kalau ya, itu
      stack ADDITIF dengan stun_taken musuh, jangan dikali.
- [ ] `original_multiplier`/`multiplier_bonus` (mindscape) — cek
      ulang semantik "increase TO x%" (set) vs "increase BY x%"
      (skill_mult_pct+). Yang "BY" harus masuk bucket.
- [ ] `unparsed` (70 entry mindscape) — triase: mana yang relevant
      formula (stat/damage) vs flavor text.

## Catatan metode (aturan lama tetap berlaku)

- Semua konstanta/field WAJIB diverifikasi ke sumber asli (Excel cell
  atau JSON dump) sebelum dipakai — jangan dari ingatan/pesan chat.
- Setiap item formula baru → tambah sanity check angka Excel kecil
  (kayak `test_calc` pattern) + kalibrasi GT tetap PASS.
- urutan kerja yang disarankan: 1 → 2 → 9 → 3 → 4 → 7 → 5 → 6 → 8
  (bucket cepat dulu, yang butuh rotasi terakhir).

# TODO — Paritas Formula okMuzzy v3.1.0

Hasil audit formula Excel (`misc/[v3.1.0] okMuzzy's ZZZ Calculator.xlsx`,
sheet `C1`/`BC1`–`C3` kolom P, `Anomaly Calcs`, `DPS Calcs`,
`W-Engine Buffs`) vs `damage_calc.py`, 2026-09-14.

## Selesai (2026-09-15 #5) — UI Disorder/Polarity/Vortex (item 5)

- [x] **Integrasi UI** (rotation menyusul; sesuai permintaan fokus item 5
      dulu):
  - `server.py`: `calculate_avatar(..., specials=...)` + helper
    `_compute_special_rows` — panggil `dc.build_special_rows` per spec
    (chain formula sama dgn rotasi) pakai toggle yang baru dihitung;
    balikin field `special`
    `[{kind, element, base_pct, count, damage, total, error}]`
    (`total = damage x count`, per instance). Elemen tak dikenal (mis.
    Lumen/Frostburn) -> baris `error` (damage 0, UI tampil "n/a"),
    BUKAN 500 — satu spec invalid tidak menggagalkan seluruh request.
    Endpoint tetap `POST /api/calc` (body `specials` opsional).
  - `site/index.html`: container `#calc-special` di calc section.
  - `site/static/app.js`: panel `renderSpecialPanel()` — 3 kartu
    (Disorder / Polarity Disorder / Vortex) dengan baris spec:
    element (default "Agent element"), count, remain/duration, skill_lv +
    nagi_ap + mindscape (polarity), is_frost (vortex), add/remove,
    total per kartu + grand total. Hasil di-render `renderSpecialResults()`
    (per-instance dmg + base% + grand total); perubahan input -> debounce
    250ms -> `refreshSpecial()` tanpa re-render tabel hit (fokus input aman).
    **Update**: number field pakai event `input` (live tiap ketik, bukan cuma
    `change`/blur) + clamp min/max; ada baris status `.special-status` yang
    kasih pesan jelas kalau server belum balikin `special` (server lama) atau
    fetch gagal — sebelumnya diam-diam "—" (disangka ga ada output).
  - **Aturan game (dikonfirmasi dari Excel `Anomaly Calcs`)**: `C54 =
    IF(TeamSlot1="Miyabi","Frost",'C1'!$B$3)` label `B54="Attribute"` ->
    elemen di formula Disorder/Vortex = **anomaly yang di-overwrite
    (atribut karakter)**, `t = A54-A56` (durasi). Jadi elemen pemicu
    (yang meng-override) harus BEDA — elemen sama cuma me-refresh, TIDAK
    trigger Disorder. Guard UI:
    - Disorder note: elemen = anomaly yang di-overwrite (biasanya elemen
      karakter), pemicu harus beda.
    - **Polarity di-gate** ke Tsukishiro Yanagi (1221) / Nangong Yu (1511)
      saja — agent lain tampil `n/a` + warning (server tetap hitung, gate
      murni UI).
    - **Vortex**: elemen `Wind` -> `0% — tidak trigger` (butuh Windswept
      (Wind) + anomaly non-Wind), note ditampilkan.
  - Verifikasi UI (Playwright vs server user `:8220`): Miyabi -> polarity
    `blocked` + warning + total `—`, disorder note tampil, vortex di-set
    Wind -> `0% tidak trigger`, grand exclude yang n/a, 0 console error.
  - `style.css`: styling panel special (kartu warna per tipe, field, total).
  - Verifikasi: kalibrasi GT tetap PASS (0.025%/0.029%) + rotation selftest
    PASS; POST /api/calc specials (Miyabi Ice, disorder t=10 base 525%,
    vortex frost t=10 base 750%) cocok; smoke test Playwright end-to-end
    (demo -> Calculate -> kartu render, add row + count x3 = 3x damage,
    0 console error).
  - Catatan parity: `enemy_stunned` untuk disorder/vortex tetap `False`
    (sama dgn `build_special_rows`); refringe/base buff sumber belum ada
    (default 0). Rotation builder belum — lihat item 10.

## Selesai (2026-09-16 #6) — fix mis-map DEF shred (Spectral Gaze)

- [x] **`14136 Spectral Gaze`** ("When the equipper's Aftershock hits an
      enemy, causing Electric DMG, the target's DEF is reduced by 25% for
      5s") dulu ke-map `effect_type:"stat", stat:"DEF", unit:"percent"` ->
      `def_percent` (player DEF%) -> inert. Sekarang `effect_type:"def_shred"`
      (`def_shred_pct`, additive di `compute_def_mult`).
- [x] Root cause di generator `scripts/wengine_passive_gen.py`: pattern
      `stat_<DEF>` generik menang atas pattern spesifik `def_shred`
      (`extract_sentence_effects` stable-sort, start/end sama -> yang lebih
      dulu menang). `def_shred` dipindah ke SEBELUM loop STAT_FRAGMENTS.
- [x] Scope: debuff ke MUSUH (`def_shred`, `enemy_dmg_down`) tidak lagi
      dipasangi `skill_types`/`elements` sebagai filter — konstanta
      `ENEMY_DEBUFF_NO_SCOPE`. Alasan: buff nempel di musuh, berlaku ke
      semua damage selama durasi; scope di teks cuma pemicu.
- [x] Mekanisme baru `default_enabled: true` di mapped entry -> `enabled=True`
      di `ToggleEntry` (wengine/mindscape/set4pc). Mode "liatin hasil buff":
      trigger game tidak dimodelkan, jadi buff dianggap aktif.
- [x] Verifikasi: generator parse -> `def_shred` tanpa scope; `ToggleEntry`
      `def_shred_pct=25` enabled; `aggregate_modifiers` -> `def_shred_pct=25`;
      DEFmult Tyrfing 0.581395 -> 0.649351 (+11.688%); end-to-end lewat
      server (equip 14136 di Miyabi, def_shred ON vs OFF) = **+11.86%**.
      Kalibrasi GT tetap PASS (0.025%/0.029%) + rotation selftest PASS.

## Selesai (2026-09-16 #7) — item 10 + 11(sebagian) + 12a

- [x] **Item 10 — Rotation builder UI**:
  - Backend: `server.calculate_rotation` + `POST /api/rotation`
    (`{showcase, avatar_id, enemy, enemy_level, rotation, toggle_overrides}`)
    → `{report, toggles, avatar, enemy}`; `dc.compute_rotation` sekarang
    terima `toggle_overrides`.
  - `_prepare_avatar` / `_toggles_payload` di server (dipakai
    /api/calc + /api/rotation, hilangin duplikasi).
  - UI `site/static/app.js`: panel `#calc-rotation` — param
    time/rotation_mult/normal_repeat/stun_repeat, dua kolom fase
    (normal/stun) dengan dropdown hit ber-`optgroup` per skill,
    add/remove/count, tombol `Compute rotation`.
  - Disorder/Polarity/Vortex panel item 5 dipakai ulang sebagai section
    rotasi (`rotationPayload()` menyertakan `CALC.specials`).
  - Laporan: grid total/DPS/non-crit/crit/daze/buildup/time + tabel
    distribusi 9 kategori + tabel entry per hit (phase/skill/hit/count).
  - Import/export JSON: tombol `JSON` (textarea + Copy/Load/Download),
    format `rotations/*.json` (`{avatars: {id: rotation}}`); guard aturan
    game (polarity Yanagi/Nangong Yu, vortex non-Wind) tetap dari item 5.
  - Error resolusi hit dari `normalize_rotation` tampil sebagai pesan
    error di panel (bukan cuma console).
- [x] **Item 11 (agregasi)** — `server.calculate_team_rotation` +
  `POST /api/team-rotation` → `{total, dps, distribution, slots, skipped}`;
  UI section "Team" (textarea + "Isi dari rotasi ini" + "Compute team")
  dengan tabel per-slot. Sisa (buff lintas-slot) menunggu item 6.
- [x] **Item 12a — Buff toggle UI** — lihat detail di heading item 12.
- Verifikasi: `calculate_rotation` (Miyabi 20s: total 1.354.629,6 /
  DPS 67.731,5 / Disorder 14,2%), `calculate_team_rotation` (Miyabi+Yixuan
  = 2.980.479,3 = jumlah kedua slot), Playwright end-to-end (rotation,
  JSON Load ubah time 20→40, team compute) tanpa page error; kalibrasi GT
  PASS (0.025%/0.029%) + rotation selftest PASS.

## Selesai (2026-09-16 #8) — verifikasi #7 + default Buffs semua aktif

- [x] **Verifikasi ulang #7** (dokumen vs kode vs angka, bukan asumsi):
      simbol (`dc.toggle_id`/`apply_toggle_overrides`/`compute_rotation` +
      `toggle_overrides`, `_prepare_avatar`/`_toggles_payload`, `/api/rotation`,
      `/api/team-rotation`, `renderBuffPanel`) ada; kalibrasi GT PASS
      (0,025%/0,029%) + rotation selftest PASS; HTTP: GT row `1085.7/2961.9`,
      FC OFF via override → **969,4**, tanpa override → 1085,7;
      `/api/rotation` Miyabi 20s = **1.354.629,6** / DPS **67.731,5** /
      Disorder **14,2%**; `/api/team-rotation` = **2.980.479,3** = Σ slot;
      slot invalid → `skipped` + reason; hit tak ter-resolve → 404 + daftar
      kandidat. **Koreksi catatan lama**: `time` cuma mengubah DPS (total
      tetap), jadi "JSON Load ubah time 20→40" itu uji UI, bukan uji total.
- [x] **Default panel Buffs = SEMUA aktif** (permintaan user): `site/static/
      app.js` — `openCalc` set `CALC.buffDefaultPending`, `renderCalcResult`
      kirim override semua-`true` **sekali** lalu hitung ulang (angka lama
      tidak dirender) dan simpan `CALC.toggles` supaya "Reset" = semua aktif.
      SENGAJA tidak mengubah auto-enable di `damage_calc.py` (metodologi
      `needs_review`/SET-semantics guard tetap utuh); baris `needs_review`
      cuma 3 dari 32 toggle & tetap ada badge-nya. Verifikasi UI: Miyabi
      **4/4 aktif** tanpa interaksi, uncheck Fusion Compiler → **3/4 aktif**
      + GT **969**, Reset → **4/4** + GT **1.086**; Ye Shunguang **6/6**
      (dulu 1/6); POST `/api/calc` = 2 saat buka (1 + 1 override, no loop);
      0 console/page error.
- [x] **Panel Rotation → bahasa Inggris** (permintaan user): 16 string di
      `.special-panel.rot-panel` di-Inggriskan — judul fase `… entries`,
      empty state `No hits yet.`, tombol `Fill from this rotation` (dulu
      "Isi dari rotasi ini"), status JSON `Rotation loaded.` /
      `Copied to clipboard.`, hint team, error `Unrecognized rotation
      format.`, hint `slot times differ` / `skipped slot(s)`, `Remove`.
      Edit ini inert (teks saja): angka tidak berubah karenanya — kenaikan
      total rotasi/team (Miyabi 1.354.629,6 → 1.473.220,7 = +8,75%,
      Yixuan 1.625.849,7 → 1.831.059,3 = +12,62%) murni efek default Buffs
      semua-ON di atas. Verifikasi: `node --check` exit 0; Playwright —
      0 kata Indonesia tersisa di panel, 0 console/page error; angka UI
      disamakan lewat API (`calculate_team_rotation` + override Miyabi =
      **3.099.070,4** == angka UI 3.099.070; selisih panel rotasi 1-slot
      1.483.284 = 1.473.220,7 + baris polarity 10.063,7 → lihat catatan open
      di bawah).
- **Catatan open (temuan verifikasi, bukan rumus):** baris `polarity` default
  panel ikut ke payload rotasi — `rotationPayload()` tidak menerapkan
  `specialKindBlocked`, jadi untuk agent non-Yanagi/Nangong Yu total rotasi
  UI > angka API: Miyabi + `rotations/example.json` → UI **1.364.693** vs API
  **1.354.630** (selisih = `Polarity Disorder (Ice)` 10.063,706). Formula
  kedua jalur identik (delta 0,00%) → murni kebijakan inklusi. Keputusan
  (gate di `rotationPayload()` vs tetap kirim + warning) belum diambil.

## Selesai (2026-09-15 #4) — item 5

- [x] **Item 5: Disorder / Polarity / Vortex** (okMuzzy 'Anomaly Calcs'
      C65-C70 / C72-C91 / C122-C127, verbatim):
  - `disorder_base_pct(element, remaining_duration_s)` — tabel base %
    PERSIS Excel: Physical/Ice `450% + floor(t)×7.5%`, Wind `100%`,
    Fire `450% + floor(t/0.5)×50%`, Electric `450% + floor(t)×125%`,
    Ether `450% + floor(t/0.5)×62.5%`.
  - `vortex_base_pct(element, duration_s, is_frost)` — C122-C127:
    Physical `800% + t×7.5%`, Wind `0%`, Ice Miyabi(frost) `t×75%` /
    selain itu `1300% + t×7.5%`, Fire `900% + (t/0.5)×7.5%`,
    Electric `650% + t×125%`, Ether `650% + (t/0.5)×62.5%`.
  - `compute_disorder_damage` / `compute_polarity_disorder_damage` /
    `compute_vortex_damage`: chain sama dengan anomaly (ATK × DEFmult ×
    RESmult(elem) × Stun × AP/100 × 2 × DMGTaken × DMG% bracket ×
    Refringe) tapi TANPA bracket crit (C65-C70/C72-C91/C122-C127 tidak
    punya CR×CD) → `crit` = `non_crit`.
  - Bracket DMG%: disorder pakai `disorder_dmg_pct` (+ panel A4, default
    0); vortex pakai elem DMG% panel + `anomaly_dmg_pct` + `vortex_dmg_pct`.
  - Polarity (Yanagi): `POLARITY_FACTOR_BY_MINDSCAPE` M0 0.15 / M2+ 0.5 /
    M6 0.8 + term `(725% + 225%×SkillLevel) × Σ NagiAP`; parameter
    `polarity_nagi_ap`/`skill_level` + bucket `polarity_dmg_pct` siap
    (belum ada sumber mapped).
  - Bucket baru `vortex_dmg_pct` (drive disc `vortex_damage_percent` →
    mapping; wengine "Vortex and Windswept +X%" masih damage_bonus generik
    — kandidat remap item 6).
  - **Integrasi rotasi**: section `disorder`/`polarity`/`vortex` di file
    rotasi (eksplisit, TANPA auto-deteksi sesuai metodologi #5) →
    `build_special_rows` + `summarize_rotation(extra_rows=...)` masuk
    kategori distribusi "Disorder". `normalize_rotation` bawa key baru.
  - Verifikasi: selftest 16 cek tabel base (disorder/vortex/polarity
    factor) + `compute_disorder_damage` numerik manual (ATK 1000/AP 100/
    Ice t=10 → 6,104.651) + extra_rows total/distribusi → PASS; kalibrasi
    GT tetap PASS (0.025%/0.029%). Contoh `rotations/example.json`
    (Miyabi Disorder+Vortex, Yixuan Disorder) jalan end-to-end.
  - Catatan parity open: `C53` di formula Excel default = 1 (SUMIF U>0
    fallback 1 saat sheet kosong) — kita tidak memodelkan faktor itu;
    trigger disorder tidak dihitung otomatis dari buildup (0 sumber
    mapped utk buildup-share multi-slot).

## Selesai (2026-09-15 #3) — item 7

- [x] **Item 7: Rotation & DPS output** (`normalize_rotation`,
      `_resolve_rotation_ref`, `summarize_rotation`, `compute_rotation`,
      `format_rotation_report` di `damage_calc.py`):
  - Format JSON: `{name, time, rotation_mult, normal[], stun[],
    normal_repeat, stun_repeat}`. Reference hit pakai `hit_id` (paling
    robust, dari `hits[].hit_id`), atau `skill` (label / kategori /
    hit_skill_type) + `hit` (nama) / `hit_index` (0-based). Referensi
    ambigu/tidak ketemu → LookupError + daftar kandidat (bukan
    diam-diam salah hit).
  - Fase stun terpisah ala BC-style: `normal` tanpa Stun Modifier,
    `stun` dengan `enemy_stunned=True` (StunTaken + Stun Multiplier
    bucket). `compute_all_damage` dipanggil per fase (fase stun hanya
    kalau ada entry `stun`).
  - Total = Σ hit × count × repeat × rotation_mult; DPS = total/time.
    Excel 'DPS Calcs': Rotation Time + Repeat X + Repeat stun X. Damage
    pakai `expected` (CR-weighted) + total non-crit/crit. DoT
    (Burn/Shock/Corruption) `count` = jumlah tick (C1!W10
    Rounddown(Duration×rate)) — tick count tetap kerjaan input rotasi.
  - Distribusi per kategori skill persis `CombinedRotationData`
    C1!V3:V11 (Basics/Dashes/Assists/Specials/Others/Chains/Ultimate/
    Anomaly/Disorder) → damage/daze/buildup + % share (kolom V-Z;
    energy/decibel resource masih TODO).
  - Row `compute_all_damage` sekarang bawa `hit_id`, `skill_key`,
    `skill_category` (dipakai rotation + server API).
  - **Bonus fix**: run.py crash `UnicodeEncodeError` (console Windows
    cp1252) waktu nama hit Yixuan mengandung U+2010 hyphen — stdout
    di-reconfigure utf-8/errors=replace. Ketemu lewat `--list-hits`.
  - Selftest murni `run_rotation_selftest()` (angka manual: total
    34,275, DPS 3,427.5, daze 70, buildup 42.5, distribusi Basics
    1,275 / Specials 3,000 / Anomaly 30,000, ambiguity guard
    LookupError) → PASS, jalan bareng `python damage_calc.py`.
  - CLI: `run.py --rotation FILE` (mendukung section per-avatar
    `{"avatars": {"1091": {...}}}` atau rotasi tunggal) + `--list-hits`
    buat authoring. Contoh: `rotations/example.json` (Miyabi 1091 +
    Yixuan 1371).
  - Verifikasi: kalibrasi GT tetap PASS (0.025%/0.029%) + rotasi contoh
    end-to-end (Miyabi DPS 58,147/s; Yixuan 77,930/s).

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

## 5. ~~Disorder / Polarity / Vortex~~ — SELESAI 2026-09-15 #4 (lihat atas)

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

## 7. ~~Rotation & DPS output~~ — SELESAI 2026-09-15 #3 (lihat atas)

## 8. Proc library per karakter (proyek mapping, MINGGUAN)

Excel C1 baris ~130–215: special follow-up damage yang trigger dari
isi rotasi (~85 entry). Contoh: Astra M6 Tone Cluster, Evelyn M6
Lunalux Garrote, Vivian/Yuzuha/Nangong Yu/Promeia Abloom, Yixuan M1/M2,
Sunna Cat's Gaze, Cissia Corrode Bone, Remielle Luminize, dll.
- [ ] Format `procs_mapped.json` per avatar: trigger (regex skill
      name / event), stat basis, multiplier per M-rank.
- [ ] Evaluasi proc saat menjumlah rotasi (butuh item 7).

## 9. ~~Review data mapped existing vs bucket formula baru~~ — SELESAI 2026-09-15 (lihat atas)

## 10. ~~Rotation builder UI~~ — SELESAI 2026-09-16 #7 (lihat atas)

## 11. Team rotation / slot aggregation (SEBAGIAN — sisa butuh #6)

- [x] **Agregasi slot** (2026-09-16 #7): `server.calculate_team_rotation` +
      `POST /api/team-rotation` (`{rotations: {avatar_id: rotation}}`) →
      `{total, dps, distribution, slots[], skipped[]}`. UI: section "Team"
      di panel Rotation (textarea JSON format `rotations/*.json`, tombol
      "Isi dari rotasi ini" + "Compute team"), laporan total/DPS/tabel
      per-slot/distribusi. Slot tak ada di showcase → masuk `skipped`.
      DPS tim = total / `max(time)` slot; `time_mismatch` di-flag.
- [ ] Buff lintas-slot (Team Buffs, item 6) + uptime-weighted ikut masuk
      ke tiap slot — **belum**, karena item 6 (mapping `Team Buffs`) belum
      ada. Tanpa itu tiap slot dihitung independen.

## 12. Buff toggle UI (SELESAI #7) + proc scaling DEF (sisa)

- [x] **Toggle UI** (2026-09-16 #7): `dc.toggle_id` / `apply_toggle_overrides`
      + `compute_all_damage(toggle_overrides=...)` + `compute_rotation(...)`;
      `POST /api/calc` terima `toggle_overrides` dan balikin `toggles[].id`.
      UI: panel "Buffs" jadi daftar checkbox (semua toggle, bukan cuma yang
      aktif) + "Reset". **Update #8**: default panel = SEMUA aktif
      (`CALC.buffDefaultPending` → override semua-`true` sekali saat buka;
      "Reset" = semua aktif) — sebelumnya cuma auto-enable yang terverifikasi
      (mis. Ye Shunguang 1/6, Miyabi 2/4). Verifikasi: uncheck Fusion Compiler
      → 969 dari 1.086; Reset → 1.086.
- **Aftershock — SKIP/DITUNDA (keputusan 2026-09-16).** Aftershock BUKAN
  kategori damage terpisah kayak Disorder: hit-nya sudah ada di skill
  karakter dan MV/scaling-nya sudah ikut ke-hitung lewat row skill biasa
  (mis. Trigger `Basic Attack: Harmonizing Shot`, `Chain Attack:
  Suppressing Tiger Cauldron` — keduanya skill normal, bukan sintetis).
  Jadi tidak perlu row/formula khusus. Sisa yang belum: 5 toggle ber-scope
  `skill_types: ["Aftershock"]` (mis. Bellicose Blaze `def_ignore` Fire)
  masih inert karena tidak ada hit ber-`hit_skill_type` "Aftershock" —
  dampingannya `skill_category` fallback ke "Others". Tidak dikerjakan
  sekarang (nyusul kalau perlu).
- [ ] `13112 Big Cylinder` ("600% of the equipper's DEF as additional DMG")
      ke-map `effect_type:"additional_dmg"` tanpa basis stat -> inert;
      perlu dukungan proc scaling DEF (nyambung item 8). **Belum**:
      butuh baris sintetis "additional DMG" (always-crit, basis DEF combat)
      + masuk ke distribusi/rotasi → lebih pas dikerjakan bareng item 8.

## Catatan metode (aturan lama tetap berlaku)

- Semua konstanta/field WAJIB diverifikasi ke sumber asli (Excel cell
  atau JSON dump) sebelum dipakai — jangan dari ingatan/pesan chat.
- Setiap item formula baru → tambah sanity check angka Excel kecil
  (kayak `test_calc` pattern) + kalibrasi GT tetap PASS.
- Sanity checks item 1+2+9 2026-09-15 (script inline, angka manual
  dari dump formula Excel): final/direct mult, sheer MV/def-ignore,
  stun additive ratio, daze, impact combat, scope daze disc,
  threshold_stack sheer, GT kalibrasi PASS 0.025%/0.029%.
- Sanity check item 7 2026-09-15: `run_rotation_selftest()` di
  `python damage_calc.py` (total/DPS/daze/buildup/distribusi/ambiguity)
  PASS bareng kalibrasi GT.
- urutan kerja yang disarankan: ~~1 → 2 → 9 → 3 → 4 → 7 → 5 →~~ 6 → 8
  → ~~10 →~~ 11 → 12 (item 1, 2, 9 selesai 2026-09-15; item 3, 4 selesai
  2026-09-15 #2; item 7 selesai #3; item 5 selesai #4; fix DEF shred
  Spectral Gaze selesai #6; item 10 + 11(agregasi) + 12(toggle UI) selesai
  #7. Sisa: item 6 & 8 (mapping MINGGUAN), sisa item 11 (buff lintas-slot,
  butuh 6), sisa item 12 (`13112 Big Cylinder`, bareng item 8)).
  Regresi penuh S1-S13 + GT kalibrasi PASS setelah tiap item.

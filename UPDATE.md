# UPDATE.md — Checklist update data tiap patch baru ZZZ

Jalanin urutan ini SETIAP kali ada patch baru rilis. Jangan skip langkah
manapun — kesalahan paling umum itu lupa regenerate file "mapped" (Tahap 3)
setelah refresh raw data (Tahap 1-2), yang bikin kalkulator "buta" ke
konten baru walau raw data-nya udah ke-update.

## Tahap 0 — Sebelum mulai

- [ ] Catat versi patch lama vs baru (buat referensi kalau perlu rollback)
- [ ] Backup folder `data/` yang lama (biar bisa diff/bandingin kalau ada
      yang aneh setelah update)

## Tahap 1 — Refresh raw data dari `git.mero.moe/dimbreath/ZenlessData`

Cek commit terbaru di repo (`git.mero.moe/dimbreath/ZenlessData`), lalu
download ulang file-file ini (WAJIB, ini yang paling sering berubah tiap
patch):

- [ ] `AvatarSkillTemplateTb.json` — skill karakter baru + rebalance
      karakter lama
- [ ] `AvatarSkillDesTemplateTb.json` — nama skill (termasuk
      `KLPLBBJABBL` explicit hit->name mapping)
- [ ] `AvatarPassiveSkillTemplateTb.json` — Core Passive karakter baru
- [ ] `WeaponTalentTemplateTb.json` — passive W-Engine baru
- [ ] `MonsterConfigTemplateTb.json` — musuh/boss baru (termasuk musuh
      seasonal Hollow Zero/Deadly Assault yang sering ganti)
- [ ] `MonsterSubTemplateTb.json` — stat musuh baru
- [ ] `TextMap_ENTemplateTb.json` — **PALING KRITIS**, semua nama/teks
- [ ] `TextMap_ENOverwriteTemplateTb.json` — override teks post-rework
- [ ] `avatars.json` (buat referensi `BaseProps`/`CoreEnhancementProps`
      -- ini dari Enka, cek Tahap 2 juga)
- [ ] `equipments.json` (drive disc data, dari Enka)

File yang JARANG berubah (cek dulu changelog patch, skip kalau nggak ada
perubahan besar ke sistem level/stat):
- [ ] `LevelCurveTemplateTb.json`
- [ ] `WeaponLevelTemplateTb.json`
- [ ] `WeaponStarTemplateTb.json`
- [ ] `EquipmentLevelTemplateTb.json`

## Tahap 2 — Refresh data dari Enka Network

Enka biasanya nyusul beberapa hari setelah patch resmi rilis (bukan hari
yang sama). Cek `enka.network` dulu apa udah update sebelum lanjut:

- [ ] `weapons.json` — W-Engine baru
- [ ] `equipments.json` — drive disc set baru
- [ ] `avatars.json` — karakter baru (kalau belum update Enka-nya,
      SKIP dulu, jangan campur data lama-baru)
- [ ] `locale_en.json` / `locs.json` — nama tampilan (Enka, terpisah
      dari TextMap Dimbreath)

## Tahap 3 — ⚠️ WAJIB: regenerate file "mapped" (paling sering kelupaan)

File-file ini BUKAN didownload ulang — mereka HASIL OLAHAN dari Tahap 1.
Kalau langkah ini kelewat, kalkulator tetep jalan tapi DIAM-DIAM buta ke
konten baru (nggak error, cuma nggak ke-detect).

- [ ] `wengine_passive_mapped.json` — regenerate dari
      `WeaponTalentTemplateTb.json` + `TextMap` yang baru
- [ ] `drive_disc_mapped.json` — regenerate dari `equipments.json` +
      `TextMap` yang baru
- [ ] `mindscape_mapped.json` — regenerate dari `AvatarSkillDesTemplateTb.json`
      (Talent_0X_Desc) buat karakter baru
- [ ] `monster_tags.json` — regenerate/tambahin buat musuh baru
- [ ] `loadouts.json` — ini per-user (hasil fetch UID), otomatis
      ke-refresh tiap `run.py` dipanggil ulang, nggak perlu manual

## Tahap 4 — Sanity check (WAJIB, jangan skip)

Field name obfuscated (`AOIJDIEHABK`, `IKAABAIDFAO`, dst) **TIDAK ADA
JAMINAN** tetap sama antar patch. Kalau developer game re-obfuscate,
mapping yang udah divalidasi bisa rusak DIAM-DIAM (angka keliatan valid
tapi sebenarnya salah field, nggak ada error yang muncul).

- [ ] Jalanin `python damage_calc.py` (kalibrasi built-in) — HARUS masih
      PASS dengan selisih di bawah toleransi (~0.5%) ke ground truth lama
      (Miyabi vs Tyrfing, non-crit 1086 / crit 2961)
- [ ] Kalau kalibrasi GAGAL atau selisihnya melonjak jauh dari biasanya:
      **JANGAN lanjut pakai data baru** — kemungkinan field mapping
      berubah/rusak. Cross-check ulang field-field kunci
      (`AOIJDIEHABK`=DEF, `IKAABAIDFAO`=DMG, dll) satu-satu ke raw JSON
      baru, jangan asumsikan field code lama masih valid.
- [ ] Test `python run.py <uid>` ke minimal 1 karakter yang gearnya
      lengkap — pastikan stat panel & damage output masuk akal (bukan
      NaN/nol semua/error)
- [ ] Test `python monster_data.py <nama_musuh_baru>` kalau ada musuh
      baru di patch ini — pastikan ke-resolve dan DEF/HP/RES masuk akal
      (bandingin ke wiki Prydwen/fandom resmi kalau ada)

## Tahap 5 — Cek dampak ke temuan/dokumentasi lama

- [ ] Kalau ada karakter yang di-rework (skill/passive berubah total),
      cek apakah entry di `hidden_hits_report.md` buat karakter itu
      masih valid atau perlu diinvestigasi ulang
- [ ] Update `SKILL_DATA_PROGRESS.md` / `TODO_agent.md` kalau ada
      temuan baru soal field mapping dari proses update ini

## Catatan penting

- **Field code fabrication tetap berlaku** — kalau ada agent lain/AI
  lain yang klaim "field X = Y" buat data patch baru, tetap WAJIB
  cross-check langsung ke JSON (`field_name in row.keys()`) sebelum
  dipakai, sama kayak aturan lama.
- Jangan campur data dari versi patch berbeda (misal `TextMap` baru
  tapi `AvatarSkillTemplateTb` lama) — bisa bikin mismatch ID yang aneh
  dan susah di-debug.

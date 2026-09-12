# TODO — Selesaikan `run.py` (pipeline UID -> stat -> damage)

## Status sekarang

`run.py` udah dibikin dan **BERHASIL ditest end-to-end**. Fetch Enka
beneran UDAH BERHASIL dijalankan (masalah 403 kemarin ternyata udah gak
ada di environment sekarang) — `python run.py 1303558818` jalan mulus
dari step 1 (fetch) ke step 2+3 tanpa edit manual.

Catatan hasil fetch real (5 Sep 2026): data live player BERUBAH dari
cache lama — Miyabi sekarang tanpa drive disc (`EquippedList: []`,
dulu 6 disc); weapon 14118 + core 6 masih ada. Makanya ATK panel live
`1564`, bukan `2715.64` seperti kalibrasi lama (itu pakai 6 disc).
BUKAN bug pipeline — verifikasi langsung ke struktur JSON live.

Hasil test — SEMUA masuk akal & konsisten:
- 24 baris damage ke-generate (Basic Attack Kazahana 5-hit, Shimotsuki
  3-charge, Special Attack, Dodge, Chain Attack + Ultimate, Assist)
- **"Defensive Assist: Drifting Petals" 0.0% sudah di-investigasi —
  BUKAN bug, memang daze-only by design**: di
  `AvatarSkillTemplateTb.json` hit 1091022/23/24 punya
  `IKAABAIDFAO=0` (damage base 0) tapi daze base 27130/34280/12830.
  Pola universal: 52 dari 59 karakter punya assist hit daze-only
  (Defensive Assist emang mekanisme parry/daze di ZZZ). Output `run.py`
  sekarang menandainya `(daze-only)` + nilai daze, bukan `0.0%`.

## Yang perlu diberesin sebelum dianggap selesai

- [x] **Test fetch Enka beneran** — BERHASIL, pipeline nyambung mulus.
- [x] **Investigasi "Defensive Assist: Drifting Petals" 0.0%** —
      BUKAN bug; daze-only by design (bukti di raw JSON). Display di
      `run.py` diperbaiki: hit daze-only ditandai `(daze-only)` +
      nilai daze-nya.
- [x] **Handle karakter tanpa weapon/gear** — tested dengan `1.json`
      (`WeaponUid: 0`, `EquippedList: []`, tanpa `Weapon` key): tidak
      crash, stat base tetap kehitung (ATK 880), 24 baris damage tetap
      ke-generate (multiplier skill emang gak butuh weapon). Skenario
      tanpa `SkillLevelList` juga aman — muncul pesan "nggak ada
      weapon/skill data buat dihitung".
- [x] **`--enemy` selain tyrfing** — tested via CLI: error ditangkap
      di `main()` lewat `sys.exit(f"Error: {e}")`, exit code 1, pesan
      jelas ("Enemy '...' belum ada datanya. Tersedia: tyrfing"), bukan
      traceback mentah. Error fetch (UID invalid 404) & showcase kosong
      juga ditangani sama.
- [x] **README/usage note** — ditambahkan subsection "Pipeline lengkap:
      `run.py`" di README.md bagian "4. Cara Pakai" (harus jalanin dari
      root repo karena JSON pendukung di-load relative, contoh command,
      catatan daze-only & karakter tanpa gear).
- [ ] **Commit `run.py` ke repo** — **DITUNDA SESUAI PERMINTAAN USER**:
      jangan commit dulu, biar dicek sama user dulu. Semua perubahan
      (`run.py`, `README.md`, file TODO ini) masih working tree.

## Desain yang SUDAH final, jangan diubah tanpa alasan kuat

- **Slot musuh** (`get_enemy_stats()` + `KNOWN_ENEMIES` dict) sengaja
  dipisah jadi fungsi kecil dengan signature tetap (`enemy_key -> EnemyStats`)
  supaya nanti gampang diganti isinya jadi baca dari Monster JSON asli
  tanpa perlu ubah caller. **Jangan inline logic musuh ke tempat lain.**
- Semua komponen (`fetch_player_data`, `compute_avatar_snapshot`,
  `compute_all_damage`) dipanggil lewat **import langsung**, bukan
  subprocess/file-passing -- pertahankan pola ini.

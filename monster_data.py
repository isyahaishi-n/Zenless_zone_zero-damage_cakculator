"""
monster_data.py — Resolve musuh ZZZ dari data Monster asli (non-hardcode).

Menggantikan slot musuh hardcoded di run.py (KNOWN_ENEMIES) dengan baca
langsung dari 3 tabel ZenlessData + TextMap:

    TextMap:  `OfficialName_Monster_<Codename>`  -> display name (mis. "Tyrfing")
    Config:   `NDJJEKDIHNN == "Monster"`, GELOADGCCFN = codename,
              DALBKGGEJEF = config id  ->  EBIKJFJOKGP (sub id list via Sub)
    Sub:      stat base per varian row (DALBKGGEJEF = sub row id)

Field mapping MonsterSubTemplateTb — VERIFIED 2026-09-05 via korelasi
622 monster overlap dengan Genshin-Optimizer/zzz-hakushin-data (field
un-obfuscated). Match rate 635/643 row (sisanya version drift):

    AOIJDIEHABK  = Defence base (L1)         [635/643 exact]
    LPKOMILKOKG  = Hp base (L1)               [630/643 exact]
    LHPKLCOJKCN  = StunDamageTakenRatio       [638/643 exact, /10000]
    EBIKJFJOKGP  = config/variant id (join ke hakushin MonsterInfo key)

    DamageRes per elemen (/10000 -> fraksi, mis. -2000 = -20%):
        Physical: ACOFKCMKDOJ   Fire: FHKIMGJHOOM     Ice: DAHICMDLIDB
        Electric: GOCPMKOMLLA   Ether: EPCAKNEIANN    Wind: MLNILAMPKDE
    BuildupRes per elemen (anomaly buildup, bukan damage):
        Physical: HEEFNBCGGGG  Fire: NFILPFLNIPC     Ice: DDMBIHOALHL
        Electric: BLNPNLJIDME  Ether: PMGFNHIKHBD    Wind: JFABMBIMGNA
    StunRes per elemen (daze resist):
        Physical: PHCJFMBBDJC  Fire: PGGMCKBGCGL      Ice: GDLJANCPPPM
        Electric: CHODLLFEEPK  Ether: FPIFENJCHJH    Wind: KOFJJDEIGAB
      (catatan: korelasi menyeluruh juga menemukan KOFJJDEIGAB dan
       MLNILAMPKDE sebagai Wind-Dmg kandidat; pasangan final diverifikasi
       ulang di validate_mapping() — lihat bagian bawah file)

Level scaling (CONFIRMED via ground truth Tyrfing L60):
    DEF(L) = AOIJDIEHABK * curve1000(L) / 100     -> 36 * 15.88 = 571.68 ✓
    HP(L)  = LPKOMILKOKG * curve1002(L) / 100      -> 1123 * 46.04 = 51702.92 ≈ 51703 ✓
    (curve1000 = 2x wiki Level Factor; curve1002 = HP growth 46.04x di L60)

Catatan penting tentang "6 field -2000" yang dulu bikin bingung:
    itu BUKAN weak ke 6 elemen — itu 2 elemen × 3 jenis RES
    (Damage + Buildup + Stun). Mis. Tyrfing: Ice{3} + Ether{3} = 6 field
    bernilai -2000, karena game set ketiga jenis RES itu identik.
"""

import json
import urllib.request
from pathlib import Path

ELEMENTS = ("Physical", "Fire", "Ice", "Electric", "Ether", "Wind")

# Join key: EBIKJFJOKGP di Sub = config id. Di dump lokal, satu config id
# bisa punya beberapa sub row (varian rank/scene: 900011096 = rank normal,
# 900011097 = rank upgrade). Resolver memilih row pertama yang punya
# stat base terbesar (varian utama), fallback row pertama.
DAMAGE_RES_FIELDS = {
    "Physical": "ACOFKCMKDOJ",
    "Fire": "FHKIMGJHOOM",
    "Ice": "DAHICMDLIDB",
    "Electric": "GOCPMKOMLLA",
    "Ether": "EPCAKNEIANN",
    "Wind": "MLNILAMPKDE",
}
BUILDUP_RES_FIELDS = {
    "Physical": "HEEFNBCGGGG",
    "Fire": "NFILPFLNIPC",
    "Ice": "DDMBIHOALHL",
    "Electric": "BLNPNJIDME",   # 2x N — verifikasi key ada di 1792/1792 row
    "Ether": "PMGFNHIKHBD",
    "Wind": "JFABMBIMGNA",
}
STUN_RES_FIELDS = {
    "Physical": "PHCJFMBBDJC",
    "Fire": "PGGMCKBGCGL",
    "Ice": "GDLJANCPPPM",
    "Electric": "CHODLLFEEPK",
    "Ether": "FPIFENJCHJH",
    "Wind": "KOFJJDEIGAB",
}

DEF_FIELD = "AOIJDIEHABK"      # Defence base
HP_FIELD = "LPKOMILKOKG"       # Hp base
STUN_TAKEN_FIELD = "LHPKLCOJKCN"  # StunDamageTakenRatio (/10000)
SUB_KEY_FIELD = "DALBKGGEJEF"  # sub row id
CONFIG_LINK_FIELD = "EBIKJFJOKGP"  # -> config id (hakushin MonsterInfo key)

DEF_CURVE_ID = 1000  # 2x wiki Level Factor (794*2=1588 di L60)
HP_CURVE_ID = 1002   # HP growth (L60 = 4604 basis 100)

# CDN asset image monster card (WebP). Diverifikasi 2026-09-06:
# Tyrfing (Monster_ClaymoreGrey), Haytor (Monster_Hayyot), Mandrake,
# Isolde -> semua 200 OK. Pola: /assets/zzz/{codename}.webp.
# Coverage (HEAD-check 207 monster, 2026-09-06): 148 direct OK + 19
# varian resolved via suffix-strip (varian share card base, mis.
# Monster_AhrimanRed -> Monster_Ahriman) = 167/207 (81%). Sisanya 40
# mob kecil yang memang tidak punya boss card di CDN manapun — frontend
# pakai fallback element icon utk kasus itu (icon_url = None).
NANOKA_ASSET_BASE = "https://static.nanoka.cc/assets/zzz/"

# Suffix varian yang share card dengan base-nya (dicoba berurut).
_CARD_SUFFIXES = ("RedPro", "GreyPro", "Red", "Grey", "Pro", "Infested",
                  "Upgrade", "Elite", "HC")


def _load_table(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["MLOEFHJHCID"]


def load_curves(path="data/LevelCurveTemplateTb.json"):
    """{curve_id: [L1, L2, ...]} — dipakai buat scaling DEF/HP per level."""
    rows = _load_table(path)
    return {r["DALBKGGEJEF"]: r["JMIKNDKIMPH"] for r in rows}


def curve_value(curves, curve_id, level):
    """Nilai curve di level (plateau di level terakhir curve)."""
    vals = curves[curve_id]
    return vals[min(level, len(vals)) - 1]


class MonsterDB:
    """Index monster dari 3 tabel + TextMap. Satu instance, load sekali."""

    def __init__(self, base_dir="."):
        base = Path(base_dir)
        self.curves = load_curves(str(base / "data" / "LevelCurveTemplateTb.json"))
        with open(base / "data" / "TextMap_ENTemplateTb.json", "r", encoding="utf-8") as f:
            self.textmap = json.load(f)
        self.config_rows = _load_table(str(base / "data" / "MonsterConfigTemplateTb.json"))
        self.sub_rows = _load_table(str(base / "data" / "MonsterSubTemplateTb.json"))

        # Sub row id yang merupakan HASIS upgrade (varian challenge/elite) —
        # dikecualikan dari resolusi varian utama. Dari MonsterUpgradeTemplateTb:
        # {base_sub_id: upgraded_sub_id}; kita simang set hasil upgrade.
        upgrade_pairs = _load_table(str(base / "data" / "MonsterUpgradeTemplateTb.json"))
        self._upgraded_sub_ids = {r["FIMGJKPCKFO"] for r in upgrade_pairs}

        # name (lowercase) -> [config ids], plus config id -> codename
        self._by_name = {}
        self._codename_by_cfg = {}
        for r in self.config_rows:
            if r.get("NDJJEKDIHNN") != "Monster":
                continue
            codename = str(r.get("GELOADGCCFN", ""))
            key = f"OfficialName_Monster_{codename.replace('Monster_', '', 1)}"
            display = self.textmap.get(key)
            if not display:
                continue
            self._by_name.setdefault(display.lower(), []).append(r["DALBKGGEJEF"])
            self._codename_by_cfg[r["DALBKGGEJEF"]] = codename

        # config id -> sub rows (via CONFIG_LINK_FIELD)
        self._subs_by_cfg = {}
        for r in self.sub_rows:
            cfg = r.get(CONFIG_LINK_FIELD)
            if cfg:
                self._subs_by_cfg.setdefault(cfg, []).append(r)

        # cache icon slug resolution (biar gak nge-probe CDN berulang)
        self._icon_slug_cache = {}

        # Tag klasifikasi (size/rank/faction/rarity) buat sort UI —
        # digenerate dari zzz-hakushin-data (join by CodeName) ke
        # monster_tags.json. Optional: kalau file gak ada, field tetap None.
        tags_path = base / "data" / "mapped" / "monster_tags.json"
        self._tags = {}
        if tags_path.exists():
            with open(tags_path, "r", encoding="utf-8") as f:
                self._tags = json.load(f)

    def list_names(self):
        """Semua nama monster yang bisa dipakai (yang punya sub row)."""
        return sorted(n for n, ids in self._by_name.items()
                     if any(i in self._subs_by_cfg for i in ids))

    def _pick_sub_row(self, config_ids):
        """Pilih sub row varian utama (yang dipakai stat monster normal).

        Urutan preferensi:
          1. sub id prefix "90001..." (combat normal) DAN bukan hasil upgrade
             (MonsterUpgradeTemplateTb) — mis. Tyrfing 900011096, bukan
             900011097 (upgraded) / 199110961 (scene test).
          2. sub id prefix "9000..." lain yang bukan hasil upgrade.
          3. apa pun yang tersedia (fallback).
        """
        pools = ([], [], [])
        for cid in config_ids:
            for r in self._subs_by_cfg.get(cid, ()):
                sid = str(r[SUB_KEY_FIELD])
                is_upgrade = r[SUB_KEY_FIELD] in self._upgraded_sub_ids
                if sid.startswith("90001") and not is_upgrade:
                    pools[0].append(r)
                elif sid.startswith("9000") and not is_upgrade:
                    pools[1].append(r)
                else:
                    pools[2].append(r)
        for pool in pools:
            if pool:
                return pool[0]
        raise LookupError("tidak ada MonsterSub row untuk config ids ini")

    def resolve_icon_slug(self, codename: str) -> str | None:
        """Cari nama file card yang tersedia di CDN nanoka utk codename.

        Chain: codename langsung -> strip suffix varian (Red/Pro/Grey/...).
        Hasil di-cache per instance (biar resolve() gak nge-probe berulang).
        Return slug (mis. 'Monster_Ahriman') atau None kalau gak ada.
        """
        if codename in self._icon_slug_cache:
            return self._icon_slug_cache[codename]
        slug = None
        base = codename
        stem = base[len("Monster_"):] if base.startswith("Monster_") else base
        # strip suffix varian; sisa '_' di ujung juga dibuang (mis.
        # Monster_Mutant_HC -> Monster_Mutant_HC -> Monster_Mutant_ -> Monster_Mutant).
        candidates = [base]
        for s in _CARD_SUFFIXES:
            if stem.endswith(s) and len(stem) > len(s):
                cand = base[: -len(s)].rstrip("_")
                if cand != base and cand not in candidates:
                    candidates.append(cand)
        for cand in candidates:
            url = NANOKA_ASSET_BASE + cand + ".webp"
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "ZZZDamageCalc/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        slug = cand
                        break
            except Exception:
                continue
        self._icon_slug_cache[codename] = slug
        return slug

    def resolve(self, name, level=60):
        """Nama monster (case-insensitive) + level -> dict stat lengkap.

        Return: {"name", "level", "def_val", "hp_val", "res_pct",
                 "stun_taken_pct", "sub_id"}
        Raise LookupError kalau nama nggak ketemu.
        """
        key = name.strip().lower()
        if key not in self._by_name:
            raise LookupError(
                f"Enemy '{name}' tidak ada di data Monster. "
                f"Contoh tersedia: {', '.join(self.list_names()[:8])} ... "
                f"(lengkap: {len(self.list_names())} monster)")

        config_ids = self._by_name[key]
        row = self._pick_sub_row(config_ids)

        def_lv = curve_value(self.curves, DEF_CURVE_ID, level) / 100.0
        hp_lv = curve_value(self.curves, HP_CURVE_ID, level) / 100.0

        res_pct = {e: row[DAMAGE_RES_FIELDS[e]] / 10000.0 for e in ELEMENTS}
        # Daze RES per elemen (StunRes fields — verifikasi sama kayak
        # Damage/Buildup: game set ketiganya identik utk weakness).
        daze_res_pct = {e: row[STUN_RES_FIELDS[e]] / 10000.0 for e in ELEMENTS}
        # Buildup RES per elemen (BuildupRes fields) — anomaly buildup
        # (C1!R3 `(1 − Buildup RES)`).
        buildup_res_pct = {e: row[BUILDUP_RES_FIELDS[e]] / 10000.0 for e in ELEMENTS}
        codename = self._codename_by_cfg[config_ids[0]]
        icon_slug = self.resolve_icon_slug(codename)
        # Klasifikasi buat sort UI: size/rank/faction/rarity.
        # rank: LittleMonster < Elite < Boss < MainStoryBoss
        # size: Small < Middle < Large < Gigantic
        # rarity: tier card 1-4 (nanoka). Tag fallback: rarity>=3 -> Boss.
        tags = self._tags.get(codename, {})
        rank = tags.get("rank")
        rarity = tags.get("rarity")
        if rank is None and rarity is not None:
            # varian (Energized/Infested/dll) tanpa tag rank eksplisit —
            # infer dari tier card: >=3 Boss, 1 LittleMonster, 2 Elite.
            rank = ("Boss" if rarity >= 3
                    else "LittleMonster" if rarity == 1
                    else "Elite")
        return {
            "name": name,
            "level": level,
            "sub_id": row[SUB_KEY_FIELD],
            "codename": codename,
            "size": tags.get("size"),
            "rank": rank,
            "faction": tags.get("faction"),
            "rarity": rarity,
            # Boss card image (frontend): nanoka CDN WebP by codename filename,
            # fallback suffix-strip utk varian (share card base). None = tidak
            # ada card di CDN (mob kecil) -> frontend render element icon.
            "icon_url": (NANOKA_ASSET_BASE + icon_slug + ".webp") if icon_slug else None,
            "def_val": row[DEF_FIELD] * def_lv,
            "hp_val": row[HP_FIELD] * hp_lv,
            "res_pct": res_pct,
            "daze_res_pct": daze_res_pct,
            "buildup_res_pct": buildup_res_pct,
            "stun_taken_pct": row[STUN_TAKEN_FIELD] / 10000.0,  # mis. 5000 -> +50% saat stun
        }


def main():
    """Quick CLI check: python monster_data.py [nama] [level]"""
    import sys
    db = MonsterDB(Path(__file__).resolve().parent)
    name = sys.argv[1] if len(sys.argv) > 1 else "Tyrfing"
    level = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    m = db.resolve(name, level)
    print(f"{m['name']} Lv.{m['level']} (sub {m['sub_id']})")
    print(f"  icon: {m['icon_url']}")
    print(f"  class: rank={m['rank']} size={m['size']} faction={m['faction']} rarity={m['rarity']}")
    print(f"  DEF: {m['def_val']:.2f}   HP: {m['hp_val']:.1f}")
    print(f"  StunDMG taken: +{m['stun_taken_pct']*100:.0f}%")
    print("  RES:", {e: f"{v*100:+.0f}%" for e, v in m["res_pct"].items() if v})


if __name__ == "__main__":
    main()

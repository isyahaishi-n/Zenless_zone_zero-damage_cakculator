"""
Mindscape combat effect generator - builds `mindscape_mapped.json` from
raw text, continuing the methodology of `wengine_passive_gen.py`.

Context: mindscape M1/M2/M4/M6 previously only had a candidate-extractor
(extract.py -> mindscapes.json display text, extractjson.py ->
candidates.json raw numbers) plus manually curated mindscape_props.json
covering 5 avatars. Full 58-avatar mapping did not exist.

Feasibility findings (2026-08-31, before this module):
1. AvatarTalentTemplateTb.json (datamine, 348 rows = 58 avatars x 6
   levels) is the structured source: PJABHBNCJOI = avatar id,
   PJBKBALOBEH = level 1-6, PADNNKFLNLG = title key,
   EHEONBCLBAG = desc key, CKPJDLGIAHO = REALIGN desc key
   (post-rework; 13 rows differ from base - use it), PPAGKJLLCIM =
   level flag (2 = pure skill bump), DPBEEACCGDC = param text ids.
2. There is NO numeric mindscape table - GFPKLHKBGKG looks like a props
   list but is a per-avatar UI marker (5011-5591, uniform value 1).
   All effect numbers are embedded in text -> text extraction is the
   only route (same as W-Engine).
3. M3/M5 are MECHANICALLY confirmed skill bumps: PPAGKJLLCIM == 2 +
   desc key Common_Talent_Desc + empty params (348/348 rows consistent).

Anti-fabrication methodology (same as W-Engine):
- The ONLY number source is the avatar *_Talent_0X_Desc_01(_Realign)
  text via TextMap EN + ENOverwrite merge; every effect carries
  `evidence` (exact sentence) + `evidence_key`; each level keeps its
  full raw `text`.
- Pattern engine = mindscape patterns first (more specific: healing,
  energy recovery, RES shred, additional DMG off stats, multipliers),
  then weapon patterns from wengine_passive_gen via the parametrized
  extract_sentence_effects.
- Numeric clauses with no effect match that cannot be stripped as
  mechanics -> `unparsed` + needs_review (explicit, never guessed).
- Audit invariant: every effect value MUST appear as a number in its
  own level text (comma-aware: "3,300" != "3300" without parsing).

Ground truth verified against mindscape_props.json (manual curation):
1091 M2 CRIT Rate +15% (toggle), 1371 M2 ignores 15% Ether RES,
1371 M4 EX Special DMG +30%/stack, 1421 M1 team DMG +10%,
1421 M4 healing +25%.
"""

import json
import re
import sys

from wengine_passive_gen import (
    NUM, extract_sentence_effects, load_textmap, make_condition,
    mech_cooldown, mech_duration, mech_stacks, stat_slug, detect_scope,
    strip_mechanics, clean_text, split_sentences, PATTERNS,
)

TEMPLATE_FILE = "data/AvatarTalentTemplateTb.json"
TEXTMAP_FILE = "data/TextMap_ENTemplateTb.json"
OVERWRITE_FILE = "data/TextMap_ENOverwriteTemplateTb.json"
AVATARS_FILE = "data/avatars.json"
OUT_FILE = "mindscape_mapped.json"

ROWS_KEY = "MLOEFHJHCID"

# number with thousands comma ("3,300%") - mindscape corpus uses these
NUMC = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
# group-wrapped form for safe composition (NUMC contains a top-level |)
NUMC_G = "(?:" + NUMC + ")"
# slash-list values ("80%/90%/100%", "6/9", "40/20")
VALSLASH = NUMC_G + r"\s*%?(?:\s*/\s*" + NUMC_G + r"\s*%?)*"

ELEM = r"Physical|Fire|Ice|Electric|Ether|Wind"
ALL_ELEM = r"All-Attribute|" + ELEM

EFFECT_LEVELS = (1, 2, 4, 6)
SKILL_BUMP_LEVELS = (3, 5)

_TEAM_RE = re.compile(
    r"\b(?:all\s+squad\s+members|all\s+units|all\s+(?:friendly|friendly\s+units)|"
    r"whole\s+squad|all\s+agents|every\s+character\s+in\s+the\s+squad|"
    r"squad\s+members\b)", re.I)


def parse_num(s: str) -> float:
    return float(s.replace(",", "").rstrip("%").strip())


def parse_val(s: str):
    """'80%/90%/100%' -> [80.0, 90.0, 100.0]; scalar otherwise."""
    if "/" in s:
        return [parse_num(x) for x in s.split("/")]
    return parse_num(s)


def num_tokens_c(text: str):
    """Comma-aware number tokens (for the anti-fabrication audit)."""
    return re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", text)


# --------------------------------------------------------------- resources
# Named character resources that are NOT damage-relevant stats. Grant /
# consume sentences over these get stripped as mechanics.

RESOURCE_NAMES = [
    "Flash Freeze", "Assist Points", "Qingming Sword Force",
    "Blazing Heart", "Remnant Flame", "Brilliant Starlight",
    "Armor Break Rounds", "Guard Feathers", "Flight Feathers",
    "Tone Clusters", "Bottled Heat", "Corrosive Chill", "Fandom Power",
    "Thunder's Cry", "Electro Blitz", "Bone-Deep Corrosion",
    "Condensed Ink", "Enhanced Shotshells", "Positive Reviews",
    "All-Out Cheering", "Technique Points", "Blade Etiquette",
    "Sugar Points", "Trial by Cold", "Steel Charge", "Fallen Frost",
    "Electro Prison", "Turbocharged", "Voidflares", "Momentum",
    "Windbite", "Adrenaline", "Resolve", "special s", "Power",
    "Charge", "Clarity", "Vortex", "Purge", "Venom", "Zap", "Heat",
    "Echo", "Chords",
]
RESOURCE = "|".join(
    re.escape(n).replace(r"\ ", r"\s+")
    for n in sorted(RESOURCE_NAMES, key=len, reverse=True)
)

_R_GRANT = re.compile(
    r"(?:gains?|accumulat\w+|obtains?|restor\w+|recovers?|grants?|"
    r"generates?|gaining)\s+"
    r"(?:an?\s+additional\s+|up\s+to\s+|a\s+max(?:imum)?\s+of\s+|only\s+)?"
    r"(?:\d+\s+consecutive\s+)?" + NUMC_G + r"\s*"
    r"(?:%|points?\s+of\s+|point\s+of\s+|stacks?\s+of\s+|special\s+)?"
    r"(?:" + RESOURCE + r")\b")
_R_CONSUME = re.compile(
    r"(?:consumes?|consume|consumed)\s+"
    r"(?:only\s+|an?\s+additional\s+|up\s+to\s+|all\s+)?"
    r"(?:\d+\s+consecutive\s+)?" + NUMC_G + r"\s*"
    r"(?:stacks?\s+of\s+|points?\s+of\s+)?"
    r"(?:" + RESOURCE + r")\b")
_R_STANDALONE = re.compile(
    NUMC_G + r"\s*(?:%|points?\s+of\s+|point\s+of\s+|stacks?\s+of\s+|special\s+)?"
    r"(?:" + RESOURCE + r")\b")
_R_WITH = re.compile(r"with\s+" + NUMC_G + r"\s+" + RESOURCE + r"\b")
_R_EVERY = re.compile(r"every\s+" + NUMC_G + r"\s+stacks?\s+of\b")
_R_SET = re.compile(
    r"(?:" + RESOURCE + r")[^,.;]{0,40}?(?:increases?|is\s+increased)\s+to\s+"
    + NUMC_G + r"\b")
_R_LIMIT = re.compile(
    r"limit\s+of\s+(?:" + RESOURCE + r")\s+from\s+" + NUMC_G
    + r"\s+to\s+" + NUMC_G)


# ---------------------------------------------------------- effect patterns
# ORDER MATTERS: mindscape patterns are more specific and come first so
# they win dedup tie-breaks against generic weapon stat patterns
# (e.g. "HP recovery is increased by 25%" is healing, NOT an HP stat).

def _mind_patterns():
    pats = []

    def add(name, rx, builder):
        pats.append((name, rx, builder))

    # --- RES shred on target (multi forms) ---
    add("res_shred_multi",
        re.compile(
            r"reduc\w+\s+((?:" + ALL_ELEM + r")\s+RES(?:\s+and)?\s*)+"
            r"by\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "res_shred", "unit": "percent",
                      "elements": re.findall(
                          r"(" + ALL_ELEM + r")(?=\s+RES)", m.group(1))})
    add("res_shred_suffer",
        re.compile(r"suffer\s+a\s*(?P<val>" + NUM + r")\s*%\s+"
                   r"(?P<elem>" + ALL_ELEM + r")\s+RES\s+reduction"),
        lambda m, s: {"effect_type": "res_shred", "unit": "percent",
                      "elements": [m.group("elem")]})
    add("res_shred",
        re.compile(
            r"(?:(?P<elem>" + ALL_ELEM + r")\s+)?RES\s+(?:is\s+)?"
            r"(?:reduced|decreases?d?)\s+by\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "res_shred", "unit": "percent",
                      "elements": ([m.group("elem")] if m.group("elem")
                                   else ["All"])})

    # --- "N% of the target's X RES/DEF is ignored" ---
    add("pct_ignored",
        re.compile(
            r"(?P<val>" + NUM + r")\s*%\s+of\s+the\s+(?:enemy|target)'s\s+"
            r"(?P<what>" + ALL_ELEM + r"\s+RES|DEF)\s+is\s+ignored"),
        lambda m, s: (
            {"effect_type": "res_ignore", "unit": "percent",
             "elements": [m.group("what").replace(" RES", "")]}
            if "RES" in m.group("what")
            else {"effect_type": "def_ignore", "unit": "percent"}))

    # --- ignore N% [of ...] Elem RES / DEF (looser than weapon) ---
    add("ignore_res_mind",
        re.compile(
            r"ignor\w*\s*(?:an\s+additional\s+)?(?P<val>" + NUM + r")\s*%\s*"
            r"(?:of\s+[^,.;]{0,50}?\b)?"
            r"(?P<elem>" + ALL_ELEM + r")\s+RES\b"),
        lambda m, s: {"effect_type": "res_ignore", "unit": "percent",
                      "elements": [m.group("elem")]})
    add("ignore_def_mind",
        re.compile(
            r"ignor\w*\s*(?:an\s+additional\s+)?(?P<val>" + NUM + r")\s*%\s*"
            r"of\s+[^,.;]{0,50}?\bDEF\b"),
        lambda m, s: {"effect_type": "def_ignore", "unit": "percent"})

    # --- Stun DMG Multiplier ---
    add("stun_dmg_mult",
        re.compile(
            r"Stun\s+DMG\s+Multiplier[^,.;]{0,150}?(?:is\s+)?"
            r"(?:increases?|increased)\s+(?:to|by)\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "stun_dmg_mult", "unit": "percent"})
    add("stun_dmg_mult_gain",
        re.compile(
            r"gain\w*\s+an?\s+additional\s+(?P<val>" + NUM + r")\s*%\s+"
            r"Stun\s+DMG\s+Multiplier"),
        lambda m, s: {"effect_type": "stun_dmg_mult", "unit": "percent"})

    # --- Sheer DMG ---
    add("sheer_dmg",
        re.compile(r"(?P<val>" + NUM + r")\s*%\s+Sheer\s+DMG\s+increase"),
        lambda m, s: {"effect_type": "sheer_dmg_bonus", "unit": "percent"})

    # --- shield from % Max HP ---
    add("shield_grant",
        re.compile(
            r"[Ss]hield[^,.;]{0,30}?(?:that\s+)?equals?\s+to\s*"
            r"(?P<val>" + NUM + r")\s*%\s*of\s+[\w\s'-]{0,40}?Max\s+HP"),
        lambda m, s: {"effect_type": "shield_grant", "scale_stat": "Max HP",
                      "unit": "percent"})

    # --- shield value up (long gap over skill names) ---
    add("shield_up_long",
        re.compile(
            r"[Ss]hield\s+value[^,.;]{0,120}?(?:is\s+)?increased\s+by\s*"
            r"(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "shield_bonus", "unit": "percent"})

    # --- healing / HP recovery ---
    add("healing_up",
        re.compile(
            r"(?:HP\s+recovery|heal\w*)[^,.;]{0,60}?"
            r"(?:is\s+)?(?:increased?\s+by|increases\s+by)\s*"
            r"(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "healing_bonus", "unit": "percent"})
    add("healing_restore",
        re.compile(r"restor\w+[^,.;]{0,30}?(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "healing_bonus", "unit": "percent"})

    # --- energy recovery/gain/grant (loose verb+gap) ---
    add("energy_recover",
        re.compile(
            r"(?:recover[s]?|restor\w+|gains?|grants?)\s+[a-zA-Z\s]{0,25}?"
            r"(?P<val>" + NUMC + r")\s*Energy\b"),
        lambda m, s: {"effect_type": "energy_flat", "unit": "energy"})

    # --- decibel variants ---
    add("decibel_pct_more",
        re.compile(r"gains?\s+(?P<val>" + NUM + r")\s*%\s*more\s+Decibels"),
        lambda m, s: {"effect_type": "decibel_bonus", "unit": "percent"})
    add("decibel_flat_more",
        re.compile(r"generates?\s+(?P<val>" + NUMC + r")\s*more\s+Decibels"),
        lambda m, s: {"effect_type": "decibel_bonus", "unit": "decibels"})
    add("decibel_restore",
        re.compile(r"restor\w+\s+(?P<val>" + NUMC + r")\s*Decibels"),
        lambda m, s: {"effect_type": "decibel_bonus", "unit": "decibels"})
    add("decibel_grant",
        re.compile(
            r"grants?\s+[a-zA-Z\s]{0,40}?(?P<val>" + NUMC + r")\s*Decibels"),
        lambda m, s: {"effect_type": "decibel_bonus", "unit": "decibels"})
    add("decibel_restored",
        re.compile(
            r"(?P<val>" + NUMC + r")\s*Decibels\s+are\s+(?:also\s+)?restored"),
        lambda m, s: {"effect_type": "decibel_bonus", "unit": "decibels"})
    add("decibel_cap",
        re.compile(r"Decibel\s+limit\s+increases?\s+by\s*(?P<val>" + NUMC + r")"),
        lambda m, s: {"effect_type": "decibel_cap", "unit": "decibels"})

    # --- anomaly buildup (percent more/increased) ---
    add("anomaly_buildup",
        re.compile(
            r"(?P<val>" + NUM + r")\s*%\s*(?:more|increased)\s+"
            r"(?:(?:" + ELEM + r")\s+)?Anomaly\s+Buildup"),
        lambda m, s: {"effect_type": "stat",
                      "stat": "Anomaly Buildup Rate", "unit": "percent"})

    # --- PEN Ratio prefix form ---
    add("pen_ratio",
        re.compile(r"(?P<val>" + NUM + r")\s*%\s+increased\s+PEN\s+Ratio"),
        lambda m, s: {"effect_type": "stat", "stat": "PEN Ratio",
                      "unit": "percent"})

    # --- "<Name> Coefficient increases by N%" ---
    add("coefficient",
        re.compile(
            r"(?P<stat>[A-Z][\w]*(?:\s+[A-Z][\w]*)?\s+Coefficient)\s+"
            r"(?:is\s+)?increased?\s+by\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "stat", "stat": m.group("stat"),
                      "unit": "percent"})

    # --- base CRIT Rate/DMG "is N%" ---
    add("base_crit",
        re.compile(
            r"(?P<stat>CRIT\s+Rate|CRIT\s+DMG)\s+is\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "stat", "stat": m.group("stat"),
                      "unit": "percent"})

    # --- element-specific "takes N% more X DMG" / "suffers N% increased DMG" ---
    add("takes_more_dmg",
        re.compile(
            r"takes?\s+(?P<val>" + NUM + r")\s*%\s+more\s+"
            r"(?P<elem>" + ELEM + r")\s+DMG"),
        lambda m, s: {"effect_type": "damage_bonus", "unit": "percent",
                      "elements": [m.group("elem")]})
    add("suffers_dmg",
        re.compile(r"suffers\s+(?P<val>" + NUM + r")\s*%\s+increased\s+DMG"),
        lambda m, s: {"effect_type": "damage_bonus", "unit": "percent"})

    # --- "deal N% [more|increased|extra] [Elem] DMG" (looser than weapon) ---
    add("deals_dmg_loose",
        re.compile(
            r"deals?\s+(?:an\s+additional\s+)?(?P<val>" + NUM + r")\s*%\s*"
            r"(?:more\s+|increased\s+|extra\s+)*"
            r"(?:(?:" + ELEM + r")\s+)?DMG"),
        lambda m, s: {"effect_type": "damage_bonus", "unit": "percent"})

    # --- DMG bonus over long comma-containing skill lists ---
    add("dmg_up_long",
        re.compile(
            r"DMG\s+dealt\s+by\s+.{0,250}?by\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "damage_bonus", "unit": "percent"})

    # --- daze variants ---
    add("daze_additional",
        re.compile(
            r"deals?\s+(?:an?\s+additional\s+)?(?P<val>" + NUM + r")\s*%\s*"
            r"(?:extra|additional)\s+Daze"),
        lambda m, s: {"effect_type": "daze_bonus", "unit": "percent"})
    add("daze_increased",
        re.compile(r"inflict\s+(?P<val>" + NUM + r")\s*%\s+increased\s+Daze"),
        lambda m, s: {"effect_type": "daze_bonus", "unit": "percent"})
    add("daze_equal_stat",
        re.compile(
            r"Daze\s+equal\s+to\s*(?P<val>" + NUMC + r")\s*%\s*of\s+"
            r"[\w\s'-]{0,40}?(?P<stat>Impact|ATK)"),
        lambda m, s: {"effect_type": "daze_bonus", "scale_stat": m.group("stat"),
                      "unit": "percent"})

    # --- additional DMG scaling off a stat ("DMG equal to N% of X's ATK") ---
    add("add_dmg_eq",
        re.compile(
            r"(?:DMG|damage)\s+(?:equal\s+to|up\s+to|equal)\s*"
            r"(?P<val>" + VALSLASH + r")\s*of\s+[\w\s&'-]{0,40}?"
            r"(?P<stat>Sheer\s+Force|Anomaly\s+Proficiency|Max\s+HP|ATK|DEF|"
            r"Impact)\b"),
        lambda m, s: {"effect_type": "additional_dmg",
                      "scale_stat": m.group("stat"), "unit": "percent"})
    # --- "N% [of] STAT ... as DMG" ("300% of Ben's DEF as DMG") ---
    add("add_dmg_as",
        re.compile(
            r"(?P<val>" + VALSLASH + r")\s*(?:of\s+)?"
            r"(?:[\w\s&'-]{0,40}?\s+)?"
            r"(?P<stat>Sheer\s+Force|Anomaly\s+Proficiency|Max\s+HP|ATK|DEF|"
            r"Impact)\b[^,.;]{0,30}?\s+as\s+(?:an?\s+)?"
            r"(?:additional\s+|extra\s+)?(?:instance\s+of\s+)?"
            r"(?:(?:" + ELEM + r")\s+)?DMG"),
        lambda m, s: {"effect_type": "additional_dmg",
                      "scale_stat": m.group("stat"), "unit": "percent"})
    # --- "equal to N% of the original ..." ---
    add("original_multiplier",
        re.compile(
            r"equal\s+to\s*(?P<val>" + VALSLASH + r")\s*of\s+the\s+original"),
        lambda m, s: {"effect_type": "original_multiplier",
                      "unit": "percent"})

    # --- passive amplification ("increases to 130% of its original value") ---
    add("amplify_original",
        re.compile(
            r"(?:increases?|increased|raised|raising)\s+to\s*"
            r"(?P<val>" + NUM + r")\s*%\s+of\s+(?:its|the)\s+original"),
        lambda m, s: {"effect_type": "passive_amplification",
                      "unit": "percent"})
    add("amplify_to",
        re.compile(
            r"(?:increases?|increased|increasing|raised|raising)\s+to\s+"
            r"(?:a\s+maximum\s+of\s+)?(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "passive_amplification",
                      "unit": "percent"})

    # --- multiplier increases ---
    add("multiplier",
        re.compile(
            r"(?:DMG\s+)?multiplier[^,.;]{0,80}?"
            r"(?:increases?|increased)\s+(?:to|by)\s*(?P<val>" + NUMC + r")\s*%"),
        lambda m, s: {"effect_type": "multiplier_bonus", "unit": "percent"})
    add("multiplier_this",
        re.compile(
            r"increases?\s+(?:this|the)\s+multiplier\s+by\s*"
            r"(?P<val>" + NUMC + r")\s*%"),
        lambda m, s: {"effect_type": "multiplier_bonus", "unit": "percent"})
    add("multiplier_fixed",
        re.compile(
            r"(?:by|at)\s+a\s+fixed\s*(?P<val>" + NUMC + r")\s*%\s*multiplier"),
        lambda m, s: {"effect_type": "multiplier_bonus", "unit": "percent"})

    # --- ramp cap variant ("up to a maximum increase of 32%") ---
    add("ramp_cap_mind",
        re.compile(
            r"up\s+to\s+a\s+maximum\s+increase\s+of\s*(?P<val>" + NUM + r")\s*%"),
        lambda m, s: {"effect_type": "ramp_cap", "unit": "percent"})

    # --- resource cost reduction ---
    add("cost_reduction",
        re.compile(
            r"(?:cost|Cost)[^,.;]{0,60}?reduced\s+by\s*(?P<val>" + NUM + r")\s*\.?"
        ),
        lambda m, s: {"effect_type": "cost_reduction", "unit": "flat"})

    # --- duration bonus (percent OR seconds) ---
    add("duration_up",
        re.compile(
            r"duration[^,.;]{0,80}?(?:is\s+)?increases?\s+by\s*"
            r"(?P<val>" + NUM + r")\s*(?P<unit>%|s\b|sec\b|seconds\b)?"),
        lambda m, s: {"effect_type": "duration_bonus",
                      "unit": ("percent" if m.group("unit") == "%"
                               else "seconds")})

    # --- stat conversion ("increases by an extra 6% of ... initial ATK") ---
    add("stat_conversion",
        re.compile(
            r"increases?\s+by\s+an?\s+extra\s*(?P<val>" + NUM + r")\s*%\s*of\s+"
            r"[\w\s']{0,30}?(?:initial\s+)?(?P<stat>ATK|Max\s+HP|DEF)"),
        lambda m, s: {"effect_type": "stat_conversion",
                      "scale_stat": m.group("stat"), "unit": "percent"})

    # --- stat cap set ("maximum Sheer Force ... increases to 720") ---
    add("stat_cap",
        re.compile(
            r"maximum\s+(?P<stat>Sheer\s+Force|Anomaly\s+Proficiency|Energy)\s+"
            r"[^,.;]{0,40}?increases\s+to\s*(?P<val>" + NUM + r")\b"),
        lambda m, s: {"effect_type": "stat_cap", "stat": m.group("stat"),
                      "unit": "flat"})

    return pats


MINDSCAPE_PATTERNS = _mind_patterns()
COMBINED_PATTERNS = MINDSCAPE_PATTERNS + PATTERNS

# ------------------------------------------------------ mechanics stripping
# Mindscape-specific numeric mechanic phrases (non-damage resources,
# thresholds, ordinals, cooldowns, caps). Applied together with the
# weapon strip list via strip_mechanics(sentence, extra_res).

MINDSCAPE_STRIP_RES = [
    _R_GRANT, _R_CONSUME, _R_STANDALONE, _R_WITH, _R_EVERY, _R_SET, _R_LIMIT,
    # thresholds / caps
    re.compile(r"less\s+than(?:\s+or\s+equal\s+to)?\s+" + NUM),
    re.compile(r"for\s+(?:every|each)\s+(?:additional\s+)?" + NUM
               + r"[^,.;]{0,60},"),
    re.compile(r"up\s+to\s+a\s+maximum\s+of\s+" + NUM + r"\b"),
    re.compile(r",\s*up\s+to\s+" + NUM + r"\s*%"),
    re.compile(r"up\s+to\s+" + NUM + r"\s+draws\b"),
    re.compile(r"from\s+" + NUM + r"\s+to\s+" + NUM),
    re.compile(r"reaches\s+" + NUM),
    re.compile(r"recovered\s+to\s+" + NUM + r"\b"),
    re.compile(r"dropping\s+below\s+" + NUM),
    re.compile(r"not\s+at\s+maximum"),
    re.compile(r"below\s+" + NUM + r"\s*%"),
    # time / frequency
    re.compile(r"for\s+up\s+to\s+" + NUM + r"\s*" + r"(?:s|sec|seconds)\b"),
    re.compile(r"(?:for|lasting|lasts?|last)\s+(?:up\s+to\s+an?\s+additional\s+|up\s+to\s+|an?\s+additional\s+)?" + NUM + r"\s*(?:s|sec|seconds)\b"),
    re.compile(r"maximum\s+duration\s+of\s+" + NUM + r"\s*(?:s|sec|seconds)\b"),
    re.compile(r"duration\s+can\s+increase\s+up\s+to\s+" + NUM + r"\s+times"),
    re.compile(r"once\s+per\s+" + NUM + r"\s*(?:s|sec|seconds)\b"),
    re.compile(r"per\s+" + NUM + r"\s*(?:s|sec|seconds)\b"),
    re.compile(r"every\s+" + NUM + r"\s+times"),
    re.compile(r"\d+\s+times\b"),
    re.compile(r"up\s+to\s+once\s+per\s+second"),
    re.compile(r"within\s+" + NUM + r"\s*(?:s|sec|seconds)\b"),
    re.compile(r"regen\s+of\s+" + NUM + r"(?:\.\d+)?/s"),
    # ordinals / counts
    re.compile(r"\d+(?:st|nd|rd|th)\b"),
    re.compile(NUM + r"\s+consecutive\b"),
    re.compile(r"\d+-bullet"),
    re.compile(r"at\s+(?:most\s+)?" + NUM + r"\s+stacks?\b"),
    re.compile(r"first\s+" + NUM + r"\b"),
    re.compile(r"perform\s+up\s+to\s+" + NUM + r"\b"),
    re.compile(r"gains?\s+" + NUM + r"\s+additional\s+activations?"),
    re.compile(r"triggers?\s+" + NUM + r"\s+(?:special\s+)?"
               r"(?:instance|instances|extra|missile|missiles|popcorns?)\b"),
    re.compile(r"\bNUMPLACEHOLDER\b"),  # removed below
]
# drop the placeholder entry added for clarity
MINDSCAPE_STRIP_RES = [r for r in MINDSCAPE_STRIP_RES
                       if r.pattern != r"\bNUMPLACEHOLDER\b"]
MINDSCAPE_STRIP_RES += [
    # reductions of mechanics, not stats
    re.compile(r"cooldown[^,.;]{0,40}?reduced\s+(?:to|by)\s+"
               + NUM + r"(?:\s*%|\s*(?:s|sec|seconds))?\b"),
    re.compile(r"interval[^,.;]{0,40}?reduced\s+to\s+" + NUM + r"\s*"
               + r"(?:s|sec|seconds)\b"),
    re.compile(r"(?:amount|total)[^,.;]{0,60}?reduced\s+to\s+" + NUM),
    re.compile(r"accumulation\s+rate\s+is\s+increased\s+by\s+" + NUM + r"\s*%"),
    re.compile(r"consumes?\s+(?:an?\s+additional\s+)?" + NUM + r"\s+Energy"),
    re.compile(r"consuming\s+a\s+total\s+of\s+" + NUM + r"\s+Energy"),
    re.compile(r"a\s+total\s+of\s+" + NUM + r"\s+Energy\s+is\s+consumed"),
    re.compile(NUM + r"\s+stacks?\s+is\s+consumed"),
    re.compile(r"increases?\s+to\s+" + NUM + r"\s+stacks"),
    re.compile(r"Charges?\s+are\s+increased\s+to\s+" + NUM),
    re.compile(r"number\s+of\s+times[^,.;]{0,80}?increases?\s+to\s+" + NUM),
    re.compile(r"max(?:imum)?\s+stack\s+(?:limit|count)[^,.;]{0,40}?"
               r"(?:increases?\s+to|is\s+increased\s+to)\s+" + NUM),
    re.compile(r"limit\s+of\s+Heat\s+from\s+" + NUM + r"\s+to\s+" + NUM),
    re.compile(r"special\s+s\b"),
    re.compile(r"gains?\s+" + NUM + r"\s+special\s+s\b"),
    re.compile(r"gaining\s+" + NUM + r"\s+special\s+s\b"),
    re.compile(r"persists?\s+for\s+an?\s+additional\s+" + NUM + r"\s*"
               + r"(?:s|sec|seconds)\b"),
]


def parse_level(text: str, text_key: str):
    """One mindscape level -> (effects, needs_review)."""
    sentences = split_sentences(text)
    effects = []

    for j, sent in enumerate(sentences):
        found = extract_sentence_effects(sent, COMBINED_PATTERNS)
        for m in found:
            extra = dict(m["extra"])
            sent_prev = sentences[j - 1] if j > 0 else None
            cond = make_condition(sent, sent_prev)
            val = parse_val(m["val_str"])
            effect = {
                "key": (stat_slug(extra["stat"]) if extra.get("stat")
                        else extra.get("effect_type", "unparsed")),
                "effect_type": extra.get("effect_type", "unparsed"),
                "condition": cond,
                "unconditional": cond["type"] == "always",
                "evidence": sent,
                "evidence_key": text_key,
            }
            if isinstance(val, list):
                effect["values"] = val
            else:
                effect["value"] = val
            for k, v in extra.items():
                if k != "effect_type":
                    effect[k] = v
            if _TEAM_RE.search(sent):
                effect["target"] = "team"
            elem, skills = detect_scope(sent)
            if elem:
                effect.setdefault("elements", elem)
            if skills:
                effect["skill_types"] = skills
            for mk, mv in (
                ("duration_seconds", mech_duration(sent)),
                ("stacks_max", mech_stacks(sent)),
                ("cooldown_seconds", mech_cooldown(sent)),
            ):
                if mv is not None:
                    effect[mk] = mv
            effects.append(effect)

        if not found:
            leftover = strip_mechanics(sent, MINDSCAPE_STRIP_RES)
            if num_tokens_c(leftover):
                effects.append({
                    "key": "unparsed",
                    "effect_type": "unparsed",
                    "condition": make_condition(sent),
                    "unconditional": False,
                    "value": None,
                    "evidence": sent,
                    "evidence_key": text_key,
                    "needs_review": True,
                    "review_reason":
                        "no effect pattern matched this numeric clause",
                })

    # unique keys per level
    seen = {}
    for e in effects:
        base = e["key"]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            e["key"] = f"{base}_{seen[base]}"

    needs_review = any(e.get("needs_review") for e in effects)
    return effects, needs_review


def resolve_key(tm, *keys):
    for k in keys:
        if k and k in tm:
            return k, tm[k]
    return None, None


def main():
    tm = load_textmap()
    template = json.load(open(TEMPLATE_FILE, encoding="utf-8"))[ROWS_KEY]
    avatars = json.load(open(AVATARS_FILE, encoding="utf-8"))

    rows = {}
    for r in template:
        rows.setdefault(r["PJABHBNCJOI"], {})[r["PJBKBALOBEH"]] = r

    out_avatars = []
    n_effects = 0
    n_unparsed = 0
    n_review = 0

    for aid in sorted(rows):
        meta = avatars[str(aid)]
        name = tm.get(meta["Name"], f"<unresolved:{meta['Name']}>")

        levels = {}
        for lvl in range(1, 7):
            r = rows[aid][lvl]
            # prefer realign (post-rework) text
            text_key, raw = resolve_key(tm, r.get("CKPJDLGIAHO"),
                                        r.get("EHEONBCLBAG"))
            title_key, title = resolve_key(tm, r.get("OKHILPNCLKH"),
                                           r.get("PADNNKFLNLG"))
            if raw is None:
                levels[str(lvl)] = {
                    "kind": "missing_text",
                    "title_key": title_key, "title": title or "",
                    "needs_review": True,
                }
                continue
            text = clean_text(raw)

            if lvl in SKILL_BUMP_LEVELS:
                # mechanical verification: flag 2 + Common_Talent_Desc +
                # empty params
                mech_ok = (r.get("PPAGKJLLCIM") == 2
                           and r.get("EHEONBCLBAG") == "Common_Talent_Desc"
                           and not r.get("DPBEEACCGDC"))
                levels[str(lvl)] = {
                    "kind": "skill_bump",
                    "title_key": title_key,
                    "title": title or "",
                    "text_key": text_key,
                    "effect": ("Basic Attack, Dodge, Assist, Special Attack, "
                               "and Chain Attack Lv. +2"),
                    "mechanically_verified": bool(mech_ok),
                    "needs_review": not mech_ok,
                }
                continue

            effects, needs_review = parse_level(text, text_key)
            for e in effects:
                if e["effect_type"] == "unparsed":
                    n_unparsed += 1
            n_effects += len(effects)
            if needs_review:
                n_review += 1
            levels[str(lvl)] = {
                "kind": "effects",
                "title_key": title_key,
                "title": title or "",
                "text_key": text_key,
                "text": text,
                "effects": effects,
                "needs_review": needs_review,
            }

        codename = None
        tk = rows[aid][1].get("PADNNKFLNLG") or ""
        m = re.match(r"(.+)_Talent_01_Title$", tk)
        if m:
            codename = m.group(1)

        out_avatars.append({
            "id": aid,
            "name": name,
            "codename": codename,
            "rarity": meta["Rarity"],
            "profession": meta["ProfessionType"],
            "levels": levels,
        })

    doc = {
        "schema_version": 1,
        "purpose": ("Mindscape combat effect mapping (M1/M2/M4/M6) for the "
                    "ZZZ damage calculator; M3/M5 are skill-level bumps"),
        "generated_by": "mindscape_passive_gen.py",
        "generation_policy": (
            "ALL effect values are extracted mechanically from the raw "
            "avatar *_Talent_0X_Desc_01(_Realign) text of the same avatar id "
            "via TextMap EN + ENOverwrite merge (Realign post-rework text "
            "preferred). No values are hardcoded. Every effect carries "
            "evidence (exact sentence) + evidence_key; each level keeps its "
            "full raw text. M3/M5 skill bumps are mechanically verified from "
            "template flags (PPAGKJLLCIM==2 + Common_Talent_Desc + empty "
            "params). Numeric clauses that no pattern matched are kept as "
            "effect_type='unparsed' with needs_review=true."
        ),
        "local_dataset": {
            "avatar_count": len(out_avatars),
            "source_files": [TEMPLATE_FILE, TEXTMAP_FILE, OVERWRITE_FILE,
                             AVATARS_FILE],
            "template_source_schema": {
                "template_file": TEMPLATE_FILE,
                "avatar_id_field": "PJABHBNCJOI",
                "level_field": "PJBKBALOBEH",
                "title_key_field": "PADNNKFLNLG",
                "desc_key_field": "EHEONBCLBAG",
                "desc_key_realign_field": "CKPJDLGIAHO",
                "param_ids_field": "DPBEEACCGDC",
                "level_flag_field": "PPAGKJLLCIM",
                "ui_marker_field": "GFPKLHKBGKG",
                "note": ("GFPKLHKBGKG is a per-avatar UI marker "
                         "(5011-5591), NOT stat props - there is no numeric "
                         "mindscape table; effect numbers are embedded in "
                         "text."),
            },
            "effect_count": n_effects,
            "unparsed_effect_count": n_unparsed,
            "levels_needing_review": n_review,
        },
        "avatars": out_avatars,
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT_FILE}: {len(out_avatars)} avatars, "
          f"{n_effects} effects, {n_unparsed} unparsed, "
          f"{n_review} levels need review")


# ------------------------------------------------------------------- audit

def _find(doc, aid):
    return next(a for a in doc["avatars"] if a["id"] == aid)


def _effects(level_entry):
    return level_entry.get("effects", [])


def _values(e):
    if e.get("values") is not None:
        return e["values"]
    v = e.get("value")
    return [v] if v is not None else []


def audit():
    doc = json.load(open(OUT_FILE, encoding="utf-8"))
    ok = True

    # 1. structure: 58 avatars x 6 levels
    avatars = doc["avatars"]
    assert len(avatars) == 58, f"expected 58 avatars, got {len(avatars)}"
    for a in avatars:
        assert set(a["levels"]) == {"1", "2", "3", "4", "5", "6"}, \
            f"avatar {a['id']} levels incomplete"
    print("  [OK] 58 avatars x 6 levels complete")

    # 2. M3/M5 mechanically-verified skill bumps
    bad = [a["id"] for a in avatars
           for lvl in ("3", "5")
           if a["levels"][lvl]["kind"] != "skill_bump"
           or not a["levels"][lvl]["mechanically_verified"]]
    passed = not bad
    print(f"  [{'OK' if passed else 'FAIL'}] M3/M5 skill_bump "
          f"mechanically verified (PPAGKJLLCIM==2 + Common_Talent_Desc)")
    ok &= passed

    # 3. anti-fabrication: every value appears in its own level text
    bad = 0
    for a in avatars:
        for lvl, entry in a["levels"].items():
            if entry.get("kind") != "effects":
                continue
            toks = [parse_num(t) for t in num_tokens_c(entry["text"])]
            for e in _effects(entry):
                for v in _values(e):
                    if not any(t == v for t in toks):
                        bad += 1
                        print(f"  FABRICATED VALUE: avatar {a['id']} M{lvl} "
                              f"effect {e['key']} value {v} not in text")
    passed = bad == 0
    print(f"  [{'OK' if passed else 'FAIL'}] all effect values verified "
          f"present in their own level text")
    ok &= passed

    # 4. ground truth from mindscape_props.json (manual curation)
    def has_stat(aid, lvl, stat, value):
        return any(e["effect_type"] == "stat" and e.get("stat") == stat
                   and e.get("value") == value
                   for e in _effects(_find(doc, aid)["levels"][str(lvl)]))

    def has_type(aid, lvl, etype, value=None, **kw):
        for e in _effects(_find(doc, aid)["levels"][str(lvl)]):
            if e["effect_type"] != etype:
                continue
            if value is not None and e.get("value") != value:
                continue
            if all(e.get(k) == v for k, v in kw.items()):
                return True
        return False

    checks = [
        ("1091 M2 CRIT Rate +15% (toggle)", lambda: (
            has_stat(1091, 2, "CRIT Rate", 15.0)
            and not next(
                e for e in _effects(_find(doc, 1091)["levels"]["2"])
                if e["effect_type"] == "stat"
                and e.get("stat") == "CRIT Rate")["unconditional"])),
        ("1371 M2 ignores 15% Ether RES", lambda: has_type(
            1371, 2, "res_ignore", 15.0, elements=["Ether"])),
        ("1371 M4 EX Special DMG +30%", lambda: has_type(
            1371, 4, "damage_bonus", 30.0)),
        ("1421 M1 team DMG +10%", lambda: has_type(
            1421, 1, "damage_bonus", 10.0, target="team")),
        ("1421 M4 healing +25%", lambda: has_type(
            1421, 4, "healing_bonus", 25.0)),
        ("1011 M1 Energy Gen Rate +12%", lambda: has_stat(
            1011, 1, "Energy Generation Rate", 12.0)),
        ("1261 M2 15% of enemy DEF ignored", lambda: has_type(
            1261, 2, "def_ignore", 15.0)),
        ("1311 M1 All-RES shred 6%", lambda: has_type(
            1311, 1, "res_shred", 6.0)),
    ]
    for label, fn in checks:
        try:
            passed = fn()
        except (KeyError, StopIteration):
            passed = False
        print(f"  [{'OK' if passed else 'FAIL'}] {label}")
        ok &= passed

    print("AUDIT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    main()
    sys.exit(audit())

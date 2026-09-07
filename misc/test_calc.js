const fs = require("fs");
const path = require("path");
const base = __dirname;

// minimal DOM stubs so app.js parses without a browser
global.document = {
  querySelector: () => null,
  createElement: () => ({ style: {}, appendChild: () => {}, addEventListener: () => {}, classList: { add: () => {}, remove: () => {}, toggle: () => {} } }),
  addEventListener: () => {},
  body: { style: {} },
};
global.fetch = () => Promise.reject(new Error("no network in test"));

let code = fs.readFileSync(path.join(base, "site/static/app.js"), "utf-8");
code = code.replace("boot();", ""); // don't auto-run

// expose internals for the test
code += "\nmodule.exports = { G, computeStats, fmtStat, PCT_STATS };\n";
const modPath = path.join(base, "site/static/_app_test.js");
fs.writeFileSync(modPath, code);
const { G, computeStats, fmtStat } = require(modPath);
fs.unlinkSync(modPath);

const j = (p) => JSON.parse(fs.readFileSync(path.join(base, p), "utf-8"));
G.avatars = j("avatars.json");
G.weapons = j("weapons.json");
G.equipments = j("equipments.json");
G.locale = j("locale_en.json");
G.mindscapes = j("mindscapes.json");
G.mindscapeProps = j("mindscape_props.json");

const tb = (p, m) => {
  const raw = j(p);
  const rows = raw.MLOEFHJHCID || raw;
  return rows.map((r) => {
    const o = {};
    for (const [k, n] of Object.entries(m)) if (k in r) o[n] = r[k];
    return o;
  });
};
G.weaponLevels = tb("WeaponLevelTemplateTb.json", { APDCBEGPHJO: "Rarity", GJGMIBEOBHP: "Level", EOMOGNMMOEJ: "EnhanceRate" });
G.weaponStars = tb("WeaponStarTemplateTb.json", { APDCBEGPHJO: "Rarity", LMBCLMNIJNA: "BreakLevel", EENDAEFLEJO: "StarRate", IIPAHNFIJOH: "RandRate" });
G.equipmentLevels = tb("EquipmentLevelTemplateTb.json", { APDCBEGPHJO: "Rarity", GJGMIBEOBHP: "Level", EOMOGNMMOEJ: "EnhanceRate" });

const api = j("1303558818.json");
const list = api.PlayerInfo.ShowcaseDetail.AvatarList;

// expected values from the python calculator (zzz_enka_stat_calc_multichar.py)
const expected = {
  0: { name: "Miyabi", HP: 10906, ATK: 2715, DEF: 864, "CRIT Rate": "51.4%", "CRIT DMG": "142.8%" },
};

let fail = 0;
for (let i = 0; i < list.length; i++) {
  const av = list[i];
  const s = computeStats(av);
  if (!s) { console.log(`#${i} id=${av.Id}: no excel data`); continue; }
  const excel = G.avatars[String(av.Id)];
  const name = G.locale[excel.Name] || excel.Name;
  const line = ["HP", "ATK", "DEF", "Impact", "CRIT Rate", "CRIT DMG", "PEN Ratio", "PEN", "Anomaly Proficiency", "Anomaly Mastery", "Energy Regen", "Sheer Force", "Ice DMG", "Ether DMG"]
    .map((k) => `${k}=${fmtStat(k, s[k])}`)
    .join("  ");
  console.log(`${name}: ${line}`);
  const exp = expected[i];
  if (exp) {
    for (const [k, v] of Object.entries(exp)) {
      if (k === "name") continue;
      const got = fmtStat(k, s[k]);
      if (got !== String(v)) { console.log(`  MISMATCH ${k}: js=${got} py=${v}`); fail++; }
    }
  }
}
console.log(fail ? `FAIL: ${fail} mismatches` : "PASS: JS matches Python reference for Miyabi");
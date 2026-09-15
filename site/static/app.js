"use strict";

/* ===================== property metadata ===================== */

const PROP_ID_TO_NAME = {
  11101: "HpMax_Base", 11102: "HpMax_Ratio", 11103: "HpMax_Delta",
  12101: "Atk_Base", 12102: "Atk_Ratio", 12103: "Atk_Delta",
  12201: "BreakStun_Base", 12202: "BreakStun_Ratio",
  12301: "SkipDefAtk_Base", 12303: "SkipDefAtk_Delta",
  13101: "Def_Base", 13102: "Def_Ratio", 13103: "Def_Delta",
  20101: "Crit_Base", 20103: "Crit_Delta",
  21101: "CritDmg_Base", 21103: "CritDmg_Delta",
  23101: "PenRatio_Base", 23103: "PenRatio_Delta",
  23201: "PenDelta_Base", 23203: "PenDelta_Delta",
  30501: "SpRecover_Base", 30502: "SpRecover_Ratio", 30503: "SpRecover_Delta",
  31201: "ElementMystery_Base", 31203: "ElementMystery_Delta",
  31401: "ElementAbnormalPower_Base", 31402: "ElementAbnormalPower_Ratio", 31403: "ElementAbnormalPower_Delta",
  31501: "AddedDamageRatio_Physics_Base", 31503: "AddedDamageRatio_Physics_Delta",
  31601: "AddedDamageRatio_Fire_Base", 31603: "AddedDamageRatio_Fire_Delta",
  31701: "AddedDamageRatio_Ice_Base", 31703: "AddedDamageRatio_Ice_Delta",
  31801: "AddedDamageRatio_Elec_Base", 31803: "AddedDamageRatio_Elec_Delta",
  31901: "AddedDamageRatio_Ether_Base", 31903: "AddedDamageRatio_Ether_Delta",
  32001: "RpRecover_Base", 32002: "RpRecover_Ratio", 32003: "RpRecover_Delta",
  32201: "SkipDefDamageRatio_Base", 32203: "SkipDefDamageRatio_Delta",
  32301: "AddedDamageRatio_Wind_Base", 32303: "AddedDamageRatio_Wind_Delta",
};

const PROP_DISPLAY = {
  11101: ["HP", false], 11102: ["HP", true], 11103: ["HP", false],
  12101: ["ATK", false], 12102: ["ATK", true], 12103: ["ATK", false],
  12201: ["Impact", false], 12202: ["Impact", true],
  12301: ["Sheer Force", false], 12303: ["Sheer Force", false],
  13101: ["DEF", false], 13102: ["DEF", true], 13103: ["DEF", false],
  20101: ["CRIT Rate", true], 20103: ["CRIT Rate", true],
  21101: ["CRIT DMG", true], 21103: ["CRIT DMG", true],
  23101: ["PEN Ratio", true], 23103: ["PEN Ratio", true],
  23201: ["PEN", false], 23203: ["PEN", false],
  30501: ["Energy Regen", false], 30502: ["Energy Regen", true], 30503: ["Energy Regen", false],
  31201: ["Anomaly Proficiency", false], 31203: ["Anomaly Proficiency", false],
  31401: ["Anomaly Mastery", false], 31402: ["Anomaly Mastery", true], 31403: ["Anomaly Mastery", false],
  31501: ["Physical DMG", true], 31503: ["Physical DMG", true],
  31601: ["Fire DMG", true], 31603: ["Fire DMG", true],
  31701: ["Ice DMG", true], 31703: ["Ice DMG", true],
  31801: ["Electric DMG", true], 31803: ["Electric DMG", true],
  31901: ["Ether DMG", true], 31903: ["Ether DMG", true],
  32001: ["Decibel Regen", false], 32002: ["Decibel Regen", true], 32003: ["Decibel Regen", false],
  32201: ["Sheer DMG", true], 32203: ["Sheer DMG", true],
  32301: ["Wind DMG", true], 32303: ["Wind DMG", true],
};

const SKILL_INDEX_TO_NAME = {
  0: "Basic Attack", 2: "Dodge", 6: "Assist",
  1: "Special Attack", 3: "Chain Attack", 5: "Core Skill",
};
const CORE_LETTERS = ["-", "A", "B", "C", "D", "E", "F"];
const RANKS = { 2: "B", 3: "A", 4: "S" };

const ELEMENTS = {
  Fire: { name: "Fire", color: "#ff5449" },
  Ice: { name: "Ice", color: "#48c8ff" },
  Elec: { name: "Electric", color: "#b458ff" },
  Ether: { name: "Ether", color: "#d9e55c" },
  Physics: { name: "Physical", color: "#cdd3de" },
  Wind: { name: "Wind", color: "#41f2a6" },
  FireFrost: { name: "Frostburn", color: "#8fd8ff" },
  AuricEther: { name: "Auric Ink", color: "#ffd24d" },
  Lumen: { name: "Lumen", color: "#fff0a8" },
  ZhenZhenAssault: { name: "Assault", color: "#ff9e64" },
};

const PROFESSIONS = {
  Attack: { name: "Attack", color: "#ff5449" },
  Stun: { name: "Stun", color: "#ffd24d" },
  Anomaly: { name: "Anomaly", color: "#b458ff" },
  Support: { name: "Support", color: "#41f2a6" },
  Defense: { name: "Defense", color: "#48c8ff" },
  Rupture: { name: "Rupture", color: "#ff9e64" },
};

/* ===================== state ===================== */

const G = {
  avatars: null, weapons: null, equipments: null, locale: null,
  mindscapes: null, mindscapeProps: null,
  weaponLevels: null, weaponStars: null, equipmentLevels: null,
  driveDiscSets: null,
};
let showcase = null; // current player showcase data
let SHOWCASE_LIST = []; // current showcase avatar list
let currentAgent = null; // selected apiAvatar

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};
const ESC_CODES = { "&": 38, "<": 60, ">": 62, '"': 34, "'": 39 };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => "&#" + ESC_CODES[c] + ";");

const fmtNum = (n) => Math.round(n).toLocaleString("en-US");

/* ===================== damage calculation section ===================== */

const CALC = {
  monsters: [],            // cached /api/monsters
  current: null,           // {avatarId, name}
  enemy: { name: "Tyrfing", level: 60, stunned: false },
};

function monsterIconUrl(mon) {
  if (!mon.icon_url) return null;
  const slug = mon.icon_url.split("/").pop();
  return `/img/monster/${encodeURIComponent(slug)}`;
}

async function loadMonsterList() {
  if (CALC.monsters.length) return CALC.monsters;
  const res = await fetch("/api/monsters");
  if (!res.ok) throw new Error("Failed to load monster list");
  const data = await res.json();
  CALC.monsters = data.monsters || [];
  return CALC.monsters;
}

function renderCalcTarget() {
  const box = $("#calc-target");
  box.innerHTML = "";

  // enemy picker
  const wrap = el("div", "enemy-picker");
  wrap.appendChild(el("span", "enemy-label", "Enemy"));

  const searchWrap = el("div", "enemy-search-wrap");
  const search = el("input", "enemy-search");
  search.type = "search";
  search.placeholder = "Search monster…";
  search.value = CALC.enemy.name;
  searchWrap.appendChild(search);
  wrap.appendChild(searchWrap);

  const lvl = el("input", "enemy-level");
  lvl.type = "number";
  lvl.min = 1; lvl.max = 80;
  lvl.value = CALC.enemy.level;
  wrap.appendChild(el("span", "enemy-label", "Lv."));
  wrap.appendChild(lvl);

  const stunBtn = el("button", "btn" + (CALC.enemy.stunned ? " btn--primary" : " btn--hollow"));
  stunBtn.textContent = CALC.enemy.stunned ? "Stunned ✓" : "Stunned";
  stunBtn.title = "Stun Modifier: damage × (1 + StunDamageTakenRatio)";
  wrap.appendChild(stunBtn);

  box.appendChild(wrap);

  // dropdown results container (anchored to the search field)
  const drop = el("div", "enemy-drop hidden");
  searchWrap.appendChild(drop);

  function showDrop(filter) {
    const f = (filter || "").toLowerCase();
    const hits = CALC.monsters.filter((m) => m.name.toLowerCase().includes(f)).slice(0, 60);
    drop.innerHTML = "";
    for (const m of hits) {
      const row = el("div", "enemy-row");
      const ic = monsterIconUrl(m);
      if (ic) {
        const im = el("img", "enemy-icon");
        im.src = ic; im.alt = ""; im.loading = "lazy";
        im.onerror = () => { im.style.visibility = "hidden"; };
        row.appendChild(im);
      } else {
        row.appendChild(el("span", "enemy-icon enemy-icon-ph", "◈"));
      }
      const nm = el("div", "enemy-row-name");
      nm.appendChild(el("div", "nm", esc(m.name)));
      const meta = [m.rank, m.size, m.faction].filter(Boolean).join(" · ");
      nm.appendChild(el("div", "meta", esc(meta)));
      row.appendChild(nm);
      if (m.rarity) row.appendChild(el("span", "enemy-rarity", "★".repeat(Math.min(4, m.rarity))));
      row.addEventListener("click", () => {
        CALC.enemy.name = m.name;
        search.value = m.name;
        drop.classList.add("hidden");
        runCalc();
      });
      drop.appendChild(row);
    }
    drop.classList.toggle("hidden", !hits.length);
  }

  search.addEventListener("input", () => showDrop(search.value));
  search.addEventListener("focus", () => showDrop(search.value));
  search.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const exact = CALC.monsters.find((m) => m.name.toLowerCase() === search.value.trim().toLowerCase());
      if (exact) { CALC.enemy.name = exact.name; drop.classList.add("hidden"); runCalc(); }
      else showDrop(search.value);
    }
  });
  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) drop.classList.add("hidden");
  });

  lvl.addEventListener("change", () => {
    CALC.enemy.level = Math.max(1, Math.min(80, parseInt(lvl.value, 10) || 60));
    lvl.value = CALC.enemy.level;
    runCalc();
  });
  stunBtn.addEventListener("click", () => {
    CALC.enemy.stunned = !CALC.enemy.stunned;
    stunBtn.textContent = CALC.enemy.stunned ? "Stunned ✓" : "Stunned";
    stunBtn.className = "btn" + (CALC.enemy.stunned ? " btn--primary" : " btn--hollow");
    runCalc();
  });
}

async function openCalc(apiAvatar) {
  CALC.current = { avatarId: apiAvatar.Id };
  const excel = G.avatars[String(apiAvatar.Id)];
  const name = excel ? localize(excel.Name, String(apiAvatar.Id)) : `#${apiAvatar.Id}`;
  $("#calc-title").textContent = `Damage — ${name} Lv.${apiAvatar.Level}`;
  $("#calc-section").classList.remove("hidden");
  renderCalcTarget();
  $("#calc-body").innerHTML = `<div class="calc-loading">Calculating…</div>`;
  $("#calc-section").scrollIntoView({ behavior: "smooth", block: "start" });
  await runCalc();
}

async function runCalc() {
  if (!CALC.current || !showcase) return;
  const body = $("#calc-body");
  body.innerHTML = `<div class="calc-loading">Calculating…</div>`;
  try {
    const res = await fetch("/api/calc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        showcase,
        avatar_id: CALC.current.avatarId,
        enemy: CALC.enemy.name,
        enemy_level: CALC.enemy.level,
        stunned: CALC.enemy.stunned,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    renderCalcResult(data);
  } catch (e) {
    body.innerHTML = `<div class="status error">${esc(e.message || "Calculation failed")}</div>`;
  }
}

function renderCalcResult(r) {
  const body = $("#calc-body");
  body.innerHTML = "";

  // enemy summary strip
  const e = r.enemy;
  const strip = el("div", "calc-enemy-strip");
  const ic = e.icon_url ? `/img/monster/${encodeURIComponent(e.icon_url.split("/").pop())}` : null;
  if (ic) {
    const im = el("img", "enemy-portrait");
    im.src = ic; im.alt = e.name;
    im.onerror = () => { im.style.visibility = "hidden"; };
    strip.appendChild(im);
  }
  const info = el("div", "enemy-info");
  info.appendChild(el("div", "nm", `${esc(e.name)} <span class="lvl">Lv.${e.level}</span>`));
  const resParts = Object.entries(e.res_pct || {}).filter(([, v]) => v)
    .map(([k, v]) => `${k} ${v > 0 ? "+" : ""}${Math.round(v * 100)}%`);
  const meta = [
    `DEF ${fmtNum(e.def_val)}`, `HP ${fmtNum(e.hp_val)}`,
    `Stun DMG taken +${Math.round(e.stun_taken_pct * 100)}%`,
    resParts.length ? `RES ${resParts.join(", ")}` : null,
    e.rank, e.faction,
  ].filter(Boolean);
  info.appendChild(el("div", "meta", esc(meta.join(" · "))));
  strip.appendChild(info);
  body.appendChild(strip);

  // active buffs (toggles)
  const active = (r.toggles || []).filter((t) => t.enabled);
  if (active.length) {
    const buffs = el("div", "calc-buffs");
    buffs.appendChild(el("span", "buff-label", "Active buffs:"));
    for (const t of active) {
      buffs.appendChild(el("span", "buff-chip",
        `${esc(t.source_name)} <b>+${t.value}${t.unit === "percent" ? "%" : ""} ${esc(t.stat)}</b>`));
    }
    body.appendChild(buffs);
  }

  // damage table
  if (!r.rows.length) {
    body.appendChild(el("div", "calc-empty",
      "No skill data to calculate (agent without gear?)."));
    return;
  }
  const wrap = el("div", "calc-table-wrap");
  const table = el("table", "calc-table");
  table.innerHTML = `
    <thead><tr>
      <th>Skill</th><th>Hit</th><th class="num">Mult</th>
      <th class="num">Daze</th><th class="num">Buildup</th>
      <th class="num">Non-Crit</th><th class="num">Crit</th>
      <th class="num">Expected</th>
      <th class="num">${r.stunned ? "Non-Crit (stunned)" : "If Stunned"}</th>
    </tr></thead>`;
  const tbody = el("tbody");
  let lastSkill = null;
  const skillCell = (row) => {
    if (row.skill === lastSkill) return "";
    const cat = row.skill_category
    // empty cat tag string below
      ? ` <span class="cat-tag">${esc("")}</span>` : "";
    return `<b>${esc(row.skill)}</b>${cat}`;
  };
  for (const row of r.rows) {
    const tr = el("tr");
    if (row.damage_pct <= 0 && row.daze_pct > 0) {
      // daze-only hit (Defensive Assist parry dsb.)
      tr.className = "daze-row";
      tr.innerHTML = `
        <td>${skillCell(row)}</td>
        <td>${esc(row.hit)}</td>
        <td class="num muted">—</td>
        <td class="num">${fmtNum(row.daze)}</td>
        <td class="num" colspan="5">(daze-only)</td>`;
      lastSkill = row.skill;
      tbody.appendChild(tr);
      continue;
    }
    if (row.anomaly_tick) {
      // Anomaly per-tick: nilai di bawah = per tick (AP-scaled);
      // tick count tergantung rotasi.
      tr.className = "anomaly-row";
      tr.innerHTML = `
        <td>${skillCell(row)}</td>
        <td>${esc(row.hit)}</td>
        <td class="num">${row.damage_pct.toFixed(1)}%<span class="per-tick">/tick</span></td>
        <td class="num muted">—</td>
        <td class="num muted">—</td>
        <td class="num">${fmtNum(row.non_crit)}</td>
        <td class="num">${fmtNum(row.crit)}</td>
        <td class="num">${fmtNum(row.expected ?? row.non_crit)}</td>
        <td class="num">${fmtNum(row.stun_non_crit)}</td>`;
      lastSkill = row.skill;
      tbody.appendChild(tr);
      continue;
    }
    tr.innerHTML = `
      <td>${skillCell(row)}</td>
      <td>${esc(row.hit)}</td>
      <td class="num">${row.damage_pct.toFixed(1)}%</td>
      <td class="num">${row.daze_pct > 0 ? fmtNum(row.daze) : "—"}</td>
      <td class="num">${row.buildup_pct > 0 ? fmtNum(row.buildup) : "—"}</td>
      <td class="num">${fmtNum(row.non_crit)}</td>
      <td class="num crit">${fmtNum(row.crit)}</td>
      <td class="num">${fmtNum(row.expected ?? row.non_crit)}</td>
      <td class="num">${fmtNum(row.stun_non_crit)}</td>`;
    lastSkill = row.skill;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  body.appendChild(wrap);
}

/* ===================== helpers ===================== */

function localize(key, fallback) {
  if (!key) return fallback;
  return G.locale[key] || key;
}

function findRow(rows, match) {
  return rows.find((r) => Object.entries(match).every(([k, v]) => r[k] === v));
}

function propName(id) {
  return PROP_ID_TO_NAME[id] || String(id);
}

function formatProp(id, value) {
  const [label, isPct] = PROP_DISPLAY[id] || [propName(id), false];
  if (isPct) return `${label} ${(value / 100).toFixed(1)}%`;
  return `${label} ${Math.floor(value)}`;
}

function effectiveSkillLevel(base, mindscape) {
  let bump = 0;
  if (mindscape >= 3) bump += 2;
  if (mindscape >= 5) bump += 2;
  return base + bump;
}

/* ===================== stat engine (port of the python calculator) ===================== */

function newLayer() {
  const l = {};
  for (const name of new Set(Object.values(PROP_ID_TO_NAME))) l[name] = 0;
  return l;
}

function addProp(l, id, value) {
  const n = propName(id);
  l[n] = (l[n] || 0) + value;
}

function computeStats(apiAvatar) {
  const excel = G.avatars[String(apiAvatar.Id)];
  if (!excel) return null;

  const level = apiAvatar.Level;
  const promotion = apiAvatar.PromotionLevel;
  const core = apiAvatar.CoreSkillEnhancement;
  const mindscape = apiAvatar.TalentLevel || 0;

  const L = newLayer();

  // --- character: base + growth + promotion ---
  const base = excel.BaseProps || {};
  const growth = excel.GrowthProps || {};
  const promoRow = (excel.PromotionProps || [])[promotion - 1] || {};
  for (const [pid, baseVal] of Object.entries(base)) {
    const id = Number(pid);
    const v = baseVal + ((growth[pid] || 0) / 10000) * (level - 1) + (promoRow[pid] || 0);
    addProp(L, id, v);
  }

  // --- core skill enhancement ---
  const coreRow = (excel.CoreEnhancementProps || [])[core] || {};
  for (const [pid, v] of Object.entries(coreRow)) addProp(L, Number(pid), v);

  // --- weapon ---
  const w = apiAvatar.Weapon;
  if (w) {
    const wmeta = G.weapons[String(w.Id)];
    if (wmeta) {
      const rarity = wmeta.Rarity;
      const lvlRow = findRow(G.weaponLevels, { Rarity: rarity, Level: w.Level });
      const starRow = findRow(G.weaponStars, { Rarity: rarity, BreakLevel: w.BreakLevel });
      if (lvlRow && starRow) {
        const main = wmeta.MainStat;
        const sub = wmeta.SecondaryStat;
        const mainVal = Math.floor(main.PropertyValue * (1 + lvlRow.EnhanceRate / 10000 + starRow.StarRate / 10000));
        const subVal = Math.floor(sub.PropertyValue * (1 + starRow.RandRate / 10000));
        addProp(L, main.PropertyId, mainVal);
        addProp(L, sub.PropertyId, subVal);
      }
    }
  }

  // --- drive discs ---
  const suitCounts = {};
  for (const equip of apiAvatar.EquippedList || []) {
    const disc = equip.Equipment;
    const meta = G.equipments.Items[String(disc.Id)];
    if (!meta) continue;
    const lvlRow = findRow(G.equipmentLevels, { Rarity: meta.Rarity, Level: disc.Level });
    if (lvlRow) {
      const main = disc.MainPropertyList[0];
      const mainVal = Math.floor(main.PropertyValue * (1 + lvlRow.EnhanceRate / 10000));
      addProp(L, main.PropertyId, mainVal);
    }
    for (const sub of disc.RandomPropertyList || []) {
      addProp(L, sub.PropertyId, sub.PropertyValue * sub.PropertyLevel);
    }
    const sid = String(meta.SuitId);
    suitCounts[sid] = (suitCounts[sid] || 0) + 1;
  }

  // --- set bonuses (2pc) ---
  for (const [sid, count] of Object.entries(suitCounts)) {
    if (count < 2) continue;
    const suit = G.equipments.Suits[sid];
    if (!suit || !suit.SetBonusProps) continue;
    for (const [pid, v] of Object.entries(suit.SetBonusProps)) addProp(L, Number(pid), v);
  }

  // --- mindscape stat props (unconditional only) ---
  const msProps = (G.mindscapeProps && G.mindscapeProps[String(apiAvatar.Id)]) || {};
  for (let m = 1; m <= mindscape; m++) {
    const entry = msProps[String(m)];
    if (entry && entry.unconditional) {
      for (const [pid, v] of Object.entries(entry.props || {})) addProp(L, Number(pid), v);
    }
  }

  // --- floor everything except SpRecover ---
  for (const k of Object.keys(L)) {
    if (k.startsWith("SpRecover_")) L[k] = L[k];
    else L[k] = Math.floor(L[k]);
  }

  // --- rupture correction (Sheer Force) ---
  if ((excel.ProfessionType || "").toLowerCase() === "rupture") {
    const atk = Math.floor(L.Atk_Base * (1 + L.Atk_Ratio / 10000) + L.Atk_Delta);
    const hp = Math.floor(L.HpMax_Base + Math.ceil(L.HpMax_Base * L.HpMax_Ratio / 10000) + L.HpMax_Delta);
    L.SkipDefAtk_Delta += Math.floor(atk * 0.3) + Math.floor(hp * 0.1);
  }

  // --- final stats ---
  const p = (n) => L[n] || 0;
  return {
    "HP": p("HpMax_Base") + Math.ceil(p("HpMax_Base") * p("HpMax_Ratio") / 10000) + p("HpMax_Delta"),
    "ATK": p("Atk_Base") * (1 + p("Atk_Ratio") / 10000) + p("Atk_Delta"),
    "DEF": p("Def_Base") * (1 + p("Def_Ratio") / 10000) + p("Def_Delta"),
    "Impact": p("BreakStun_Base") * (1 + p("BreakStun_Ratio") / 10000),
    "CRIT Rate": p("Crit_Base") + p("Crit_Delta"),
    "CRIT DMG": p("CritDmg_Base") + p("CritDmg_Delta"),
    "PEN Ratio": p("PenRatio_Base") + p("PenRatio_Delta"),
    "PEN": p("PenDelta_Base") + p("PenDelta_Delta"),
    "Anomaly Proficiency": p("ElementMystery_Base") + p("ElementMystery_Delta"),
    "Anomaly Mastery": p("ElementAbnormalPower_Base") * (1 + p("ElementAbnormalPower_Ratio") / 10000) + p("ElementAbnormalPower_Delta"),
    "Energy Regen": (p("SpRecover_Base") * (1 + p("SpRecover_Ratio") / 10000) + p("SpRecover_Delta")) / 100,
    "Sheer Force": p("SkipDefAtk_Base") + p("SkipDefAtk_Delta"),
    "Physical DMG": p("AddedDamageRatio_Physics_Base") + p("AddedDamageRatio_Physics_Delta"),
    "Fire DMG": p("AddedDamageRatio_Fire_Base") + p("AddedDamageRatio_Fire_Delta"),
    "Ice DMG": p("AddedDamageRatio_Ice_Base") + p("AddedDamageRatio_Ice_Delta"),
    "Electric DMG": p("AddedDamageRatio_Elec_Base") + p("AddedDamageRatio_Elec_Delta"),
    "Ether DMG": p("AddedDamageRatio_Ether_Base") + p("AddedDamageRatio_Ether_Delta"),
    "Wind DMG": p("AddedDamageRatio_Wind_Base") + p("AddedDamageRatio_Wind_Delta"),
    "Sheer DMG": p("SkipDefDamageRatio_Base") + p("SkipDefDamageRatio_Delta"),
  };
}

const PCT_STATS = new Set([
  "CRIT Rate", "CRIT DMG", "PEN Ratio", "Physical DMG", "Fire DMG",
  "Ice DMG", "Electric DMG", "Ether DMG", "Wind DMG", "Sheer DMG",
]);

function fmtStat(name, value) {
  if (PCT_STATS.has(name)) return (Math.floor(value) / 100).toFixed(1) + "%";
  if (name === "Energy Regen") return String(Math.round(value * 100) / 100);
  return String(Math.floor(value));
}

/* ===================== rendering ===================== */

function setStatus(msg, isError) {
  const s = $("#status");
  if (!msg) { s.classList.add("hidden"); return; }
  s.textContent = msg;
  s.classList.toggle("error", !!isError);
  s.classList.remove("hidden");
}

/* ---- battle-records icon maps (bundled from act.hoyolab.com) ---- */

const HL_ICON = {
  "HP": "prop-hp-icon.59cb16ef.png",
  "ATK": "prop-atk-icon.7e5f0cb6.png",
  "DEF": "prop-def-icon.a927965c.png",
  "Impact": "prop-impact-icon.6d9c9282.png",
  "CRIT Rate": "prop-crit-rate-icon.810d1d8e.png",
  "CRIT DMG": "prop-crit-dmg-icon.b896fc9e.png",
  "Anomaly Proficiency": "prop-anomaly-proficiency-icon.38adc36b.png",
  "Anomaly Mastery": "prop-anomaly-mastery-icon.f4fc5970.png",
  "PEN Ratio": "prop-pen-ratio-icon.90bc6385.png",
  "PEN": "prop-pen-value-icon.7646b67f.png",
  "Energy Regen": "prop-energy-regen-icon.2ec55369.png",
};
const hlIcon = (stat) => HL_ICON[stat] ? `/static/hoyolab/${HL_ICON[stat]}` : null;

// skill index -> hoyolab skill icon + display label (battle records order)
const BR_SKILLS = [
  { index: 0, icon: "skill-icon-0.0d9692b6.png", label: "Basic Attack" },
  { index: 2, icon: "skill-icon-2.d863591b.png", label: "Dodge" },
  { index: 6, icon: "skill-icon-6.3fc55b66.png", label: "Assist" },
  { index: 1, icon: "skill-icon-1.e2f84ffb.png", label: "Special Attack" },
  { index: 3, icon: "skill-icon-3.afdb8abe.png", label: "Chain Attack" },
  { index: 5, icon: "skill-icon-5.3d486da1.png", label: "Core Skill" },
];

const EQUIP_BG = {
  S: { left: "equip-bg-left-S.dbbcb2de.png", right: "equip-bg-right-S.6aad8fa3.png" },
  A: { left: "equip-bg-left-S.dbbcb2de.png", right: "equip-bg-right-S.6aad8fa3.png" },
  B: { left: "equip-bg-left-S.dbbcb2de.png", right: "equip-bg-right-S.6aad8fa3.png" },
};
const WEAPON_BG = { S: "weapon-bg-S.c5c5eac9.png", A: "weapon-bg-S.c5c5eac9.png", B: "weapon-bg-S.c5c5eac9.png" };

// stat rows order (battle records)
const STAT_ROWS = [
  "HP", "ATK", "DEF", "Impact", "CRIT Rate", "CRIT DMG",
  "Anomaly Proficiency", "Anomaly Mastery", "PEN Ratio", "PEN", "Energy Regen",
];

function renderPlayer(api) {
  const box = $("#player");
  const soc = api.PlayerInfo && api.PlayerInfo.SocialDetail;
  if (!soc) { box.classList.add("hidden"); return; }
  const pd = soc.ProfileDetail || {};
  const profAvatar = G.avatars[String(pd.AvatarId)];
  const img = profAvatar ? profAvatar.CircleIcon : null;
  const platform = { 1: "iOS", 2: "Android", 3: "PC", 4: "PS5" }[pd.PlatformType] || "?";
  box.innerHTML = "";
  if (img) {
    const av = el("img", "player-avatar");
    av.src = img;
    av.alt = "";
    box.appendChild(av);
  }
  const info = el("div", "player-info");
  info.appendChild(el("div", "player-name", esc(pd.Nickname || "Agent")));
  info.appendChild(el("div", "player-meta", `Lv.${pd.Level || "?"} · UID ${pd.Uid || "?"} · ${platform}`));
  if (soc.Comment) info.appendChild(el("div", "player-desc", esc(soc.Comment)));
  box.appendChild(info);
  box.classList.remove("hidden");
}

/* ---- battle-records agent showcase ---- */

function renderRoleSwiper(list) {
  const strip = $("#role-swiper");
  strip.innerHTML = "";
  for (const av of list) {
    const excel = G.avatars[String(av.Id)];
    const item = el("div", "role-swiper-item");
    if (excel) {
      const im = el("img");
      // CircleIcon is the consistent square head-shot avatar; fall back to the
      // full-body painting if it is missing (keeps the card from going blank).
      im.src = excel.CircleIcon || excel.Image;
      im.alt = localize(excel.Name, String(av.Id));
      im.loading = "lazy";
      item.appendChild(im);
    }
    item.addEventListener("click", () => selectAgent(av));
    strip.appendChild(item);
  }
}

function selectAgent(av) {
  currentAgent = av;
  document.querySelectorAll(".role-swiper-item").forEach((it, i) => {
    it.classList.toggle("selected", SHOWCASE_LIST[i] === av);
  });
  renderAgentDetail(av);
}

function renderAgentDetail(apiAvatar) {
  const excel = G.avatars[String(apiAvatar.Id)];
  const sc = $("#showcase");
  if (!excel) {
    sc.classList.remove("hidden");
    $("#role-name").textContent = `Unknown #${apiAvatar.Id}`;
    return;
  }

  const stats = computeStats(apiAvatar) || {};
  const rank = RANKS[excel.Rarity] || "?";
  const elems = excel.ElementTypes || [];
  const mainElem = elems[elems.length - 1] || "Physics";
  const elemMeta = ELEMENTS[mainElem] || { name: mainElem, color: "#999" };
  const profMeta = PROFESSIONS[excel.ProfessionType] || { name: excel.ProfessionType, color: "#999" };
  const name = localize(excel.Name, String(apiAvatar.Id));
  const mindscape = apiAvatar.TalentLevel || 0;
  const core = apiAvatar.CoreSkillEnhancement;
  const coreLetter = CORE_LETTERS[core] || String(core);

  // tint the detail bg by element color
  $("#role-detail-bg").style.background =
    `linear-gradient(180deg, ${elemMeta.color}2E 0%, transparent 42%), #101010`;

  // portrait + giant marquee name
  const img = $("#role-portrait-img");
  img.src = excel.Image;
  img.alt = name;
  const marquee = $("#marquee-name");
  marquee.textContent = name;

  // name + meta
  $("#role-name").textContent = name;
  const meta = $("#role-meta");
  meta.innerHTML = "";
  meta.appendChild(el("span", "rank-tag", `${rank}-Rank`));
  meta.appendChild(el("span", "", `<span style="color:${elemMeta.color}">${esc(elemMeta.name)}</span>`));
  meta.appendChild(el("span", "", `<span style="color:${profMeta.color}">${esc(profMeta.name)}</span>`));
  meta.appendChild(el("span", "", `Lv.${apiAvatar.Level}`));
  meta.appendChild(el("span", "", `M${mindscape}`));
  meta.appendChild(el("span", "", `Core ${coreLetter}`));

  // property panel
  const props = $("#property-info");
  props.innerHTML = "";
  for (const key of STAT_ROWS) {
    const v = stats[key];
    if (v === undefined) continue;
    const li = el("li");
    const label = el("div", "prop-label");
    const icon = hlIcon(key);
    if (icon) {
      const im = el("img");
      im.src = icon;
      im.alt = "";
      label.appendChild(im);
    }
    label.appendChild(el("span", "", esc(key)));
    const value = el("div", "prop-value");
    value.appendChild(el("span", "final-prop", esc(fmtStat(key, v))));
    li.appendChild(label);
    li.appendChild(value);
    props.appendChild(li);
  }

  renderEquipment(apiAvatar);
  renderSkillsBR(apiAvatar);
  sc.classList.remove("hidden");
}

/* the game's tooltip markup uses <color=#RRGGBB>…</color>; render it as styled spans */
function richText(raw) {
  if (!raw) return "";
  const safe = String(raw)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return safe.replace(
    /&lt;color=(#[0-9A-Fa-f]{3,8})&gt;([\s\S]*?)&lt;\/color&gt;/g,
    (_, c, t) => `<span style="color:${c}">${t}</span>`
  );
}

let _discSetByName = null;
function driveDiscSetByName(name) {
  if (!_discSetByName) {
    _discSetByName = {};
    for (const s of G.driveDiscSets || []) _discSetByName[s.name] = s;
  }
  return _discSetByName[name] || null;
}

function renderEquipment(apiAvatar) {
  // ---- w-engine (center) ----
  const wbox = $("#weapon-info");
  wbox.innerHTML = "";
  const w = apiAvatar.Weapon;
  if (w) {
    const wmeta = G.weapons[String(w.Id)];
    if (wmeta) {
      const wname = localize(wmeta.ItemName, String(w.Id));
      const wrank = RANKS[wmeta.Rarity] || "?";
      const bg = el("img", "bg");
      bg.src = `/static/hoyolab/${WEAPON_BG[wrank] || WEAPON_BG.S}`;
      bg.alt = "";
      wbox.appendChild(bg);
      const icon = el("img", "icon");
      icon.src = wmeta.ImagePath;
      icon.alt = wname;
      wbox.appendChild(icon);
      const rankIm = el("img", "rank");
      rankIm.src = "/static/hoyolab/role-star-1.e9cd3b86.png";
      rankIm.alt = "";
      wbox.appendChild(rankIm);
      wbox.appendChild(el("span", "level", `Lv.${w.Level}`));
      wbox.onclick = () => showEquipPop(wbox, {
        name: wname, icon: wmeta.ImagePath,
        meta: `${wrank}-Rank · Lv.${w.Level} · Mod ${w.BreakLevel}`,
        rows: weaponRows(w, wmeta),
      });
    }
  }

  // ---- drive disc slots 1-6 ----
  const equipped = [...(apiAvatar.EquippedList || [])];
  const bySlot = {};
  for (const eq of equipped) bySlot[eq.Slot] = eq;

  const suitCounts = {};
  const suitOfSlot = {};
  for (const eq of equipped) {
    const meta = G.equipments.Items[String(eq.Equipment.Id)];
    if (!meta) continue;
    suitCounts[meta.SuitId] = (suitCounts[meta.SuitId] || 0) + 1;
    suitOfSlot[eq.Slot] = meta.SuitId;
  }

  for (let slot = 1; slot <= 6; slot++) {
    const box = $(`#equip-slot-${slot}`);
    box.innerHTML = "";
    const eq = bySlot[slot];
    if (!eq) continue;
    const disc = eq.Equipment;
    const meta = G.equipments.Items[String(disc.Id)];
    if (!meta) continue;
    const suit = G.equipments.Suits[String(meta.SuitId)];
    const dr = RANKS[meta.Rarity] || "?";

    const inner = el("div");
    const im = el("img", "icon");
    im.src = suit ? suit.Icon : "";
    im.alt = "";
    im.onerror = () => { im.style.visibility = "hidden"; };
    inner.appendChild(im);
    inner.appendChild(el("span", "level", `Lv.${disc.Level}`));
    box.appendChild(inner);
    const bg = el("img", "bg");
    bg.src = `/static/hoyolab/${(slot <= 3 ? EQUIP_BG[dr].left : EQUIP_BG[dr].right)}`;
    bg.alt = "";
    box.appendChild(bg);
    box.onclick = () => showEquipPop(box, {
      name: suit ? localize(suit.Name, String(meta.SuitId)) : `Disc #${disc.Id}`,
      icon: suit ? suit.Icon : "",
      meta: `Slot ${slot} · ${dr}-Rank · +${disc.Level}`,
      rows: discRows(disc, meta),
    });
  }

  // ---- set effects ----
  const effBox = $("#suit-effects");
  effBox.innerHTML = "";
  effBox.appendChild(el("h3", "", "Active Set Effects"));
  const ul = el("ul");
  for (const [sid, count] of Object.entries(suitCounts)) {
    if (count < 2) continue;
    const suit = G.equipments.Suits[sid];
    if (!suit) continue;
    const nm = localize(suit.Name, sid);
    const mapped = driveDiscSetByName(nm);
    const li = el("li");
    const inner = el("div");
    const texts = el("div", "suit-texts");

    const head = el("p", "suit-name");
    head.innerHTML = `${esc(nm)} <span class="suit-count">${count}/4</span>`;
    texts.appendChild(head);

    if (mapped && mapped.bonus_2pc_raw) {
      const p = el("p", "suit-desc");
      p.innerHTML = `<span class="pc-tag">2-Pc</span>${richText(mapped.bonus_2pc_raw)}`;
      texts.appendChild(p);
    }
    if (count >= 4 && mapped && mapped.bonus_4pc_raw) {
      const p = el("p", "suit-desc");
      p.innerHTML = `<span class="pc-tag">4-Pc</span>${richText(mapped.bonus_4pc_raw)}`;
      texts.appendChild(p);
    }
    if (!mapped) texts.appendChild(el("p", "suit-desc", "Set bonus active"));

    const ic = el("img");
    ic.src = "/static/hoyolab/weapon-suit-icon.f75f0d28.png";
    ic.alt = "";
    inner.appendChild(texts);
    inner.appendChild(ic);
    li.appendChild(inner);
    ul.appendChild(li);
  }
  if (!ul.children.length) {
    const li = el("li");
    const inner = el("div");
    inner.appendChild(el("div", "suit-texts", "<p>No set effects</p>"));
    li.appendChild(inner);
    ul.appendChild(li);
  }
  effBox.appendChild(ul);
}

function weaponRows(w, wmeta) {
  const rows = [];
  const lvlRow = findRow(G.weaponLevels, { Rarity: wmeta.Rarity, Level: w.Level });
  const starRow = findRow(G.weaponStars, { Rarity: wmeta.Rarity, BreakLevel: w.BreakLevel });
  if (lvlRow && starRow && wmeta.MainStat) {
    const mv = Math.floor(wmeta.MainStat.PropertyValue * (1 + lvlRow.EnhanceRate / 10000 + starRow.StarRate / 10000));
    const sv = Math.floor(wmeta.SecondaryStat.PropertyValue * (1 + starRow.RandRate / 10000));
    rows.push({ k: formatProp(wmeta.MainStat.PropertyId, mv), main: true });
    rows.push({ k: formatProp(wmeta.SecondaryStat.PropertyId, sv), main: false });
  }
  return rows;
}

function discRows(disc, meta) {
  const rows = [];
  const lvlRow = findRow(G.equipmentLevels, { Rarity: meta.Rarity, Level: disc.Level });
  if (lvlRow && disc.MainPropertyList && disc.MainPropertyList[0]) {
    const main = disc.MainPropertyList[0];
    const mv = Math.floor(main.PropertyValue * (1 + lvlRow.EnhanceRate / 10000));
    rows.push({ k: formatProp(main.PropertyId, mv), main: true });
  }
  for (const sub of disc.RandomPropertyList || []) {
    rows.push({ k: formatProp(sub.PropertyId, sub.PropertyValue * sub.PropertyLevel), main: false });
  }
  return rows;
}

let popEl = null;
function showEquipPop(anchor, data) {
  hideEquipPop();
  popEl = el("div", "equip-pop");
  const head = el("div", "ep-head");
  if (data.icon) {
    const im = el("img");
    im.src = data.icon;
    im.alt = "";
    head.appendChild(im);
  }
  const hd = el("div");
  hd.appendChild(el("div", "nm", esc(data.name)));
  hd.appendChild(el("div", "meta", esc(data.meta)));
  head.appendChild(hd);
  popEl.appendChild(head);
  const body = el("div", "ep-body");
  for (const r of data.rows || []) {
    body.appendChild(el("div", "row" + (r.main ? " main" : ""), `<span class="k">${esc(r.k)}</span>`));
  }
  if (!(data.rows || []).length) body.appendChild(el("div", "row", "<span class='k'>No stats</span>"));
  popEl.appendChild(body);
  document.body.appendChild(popEl);
  const rect = anchor.getBoundingClientRect();
  const pw = 300;
  let left = rect.left + rect.width / 2 - pw / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
  let top = rect.bottom + 8;
  if (top + 220 > window.innerHeight) top = Math.max(8, rect.top - 226);
  popEl.style.left = left + "px";
  popEl.style.top = top + "px";
  setTimeout(() => {
    document.addEventListener("click", hideEquipPopOnOutside, { once: false });
  }, 0);
}
function hideEquipPopOnOutside(e) {
  if (popEl && !popEl.contains(e.target) && !e.target.closest(".equip-info") && !e.target.closest(".weapon-info")) {
    hideEquipPop();
  }
}
function hideEquipPop() {
  if (popEl) { popEl.remove(); popEl = null; }
  document.removeEventListener("click", hideEquipPopOnOutside);
}

function renderSkillsBR(apiAvatar) {
  const ul = $("#skill-list-br");
  ul.innerHTML = "";
  const mindscape = apiAvatar.TalentLevel || 0;
  const levels = {};
  for (const sk of apiAvatar.SkillLevelList || []) levels[sk.Index] = sk.Level;
  for (const s of BR_SKILLS) {
    const base = levels[s.index] ?? 0;
    const eff = effectiveSkillLevel(base, mindscape);
    const li = el("li", "skill-item");
    const outer = el("div");
    const inner = el("div");
    const im = el("img", "skill-icon");
    im.src = `/static/hoyolab/${s.icon}`;
    im.alt = s.label;
    inner.appendChild(im);
    const p = el("p", "", `<span>${String(eff).padStart(2, "0")}</span><span>LEVEL</span>`);
    inner.appendChild(p);
    inner.appendChild(el("h2", "", esc(s.label)));
    inner.appendChild(el("h3", "", base !== eff ? `Base ${base} → ${eff} (M${mindscape})` : " "));
    outer.appendChild(inner);
    li.appendChild(outer);
    ul.appendChild(li);
  }
}

function renderShowcase(api) {
  const list = (api.PlayerInfo && api.PlayerInfo.ShowcaseDetail && api.PlayerInfo.ShowcaseDetail.AvatarList) || [];
  if (!list.length) {
    setStatus("This player's showcase is empty (agents hidden in-game).", true);
    $("#showcase").classList.add("hidden");
    return;
  }
  SHOWCASE_LIST = list;
  renderRoleSwiper(list);
  selectAgent(list[0]);
}

/* ===================== data loading ===================== */

async function loadGameData() {
  const res = await fetch("/api/data");
  if (!res.ok) throw new Error("Failed to load game data");
  const data = await res.json();
  G.avatars = data.avatars;
  G.weapons = data.weapons;
  G.equipments = data.equipments;
  G.locale = data.locale;
  G.mindscapes = data.mindscapes;
  G.mindscapeProps = data.mindscapeProps;
  G.weaponLevels = data.weaponLevels;
  G.weaponStars = data.weaponStars;
  G.equipmentLevels = data.equipmentLevels;
  G.driveDiscSets = (data.driveDiscSets && data.driveDiscSets.sets) || [];
}

async function loadShowcase(url) {
  setStatus("Loading…");
  $("#showcase").classList.add("hidden");
  $("#player").classList.add("hidden");
  $("#calc-section").classList.add("hidden");
  CALC.current = null;
  showResults();
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    showcase = data;
    setStatus("");
    renderPlayer(data);
    renderShowcase(data);
  } catch (e) {
    setStatus(e.message || "Failed to load showcase", true);
  }
}

/* ===================== landing/results view switch ===================== */

function showLanding() {
  $("#hero").classList.remove("hidden");
  $("#results").classList.add("hidden");
  document.body.style.overflow = "";
}

function showResults() {
  $("#hero").classList.add("hidden");
  $("#results").classList.remove("hidden");
  window.scrollTo(0, 0);
}

/* ===================== boot ===================== */

async function boot() {
  $("#uid-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const uid = $("#uid-input").value.trim();
    if (!/^\d{6,12}$/.test(uid)) {
      setStatus("Please enter a valid UID (6-12 digits).", true);
      return;
    }
    loadShowcase(`/api/uid/${uid}`);
  });
  $("#btn-sample").addEventListener("click", () => loadShowcase("/api/local"));
  $("#btn-back").addEventListener("click", showLanding);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideEquipPop();
  });
  $("#calc-close").addEventListener("click", () => {
    $("#calc-section").classList.add("hidden");
    CALC.current = null;
  });
  $("#btn-calc").addEventListener("click", () => {
    if (currentAgent) openCalc(currentAgent);
  });

  try {
    await loadGameData();
    loadMonsterList().catch(() => {}); // preload monster list (background)
  } catch (e) {
    setStatus("Failed to load game data: " + e.message, true);
  }
}

boot();
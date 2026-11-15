"use strict";

const CATS = {
  hudba: "Hudba", divadlo: "Divadlo & stand-up", film: "Film", vystavy: "Výstavy",
  deti: "Pro děti", trhy: "Trhy & advent", festivaly: "Festivaly", sport: "Sport",
  prednasky: "Přednášky & prohlídky", tanec: "Tanec & party", ostatni: "Ostatní",
};
const REGIONS = { all: "Vše", ostrava: "Ostrava", fm: "Frýdek-Místek", okoli: "Okolí" };
const DAY = 864e5;

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fold = (s) => String(s ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

// Dates are handled as local "YYYY-MM-DD" strings to avoid timezone surprises.
const parse = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (s, n) => iso(new Date(parse(s).getTime() + n * DAY + 12 * 36e5));
const fmtDay = new Intl.DateTimeFormat("cs-CZ", { weekday: "long", day: "numeric", month: "long" });
const fmtShort = new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "numeric" });
const fmtMonth = new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "long" });
const fmtStamp = new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

const store = {
  get(k, d) { try { const v = localStorage.getItem("whatsup:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("whatsup:" + k, JSON.stringify(v)); } catch { /* private mode */ } },
};

const state = {
  mode: store.get("mode", "weekend"),
  region: store.get("region", "all"),
  cats: new Set(store.get("cats", [])),
  venues: new Set(store.get("venues", [])),
  vq: "",
  tips: false,
  kids: store.get("kids", false),
  q: "",
};
let feed = null;
let today = iso(new Date());

// ------------------------------------------------------------------ periods

/** Weekend = Fri–Sun; week = Mon–Sun. Returns [{key, title, days:[iso…]}] clipped to [today, feed.to]. */
function periods() {
  const out = [];
  const end = feed.to;
  const dow = (parse(today).getDay() + 6) % 7; // Mon=0 … Sun=6
  let monday = addDays(today, -dow);
  for (let i = 0; monday <= end; i++, monday = addDays(monday, 7)) {
    const first = state.mode === "weekend" ? addDays(monday, 4) : monday;
    const days = [];
    for (let d = first; d <= addDays(monday, 6); d = addDays(d, 1)) if (d >= today && d <= end) days.push(d);
    if (!days.length) continue;
    const n = out.length;
    const wk = state.mode === "weekend";
    const title = n === 0 ? (wk ? "Tento víkend" : "Tento týden")
      : n === 1 ? (wk ? "Příští víkend" : "Příští týden")
      : wk ? `Víkend ${rangeLabel(days, true)}` : `Týden od ${fmtMonth.format(parse(monday))}`;
    out.push({ key: `p${monday}`, title, days, short: n < 2 ? title : rangeLabel(days, true) });
  }
  return out;
}

function rangeLabel(days, short = false) {
  const a = parse(days[0]), b = parse(days[days.length - 1]);
  if (days.length === 1) return short ? fmtShort.format(a) : fmtMonth.format(a);
  if (a.getMonth() === b.getMonth()) return `${a.getDate()}.–${short ? fmtShort.format(b) : fmtMonth.format(b)}`;
  return `${short ? fmtShort.format(a) : fmtMonth.format(a)} – ${short ? fmtShort.format(b) : fmtMonth.format(b)}`;
}

// ------------------------------------------------------------------ filtering

/** Venue label used for the venue filter (aggregator events without a venue fall back to the town). */
const venueOf = (e) => e.venue || e.city || "Neuvedeno";

function matches(e, { ignoreCats = false, ignoreVenues = false } = {}) {
  if (state.region !== "all" && e.region !== state.region) return false;
  if (!ignoreCats && state.cats.size && !state.cats.has(e.category)) return false;
  if (!ignoreVenues && state.venues.size && !state.venues.has(venueOf(e))) return false;
  if (state.tips && !e.top) return false;
  if (state.kids && !(e.kids || e.category === "deti")) return false;
  if (state.q) {
    const hay = fold(`${e.title} ${e.venue || ""} ${e.city || ""} ${e.description || ""} ${CATS[e.category] || ""}`);
    if (!fold(state.q).split(/\s+/).every((w) => hay.includes(w))) return false;
  }
  return true;
}

/** Is the event shown anywhere in the current view? (weekend mode hides weekday-only events) */
function inView(e) {
  const last = e.end_date || e.date;
  if (last < today) return false;
  if (e.long) return true; // listed in the "Dlouhodobé" section
  const days = shownDays();
  for (let d = e.date < today ? today : e.date; d <= last && d <= feed.to; d = addDays(d, 1)) if (days.has(d)) return true;
  return false;
}
let _days = null, _daysMode = null;
function shownDays() {
  if (_daysMode !== state.mode) { _days = new Set(periods().flatMap((p) => p.days)); _daysMode = state.mode; }
  return _days;
}

/** The day within `days` on which an event is shown (its start, or the first day of the period if it's ongoing). */
function displayDay(e, days) {
  const last = e.end_date || e.date;
  if (last < days[0] || e.date > days[days.length - 1]) return null;
  return e.date >= days[0] ? e.date : days[0];
}

// ------------------------------------------------------------------ rendering

function gcalLink(e) {
  const d = (s) => s.replaceAll("-", "");
  let dates;
  if (e.time) {
    const start = `${d(e.date)}T${e.time.replace(":", "")}00`;
    const endT = e.end_time ? e.end_time.replace(":", "") + "00" : String(Math.min(23, +e.time.slice(0, 2) + 2)).padStart(2, "0") + e.time.slice(3) + "00";
    dates = `${start}/${d(e.end_date || e.date)}T${endT}`;
  } else {
    dates = `${d(e.date)}/${d(addDays(e.end_date || e.date, 1))}`;
  }
  const p = new URLSearchParams({
    action: "TEMPLATE", text: e.title, dates, ctz: "Europe/Prague",
    location: [e.venue, e.city].filter(Boolean).join(", "), details: e.url,
  });
  return `https://calendar.google.com/calendar/render?${p}`;
}

function card(e, shownOn) {
  const color = `var(--c-${e.category})`;
  const ongoing = e.end_date && e.end_date !== e.date;
  let when = e.time ? `<span class="time">${esc(e.time)}${e.end_time ? "–" + esc(e.end_time) : ""}</span>` : "";
  if (ongoing) {
    const from = shownOn && shownOn > e.date ? `probíhá ` : `${fmtShort.format(parse(e.date))} – `;
    when += `<span>${from}do ${fmtShort.format(parse(e.end_date))}</span>`;
  } else if (!e.time && !shownOn) {
    when = `<span class="time">${fmtShort.format(parse(e.date))}</span>`;
  }
  const badges = [
    e.top && `<span class="badge tip">Tip</span>`,
    e.sold_out && `<span class="badge sold">Vyprodáno</span>`,
    e.kids && e.category !== "deti" && !(e.tags || []).some((t) => t.startsWith("Věk")) && `<span class="badge kids">Pro děti</span>`,
    ...(e.tags || []).map((t) => `<span class="badge ${t.startsWith("Věk") ? "kids" : "free"}">${esc(t)}</span>`),
  ].filter(Boolean).join("");
  const where = [e.venue, e.city && !(e.venue || "").includes(e.city) && e.city !== "Ostrava" ? e.city : null].filter(Boolean).join(" · ");
  const initial = esc((e.title.match(/[\p{L}\p{N}]/u) || ["?"])[0].toUpperCase());
  return `
  <article class="card${e.top ? " top" : ""}${e.sold_out ? " sold" : ""}" style="--c:${color}">
    <div class="thumb"><span>${initial}</span>${e.image ? `<img src="${esc(e.image)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}</div>
    <div class="body">
      <div class="meta">${when}<span class="cat">${esc(CATS[e.category] || "Ostatní")}</span>${badges ? `<span class="badges">${badges}</span>` : ""}</div>
      <h4 class="title"><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a></h4>
      ${where ? `<div class="where">${esc(where)}</div>` : ""}
      ${e.description ? `<p class="desc">${esc(e.description)}</p>` : ""}
      <div class="actions">
        ${e.tickets ? `<a class="btn primary" href="${esc(e.tickets)}" target="_blank" rel="noopener">Vstupenky</a>` : ""}
        <a class="btn" href="${esc(gcalLink(e))}" target="_blank" rel="noopener">+ Do kalendáře</a>
        <span class="src">${esc(e.source)}</span>
      </div>
    </div>
  </article>`;
}

function render() {
  const ps = periods();
  const visible = feed.events.filter((e) => matches(e));
  const regular = visible.filter((e) => !e.long);
  const long = visible.filter((e) => e.long && (e.end_date || e.date) >= today);

  let html = "";
  const jump = [];
  for (const p of ps) {
    const byDay = new Map(p.days.map((d) => [d, []]));
    for (const e of regular) {
      const d = displayDay(e, p.days);
      if (d) byDay.get(d).push(e);
    }
    const total = [...byDay.values()].reduce((n, l) => n + l.length, 0);
    jump.push(`<a class="chip" href="#${p.key}">${esc(p.short)} <span class="n">${total}</span></a>`);

    html += `<section class="period" id="${p.key}">
      <div class="period-head"><h2>${esc(p.title)}</h2><span class="range">${esc(rangeLabel(p.days))}</span><span class="count">${total} ${plural(total)}</span></div>`;
    if (!total) html += `<div class="empty">Pro zvolené filtry tu nic není.</div>`;
    for (const [d, list] of byDay) {
      if (!list.length) continue;
      // events starting today by time; ones that started earlier ("probíhá") go last
      list.sort((a, b) => (a.date < d) - (b.date < d) || (a.time || "99").localeCompare(b.time || "99") || a.title.localeCompare(b.title, "cs"));
      const label = d === today ? "Dnes" : d === addDays(today, 1) ? "Zítra" : "";
      html += `<div class="day"><h3>${esc(fmtDay.format(parse(d)))}${label ? `<small>${label}</small>` : ""}</h3>
        <div class="list">${list.map((e) => card(e, d)).join("")}</div></div>`;
    }
    html += `</section>`;
  }

  if (long.length) {
    long.sort((a, b) => (a.end_date || a.date).localeCompare(b.end_date || b.date));
    html += `<details class="long"${store.get("longOpen", false) ? " open" : ""}>
      <summary>Dlouhodobé akce a výstavy <span>${long.length}</span></summary>
      <div class="list">${long.map((e) => card(e, null)).join("")}</div></details>`;
  }
  if (!ps.length) html = `<div class="empty">Data jsou zastaralá – počkej na další aktualizaci.</div>`;

  if (state.mode === "weekend") {
    const hidden = visible.filter((e) => !e.long && (e.end_date || e.date) >= today && !inView(e)).length;
    const anyShown = visible.some((e) => inView(e));
    if (hidden && !anyShown) {
      html = `<div class="empty hint">O víkendech tu nic není, ale ve všední dny ${hidden === 1 ? "je" : hidden < 5 ? "jsou" : "je"} ${hidden} ${plural(hidden)}.
        <button class="btn primary" data-switch-all>Zobrazit všechny dny</button></div>` + html;
    }
  }
  $("#feed").innerHTML = html;
  $("#feed [data-switch-all]")?.addEventListener("click", () => document.querySelector('.seg [data-mode="all"]').click());
  $("#jump").innerHTML = jump.join("");
  $("details.long")?.addEventListener("toggle", (ev) => store.set("longOpen", ev.target.open));
  renderCats();
  renderVenues();
}

function plural(n) { return n === 1 ? "akce" : n >= 2 && n <= 4 ? "akce" : "akcí"; }

function renderRegions() {
  const counts = { all: 0 };
  for (const e of feed.events) if ((e.end_date || e.date) >= today) { counts.all++; counts[e.region] = (counts[e.region] || 0) + 1; }
  $("#regions").innerHTML = Object.entries(REGIONS)
    .filter(([k]) => k === "all" || counts[k])
    .map(([k, label]) => `<button class="chip${state.region === k ? " on" : ""}" data-region="${k}">${label}</button>`)
    .join("") +
    `<button class="chip star${state.tips ? " on" : ""}" data-tips>★ Jen tipy</button>` +
    `<button class="chip kids${state.kids ? " on" : ""}" data-kids aria-pressed="${state.kids}">
       <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="5" r="2.2"/><circle cx="16.5" cy="8.5" r="1.8"/><path d="M8 8.5v6m0 0-2 5.5m2-5.5 2 5.5M5 11h6M16.5 11.5v4m0 0-1.5 4.5m1.5-4.5 1.5 4.5M14 13.5h5"/></svg>
       S dětmi</button>` +
    `<button class="chip venue-btn${state.venues.size ? " on" : ""}" data-venues aria-expanded="${!$("#venues").hidden}" aria-controls="venues">
       <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>
       ${state.venues.size ? `Místa: ${state.venues.size}` : "Místa"}</button>` +
    (state.venues.size ? `<button class="chip clear" data-clear-venues aria-label="Zrušit výběr míst">✕</button>` : "");
}

function renderVenues() {
  const panel = $("#venues");
  if (panel.hidden) return;
  const counts = new Map();
  const regionOf = new Map();
  for (const e of feed.events) {
    if (!inView(e) || !matches(e, { ignoreVenues: true })) continue;
    const v = venueOf(e);
    counts.set(v, (counts.get(v) || 0) + 1);
    if (!regionOf.has(v)) regionOf.set(v, e.region);
  }
  for (const v of state.venues) if (!counts.has(v)) { counts.set(v, 0); regionOf.set(v, "okoli"); }
  const q = fold(state.vq);
  const groups = { ostrava: [], fm: [], okoli: [] };
  for (const [v, n] of counts) if (!q || fold(v).includes(q)) groups[regionOf.get(v) || "okoli"].push([v, n]);
  const html = Object.entries(groups).filter(([, l]) => l.length).map(([r, list]) => {
    list.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "cs"));
    return `<fieldset><legend>${REGIONS[r]} <span>${list.length}</span></legend>${list.map(([v, n]) =>
      `<label class="vopt${n ? "" : " zero"}"><input type="checkbox" value="${esc(v)}"${state.venues.has(v) ? " checked" : ""}><span class="vname">${esc(v)}</span><span class="n">${n}</span></label>`).join("")}</fieldset>`;
  }).join("");
  $("#venues-body").innerHTML = html || `<div class="empty">Žádné místo neodpovídá hledání.</div>`;
}

function toggleVenuePanel(open = $("#venues").hidden) {
  $("#venues").hidden = !open;
  renderRegions();
  renderVenues();
  setToolbarHeight();
  if (open) $("#vq").focus({ preventScroll: true });
}

function venuesChanged() {
  store.set("venues", [...state.venues]);
  renderRegions();
  renderVenues();
  render();
}

function renderCats() {
  const counts = {};
  for (const e of feed.events) if (inView(e) && matches(e, { ignoreCats: true })) counts[e.category] = (counts[e.category] || 0) + 1;
  $("#cats").innerHTML = `<button class="chip${state.cats.size ? "" : " on"}" data-cat="">Všechny kategorie</button>` +
    Object.entries(CATS)
      .filter(([k]) => counts[k] || state.cats.has(k))
      .map(([k, label]) => `<button class="chip${state.cats.has(k) ? " on" : ""}" data-cat="${k}" style="--c:var(--c-${k})"><span class="dot"></span>${label} <span class="n">${counts[k] || 0}</span></button>`)
      .join("");
}

function renderFoot() {
  const gen = new Date(feed.generated);
  $("#updated").textContent = `${feed.events.length} akcí na příštích ${Math.round((parse(feed.to) - parse(feed.from)) / DAY / 7)} týdnů · aktualizováno ${fmtStamp.format(gen)}`;
  $("#foot").innerHTML = `Data se stahují automaticky jednou denně z veřejných kalendářů. Před cestou si raději ověř detaily u pořadatele.
    <ul>${feed.sources.map((s) => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a> · <span class="${s.ok ? "ok" : "err"}">${s.ok ? s.count + " akcí" : "chyba"}</span></li>`).join("")}</ul>`;
}

function setToolbarHeight() {
  const tb = $("#toolbar");
  const h = getComputedStyle(tb).position === "sticky" ? tb.offsetHeight : 0;
  document.documentElement.style.setProperty("--toolbar-h", h + "px");
  document.documentElement.style.scrollPaddingTop = h + 40 + "px";
}

// ------------------------------------------------------------------ events

function bind() {
  document.querySelectorAll(".seg button").forEach((b) => {
    b.classList.toggle("on", b.dataset.mode === state.mode);
    b.addEventListener("click", () => {
      state.mode = b.dataset.mode; store.set("mode", state.mode);
      document.querySelectorAll(".seg button").forEach((x) => x.classList.toggle("on", x === b));
      render();
    });
  });
  $("#regions").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    if ("venues" in b.dataset) return toggleVenuePanel();
    if ("clearVenues" in b.dataset) { state.venues.clear(); return venuesChanged(); }
    if ("tips" in b.dataset) state.tips = !state.tips;
    else if ("kids" in b.dataset) { state.kids = !state.kids; store.set("kids", state.kids); }
    else { state.region = b.dataset.region; store.set("region", state.region); }
    renderRegions(); renderVenues(); render();
  });
  $("#venues-body").addEventListener("change", (ev) => {
    const cb = ev.target.closest("input[type=checkbox]"); if (!cb) return;
    cb.checked ? state.venues.add(cb.value) : state.venues.delete(cb.value);
    venuesChanged();
  });
  $("#vq").addEventListener("input", (ev) => { state.vq = ev.target.value.trim(); renderVenues(); });
  $("#v-all").addEventListener("click", () => {
    document.querySelectorAll("#venues-body input[type=checkbox]").forEach((cb) => state.venues.add(cb.value));
    venuesChanged();
  });
  $("#v-none").addEventListener("click", () => { state.venues.clear(); venuesChanged(); });
  $("#v-close").addEventListener("click", () => toggleVenuePanel(false));
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !$("#venues").hidden) toggleVenuePanel(false); });
  $("#cats").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    const k = b.dataset.cat;
    if (!k) state.cats.clear();
    else state.cats.has(k) ? state.cats.delete(k) : state.cats.add(k);
    store.set("cats", [...state.cats]);
    renderVenues(); render();
  });
  let t;
  $("#q").addEventListener("input", (ev) => {
    clearTimeout(t);
    t = setTimeout(() => { state.q = ev.target.value.trim(); renderVenues(); render(); }, 120);
  });
  window.addEventListener("resize", setToolbarHeight);
}

function loadScriptFeed() {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `data/events.js?v=${Date.now().toString(36)}`;
    s.onload = () => (window.__FEED__ ? resolve(window.__FEED__) : reject(new Error("prázdná data")));
    s.onerror = () => reject(new Error("data/events.js nenalezen"));
    document.head.appendChild(s);
  });
}

async function loadFeed() {
  // file:// blocks fetch(), so load the data as a script there; on a web server prefer JSON.
  if (location.protocol === "file:") return loadScriptFeed();
  try {
    const r = await fetch(`data/events.json?v=${Date.now().toString(36)}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch {
    return loadScriptFeed();
  }
}

async function init() {
  try {
    feed = await loadFeed();
  } catch (err) {
    $("#feed").innerHTML = `<div class="empty">Nepodařilo se načíst program (${esc(err.message)}).</div>`;
    $("#updated").textContent = "";
    return;
  }
  if (today < feed.from) today = feed.from;
  for (const k of [...state.cats]) if (!CATS[k]) state.cats.delete(k);
  renderRegions();
  renderFoot();
  bind();
  render();
  setToolbarHeight();
  if (location.hash) document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView();
}

init();

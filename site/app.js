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
  tips: false,
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

function matches(e, { ignoreCats = false } = {}) {
  if (state.region !== "all" && e.region !== state.region) return false;
  if (!ignoreCats && state.cats.size && !state.cats.has(e.category)) return false;
  if (state.tips && !e.top) return false;
  if (state.q) {
    const hay = fold(`${e.title} ${e.venue || ""} ${e.city || ""} ${e.description || ""} ${CATS[e.category] || ""}`);
    if (!fold(state.q).split(/\s+/).every((w) => hay.includes(w))) return false;
  }
  return true;
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
    e.kids && e.category !== "deti" && `<span class="badge kids">Dětem</span>`,
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

  $("#feed").innerHTML = html;
  $("#jump").innerHTML = jump.join("");
  $("details.long")?.addEventListener("toggle", (ev) => store.set("longOpen", ev.target.open));
  renderCats();
}

function plural(n) { return n === 1 ? "akce" : n >= 2 && n <= 4 ? "akce" : "akcí"; }

function renderRegions() {
  const counts = { all: 0 };
  for (const e of feed.events) if ((e.end_date || e.date) >= today) { counts.all++; counts[e.region] = (counts[e.region] || 0) + 1; }
  $("#regions").innerHTML = Object.entries(REGIONS)
    .filter(([k]) => k === "all" || counts[k])
    .map(([k, label]) => `<button class="chip${state.region === k ? " on" : ""}" data-region="${k}">${label}</button>`)
    .join("") + `<button class="chip star${state.tips ? " on" : ""}" data-tips>★ Jen tipy</button>`;
}

function renderCats() {
  const counts = {};
  for (const e of feed.events) if ((e.end_date || e.date) >= today && matches(e, { ignoreCats: true })) counts[e.category] = (counts[e.category] || 0) + 1;
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
    if ("tips" in b.dataset) state.tips = !state.tips;
    else { state.region = b.dataset.region; store.set("region", state.region); }
    renderRegions(); render();
  });
  $("#cats").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    const k = b.dataset.cat;
    if (!k) state.cats.clear();
    else state.cats.has(k) ? state.cats.delete(k) : state.cats.add(k);
    store.set("cats", [...state.cats]);
    render();
  });
  let t;
  $("#q").addEventListener("input", (ev) => {
    clearTimeout(t);
    t = setTimeout(() => { state.q = ev.target.value.trim(); render(); }, 120);
  });
  window.addEventListener("resize", setToolbarHeight);
}

async function init() {
  try {
    const r = await fetch(`data/events.json?v=${Date.now().toString(36)}`, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    feed = await r.json();
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

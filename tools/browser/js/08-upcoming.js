// ---------- coming up ----------
const TX = {}; D.texts.forEach(t => TX[t.id] = t);
function overlapMoods(textIds, verses) {
  const out = [];
  textIds.forEach(id => (TX[id] ? TX[id].sections : []).forEach(s => {
    if (s.verses !== "all" && verses) {
      const [lo, hi] = s.verses.split("-").map(Number);
      if (!verses.some(v => v >= lo && v <= (hi || lo))) return;
    }
    s.mood.forEach(m => { if (!out.includes(m)) out.push(m); });
  }));
  return out;
}
function recentChants(date, weeks = 12) {
  if (!date) date = ymd();
  const lo = new Date(new Date(date) - weeks * 7 * 864e5).toISOString().slice(0, 10);
  const set = new Set(D.history.filter(h => h.date >= lo && h.date < date).map(h => h.chant));
  D.calendar.filter(c => c.date >= lo && c.date < date).forEach(c => c.planned.forEach(pl => pl.chants.forEach(x => set.add(x))));
  return set;
}
function goText(id) {
  curText = id;
  document.querySelector('nav button[data-tab="texts"]').click();
}
// the copy on GitHub Pages: everything to look at, nothing to save
const demoNote = () => D.demo ? `<div class="card" style="margin-bottom:12px"><b>A demo of the chant browser</b>, for the fictional St. Example's: the chants, the psalms with their moods, and the lectionary are all here to try. Planning and saving a service, building its leaflet and keeping your own notes need a copy on your own computer: see <a href="https://github.com/choyun1/precentor#getting-started" target="_blank" rel="noopener">Getting started</a>.</div>` : "";

// the launcher's first run: no parish folder yet
function setupCard() {
  if (!SETUP) return "";
  return `<div class="card" id="setup" style="margin-bottom:12px"><b>Welcome.</b> A few things about your parish, to make its own folder (<code>parish/</code>), where your services, notes and pointing will be kept. All of it can be changed later in <code>parish/parish.txt</code>.
    <label class="hint" style="display:block;margin:8px 0 4px">The parish's name (as on a service leaflet)<br><input type="text" id="su-name" style="width:100%" placeholder="St. Mary's, Anytown"></label>
    <div style="display:flex;gap:12px;flex-wrap:wrap">
      <label class="hint">Season after Pentecost: lectionary track${info("Track 1 follows the Old Testament stories week by week (semicontinuous); Track 2 pairs the reading with the Gospel. The other is always offered too.")}<br><select id="su-track"><option value="2">Track 2</option><option value="1">Track 1</option></select></label>
      <label class="hint">Patronal feast<br><select id="su-feast"><option value="">none</option>${SETUP.map(f => `<option value="${esc(f.key)}">${esc(f.name)} (${esc(f.date)})</option>`).join("")}</select></label>
      <label class="hint">Verses the lectionary puts in brackets<br><select id="su-verses"><option value="sing">sing them</option><option value="leave out">leave them out</option></select></label></div>
    <p style="margin:10px 0 0"><button class="small primary" onclick="setupParish(this)">Make the parish folder</button> <span class="hint" id="su-msg"></span></p></div>`;
}
async function setupParish(btn) {
  const name = $("#su-name").value.trim(), msg = $("#su-msg");
  if (!name) { msg.textContent = "the parish's name, please"; return; }
  btn.disabled = true; msg.textContent = "Making it…";
  const j = await post("/api/setup", {name, track: $("#su-track").value, patronal: $("#su-feast").value, optionalVerses: $("#su-verses").value});
  if (!j.ok) { btn.disabled = false; msg.textContent = j.error || "Could not make it"; return; }
  msg.textContent = j.done.join(" ") + " Starting again in it (the chants' pictures are kept; this takes a moment)…";
  for (let i = 0; i < 300; i++) {                  // the launcher starts again, rebuilding the page for the parish
    await new Promise(r => setTimeout(r, 2000));
    try { const p = await fetch("/api/ping").then(r => r.json()); if (p.ok && !p.setup) { location.href = j.url; return; } } catch (e) {}
  }
  msg.textContent = "The launcher hasn't come back: close it and open it again.";
}

function toggleDay(date) {             // open a day (sliding), or shut it
  if (UPCOMING.open.has(date)) {
    const row = document.querySelector(`.urow[data-date="${date}"]`);
    if (row) row.classList.remove("open");
    slideShut([document.querySelector(`#tab-upcoming .card[data-day="${date}"]`)], () => { UPCOMING.open.delete(date); renderUpcoming(); });
  } else {
    UPCOMING.open.add(date); JUST = "day:" + date; renderUpcoming(); slideOpen();
  }
}
function renderUpcoming() {
  const today = ymd();
  const all = D.calendar.filter(c => c.date >= today), rows = all.slice(0, UPCOMING.n);
  const first = c => c.options.find(o => o.track === "Track " + D.parish.track) || c.options[0];
  $("#tab-upcoming").innerHTML = demoNote() + setupCard() + `<p class="count">The psalms appointed for the coming weeks${info("The Revised Common Lectionary (Episcopal edition). In the season after Pentecost, Track 1 is the semicontinuous psalm and Track 2 the one related to the Old Testament reading. Click a day for its psalms, their moods and chants to try.")}</p>
    <div class="clist">` + rows.map(c => {
    const open = UPCOMING.open.has(c.date), f = first(c);
    const status = c.planned.map(pl => `<span class="chip ${pl.sung ? "g-calm on" : "g-calm"}">${pl.sung ? "sung" : "planned"}: ${pl.choir === false ? "no choir" : esc(pl.chants.map(chantText).join(", ") || "chant not chosen")}</span>`).join(" ");
    const row = `<div class="crow urow ${open ? "open" : ""} ${JUST === "day:" + c.date ? "just" : ""}" data-date="${c.date}" onclick="toggleDay('${c.date}')">
      <span class="nm"><span class="caret">▸</span>${swatch(c.date)}${esc(new Date(c.date + "T12:00").toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"}))}</span>
      <span>${esc(c.label)} <span class="meta">· ${esc(c.year)}</span></span>
      <span class="meta">${f ? (/^\d/.test(f.spec) ? "Ps " : "") + esc(f.spec) + (c.options.length > 1 ? ` <span title="${esc(c.options.slice(1).map(o => o.spec).join(", "))}">+${c.options.length - 1}</span>` : "") : "—"}</span>
      <span>${status}</span></div>`;
    if (!open) return row;
    const recent = recentChants(c.date);
    return row + `<div class="card ${JUST === "day:" + c.date ? "opening" : ""}" data-day="${c.date}"><p style="margin:0 0 4px">${lectLink("The readings for " + c.label, c.link)} · <span class="link" onclick="planOn('${c.date}')">Plan this day</span></p>
      ${c.options.length ? c.options.map(o => {
        const mood = overlapMoods(o.texts, o.verses);
        const sg = mood.length ? D.chants.map(ch => ({ch, ...score(mood, val(ch, "mood"))})).filter(x => x.s > 0 && !recent.has(x.ch.id))
          .sort((a, b) => b.s - a.s || (val(b.ch, "rating") || 0) - (val(a.ch, "rating") || 0)).slice(0, 4) : [];
        return `<div class="section"><div class="moodrow"><b style="font-weight:normal">${o.track ? esc(o.track) + ": " : ""}${/^\d/.test(o.spec) ? "Psalm " : ""}${esc(o.spec)}</b>
          ${o.texts.map(id => `<span class="link" onclick="goText('${esc(id)}')">${esc(TX[id] ? TX[id].title : id)}</span>`).join(", ")}
          ${mood.map(m => chip(m)).join(" ")}${o.error ? ` <span class="hint">${/^\d/.test(o.spec) ? esc(o.error) : "not in the library yet"}</span>` : ""}</div>
          ${sg.length ? `<div class="used">Try: ${sg.map(x => `<span class="link" onclick="showChant('${esc(x.ch.id)}')">${esc(CN(x.ch.id))}</span>`).join(" · ")}</div>` : ""}</div>`;
      }).join("") : '<p class="hint">No psalm in the table for this day.</p>'}</div>`;
  }).join("") + `</div>` + (all.length > rows.length ? `<span class="link more" onclick="UPCOMING.n += 12; renderUpcoming()">Show more weeks</span>` : "");
}
async function planOn(date) { B.started = true; await setDate(date); document.querySelector('nav button[data-tab="builder"]').click(); }
const UPCOMING = {n: 8, open: new Set()};

// ---------- the music library (parish/library/catalog.csv; tools/library.py) ----------
// Optional: with no library the planner works as before. Pieces are suggested for the day (its occasion, then its
// season, then any time): the choir's in the anthem boxes, organ music in the prelude and postlude. They can be added
// from those boxes, from what's been done before, or from the score folders.
const LIB = SV.library || {rows: [], folders: false, seasons: [], formats: [], where: "library/catalog.csv"};
const SEASON_NAMES = {advent: "Advent", christmas: "Christmas", epiphany: "Epiphany", lent: "Lent", holy_week: "Holy Week",
  easter: "Easter", pentecost: "after Pentecost"};
const libPiece = r => r.Composer ? `${r.Title} - ${r.Composer}${r.Years ? " (" + r.Years + ")" : ""}` : r.Title;
const libSurname = x => normT((String(x || "").replace(/\(.*?\)/g, "").trim().split(/\s+/).pop() || ""));
// an index of the library, so each lookup isn't a walk through every piece (and every anthem sung)
let LIBX = null;
function libIndex() {
  if (LIBX && LIBX.rows === LIB.rows && LIBX.n === LIB.rows.length) return LIBX;
  const byTitle = new Map();
  for (const r of LIB.rows) { const k = normT(r.Title); if (!byTitle.has(k)) byTitle.set(k, []); byTitle.get(k).push(r); }
  LIBX = {rows: LIB.rows, n: LIB.rows.length, byTitle, found: new Map(), sung: null, options: {}, fam: new Map()};
  return LIBX;
}
const libChanged = () => { LIBX = null; };
function libFind(v) {
  const X = libIndex(), key = String(v || "");
  if (!X.found.has(key)) {
    const [t, c] = splitPiece(key);
    X.found.set(key, (X.byTitle.get(normT(t)) || []).find(r => !c || libSurname(r.Composer) === libSurname(c)) || null);
  }
  return X.found.get(key);
}
const daySeason = () => (SV.seasons || {})[B.date] || "";
function libOccasion(r) {
  const label = normT(((SV.lect || {})[B.date] || [])[2] || "");
  return !!label && String(r.Occasion || "").split(/[;,]/).map(normT).some(o => o && label.includes(o));
}
// 0: for this day, 1: this season, 2: any time, 3: another season
const libRank = r => libOccasion(r) ? 0 : r.Season && r.Season === daySeason() ? 1 : !r.Season ? 2 : 3;
// a piece's family in the record: organ music is done as a prelude or postlude, the rest as an anthem
function libFam(r) {
  const X = libIndex();
  if (!X.fam.has(r)) X.fam.set(r, libFor(r) === "organ" ? "organ" : "anthem");
  return X.fam.get(r);
}
function libSung(r) {
  const X = libIndex();
  if (!X.sung) {
    X.sung = new Map();
    for (const f of ["anthem", "organ"]) for (const x of REP[f] || []) {
      const hit = libFind(x[0]); if (!hit) continue;
      const had = X.sung.get(hit);                // the same piece under two names, or as an anthem and a voluntary
      X.sung.set(hit, had ? [...new Set(had.concat(x[1]))].sort() : x[1]);
    }
  }
  return (X.sung.get(r) || []).filter(d => d < (B.date || "9999"));
}
function libWhere(r) {
  const bits = [r.Format, r.Location, r.Copies ? r.Copies + " copies" : "", r["Publisher no."] ? "order no. " + r["Publisher no."] : "", r.Voicing];
  return bits.filter(Boolean).map(esc).join(" · ");
}
// the suggestions for an anthem box (fam "anthem": the choir's pieces) or a prelude or postlude ("organ"): the
// library for this day first, then everything done before that isn't in it
function libOptions(fam) {
  const X = libIndex(), key = fam + " " + (B.date || "");
  if (X.options[key] !== undefined) return X.options[key];
  const rows = LIB.rows.filter(r => libReal(r) && libFam(r) === fam).map(r => [libRank(r), r])
    .sort((a, b) => a[0] - b[0] || normT(a[1].Title).localeCompare(normT(b[1].Title)));
  const lib = rows.map(([k, r]) => {
    const sung = libSung(r), when = k === 0 ? "for this day" : r.Season ? SEASON_NAMES[r.Season] || r.Season : "any time";
    return `<option value="${esc(libPiece(r))}">${esc(when)}${r.Format ? " · " + esc(r.Format) : ""}${sung.length ? ` · ${sung.length}× · last ${esc(sung[sung.length - 1])}` : ` · not ${fam === "organ" ? "played" : "sung"} here yet`}</option>`;
  });
  const rest = (REP[fam] || []).filter(x => !libFind(x[0])).map(r => `<option value="${esc(r[0])}">${r[1].length}× · last ${esc(r[1][r[1].length - 1])}</option>`);
  return (X.options[key] = lib.concat(rest).join(""));
}
// under an anthem: what the library knows of it, with its PDF
function libHint(v) {
  const r = libFind(v); if (!r) return "";
  const i = LIB.rows.indexOf(r);
  return `<br><span class="hint">In the library${r.Season ? " (" + esc(SEASON_NAMES[r.Season] || r.Season) + ")" : ""}${libWhere(r) ? ": " + libWhere(r) : ""}</span>${libPdf(r) ? ` · <span class="link" onclick="libOpen(${i})">Open score</span>` : ""}`;
}
// the PDF of a piece on this computer (the launcher matches the score folders' files to the library: /api/ping)
const libPdf = r => SERVER && LIB.folders ? (LIB.pdfs || {})[libPiece(r)] || "" : "";
// not "???" or "TBD", nor a parish's "not music:" (parish.txt), such as SNOW DAY
const NOT_MUSIC = new Set(["", "tbd", "tba"].concat((SV.notMusic || []).map(w => w.toLowerCase().replace(/[\s?.\-–—]/g, ""))));
const libReal = r => !NOT_MUSIC.has(String(r.Title || "").toLowerCase().replace(/[\s?.\-–—]/g, ""));
async function libOpen(i) {
  const j = await post("/api/score", {file: libPdf(LIB.rows[i])});
  if (!j.ok) alert(j.error || "could not open it");
}
// "Add to the library", under an anthem that isn't in it
const LIBV = {};
function libAddBox(id, v, organ) {
  v = String(v || "").trim();
  if (!SERVER || !v || hymnsOf(v).length || libFind(v)) return "";
  LIBV[id] = v;
  const [t, comp] = splitPiece(v), m = comp.match(/^(.*?)\s*\(([^)]*\d[^)]*)\)\s*$/);
  const opt = (list, cur, names) => list.map(x => `<option value="${esc(x)}" ${x === cur ? "selected" : ""}>${esc(names ? names[x] || x : x || "")}</option>`).join("");
  return `<details style="margin:4px 0 8px"><summary class="hint">Not in the library: add it</summary>
    <div class="libform">
      <label>Title <input type="text" id="lt-${id}" value="${esc(t)}"></label>
      <label>Composer <input type="text" id="lc-${id}" value="${esc(m ? m[1] : comp)}"></label>
      <label>Years <input type="text" id="ly-${id}" value="${esc(m ? m[2] : "")}" placeholder="1852-1924" style="width:7em"></label>
      <label>Season <select id="ls-${id}"><option value="">any time</option>${opt(LIB.seasons, daySeason(), SEASON_NAMES)}</select></label>
      <label>Occasion <input type="text" id="lo-${id}" placeholder="e.g. Ascension"></label>
      <label>Format <select id="lf-${id}"><option value=""></option>${opt(LIB.formats, "")}</select></label>
      <label>Voicing <input type="text" id="lv-${id}" value="${organ ? "organ" : ""}" placeholder="SATB, organ"></label>
      <label>Where the copies are <input type="text" id="ll-${id}" placeholder="e.g. choir library, box 14"></label>
      <label>Copies <input type="number" min="0" id="ln-${id}" style="width:5em"></label>
      <label>Publisher no. <input type="text" id="lp-${id}" placeholder="for reordering"></label>
      ${LIB.folders ? `<label>PDF <input type="file" accept="application/pdf,.pdf" id="lpdf-${id}"></label>` : ""}
    </div>
    <button class="small" onclick="libAdd('${id}')">Add to the library</button>
    <span class="hint">kept in ${esc(LIB.where)}${LIB.folders ? "; a PDF is copied into your score folder" : ""}</span></details>`;
}
async function libAdd(id) {
  const g = k => ($("#" + k + "-" + id) || {}).value || "";
  const row = {Title: g("lt").trim(), Composer: g("lc").trim(), Years: g("ly").trim(), Season: g("ls"), Occasion: g("lo").trim(),
    Format: g("lf"), Voicing: g("lv").trim(), Location: g("ll").trim(), Copies: g("ln").trim(), "Publisher no.": g("lp").trim()};
  const f = ($("#lpdf-" + id) || {}).files, body = {row};
  if (f && f[0]) {
    if (f[0].size > 14 * 1024 * 1024) { alert("That PDF is too big to send from here (over 14 MB): put it in the score folder and use Look for new PDFs."); return; }
    body.pdf = await new Promise(ok => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result).split(",")[1]); fr.readAsDataURL(f[0]); });
    if (!row.Format) row.Format = "PDF";
  }
  const j = await post("/api/library/add", body);
  if (!j.ok) { alert(j.error || "could not add it"); return; }
  const old = libFind(libPiece(j.row)); if (old) Object.assign(old, j.row); else LIB.rows.push(j.row); libChanged();
  renderBuilder();
}
// ---------- the Music library tab ----------
// organ alone, or the choir (with or without organ): from the Voicing, else guessed from the title
const ORGAN_WORDS = /\b(voluntary|prelude|fugue|toccata|invention|trio|improvisation|organ|fantasia|postlude|chorale prelude|trumpet tune|partita|sortie|offertoire|carillon|almain|pavan|galliard)\b|\bBWV\s*[5-7]\d\d\b/i;
const VOICES = /\b(s?a?t?b|satb|ssa|sab|ttbb|ttb|unison|choir|voices?|treble|soprano|alto|tenor|bass|cantor)\b/i;
function libFor(r) {
  const v = String(r.Voicing || "");
  if (v) return /\b(organ|keyboard|piano|harpsichord)\b/i.test(v) && !VOICES.test(v) ? "organ" : "choir";
  return ORGAN_WORDS.test(r.Title) && !VOICES.test(r.Title) ? "organ" : "choir";
}
const FOR_NAMES = {choir: "Choir", organ: "Organ"};
const LV = {q: "", only: "", shown: 100, key: ""};   // shown: how many rows the list shows (100 more at a time)
const SEASON_ORDER = ["advent", "christmas", "epiphany", "lent", "holy_week", "easter", "pentecost", ""];
const libLast = r => { const s = libSung(r); return s.length ? s[s.length - 1] : ""; };
// each field: its label, its usual direction, the value to sort on (empty: last, whichever way)
const LIB_FIELDS = {
  title: {label: "Title", dir: 1, val: r => normT(r.Title)},
  composer: {label: "Composer", dir: 1, val: r => normT(libSurname(r.Composer) + " " + r.Composer)},
  for: {label: "For", dir: 1, val: r => libFor(r)},
  season: {label: "Season", dir: 1, val: r => String(SEASON_ORDER.indexOf(r.Season || "")).padStart(2, "0")},
  where: {label: "Where", dir: 1, val: r => normT(libWhere(r))},
  sung: {label: "Last sung", dir: -1, val: r => libLast(r)},
  times: {label: "Times sung", dir: -1, val: r => String(libSung(r).length).padStart(4, "0")},
  pdf: {label: "Has a PDF", dir: -1, val: r => libPdf(r) ? "1" : "0"},
};
LV.levels = (() => {
  try { const v = JSON.parse(localStorage.getItem("precentor-sort-library")); if (Array.isArray(v) && v.length && v.every(l => LIB_FIELDS[l.f])) return v; } catch (e) {}
  return [{f: "title", d: 1}];
})();
function libCompare(a, b) {
  for (const l of LV.levels) {
    const f = LIB_FIELDS[l.f], va = f.val(a), vb = f.val(b);
    if (va === vb) continue;
    if (va === "") return 1;
    if (vb === "") return -1;
    return (va < vb ? -1 : 1) * l.d;
  }
  return normT(a.Title).localeCompare(normT(b.Title));
}
function libSortChanged() { try { localStorage.setItem("precentor-sort-library", JSON.stringify(LV.levels)); } catch (e) {} renderLibrary(); }
function libSortBy(f) {                       // a heading: sort by it first; again, the other way round
  if (LV.levels[0].f === f) LV.levels[0].d *= -1;
  else LV.levels = [{f, d: LIB_FIELDS[f].dir}].concat(LV.levels.filter(l => l.f !== f)).slice(0, 5);
  libSortChanged();
}
function libSortSet(i, f) { LV.levels[i] = {f, d: LIB_FIELDS[f].dir}; libSortChanged(); }
function libSortDir(i) { LV.levels[i].d *= -1; libSortChanged(); }
function libSortDel(i) { LV.levels.splice(i, 1); libSortChanged(); }
function libSortAdd() {
  const used = new Set(LV.levels.map(l => l.f));
  const f = ["composer", "season", "for", "title", "sung"].find(k => !used.has(k)) || "title";
  LV.levels.push({f, d: LIB_FIELDS[f].dir}); libSortChanged();
}
function libSortControl() {
  const opts = sel => Object.entries(LIB_FIELDS).map(([k, f]) => `<option value="${k}" ${k === sel ? "selected" : ""}>${esc(f.label)}</option>`).join("");
  return `<div class="sortlevels" style="max-width:340px">${LV.levels.map((l, i) => `<div class="row" style="gap:4px;margin-bottom:4px;flex-wrap:nowrap">
      <span class="hint" style="width:52px;flex:none">${i ? "then by" : "sort by"}</span>
      <select onchange="libSortSet(${i}, this.value)" style="min-width:0;flex:1">${opts(l.f)}</select>
      <button class="small" title="${l.d > 0 ? "ascending: click for descending" : "descending: click for ascending"}" onclick="libSortDir(${i})">${l.d > 0 ? "↑" : "↓"}</button>
      ${i ? `<span class="link" title="remove" onclick="libSortDel(${i})">✕</span>` : ""}</div>`).join("")}
    ${LV.levels.length < 5 ? `<span class="link hint" onclick="libSortAdd()">+ then by</span>` : ""}</div>`;
}
function libTools() {
  if (!SERVER) return "";
  const not = f => (REP[f] || []).filter(x => libReal({Title: x[0]}) && !hymnsOf(x[0]).length && !libFind(x[0])).length;
  const na = not("anthem"), no = not("organ"), n = na + no;
  const what = [na ? `${na} ${na === 1 ? "anthem" : "anthems"}` : "", no ? `${no} organ ${no === 1 ? "piece" : "pieces"}` : ""].filter(Boolean).join(" and ");
  return [n ? `<button class="small" onclick="libFromRecord()">Add the ${what} done here before</button>` : "",
    LIB.folders ? `<button class="small" onclick="libScan()">Look for new PDFs</button>`
    : (LIB.unfound || []).length ? `<p class="hint" style="margin:6px 0 0"><span class="warn">Score folder not found</span> on this computer: ${LIB.unfound.map(esc).join("; ")}. Fix "score folders:" in parish/library/library.txt to look for new PDFs here.</p>` : ""].filter(Boolean).join(" ");
}
function renderLibrary() {
  const nav = $('nav button[data-tab="library"]'); if (nav) nav.hidden = !LIB.rows.length && !SERVER;
  const el = $("#tab-library"); if (!el || el.hidden) return;
  if (!LIB.rows.length) {
    el.innerHTML = `<div class="card"><h3 style="font-weight:normal;margin:0 0 4px">Music library <span class="hint">· none yet</span></h3>
      <p class="hint" style="margin:0 0 8px">A list of the music you have, so the anthem boxes (and the prelude and postlude, for organ music) can suggest pieces for the season and say where the copies are. Start it from what's been done here, add pieces one at a time from those boxes in the Service planner, or put a spreadsheet at ${esc(LIB.where)}.</p>
      ${libTools()}${libScanCard()}</div>`;
    return;
  }
  const q = normT(LV.q), real = LIB.rows.filter(libReal);
  const hits = real.filter(r => (!LV.only || libFor(r) === LV.only) && (!q || normT(libPiece(r) + " " + r.Occasion + " " + r.Voicing + " " + r.Location + " " + (r.Tags || "") + " " + (SEASON_NAMES[r.Season] || "")).includes(q)))
    .sort(libCompare);
  const key = JSON.stringify([LV.q, LV.only, LV.levels]);
  if (key !== LV.key) { LV.key = key; LV.shown = 100; }   // a new search, filter or sort starts at the top again
  const more = hits.length - LV.shown;
  const where = hits.some(r => libWhere(r)), date = B.date && SERVER ? B.date : "", first = LV.levels[0];
  const cols = [["title", "Title"], ["composer", "Composer"], ["for", "For"], ["season", "Season"], ...(where ? [["where", "Where"]] : []), ["sung", "Sung"]];
  const th = ([f, label]) => `<th class="sortable${f === "where" ? " libwhere" : ""}${first.f === f ? " on" : ""}" title="sort by this; again for the other way round" onclick="libSortBy('${f}')">${label}${first.f === f ? (first.d > 0 ? " ▲" : " ▼") : ""}</th>`;
  const rows = hits.slice(0, LV.shown).map(r => {
    const sung = libSung(r), i = LIB.rows.indexOf(r), pdf = libPdf(r), fr = libFor(r);
    return `<tr><td>${pdf ? `<span class="link" title="open the PDF" onclick="libOpen(${i})">${esc(r.Title)}</span> <span class="hint">PDF</span>` : esc(r.Title)}
        ${date ? ` <span class="link hint" title="put it in the first empty ${fr === "organ" ? "prelude or postlude" : "anthem slot"} of the service for ${esc(date)}" onclick="libUse(${i})">+ service</span>` : ""}</td>
      <td>${esc(r.Composer)}${r.Years ? ` <span class="hint">(${esc(r.Years)})</span>` : ""}</td>
      <td class="nowrap"><span class="forlabel ${fr}" title="${esc(r.Voicing || (fr === "organ" ? "organ alone (guessed from the title: set the Voicing to be sure)" : "the choir"))}">${FOR_NAMES[fr]}</span></td>
      <td class="hint nowrap">${r.Season ? esc(SEASON_NAMES[r.Season] || r.Season) : "any time"}</td>${where ? `<td class="hint libwhere">${libWhere(r)}</td>` : ""}
      <td class="hint nowrap">${sung.length ? `${sung.length}×, last ${esc(sung[sung.length - 1])}` : "not yet"}</td></tr>`;
  }).join("");
  const tools = libTools(), nOrgan = real.filter(r => libFor(r) === "organ").length;
  const seg = (v, label) => `<button class="${LV.only === v ? "on" : ""}" onclick="LV.only='${v}'; renderLibrary()">${label}</button>`;
  el.innerHTML = `<div class="card">
    <div style="display:flex;gap:10px 28px;align-items:flex-start;flex-wrap:wrap;margin-bottom:8px">
      <div style="width:min(340px,100%)"><input type="search" id="libq" value="${esc(LV.q)}" placeholder="Find a title, composer, season, occasion…" oninput="LV.q=this.value; libRefresh()" style="width:100%;box-sizing:border-box">
        ${nOrgan ? `<div class="seg" style="max-width:340px;margin-top:6px">${seg("", "All")}${seg("choir", "Choir")}${seg("organ", "Organ")}</div>` : ""}
        <p class="hint" style="margin:6px 0 0">${hits.length === real.length ? real.length + " pieces" : hits.length + " of " + real.length + " pieces"}${Object.keys(LIB.pdfs || {}).length ? ` · ${Object.keys(LIB.pdfs).length} with a PDF on this computer` : ""}</p></div>
      ${libSortControl()}</div>
    ${tools ? `<p style="margin:0 0 8px">${tools}</p>` : ""}${libScanCard()}
    <div id="libtable">${rows ? `<table class="libtable"><tr>${cols.map(th).join("")}</tr>${rows}</table>` : '<p class="hint">Nothing matches.</p>'}</div>
    ${more > 0 ? `<p style="margin:8px 0 0"><span class="hint">Showing ${LV.shown} of ${hits.length}.</span> <button class="small" onclick="LV.shown+=100; renderLibrary()">Show next ${Math.min(100, more)}</button> <button class="small" onclick="LV.shown=Infinity; renderLibrary()">Show all</button></p>` : ""}
    <p class="hint" style="margin:8px 0 0">${date ? `“+ service” puts a piece in the first empty anthem slot (organ music: the prelude or postlude) of the service for ${esc(date)} in the Service planner. ` : ""}Organ or choir comes from a piece's Voicing (“organ” alone is organ); without one, it's guessed from the title. Kept in ${esc(LIB.where)}${LIB.rows.some(r => r.From) ? "; some pieces, seasons and organ music come from a plugin (change them where it reads them)" : ""}.</p></div>`;
}
function libRefresh() {
  const pos = $("#libq") ? $("#libq").selectionStart : null;
  renderLibrary();
  const q = $("#libq"); if (q) { q.focus(); if (pos !== null) q.setSelectionRange(pos, pos); }
}
function libUse(i) {
  const r = LIB.rows[i], v = libPiece(r), fam = libFam(r), mine = x => family(x) === fam;
  if (isSeq()) {
    const s = slotsOf(curOrder()).find(mine);
    B.seq.push([s ? s.key : "also", v]);
  } else {
    const s = slotsOf(curOrder()).filter(mine).find(x => !(B.svc[x.key] || "").trim());
    if (!s) { alert(`Every ${fam === "organ" ? "prelude and postlude" : "anthem slot"} of that service is filled: empty one first.`); return; }
    B.svc[s.key] = v;
  }
  $('nav button[data-tab="builder"]').click();
}
async function libFromRecord() {
  const j = await post("/api/library/from-record", {});
  if (!j.ok) { alert(j.error || "could not do it"); return; }
  LIB.rows = j.rows; libChanged(); renderLibrary();
}
async function libScan() {
  const j = await post("/api/library/scan", {});
  if (!j.ok) { alert(j.error || "could not look"); return; }
  B.libScan = j; renderLibrary();
}
function libScanCard() {
  const s = B.libScan; if (!s) return "";
  if (!s.new.length && !s.moved.length && !s.missing.length) return `<p class="hint">The score folders and the library agree: nothing new.</p>`;
  const opt = cur => `<option value="">any time</option>` + LIB.seasons.map(x => `<option value="${x}" ${x === cur ? "selected" : ""}>${esc(SEASON_NAMES[x] || x)}</option>`).join("");
  return `<div style="margin:10px 0"><b style="font-weight:normal">In the score folders:</b>
    ${s.new.length ? `<p class="hint" style="margin:4px 0">${s.new.length} new PDFs, read from their names: check them, then keep.</p>
      <table class="libtable"><tr><th></th><th>Composer</th><th>Title</th><th>Season</th><th>File</th></tr>${s.new.map((r, i) => `<tr>
        <td><input type="checkbox" id="lk-${i}" checked></td><td><input type="text" id="lkc-${i}" value="${esc(r.Composer)}"></td>
        <td><input type="text" id="lkt-${i}" value="${esc(r.Title)}"></td><td><select id="lks-${i}">${opt(r.Season)}</select></td><td class="hint">${esc(r.File)}${r.Matches ? `<br>the PDF of ${esc(r.Matches)}, already in the library` : ""}</td></tr>`).join("")}</table>` : ""}
    ${s.moved.length ? `<p class="hint" style="margin:4px 0">Moved (the library will follow): ${s.moved.map(([a, b]) => esc(a) + " → " + esc(b)).join("; ")}</p>` : ""}
    ${s.missing.length ? `<p class="hint" style="margin:4px 0"><span class="warn">Not found</span> (left in the library): ${s.missing.map(esc).join("; ")}</p>` : ""}
    ${s.new.length || s.moved.length ? `<button class="small primary" onclick="libKeep()">Keep these</button>` : ""} <button class="small" onclick="B.libScan=null; renderLibrary()">Close</button></div>`;
}
async function libKeep() {
  const s = B.libScan;
  const rows = s.new.map((r, i) => ($("#lk-" + i) || {}).checked ? Object.assign({}, r, {Composer: $("#lkc-" + i).value.trim(), Title: $("#lkt-" + i).value.trim(), Season: $("#lks-" + i).value}) : null).filter(Boolean);
  const j = await post("/api/library/keep", {rows, moved: s.moved});
  if (!j.ok) { alert(j.error || "could not keep them"); return; }
  LIB.rows = j.rows; B.libScan = null; libChanged(); renderLibrary();
}


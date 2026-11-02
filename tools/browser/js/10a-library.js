// ---------- the music library (parish/library/catalog.csv; tools/library.py) ----------
// Optional: with no library the planner works as before. Pieces are suggested for the day (its occasion, then its
// season, then any time), and can be added from the anthem box, from what's been sung, or from the score folders.
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
  LIBX = {rows: LIB.rows, n: LIB.rows.length, byTitle, found: new Map(), sung: null, options: {}};
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
function libSung(r) {
  const X = libIndex();
  if (!X.sung) {
    X.sung = new Map();
    for (const x of REP.anthem || []) { const hit = libFind(x[0]); if (hit && !X.sung.has(hit)) X.sung.set(hit, x[1]); }
  }
  return (X.sung.get(r) || []).filter(d => d < (B.date || "9999"));
}
function libWhere(r) {
  const bits = [r.Format, r.Location, r.Copies ? r.Copies + " copies" : "", r["Publisher no."] ? "order no. " + r["Publisher no."] : "", r.Voicing];
  return bits.filter(Boolean).map(esc).join(" · ");
}
// the anthem box's suggestions: the library for this day first, then everything sung before that isn't in it
function anthemOptions() {
  const X = libIndex(), key = B.date || "";
  if (X.options[key] !== undefined) return X.options[key];
  const rows = LIB.rows.filter(libReal).map(r => [libRank(r), r]).sort((a, b) => a[0] - b[0] || normT(a[1].Title).localeCompare(normT(b[1].Title)));
  const lib = rows.map(([k, r]) => {
    const sung = libSung(r), when = k === 0 ? "for this day" : r.Season ? SEASON_NAMES[r.Season] || r.Season : "any time";
    return `<option value="${esc(libPiece(r))}">${esc(when)}${r.Format ? " · " + esc(r.Format) : ""}${sung.length ? ` · ${sung.length}× · last ${esc(sung[sung.length - 1])}` : " · not sung here yet"}</option>`;
  });
  const rest = (REP.anthem || []).filter(x => !libFind(x[0])).map(r => `<option value="${esc(r[0])}">${r[1].length}× · last ${esc(r[1][r[1].length - 1])}</option>`);
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
const libReal = r => !!String(r.Title || "").replace(/[\s?.\-–—]/g, "");     // not a "???" placeholder
async function libOpen(i) {
  const j = await post("/api/score", {file: libPdf(LIB.rows[i])});
  if (!j.ok) alert(j.error || "could not open it");
}
// "Add to the library", under an anthem that isn't in it
const LIBV = {};
function libAddBox(id, v) {
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
      <label>Voicing <input type="text" id="lv-${id}" placeholder="SATB, organ"></label>
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
// the library card, under the rest of the service
function libraryCard() {
  if (!ORDER_NAMES.length || (!LIB.rows.length && !SERVER)) return "";
  const notIn = (REP.anthem || []).filter(x => libReal({Title: x[0]}) && !hymnsOf(x[0]).length && !libFind(x[0])).length;
  const tools = SERVER ? [notIn ? `<button class="small" onclick="libFromRecord()">Add the ${notIn} ${notIn === 1 ? "anthem" : "anthems"} sung here before</button>` : "",
    LIB.folders ? `<button class="small" onclick="libScan()">Look for new PDFs</button>`
    : (LIB.unfound || []).length ? `<p class="hint" style="margin:6px 0 0"><span class="warn">Score folder not found</span> on this computer: ${LIB.unfound.map(esc).join("; ")}. Fix "score folders:" in parish/library/library.txt to look for new PDFs here.</p>` : ""].filter(Boolean).join(" ") : "";
  if (!LIB.rows.length) {
    return `<div class="card"><h3 style="font-weight:normal;margin:0 0 4px">Music library <span class="hint">· none yet</span></h3>
      <p class="hint" style="margin:0 0 8px">A list of the music you have, so the anthem boxes can suggest pieces for the season and say where the copies are. Start it from what's been sung, add pieces one at a time from an anthem box, or put a spreadsheet at ${esc(LIB.where)}.</p>
      ${tools}${libScanCard()}</div>`;
  }
  const q = normT(B.libQ || ""), season = daySeason();
  const hits = LIB.rows.filter(libReal).filter(r => q ? normT(libPiece(r) + " " + r.Occasion + " " + r.Voicing + " " + r.Location).includes(q) : libRank(r) < 3)
    .sort((a, b) => libRank(a) - libRank(b) || normT(a.Title).localeCompare(normT(b.Title)));
  const shown = hits.slice(0, 60);
  const where = shown.some(r => libWhere(r));                // (a Where column only when something says where)
  const rows = shown.map(r => {
    const sung = libSung(r), i = LIB.rows.indexOf(r);
    return `<tr><td><span class="link" title="use it in this service" onclick="libUse(${i})">${esc(r.Title)}</span>${libPdf(r) ? ` <span class="link hint" title="open the PDF" onclick="libOpen(${i})">PDF</span>` : ""}</td>
      <td>${esc(r.Composer)}${r.Years ? ` <span class="hint">(${esc(r.Years)})</span>` : ""}</td>
      <td class="hint nowrap">${r.Season ? esc(SEASON_NAMES[r.Season] || r.Season) : "any time"}${libRank(r) === 0 ? " · this day" : ""}</td>${where ? `<td class="hint libwhere">${libWhere(r)}</td>` : ""}
      <td class="hint nowrap">${sung.length ? `${sung.length}×, last ${esc(sung[sung.length - 1])}` : "not yet"}</td></tr>`;
  }).join("");
  const forNow = LIB.rows.filter(r => libReal(r) && libRank(r) < 2).length, real = LIB.rows.filter(libReal).length;
  return `<details class="card" ${B.libOpen ? "open" : ""} ontoggle="B.libOpen=this.open"><summary style="color:var(--ink)">Music library <span class="hint">· ${real} pieces${season ? `, ${forNow} for ${esc(SEASON_NAMES[season] || season)}` : ""}</span></summary>
    <p style="margin:8px 0"><input type="search" id="libq" value="${esc(B.libQ || "")}" placeholder="Find a title, composer, occasion…" oninput="B.libQ=this.value; libRefresh()" style="width:min(360px,100%)">
      <span class="hint">${q ? "" : "this day, this season and any time; type to look through everything"}</span></p>
    <div id="libtable">${rows ? `<table class="libtable"><tr><th>Title</th><th>Composer</th><th>Season</th>${where ? '<th class="libwhere">Where</th>' : ""}<th>Sung</th></tr>${rows}</table>${hits.length > shown.length ? `<p class="hint">and ${hits.length - shown.length} more: type to narrow them down</p>` : ""}` : '<p class="hint">Nothing matches.</p>'}</div>
    <p class="hint" style="margin:8px 0 0">Click a piece to put it in the first empty anthem slot. Kept in ${esc(LIB.where)}.</p>
    ${tools ? `<p style="margin:8px 0 0">${tools}</p>` : ""}${libScanCard()}</details>`;
}
function libRefresh() {
  const pos = $("#libq") ? $("#libq").selectionStart : null;
  renderBuilder();
  const q = $("#libq"); if (q) { q.focus(); if (pos !== null) q.setSelectionRange(pos, pos); }
}
function libUse(i) {
  const v = libPiece(LIB.rows[i]);
  if (isSeq()) {
    const s = slotsOf(curOrder()).find(x => x.kind === "anthem");
    B.seq.push([s ? s.key : "also", v]); renderBuilder(); return;
  }
  const s = slotsOf(curOrder()).filter(x => x.kind === "anthem").find(x => !(B.svc[x.key] || "").trim());
  if (!s) { alert("Every anthem slot is filled: empty one first."); return; }
  B.svc[s.key] = v; renderBuilder();
}
async function libFromRecord() {
  const j = await post("/api/library/from-record", {});
  if (!j.ok) { alert(j.error || "could not do it"); return; }
  LIB.rows = j.rows; B.libOpen = true; libChanged(); renderBuilder();
}
async function libScan() {
  const j = await post("/api/library/scan", {});
  if (!j.ok) { alert(j.error || "could not look"); return; }
  B.libScan = j; B.libOpen = true; renderBuilder();
}
function libScanCard() {
  const s = B.libScan; if (!s) return "";
  if (!s.new.length && !s.moved.length && !s.missing.length) return `<p class="hint">The score folders and the library agree: nothing new.</p>`;
  const opt = cur => `<option value="">any time</option>` + LIB.seasons.map(x => `<option value="${x}" ${x === cur ? "selected" : ""}>${esc(SEASON_NAMES[x] || x)}</option>`).join("");
  return `<div style="margin-top:10px"><b style="font-weight:normal">In the score folders:</b>
    ${s.new.length ? `<p class="hint" style="margin:4px 0">${s.new.length} new PDFs, read from their names: check them, then keep.</p>
      <table class="libtable"><tr><th></th><th>Composer</th><th>Title</th><th>Season</th><th>File</th></tr>${s.new.map((r, i) => `<tr>
        <td><input type="checkbox" id="lk-${i}" checked></td><td><input type="text" id="lkc-${i}" value="${esc(r.Composer)}"></td>
        <td><input type="text" id="lkt-${i}" value="${esc(r.Title)}"></td><td><select id="lks-${i}">${opt(r.Season)}</select></td><td class="hint">${esc(r.File)}${r.Matches ? `<br>the PDF of ${esc(r.Matches)}, already in the library` : ""}</td></tr>`).join("")}</table>` : ""}
    ${s.moved.length ? `<p class="hint" style="margin:4px 0">Moved (the library will follow): ${s.moved.map(([a, b]) => esc(a) + " → " + esc(b)).join("; ")}</p>` : ""}
    ${s.missing.length ? `<p class="hint" style="margin:4px 0"><span class="warn">Not found</span> (left in the library): ${s.missing.map(esc).join("; ")}</p>` : ""}
    ${s.new.length || s.moved.length ? `<button class="small primary" onclick="libKeep()">Keep these</button>` : ""} <button class="small" onclick="B.libScan=null; renderBuilder()">Close</button></div>`;
}
async function libKeep() {
  const s = B.libScan;
  const rows = s.new.map((r, i) => ($("#lk-" + i) || {}).checked ? Object.assign({}, r, {Composer: $("#lkc-" + i).value.trim(), Title: $("#lkt-" + i).value.trim(), Season: $("#lks-" + i).value}) : null).filter(Boolean);
  const j = await post("/api/library/keep", {rows, moved: s.moved});
  if (!j.ok) { alert(j.error || "could not keep them"); return; }
  LIB.rows = j.rows; B.libScan = null; libChanged(); renderBuilder();
}
PLUGINS.cards.unshift(libraryCard);

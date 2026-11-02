// ---------- the rest of the service ----------
const SV = D.service || {orders: {}, hymnals: {}, repertoire: {}, hymnHistory: {}, anthems: [], byDate: {}, plugins: {}, pluginKeys: []};
// what a parish's plugins (parish/plugins/, see tools/plugins.py) add to the Service planner
const PLUGINS = {cards: [], rows: [], changed: [], reset: []};
const PLUGIN_KEYS = new Set(SV.pluginKeys || []);
const REP = SV.repertoire || {};
const ORDER_NAMES = Object.keys(SV.orders);
const SVC_KEYS = new Set(["organist"].concat(...Object.values(SV.orders).map(o => o.map(s => s.key))));
const SVC_ALIAS = {"gloria-in-excelsis": "gloria in excelsis", "lamb of god": "agnus dei", "agnus": "agnus dei", "sanctus & benedictus": "sanctus",
  "opening hymn": "opening", "closing hymn": "closing", "gradual hymn": "gradual", "offertory hymn": "offertory", "offertory anthem": "offertory",
  "communion anthem": "communion", "communion hymn": "communion"};
const BOOKS = {EH1982: "EH1982", H82: "EH1982", EH: "EH1982", HYMNAL1982: "EH1982", LEVAS: "LEVAS", LEVAS2: "LEVAS", LEVASII: "LEVAS", WLP: "WLP", EH1940: "EH1940", EH1928: "EH1928"};
function orderFor(service, label) {
  const first = ORDER_NAMES[0];
  for (const want of [service && service !== "Eucharist" ? service : "", label || ""]) {
    if (!want) continue;
    const exact = ORDER_NAMES.find(n => n.toLowerCase() === want.toLowerCase()); if (exact) return exact;
    const part = ORDER_NAMES.find(n => n !== first && want.toLowerCase().includes(n.toLowerCase())); if (part) return part;
    const words = new Set(want.toLowerCase().match(/[a-z]+/g) || []);      // "Easter Vigil" for "The Great Vigil of Easter"
    const all = ORDER_NAMES.find(n => n !== first && (n.toLowerCase().match(/[a-z]+/g) || []).every(w => words.has(w))); if (all) return all;
  }
  return first;
}
const curOrder = () => orderFor(B.service, B.label);
const slotsOf = o => SV.orders[o] || SV.orders[ORDER_NAMES[0]] || [];
const anySlot = k => slotsOf(curOrder()).find(s => s.key === k) || Object.values(SV.orders).flat().find(s => s.key === k);
function hymnOf(v) {
  const m = String(v || "").trim().match(/^(?:((?!S\s?\d)[A-Za-z][A-Za-z0-9]*)\s+)?(S\s?\d{1,3}|\d{1,3}[a-z]?)\.?(?:\s*\(([A-Za-z][A-Za-z0-9]*)\))?(?:\s+(.+))?$/);
  if (!m || (m[4] && m[4].includes(" - "))) return null;
  const b = (m[1] || m[3] || "EH1982").toUpperCase(); if (!BOOKS[b]) return null;
  const book = BOOKS[b], number = m[2].replace(" ", "");
  return {book, number, title: (m[4] || "").trim() || (SV.hymnals[book] || {})[number] || "", service: number.startsWith("S")};
}
function hymnsOf(v) {
  v = String(v || "").trim(); if (!v) return [];
  const parts = v.split(/\s*[;,]\s*/).filter(Boolean);
  if (parts.length > 1) { const hs = parts.map(hymnOf); if (hs.every(Boolean)) return hs; }
  const h = hymnOf(v); return h ? [h] : [];
}
const normT = s => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
function splitPiece(v) { const i = String(v).lastIndexOf(" - "); return i < 0 ? [String(v).trim(), ""] : [v.slice(0, i).trim(), v.slice(i + 3).trim()]; }
function findAnthem(v) {
  const [t, comp] = splitPiece(v);
  const hits = SV.anthems.filter(a => normT(a.title) === normT(t));
  const sur = x => (x.replace(/\(.*?\)/g, "").trim().split(/\s+/).pop() || "").toLowerCase();
  return (hits.length > 1 && comp ? hits.find(a => sur(a.composer) === sur(comp)) : null) || hits[0] || null;
}
const family = s => s.kind === "anthem" ? "anthem" : (s.key === "prelude" || s.key === "postlude") ? "organ" : s.key;
const sid = k => k.replace(/[^a-z0-9]/gi, "_");
const isSeq = () => slotsOf(curOrder()).some(s => s.repeat);
function svcLines() {
  const L = [], done = new Set(["organist"]);
  const pad = k => (k + ":").padEnd(Math.max(11, k.length + 2));
  if ((B.svc.organist || "").trim()) L.push(pad("organist") + B.svc.organist.trim());
  if (isSeq()) {                              // a service in a free order (Lessons and Carols): the list as it stands
    (B.seq || []).forEach(([k, v]) => { if ((v || "").trim()) L.push(pad(k) + v.trim()); });
    Object.entries(B.extra || {}).forEach(([k, v]) => (v || "").split("\n").map(x => x.trim()).filter(Boolean).forEach(x => L.push(pad(k) + x)));
    B.note.split("\n").map(x => x.trim()).filter(Boolean).forEach(x => L.push(pad("note") + x));
    return L;
  }
  slotsOf(curOrder()).forEach(s => { done.add(s.key); const v = (B.svc[s.key] || "").trim(); if (v) L.push(pad(s.key) + v); });
  Object.keys(B.svc).forEach(k => { const v = (B.svc[k] || "").trim(); if (!done.has(k) && v) L.push(pad(k) + v); });
  B.also.split("\n").map(x => x.trim()).filter(Boolean).forEach(x => L.push(pad("also") + x));
  Object.entries(B.extra || {}).forEach(([k, v]) => (v || "").split("\n").map(x => x.trim()).filter(Boolean).forEach(x => L.push(pad(k) + x)));
  B.note.split("\n").map(x => x.trim()).filter(Boolean).forEach(x => L.push(pad("note") + x));
  return L;
}
// the service on record for this file (its name), or the first on this date
function serviceOn(date) {
  const e = SV.byDate[B.name];
  return e && e.date === date ? e : SV.byDate[date] || Object.values(SV.byDate).find(x => x.date === date) || null;
}
function prefillService(date) {
  B.svc = {}; B.also = ""; B.note = ""; B.extra = {}; B.showOpt = new Set(); B.seq = [];
  const e = serviceOn(date);
  if (e && e.order !== ORDER_NAMES[0]) B.service = e.order;
  if (e) e.items.forEach(([k, v]) => {
    if (PLUGIN_KEYS.has(k)) B.extra[k] = (B.extra[k] ? B.extra[k] + "\n" : "") + v; else if (k === "note") B.note += (B.note ? "\n" : "") + v;
    else { if (k === "also") B.also += (B.also ? "\n" : "") + v; else B.svc[k] = v; if (k !== "organist") B.seq.push([k, v]); }
  });
  carryService();
}
function carryService() {
  const prev = previousService(B.date, curOrder());
  slotsOf(curOrder()).forEach(s => { if (s.kind === "service" && !B.svc[s.key] && prev.svc[s.key]) B.svc[s.key] = prev.svc[s.key]; });
  if (!B.svc.organist && prev.svc.organist) B.svc.organist = prev.svc.organist;
}
function previousService(date, order) {
  const keys = slotsOf(order).filter(s => s.kind === "service").map(s => s.key);
  const d = Object.keys(SV.byDate).filter(x => x < date && SV.byDate[x].order === order && SV.byDate[x].items.some(([k]) => keys.includes(k))).sort().pop();
  const svc = {}; if (d) SV.byDate[d].items.forEach(([k, v]) => svc[k] = v);
  return {date: d || "", svc};
}
function slotHint(s, value) {
  const v = (value !== undefined ? value : (B.svc[s.key] || "")).trim(); if (!v) return "";
  const hs = s.kind === "music" ? [] : hymnsOf(v);
  if (hs.length && !hs.every(h => h.service)) {
    return hs.map(h => {
      const sung = (SV.hymnHistory[h.book + " " + h.number] || []).filter(d => d < B.date).sort().reverse();
      return `${hs.length > 1 ? esc(h.number) + ". " : ""}${h.title ? esc(h.title) : '<span class="warn">not in the ' + esc(h.book) + ' index: add the title after the number</span>'} <span class="hint">(${esc(h.book)})${sung.length ? " · sung " + sung.length + "×, last " + esc(sung[0]) : " · not sung here before"}</span>`;
    }).join("<br>");
  }
  if (hs.length) {
    const prev = previousService(B.date, curOrder());
    const pv = prev.svc[s.key];
    return `<span class="hint">${hs.length === 1 && hs[0].title ? esc(hs[0].title) + " · " : ""}${pv && pv !== v ? "a change from " + esc(pv) + " (" + esc(prev.date) + ")" : pv ? "same as last time" : "carries on to the next " + esc(curOrder())}</span>`;
  }
  const r = (REP[family(s)] || []).find(x => x[0] === v);
  const before = r ? r[1].filter(d => d < B.date) : [];
  return `<span class="hint">${before.length ? `done ${before.length}× before · last ${esc(before[before.length - 1])}` : "not done here before"}</span>${s.kind === "anthem" ? libHint(v) : ""}`;
}
function anthemBox(k) {
  const v = (B.svc[k] || "").trim();
  if (!v || hymnsOf(v).length) return "";
  const a = findAnthem(v), t = splitPiece(v)[0], id = sid(k);
  return `<details ${a ? "" : "open"} style="margin:4px 0 8px"><summary class="hint">${a ? "Words" + (a.source ? " (" + esc(a.source) + ")" : "") + ": on file" : "No words on file for this piece yet: paste them here (or leave empty)"}</summary>
    <input type="text" id="asrc-${id}" value="${esc(a ? a.source : "")}" placeholder="Where the words come from (optional), e.g. John 3:16" style="width:100%;margin:6px 0">
    <textarea id="atxt-${id}" style="width:100%;height:${a ? Math.min(24, a.text.split("\n").length + 1) * 1.45 : 8}em;font-family:inherit;font-size:15px;line-height:1.45">${esc(a ? a.text : "")}</textarea>
    ${SERVER ? `<button class="small" onclick="saveAnthem('${k}')">Save the words</button> <span class="hint">kept in parish/anthems/, used whenever ${esc(t)} comes round again</span>` : ""}</details>${libAddBox(id, v)}`;
}
async function saveAnthem(k) {
  const id = sid(k), [title, composer] = splitPiece(B.svc[k]);
  const source = $("#asrc-" + id).value.trim(), text = $("#atxt-" + id).value;
  const j = await post("/api/anthem", {title, composer, source, text});
  if (!j.ok) { alert(j.error || "could not save"); return; }
  const a = findAnthem(B.svc[k]);
  if (a) Object.assign(a, {source, text}); else SV.anthems.push({title, composer, source, text});
  refreshSlot(k);
}
function wordsHint(s) {
  const a = SV.anthems.find(x => x.file === s.words) || SV.anthems.find(x => normT(x.title) === normT(s.words));
  return `<div class="hint">${a ? "Words: " + esc(a.title) + (a.source ? " (" + esc(a.source) + ")" : "") : '<span class="warn">no words on file: add parish/anthems/' + esc(s.words) + '.txt</span>'}</div>`;
}
// what was sung on this day of the lectionary before: the same readings (three years ago, six…) first
function beforeCard() {
  const me = (SV.lect || {})[B.date]; if (!me) return "";
  const L = k => SV.lect[SV.byDate[k].date] || [];       // services are named by file or date: the day is by date
  const prior = Object.keys(SV.byDate).filter(k => SV.byDate[k].date < B.date && L(k)[0] === me[0]).sort().reverse();
  if (!prior.length) return "";
  const same = prior.filter(k => L(k)[1] === me[1]), other = prior.filter(k => L(k)[1] !== me[1]);
  const one = (d, open) => {
    const e = SV.byDate[d], items = e.items.filter(([k]) => !["organist", "note"].includes(k) && !PLUGIN_KEYS.has(k));
    return `<details ${open ? "open" : ""} style="margin:4px 0"><summary>${esc(d)} <span class="hint">· ${esc(L(d)[2])}, Year ${esc(L(d)[1])}${e.order !== ORDER_NAMES[0] ? " · " + esc(e.order) : ""}</span></summary>
      <ul style="margin:4px 0 2px 1.1em;padding:0">${(e.psalms || []).map(ps => `<li><span class="hint">Psalm:</span> ${esc(ps.replace(/\s*\(\)$/, ""))}</li>`).join("")}${items.map(([k, v]) => `<li>${itemText(e.order, k, v)}</li>`).join("")}</ul></details>`;
  };
  const lastSame = same[0] ? SV.byDate[same[0]] : null;
  return `<details class="card" ${B.beforeOpen ? "open" : ""} ontoggle="B.beforeOpen=this.open"><summary style="color:var(--ink)">Before on ${lectLink(me[2], me[3])} <span class="hint">· ${same.length ? "last with these readings " + esc(same[0]) + ((lastSame.psalms || [])[0] ? ": " + esc(lastSame.psalms[0]) : "") : "not with these readings yet"}${prior.length > 1 ? ` · ${prior.length} times in all` : ""}</span></summary>
    ${same.length ? `<div class="hint">With these readings (Year ${esc(me[1])}):</div>${same.map((d, i) => one(d, i === 0)).join("")}` : `<p class="hint" style="margin:0">Not with these readings (Year ${esc(me[1])}) since the record began.</p>`}
    ${other.length ? `<div class="hint" style="margin-top:6px">The same day in other years:</div>${other.map(d => one(d, false)).join("")}` : ""}</details>`;
}
// a service in a free order: rows to add, change, move and remove
function seqCard() {
  const order = curOrder(), sl = slotsOf(order);
  const prev = Object.keys(SV.byDate).filter(d => d < (B.date || "9999") && SV.byDate[d].order === order).sort().pop();
  let n = 0;
  const rows = (B.seq || []).map(([k, v], i) => {
    const s = sl.find(x => x.key === k) || (k === "also" ? {key: "also", label: "Other", kind: "music"} : anySlot(k) || {key: k, label: k, kind: "music"});
    if (s.kind === "lesson") n++;
    const opts = sl.map(x => `<option value="${esc(x.key)}" ${x.key === k ? "selected" : ""}>${esc(x.label.replace(/\s*\{hymn\|anthem\}/, ""))}</option>`).join("") + `<option value="also" ${k === "also" ? "selected" : ""}>Other (as written)</option>`;
    const list = s.kind === "lesson" ? "rep-lesson" : s.kind === "hymn" ? "" : "rep-" + sid(family(s));
    const ph = {lesson: "e.g. Isaiah 40:1-11 (the summary comes from earlier years) or Isaiah 40:1-11 | summary", hymn: "hymn number, e.g. 102", anthem: "Title - Composer (dates), or a hymn number", music: "Title - Composer (dates)"}[s.kind] || "";
    const hint = s.kind === "lesson" ? lessonHint(v, n) : slotHint(s, v);
    return `<div class="seqrow"><select onchange="B.seq[${i}][0]=this.value; renderBuilder()">${opts}</select>
      <div><input type="text" value="${esc(v)}" ${list ? `list="${list}"` : ""} placeholder="${esc(ph)}" onchange="B.seq[${i}][1]=this.value.trim(); renderBuilder()" style="width:100%">
        <div class="svhint">${hint}</div>${s.kind === "anthem" ? seqAnthemBox(i) : ""}</div>
      <div class="seqbtn"><span class="link" title="move up" onclick="seqMove(${i},-1)">↑</span> <span class="link" title="move down" onclick="seqMove(${i},1)">↓</span> <span class="link" title="remove" onclick="B.seq.splice(${i},1); renderBuilder()">✕</span></div></div>`;
  }).join("");
  const adds = sl.filter(x => x.repeat || !(B.seq || []).some(([k]) => k === x.key));
  return `<div class="card"><h3 style="font-weight:normal;margin:0 0 4px">The service <span class="hint">· ${esc(order)}, in the order it happens</span></h3>
    <p class="hint" style="margin:0 0 8px">Add lessons, hymns and pieces in any order; ↑ ↓ move them. Lessons are numbered for you (The First Lesson…).${prev ? ` <span class="link" onclick="copySeq('${prev}')">Start from ${esc(prev)}'s order</span>` : ""}</p>
    <div class="svrow"><label>Organist</label><div><input type="text" value="${esc(B.svc.organist || "")}" onchange="setSvc('organist', this.value)" style="width:120px"></div></div>
    ${rows || '<p class="hint">Nothing yet.</p>'}
    <p style="margin:8px 0" class="hint">add: ${adds.map(x => `<span class="link" onclick="B.seq.push(['${x.key}','']); renderBuilder()">${esc(x.label.replace(/\s*\{hymn\|anthem\}/, ""))}</span>`).join(" · ")} · <span class="link" onclick="B.seq.push(['also','']); renderBuilder()">other</span></p>
    <div class="svrow"><label>Note</label><div><textarea rows="2" style="width:100%" onchange="B.note=this.value; refreshFile()">${esc(B.note)}</textarea></div></div>
    ${PLUGINS.rows.map(f => f()).join("")}
    <datalist id="rep-lesson">${(SV.lessons || []).map(l => `<option value="${esc(l.reading)}">${esc(l.summary)}</option>`).join("")}</datalist>
  </div>`;
}
function seqMove(i, d) { const j = i + d; if (j < 0 || j >= B.seq.length) return; [B.seq[i], B.seq[j]] = [B.seq[j], B.seq[i]]; renderBuilder(); }
function copySeq(d) {
  if (B.seq.length && !confirm("Replace this list with " + d + "'s?")) return;
  B.seq = SV.byDate[d].items.filter(([k]) => !["organist", "note"].includes(k) && !PLUGIN_KEYS.has(k)).map(([k, v]) => [k, v]); renderBuilder();
}
const ORD = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth"];
function lessonKey(ref) { const m = String(ref).replace(/–/g, "-").match(/^\s*((?:\d\s*)?[A-Za-z]+)\s*(\d+)\s*:\s*(\d+)/); return m ? `${m[1].toLowerCase().replace(/ /g, "")} ${m[2]}:${m[3]}` : String(ref).trim().toLowerCase(); }
function lessonHint(v, n) {
  if (!(v || "").trim()) return "";
  let [ref, summary] = v.split("|").map(x => x.trim());
  if (!summary) { const hit = (SV.lessons || []).find(l => lessonKey(l.reading) === lessonKey(ref)); summary = hit ? hit.summary : ""; }
  return `<span class="hint">The ${ORD[n - 1] || n + "th"} Lesson: ${esc(ref)}${summary ? " (" + esc(summary) + ")" : ' · <span class="warn">no summary yet: add one after a |</span>'}</span>`;
}
function seqAnthemBox(i) {
  const v = (B.seq[i][1] || "").trim(); if (!v || hymnsOf(v).length) return "";
  const a = findAnthem(v);
  const [t] = splitPiece(v), id = "seq" + i;
  return `<details style="margin:4px 0 8px"><summary class="hint">${a ? "Words" + (a.source ? " (" + esc(a.source) + ")" : "") + ": on file" : "No words on file yet: paste them here"}</summary>
    <input type="text" id="asrc-${id}" value="${esc(a ? a.source : "")}" placeholder="Where the words come from (optional)" style="width:100%;margin:6px 0">
    <textarea id="atxt-${id}" style="width:100%;height:${a ? Math.min(24, a.text.split("\n").length + 1) * 1.45 : 8}em;font-family:inherit;font-size:15px;line-height:1.45">${esc(a ? a.text : "")}</textarea>
    ${SERVER ? `<button class="small" onclick="saveSeqAnthem(${i})">Save the words</button>` : ""}</details>${libAddBox(id, v)}`;
}
async function saveSeqAnthem(i) {
  const [title, composer] = splitPiece(B.seq[i][1]), id = "seq" + i;
  const source = $("#asrc-" + id).value.trim(), text = $("#atxt-" + id).value;
  const j = await post("/api/anthem", {title, composer, source, text});
  if (!j.ok) { alert(j.error || "could not save"); return; }
  const a = findAnthem(B.seq[i][1]);
  if (a) Object.assign(a, {source, text}); else SV.anthems.push({title, composer, source, text});
  renderBuilder();
}
function serviceCard() {
  if (!ORDER_NAMES.length) return "";
  if (isSeq()) return seqCard();
  const order = curOrder(), sl = slotsOf(order), prev = previousService(B.date, order);
  const shown = sl.filter(s => !s.optional || B.svc[s.key] || B.showOpt.has(s.key));
  const hidden = sl.filter(s => !shown.includes(s));
  const others = Object.keys(B.svc).filter(k => k !== "organist" && !sl.some(s => s.key === k) && (B.svc[k] || "").trim());
  const row = s => {
    const list = s.kind === "hymn" || s.kind === "service" ? "" : "rep-" + sid(family(s));
    const ph = {hymn: "hymn number(s), e.g. 390 or LEVAS 114", anthem: "hymn number, or Title - Composer (dates)", music: "Title - Composer (dates)", service: "e.g. S278"}[s.kind];
    return `<div class="svrow"><label>${esc(s.label.replace("{hymn|anthem}", "hymn or anthem"))}</label>
      <div><input type="text" value="${esc(B.svc[s.key] || "")}" ${list ? `list="${list}"` : ""} placeholder="${ph}" onchange="setSvc('${s.key}', this.value)" style="width:100%">
      <div id="sh-${sid(s.key)}" class="svhint">${slotHint(s)}</div>
      <div id="ab-${sid(s.key)}">${s.kind === "anthem" ? anthemBox(s.key) : ""}${s.words ? wordsHint(s) : ""}</div></div></div>`;
  };
  return `${beforeCard()}<div class="card"><h3 style="font-weight:normal;margin:0 0 4px">The rest of the service <span class="hint">· ${esc(order)}</span>${info((serviceOn(B.date) ? "Already planned for this date (the imported record or this Sunday's file). " : "") + "Service music carries on from the last service of this kind unless you change it. The order of service comes from the Service box (or the day), and is set out in services.txt.")}</h3>
    
    <div class="svrow"><label>Organist</label><div><input type="text" value="${esc(B.svc.organist || "")}" onchange="setSvc('organist', this.value)" style="width:120px"></div></div>
    ${shown.map(row).join("")}
    ${others.map(k => row({key: k, label: k + " (not in this order)", kind: (anySlot(k) || {}).kind || "music"})).join("")}
    ${hidden.length ? `<div class="svrow"><label></label><div class="hint">add: ${hidden.map(s => `<span class="link" onclick="B.showOpt.add('${s.key}'); renderBuilder()">${esc(s.label.replace(/\s*\{hymn\|anthem\}/, ""))}</span>`).join(" · ")}</div></div>` : ""}
    <div class="svrow"><label>Other items</label><div><textarea rows="2" style="width:100%" placeholder="One per line, as written, e.g. Te Deum: Collegium Regale - Herbert Howells (1892-1983)" onchange="B.also=this.value; refreshFile()">${esc(B.also)}</textarea></div></div>
    <div class="svrow"><label>Note</label><div><textarea rows="2" style="width:100%" placeholder="Anything else worth writing down about this service" onchange="B.note=this.value; refreshFile()">${esc(B.note)}</textarea></div></div>
    ${PLUGINS.rows.map(f => f()).join("")}
  </div>`;
}
function repLists() {
  const fams = [...new Set(Object.keys(REP).concat("anthem"))];       // anthems: the library first (10a-library.js)
  return fams.map(f => `<datalist id="rep-${sid(f)}">${f === "anthem" ? anthemOptions() : REP[f].map(r => `<option value="${esc(r[0])}">${r[1].length}× · last ${esc(r[1][r[1].length - 1])}</option>`).join("")}</datalist>`).join("");
}
function setSvc(k, v) {
  B.svc[k] = v.trim(); refreshSlot(k);
  // the Nunc dimittis usually follows the Magnificat's setting
  const m = B.svc[k].match(/^Magnificat\b(.*)$/i);
  if (k === "magnificat" && m && !(B.svc["nunc dimittis"] || "").trim() && slotsOf(curOrder()).some(x => x.key === "nunc dimittis")) {
    B.svc["nunc dimittis"] = "Nunc dimittis" + m[1]; renderBuilder();
  }
}
function refreshSlot(k) {
  const s = anySlot(k);
  if (s) { const h = $("#sh-" + sid(k)); if (h) h.innerHTML = slotHint(s); const ab = $("#ab-" + sid(k)); if (ab && s.kind === "anthem") ab.innerHTML = anthemBox(k); }
  refreshFile();
}
function refreshFile() { const pre = $("#bfile"); if (pre) pre.textContent = sundayText(); PLUGINS.changed.forEach(f => f()); }

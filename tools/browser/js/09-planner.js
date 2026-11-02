// ---------- Service planner (psalm builder + the rest of the service) ----------
const SERVICES = [...new Set(Object.keys((D.service || {}).orders || {}).concat(["Eucharist", "Evensong", "Office", "Morning Prayer", "Evening Prayer"]))];
const B = {music: {}, date: "", name: "", label: "", year: "", service: "Eucharist", gloria: "auto", reprint: true, sung: false,
           psalms: [{spec: "", chants: [{name: "", from: ""}]}], status: "", log: "", files: [], existing: null,
           svc: {}, also: "", note: "", extra: {}, showOpt: new Set(), mode: (() => { try { return localStorage.getItem("psalter-mode") || "service"; } catch (e) { return "service"; } })()};
function setMode(m) { B.mode = m; try { localStorage.setItem("psalter-mode", m); } catch (e) {} renderBuilder(); }
function nextSunday() { const d = new Date(); d.setDate(d.getDate() + ((7 - d.getDay()) % 7 || 7)); return ymd(d); }
function calEntry(date) { return D.calendar.find(c => c.date === date); }
// a psalm tone's intonation: on verse 1 only, unless set to every verse
const intoneDefault = p => false;
const intoneEvery = p => p.intonation ? p.intonation === "every" : intoneDefault(p);
// verses the lectionary prints in brackets are optional: sung or not as parish.txt says, or as set per psalm
const optOf = p => p && p.optional != null ? p.optional : !!D.parish.optional;
function optionalVerses(spec) {
  const m = String(spec || "").match(/:\s*([\d,\-()a-d\s]+)$/); if (!m) return [];
  const out = [];
  m[1].split(",").forEach(part => { part = part.trim(); if (!/^\(.*\)$/.test(part)) return;
    const q = part.replace(/[()\sa-d]/g, "").split("-").map(Number); for (let v = q[0]; v <= (q[1] || q[0]); v++) out.push(v); });
  return out;
}
function resolveSpec(spec, optional = true) {
  spec = (spec || "").trim();
  let m = spec.match(/^canticle\s+(\d+)$/i);
  if (m) return TX["Canticle_" + m[1]] ? [{id: "Canticle_" + m[1], verses: null}] : [];
  m = spec.match(/^(?:psalm\s+)?(\d+)(?:\s*:?\s*part\s+(\w+)|\s+([A-Za-z]+))?(?:\s*:\s*([\d,\-()a-d\s]+))?$/i);
  if (!m) return [];
  const base = "Psalm_" + String(+m[1]).padStart(3, "0");
  let verses = null;
  if (m[4]) { verses = []; m[4].split(",").forEach(p => { if (!optional && /^\s*\(.*\)\s*$/.test(p)) return; const q = p.replace(/[()\sa-d]/g, "").split("-").map(Number); for (let v = q[0]; v <= (q[1] || q[0]); v++) verses.push(v); }); }
  let ids = m[2] ? [base + "_Part_" + m[2]] : m[3] ? [base + "_V_" + m[3][0].toUpperCase() + m[3].slice(1).toLowerCase()]
          : TX[base] ? [base] : D.texts.filter(t => t.id.startsWith(base + "_")).map(t => t.id);
  ids = ids.filter(id => TX[id]);
  if (verses) ids = ids.filter(id => TX[id].verses && verses.some(v => v >= TX[id].verses[0] && v <= TX[id].verses[1]));
  return ids.map(id => ({id, verses}));
}
function sundayText() {
  const L = [];
  if (B.label) L.push(`# ${B.label}${B.year ? ", Year " + B.year : ""}`);
  if (B.date) L.push(`date:    ${B.date}`);
  if (B.service !== "Eucharist") L.push(`service: ${B.service}`);
  const musicDone = new Set();            // a chant's music for this service, written once, under its first use
  B.psalms.forEach(p => {
    if (!p.spec.trim()) return;
    L.push(`psalm:   ${p.spec.trim()}`);
    p.chants.forEach((c, i) => {
      const nm = c.name.trim(); if (!nm) return;
      const tm = nm.match(/^tone[:\s]+(.+)$/i);
      L.push(`${tm ? "tone:    " + tm[1].replace(/\s+/g, "") : "chant:   " + nm + (c.shift ? " " + shiftWords(c.shift) : "")}${i > 0 && c.from ? " from " + c.from : ""}`);
      const mine = !tm && (B.music || {})[nm];
      if (mine && !musicDone.has(nm)) {
        musicDone.add(nm);
        Object.entries(mine).forEach(([v, x]) => L.push(`music:   ${v} ${x ? x.start + " " + x.body.replace(/\s+/g, " ").trim() : "silent"}`));
      }
    });
    if (p.intonation && (p.intonation === "every") !== intoneDefault(p) && p.chants.some(c => /^tone[:\s]/i.test(c.name))) L.push(`intonation: ${p.intonation === "every" ? "every verse" : "first verse"}`);
    if (optionalVerses(p.spec).length && p.optional != null && p.optional !== !!D.parish.optional) L.push(`optional: ${p.optional ? "yes" : "no"}           # ${p.optional ? "sing" : "leave out"} the verses in brackets`);
    if (p.daggers) L.push(`daggers: ${p.daggers.length ? p.daggers.join(", ") : "none"}            # this Sunday's †, in place of the text's`);
    Object.keys(p.pointing || {}).sort((a, b) => a - b).forEach(n => {      // this Sunday's pointing of a verse
      p.pointing[n].split("\n").forEach((l, i) => L.push(i ? "         " + l.trim() : "verse:   " + l));
    });
  });
  if (B.gloria !== "auto") L.push(`gloria:  ${B.gloria}`);
  if (!B.reprint) L.push("reprint: no");
  if (B.sung) L.push("sung:    yes");
  if (B.choir === false) L.push("choir:   no                       # no choir this week: the psalm is said");
  const svc = svcLines();                // "Psalm only" hides the rest of the service; it still keeps it
  if (svc.length) L.push("", "# The rest of the service", ...svc);
  return L.join("\n") + "\n";
}
function parseSunday(text) {
  B.psalms = []; B.music = {}; B.service = "Eucharist"; B.gloria = "auto"; B.reprint = true; B.sung = false; B.choir = true; B.svc = {}; B.also = ""; B.note = ""; B.extra = {};
  const alsoL = [], noteL = [], seqL = [];
  let verse = null;                              // a verse: line, collecting its indented lines
  const endVerse = () => { if (verse && B.psalms.length) { const v = parseVerseBlock(verse.join("\n")); const p = B.psalms[B.psalms.length - 1]; if (v) p.pointing = Object.assign({}, p.pointing, {[v[0]]: verse.join("\n")}); } verse = null; };
  text.split("\n").forEach(raw => {
    const line = raw.split("#")[0].trim(); if (!line) return;
    if (verse && /^[ \t]/.test(raw)) { verse.push("    " + line); return; }
    endVerse();
    const i = line.indexOf(":"); if (i < 0) return;
    const k = line.slice(0, i).trim().toLowerCase(), v = line.slice(i + 1).trim();
    if (k === "service") B.service = v;
    else if (k === "gloria") B.gloria = /^(y|yes|true|on)$/i.test(v) ? "yes" : "no";
    else if (k === "reprint") B.reprint = !/^(n|no|false|off)$/i.test(v);
    else if (k === "sung") B.sung = /^(y|yes|true|on)$/i.test(v);
    else if (k === "choir") B.choir = !/^(n|no|false|off|none)$/i.test(v);
    else if (k === "psalm") B.psalms.push({spec: v, chants: [], daggers: null});
    else if (k === "verse" && B.psalms.length) verse = [v];
    else if (k === "intonation" && B.psalms.length) B.psalms[B.psalms.length - 1].intonation = /^(every|all|yes)/i.test(v) ? "every" : "first";
    else if (k === "optional" && B.psalms.length) B.psalms[B.psalms.length - 1].optional = /^(y|yes|true|on|sing|include)$/i.test(v);
    else if ((k === "daggers" || k === "dagger") && B.psalms.length) B.psalms[B.psalms.length - 1].daggers = /^(none|no|-)?$/i.test(v) ? [] : v.split(/[\s,]+/).map(x => parseInt(x.replace(/[^0-9]/g, ""))).filter(x => x);
    else if (SVC_ALIAS[k] || SVC_KEYS.has(k)) { B.svc[SVC_ALIAS[k] || k] = v; if (k !== "organist") seqL.push([SVC_ALIAS[k] || k, v]); }
    else if (k === "also") { alsoL.push(v); seqL.push(["also", v]); }
    else if (k === "note") noteL.push(raw.slice(raw.indexOf(":") + 1).trim());
    else if (PLUGIN_KEYS.has(k)) B.extra[k] = (B.extra[k] ? B.extra[k] + "\n" : "") + raw.slice(raw.indexOf(":") + 1).trim();
    else if (k === "music" && B.psalms.length) {        // a voice of the chant above, as this service has it
      const cs = B.psalms[B.psalms.length - 1].chants, c = cs[cs.length - 1], m = v.match(/^(\w+_notes)\s+(silent|(\S+)\s+(.+))$/);
      if (c && c.name && m) (B.music[c.name] = B.music[c.name] || {})[m[1]] = m[2] === "silent" ? null : {start: m[3], body: m[4].replace(/\\bar "\|\|"\s*/g, '\\bar "||"\n').trim()};
    }
    else if ((k === "chant" || k === "tone") && B.psalms.length) { const m = v.match(/^(.+?)(?:\s+from\s+(\d+))?$/); if (m) { const r = k === "tone" ? {name: "tone " + m[1], shift: 0} : chantRef(m[1]); B.psalms[B.psalms.length - 1].chants.push({name: r.name === "???" ? "" : r.name, from: m[2] || "", shift: r.shift}); } }
  });
  endVerse();
  B.also = alsoL.join("\n"); B.note = noteL.join("\n"); B.seq = seqL;
  B.psalms.forEach(p => { if (!p.chants.length) p.chants.push({name: "", from: ""}); });
  if (!B.psalms.length) B.psalms = [{spec: "", chants: [{name: "", from: ""}]}];
}
function specOf(id) {
  let m = id.match(/^Psalm_(\d+)_Part_(\w+)$/); if (m) return `${+m[1]} Part ${m[2]}`;
  m = id.match(/^Psalm_(\d+)_V_(\w+)$/); if (m) return `${+m[1]} ${m[2]}`;
  m = id.match(/^Psalm_(\d+)$/); if (m) return String(+m[1]);
  m = id.match(/^Canticle_(\d+)$/); return m ? "Canticle " + m[1] : id;
}
function buildThisPsalm(id) {
  // the Psalm builder on its own: no date, no service, just this text and a chant
  B.mode = "psalm"; try { localStorage.setItem("psalter-mode", "psalm"); } catch (e) {}
  B.started = true; B.date = ""; B.label = ""; B.year = ""; B.service = "Eucharist"; B.existing = null; B.files = []; B.status = ""; B.log = ""; B.pdf = "";
  B.name = id.toLowerCase().replace(/_/g, "-"); B.svc = {}; B.also = ""; B.note = ""; B.extra = {}; PLUGINS.reset.forEach(f => f()); B.sung = false; B.choir = true;
  B.psalms = [{spec: specOf(id), chants: [{name: "", from: ""}], daggers: null, open: true}]; B.music = {};
  document.querySelector('nav button[data-tab="builder"]').click();
}
async function setDate(date) {
  if (!date) {                                    // no date: keep the psalm, drop the day
    B.date = ""; B.label = ""; B.year = ""; B.existing = null; PLUGINS.reset.forEach(f => f());
    if (!B.name || /^\d{4}-/.test(B.name)) B.name = "psalm";
    renderBuilder(); return;
  }
  B.date = date; PLUGINS.reset.forEach(f => f()); B.name = date || (B.name && !/^\d{4}-/.test(B.name) ? B.name : "psalm"); B.status = ""; B.log = ""; B.files = []; B.existing = null; B.sung = false; B.choir = true; B.pdf = "";
  const c = calEntry(date);
  B.label = c ? c.label : ""; B.year = c ? c.year : "";
  const opts = c ? c.options.filter(o => o.texts.length) : [];
  const pick = opts.find(o => o.track === "Track " + D.parish.track) || opts[0];
  B.psalms = [{spec: pick ? pick.spec : "", chants: [{name: "", from: ""}], daggers: null}]; B.music = {};
  B.service = c && /Ash Wednesday|Good Friday|Maundy|Vigil/.test(c.label) ? c.label : "Eucharist";
  prefillService(date);
  PLUGINS.reset.forEach(f => f());
  if (SERVER) {
    try { const j = await (await fetch("/api/sunday?name=" + encodeURIComponent(date))).json(); if (j.exists && B.date === date) B.existing = j.text; } catch (e) {}   // not if another day was chosen meanwhile
  }
  renderBuilder();
}
const TONE_NAMES = (D.tones || []).map(t => t.name);
const TONE_OF = {}; (D.toneGroups || []).forEach(g => g.endings.forEach(n => TONE_OF[n.toLowerCase()] = g));
// a tone and then one of its endings, for a chant box (onpick gets e.g. "tone 1g2")
function toneMenus(current, onpick) {
  const cur = (current || "").replace(/^tone[:\s]*/i, "").toLowerCase(), g = TONE_OF[cur];
  const ends = {}; (D.tones || []).forEach(t => ends[t.name] = t);
  return `<select onchange="const g = (D.toneGroups || [])[this.value]; if (g) (${onpick})('tone ' + g.endings[0])">
      <option value="">${g ? "" : "tone…"}</option>${(D.toneGroups || []).map((x, i) => `<option value="${i}" ${x === g ? "selected" : ""}>${esc(x.label)}</option>`).join("")}</select>
    ${g && g.endings.length > 1 ? `<select onchange="(${onpick})('tone ' + this.value)">${g.endings.map(n => `<option value="${esc(n)}" ${n.toLowerCase() === cur ? "selected" : ""}>ending ${esc(ends[n].ending)}</option>`).join("")}</select>` : ""}`;
}
function chantOptions() { return TONE_NAMES.map(t => `<option value="tone ${t}">plainchant psalm tone</option>`).join("") + D.chants.map(c => `<option value="${esc(c.id)}">${esc(CN(c.id))}${val(c, "mood").length ? " · " + esc(val(c, "mood").join(", ")) : ""}</option>`).join(""); }
function renderBuilder() {
  if (!B.date && !B.started) { B.started = true; setDate(nextSunday()); return; }
  B.started = true;
  const c = calEntry(B.date);
  const recent = recentChants(B.date);
  const text = sundayText();
  if (B.pdf && B.pdfText !== text) B.pdf = "";        // the PDF no longer matches: fall back to the quick preview
  $("#tab-builder").innerHTML = `${layoutOpen("builder")}
      <h3>Planning</h3><div class="seg"><button class="${B.mode !== "psalm" ? "on" : ""}" onclick="setMode('service')">Whole service</button><button class="${B.mode === "psalm" ? "on" : ""}" onclick="setMode('psalm')">Psalm only</button></div>
      <h3>Day</h3><input type="date" id="bdate" value="${esc(B.date)}" style="width:100%">
      <p class="hint" style="margin:6px 0">${swatch(B.date)}${c ? lectLink(c.label + " · Year " + c.year, ((SV.lect || {})[B.date] || [])[3]) : B.date ? "Not in the calendar: type the psalm yourself." : "No date: a psalm on its own (a rehearsal, a one-off). Name the file below."}${B.mode === "psalm" && B.date ? ` <span class="link" onclick="setDate('')">no date</span>` : ""}</p>
      <h3>File name ${info("Use e.g. " + (B.date || "2026-12-24") + "-midnight for a second service that day.")}</h3><input type="text" id="bname" value="${esc(B.name)}" style="width:100%">

      <h3>Service</h3><select id="bservice">${[...new Set(SERVICES.concat([B.service]))].map(sv => `<option ${sv === B.service ? "selected" : ""}>${esc(sv)}</option>`).join("")}</select>
      <h3>Gloria Patri</h3><select id="bgloria">${[["auto", "by service"], ["yes", "yes"], ["no", "no"]].map(([v, l]) => `<option value="${v}" ${B.gloria === v ? "selected" : ""}>${l}</option>`).join("")}</select>
      <h3>Options</h3><label class="hint"><input type="checkbox" id="breprint" ${B.reprint ? "checked" : ""}> reprint chant at top of page</label><br>
      <label class="hint"><input type="checkbox" id="bsung" ${B.sung ? "checked" : ""}> sung (confirmed): counts in the history</label><br>
      <label class="hint"><input type="checkbox" id="bnochoir" ${B.choir === false ? "checked" : ""}> no choir this week (the psalm is said)</label>
    </aside><div>
    ${B.existing !== null ? `<div class="card"><b style="font-weight:normal">${esc(B.name)}.txt already exists.</b> <span class="link" onclick="loadExisting()">Load it</span> or carry on to replace it.</div>` : ""}
    ${c && c.options.length ? `<p class="count" style="margin:2px 0 12px">Appointed: ${c.options.map(o =>
      `<span class="link" onclick="usePsalm('${esc(o.spec)}')">${o.track ? esc(o.track) + ": " : ""}${/^\d/.test(o.spec) ? "Psalm " : ""}${esc(o.spec)}</span>${o.texts.length ? "" : ` <span class="hint">(${/^\d/.test(o.spec) ? esc(o.error || "no text yet") : "not in the library yet"})</span>`}`).join(" · ")}${info("Click one to use it." + (D.parish.name ? " " + D.parish.name + " uses" : " Default:") + " Track " + D.parish.track + " after Pentecost (parish.txt).")}</p>` : ""}
    ${B.psalms.map((p, pi) => psalmBlock(p, pi, recent)).join("")}
    <p><span class="link" onclick="addPsalm()">+ another psalm</span></p>
    <div class="card"><details ${B.previewOpen ? "open" : ""} ontoggle="B.previewOpen=this.open"><summary>Preview</summary>
      ${SERVER ? `<p style="margin:8px 0"><button class="small" ${B.busy ? "disabled" : ""} onclick="pdfPreview()">${B.busy && /PDF preview/.test(B.status) ? "Making the PDF…" : "Exact PDF preview"}</button> <span class="hint">LilyPond takes a few seconds</span></p>` : ""}
      ${B.pdf ? `<p style="margin:4px 0"><a href="/${encodeURI(B.pdf)}" target="_blank">Open the PDF in its own tab</a> · <span class="link" onclick="B.pdf=''; renderBuilder()">back to the quick preview</span></p>
        <iframe src="/${encodeURI(B.pdf)}?t=${Date.now()}" style="width:100%;height:80vh;border:1px solid var(--line);border-radius:6px;background:#fff"></iframe>` : quickPreview()}
    </details></div>
    ${B.mode === "psalm" ? "" : serviceCard()}
    <div class="card"><h3 style="font-weight:normal;margin:0 0 6px">The file: ${esc(B.name)}.txt</h3>
      <pre id="bfile" style="font: 14px/1.5 ui-monospace, Menlo, Consolas, monospace; white-space: pre-wrap; margin:0">${esc(text)}</pre>
      <p style="margin:10px 0 0">
        <button class="small primary" onclick="saveSunday()">${SERVER ? "Save" : "Save file…"}</button>
        ${SERVER ? `<button class="small" ${B.busy ? "disabled" : ""} onclick="checkSunday()">Save &amp; check</button>
        <button class="small primary" ${B.busy ? "disabled" : ""} onclick="buildSunday(false)">Save &amp; build PDF + images</button>
        <button class="small" ${B.busy ? "disabled" : ""} onclick="buildSunday(true)">PDF only</button>` : ""}
      </p>
      ${SERVER ? "" : `<p class="hint">Saving writes parish/sundays/${esc(B.name)}.txt (Chrome/Edge) or downloads it. To check and build from here, open the browser with the Precentor launcher (or <code>python tools/serve.py</code>).</p>`}
      ${B.status ? `<p><b style="font-weight:normal">${esc(B.status)}</b></p>` : ""}
      ${B.log ? `<pre style="font: 13px/1.45 ui-monospace, Menlo, Consolas, monospace; white-space: pre-wrap; background: var(--bg); padding: 8px; border-radius: 6px">${esc(B.log)}</pre>` : ""}
      ${B.files.length ? `<p>${B.files.map(f => `<a href="/${encodeURI(f)}" target="_blank">${esc(f.split("/").pop())}</a>`).join(" · ")}</p>` : ""}
    </div>
    ${B.mode === "psalm" ? "" : PLUGINS.cards.map(f => f()).join("")}
    </div></div>
    <datalist id="chantlist">${chantOptions()}</datalist>
    ${repLists()}`;
  $("#bdate").onchange = e => setDate(e.target.value);
  $("#bname").onchange = e => { B.name = e.target.value.trim() || B.date || "psalm"; renderBuilder(); };
  $("#bservice").onchange = e => {
    B.service = e.target.value;
    const keep = new Set(slotsOf(curOrder()).map(x => x.key));          // drop service music the new order doesn't have
    Object.keys(B.svc).forEach(k => { const sl = anySlot(k); if (sl && sl.kind === "service" && !keep.has(k)) delete B.svc[k]; });
    carryService(); renderBuilder();
  };
  $("#bgloria").onchange = e => { B.gloria = e.target.value; renderBuilder(); };
  $("#breprint").onchange = e => { B.reprint = e.target.checked; renderBuilder(); };
  $("#bsung").onchange = e => { B.sung = e.target.checked; renderBuilder(); };
  $("#bnochoir").onchange = e => { B.choir = !e.target.checked; renderBuilder(); };
}

// pointed text as HTML
function pointedLine(t) {
  // mark the pointing with placeholders first, then escape, then turn placeholders into markup
  t = t.replace(/(\S+)- \| -(\S+)/g, "$1\u0001$2").replace(/(\S+)- \| (\S+)/g, "$1-\u0001$2")
       .replace(/(\S+)- \. -(\S+)/g, "$1\u0004$2")
       .replace(/(^|\s)\|\s/g, "$1\u0001").replace(/\s\.\s/g, " \u0004 ")
       .replace(/=([^\s\u0001]+)/g, "\u0002$1\u0003");
  let h = esc(t).replace(/&quot;/g, '"');
  h = h.replace(/(^|[\s\u0001\u0002])"(?=\S)/g, "$1“").replace(/"/g, "”").replace(/(^|[\s\u0001\u0002])'(?=\w)/g, "$1‘").replace(/'/g, "’");
  h = h.replace(/\bLORD/g, 'L<span class="sc">ord</span>').replace(/\bGOD\b/g, 'G<span class="sc">od</span>');
  return h.replace(/\u0001/g, '<span class="pbar"></span>').replace(/\u0004/g, "·")
          .replace(/\u0002/g, '<span class="held">').replace(/\u0003/g, "</span>");
}
function pointedHTML(body, verses, pi, textId) {
  // pi given: the verse numbers can be clicked to put a † on the verse or take it off (this Sunday only);
  // textId given too (with the launcher): ✎ beside a verse edits its pointing there and then
  const vn = (n, dag) => pi === undefined || n === "" ? `<span class="vn">${dag ? "† " : ""}${esc(n)}</span>`
    : `<span class="vn vclick" title="click: † on this verse or off (this file only)" onclick="toggleDagger(${pi}, ${n})">${dag ? "† " : ""}${esc(n)}</span>`;
  const t = textId && D.texts.find(x => x.id === textId);
  const own = n => pi !== undefined && (B.psalms[pi].pointing || {})[n];
  const pen = n => t && SERVER && n !== "" ? (own(n) ? ' <span class="changed" title="Pointed differently for this service">✱</span>' : "") +
    ` <span class="link pen" title="Change this verse's pointing for this service" onclick="startEdit(${JSON.stringify(n)}, '${esc(textId)}', renderBuilder, {pi: ${pi}})">✎</span>` : "";
  return '<div class="ptext">' + body.filter(v => !verses || verses.includes(v[0]) || v[0] === "").map(([n, dag, lines]) =>
    t && editing(textId, n) ? verseEditor(t, t.body.find(x => x[0] === n)) :
    `<div class="v">${lines.map((l, i) => `<div class="${i === 0 ? "" : l[2] ? "wrap" : l[1] === 2 ? "l2" : "l1"}">${i === 0 ? vn(n, dag) : ""}${pointedLine(l[0])}${i === lines.length - 1 ? pen(n) : ""}</div>`).join("")}</div>`).join("") + "</div>";
}
// second-half repeats (†): the text's own, or this Sunday's
function textDaggers(res) { return textBody(res).flatMap(seg => seg.body.filter(v => v[1]).map(v => v[0])); }
function withDaggers(body, daggers) { return daggers ? body.map(v => [v[0], daggers.includes(v[0]) ? 1 : 0, v[2]]) : body; }
function toggleDagger(pi, n) {
  const p = B.psalms[pi], res = resolveSpec(p.spec, optOf(p));
  const orig = textDaggers(res), cur = new Set(p.daggers || orig);
  cur.has(n) ? cur.delete(n) : cur.add(n);
  const list = [...cur].sort((a, b) => a - b);
  p.daggers = list.join() === orig.slice().sort((a, b) => a - b).join() ? null : list;
  p.open = true; renderBuilder();
}
function fitReport(p, pi) {
  // the same check as the build: does each double-chant section come out even?
  const res = resolveSpec(p.spec, optOf(p)); if (!res.length) return "";
  const verses = textBody(res, p).flatMap(seg => withDaggers(seg.body, p.daggers)).filter(v => v[0] !== "");
  let chants = p.chants.filter(c => c.name).map((c, i) => ({name: c.name, from: i === 0 ? verses[0][0] : +c.from}));
  if (!chants.length) { const prev = B.psalms.slice(0, pi).reverse().map(q => q.chants.filter(c => c.name).pop()).find(Boolean); if (prev) chants = [{name: prev.name, from: verses[0][0]}]; }
  const out = [];
  chants.forEach((c, i) => {
    if (i > 0 && !c.from) { out.push(`<span class="warn">⚠ say from which verse ${esc(CN(c.name))} starts</span>`); return; }
    const to = i + 1 < chants.length ? (chants[i + 1].from || 1e9) : 1e9, ch = C[c.name];
    const vs = verses.filter(v => v[0] >= c.from && v[0] < to);
    if (!ch || !vs.length) return;
    if (!ch.double) { if (vs.some(v => v[1])) out.push(`<span class="warn">⚠ † in a single chant (${esc(c.name)}): sung as ordinary verses</span>`); return; }
    let half = 1; const probs = [];
    vs.forEach(v => { if (v[1]) { if (half !== 1) probs.push(`† at v. ${v[0]} falls on the second half`); return; } half = half === 1 ? 2 : 1; });
    if (half !== 1) probs.push("ends in the middle of the chant: put a † on one verse (click its number in the text)");
    out.push(probs.length ? `<span class="warn">⚠ ${esc(c.name)}: ${probs.join("; ")}</span>` : `<span class="hint">✓ the verses fit ${esc(c.name)} (double)</span>`);
  });
  return out.join("<br>");
}
function textBody(res, p) {
  // p given: with that psalm's pointing for this service in place of the text's (B.psalms[pi].pointing)
  const own = n => p && p.pointing && p.pointing[n] && parseVerseBlock(p.pointing[n]);
  return res.map(r => ({id: r.id, title: TX[r.id].title,
    body: TX[r.id].body.filter(v => !r.verses || r.verses.includes(v[0])).map(v => own(v[0]) || v)}));
}

// quick preview of the whole page, without LilyPond
function quickPreview() {
  const out = [];
  let lastMusic = null;
  const gl = B.gloria === "yes" || (B.gloria === "auto" && /office|evensong|morning prayer|evening prayer/i.test(B.service));
  B.psalms.forEach((p, pi) => {
    const res = resolveSpec(p.spec, optOf(p)); if (!res.length) return;
    const chants = p.chants.filter(c => c.name).map((c, i) => ({name: c.name, shift: c.shift || 0, from: i === 0 ? null : +c.from || null}));
    if (!chants.length && lastMusic) chants.push({...lastMusic, from: null});
    textBody(res, p).map(seg => ({...seg, body: withDaggers(seg.body, p.daggers)})).forEach((seg, si) => {
      seg.body.forEach((v, vi) => {
        const starts = chants.filter((c, i) => (i === 0 && pi >= 0 && si === 0 && vi === 0) || (c.from === v[0]));
        starts.forEach(c => { out.push(musicHTML(c.name, c.shift)); lastMusic = c; });
        if (vi === 0) out.push(`<h2 style="font-weight:normal;margin:10px 0 0">${esc(seg.title)} <span class="latin">${esc(TX[seg.id].latin)}</span></h2>`);
        out.push(pointedHTML([v]));
      });
    });
  });
  const lastText = (() => { const p = [...B.psalms].reverse().find(p => resolveSpec(p.spec, optOf(p)).length); const r = p ? resolveSpec(p.spec, optOf(p)) : []; return r.length ? TX[r[r.length - 1].id] : null; })();
  if (gl && D.gloria.length && !(lastText && lastText.noGloria)) out.push(pointedHTML(D.gloria));     // the Te Deum and others take none
  return out.join("") || '<p class="hint">Choose a psalm to see it here.</p>';
}
function musicHTML(name, shift = 0) {
  const tm = name.match(/^tone[:\s]+(.+)$/i);
  if (tm) return `<div class="pv-music"><div class="pv-credit">Tone ${esc(tm[1])}</div><p class="hint">(The tone and the first verse set to it appear in the PDF.)</p></div>`;
  const c = C[name];
  if (!c) return `<p class="hint">${esc(name)}: not in the catalog</p>`;
  const mine = (B.music || {})[c.id];
  return `<div class="pv-music"><div class="pv-credit">${esc(c.composer)}${c.years ? " (" + esc(c.years) + ")" : ""}</div>
    ${mine && SERVER ? serviceImg(c.id, shift, mine) : shift && SERVER ? transposedImg(c.id, shift) : c.img ? `<img src="${esc(chantImg(c))}" alt="${esc(c.id)}">` : esc(c.id)}
    ${shift ? `<p class="hint">${SERVER ? `In ${esc(keyAt(c, shift))} (${shiftWords(shift)}), as the PDF prints it.` : `Shown as written; the PDF prints it in ${esc(keyAt(c, shift))} (${shiftWords(shift)}).`}</p>` : ""}
    ${mine ? `<p class="hint" style="margin:2px 0"><span class="changed">✱</span> changed for this service: ${esc(musicChanges(mine))}. The chant itself is unchanged.</p>` : ""}
    ${SERVER ? `<p class="hint" style="margin:2px 0"><span class="link" onclick="editMusic('${esc(c.id)}', renderBuilder, {service: true})">${mine ? "change it further" : "change the music for this service"}</span>${mine
      ? ` · <span class="link" onclick="delete B.music['${esc(c.id)}']; renderBuilder()">put the chant's own music back</span>` : ""}</p>` : ""}</div>`;
}
const VOICE_NAMES = {S_notes: "soprano", A_notes: "alto", T_notes: "tenor", B_notes: "bass", Unison_notes: "unison", Descant_notes: "descant"};
const musicChanges = m => Object.entries(m).map(([v, x]) => (VOICE_NAMES[v] || v) + (x ? " changed" : " silent")).join(", ");
// a chant as this service has it (its music: lines), drawn by the launcher: like transposedImg
function serviceImg(id, shift, mine) {
  const k = id + "@" + shift + "@" + JSON.stringify(mine);
  if (TRANS[k]) return `<img src="${esc(TRANS[k])}" alt="${esc(id)} as changed for this service">`;
  post("/api/chant/open", {name: id}).then(j => {
    if (!j.ok) return;
    j.parts.voices.forEach(v => { if (v.var in mine) Object.assign(v, mine[v.var] ? {start: mine[v.var].start, body: mine[v.var].body} : {body: ""}); });
    return post("/api/chant/preview", {name: id, shift, parts: j.parts});
  }).then(j => {
    if (!j || !j.ok) return;
    TRANS[k] = j.img;
    document.querySelectorAll(`img[data-trans="${CSS.escape(k)}"]`).forEach(el => { el.src = j.img; el.style.opacity = 1; });
  });
  return `<img data-trans="${esc(k)}" src="${esc(chantImg(C[id]))}" alt="${esc(id)}" style="opacity:.35">`;
}
// a chant transposed, drawn by the launcher once and kept: an <img> filled in when the picture comes
const TRANS = {};
function transposedImg(id, shift) {
  const k = id + "@" + shift;
  if (TRANS[k]) return `<img src="${esc(TRANS[k])}" alt="${esc(id)} ${shiftWords(shift)}">`;
  post("/api/chant/preview", {name: id, shift}).then(j => {
    if (!j.ok) return;
    TRANS[k] = j.img;
    document.querySelectorAll(`img[data-trans="${CSS.escape(k)}"]`).forEach(el => { el.src = j.img; el.style.opacity = 1; });
  });
  return `<img data-trans="${esc(k)}" src="${esc(chantImg(C[id]))}" alt="${esc(id)}" style="opacity:.35">`;
}
// one job at a time: while the launcher checks or builds, the buttons wait (a second click does nothing)
async function busy(fn) {
  if (B.busy) return;
  B.busy = true; renderBuilder();
  try { await fn(); } catch (e) { B.status = "Something went wrong:"; B.log = String(e); }
  finally { B.busy = false; renderBuilder(); }
}
function pdfPreview() { return busy(pdfPreviewNow); }
async function pdfPreviewNow() {
  if (!(await saveSunday())) return;
  B.status = "Making the PDF preview…"; B.log = ""; B.pdf = ""; renderBuilder();
  const j = await post("/api/build", {name: B.name, pdfOnly: true});
  B.status = j.ok ? "" : "The build stopped:"; B.log = j.ok ? "" : (j.log || j.error);
  B.pdf = j.ok ? (j.files || []).find(f => f.endsWith(".pdf")) || "" : "";
  B.pdfText = sundayText();
  B.files = j.files || [];
  B.previewOpen = true; renderBuilder();
}

// chant picker
const P = {pi: 0, ci: 0, q: "", moods: new Set(), mode: "", key: "", sd: "", minRating: 0, pin: "", tone: ""};
SORTS.picker = {levels: sortLevels("picker", [{f: "match", d: -1}, {f: "rating", d: -1}, {f: "stale", d: 1}]), render: () => renderPicker()};
function openPicker(pi, ci) {
  P.pi = pi; P.ci = ci;
  dlg.classList.add("wide");
  renderPicker(); dlg.showModal();
}
function renderPicker() {
  const p = B.psalms[P.pi];
  const res = resolveSpec(p.spec, optOf(p));
  const mood = overlapMoods(res.map(r => r.id), res.length && res[0].verses);
  const recent = recentChants(B.date);
  let list = D.chants.map(c => ({c, ...score(mood, val(c, "mood"))})).filter(({c}) => {
    const m = val(c, "mood"), r = val(c, "rating") || 0;
    if (P.q && !(c.id + " " + c.composer + " " + c.label).toLowerCase().includes(P.q)) return false;
    if (P.moods.size && ![...P.moods].some(t => m.includes(t))) return false;
    if (P.mode === "other" ? ["Major", "Minor"].includes(c.mode) : P.mode && c.mode !== P.mode) return false;
    if (P.key && keyName(c) !== P.key) return false;
    if (P.sd && (P.sd === "d") !== c.double) return false;
    return r >= P.minRating && pinFilter(c, P.pin);
  });
  list.sort(sortCompare(SORTS.picker.levels, x => x.c));
  $("#dlgbody").innerHTML = `<h2 style="font-weight:normal;margin:6px 0">Choose a chant for ${esc(p.spec ? "Psalm " + p.spec : "this psalm")}
      ${mood.length ? '<span style="font-size:15px">' + mood.map(m => chip(m)).join(" ") + "</span>" : ""}</h2>
    <div class="pick"><div>
      <input type="search" id="pq" placeholder="Composer or chant" value="${esc(P.q)}" style="width:100%">
      <h3 class="hint" style="margin:10px 0 4px">Mood</h3>${D.vocabulary.map(g => `<div class="row" style="margin-bottom:5px">${g.tags.map(t =>
        `<button class="chip g-${esc(g.group)} ${P.moods.has(t) ? "on" : ""}" data-pm="${esc(t)}">${esc(t)}</button>`).join("")}</div>`).join("")}
      <h3 class="hint" style="margin:10px 0 4px">Key</h3><select id="pkey"><option value="">any</option>${KEYS_PRESENT.map(k => `<option ${P.key === k ? "selected" : ""}>${esc(k)}</option>`).join("")}</select>
      <h3 class="hint" style="margin:10px 0 4px">Mode</h3><select id="pmode"><option value="">any</option>${["Major", "Minor"].map(m => `<option ${P.mode === m ? "selected" : ""}>${m}</option>`).join("")}<option value="other" ${P.mode === "other" ? "selected" : ""}>modal / other</option></select>
      <h3 class="hint" style="margin:10px 0 4px">Single or double</h3><select id="psd"><option value="">either</option><option value="s" ${P.sd === "s" ? "selected" : ""}>single</option><option value="d" ${P.sd === "d" ? "selected" : ""}>double</option></select>
      <h3 class="hint" style="margin:10px 0 4px">Pinned</h3><select id="ppin">${[["", "all chants"], ["favorite", "favorites"], ["to try", "to try"], ["to check", "to check"]].map(([v, l]) => `<option value="${v}" ${P.pin === v ? "selected" : ""}>${l}</option>`).join("")}</select>
      <h3 class="hint" style="margin:10px 0 4px">Rating at least</h3><select id="prt"><option value="0">any</option>${[1, 2, 3, 4, 5].map(n => `<option ${P.minRating === n ? "selected" : ""}>${n}</option>`).join("")}</select>
      <h3 class="hint" style="margin:10px 0 4px">Sort</h3>${sortControl("picker", true)}
      <h3 class="hint" style="margin:14px 0 4px">Or a plainchant tone</h3><div id="ptone">${toneMenus(P.tone, "t => { P.tone = t; renderPicker(); }")}</div>
      ${P.tone ? `<p style="margin:6px 0 0"><button class="small primary" onclick="pickChant(P.tone)">Use ${esc(P.tone)}</button> <button class="small play" onclick="playTone(P.tone.replace(/^tone /, ''), this)">▶ Play</button></p>` : ""}
    </div><div>
      <p class="count">${list.length} chants</p>
      ${list.slice(0, 80).map(({c, hits}) => `<div class="item">
        <button class="small primary" style="float:right;margin-left:6px" onclick="pickChant('${esc(c.id)}')">Use</button>
        <button class="small play" onclick="play('${esc(c.id)}', this)">▶ Play</button>${pinButtons(c)}
        <b style="font-weight:normal;font-size:19px">${esc(CN(c.id))}</b> <span class="who">${esc(c.composer)} · ${esc(c.id)}</span>
        <div class="facts"><b>${esc(keyName(c))}</b> · ${c.double ? "double" : "single"} ${stars(val(c, "rating"))} · last used ${esc(lastUsed(c.id) || "never")}${recent.has(c.id) ? " <b>(recent)</b>" : ""}</div>
        <div class="moodrow">${val(c, "mood").map(t => chip(t, hits.includes(t) ? "on" : "")).join("")}</div>
        ${c.img ? `<img loading="lazy" src="${esc(chantImg(c))}" alt="">` : ""}
        ${notesBox(val(c, "notes"), false)}
      </div>`).join("")}
      ${list.length > 80 ? '<p class="hint">Showing the first 80: narrow the filters to see others.</p>' : ""}
    </div></div>`;
  $("#pq").oninput = e => { P.q = e.target.value.toLowerCase(); renderPicker(); setTimeout(() => { const el = $("#pq"); el.focus(); el.setSelectionRange(el.value.length, el.value.length); }, 0); };
  document.querySelectorAll("[data-pm]").forEach(b => b.onclick = () => { const t = b.dataset.pm; P.moods.has(t) ? P.moods.delete(t) : P.moods.add(t); renderPicker(); });
  $("#pkey").onchange = e => { P.key = e.target.value; renderPicker(); };
  $("#pmode").onchange = e => { P.mode = e.target.value; renderPicker(); };
  $("#psd").onchange = e => { P.sd = e.target.value; renderPicker(); };
  $("#prt").onchange = e => { P.minRating = +e.target.value; renderPicker(); };
  $("#ppin").onchange = e => { P.pin = e.target.value; renderPicker(); };
}
function pickChant(id) {
  stopPlay();
  B.psalms[P.pi].chants[P.ci].name = id; B.psalms[P.pi].chants[P.ci].shift = 0;
  dlg.close(); dlg.classList.remove("wide");
  renderBuilder();
}
async function useInBuilder(id) {
  if (!B.started) { B.started = true; await setDate(nextSunday()); }      // the builder not opened yet: start it first
  const cs = B.psalms[0].chants; const slot = cs.find(c => !c.name) || cs[0]; slot.name = id; slot.shift = 0;
  document.querySelector('nav button[data-tab="builder"]').click();
}

function psalmBlock(p, pi, recent) {
  const res = resolveSpec(p.spec, optOf(p)), opt = optionalVerses(p.spec);
  const mood = overlapMoods(res.map(r => r.id), res.length && res[0].verses);
  const sg = mood.length ? D.chants.map(ch => ({ch, ...score(mood, val(ch, "mood"))})).filter(x => x.s > 0 && !recent.has(x.ch.id))
    .sort((a, b) => b.s - a.s || (val(b.ch, "rating") || 0) - (val(a.ch, "rating") || 0) || lastUsed(a.ch.id).localeCompare(lastUsed(b.ch.id))).slice(0, 8) : [];
  return `<div class="card">
    <div class="moodrow">Psalm <input type="text" value="${esc(p.spec)}" placeholder="e.g. 70, 72:1-7,18-19, 119 Aleph" style="width:260px"
      onchange="Object.assign(B.psalms[${pi}], {spec: this.value, daggers: null, optional: null, pointing: null}); renderBuilder()">
      ${res.length ? res.map(r => `<span class="link" onclick="goText('${esc(r.id)}')">${esc(TX[r.id].title)}</span>`).join(", ") : (p.spec ? '<span class="hint">no matching text</span>' : "")}
      ${mood.map(m => chip(m)).join(" ")}
      ${B.psalms.length > 1 ? `<span class="link" style="margin-left:auto" onclick="B.psalms.splice(${pi},1); renderBuilder()">remove</span>` : ""}</div>
    ${p.chants.some(c => /^tone[:\s]/i.test(c.name)) ? `<div class="moodrow"><label class="hint"><input type="checkbox" ${intoneEvery(p) ? "checked" : ""} onchange="B.psalms[${pi}].intonation=this.checked ? 'every' : 'first'; renderBuilder()"> sing the tone's intonation on every verse (otherwise on verse 1 only)</label></div>` : ""}
    ${opt.length ? `<div class="moodrow"><label class="hint"><input type="checkbox" ${optOf(p) ? "checked" : ""} onchange="B.psalms[${pi}].optional=this.checked; renderBuilder()"> sing the optional verses (${esc(opt.length > 1 ? "vv. " + opt[0] + "–" + opt[opt.length - 1] : "v. " + opt[0])}, in brackets in the lectionary)</label></div>` : ""}
    ${res.length ? `<details ${p.open ? "open" : ""} ontoggle="B.psalms[${pi}].open=this.open"><summary>The text</summary>
      <p class="hint" style="margin:6px 0 0">Click a verse number to put a † (second half again) on it or take it off, for this file only (the psalm text keeps its own).${SERVER ? " ✎ beside a verse changes its pointing for this service (✱ marks one changed); the text's own pointing is changed on the Psalms tab." : ""}${p.daggers ? ` <span class="link" onclick="B.psalms[${pi}].daggers=null; renderBuilder()">back to the text's own †</span>` : ""}</p>
      ${textBody(res, p).map(seg => `<div class="hint" style="margin-top:6px">${esc(seg.title)}</div>` + pointedHTML(withDaggers(seg.body, p.daggers), null, pi, seg.id)).join("")}</details>` : ""}
    ${B.choir === false ? '<p class="hint" style="margin:6px 0">No choir this week: the psalm is said, so no chant (untick <i>no choir</i> under Options to choose one).</p>' : p.chants.map((c, ci) => {
      const ch = C[c.name];
      return `<div class="moodrow">${ci === 0 ? "Chant" : "then"} <input type="text" list="chantlist" value="${esc(c.name)}" placeholder="chant, or e.g. tone 7a" style="width:170px"
        onchange="{ const r = /^tone[:\\s]/i.test(this.value.trim()) ? {name: this.value.trim(), shift: 0} : chantRef(this.value); B.psalms[${pi}].chants[${ci}].name=r.name; B.psalms[${pi}].chants[${ci}].shift=r.shift; renderBuilder(); }">
        <button class="small" onclick="openPicker(${pi}, ${ci})">Choose…</button>
        ${ch ? `<select title="Transpose: the PDF prints the chant in this key" onchange="B.psalms[${pi}].chants[${ci}].shift=+this.value; renderBuilder()">${
          [...new Set([-4, -3, -2, -1, 0, 1, 2, 3, 4, c.shift || 0])].sort((a, b) => a - b).map(s => `<option value="${s}" ${s === (c.shift || 0) ? "selected" : ""}>${esc(keyAt(ch, s))}${s ? " (" + shiftWords(s) + ")" : " (as written)"}</option>`).join("")}</select>` : ""}
        ${ci > 0 ? `from verse <input type="text" value="${esc(c.from)}" style="width:50px" onchange="B.psalms[${pi}].chants[${ci}].from=this.value.trim(); renderBuilder()">` : ""}
        ${/^tone[:\s]/i.test(c.name) ? toneMenus(c.name, `t => { B.psalms[${pi}].chants[${ci}].name = t; renderBuilder(); }`) : ""}
        ${ch ? `<button class="small play" onclick="play('${esc(ch.id)}', this, ${c.shift || 0})">▶ Play</button>` : (c.name && !/^tone[:\s]/i.test(c.name)) ? '<span class="hint">not in the catalog</span>' : ""}
        ${ci > 0 ? `<span class="link" onclick="B.psalms[${pi}].chants.splice(${ci},1); renderBuilder()">remove</span>` : ""}</div>
        ${ch ? `<div class="moodrow chantfacts"><span class="hint"><span class="link" onclick="showChant('${esc(ch.id)}')">${esc(CN(ch.id))}</span>, ${ch.double ? "double" : "single"} · last used ${esc(lastUsed(ch.id) || "never")}</span>
          ${val(ch, "mood").map(t => chip(t, mood.includes(t) ? "on" : "")).join("") || '<span class="hint">no moods yet</span>'}</div>` : ""}`;
    }).join("")}
    ${B.choir === false ? "" : `<p style="margin:4px 0"><span class="link" onclick="B.psalms[${pi}].chants.push({name:'',from:''}); renderBuilder()">+ change chant partway</span></p>`}
    ${res.length && B.choir !== false ? `<div style="margin:2px 0 6px">${fitReport(p, pi)}${(() => { const d = p.daggers || textDaggers(res); return `<div class="hint">† ${d.length ? "on v. " + d.join(", ") : "on no verse"}${p.daggers ? " (moved for this Sunday)" : " (as marked in the text)"} · <span class="link" onclick="B.psalms[${pi}].open=true; renderBuilder()">change</span></div>`; })()}</div>` : ""}
    ${sg.length && B.choir !== false ? `<div class="used">Suggestions (moods match, not used in the last 12 weeks): ${sg.map(x =>
      `<span class="link" onclick="useChant(${pi}, '${esc(x.ch.id)}')">${esc(CN(x.ch.id))}</span>`).join(" · ")}</div>`
      : ""}
  </div>`;
}
function usePsalm(spec) { Object.assign(B.psalms[0], {spec, daggers: null, optional: null, pointing: null}); renderBuilder(); }   // the †s were the old psalm's
function addPsalm() { B.psalms.push({spec: "", chants: [{name: "", from: ""}]}); renderBuilder(); }
function useChant(pi, id) { const cs = B.psalms[pi].chants; const slot = cs.find(c => !c.name) || cs[0]; slot.name = id; slot.shift = 0; renderBuilder(); }
function loadExisting() { parseSunday(B.existing); B.existing = null; renderBuilder(); }
async function saveSunday() {
  const text = sundayText();
  if (SERVER) {
    const j = await post("/api/sunday", {name: B.name, text});
    B.status = j.ok ? "Saved " + j.path : "Could not save: " + j.error; B.existing = null; renderBuilder(); return j.ok;
  }
  try {
    if ("showSaveFilePicker" in window) {
      const h = await window.showSaveFilePicker({suggestedName: B.name + ".txt", types: [{description: "Sunday file", accept: {"text/plain": [".txt"]}}]});
      const w = await h.createWritable(); await w.write(text); await w.close();
      B.status = "Saved " + h.name + " (it belongs in the sundays folder).";
    } else {
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], {type: "text/plain"})); a.download = B.name + ".txt"; a.click();
      B.status = "Downloaded " + B.name + ".txt: move it into the sundays folder.";
    }
  } catch (e) { if (e.name !== "AbortError") B.status = "Could not save: " + e.message; }
  renderBuilder();
}
function checkSunday() { return busy(checkSundayNow); }
async function checkSundayNow() {
  if (!(await saveSunday())) return;
  B.status = "Checking…"; renderBuilder();
  const j = await post("/api/check", {name: B.name});
  B.status = j.ok ? "Checks done." : "Problem:"; B.log = j.log || j.error; renderBuilder();
}
function buildSunday(pdfOnly) { return busy(() => buildSundayNow(pdfOnly)); }
async function buildSundayNow(pdfOnly) {
  if (!(await saveSunday())) return;
  B.status = "Building… (LilyPond takes a little while)"; B.log = ""; B.files = []; renderBuilder();
  const j = await post("/api/build", {name: B.name, pdfOnly});
  B.status = !j.ok ? "The build stopped:" : B.choir === false ? "No choir this week: nothing to build." : "Built.";
  B.log = B.choir === false && j.ok ? "" : j.log || j.error; B.files = j.files || [];
  if (j.ok && !pdfOnly) B.builtText = sundayText();
  renderBuilder();
}

// ---------- editing a chant: its details (the catalog row) and its music (the .ly file), with the launcher ----------
// a chant's picture: the one just drawn in the editor, if it was saved this session, else the browser's
const chantImg = c => c.previewImg || `notation/${encodeURIComponent(c.id)}.png`;

// details, in the card (like the moods)
const detailsOpen = new Set();
function detailsBox(c) {
  const f = (k, label, v, w = "100%") => `<label class="hint" style="display:block;margin:4px 0">${label}<br><input type="text" data-f="${k}" value="${esc(v || "")}" style="width:${w}"></label>`;
  return `<div class="edit" id="details-${esc(c.id)}">
    ${f("Composer", "Composer (Surname, Given names)", c.composer)}
    <div style="display:flex;gap:10px;flex-wrap:wrap">${f("Years", "Years", c.years, "120px")}${f("Key", "Key (A, Bb, F#)", c.key, "90px")}${f("Mode", "Mode (Major, Minor, Mix…)", c.mode, "130px")}
      <label class="hint" style="display:block;margin:4px 0">Single or double<br><select data-f="Single/Double"><option ${c.double ? "" : "selected"}>Single</option><option ${c.double ? "selected" : ""}>Double</option></select></label></div>
    ${f("Source", "Source (ACP 074, a book…)", c.source)}${f("ACP Psalm", "Psalms the ACP sets it to (35, 78-1)", c.acp)}
    <p style="margin:6px 0 0"><button class="small primary" onclick="saveDetails('${esc(c.id)}')">Save details</button>
      <button class="small" onclick="toggleDetails('${esc(c.id)}')">Cancel</button> <span class="hint" id="dmsg-${esc(c.id)}"></span></p>
  </div>`;
}
function toggleDetails(id) {
  if (detailsOpen.has(id)) return shutPanel(id, () => detailsOpen.delete(id));
  openEdits.delete(id); detailsOpen.add(id); JUST = "details:" + id; refreshCard(id);
}
function openDetails(id) { if (!detailsOpen.has(id)) toggleDetails(id); }
async function saveDetails(id) {
  const box = $("#details-" + CSS.escape(id)), fields = {};
  box.querySelectorAll("[data-f]").forEach(el => fields[el.dataset.f] = el.value.trim());
  $("#dmsg-" + CSS.escape(id)).textContent = "Saving…";
  const j = await post("/api/chant/details", {name: id, fields});
  if (!j.ok) { $("#dmsg-" + CSS.escape(id)).textContent = j.error || "Could not save"; return; }
  Object.assign(C[id], {composer: fields.Composer, years: fields.Years, key: fields.Key, mode: fields.Mode,
                        double: fields["Single/Double"] === "Double", source: fields.Source, acp: fields["ACP Psalm"]});
  shutPanel(id, () => detailsOpen.delete(id));
}

// the music: each voice in LilyPond's note language, with a picture that redraws as you type
const ME = {name: "", parts: null, img: "", problems: [], error: "", voices: null, busy: false, isNew: false, details: null, timer: 0, after: null};
const TONICS = ["c", "cis", "des", "d", "dis", "ees", "e", "f", "fis", "ges", "g", "gis", "aes", "a", "ais", "bes", "b"];
const tonicName = t => t[0].toUpperCase() + t.slice(1).replace("is", "♯").replace(/e?s$/, "♭");     // aes -> A♭
const catalogKey = t => t[0].toUpperCase() + t.slice(1).replace("is", "#").replace(/e?s$/, "b");    // aes -> Ab
async function editMusic(name, after, opts = {}) {
  const j = await post("/api/chant/open", {name});
  if (!j.ok) { window.alert(j.error || "Could not open it"); return; }
  // for one service (from the planner): the chant's own music with this service's changes; saved in the Sunday file
  const mine = opts.service ? (B.music || {})[name] || {} : null, own = JSON.parse(JSON.stringify(j.parts));
  if (mine) j.parts.voices.forEach(v => { if (v.var in mine) Object.assign(v, mine[v.var] ? {start: mine[v.var].start, body: mine[v.var].body} : {body: ""}); });
  Object.assign(ME, {name, parts: j.parts, own: opts.service ? own : null, service: !!opts.service,
                     img: "", problems: [], error: "", voices: null, half: null, isNew: !j.exists, after: after || null, details: null});
  drawMusicEditor(); dlg.classList.add("wide"); if (!dlg.open) dlg.showModal();
  previewMusic();
}
function drawMusicEditor() {
  const p = ME.parts, k = p.key || {tonic: "c", mode: "major"};
  const modes = [...new Set(["major", "minor", k.mode])];
  $("#dlgbody").innerHTML = `<h3 style="margin:4px 0">${ME.service ? "Music for this service: " : ME.isNew ? "New chant: " : "Music: "}${esc(C[ME.name] ? CN(ME.name) : ME.name)} <span class="hint">${esc(ME.name)}${ME.service ? "" : ".ly"}</span></h3>
    ${ME.service ? `<p class="hint" style="margin:0 0 6px">Changes here are for this service only, kept in its Sunday file (like pointing changed for a service); the chant itself stays as it is. Leave a voice empty and it doesn't sing; edit a chord (<code>&lt;a f&gt;2</code>) to one note to drop a part. The key and the time stay the chant's; to move the key, transpose it in the planner.</p>` : ""}
    <div class="me-grid"><div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;${ME.service ? "display:none" : ""}">
        <label class="hint">Key<br><select id="me-tonic">${TONICS.map(t => `<option value="${t}" ${t === k.tonic ? "selected" : ""}>${esc(tonicName(t))}</option>`).join("")}</select>
          <select id="me-mode">${modes.map(m => `<option ${m === k.mode ? "selected" : ""}>${m}</option>`).join("")}</select></label>
        <label class="hint">Time<br><input type="text" id="me-time" value="${esc(p.time)}" style="width:60px"></label>
        <label class="hint" style="flex:1;min-width:200px">Credit line<br><input type="text" id="me-credit" value="${esc(p.credit)}" style="width:100%"></label>
      </div>
      ${p.voices.map((v, i) => `<label class="hint" style="display:block;margin-top:8px">${esc(v.label)} <span title="the pitch the first note is counted from (LilyPond's \\relative)">from <input type="text" class="me-start" data-i="${i}" value="${esc(v.start)}" style="width:44px"></span>
        <textarea class="me-voice" data-i="${i}" spellcheck="false" rows="${Math.max(3, v.body.split("\n").length)}" style="width:100%;font:14px/1.5 ui-monospace,Menlo,Consolas,monospace">${esc(v.body)}</textarea></label>`).join("")}
      <p class="hint" style="margin:6px 0">Notes as LilyPond writes them: <code>aes2</code> a half-note A♭, <code>c4.</code> a dotted quarter, <code>'</code> up an octave, <code>,</code> down; <code>|</code> a bar, <code>\\bar "||"</code> the end of a phrase.</p>
    </div><div>
      <div id="me-pic" class="notation">${musicPicture()}</div>
      <p style="margin:6px 0"><button class="small play" onclick="playEdited(this)">▶ Play</button> <span class="hint" id="me-state"></span></p>
    </div></div>
    <p style="margin:10px 0 0">${ME.service
      ? `<button class="small primary" id="me-save" onclick="useForService()">Use for this service</button>
         ${(B.music || {})[ME.name] ? `<button class="small" onclick="delete B.music[ME.name]; const a = ME.after; dlg.close(); if (a) a()">Put the chant's own music back</button>` : ""}`
      : `<button class="small primary" id="me-save" onclick="saveMusic()">${ME.isNew ? "Add the chant" : "Save the music"}</button>`}
      <button class="small" onclick="dlg.close()">Cancel</button></p>`;
  $("#dlgbody").querySelectorAll("select, input, textarea").forEach(el => el.addEventListener("input", () => { clearTimeout(ME.timer); ME.timer = setTimeout(previewMusic, 700); }));
}
function musicPicture() {
  return `${ME.img ? `<img src="${esc(ME.img)}" alt="the chant as edited" style="max-height:220px">` : '<p class="hint">Drawing…</p>'}
    ${ME.error ? `<p class="warn">${esc(ME.error)}</p>` : ""}
    ${ME.problems.map(x => `<p class="warn" style="margin:2px 0">⚠ ${esc(x)}</p>`).join("")}${ME.img && !ME.error && !ME.problems.length ? '<p class="hint"><span class="ok">✓</span> the voices agree, phrase by phrase</p>' : ""}`;
}
function editedParts() {
  const p = JSON.parse(JSON.stringify(ME.parts));
  if ($("#me-tonic")) p.key = {tonic: $("#me-tonic").value, mode: $("#me-mode").value};
  if ($("#me-time")) p.time = $("#me-time").value.trim();
  if ($("#me-credit")) p.credit = $("#me-credit").value;
  document.querySelectorAll(".me-voice").forEach(t => p.voices[+t.dataset.i].body = t.value);
  document.querySelectorAll(".me-start").forEach(t => p.voices[+t.dataset.i].start = t.value.trim());
  return p;
}
async function previewMusic() {
  const parts = editedParts(), state = $("#me-state");
  if (state) state.textContent = "Drawing…";
  let j;
  try { j = await post("/api/chant/preview", {name: ME.name, parts, credit: parts.credit}); } catch (e) { j = {ok: false, error: "the launcher didn't answer"}; }
  ME.parts = parts;
  Object.assign(ME, {img: j.img || ME.img, error: j.ok ? "" : (j.error || "could not draw it"), problems: j.problems || [], voices: j.voices || ME.voices,
                     double: j.double, half: j.half});
  if ($("#me-pic")) $("#me-pic").innerHTML = musicPicture();
  if (state) state.textContent = "";
}
// for one service: keep in B.music only the voices that differ from the chant's own (empty: that voice is silent)
function useForService() {
  const parts = editedParts(), own = ME.own, mine = {};
  parts.voices.forEach(v => {
    const o = own.voices.find(x => x.var === v.var);
    if (!v.body.trim()) mine[v.var] = null;
    else if (!o || o.body.replace(/\s+/g, " ").trim() !== v.body.replace(/\s+/g, " ").trim() || o.start !== v.start) mine[v.var] = {start: v.start, body: v.body.trim()};
  });
  if (Object.keys(mine).length) B.music[ME.name] = mine; else delete B.music[ME.name];
  const after = ME.after; dlg.close();
  if (after) after();
}
function playEdited(btn) { if (ME.voices) playVoices(ME.voices, btn, ME.half); }
async function saveMusic() {
  const parts = editedParts();
  if (ME.details) Object.assign(ME.details, {Key: catalogKey(parts.key.tonic), Mode: parts.key.mode[0].toUpperCase() + parts.key.mode.slice(1),
                                             "Single/Double": ME.double === false ? "Single" : "Double"});
  $("#me-save").disabled = true;
  const j = await post("/api/chant/save", {name: ME.name, parts, credit: parts.credit, details: ME.details, private: ME.details && ME.details.private});
  $("#me-save").disabled = false;
  if (!j.ok) { $("#me-state").textContent = j.error || "Could not save"; return; }
  await previewMusic();
  if (!C[ME.name]) {                               // a new chant: into the list now; the next rebuild fills in the rest
    const d = ME.details || {}, c = {id: ME.name, composer: d.Composer || "", years: d.Years || "", key: d.Key || "", mode: d.Mode || "",
      double: d["Single/Double"] !== "Single", range: null, rating: null, mood: [], notes: "", pins: [], source: d.Source || "", acp: "", img: true, voices: ME.voices, private: !!d.private, label: ME.name};
    D.chants.push(c); C[c.id] = c;
  }
  Object.assign(C[ME.name], {previewImg: ME.img, voices: ME.voices, img: true});
  const after = ME.after; dlg.close();
  if (after) after(); else if (!$("#tab-chants").hidden) renderChants();
}

// a new chant: its name and facts first, then the music editor
function newChant() {
  ME.imported = null;
  $("#dlgbody").innerHTML = `<h3>New chant</h3>
    <p style="margin:4px 0 8px"><label class="hint">Start from a score (optional): MusicXML from MuseScore, Finale, Sibelius or Dorico<br>
      <input type="file" id="nc-file" accept=".musicxml,.mxl,.xml" onchange="importScore(this.files[0])"></label> <span class="hint" id="nc-imp"></span></p>
    <label class="hint" style="display:block;margin:4px 0">Composer (Surname, Given names)<br><input type="text" id="nc-composer" style="width:100%" oninput="ncName()"></label>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <label class="hint">Years<br><input type="text" id="nc-years" placeholder="1802-1882" style="width:110px"></label>
      <label class="hint">File name<br><input type="text" id="nc-name" placeholder="Turle-7" style="width:130px"></label>
      <label class="hint">Source<br><input type="text" id="nc-source" placeholder="ACP 065, a book…" style="width:200px"></label></div>
    <p style="margin:8px 0"><label class="hint"><input type="radio" name="nc-where" value="public" checked> public domain (goes in chants/, shared)</label><br>
      <label class="hint"><input type="radio" name="nc-where" value="private"> still under copyright (goes in parish/chants/, private)</label></p>
    <p><button class="small primary" onclick="startNewChant()">Next: the music</button> <button class="small" onclick="dlg.close()">Cancel</button> <span class="hint" id="nc-msg"></span></p>`;
  dlg.showModal();
}
// a score exported as MusicXML: its four voices, key, time and composer, ready for the editor
async function importScore(file) {
  const msg = $("#nc-imp");
  ME.imported = null;
  if (!file) { msg.textContent = ""; return; }                 // the choice cancelled
  if (file.size > 5e6) { msg.innerHTML = '<span class="warn">that file is too big for a chant</span>'; return; }
  msg.textContent = "Reading…";
  let j;
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let bin = ""; for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    j = await post("/api/chant/import", {filename: file.name, file: btoa(bin)});
  } catch (e) { j = {ok: false, error: "the launcher didn't answer"}; }
  if ($("#nc-file") && $("#nc-file").files[0] !== file) return;   // another file was chosen meanwhile
  if (!j.ok) { msg.innerHTML = `<span class="warn">${esc(j.error || "could not read it")}</span>`; return; }
  ME.imported = j.parts;
  const credit = (j.composer || "").trim(), paren = credit.match(/\(([^)]*)\)\s*$/);   // "James Turle (1802-1882)"
  const who = credit.replace(/\s*\([^)]*\)\s*$/, "").trim(), years = paren && paren[1].match(/^\s*(\d{3,4})\s*[-–]\s*(\d{3,4})?\s*$/);
  if (who && !$("#nc-composer").value) {
    const words = who.split(/\s+/), sur = words.pop();
    $("#nc-composer").value = words.length ? `${sur}, ${words.join(" ")}` : sur;
    ncName();
  }
  if (years && !$("#nc-years").value) $("#nc-years").value = years[1] + "-" + (years[2] || "");
  msg.innerHTML = `<span class="ok">✓</span> four voices in ${esc(tonicName(j.parts.key.tonic))} ${esc(j.parts.key.mode)}${j.title ? ", “" + esc(j.title) + "”" : ""}`
    + (j.warnings || []).map(w => `<br><span class="warn">⚠ ${esc(w)}</span>`).join("");
}
function ncName() {
  const sur = ($("#nc-composer").value.split(",")[0] || "").replace(/[^A-Za-z]/g, "");
  if (!sur) return;
  let n = 1; while (C[`${sur}-${n}`] || (D.aliases || {})[`${sur}-${n}`]) n++;
  $("#nc-name").value = `${sur}-${n}`;
}
async function startNewChant() {
  const name = $("#nc-name").value.trim(), composer = $("#nc-composer").value.trim();
  if (!/^[A-Za-z][A-Za-z0-9]*-\d+$/.test(name)) { $("#nc-msg").textContent = "a file name like Turle-7"; return; }
  if (C[name] || (D.aliases || {})[name]) { $("#nc-msg").textContent = name + " is taken"; return; }
  const years = $("#nc-years").value.trim(), given = composer.split(",")[1] || "", sur = composer.split(",")[0] || "";
  const credit = `${(given.trim() + " " + sur.trim()).trim()}${years ? " (" + years + ")" : ""}`;
  ME.details = {Composer: composer, Years: years, Source: $("#nc-source").value.trim(), "Single/Double": "Double",
                private: document.querySelector('input[name="nc-where"]:checked').value === "private"};
  const j = await post("/api/chant/open", {name, credit});
  if (!j.ok) { $("#nc-msg").textContent = j.error || "Could not start it"; return; }
  const parts = ME.imported ? Object.assign(JSON.parse(JSON.stringify(ME.imported)), {credit: j.parts.credit}) : j.parts;
  Object.assign(ME, {name, parts, service: false, own: null, img: "", problems: [], error: "", voices: null, isNew: true, after: null});
  drawMusicEditor(); dlg.classList.add("wide"); previewMusic();
}

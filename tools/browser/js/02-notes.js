// ---------- local edits (kept in this browser until exported) ----------
const KEY = "precentor-edits-v1";
let edits = {};
try { edits = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { edits = {}; }
function saveEdits() { try { localStorage.setItem(KEY, JSON.stringify(edits)); } catch (e) {} renderSavebar(); }
const C = {}; D.chants.forEach(c => C[c.id] = c);
Object.keys(edits).forEach(id => {
  if (!C[id]) { delete edits[id]; return; }
  Object.keys(edits[id]).forEach(f => { if (JSON.stringify(C[id][f]) === JSON.stringify(edits[id][f])) delete edits[id][f]; });
  if (!Object.keys(edits[id]).length) delete edits[id];
});
try { localStorage.setItem(KEY, JSON.stringify(edits)); } catch (e) {}
function val(c, f) { return edits[c.id] && f in edits[c.id] ? edits[c.id][f] : c[f]; }
function setEdit(id, f, v) {
  edits[id] = edits[id] || {};
  const orig = C[id][f];
  if (JSON.stringify(orig) === JSON.stringify(v)) delete edits[id][f]; else edits[id][f] = v;
  if (!Object.keys(edits[id]).length) delete edits[id];
  saveEdits();
}
let savedNote = "";
function renderSavebar() {
  const n = Object.keys(edits).length;
  const canWrite = SERVER || "showSaveFilePicker" in window;
  $("#savebar").innerHTML = (savedNote ? `<span>${esc(savedNote)}</span> ` : "") + (n ? `${n} chant${n > 1 ? "s" : ""} edited here
    <button class="small primary" onclick="saveCatalog()">${canWrite ? "Save" : "Download chant_notes.csv"}</button>
    <button class="small" onclick="discardEdits()">Discard</button>` : "");
}
function discardEdits() { if (window.confirm("Discard the edits made in this browser?")) { edits = {}; savedNote = ""; saveEdits(); renderChants(); } }
function csvField(v) { v = String(v ?? ""); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
function catalogText() {
  const cols = ["Chant", "Rating", "Mood", "Notes", "Pin"];
  const lines = [cols.join(",")];
  D.chants.forEach(c => {
    const r = val(c, "rating");
    lines.push([c.id, r == null ? "" : r, val(c, "mood").join("; "), val(c, "notes"), (val(c, "pins") || []).join("; ")].map(csvField).join(","));
  });
  return lines.join("\n") + "\n";
}
// remember the catalog file between visits (Chrome and Edge only)
function idb(mode, fn) {
  return new Promise((res, rej) => {
    const r = indexedDB.open("precentor", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("kv");
    r.onerror = () => rej(r.error);
    r.onsuccess = () => { const tx = r.result.transaction("kv", mode); const q = fn(tx.objectStore("kv")); tx.oncomplete = () => res(q && q.result); tx.onerror = () => rej(tx.error); };
  });
}
async function saveCatalog() {
  const text = catalogText();
  if (SERVER) {
    savedNote = "Saving…"; renderSavebar();
    const j = await post("/api/notes", {csv: text});
    savedNote = !j.ok ? "Could not save: " + (j.error || j.log)
      : j.rebuilt === false ? "Saved to chant_notes.csv, but the page couldn't be refreshed: " + (j.log || "").trim().split("\n").pop()
      : "Saved.";
    if (j.ok) {                                   // what was saved is now the chant's own value: nothing left pending
      Object.entries(edits).forEach(([id, e]) => { if (C[id]) Object.assign(C[id], e); });
      edits = {}; saveEdits();
    }
    renderSavebar(); return;
  }
  if (!("showSaveFilePicker" in window)) {
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], {type: "text/csv"})); a.download = "chant_notes.csv"; a.click();
    savedNote = "Downloaded: save it over parish/chant_notes.csv.";
    renderSavebar(); return;
  }
  try {
    let h = null;
    try { h = await idb("readonly", st => st.get("notes")); } catch (e) {}
    if (h && (await h.requestPermission({mode: "readwrite"})) !== "granted") h = null;
    if (!h) {
      window.alert("Choose parish/chant_notes.csv in your precentor folder. The browser will remember it next time.");
      h = await window.showSaveFilePicker({suggestedName: "chant_notes.csv", types: [{description: "CSV", accept: {"text/csv": [".csv"]}}]});
      try { await idb("readwrite", st => st.put(h, "notes")); } catch (e) {}
    }
    const w = await h.createWritable(); await w.write(text); await w.close();
    savedNote = "Saved to " + h.name + ". Run tools/browser.py to refresh, then commit.";
    renderSavebar();
  } catch (e) {
    if (e && e.name !== "AbortError") window.alert("Could not save: " + e.message);
  }
}

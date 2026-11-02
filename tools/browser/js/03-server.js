// ---------- the launcher: saving, Undo and Changes, Sync with GitHub ----------
let SERVER = false, SETUP = null;        // SETUP: the feasts to offer, when the launcher has no parish folder yet
if (location.protocol.startsWith("http") && !D.demo) fetch("/api/ping").then(r => r.ok && r.json()).then(j => { if (j && j.ok) { SERVER = true; SETUP = j.setup ? j.feasts : null; if (j.library) Object.assign(LIB, j.library); if (!$("#tab-upcoming").hidden) renderUpcoming(); renderSavebar(); renderHistory(); refreshGit(); renderChantsShell(); renderChants(); if (!$("#tab-builder").hidden) renderBuilder(); renderLibrary(); } }).catch(() => {});
let CHANGES = [], PENDING = {n: 0, files: []};
// a cloud with two arrows going round: syncing with an online copy
const SYNC_ICON = `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.1 9.2 4.5 4.5 0 0 0 7 18z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><g class="arrows"><path d="M9.5 12.5a2.6 2.6 0 0 1 4.6-1.2M14.5 13.5a2.6 2.6 0 0 1-4.6 1.2" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/><path d="M14.6 9.6v1.9h-1.9M9.4 16.4v-1.9h1.9" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></g></svg>`;
let SYNCING = false;        // the arrows go round while a sync runs
async function refreshGit() {
  if (!SERVER) return;
  try {
    const [g, h] = await Promise.all([fetch("/api/git").then(r => r.json()), fetch("/api/history").then(r => r.json())]);
    CHANGES = h.changes || [];
    const n = g.repos.reduce((a, r) => a + r.unpushed + r.files.length, 0);
    const synced = !n && g.repos.length && g.repos.every(r => r.online !== false);   // all of it on GitHub
    const last = CHANGES[0];
    $("#gitbar").innerHTML = (last ? ` <button class="small" title="Undo: ${esc(last.message)}" onclick="undoChange(0)">↶ Undo</button>
      <button class="small" onclick="showChanges()">Changes</button>` : "")
      + ` <button class="small sync${SYNCING ? " busy" : ""}" title="${n ? n + " change(s) not on GitHub yet" : synced ? "Everything here is on GitHub" : "No GitHub copy is set up for this folder"}" onclick="showSync()">${SYNC_ICON} Sync with GitHub${
        n ? ` <span class="badge">${n}</span>` : synced ? ' <span class="ok">✓</span>' : ""}</button><span class="info" style="cursor:pointer" title="${esc(SYNC_WHY)}" onclick="showSyncWhy()">i</span>`;
    PENDING = {n, files: g.repos.flatMap(r => r.files.map(f => r.repo + ": " + f))};
    if (dlg.open && $("#changes")) showChanges();
  } catch (e) {}
}
function whenText(t) {
  const d = new Date(t * 1000), now = new Date();
  const time = d.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
  if (d.toDateString() === now.toDateString()) return "today " + time;
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (d.toDateString() === y.toDateString()) return "yesterday " + time;
  return d.toLocaleDateString([], {month: "short", day: "numeric", year: d.getFullYear() === now.getFullYear() ? undefined : "numeric"}) + " " + time;
}
function showChanges() {
  $("#dlgbody").innerHTML = `<h3>Changes</h3>
    <p class="muted">Every save here is kept, newest first. Undo puts back what a change changed, as a new change, so an undo can itself be undone. Sync with GitHub brings in what's new there and sends a copy of these.</p>
    <table id="changes">${CHANGES.map((c, i) => `<tr><td class="muted" style="white-space:nowrap">${whenText(c.time)}</td>
      <td>${esc(c.message)}${c.pushed ? "" : ' <span class="muted" title="Recorded on this computer, not yet saved to GitHub">•</span>'}</td>
      <td><button class="small" onclick="undoChange(${i})">Undo</button></td></tr>`).join("") || '<tr><td class="muted">Nothing yet.</td></tr>'}</table>`;
  if (!dlg.open) dlg.showModal();
}
async function undoChange(i) {
  const c = CHANGES[i];
  if (!c || !window.confirm(`Undo this change?\n\n${c.message} (${whenText(c.time)})`)) return;
  $("#gitbar").textContent = " Undoing…";
  const j = await post("/api/undo", {repo: c.repo, sha: c.sha});
  if (!j.ok) { window.alert("Could not undo: " + (j.error || "something went wrong")); return refreshGit(); }
  location.reload();                    // the page was rebuilt without that change
}
// Sync with GitHub: the button asks right beside it, then syncs; the (i) beside it says why one would
const SYNC_WHY = "Everything you save here is kept on this computer at once, and Undo works without GitHub. Syncing adds:\n" +
  "• a backup of your parish folder in your own GitHub account, safe if this computer is lost;\n" +
  "• your other computers: their changes come here, and yours go there (sync before you switch);\n" +
  "• updates to Precentor itself (it starts again on its own).";
function syncPop(html, keep) {
  let pop = $("#syncpop");
  if (!pop) { pop = Object.assign(document.createElement("div"), {id: "syncpop", className: "pop"}); document.body.appendChild(pop); }
  const b = $("button.sync"), r = b ? b.getBoundingClientRect() : {right: innerWidth - 16, bottom: 60};
  pop.style.top = (r.bottom + 6) + "px";
  pop.style.right = Math.max(8, innerWidth - r.right) + "px";
  pop.innerHTML = html; pop.hidden = false;
  if (pop.getBoundingClientRect().left < 8) pop.style.right = Math.max(8, innerWidth - pop.offsetWidth - 8) + "px";   // (a narrow window)
  clearTimeout(syncPop.t);
  if (!keep) syncPop.t = setTimeout(() => { pop.hidden = true; }, 5000);
}
function closeSyncPop() { const p = $("#syncpop"); if (p) p.hidden = true; }
// a click outside closes it; not the click on its own Sync button, which replaced what was clicked with the progress
document.addEventListener("click", e => { if (e.target.isConnected && !e.target.closest("#syncpop, button.sync")) closeSyncPop(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeSyncPop(); });
function showSync() {
  const waiting = CHANGES.filter(c => !c.pushed);
  syncPop(`<div>${PENDING.n ? `Send <b>${PENDING.n}</b> change${PENDING.n > 1 ? "s" : ""} to GitHub, and bring in anything new?` : "Nothing to send. Bring in anything new from GitHub?"}</div>
    ${waiting.length ? `<div class="hint" style="margin-top:4px">${waiting.slice(0, 3).map(c => esc(c.message)).join("<br>")}${waiting.length > 3 ? `<br>and ${waiting.length - 3} more` : ""}</div>` : ""}
    <div style="margin-top:8px;text-align:right"><button class="small" onclick="closeSyncPop()">Cancel</button> <button class="small primary" onclick="commitAll()">Sync</button></div>`, true);
}
function showSyncWhy() { $("#dlgbody").innerHTML = `<h3>${SYNC_ICON} Why sync with GitHub</h3><p style="white-space:pre-line">${esc(SYNC_WHY)}</p>`; dlg.showModal(); }
// while it syncs: a bar that fills step by step (save, ask GitHub, bring in, send, for each folder), and the step
const syncBar = (done, total, step) => `<div class="hint">Syncing with GitHub…</div>
  <div class="bar"><span style="width:${total ? Math.max(6, Math.round(100 * done / total)) : 6}%"></span></div>
  <div class="hint step" style="font-size:13px;margin-top:3px">${esc(step && step !== "starting" ? step : "starting")}</div>`;
async function commitAll() {
  SYNCING = true; const btn = $("button.sync"); if (btn) btn.classList.add("busy");
  syncPop(syncBar(0, 0, ""), true);
  let j, polling = true;
  const poll = async () => {
    while (polling) {
      try {
        const p = await fetch("/api/sync/progress").then(r => r.json()), bar = $("#syncpop .bar span");
        if (!polling) break;
        if (bar) { bar.style.width = (p.total ? Math.max(6, Math.round(100 * p.done / p.total)) : 6) + "%"; $("#syncpop .step").textContent = p.step && p.step !== "starting" ? p.step : "starting"; }
        else syncPop(syncBar(p.done, p.total, p.step), true);
      } catch (e) {}
      await new Promise(r => setTimeout(r, 250));
    }
  };
  poll();
  try { j = await post("/api/commit", {}); } catch (e) { j = {ok: false, error: "the launcher didn't answer: is it still running?"}; }
  polling = false;
  if (!j.restarting) { SYNCING = false; const b = $("button.sync"); if (b) b.classList.remove("busy"); }
  if (j.ok && j.restarting) {                        // an update to Precentor itself: the launcher starts again
    syncPop(`<span class="ok">✓</span> Brought in an update to Precentor: starting it again…`, true);
    for (let i = 0; i < 120; i++) {
      await new Promise(r => setTimeout(r, 1000));
      try { if ((await fetch("/api/ping").then(r => r.json())).ok && i > 0) { location.reload(); return; } } catch (e) {}
    }
    syncPop(`<span class="warn">Precentor didn't start again:</span> close its window and open it again.`); return;
  }
  if (j.ok && /brought in/.test(j.log || "")) { location.reload(); return; }     // new things came: show them
  if (j.ok) syncPop(`<span class="ok">✓</span> ${esc(j.log || "Done.").replace(/\n/g, "<br>")}`);
  else syncPop(`<span class="warn">Could not sync:</span> ${esc(j.error || j.log || "something went wrong").replace(/\n/g, "<br>")}
    <div style="margin-top:8px;text-align:right"><button class="small" onclick="closeSyncPop()">Close</button></div>`, true);
  refreshGit();
}
setInterval(refreshGit, 30000);
async function post(url, obj) {
  const r = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(obj)});
  setTimeout(refreshGit, 800);
  return r.json();
}

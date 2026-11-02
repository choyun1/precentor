// ---------- history tab ----------
async function markSung(name, btn) {
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Marking and rebuilding the history…'; }
  const j = await post("/api/sung", {name, sung: true});
  if (j.ok) location.reload();
  else { window.alert("Could not mark it: " + (j.error || "")); if (btn) { btn.disabled = false; btn.textContent = "Mark as sung"; } }
}
const HV = {mode: "psalms"};
// every service on record (an imported record, then the Sunday files): what was sung, by date
function servicesRecord() {
  const orders = [...new Set(Object.values(SV.byDate).map(e => e.order))];
  return `<input type="search" id="sq" placeholder="Filter: a date, hymn number, anthem, composer…" style="width:min(420px,100%)">
    <select id="so"><option value="">every kind of service</option>${orders.map(o => `<option>${esc(o)}</option>`).join("")}</select>
    <button class="small" onclick="downloadRecord()">Download the whole record (CSV)</button>
    <p class="count" id="scount"></p><div id="slist"></div>`;
}
function itemText(order, k, v) {
  const s = (SV.orders[order] || []).find(x => x.key === k) || anySlot(k) || {label: k === "also" ? "" : k, kind: "music"};
  const label = s.label.replace(/\s*\{hymn\|anthem\}/, "");
  const hs = s.kind !== "music" && s.kind !== "lesson" ? hymnsOf(v) : [];
  const body = hs.length ? hs.map(h => h.number + (h.title && !h.service ? ". " + h.title : "") + (h.book !== "EH1982" ? " (" + h.book + ")" : "")).join("; ") : v.split("|").map(x => x.trim()).join(" — ");
  return label ? `<span class="hint">${esc(label)}:</span> ${esc(body)}` : esc(body);
}
function csvCell(v) { v = String(v ?? ""); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
// a day's name, linked to its readings on the Episcopal Church's lectionary site (tools/lectionary_links.py)
// the liturgical color of a date (lectionary.py, with the parish's choices in parish.txt)
function litColor(date) { return ((SV.colors || {})[String(date || "").slice(0, 10)]) || ""; }
function litShade(name) { return (SV.shades || {})[name] || name; }
function swatch(date) {
  const c = litColor(date);
  return c ? `<span class="swatch" style="background:${esc(litShade(c))}" title="${esc(c[0].toUpperCase() + c.slice(1))}"></span>` : "";
}
function lectLink(text, url) { return url ? `<a href="${esc(url)}" target="_blank" title="The readings, on lectionary.episcopalchurch.org">${esc(text)}</a>` : esc(text); }
function downloadRecord() {
  // every service on record, one row per piece, with hymn titles spelled out
  const rows = [["date", "service", "lectionary day", "slot", "item", "title", "readings"]];
  Object.keys(SV.byDate).sort().forEach(k => {
    const e = SV.byDate[k], d = e.date, day = (SV.lect || {})[d], lect = day ? `${day[2]}, Year ${day[1]}` : "", url = day ? day[3] || "" : "";
    (e.psalms || []).forEach(ps => rows.push([d, e.order, lect, "Psalm", ps.replace(/\s*\(\)$/, ""), "", url]));
    e.items.filter(([k]) => !["organist", "note"].includes(k) && !PLUGIN_KEYS.has(k)).forEach(([k, v]) => {
      const s = (SV.orders[e.order] || []).find(x => x.key === k) || anySlot(k) || {label: k === "also" ? "Other" : k, kind: "music"};
      const hs = s.kind !== "music" && s.kind !== "lesson" ? hymnsOf(v) : [];
      rows.push([d, e.order, lect, s.label.replace(/\s*\{hymn\|anthem\}/, ""), hs.length ? hs.map(h => (h.book === "EH1982" ? "" : h.book + " ") + h.number).join("; ") : v, hs.map(h => h.title).join("; "), url]);
    });
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["\ufeff" + rows.map(r => r.map(csvCell).join(",")).join("\r\n")], {type: "text/csv"}));
  a.download = "music-record-" + ymd() + ".csv"; a.click();
}
function drawServices() {
  const q = $("#sq").value.toLowerCase(), o = $("#so").value;
  const dates = Object.keys(SV.byDate).sort().reverse().filter(k => {
    const e = SV.byDate[k];
    if (o && e.order !== o) return false;
    if (!q) return true;
    const words = [k, e.order].concat(e.items.map(([k, v]) => v + " " + hymnsOf(v).map(h => h.title).join(" "))).join(" ").toLowerCase();
    return words.includes(q);
  });
  $("#scount").textContent = dates.length + " services";
  $("#slist").innerHTML = dates.slice(0, 200).map(k => {
    const e = SV.byDate[k], d = e.date;
    const items = e.items.filter(([k]) => !["organist", "note"].includes(k) && !PLUGIN_KEYS.has(k));
    return `<details class="card" style="padding:8px 14px;margin-bottom:6px"><summary>${swatch(d)}${esc(k)} · ${(SV.lect || {})[d] ? lectLink(SV.lect[d][2] + ", Year " + SV.lect[d][1], SV.lect[d][3]) + " · " : ""}${esc(e.order)} <span class="hint">· ${items.length} items${e.source === "file" ? " · from its file here" : " · from the imported record"}</span></summary>
      <ul style="margin:6px 0 2px 1.1em;padding:0">${items.map(([k, v]) => `<li>${itemText(e.order, k, v)}</li>`).join("")}</ul></details>`;
  }).join("") + (dates.length > 200 ? '<p class="hint">Showing the 200 most recent: filter to find older ones.</p>' : "");
}
function renderHistory() {
  const unc = D.unconfirmed || [];
  $("#tab-history").innerHTML = (unc.length ? `<div class="card"><h3 style="font-weight:normal;margin:0 0 6px">Past Sundays not yet confirmed</h3>
    <p class="hint" style="margin:0 0 6px">A Sunday counts in the history once it's marked as sung${SERVER ? "" : " (add the line <code>sung: yes</code> to its file, or open the browser with the launcher for a button)"}.</p>
    <table class="hist">${unc.map(u => `<tr><td>${esc(u.date)}</td><td>${esc(u.psalms.join(", "))}</td><td>${esc(u.chants.map(chantText).join(", "))}</td>
      <td>${SERVER ? `<button class="small primary" onclick="markSung('${esc(u.name)}', this)">Mark as sung</button>` : `<span class="hint">${esc(u.name)}.txt</span>`}</td></tr>`).join("")}</table></div>` : "") +
    `<div class="seg" style="max-width:420px;margin-bottom:10px"><button class="${HV.mode !== "services" ? "on" : ""}" onclick="HV.mode='psalms'; renderHistory()">Psalms and chants</button><button class="${HV.mode === "services" ? "on" : ""}" onclick="HV.mode='services'; renderHistory()">Whole services</button></div>` +
    (HV.mode === "services" ? servicesRecord() :
    `<input type="search" id="hq" placeholder="Filter by date, psalm or chant" style="width:min(420px,100%)">
    <p class="count" id="hcount"></p><table class="hist" id="htab"></table>`);
  if (HV.mode === "services") { $("#sq").oninput = drawServices; $("#so").onchange = drawServices; drawServices(); return; }
  const draw = () => {
    const q = $("#hq").value.toLowerCase();
    const rows = D.history.slice().reverse().filter(h => !q || [h.date, h.text, textTitle[h.text], h.chant, h.note].join(" ").toLowerCase().includes(q));
    $("#hcount").textContent = rows.length + " entries";
    $("#htab").innerHTML = `<tr><th>Date</th><th>Text</th><th>Verses</th><th>Chant</th><th></th></tr>` + rows.map(h =>
      `<tr><td>${swatch(h.date)}${lectLink(h.date, ((SV.lect || {})[h.date] || [])[3])}</td><td>${esc(textTitle[h.text] || h.text)}</td><td>${esc(h.verses)}</td>
       <td>${C[h.chant] ? `<span class="link" onclick="showChant('${esc(h.chant)}')">${esc(CN(h.chant))}</span>${h.shift ? ` <span class="hint">${shiftWords(h.shift)}</span>` : ""}` : h.chant && h.chant !== "?" ? esc(h.chant) : '<span class="hint">no chant</span>'}</td><td class="hint">${esc(h.note)}</td></tr>`).join("");
  };
  $("#hq").oninput = draw; draw();
}

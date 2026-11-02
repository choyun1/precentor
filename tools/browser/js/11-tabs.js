// ---------- tabs ----------
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("nav button").forEach(x => x.classList.toggle("on", x === b));
  ["upcoming", "builder", "chants", "texts", "library", "history"].forEach(t => $("#tab-" + t).hidden = t !== b.dataset.tab);
  stopPlay();
  if (b.dataset.tab === "texts") renderTextsShell();
  if (b.dataset.tab === "upcoming") renderUpcoming();
  if (b.dataset.tab === "builder") renderBuilder();
  if (b.dataset.tab === "library") renderLibrary();
});
const dlg = $("#dlg");
dlg.addEventListener("close", () => { dlg.classList.remove("wide"); stopPlay(); if (!$("#tab-chants").hidden) renderChants(); else if (!$("#tab-texts").hidden) renderText(); });
renderSavebar(); renderUpcoming(); renderChantsShell(); renderChants(); renderHistory(); renderLibrary();

// ---------- tabs ----------
// Each tab remembers how far down it was scrolled (the page and its side list),
// so switching away and back returns to the same place.
const tabScroll = {};
const currentTab = () => document.querySelector("nav button.on")?.dataset.tab;
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  const from = currentTab(), to = b.dataset.tab;
  if (from) tabScroll[from] = { y: window.scrollY, aside: $("#tab-" + from + " aside")?.scrollTop || 0 };
  document.querySelectorAll("nav button").forEach(x => x.classList.toggle("on", x === b));
  ["upcoming", "builder", "chants", "texts", "library", "history"].forEach(t => $("#tab-" + t).hidden = t !== to);
  stopPlay();
  if (to === "texts") renderTextsShell();
  if (to === "upcoming") renderUpcoming();
  if (to === "builder") renderBuilder();
  if (to === "library") renderLibrary();
  if (to === from) return;
  const saved = tabScroll[to] || { y: 0, aside: 0 };
  const aside = $("#tab-" + to + " aside");
  if (aside) aside.scrollTop = saved.aside;
  window.scrollTo(0, saved.y);
});
const dlg = $("#dlg");
dlg.addEventListener("close", () => { dlg.classList.remove("wide"); stopPlay(); if (!$("#tab-chants").hidden) renderChants(); else if (!$("#tab-texts").hidden) renderText(); });
renderSavebar(); renderUpcoming(); renderChantsShell(); renderChants(); renderHistory(); renderLibrary();

// ---------- playback ----------
// Each note is an organ pipe: an 8' principal (a steady tone, the fundamental strong with a few softer upper
// partials), a little wind "chiff" as it speaks, and a small room around it. A double chant breathes between
// its halves.
let audio = null, playing = null, playId = 0;     // playId: which playback is current, so an old one's timer can't stop a new one
let principal = null, room = null;
const BREATH = 0.25;                              // the rest between a double chant's halves, in whole notes
function stopPlay() { playId++; if (playing) { playing.forEach(o => { try { o.stop(); } catch (e) {} }); playing = null; } document.querySelectorAll(".play").forEach(b => b.textContent = "▶ Play"); }
function play(id, btn, shift = 0) {
  const v = shift ? Object.fromEntries(Object.entries(C[id].voices).map(([k, evs]) => [k, evs.map(([m, a, b]) => [m + shift, a, b])])) : C[id].voices;
  playVoices(v, btn, C[id].half);
}
function playTone(name, btn) { playVoices((D.tones || []).find(t => t.name === name).voices, btn); }
// the times of a voice's notes with a breath before the second half (half: when it starts, in whole notes)
function withBreath(evs, half) {
  if (half == null) return evs;
  return evs.map(([m, st, du]) => st >= half - 1e-6 ? [m, st + BREATH, du] : [m, st, du]);
}
function organSetup() {
  // partials of a principal: the 2nd and 3rd present, the rest fading (amplitudes, from the fundamental up)
  const amp = [0, 1, .42, .24, .12, .08, .05, .035, .02];
  principal = audio.createPeriodicWave(new Float32Array(amp.length), new Float32Array(amp));
  // a small stone room: 1.6 s of decaying noise as the impulse
  const len = Math.floor(audio.sampleRate * 1.6), buf = audio.createBuffer(2, len, audio.sampleRate);
  for (let ch = 0; ch < 2; ch++) { const d = buf.getChannelData(ch); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3.2); }
  room = buf;
}
function playVoices(voices, btn, half = null) {
  if (playing) { const was = btn.textContent.startsWith("■"); stopPlay(); if (was) return; }
  audio = audio || new (window.AudioContext || window.webkitAudioContext)();
  if (!principal) organSetup();
  const wn = 2.09;                                // seconds per whole note (raise to slow down)
  const t0 = audio.currentTime + 0.08, out = audio.createGain(); out.gain.value = 0.16; out.connect(audio.destination);
  const lp = audio.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 3200; lp.Q.value = 0.5;
  const dry = audio.createGain(), wet = audio.createGain(), verb = audio.createConvolver();
  dry.gain.value = 0.8; wet.gain.value = 0.28; verb.buffer = room;
  lp.connect(dry); dry.connect(out); lp.connect(verb); verb.connect(wet); wet.connect(out);
  playing = []; let end = 0;
  Object.entries(voices).forEach(([v, evs]) => {
    if (v === "descant") return;
    withBreath(evs, half).forEach(([m, st, du]) => {
      const f = 440 * Math.pow(2, (m - 69) / 12), a = t0 + st * wn, b = a + du * wn;   // midi 69 = A4 = 440 Hz
      end = Math.max(end, b);
      // the pipe: speaks in ~50 ms, holds steady, and stops in ~70 ms
      const g = audio.createGain(); g.gain.setValueAtTime(0, a); g.gain.linearRampToValueAtTime(1, a + 0.05);
      g.gain.setValueAtTime(1, Math.max(a + 0.05, b - 0.07)); g.gain.linearRampToValueAtTime(0, b); g.connect(lp);
      const o = audio.createOscillator(); o.setPeriodicWave(principal); o.frequency.value = f;
      o.detune.value = (Math.random() - 0.5) * 4;  // pipes are never quite in tune with each other
      o.connect(g); o.start(a); o.stop(b + 0.02); playing.push(o);
      // chiff: a soft breath of the octave as the pipe speaks
      const c = audio.createOscillator(), cg = audio.createGain(); c.type = "sine"; c.frequency.value = f * 2;
      cg.gain.setValueAtTime(0, a); cg.gain.linearRampToValueAtTime(0.22, a + 0.015); cg.gain.exponentialRampToValueAtTime(0.001, a + 0.09);
      c.connect(cg); cg.connect(g); c.start(a); c.stop(a + 0.1); playing.push(c);
    });
  });
  btn.textContent = "■ Stop";
  const me = ++playId;
  setTimeout(() => { if (me === playId) stopPlay(); }, (end - audio.currentTime + 0.2) * 1000);
}

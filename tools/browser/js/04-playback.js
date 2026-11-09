// ---------- playback ----------
// Each voice is an 8' principal: a steady organ tone, the fundamental strong with a few softer upper partials,
// with a soft chiff of the octave as each note speaks, in a small room; the low end is trimmed and the melody sits a little forward so
// the four parts stay clear. Each half of a chant is played legato: a voice moves from note to note with no gap
// (a repeated note is re-struck), and a double chant breathes between its halves.
let audio = null, playing = null, playId = 0;     // playId: which playback is current, so an old one's timer can't stop a new one
let principal = null, room = null;
const BREATH = 0.07;                              // the rest between a double chant's halves, in whole notes
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
// a voice's notes as slurs: runs of notes each starting as the one before ends (a chord's notes go in runs of their own)
function slurs(evs) {
  const runs = [];
  [...evs].sort((x, y) => x[1] - y[1]).forEach(e => {
    const r = runs.find(r => { const l = r[r.length - 1]; return Math.abs(l[1] + l[2] - e[1]) < 1e-6; });
    if (r) r.push(e); else runs.push([e]);
  });
  return runs;
}
function soundSetup() {
  const amp = [0, 1, .3, .12, .05, .025, .012];   // a round principal: the fundamental, the 2nd and 3rd softly, little above
  principal = audio.createPeriodicWave(new Float32Array(amp.length), new Float32Array(amp));
  const len = Math.floor(audio.sampleRate * 1.2), buf = audio.createBuffer(2, len, audio.sampleRate);   // a small stone room
  for (let ch = 0; ch < 2; ch++) { const d = buf.getChannelData(ch); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3); }
  room = buf;
}
function playVoices(voices, btn, half = null) {
  if (playing) { const was = btn.textContent.startsWith("■"); stopPlay(); if (was) return; }
  audio = audio || new (window.AudioContext || window.webkitAudioContext)();
  if (!principal) soundSetup();
  const wn = 2.09;                                // seconds per whole note (raise to slow down)
  const t0 = audio.currentTime + 0.1, out = audio.createGain(); out.gain.value = 0.17; out.connect(audio.destination);
  const lp = audio.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 4500; lp.Q.value = 0.5;
  const hp = audio.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 140; hp.Q.value = 0.6;    // no boom below the bass's fundamentals
  const lo = audio.createBiquadFilter(); lo.type = "lowshelf"; lo.frequency.value = 300; lo.gain.value = -5;   // and less of the muddy low mid
  const hi = audio.createBiquadFilter(); hi.type = "peaking"; hi.frequency.value = 2500; hi.Q.value = 0.8; hi.gain.value = 0;   // (no added presence: the tone stays round)
  hp.connect(lo); lo.connect(hi); hi.connect(lp);
  const dry = audio.createGain(), wet = audio.createGain(), verb = audio.createConvolver();
  dry.gain.value = 0.85; wet.gain.value = 0.14; verb.buffer = room;
  lp.connect(dry); dry.connect(out); lp.connect(verb); verb.connect(wet); wet.connect(out);
  const hz = m => 440 * Math.pow(2, (m - 69) / 12);   // midi 69 = A4 = 440 Hz
  playing = []; let end = 0;
  Object.entries(voices).forEach(([v, evs]) => {
    if (v === "descant") return;
    const level = /^(S|Unison)_/.test(v) || v === "chant" ? 1 : /^B_/.test(v) ? 0.6 : 0.68;   // the tune forward, the bass not heavy
    slurs(withBreath(evs, half)).forEach(run => {
      const a = t0 + run[0][1] * wn, last = run[run.length - 1], b = t0 + (last[1] + last[2]) * wn;
      end = Math.max(end, b);
      // the pipe speaks in ~50 ms, holds, and stops in ~70 ms; within a half it only changes note
      const g = audio.createGain(), vol = audio.createGain(); vol.gain.value = level; g.connect(vol); vol.connect(hp);
      g.gain.setValueAtTime(0, a); g.gain.linearRampToValueAtTime(1, a + 0.05);
      const o = audio.createOscillator(); o.setPeriodicWave(principal); o.frequency.setValueAtTime(hz(run[0][0]), a);
      o.detune.value = (Math.random() - 0.5) * 4;  // pipes are never quite in tune with each other
      // chiff: a soft breath of the octave as the pipe speaks each note
      const chiff = (m, t) => {
        const c = audio.createOscillator(), cg = audio.createGain(); c.frequency.value = hz(m) * 2;
        cg.gain.setValueAtTime(0, t); cg.gain.linearRampToValueAtTime(0.18, t + 0.015); cg.gain.exponentialRampToValueAtTime(0.001, t + 0.09);
        c.connect(cg); cg.connect(vol); c.start(t); c.stop(t + 0.1); playing.push(c);
      };
      chiff(run[0][0], a);
      run.forEach(([m, st], i) => {
        if (!i) return;
        const t = t0 + st * wn;
        chiff(m, t);
        if (m === run[i - 1][0]) {               // the same note again: lift and re-strike it
          g.gain.setValueAtTime(1, t - 0.05); g.gain.linearRampToValueAtTime(0.1, t - 0.01); g.gain.linearRampToValueAtTime(1, t + 0.04);
        } else o.frequency.setTargetAtTime(hz(m), t, 0.004);   // legato: straight on to the next note
      });
      g.gain.setValueAtTime(1, Math.max(a + 0.05, b - 0.07)); g.gain.linearRampToValueAtTime(0, b);
      o.connect(g); o.start(a); o.stop(b + 0.02); playing.push(o);
    });
  });
  btn.textContent = "■ Stop";
  const me = ++playId;
  setTimeout(() => { if (me === playId) stopPlay(); }, (end - audio.currentTime + 0.2) * 1000);
}

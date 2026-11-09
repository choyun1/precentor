// ---------- playback ----------
// Each voice is a flute: a clear tone (the fundamental, with enough of the partials above to keep it bright),
// a little breath and a gentle vibrato; the low end is trimmed and the melody sits a little forward so the four parts stay clear. Each half of a
// chant is slurred, so a voice is one breath that moves from note to note (a repeated note gets a light
// tongue); a double chant breathes between its halves.
let audio = null, playing = null, playId = 0;     // playId: which playback is current, so an old one's timer can't stop a new one
let flute = null, room = null, breathNoise = null;
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
  const amp = [0, 1, .42, .26, .12, .07, .035, .02];   // a flute: the fundamental strong, the 2nd and 3rd partials clearly there
  flute = audio.createPeriodicWave(new Float32Array(amp.length), new Float32Array(amp));
  const len = Math.floor(audio.sampleRate * 1.2), buf = audio.createBuffer(2, len, audio.sampleRate);   // a small stone room
  for (let ch = 0; ch < 2; ch++) { const d = buf.getChannelData(ch); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3); }
  room = buf;
  const n = audio.createBuffer(1, audio.sampleRate * 2, audio.sampleRate), d = n.getChannelData(0);    // breath: 2 s of noise, looped
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  breathNoise = n;
}
function playVoices(voices, btn, half = null) {
  if (playing) { const was = btn.textContent.startsWith("■"); stopPlay(); if (was) return; }
  audio = audio || new (window.AudioContext || window.webkitAudioContext)();
  if (!flute) soundSetup();
  const wn = 2.09;                                // seconds per whole note (raise to slow down)
  const t0 = audio.currentTime + 0.1, out = audio.createGain(); out.gain.value = 0.17; out.connect(audio.destination);
  const lp = audio.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 7000; lp.Q.value = 0.5;
  const hp = audio.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 140; hp.Q.value = 0.6;    // no boom below the bass's fundamentals
  const lo = audio.createBiquadFilter(); lo.type = "lowshelf"; lo.frequency.value = 300; lo.gain.value = -5;   // and less of the muddy low mid
  const hi = audio.createBiquadFilter(); hi.type = "peaking"; hi.frequency.value = 2500; hi.Q.value = 0.8; hi.gain.value = 3;   // a little presence
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
      // the breath that carries the slur: swells in, holds (a soft tongue on a repeated note), and dies away
      const g = audio.createGain(), vol = audio.createGain(); vol.gain.value = level; g.connect(vol); vol.connect(hp);
      g.gain.setValueAtTime(0, a); g.gain.linearRampToValueAtTime(1, a + 0.08);
      const o = audio.createOscillator(); o.setPeriodicWave(flute); o.frequency.setValueAtTime(hz(run[0][0]), a);
      run.forEach(([m, st], i) => {
        if (!i) return;
        const t = t0 + st * wn;
        if (m === run[i - 1][0]) {               // the same note again: tongue it
          g.gain.setValueAtTime(1, t - 0.04); g.gain.linearRampToValueAtTime(0.45, t); g.gain.linearRampToValueAtTime(1, t + 0.05);
        } else o.frequency.setTargetAtTime(hz(m), t, 0.012);   // a slur: glide to the next note in a few ms
      });
      g.gain.setValueAtTime(1, Math.max(a + 0.08, b - 0.1)); g.gain.linearRampToValueAtTime(0, b);
      // vibrato, coming in after the note has spoken
      const lfo = audio.createOscillator(), depth = audio.createGain(); lfo.frequency.value = 4.8 + Math.random() * 0.6;
      depth.gain.setValueAtTime(0, a); depth.gain.linearRampToValueAtTime(0, a + 0.25); depth.gain.linearRampToValueAtTime(9, a + 0.8);   // cents
      lfo.connect(depth); depth.connect(o.detune);
      o.connect(g); o.start(a); o.stop(b + 0.02); lfo.start(a); lfo.stop(b + 0.02); playing.push(o, lfo);
      // a faint, steady air in the tone (no chiff as it speaks)
      const air = audio.createBufferSource(), bp = audio.createBiquadFilter(), ag = audio.createGain();
      air.buffer = breathNoise; air.loop = true; bp.type = "bandpass"; bp.frequency.value = hz(run[0][0]) * 2; bp.Q.value = 1.2;
      ag.gain.setValueAtTime(0, a); ag.gain.linearRampToValueAtTime(0.05, a + 0.08);
      ag.gain.setValueAtTime(0.05, Math.max(a + 0.08, b - 0.1)); ag.gain.linearRampToValueAtTime(0, b);
      air.connect(bp); bp.connect(ag); ag.connect(hp); air.start(a); air.stop(b + 0.02); playing.push(air);
    });
  });
  btn.textContent = "■ Stop";
  const me = ++playId;
  setTimeout(() => { if (me === playId) stopPlay(); }, (end - audio.currentTime + 0.2) * 1000);
}

"""The MusicXML import against an independent reader and writer (music21), on real music:

    pip install music21 && python -m unittest tests.test_musicxml_roundtrip      (skipped without music21)

- every chant here, written out by music21 as MusicXML in three layouts (four parts; two staves of two voices;
  two staves of chords, where the voices move together), comes back through the importer note for note, with
  its phrases;
- Bach's four-part chorales (music21's corpus, MusicXML from several programs) come in note for note as
  music21 reads them, or are refused with a message (never a crash).
"""
import os, sys, tempfile, unittest
from fractions import Fraction as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import chantedit, musicxml, paths   # noqa: E402
from chantparse import load_chant   # noqa: E402

try:
    import music21
    from music21 import bar, chord, duration, key, layout, metadata, meter, note, pitch, stream
except ImportError:
    music21 = None

SATB = ('S_notes', 'A_notes', 'T_notes', 'B_notes')
STEPS = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}


def facts(text):
    """{voice: ([(midi, start, length)], phrases)} of a chant file, by the chant files' own reader."""
    c = load_chant(text, is_text=True)
    return {v: ([(h.midi, F(h.start), F(h.dur)) for n in ns for h in (n if isinstance(n, list) else [n])], list(sec))
            for v, (ns, sec) in c['voices'].items() if v in SATB}


def m21pitch(h):
    for octave in range(9):
        alter = h.midi - (12 * (octave + 1) + STEPS[h.name[0]])
        if -2 <= alter <= 2:
            p = pitch.Pitch(h.name[0].upper() + str(octave))
            p.accidental = pitch.Accidental(alter) if alter else None
            return p


def events(notes):
    return [(F(n[0].start if isinstance(n, list) else n.start), F(n[0].dur if isinstance(n, list) else n.dur),
             [m21pitch(h) for h in (n if isinstance(n, list) else [n])]) for n in notes]


def gaps(notes):
    """Does the voice fall silent anywhere (a rest, or cue-size notes only)?"""
    evs = events(notes)
    return evs[0][0] > 0 or any(b[0] > a[0] + a[1] for a, b in zip(evs, evs[1:]))


def line(evs, ts, ks, phrases, cls=None):
    s = (cls or stream.Part)()
    s.append(ks)
    s.append(meter.TimeSignature(ts))
    at = F(0)
    for st, d, ps in evs:
        if st > at:                                  # a silent stretch (a rest, or cue-size notes only)
            r = note.Rest()
            r.duration = duration.Duration(float((st - at) * 4))
            s.append(r)
        el = chord.Chord(ps) if len(ps) > 1 else note.Note(ps[0])
        el.duration = duration.Duration(float(d * 4))
        s.append(el)
        at = st + d
    m = s.makeMeasures()
    m.makeTies(inPlace=True)
    ms, at = list(m.getElementsByClass(stream.Measure)), 0
    for k in phrases:
        at += k
        if at <= len(ms):
            ms[at - 1].rightBarline = bar.Barline('double' if at < len(ms) else 'final')
    return m


def write(c, ts, how):
    """The chant c (as load_chant reads it) as MusicXML bytes, laid out how; None if it can't be laid out so."""
    tonic, mode = c['key']
    ks = key.Key(tonic[0].upper() + {'is': '#', 'es': '-', 's': '-'}.get(tonic[1:], ''), mode)
    V = {v: c['voices'][v] for v in SATB}
    sc = stream.Score()
    sc.metadata = metadata.Metadata()
    sc.metadata.composer = 'A. N. Other (1800-1900)'
    if how == 'parts':
        for v, name in zip(SATB, ('Soprano', 'Alto', 'Tenor', 'Bass')):
            p = line(events(V[v][0]), ts, ks, V[v][1])
            p.partName = name
            sc.insert(0, p)
    else:
        staves = []
        for hi, lo in (('S_notes', 'A_notes'), ('T_notes', 'B_notes')):
            if how == 'closed':
                if any(gaps(V[x][0]) for x in (hi, lo)):
                    return None                      # a voice resting in a closed staff reads as singing the other's notes
                st = stream.PartStaff()
                a, b = line(events(V[hi][0]), ts, ks, V[hi][1]), line(events(V[lo][0]), ts, ks, V[lo][1])
                for ma, mb in zip(a.getElementsByClass(stream.Measure), b.getElementsByClass(stream.Measure)):
                    m = stream.Measure(number=ma.number)
                    for el in ma.getElementsByClass(['KeySignature', 'TimeSignature', 'Clef']):
                        m.insert(el.offset, el)
                    va, vb = stream.Voice(id='1'), stream.Voice(id='2')
                    for el in ma.notesAndRests:
                        va.insert(el.offset, el)
                    for el in mb.notesAndRests:
                        vb.insert(el.offset, el)
                    m.insert(0, va)
                    m.insert(0, vb)
                    m.rightBarline = ma.rightBarline
                    st.append(m)
            else:                                    # chords: only where the two voices move together, undivided
                ga, gb = events(V[hi][0]), events(V[lo][0])
                if [e[:2] for e in ga] != [e[:2] for e in gb] or any(len(e[2]) > 1 for e in ga + gb):
                    return None
                if any(a[2][0].midi < b[2][0].midi for a, b in zip(ga, gb)):
                    return None                      # crossed voices can't be told apart on one stem
                st = line([(s, d, pa + pb) for (s, d, pa), (_, _, pb) in zip(ga, gb)], ts, ks, V[hi][1], stream.PartStaff)
            staves.append(st)
            sc.insert(0, st)
        sc.insert(0, layout.StaffGroup(staves, symbol='brace'))
    with tempfile.TemporaryDirectory() as d:
        return open(sc.write('musicxml', fp=os.path.join(d, 'c.musicxml')), 'rb').read()


@unittest.skipIf(music21 is None, 'needs music21 (pip install music21)')
class RoundTrip(unittest.TestCase):
    def test_every_chant(self):
        done = 0
        for r in paths.catalog():
            f = paths.chant_file(r['Chant'])
            text = f and paths.read(f)
            c = f and load_chant(f)
            if not f or not all(v in c['voices'] for v in SATB):
                continue
            ts, want = chantedit.parts(text)['time'], facts(text)
            for how in ('parts', 'closed', 'chords'):
                data = write(c, ts, how)
                if data is None:
                    continue
                with self.subTest(chant=r['Chant'], layout=how):
                    parts, info = musicxml.to_parts(data)
                    self.assertEqual(facts(chantedit.apply(chantedit.template(), parts)), want)
                    self.assertEqual(info['warnings'], [])
                    tonic, mode = c['key']
                    self.assertEqual(parts['key']['mode'], mode)
                done += 1
        self.assertGreater(done, 150)

    def test_bach_chorales(self):
        from music21 import converter, corpus
        files = [p for p in corpus.getComposer('bach') if str(p).endswith('.mxl')][::6]     # a sample, for speed
        same = 0
        for p in files:
            with open(p, 'rb') as fh:
                data = fh.read()
            with self.subTest(chorale=os.path.basename(str(p))):
                try:
                    parts, info = musicxml.to_parts(data, str(p))
                except ValueError:
                    continue                                       # refused, with a message: fine
                got = facts(chantedit.apply(chantedit.template(), parts))
                sc = converter.parse(p)
                named = {}
                for prt in sc.parts:
                    v = musicxml.voices_named(prt.partName or '')
                    if len(v) == 1:
                        named.setdefault(v[0], prt)
                if len(named) < 4:
                    continue                                       # five voices and the like: not a chant
                for v in SATB:
                    ref = [(n.pitches[-1].midi if isinstance(n, chord.Chord) else n.pitch.midi,
                            F(n.duration.quarterLength).limit_denominator(64) / 4)
                           for n in named[v].flatten().notes if not n.duration.isGrace]
                    ours_top = []                                  # a chord: compare its top note
                    i = 0
                    while i < len(got[v][0]):
                        m, s, d = got[v][0][i]
                        group = [x for x in got[v][0][i:] if x[1] == s]
                        ours_top.append((max(x[0] for x in group), d))
                        i += len(group)
                    self.assertEqual(ours_top, ref, v)
                same += 1
        self.assertGreater(same, len(files) * 0.9)


if __name__ == '__main__':
    unittest.main()

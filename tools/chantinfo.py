"""Facts read straight from a chant's LilyPond file: key, mode, single/double, soprano range, notes for playback."""
import os, re, sys
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from chantparse import load_chant      # noqa: E402

NAMES = ['C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B']


def key_label(tonic, mode):
    m = re.match(r'([a-g])(is|es|s)?', tonic)
    acc = {'is': '♯', 'es': '♭', 's': '♭', None: ''}[m.group(2)]
    return m.group(1).upper() + acc, mode


def first(x):
    return x[0] if isinstance(x, list) else x


def info(path, text=None):
    """The facts of the chant file at path (or of text, a chant not yet saved)."""
    c = load_chant(text, is_text=True) if text is not None else load_chant(path)
    tonic, mode = c['key'] or ('c', 'major')
    voices = {}
    for v, (notes, sections) in c['voices'].items():
        ev, starts = [], {}
        for n in notes:
            for h in (n if isinstance(n, list) else [n]):
                ev.append([h.midi, float(h.start), float(h.dur)])
                if h.section >= 1:
                    starts[h.section] = min(starts.get(h.section, h.start), h.start)
        voices[v] = {'events': ev, 'sections': sections, 'phrases': [float(starts[k]) for k in sorted(starts)]}
    melody = voices.get('S_notes') or voices.get('Unison_notes') or next(iter(voices.values()))
    sop = [e[0] for e in melody['events']]
    name = lambda m: NAMES[m % 12] + str(m // 12 - 1)
    k, md = key_label(tonic, mode)
    return {
        'key': k, 'mode': md,
        'double': len(melody['sections']) >= 4,
        'phrases': melody['phrases'],   # where each phrase after the first starts, in whole notes: Play breathes there
        'range': [name(min(sop)), name(max(sop))] if sop else None,
        'voices': {v: d['events'] for v, d in voices.items()},
    }

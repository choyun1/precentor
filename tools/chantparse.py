"""Parse the chant .ly files (S/A/T/B \\relative variables) into note events."""
import re
from fractions import Fraction as F
import ly.document, ly.pitch.rel2abs

STEP = {'c': 0, 'd': 1, 'e': 2, 'f': 3, 'g': 4, 'a': 5, 'b': 6}
PC = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
NOTE_RE = re.compile(r"^([a-g])((?:isis|eses|ses|sas|is|es|s)?)([',]*)([!?]?)(\d+)?(\.*)$")
VOICES = ['S_notes', 'A_notes', 'T_notes', 'B_notes']


def to_abs(text):
    d = ly.document.Document(text)
    ly.pitch.rel2abs.rel2abs(ly.document.Cursor(d))
    return d.plaintext()


def var_bodies(text):
    """{varname: body} for top-level `name = { ... }` (after rel2abs)."""
    out = {}
    for m in re.finditer(r'^(\w+)\s*=\s*\{', text, re.M):
        i = m.end() - 1
        depth, j = 0, i
        while j < len(text):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out[m.group(1)] = text[i + 1:j]
    return out


class Note:
    __slots__ = ('name', 'acc', 'oct', 'start', 'dur', 'bar', 'section', 'src')

    @property
    def midi(self):
        a = {'': 0, 'is': 1, 'isis': 2, 'es': -1, 's': -1, 'eses': -2, 'ses': -2, 'sas': -2}[self.acc]
        return 48 + 12 * self.oct + PC[self.name] + a  # c = C3 = 48

    @property
    def diat(self):  # diatonic step number, for interval-size checks
        return 7 * self.oct + STEP[self.name]

    def label(self):
        a = self.acc
        return self.name + a + ("'" * self.oct if self.oct > 0 else "," * -self.oct)


SMALL = '@'   # marks a cue-size head (\\tweak font-size #-3): printed for the organist, not sung or played
SMALL_RE = re.compile(r"(?:\\parenthesize\s+)?\\tweak\s+font-size\s+#?-[\d.]+\s+(?:\\parenthesize\s+)?"
                      r"([a-g](?:isis|eses|ses|sas|is|es|s)?[',]*[!?]?)")


def _drop_balanced(text, pattern):
    """text without each match of pattern and the bracketed group ({…}, (…)) or "string" that follows it."""
    out, i = [], 0
    for m in re.finditer(pattern, text):
        if m.start() < i:
            continue
        j = m.end()
        while j < len(text) and text[j] in ' \t\n':
            j += 1
        if j < len(text) and text[j] == '"':
            k = text.find('"', j + 1)
            j = len(text) if k < 0 else k + 1
        elif j < len(text) and text[j] in '{(':
            o, c = text[j], '}' if text[j] == '{' else ')'
            depth = 0
            while j < len(text):
                depth += {o: 1, c: -1}.get(text[j], 0)
                j += 1
                if depth == 0:
                    break
        out.append(text[i:m.start()] + ' ')
        i = j
    return ''.join(out) + text[i:]


def parse_voice(body):
    """Return (notes, sections) where sections = list of bar-counts per '||' section.
    Text (\\markup), brackets (\\set Score.repeatCommands) and cue-size heads are print only: a chord of
    nothing but cue-size heads takes its time like a rest."""
    body = re.sub(r'%[^\n]*', '', body)
    body = _drop_balanced(body, r'[_^-]?\\markup\b(?:\s*\\\w+)*')      # _\markup \italic "Unison."
    body = _drop_balanced(body, r"\\set\s+[\w.]+\s*=\s*#'?(?=\()")             # \set Score.repeatCommands = #'((volta "…"))
    body = SMALL_RE.sub(lambda m: m.group(1) + SMALL, body)
    body = re.sub(r'\\tweak\s+[\w.-]+\s+(?:#\S+|"[^"]*"|-?[\d.]+)', ' ', body)
    body = re.sub(r'\\(parenthesize|startMeasureSpanner|stopMeasureSpanner|hide|slurDown|slurUp)\b', ' ', body)
    body = re.sub(r'\\override\s+\S+\s*=\s*#\S+', ' ', body)
    body = re.sub(r'\\(set|unset)\s+\S+(\s*=\s*#\S+)?', ' ', body)
    body = re.sub(r'\\bar\s+"([^"]*)"', lambda m: ' BAR(%s) ' % m.group(1), body)
    toks = re.findall(r"<[^>]*>[\d.]*|BAR\([^)]*\)|\\\w+|[a-g](?:isis|eses|ses|sas|is|es|s)?[',]*[!?]?@?\d*\.*|[rsR]\d*\.*|\||\S", body)
    notes, sections = [], []
    t, dur, bar, bars_in_sec, sec = F(0), F(1, 4), 0, 0, 0
    bar_has = False
    for tok in toks:
        if tok.startswith('BAR('):
            if bar_has:
                bars_in_sec += 1; bar += 1; bar_has = False
            if '||' in tok or '|.' in tok:
                sections.append(bars_in_sec); bars_in_sec = 0; sec += 1
            continue
        if tok == '|':
            if bar_has:
                bars_in_sec += 1; bar += 1; bar_has = False
            continue
        if tok.startswith('\\') or tok in ('(', ')', '~', '[', ']', '-', '^', '_'):
            continue
        tok = tok.rstrip('()~[]')
        chord = None
        if tok.startswith('<'):
            m = re.match(r'<([^>]*)>([\d.]*)', tok)
            chord = m.group(1).split()
            durtxt = m.group(2)
            heads = chord
        else:
            heads, durtxt = [tok], None
        evs, small = [], []
        for h in heads:
            small.append(SMALL in h)
            h = h.replace(SMALL, '')
            m = NOTE_RE.match(h if chord is None else h + (durtxt or ''))
            if not m:
                mr = re.match(r'^[rsR](\d+)?(\.*)$', h)
                if mr:
                    if mr.group(1):
                        dur = F(1, int(mr.group(1))) * (F(3, 2) if mr.group(2) else 1)
                    t += dur; bar_has = True
                break
            n = Note()
            n.name, n.acc = m.group(1), m.group(2)
            n.oct = m.group(3).count("'") - m.group(3).count(",")
            if m.group(5):
                d = F(1, int(m.group(5)))
                for k in range(len(m.group(6))):
                    d += F(1, int(m.group(5))) / (2 ** (k + 1))
                dur = d
            n.dur, n.start, n.bar, n.section, n.src = dur, t, bar, sec, h
            evs.append(n)
        if evs and len(small) == len(evs) and all(small):  # only cue-size heads: silent here, like a rest
            t += dur; bar_has = True
            continue
        if evs:
            if len(small) == len(evs) and any(small):       # cue-size heads beside sung ones: print only
                evs = [n for n, sm in zip(evs, small) if not sm]
            # for divisi chords keep all heads; flag later
            for n in evs:
                n.dur = dur
            notes.append(evs if len(evs) > 1 else evs[0])
            t += dur; bar_has = True
    if bar_has or bars_in_sec:
        sections.append(bars_in_sec + (1 if bar_has else 0))
    return notes, sections


def load_chant(path_or_text, is_text=False):
    if is_text:
        text = path_or_text
    else:
        with open(path_or_text, encoding='utf-8') as fh:
            text = fh.read()
    key = re.search(r'\\key\s+(\w+)\s+\\(\w+)', text)
    comp = re.search(r'composer\s*=.*?"([^"]+)"', text)
    bodies = var_bodies(to_abs(text))
    voices = {}
    for v, body in bodies.items():
        if v.endswith('_notes') or v in ('descant',):
            voices[v] = parse_voice(body)
    return {'key': key.groups() if key else None, 'composer': comp.group(1) if comp else None,
            'voices': voices, 'raw': text}

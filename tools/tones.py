"""Gregorian psalm tones (Liber Usualis) applied to the pointed texts.

A tone is written as in the Liber: VIIa, 1D2, 8G, 4E, 2D, per (Tonus Peregrinus), and so on.
The formulas are in reference/psalm_tones.json (gabc notation, from the public-domain jgabc project).

How a half-verse is fitted to a cadence:
  * the cadence's accents fall on the last stressed syllables (taken from the Anglican pointing:
    the syllable after each | is stressed; unpointed texts fall back on a pronouncing dictionary);
  * syllables between accents go to the "open" note (written e.g. `jr`), however many there are;
  * fixed notes after the last accent each take a syllable; if there are too few syllables, the
    remaining notes are sung on the accented syllable (a melisma, marked with a slur);
  * preparatory notes take the syllables just before the first accent;
  * everything before is sung on the reciting note, the first verse starting with the intonation;
  * a line break inside the first half is a flex: its last stressed syllable drops to the flex note.
"""
import json, os, re, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import pointed, emit           # noqa: E402

import pyphen
try:
    import pronouncing
except ImportError:
    pronouncing = None

HY = pyphen.Pyphen(lang='en_US')
TONES = json.load(open(os.path.join(ROOT, 'reference', 'psalm_tones.json'), encoding='utf-8'))
ROMAN = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6, 'vii': 7, 'viii': 8}
UNSTRESSED = set('a an the and or but nor of to in on at by for from with as is are was were be been am '
                 'his her its my your our their thy thine mine me him us them it he she we they you i '
                 'that which who whom whose shall will would should may might can could do does did '
                 'have has had not no so than then there when where while if upon unto into o'.split())


# ------------------------------------------------------------- tones
def tone(name):
    """'VIIa' / '7a' / 'Tone 1 D2' / 'per' -> dict(label, clef, mediant, termination)"""
    s = re.sub(r'(?i)^tone\s*', '', name.strip()).replace(' ', '')
    if re.match(r'(?i)^per', s):
        t = TONES['per.']
        return {'label': 'Tonus peregrinus', 'clef': t['clef'], 'mediant': t['mediant'], 'termination': t['termination']}
    m = re.match(r'(?i)^(viii|vii|vi|iv|v|iii|ii|i|[1-8])\.?(.*)$', s)
    if not m:
        raise SystemExit(f'unknown tone {name!r}')
    n = int(m.group(1)) if m.group(1).isdigit() else ROMAN[m.group(1).lower()]
    ending = m.group(2)
    alt = ending.lower().startswith('alt')                    # "6alt": Tone VI's alternative mediant
    if alt:
        ending = ending[3:].lstrip('.')
    keys = ([f'{n}. alt'] if alt else [f'{n}.']) + ([f'{n}. alt'] if not alt and f'{n}. alt' in TONES else [])
    for k in keys:
        t = TONES[k]
        single = {2: 'D', 5: 'a', 6: 'F'}            # Liber names for tones with one ending
        terms = t.get('terminations') or {single.get(n, ''): t['termination']}
        if ending in terms or (ending == '' and len(terms) == 1):
            e = ending if ending in terms else next(iter(terms))
            roman = [k2 for k2, v in ROMAN.items() if v == n][0].upper()
            return {'label': f'Tone {roman}{e}' + (' (alt.)' if k.endswith('alt') and n == 6 else ''), 'clef': t['clef'],
                    'mediant': t['mediant'], 'termination': terms[e], 'flex': t.get('flex')}
    avail = sorted({e for k in keys for e in (TONES[k].get('terminations') or {'': 0})})
    raise SystemExit(f'tone {n} has no ending {ending!r}; endings: {", ".join(e or "(none)" for e in avail)}')


def parse_token(tok):
    """gabc token -> dict(accent, open, notes=[(letter, flat)])"""
    acc = tok.startswith("'")
    t = tok.lstrip("'")
    is_open = bool(re.search(r'r\.*$', t))
    t = re.sub(r'r(\.*)$', r'\1', t)
    notes, flats, i = [], set(), 0
    while i < len(t):
        ch = t[i]
        if ch.lower() in 'abcdefghijklm':
            if i + 1 < len(t) and t[i + 1] in 'xy':
                (flats.add if t[i + 1] == 'x' else flats.discard)(ch.lower())
                i += 2
                continue
            notes.append((ch.lower(), ch.lower() in flats))
        i += 1
    return {'accent': acc, 'open': is_open, 'notes': notes}


def formula(gabc):
    toks = [parse_token(t) for t in gabc.split()]
    first_open = next(i for i, t in enumerate(toks) if t['open'])
    intonation, tenor, rest = toks[:first_open], toks[first_open], toks[first_open + 1:]
    cad = []
    for t in rest:                       # consecutive open notes act as one
        if t['open'] and cad and cad[-1]['open']:
            continue
        cad.append(t)
    return {'intonation': intonation, 'tenor': tenor, 'cadence': cad}


def flex_note(tenor_letter, clef):
    """The flex: a tone below the tenor, or a minor third when the tone below is a semitone."""
    pitch = to_pitch(tenor_letter, clef)
    below = to_pitch(chr(ord(tenor_letter) - 1), clef)
    return chr(ord(tenor_letter) - (2 if (pitch - below) == 1 else 1))


# ------------------------------------------------------------- pitch
STEP_SEMI = [0, 2, 4, 5, 7, 9, 11]


def _ref(clef):
    line = int(clef[-1])
    return 3 + 2 * (line - 1), (0 if clef[0] == 'c' else 3)   # letter index of the clef line, its scale step (C=0, F=3)


def to_pitch(letter, clef):
    """midi number of a gabc letter (c clef line = C5, f clef line = F4)."""
    ref_idx, ref_step = _ref(clef)
    steps = ord(letter) - ord('a') - ref_idx
    base_oct = 5 if clef[0] == 'c' else 4
    d = ref_step + steps
    octv, step = base_oct + d // 7, d % 7
    return 12 * (octv + 1) + STEP_SEMI[step]


def to_lily(letter, flat, clef):
    ref_idx, ref_step = _ref(clef)
    d = ref_step + ord(letter) - ord('a') - ref_idx
    base_oct = 5 if clef[0] == 'c' else 4
    octv, step = base_oct + d // 7, d % 7
    name = 'cdefgab'[step] + ('es' if flat and step != 2 and step != 5 else ('s' if flat else ''))
    if flat and step in (2, 5):           # e-flat / a-flat spellings
        name = 'cdefgab'[step] + ('s' if step == 5 else 's')
        name = {'e': 'ees', 'a': 'aes'}['cdefgab'[step]]
    marks = octv - 3
    return name + ("'" * marks if marks > 0 else ',' * (-marks))


# ------------------------------------------------------------- syllables
def _cmu_count(word):
    if not pronouncing:
        return None
    ph = pronouncing.phones_for_word(word.lower())
    return pronouncing.syllable_count(ph[0]) if ph else None


def _cmu_stress(word):
    if not pronouncing:
        return None
    ph = pronouncing.phones_for_word(word.lower())
    return pronouncing.stresses(ph[0]) if ph else None


def split_word(core):
    """Letters of one word -> syllables (strings)."""
    if core.upper() in ('LORD', "LORD'S", 'GOD', "GOD'S"):
        return [core]
    parts = HY.inserted(core).split('-') if len(core) > 3 else [core]
    want = _cmu_count(re.sub(r"'s$", '', core))
    if want and len(parts) < want:
        # split further at vowel-group boundaries until the count matches the dictionary
        out = []
        for p in parts:
            groups = [m.start() for m in re.finditer(r'[aeiouy]+', p, re.I)]
            out.append(p) if len(groups) < 2 else out.extend(_vsplit(p))
        if len(out) <= want:
            parts = out
    return [p for p in parts if p]


def _vsplit(p):
    m = list(re.finditer(r'[aeiouy]+', p, re.I))
    cuts = []
    for a, b in zip(m, m[1:]):
        gap = p[a.end():b.start()]
        cuts.append(a.end() + (len(gap) // 2 if gap else 0))
    if not cuts and len(m) == 2:
        cuts = [m[0].end()]
    out, prev = [], 0
    for c in cuts:
        if 0 < c < len(p) and c > prev:
            out.append(p[prev:c])
            prev = c
    out.append(p[prev:])
    return out


def line_syllables(text):
    """One printed line of pointed text -> list of syllables dict(text, word, stress, join).

    join: how this syllable attaches to the previous one ('' inside a word, '-' after a hyphen, ' ' new word)."""
    toks = pointed.tokens(text)
    words, stress_next = [], False         # words: list of [text, [boundary offsets that are stressed], hyphen_before]
    for t in toks:
        if t == '|':
            stress_next = True
            continue
        if t in ('.', '*', '—'):
            continue
        t = t.replace('=', '')
        if words and words[-1][0].endswith('-') and t.startswith('-'):        # re- | -vives
            w = words[-1]
            off = len(w[0]) - 1
            w[0] = w[0][:-1] + t[1:]
            if stress_next:
                w[1].append(off)
        elif words and words[-1][0].endswith('-') and words[-1][0] != '-':    # loving- | kindness
            words.append([t, [0] if stress_next else [], True])
        else:
            words.append([t, [0] if stress_next else [], False])
        stress_next = False
    out = []
    for wi, (w, stressed, hyph) in enumerate(words):
        lead = re.match(r'^[^A-Za-z]*', w).group(0)
        trail = re.search(r'[^A-Za-z\']*$', w).group(0)
        core = w[len(lead):len(w) - len(trail)] if trail else w[len(lead):]
        if not core:
            if out:
                out[-1]['text'] += w
            continue
        sylls, joins, offs, pos = [], [], [], len(lead)
        for pi, part in enumerate(core.split('-')):          # a hyphen inside the word (white-robed) stays
            for si, s in enumerate(split_word(part) if part else []):
                sylls.append(s)
                joins.append('-' if pi and not si else '')
                offs.append(pos)
                pos += len(s)
            pos += 1
        sylls[0] = lead + sylls[0]
        sylls[-1] = sylls[-1] + trail
        offs[0] = 0
        marked = set()
        for b in stressed:
            k = max(i for i, o in enumerate(offs) if o <= max(b, 0)) if b else 0
            marked.add(k)
        for i, s in enumerate(sylls):
            out.append({'text': s, 'word': wi, 'stress': i in marked, 'pointed': bool(stressed),
                        'join': joins[i] if i else ('-' if hyph else ' '), 'core': core})
    return out


def word_stress(sylls):
    """Mark the stressed syllables of a line.

    Word stress comes from the pronouncing dictionary (primary and secondary stress); little words
    (the, of, my, you ...) are unstressed. Where the dictionary doesn't know a word, the Anglican
    pointing (the syllable after a bar) or else the first syllable is used."""
    words = {}
    for i, s in enumerate(sylls):
        words.setdefault(s['word'], []).append(i)
    for w, idx in words.items():
        core = re.sub(r"'s$", '', sylls[idx[0]]['core'])
        pointed_here = [i for i in idx if sylls[i]['stress']]
        for i in idx:
            sylls[i]['stress'] = False
        if core.lower() in UNSTRESSED:
            continue
        if len(idx) == 1:
            sylls[idx[0]]['stress'] = True
            continue
        st = _cmu_stress(core)
        if st and len(st) == len(idx):
            for k, i in enumerate(idx):
                sylls[i]['stress'] = st[k] == '1'
        elif pointed_here:
            sylls[pointed_here[0]]['stress'] = True
        else:
            sylls[idx[0]]['stress'] = True
    return sylls


# ------------------------------------------------------------- fitting
def fit_region(m, toks):
    """Fit m syllables to a token run (open tokens take any number). -> (list of note-lists, leftover notes)"""
    fixed = [t for t in toks if not t['open']]
    if m >= len(fixed):
        extra, out, used_extra = m - len(fixed), [], False
        for t in toks:
            if t['open']:
                if not used_extra:
                    out += [('open', t['notes'])] * extra
                    used_extra = True
            else:
                out.append(('fin', t['notes']))
        if not used_extra and extra:                      # no open note: repeat the first note
            out = [('open', fixed[0]['notes'])] * extra + out
        return out, []
    keep = fixed[len(fixed) - m:] if m else []
    left = [n for t in fixed[:len(fixed) - m] for n in t['notes']]
    return [('fin', t['notes']) for t in keep], left


def apply(sylls, part, clef, intonation=False):
    """Give each syllable of a half-verse its notes and role. Changes sylls in place."""
    f = formula(part)
    cad = f['cadence']
    acc_tok = [i for i, t in enumerate(cad) if t['accent']]
    k = len(acc_tok)
    n = len(sylls)
    for s in sylls:
        s['notes'], s['role'] = f['tenor']['notes'], 'ten'
    # accent syllables: the last k stressed syllables
    stressed = [i for i, s in enumerate(sylls) if s['stress']]
    acc = stressed[-k:] if len(stressed) >= k else []
    if len(acc) < k:                                   # not enough stresses: count back in twos
        acc = sorted({max(0, n - 1 - 2 * j) for j in range(k)})
    # after each accent
    bounds = acc + [n]
    for j in range(k):
        a = acc[j]
        toks = cad[acc_tok[j] + 1: acc_tok[j + 1] if j + 1 < k else len(cad)]
        m = bounds[j + 1] - a - 1
        notes, left = fit_region(m, toks)
        if j == k - 1 and a == n - 1:
            left = []      # an abrupt cadence: the half-verse ends on its accent, which takes the accent note only
        sylls[a]['notes'] = cad[acc_tok[j]]['notes'] + left
        sylls[a]['role'] = 'acc'
        for i, (role, nts) in enumerate(notes):
            sylls[a + 1 + i]['notes'], sylls[a + 1 + i]['role'] = nts, role
    # preparatory notes before the first accent
    prep = [t for t in cad[:acc_tok[0]] if not t['open']] if k else []
    start = acc[0] if k else n
    q = min(len(prep), start)
    for i in range(q):
        sylls[start - q + i]['notes'] = prep[len(prep) - q + i]['notes']
        sylls[start - q + i]['role'] = 'prep'
    cad_start = start - q
    # intonation
    if intonation and f['intonation'] and cad_start >= len(f['intonation']):
        for i, t in enumerate(f['intonation']):
            sylls[i]['notes'], sylls[i]['role'] = t['notes'], 'int'
    return sylls


def point_verse(v, t, first=False):
    """A verse -> dict(n, dagger, halves=[[line sylls, ...], [line sylls, ...]], flex=[...])."""
    halves = [[], []]
    for ln in v['lines']:
        h = halves[ln['half'] - 1]
        sy = line_syllables(ln['text'])
        if ln['wrap'] and h:
            if sy:
                sy[0]['join'] = ' '
            h[-1].extend(sy)
        else:
            h.append(sy)
    for h in halves:
        for line in h:
            word_stress(line)
    tenor = formula(t['mediant'])['tenor']['notes'][0][0]
    fx = t.get('flex') or flex_note(tenor, t['clef'])
    for hi, h in enumerate(halves):
        if not h:
            continue
        part = t['mediant'] if hi == 0 else t['termination']
        for li, line in enumerate(h):
            if li < len(h) - 1:
                ten = formula(part)['tenor']['notes']
                for s in line:
                    s['notes'], s['role'] = ten, 'ten'
                if hi == 0:
                    # the flex (Liber usualis): the last accent stays on the reciting note and the voice drops
                    # on the syllables after it; on a final accented syllable (a monosyllable) it drops there
                    st = [i for i, s in enumerate(line) if s['stress']] or [len(line) - 1]
                    a = st[-1]
                    for i in range(a + 1 if a < len(line) - 1 else a, len(line)):
                        line[i]['notes'], line[i]['role'] = [(fx, False)], 'flex'
                    line[a]['flexacc'] = True
                    line[-1]['flexend'] = True
                if hi == 0 and li == 0 and first:      # the intonation opens the verse, even before a flex
                    ints = formula(part)['intonation']
                    if ints and len(line) > len(ints) and all(line[i]['role'] == 'ten' for i in range(len(ints))):
                        for i, tk in enumerate(ints):
                            line[i]['notes'], line[i]['role'] = tk['notes'], 'int'
                        line[0]['int_open'] = line[len(ints) - 1]['int_close'] = True
            else:
                apply(line, part, t['clef'], intonation=(first and hi == 0 and li == 0))
                ints = [s for s in line if s['role'] == 'int']
                if ints:
                    ints[0]['int_open'], ints[-1]['int_close'] = True, True
    return {'n': v['n'], 'dagger': v['dagger'], 'halves': halves}


# ------------------------------------------------------------- text output
def syl_markup(s, cad_mark):
    text, tail = s['text'], ''
    if s['role'] == 'int' and s.get('int_close'):          # (My God), my God: punctuation after the bracket
        m = re.match(r'^(.*?)([,;:.!?\'"’”]*)$', text)
        text, tail = m.group(1), m.group(2)
    pieces = emit._text(emit.curly(text))
    mk = emit._cat(pieces)
    if s['role'] in ('acc',) or s.get('flexacc'):
        mk = '\\bold ' + mk
    if s['role'] in ('acc', 'fin', 'prep', 'open', 'int') and len(s['notes']) > 1:
        mk = '\\slurunder ' + mk
    if s['role'] == 'int':                    # the intonation: in brackets and italic, (My God), my God …
        mk = '\\italic ' + mk
        if s.get('int_open') or s.get('int_close'):
            close = (' ' + emit.lystr(')' + emit.curly(tail))) if s.get('int_close') else ''
            mk = '\\concat { %s%s%s }' % ('"(" ' if s.get('int_open') else '', mk, close)
    if cad_mark:
        mk = '\\concat { \\tonebar ' + mk + ' }'
    return mk


def line_markup(sylls, star=False):
    words, cur = [], []
    first_cad = next((i for i, s in enumerate(sylls) if s['role'] in ('prep', 'acc')), None)
    for i, s in enumerate(sylls):
        if s['join'] == ' ' and cur:
            words.append(cur)
            cur = []
        if s['join'] == '-' and cur and not sylls[i - 1]['text'].endswith('-'):   # loving- | kindness has its hyphen already
            cur.append('"-"')
        cur.append(syl_markup(s, i == first_cad))
    if cur:
        words.append(cur)
    out = ' '.join(('\\concat { ' + ' '.join(w) + ' }') if len(w) > 1 else w[0] for w in words)
    if sylls and sylls[-1].get('flexend'):
        out += ' \\flexmark'
    if star:
        out += ' "*"'
    return out


def verse_lines(pv):
    lines = []
    for hi, h in enumerate(pv['halves']):
        for li, line in enumerate(h):
            star = hi == 0 and li == len(h) - 1
            body = line_markup(line, star)
            if hi == 0 and li == 0:
                lead = '\\vstart %s ##f' % emit.lystr(str(pv['n']))
            elif hi == 0:
                lead = "\\ind #'flex"
            else:
                lead = "\\ind #'second"
            lines.append('  \\line { %s %s }' % (lead, body))
    return lines


def single_block(title, pvs):
    rows = []
    for i, pv in enumerate(pvs):
        if i:
            rows.append('  \\versegap')
        rows += verse_lines(pv)
    text = '\\psalmtext {\n' + '\n'.join(rows) + '\n}'
    if not title:
        return '\\markup ' + text
    # the title stays its own size; only the verses are set at text-size
    return ('\\markup { \\override #(cons \'baseline-skip line-spacing) \\column {\n  ' + title +
            '\n  \\vspace #(* 0.5 verse-gap)\n' + text + '\n} }')


def verse_markup(pv):
    lines = []
    for hi, h in enumerate(pv['halves']):
        for li, line in enumerate(h):
            star = hi == 0 and li == len(h) - 1
            body = line_markup(line, star)
            if hi == 0 and li == 0:
                lead = '\\vstart %s ##f' % emit.lystr(str(pv['n']))
            elif hi == 0:
                lead = "\\ind #'flex"
            else:
                lead = "\\ind #'second"
            lines.append('  \\line { %s %s }' % (lead, body))
    return '\\markup \\psalmtext {\n' + '\n'.join(lines) + '\n}'


# ------------------------------------------------------------- notation
def _notes_ly(notes, clef, dur, slur=True):
    ps = [to_lily(l, fl, clef) for l, fl in notes]
    if len(ps) == 1:
        return ps[0] + dur
    return ps[0] + dur + ('(' if slur else '') + ' ' + ' '.join(ps[1:]) + (')' if slur else '')


def _lyric(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


def verse_score(pv, t):
    """Verse fully set to the notes: reciting text under one long note, cadence syllable by syllable."""
    clef = t['clef']
    music, lyr = [], []
    for hi, h in enumerate(pv['halves']):
        # lines of the second half run on (no flex); first-half lines are kept apart by their flex
        if hi == 1 and len(h) > 1:
            merged = []
            for line in h:
                if merged and line:
                    line = [dict(line[0], join=' ')] + line[1:]
                merged.extend(line)
            h = [merged]
        for li, line in enumerate(h):
            i = 0
            while i < len(line):
                s = line[i]
                if s['role'] == 'ten':
                    j = i
                    while j < len(line) and line[j]['role'] == 'ten':
                        j += 1
                    txt = ''.join((x['join'] if k else (x['join'].strip() and x['join'])) + x['text'] for k, x in enumerate(line[i:j]))
                    music.append(_notes_ly(s['notes'], clef, '1'))
                    lyr.append('\\once \\override LyricText.self-alignment-X = #LEFT ' + _lyric(emit.curly(txt.strip())))
                    i = j
                    continue
                music.append(_notes_ly(s['notes'], clef, '4'))
                txt = emit.curly(s['text'])
                nxt = line[i + 1] if i + 1 < len(line) else None
                hyph = nxt is not None and nxt['join'] == ''
                lyr.append(_lyric(txt) + (' --' if hyph else ''))
                i += 1
            if li < len(h) - 1:
                music.append('\\bar "\'"' if hi == 0 else '')
        music.append('\\bar "|"' if hi == 0 else '\\bar "||"')
    return music, lyr


def formula_score(t, parts=('mediant', 'termination')):
    """The tone itself: intonation, reciting note, mediant || reciting note, termination (or just some parts)."""
    clef = t['clef']
    out = []
    for part in parts:
        f = formula(t[part])
        toks = (f['intonation'] if part == 'mediant' else []) + [f['tenor']] + f['cadence']
        for tk in toks:
            if tk is f['tenor']:
                out.append(_notes_ly(tk['notes'], clef, '1'))
                continue
            note = _notes_ly(tk['notes'], clef, '4')
            if tk['open']:
                note = '\\parenthesize ' + note
            if tk['accent']:
                note = note.replace('4', '4^\\markup { \\fontsize #-2 "´" }', 1)
            out.append(note)
        out.append('\\bar "|"' if part == 'mediant' else '\\bar "||"')
    return out


SCORE_LAYOUT = r'''
  \layout {
    indent = 0
    #(layout-set-staff-size 27)
    \context { \Staff \remove "Time_signature_engraver"
      \override StaffSymbol.line-count = 4
      \override Clef.font-size = #2
      \override Accidental.alteration-glyph-name-alist = #alteration-vaticana-glyph-name-alist }
    \context { \Voice
      \override NoteHead.style = #'vaticana.punctum
      \override NoteHead.font-size = #3.5
      \override Stem.transparent = ##t \override Flag.transparent = ##t
      \override Slur.transparent = ##t }
    \context { \Score \override SpacingSpanner.base-shortest-duration = #(ly:make-moment 1/32) }
    \context { \Lyrics \override LyricSpace.minimum-distance = #1.0 \override LyricText.font-size = #-2.6
      \override StanzaNumber.font-size = #-2.6 }
  }'''


def clef_ly(clef):
    """A movable C (or F) clef on the gabc line, on a four-line staff: only the relative pitch matters."""
    line = int(clef[-1])
    pos = -3 + 2 * (line - 1)
    if clef[0] == 'c':
        return ('\\set Staff.clefGlyph = "clefs.vaticana.do" \\set Staff.clefPosition = #%d '
                '\\set Staff.middleCPosition = #%d' % (pos, pos - 7))
    return ('\\set Staff.clefGlyph = "clefs.vaticana.fa" \\set Staff.clefPosition = #%d '
            '\\set Staff.middleCPosition = #%d' % (pos, pos - 3))


def score_ly(music, lyrics=None, label=None, stanza=None, clef='c4'):
    m = ' '.join(x for x in music if x)
    s = '\\score {\n  <<\n    \\new Staff {\n      \\cadenzaOn ' + clef_ly(clef) + '\n'
    s += '      \\new Voice = "v" { ' + m + ' }\n    }\n'
    if lyrics:
        st = ('\\set stanza = %s ' % _lyric(stanza)) if stanza else ''
        s += '    \\new Lyrics \\lyricsto "v" { ' + st + ' '.join(lyrics) + ' }\n'
    s += '  >>' + SCORE_LAYOUT + '\n}'
    return s

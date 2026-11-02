"""Editing a chant from the chant browser: its notes, voice by voice, its key and time, its credit line,
and its facts in the catalog. The launcher (serve.py) calls these; nothing here runs on its own.

A chant file keeps its layout (the score block, staff setup and anything unusual); only the parts the
editor shows are replaced: the \\key and \\time in `global`, the composer credit in the \\header, and the
body (and starting pitch) of each `X_notes = \\relative p { … }` voice.
"""
import csv, hashlib, os, re, shutil, sys, tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths   # noqa: E402

VOICE_RE = re.compile(r'^(?P<var>\w+_notes)\s*=\s*\\relative\s+(?P<start>\S+)\s*\{', re.M)
KEY_RE = re.compile(r'\\key\s+(?P<tonic>[a-g](?:is|es|s)?)\s*\\(?P<mode>\w+)')
TIME_RE = re.compile(r'\\time\s+(?P<time>\d+/\d+)')
CREDIT_RE = re.compile(r'(composer\s*=\s*\\markup\s*\{[^}]*?\\italic\s*)"(?P<credit>[^"]*)"')
LABELS = {'S_notes': 'Soprano', 'A_notes': 'Alto', 'T_notes': 'Tenor', 'B_notes': 'Bass',
          'Unison_notes': 'Unison', 'descant_notes': 'Descant'}
PREVIEWS = os.path.join(tempfile.gettempdir(), 'precentor-previews')     # pictures of chants being edited


def _body_end(text, open_brace):
    depth = 0
    for j in range(open_brace, len(text)):
        depth += {'{': 1, '}': -1}.get(text[j], 0)
        if depth == 0:
            return j
    raise ValueError('a { without its }')


def template(credit=''):
    """A new double chant, in the layout of the others: four voices of placeholder notes to replace."""
    return TEMPLATE.replace('@CREDIT@', credit.replace('"', "'"))


def parts(text):
    """What the editor shows: {key: {tonic, mode}, time, credit, voices: [{var, label, start, body}]}."""
    k, t, c = KEY_RE.search(text), TIME_RE.search(text), CREDIT_RE.search(text)
    voices = []
    for m in VOICE_RE.finditer(text):
        end = _body_end(text, m.end() - 1)
        body = text[m.end():end]
        lines = [l.rstrip() for l in body.strip('\n').split('\n')]
        indent = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
        voices.append({'var': m.group('var'), 'label': LABELS.get(m.group('var'), m.group('var')),
                       'start': m.group('start'), 'body': '\n'.join(l[indent:] for l in lines)})
    return {'key': {'tonic': k.group('tonic'), 'mode': k.group('mode')} if k else None,
            'time': t.group('time') if t else '', 'credit': c.group('credit') if c else '', 'voices': voices}


def apply(text, new):
    """text with the editor's parts put in (new: as parts() gives them)."""
    if new.get('key') and KEY_RE.search(text):
        tonic, mode = new['key']['tonic'], new['key']['mode']
        if not re.fullmatch(r'[a-g](?:is|es|s)?', tonic) or mode not in ('major', 'minor', 'dorian', 'mixolydian',
                                                                          'phrygian', 'lydian', 'aeolian', 'ionian'):
            raise ValueError('a key like aes major, fis minor')
        text = KEY_RE.sub(lambda m: f'\\key {tonic} \\{mode}', text, count=1)
    if new.get('time') and TIME_RE.search(text):
        if not re.fullmatch(r'\d+/\d+', new['time']):
            raise ValueError('a time signature like 2/4')
        text = TIME_RE.sub(lambda m: f"\\time {new['time']}", text, count=1)
    if 'credit' in new and CREDIT_RE.search(text):
        credit = ' '.join(str(new['credit']).split()).replace('"', "'").replace('\\', '')
        text = CREDIT_RE.sub(lambda m: m.group(1) + f'"{credit}"', text, count=1)
    for v in new.get('voices', []):
        m = next((m for m in VOICE_RE.finditer(text) if m.group('var') == v['var']), None)
        if not m:
            continue
        if not re.fullmatch(r"[a-g](?:is|es|s)?[',]*", v.get('start', m.group('start'))):
            raise ValueError(f"{v['var']}: the starting note is a pitch, like g' or c")
        if v['body'].count('{') != v['body'].count('}'):
            raise ValueError(f"{LABELS.get(v['var'], v['var'])}: a {{ without its }} (or the other way round)")
        end = _body_end(text, m.end() - 1)
        if not v['body'].strip():                     # a voice left empty: silent, its bars kept (spacers)
            v = dict(v, body=spacers(text[m.end():end - 1]))
        body = '\n'.join('  ' + l if l.strip() else '' for l in v['body'].strip('\n').split('\n'))
        head = f"{v['var']} = \\relative {v.get('start', m.group('start'))} {{"
        text = text[:m.start()] + head + '\n' + body + '\n' + text[end:]
    return text


SOUNDING = re.compile(r"(?<![\\\w])(?:<[^>]*>|[a-g](?:isis|eses|is|es|s)?[',]*|r)(?=[\d.~?!\s|\\]|$)")


def spacers(body):
    """A voice's notes made silent, their lengths and bars kept: 'a2 | <d fis>4 e~ |' -> 's2 | s4 s |'."""
    return re.sub(r'[~?!]', '', SOUNDING.sub('s', body)).strip('\n')


def service_text(text, music):
    """A chant file as one service has it: music is {var: (start, body)} for the voices changed for that service,
    or {var: None} for a voice that doesn't sing there."""
    p = parts(text)
    for v in p['voices']:
        if v['var'] in music:
            got = music[v['var']]
            v['start'], v['body'] = (v['start'], '') if got is None else got
    return apply(text, p)


def check(text):
    """(problems, facts): the voices must agree phrase by phrase; a chant is single (2 phrases) or double (4)."""
    import chantinfo
    from chantparse import load_chant
    problems = []
    try:
        c = load_chant(text, is_text=True)
        facts = chantinfo.info(None, text)
    except Exception as e:
        return [f'cannot read the notes: {e}'], None
    secs = {v: s for v, (_, s) in c['voices'].items() if v in LABELS and not v.startswith('descant')}   # not a pedal
    if not secs:
        problems.append('no voices (S_notes = \\relative … { … })')
    shapes = {v: s for v, s in secs.items()}
    first = next(iter(shapes.values()), [])
    for v, s in shapes.items():
        if s != first:
            problems.append(f"{LABELS.get(v, v)} has {len(s)} phrases of {', '.join(map(str, s))} bars; "
                            f"{LABELS.get(next(iter(shapes)), '')} has {len(first)} of {', '.join(map(str, first))}")
    if first and len(first) not in (2, 4):
        problems.append(f'{len(first)} phrases: a single chant has 2 (|| between them), a double 4')
    tm = re.search(r'\\time\s+(\d+)/(\d+)', text)
    if tm and int(tm.group(2)):                   # each bar as long as the time signature says
        from fractions import Fraction
        whole = Fraction(int(tm.group(1)), int(tm.group(2)))
        for v, (notes, _) in c['voices'].items():
            bars = {}
            for n in notes:
                h = n[0] if isinstance(n, list) else n
                bars[h.bar] = bars.get(h.bar, 0) + Fraction(h.dur)
            off = [(b, x) for b, x in sorted(bars.items()) if x != whole]
            if off:
                b, x = off[0]
                more = f' (and {len(off) - 1} more)' if len(off) > 1 else ''
                problems.append(f"{LABELS.get(v, v)}: bar {b + 1} is {'too long' if x > whole else 'too short'} "
                                f"for {tm.group(1)}/{tm.group(2)}{more}")
    return problems, facts


def render(text, shift=0):
    """A picture of the chant as written (or transposed): -> (file name in PREVIEWS, error)."""
    import build, browser
    os.makedirs(PREVIEWS, exist_ok=True)
    name = hashlib.sha1(f'{shift}\n{text}'.encode()).hexdigest()[:16] + '.png'
    out = os.path.join(PREVIEWS, name)
    if os.path.exists(out):
        return name, None
    try:
        c = build.read_chant('preview', text)
        c['name'] = 'preview'
        if shift:
            build.transpose(c, shift)
    except (SystemExit, ValueError) as e:
        return None, str(e)
    ok = browser.draw(build.lilypond_exe(), 'preview', out, c)
    olds = sorted((os.path.join(PREVIEWS, f) for f in os.listdir(PREVIEWS)), key=os.path.getmtime)
    for f in olds[:-60]:                          # keep the last few dozen
        os.remove(f)
    return (name, None) if ok else (None, 'LilyPond could not draw it: look for a typing slip in the notes')


def catalog_path(name, private=None):
    """The catalog.csv beside the chant's file (for a new one: the parish's if private, else the public one)."""
    f = paths.chant_file(name)
    if f:
        return os.path.join(os.path.dirname(f), 'catalog.csv')
    d = paths.CHANT_DIRS[-1] if private and len(paths.CHANT_DIRS) > 1 else paths.CHANT_DIRS[0]
    return os.path.join(d, 'catalog.csv')


def save_details(name, fields, private=None):
    """Write a chant's row in its catalog (made if new). -> the catalog's path."""
    p = catalog_path(name, private)
    rows = []
    if os.path.exists(p):
        with open(p, encoding='utf-8', newline='') as fh:
            rows = list(csv.DictReader(fh))
    row = next((r for r in rows if r['Chant'] == name), None)
    if row is None:
        row = {k: '' for k in paths.CATALOG_COLUMNS}
        row['Chant'] = name
        rows.append(row)
    for k in paths.CATALOG_COLUMNS[1:]:
        if k in fields:
            row[k] = ' '.join(str(fields[k] or '').split())
    rows.sort(key=lambda r: [(int(t) if t.isdigit() else t.lower()) for t in re.split(r'(\d+)', r['Chant'])])
    with open(p, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, paths.CATALOG_COLUMNS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return p


def save_music(name, text, private=None):
    """Write a chant's file (a new one goes beside its catalog). -> its path."""
    problems, _ = check(text)
    p = paths.chant_file(name) or os.path.join(os.path.dirname(catalog_path(name, private)), name + '.ly')
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(text)
    shutil.move(tmp, p)
    return p, problems


TEMPLATE = r'''\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "@CREDIT@"}
  tagline=#f
}

global = {
  \key c \major
  \time 2/4
}


S_notes = \relative c'' {
  c2 | c4 c | c2 \bar "||"
  c2 | c4 c | c4 c | c2 \bar "||"
  c2 | c4 c | c2 \bar "||"
  c2 | c4 c | c4 c | c2 \bar "||"
}

A_notes = \relative c' {
  e2 | e4 e | e2 \bar "||"
  e2 | e4 e | e4 e | e2 \bar "||"
  e2 | e4 e | e2 \bar "||"
  e2 | e4 e | e4 e | e2 \bar "||"
}

T_notes = \relative c' {
  g2 | g4 g | g2 \bar "||"
  g2 | g4 g | g4 g | g2 \bar "||"
  g2 | g4 g | g2 \bar "||"
  g2 | g4 g | g4 g | g2 \bar "||"
}

B_notes = \relative c {
  c2 | c4 c | c2 \bar "||"
  c2 | c4 c | c4 c | c2 \bar "||"
  c2 | c4 c | c2 \bar "||"
  c2 | c4 c | c4 c | c2 \bar "||"
}

% Use markup to center the chant on the page
\markup {
  \fill-line {
    \score {  % centered
      <<
        \new ChoirStaff <<
          \new Staff <<
            \global
            \clef "treble"
            \new Voice = "Soprano" <<
              \voiceOne \S_notes
            >>
            \new Voice = "Alto" <<
              \voiceTwo \A_notes
            >>
          >>
          \new Staff <<
            \global
            \clef "bass"
            \new Voice = "Tenor" <<
              \voiceOne \T_notes
            >>
            \new Voice = "Bass" <<
              \voiceTwo \B_notes
            >>
          >>
        >>
      >>

      \layout {
        \context {
          \Staff
          \remove "Time_signature_engraver"
        }
      }
    }  % End score
  }
}  % End markup
'''

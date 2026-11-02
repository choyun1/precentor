#!/usr/bin/env python3
"""Build a Sunday's psalm: the choir PDF and the numbered images for the parish administrator.

    python tools/build.py parish/sundays/2024-03-03.txt     # PDF + images
    python tools/build.py parish/sundays/2024-03-03.txt --pdf-only
    python tools/build.py parish/sundays/2024-03-03.txt --check     # only run the checks

A Sunday file looks like this (one item per line; # starts a comment):

    date:    2024-03-03
    service: Eucharist                # Eucharist (default) | Office | Evensong
    psalm:   19                       # or 19:1-6, 72:1-7,18-19, 89 Part 1, 89:20-37, 119 Aleph, Canticle 16
    chant:   Wesley-2                 # the chant the psalm starts with
    chant:   Smart-1 from 7           # change chant at verse 7
    chant:   Wesley-2 from 13
    chant:   Turle-2 down 2           # transposed: up or down so many semitones (here D minor to C minor)
    verse:   7  And let them | know that this | is your | hand, *       # this Sunday's pointing of a verse,
                that | you, O | Lord, have | done it.                  # the text's own left as it is
    tone:    VIIa                     # instead of chant: a Gregorian psalm tone (Liber Usualis), e.g. VIIa, 1D2, 8G, per
    gloria:  no                       # default: yes for Office/Evensong, no otherwise
    reprint: yes                      # reprint the chant at the top of a page (default yes)
    choir:   no                       # no choir this week: the psalm is said, so nothing to build
    sung:    yes                      # confirmed as sung: only then does it count in the history

Several psalm: lines may follow one another; chant: lines belong to the psalm above them, and a
psalm with no chant: line of its own continues with the previous chant.

Outputs go to output/<file name>/: psalm_<file name>.pdf, .ly (editable), admin/NN_*.jpg.
Two services on one day: name the files e.g. 2026-12-24-early.txt and 2026-12-24-midnight.txt.
"""
import argparse, os, re, shutil, subprocess, sys, tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import pointed, emit, tones, paths                    # noqa: E402

PINNED_LILYPOND = '2.26.0'
LY_VERSION = '2.24.0'          # syntax level of the generated files; compiles on 2.24 and later
STYLE = os.path.join(ROOT, 'style', 'psalm-style.ily')


# ================================================================== input
def parse_sunday(path):
    import service
    s = {'date': None, 'service': 'Eucharist', 'gloria': None, 'reprint': True, 'sung': False, 'choir': True,
         'items': [], 'music': [], 'chant_music': {}}
    verse = None                                   # a verse: line, collecting its indented lines
    for raw in paths.read(path).splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if verse is not None and raw[:1] in ' \t':
            verse.append(line)
            continue
        if verse is not None:
            _pointing(s, verse, path)
            verse = None
        key, _, val = line.partition(':')
        key, val = key.strip().lower(), val.strip()
        if key == 'date':
            s['date'] = val
        elif key == 'service':
            s['service'] = val
        elif key == 'gloria':
            s['gloria'] = val.lower() in ('yes', 'y', 'true', 'on')
        elif key == 'reprint':
            s['reprint'] = val.lower() in ('yes', 'y', 'true', 'on')
        elif key == 'sung':
            s['sung'] = val.lower() in ('yes', 'y', 'true', 'on')
        elif key == 'choir':
            s['choir'] = val.lower() not in ('no', 'n', 'false', 'off', 'none')
        elif key == 'psalm':
            s['items'].append({'spec': val, 'chants': []})
        elif key == 'intonation':
            # a psalm tone's intonation on every verse ("every verse") or on the first only ("first verse", the usual)
            if not s['items']:
                raise SystemExit(f'{path}: an intonation: line must come after a psalm: line')
            s['items'][-1]['intonation'] = 'every' if val.lower().startswith(('every', 'all', 'yes')) else 'first'
        elif key == 'optional':
            # the psalm above: sing its optional (bracketed) verses or not, whatever parish.txt says
            if not s['items']:
                raise SystemExit(f'{path}: an optional: line must come after a psalm: line')
            s['items'][-1]['optional'] = val.lower() in ('yes', 'y', 'true', 'on', 'sing', 'include')
        elif key in ('dagger', 'daggers'):
            # this Sunday's second-half repeats for the psalm above, replacing the ones marked in the text
            if not s['items']:
                raise SystemExit(f'{path}: a {key}: line must come after a psalm: line')
            v = val.lower().strip()
            try:
                s['items'][-1]['daggers'] = set() if v in ('none', 'no', '-', '') else \
                    {int(x) for x in re.split(r'[\s,]+', v.replace('†', '').replace('v.', '')) if x}
            except ValueError:
                raise SystemExit(f'{path}: cannot read {key} line {val!r} (verse numbers, e.g. "daggers: 7, 15", or "none")')
        elif key == 'verse':
            if not s['items']:
                raise SystemExit(f'{path}: a verse: line must come after a psalm: line')
            verse = [val]
        elif key in ('chant', 'tone'):
            if not s['items']:
                raise SystemExit(f'{path}: a {key}: line must come after a psalm: line')
            m = re.match(r'^(.+?)(?:\s+from\s+(\d+))?$', val)
            if not m or re.match(r'^from\s+\d+$', val):
                raise SystemExit(f'{path}: cannot read {key} line {val!r}')
            name = m.group(1).strip()
            if key == 'tone':
                name = 'tone:' + name.replace(' ', '')
            else:
                name = paths.canonical(name)            # 'Turle-5' (a copy of Turle-2) -> 'Turle-2 down 2'
            s['items'][-1]['chants'].append((name, int(m.group(2)) if m.group(2) else None))
        elif key == 'music':
            # a voice of the chant above as this service has it: "music: A_notes c' d2 | …", or "music: T_notes silent"
            chants = s['items'][-1]['chants'] if s['items'] else []
            if not chants or is_tone(chants[-1][0]):
                raise SystemExit(f'{path}: a music: line must come after a chant: line')
            mm = re.match(r"^([STAB]_notes|Unison_notes|Descant_notes)\s+(silent|[a-g](?:is|es|s)?[',]*\s+(.+))$", val)
            if not mm:
                raise SystemExit(f'{path}: cannot read the music: line {val!r} (a voice, its first pitch, its notes; '
                                 'or a voice and "silent")')
            base = paths.split_chant(chants[-1][0])[0]
            got = None if mm.group(2) == 'silent' else (mm.group(2).split()[0], mm.group(3).replace('\\bar "||" ', '\\bar "||"\n'))
            s['chant_music'].setdefault(base, {})[mm.group(1)] = got
        elif key in service.KEYS:
            s['music'].append((key, val))         # the rest of the service
        else:
            raise SystemExit(f'{path}: unknown line {line!r}')
    if verse is not None:
        _pointing(s, verse, path)
    if s['gloria'] is None:
        s['gloria'] = s['service'].lower() in ('office', 'evensong', 'morning prayer', 'evening prayer')
    if not s['date']:
        stem = os.path.splitext(os.path.basename(path))[0]
        s['date'] = stem if re.match(r'^\d{4}-\d\d-\d\d', stem) else ''     # a psalm on its own may have no date
    return s


def _pointing(s, lines, path):
    """A verse: line and the indented lines after it -> this Sunday's pointing of that verse, for the psalm above."""
    try:
        vs = pointed.parse('x\n' + '\n'.join([lines[0]] + ['    ' + l for l in lines[1:]]))['verses']
    except ValueError as e:
        raise SystemExit(f'{path}: cannot read the verse: line {lines[0]!r} ({e})')
    if len(vs) != 1:
        raise SystemExit(f'{path}: a verse: line holds one verse, its number first: {lines[0]!r}')
    s['items'][-1].setdefault('pointing', {})[vs[0]['n']] = vs[0]


def verse_list(ns):
    """[1,2,3,7,8] -> '1–3, 7–8'"""
    out, i = [], 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
            j += 1
        out.append(str(ns[i]) if i == j else f'{ns[i]}–{ns[j]}')
        i = j + 1
    return ', '.join(out)


def optional_default():
    """parish.txt "optional_verses: leave out" (or "sing"): what to do with verses the lectionary prints in brackets."""
    import lectionary
    return not lectionary.PARISH.get('optional_verses', 'sing').strip().lower().startswith(('leave', 'omit', 'no', 'skip'))


def parse_verses(txt, optional=True):
    """'1-7,18-19' / '1-8,(19-22)' / '1-12,21c' -> sorted verse numbers. Verses in brackets are optional:
    left out when optional is False."""
    out = set()
    for part in re.split(r'\s*,\s*', txt.strip()):
        if not optional and part.strip().startswith('(') and part.strip().endswith(')'):
            continue
        part = part.strip('() ')
        m = re.match(r'^(\d+)[a-d]?(?:\s*-\s*(\d+)[a-d]?)?$', part)
        if not m:
            raise SystemExit(f'cannot read verses {txt!r}')
        lo = int(m.group(1)); hi = int(m.group(2) or lo)
        out.update(range(lo, hi + 1))
    return sorted(out)


def optional_verses(spec):
    """The verses a psalm line marks as optional: '34:1-8,(19-22)' -> [19, 20, 21, 22]."""
    m = re.match(r'^.*?:\s*([\d,\-()a-d\s]+)$', spec.strip())
    if not m:
        return []
    return sorted(set(parse_verses(m.group(1))) - set(parse_verses(m.group(1), optional=False)))


def resolve(spec, optional=True):
    """A psalm line -> list of (path, verse numbers or None for all).

    '19'  '19:1-6'  '72:1-7,18-19'  '34:1-8,(19-22)'  '147:1-12,21c'  '89 Part 1'  '89:20-37'
    '119 Aleph'  '119:9-16'  'Canticle 16'.  A psalm printed in parts or sections needs either
    the part's name or verse numbers; verses are then taken from whichever files hold them.
    Two psalms sung as one, as the lectionary prints them: '42 and 43'."""
    spec = spec.strip()
    if re.search(r'\s+and\s+', spec, re.I):
        return [seg for part in re.split(r'\s+and\s+', spec, flags=re.I) for seg in resolve(part, optional)]
    m = re.match(r'^(.*?)(?:\s*:\s*([\d,\-()a-d\s]+))?$', spec)
    name, vtxt = m.group(1).strip(), m.group(2)
    verses = parse_verses(vtxt, optional) if vtxt else None
    if re.match(r'^(?i:canticle)\s+\d+$', name):
        files = ['Canticle_%d' % int(name.split()[1])]
    else:
        mm = re.match(r'^(?:(?i:psalm)\s+)?(\d+)(?:\s*:?\s*(?i:part)\s+(\w+)|\s+([A-Za-z]+))?$', name)
        if not mm:
            raise SystemExit(f'cannot read psalm {spec!r}')
        n, part, sec = mm.groups()
        base = 'Psalm_%03d' % int(n)
        if part:
            roman = {'I': '1', 'II': '2', 'III': '3', 'IV': '4'}             # 89 Part I is 89 Part 1
            files = [base + '_Part_' + roman.get(part.upper(), part.upper())]
        elif sec:
            files = [base + '_V_' + sec.capitalize()]
        elif paths.text_file(base):
            files = [base]
        else:
            files = [n for n in paths.text_names() if n.startswith(base + '_')]
            if not files:
                raise SystemExit(f'no text file for {spec!r}')
            if verses is None:
                kinds = [f.split('_', 2)[2] for f in files]                 # Part_1, Part_2 / V_Aleph, V_Beth…
                names = [k.replace('V_', '').replace('_', ' ') for k in kinds]
                eg = f'{int(n)} {names[0]}' if kinds[0].startswith('V_') else f'{int(n)} Part 1'
                raise SystemExit(f'Psalm {int(n)} is printed in parts ({", ".join(names)}): '
                                 f'give the part or the verses, e.g. "{eg}" or "{int(n)}:1-8"')
    out = []
    for f in files:
        path = paths.text_file(f) or os.path.join(paths.TEXT_DIRS[0], f + '.txt')
        if not os.path.exists(path):
            raise SystemExit(f'no text file texts/{f}.txt for {spec!r}' +
                             (' (the canticles are numbered 1-21, as in the BCP)' if f.startswith('Canticle') else ''))
        if verses is None:
            out.append((path, None))
            continue
        nums = {v['n'] for v in pointed.load(path)['verses']}
        take = [v for v in verses if v in nums]
        if take:
            out.append((path, take))
    if verses is not None:
        found = {v for _, t in out for v in t}
        missing = [v for v in verses if v not in found]
        if missing:
            raise SystemExit(f'{spec!r}: no verse {", ".join(map(str, missing))} in the text files')
    order = lambda pv: min(pv[1]) if pv[1] else 0
    return sorted(out, key=order)


def text_file(spec):
    """Backward-compatible: the first file a psalm line refers to."""
    return resolve(spec)[0][0], None, None


# ================================================================== chants
NOTE = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}


def chant_path(name):
    p = paths.chant_file(name)
    if not p:
        raise SystemExit(f'no chant file {name}.ly (looked in chants/ and parish/chants/)')
    return p


def _brace_block(s, start):
    d = 0
    for j in range(start, len(s)):
        if s[j] == '{':
            d += 1
        elif s[j] == '}':
            d -= 1
            if d == 0:
                return j + 1
    raise ValueError('unbalanced braces')


def read_chant(name, src=None):
    """A chant's file, taken apart for the PDF (src: the file's text, when it isn't saved yet)."""
    src = src if src is not None else paths.read(chant_path(name))
    info = {'name': name}
    hm = re.search(r'\\header\s*\{', src)
    credit = []
    if hm:
        hdr = src[hm.start():_brace_block(src, hm.end() - 1)]
        credit = re.findall(r'\\italic\s*"([^"]*)"', hdr)
        src = src[:hm.start()] + src[hm.start() + len(hdr):]
    info['credit'] = credit
    src = re.sub(r'\\version\s*"[^"]*"', '', src)
    for pm in list(re.finditer(r'\\paper\s*\{', src))[::-1]:
        src = src[:pm.start()] + src[_brace_block(src, pm.end() - 1):]
    blocks = []
    for mm in re.finditer(r'^\\markup\s*\{', src, re.M):
        blocks.append((mm.start(), _brace_block(src, mm.end() - 1)))
    main = [b for b in blocks if re.search(r'\\score\s*\{', src[b[0]:b[1]])]
    if not main:
        raise SystemExit(f'chants/{name}.ly: no \\markup block holding the score')
    a, b = main[0]
    defs = src[:a]
    for x, y in sorted((blk for blk in blocks if blk[0] < a), reverse=True):
        defs = defs[:x] + defs[y:]
    info['defs'] = defs.strip()
    info['score'] = src[a:b].strip()
    # small print before or after the score ("DESCANT", "Pedal held throughout") travels with it
    info['before'] = [src[x:y].strip() for x, y in blocks if x < a]
    info['after'] = [src[x:y].strip() for x, y in blocks if x > a]
    km = re.search(r'\\key\s+([a-g])((?:is|es|s)*)\s*\\(major|minor)', src)
    if km:
        info['tonic'] = km.group(1) + km.group(2)
        pc = NOTE[km.group(1)] + km.group(2).count('is') - km.group(2).count('es') - (1 if km.group(2) in ('s',) else 0)
        info['key'] = (pc % 12, km.group(3), km.group(1).upper() + km.group(2).replace('is', '♯').replace('es', '♭').replace('s', '♭'))
    sm = re.search(r'S_notes\s*=.*?\{(.*?)\n\}', src, re.S) or re.search(r'Unison_notes\s*=.*?\{(.*?)\n\}', src, re.S)
    phrases = sm.group(1).count('\\bar "||"') if sm else 0
    info['double'] = phrases >= 4
    return info


def is_tone(name):
    return name.startswith('tone:')


def load_music(name, music=None):
    """A chant file (perhaps transposed: 'Turle-2 down 2'), or a psalm tone given as tone:VIIa. music: the voices
    one service changes ({var: (start, notes) or None for silent}, from its music: lines)."""
    if is_tone(name):
        t = tones.tone(name[5:])
        return {'name': name, 'tone': t, 'double': False, 'credit': [t['label']], 'key': None}
    base, shift = paths.split_chant(name)
    if music:
        import chantedit
        try:
            info = read_chant(base, chantedit.service_text(paths.read(chant_path(base)), music))
        except ValueError as e:
            raise SystemExit(f'{base}: the music changed for this service: {e}')
    else:
        info = read_chant(base)
    if shift:
        transpose(info, shift)
    catalog_key(info, base, shift)
    info['name'] = name
    return info


def catalog_key(info, base, shift):
    """The key the catalog gives (Key, Mode: it may say G Mixolydian where the file's signature says C major) wins
    for what the checks report, moved by the transposition; the file's own key still drives the \\transpose."""
    row = next((r for r in paths.catalog() if r['Chant'] == base), None)
    m = re.match(r'^([A-G])([#b♯♭]?)$', (row or {}).get('Key', '').strip())
    if not m or not row.get('Mode', '').strip():
        return
    mode = row['Mode'].strip().lower()
    mode = {'mix': 'mixolydian', 'dor': 'dorian', 'phr': 'phrygian', 'lyd': 'lydian', 'aeo': 'aeolian'}.get(mode[:3], mode)
    pc = (NOTE[m.group(1).lower()] + (1 if m.group(2) in '#♯' and m.group(2) else -1 if m.group(2) else 0) + shift) % 12
    spelled = SPELL['minor' if mode in ('minor', 'aeolian', 'dorian', 'phrygian') else 'major'][pc]
    info['key'] = (pc, mode, spelled[0].upper() + spelled[1:].replace('is', '♯').replace('es', '♭'))


# the usual spelling of each key's tonic, by semitone above C (Dutch names, as LilyPond writes them)
SPELL = {'major': ['c', 'des', 'd', 'ees', 'e', 'f', 'fis', 'g', 'aes', 'a', 'bes', 'b'],
         'minor': ['c', 'cis', 'd', 'ees', 'e', 'f', 'fis', 'g', 'gis', 'a', 'bes', 'b']}


def lily_midi(p):
    """'aes' -> 56, 'c\'' -> 60 (LilyPond's absolute pitch)."""
    m = re.match(r"([a-g])((?:is|es|s)*)([',]*)$", p)
    acc = m.group(2).count('is') - m.group(2).count('es') - (1 if m.group(2) == 's' else 0)
    return 48 + NOTE[m.group(1)] + acc + 12 * (m.group(3).count("'") - m.group(3).count(','))


def transpose(info, shift):
    """Move a chant up (+) or down (-) so many semitones: the score is wrapped in \\transpose, from its tonic
    to the new key's tonic spelled the usual way (D minor down 2 is C minor, not B♯ minor)."""
    if 'tonic' not in info or 'key' not in info:
        raise SystemExit(f"chant {info['name']}: no \\key in its file, so it can't be transposed")
    src = info['tonic']
    mode = info['key'][1]
    want = lily_midi(src) + shift
    t = SPELL[mode][want % 12]
    octave = (want - lily_midi(t)) // 12
    t += ("'" * octave) if octave > 0 else ("," * -octave)
    info['score'] = re.sub(r'\\score\s*\{', lambda m: m.group(0) + f' \\transpose {src} {t}', info['score'], count=1)
    letter = t.rstrip("',")
    info['key'] = (want % 12, mode, letter[0].upper() + letter[1:].replace('is', '♯').replace('es', '♭'))
    info['shift'] = shift


def prefixed(info, tag):
    """Chant definitions and score with every variable renamed so several chants can share one file."""
    names = re.findall(r'^([A-Za-z_]+)\s*=', info['defs'], re.M)
    defs, score = info['defs'], info['score']
    for n in sorted(set(names), key=len, reverse=True):
        new = tag + n.replace('_', '')
        defs = re.sub(r'^%s(\s*=)' % n, new + r'\1', defs, flags=re.M)
        defs = re.sub(r'\\%s\b' % n, '\\\\' + new, defs)
        score = re.sub(r'\\%s\b' % n, '\\\\' + new, score)
    return defs, score


def key_relation(a, b):
    if not a or not b:
        return 'key unknown'
    (pa, ma, _), (pb, mb, _) = a, b
    d = (pb - pa) % 12
    if d == 0 and ma == mb:
        return 'same key'
    if d == 0:
        return 'parallel %s' % mb
    if (ma, mb, d) in (('minor', 'major', 3), ('major', 'minor', 9)):
        return 'relative %s' % mb
    if d == 7:
        return 'up a fifth (dominant)'
    if d == 5:
        return 'up a fourth (subdominant)'
    names = {1: 'up a semitone', 2: 'up a tone', 3: 'up a minor third', 4: 'up a major third',
             6: 'up a tritone', 8: 'down a major third', 9: 'down a minor third', 10: 'down a tone', 11: 'down a semitone'}
    return names.get(d, '%d semitones up' % d) + ('' if ma == mb else f', {ma} to {mb}')


def key_name(k):
    return '%s %s' % (k[2], k[1]) if k else '?'


# ================================================================== plan
def intone_every(item):
    """Is a psalm tone's intonation sung on every verse? Only when the Sunday file says so: verse 1 otherwise."""
    return item.get('intonation') == 'every'


def plan(sunday):
    """-> list of psalms (one per text file), each dict(id, doc, spec, sections=[dict(chant, verses=[...])])"""
    psalms, current = [], None
    for item in sunday['items']:
        segs = []
        for path, take in resolve(item['spec'], item.get('optional', optional_default())):
            doc = pointed.load(path)
            vs = [v for v in doc['verses'] if take is None or v['n'] in take]
            if item.get('pointing'):                      # this Sunday's pointing of some verses
                vs = [item['pointing'].get(v['n'], v) for v in vs]
            if 'daggers' in item:                        # this Sunday's own † placement
                vs = [dict(v, dagger=v['n'] in item['daggers']) for v in vs]
            segs.append((path, doc, vs))
        allv = [v for _, _, vs in segs for v in vs]
        if not allv:
            raise SystemExit(f'no verses {item["spec"]}')
        changes = item['chants'] or [(current, None)]
        if changes[0][0] is None:
            raise SystemExit(f'psalm {item["spec"]}: no chant given')
        starts = []
        for i, (name, frm) in enumerate(changes):
            if i == 0 and frm is not None and frm > allv[0]['n']:      # the verses before carry on the chant before
                if current is None:
                    raise SystemExit(f'psalm {item["spec"]}: chant {name} starts at verse {frm}: '
                                     f'give a chant for the verses before it')
                starts.append((allv[0]['n'], current))
            frm = allv[0]['n'] if (frm is None and i == 0) else frm
            if frm is None:
                raise SystemExit(f'chant {name}: say "from <verse>" for every chant after the first')
            starts.append((frm, name))
        if any(b[0] <= a[0] for a, b in zip(starts, starts[1:])):
            raise SystemExit(f'psalm {item["spec"]}: each "from" verse must come after the one before '
                             f'({", ".join(str(f) for f, _ in starts)})')
        for path, doc, vs in segs:
            sections = []
            for i, (frm, name) in enumerate(starts):
                to = starts[i + 1][0] if i + 1 < len(starts) else 10 ** 6
                # a section that started in an earlier file carries on into this one
                sv = [v for v in vs if frm <= v['n'] < to]
                if sv:
                    sections.append({'chant': name, 'verses': sv})
            psalms.append({'id': os.path.basename(path)[:-4], 'doc': doc, 'spec': item['spec'], 'sections': sections,
                           'every': intone_every(item)})
        current = starts[-1][1]
    # a text whose file says "% no Gloria Patri" (the Te Deum, the Benedicite…) ends without it
    if psalms and any(c.lower().startswith('no gloria patri') for c in psalms[-1]['doc'].get('comments', [])):
        sunday['gloria'] = False
    return psalms


GLORIA = paths.text_file('Gloria') or os.path.join(ROOT, 'texts', 'Gloria.txt')


def checks(sunday, psalms, chants):
    """Human-readable report: chant halves, daggers, key changes."""
    out, prev = [], None
    for it in sunday['items']:
        opt = optional_verses(it['spec'])
        if opt:
            sing = it.get('optional', optional_default())
            out.append(f"Psalm {it['spec']}: optional vv. {verse_list(opt)} " +
                       ('sung' if sing else 'left out') + f" (optional: {'no' if sing else 'yes'} under the psalm to change)")
    import chantedit
    names = {'S_notes': 'soprano', 'A_notes': 'alto', 'T_notes': 'tenor', 'B_notes': 'bass', 'Unison_notes': 'unison',
             'Descant_notes': 'descant'}
    for base, music in sunday['chant_music'].items():   # a chant's music as this service has it
        what = ', '.join(names.get(v, v) + (' silent' if got is None else '') for v, got in music.items())
        out.append(f'{base}: music changed for this service ({what}); the chant itself is unchanged')
        for problem in chantedit.check(chantedit.service_text(paths.read(chant_path(base)), music))[0]:
            out.append(f'  ! {base} as changed: {problem}')
    import check_texts
    for ps in psalms:                              # this Sunday's own pointing: still one * and the BCP's words?
        it = next((i for i in sunday['items'] if i['spec'] == ps['spec']), {})
        mine = {n: v for n, v in (it.get('pointing') or {}).items() if any(x['n'] == n for x in ps['doc']['verses'])}
        for n, v in sorted(mine.items()):
            probs = check_texts.verse_problems(ps['id'] + '.txt', v)
            out.append(f"{ps['doc']['title']} v. {n}: this Sunday's pointing" + (' ⚠ ' + '; '.join(probs) if probs else ''))
    for ps in psalms:
        for sec in ps['sections']:
            c = chants[sec['chant']]
            vs = sec['verses']
            rng = ('vv. ' if len(vs) > 1 else 'v. ') + verse_list([v['n'] for v in vs])
            if c.get('tone'):
                out.append(f"{ps['doc']['title']} {rng}: {c['tone']['label']} (plainchant)")
                prev = sec['chant']
                continue
            line = f"{ps['doc']['title']} {rng}: {sec['chant']} ({key_name(c.get('key'))}, {'double' if c['double'] else 'single'})"
            if prev is not None and prev != sec['chant'] and not is_tone(prev):
                line += f" — from {prev}: {key_relation(chants[prev].get('key'), c.get('key'))}"
            out.append(line)
            if c['double']:
                half, problems = 1, []
                for v in vs:
                    if v['dagger']:
                        if half != 1:
                            problems.append(f"† at v. {v['n']} falls on the second half")
                        continue          # † verse repeats the second half; the next verse starts the chant again
                    half = 2 if half == 1 else 1
                if half != 1:
                    problems.append('ends in the middle of the chant (odd number of verses)')
                out += ['   ⚠ ' + p for p in problems] or ['   ✓ verses fit the double chant']
            else:
                if any(v['dagger'] for v in vs):
                    out.append('   ⚠ † verses in a single chant section (they will be sung as ordinary verses)')
            prev = sec['chant']
    out.append('Gloria Patri: ' + ('yes' if sunday['gloria'] else 'no') + f" (service: {sunday['service']})")
    return out


# ================================================================== LilyPond
def installed_lilyponds():
    """LilyPond where it's usually unpacked or installed, when it isn't on the PATH (Windows and macOS have no
    installer that puts it there)."""
    import glob
    home = os.path.expanduser('~')
    pats = [os.path.join(d, 'lilypond*', 'bin', 'lilypond.exe') for d in
            (os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
             os.environ.get('LOCALAPPDATA', ''), home, os.path.join(home, 'Downloads'), os.path.join(home, 'Documents'), 'C:\\')
            if d] + ['/Applications/LilyPond.app/Contents/Resources/bin/lilypond', '/Applications/lilypond*/bin/lilypond',
                     os.path.join(home, 'lilypond*', 'bin', 'lilypond'), '/opt/homebrew/bin/lilypond', '/usr/local/bin/lilypond']
    found = [p for pat in pats for p in glob.glob(pat) if os.path.isfile(p)]
    return sorted(found, reverse=True)                  # lilypond-2.26.0 before lilypond-2.24.4


def lilypond_exe():
    for cand in (os.environ.get('LILYPOND'), shutil.which('lilypond'), *installed_lilyponds()):
        if cand:
            return cand
    try:
        import lilypond            # pip package "lilypond"
        return str(lilypond.executable())
    except Exception:
        raise SystemExit('LilyPond not found. Install it from https://lilypond.org/download.html (on Windows, unzip it '
                         'into Program Files, your home folder or Downloads, where Precentor looks for it), or set '
                         'LILYPOND to the program\'s path, or run: python -m pip install lilypond')


def lilypond_version(exe):
    out = subprocess.run([exe, '--version'], capture_output=True, text=True).stdout
    m = re.search(r'LilyPond (\d+\.\d+\.\d+)', out)
    return m.group(1) if m else '?'


def run_lilypond(exe, ly, outbase, *opts):
    r = subprocess.run([exe, '-dno-point-and-click', *opts, '-o', outbase, ly], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(f'LilyPond failed on {ly}')
    warn = [l for l in r.stderr.splitlines() if 'warning' in l.lower()]
    for w in warn:
        print('  LilyPond: ' + w)


def header(outdir, paper_extra=''):
    inc = os.path.relpath(STYLE, outdir).replace(os.sep, '/')
    return [f'\\version "{LY_VERSION}"', f'\\include "{inc}"', '',
            '\\paper {', '  top-margin = 0.5\\in', '  bottom-margin = 0.5\\in',
            '  print-page-number = ##f', paper_extra, '}', '\\header { tagline = ##f }', '']


def chant_markup(c, score):
    """Composer credit (right-aligned) and the chant, as one block so they never part at a page break."""
    inner = re.sub(r'^\\markup\s*\{', '', score.strip())
    inner = inner[:inner.rstrip().rfind('}')]
    credit = ''
    if c['credit']:
        parts = ' \\hspace #3 '.join('\\italic %s' % emit.lystr(t) for t in c['credit'])
        credit = '\\fill-line { \\null \\line { %s } }\n' % parts
    def body(m):
        t = re.sub(r'^\\markup\s*\{', '', m.strip())
        return t[:t.rstrip().rfind('}')].strip()
    before = ''.join(body(m) + '\n' for m in c.get('before', []))
    after = ''.join('\n' + body(m) for m in c.get('after', []))
    return '\\markup \\column {\n' + credit + before + inner.strip() + after + '\n}'


def music_markup(c, tag):
    """The block printed above a section: a chant (with its credit) or a psalm tone."""
    if c.get('tone'):
        t = c['tone']
        score = tones.score_ly(tones.formula_score(t), clef=t['clef'])
        return ('\\markup \\column {\n\\fill-line { \\null \\line { \\italic %s } }\n'
                '\\fill-line { %s }\n}' % (emit.lystr(t['label']), score))
    return chant_markup(c, prefixed(c, tag)[1])


def tone_verse_notated(pv, t):
    """First verse of a tone section, every syllable under its note."""
    music, lyr = tones.verse_score(pv, t)
    score = tones.score_ly(music, lyr, stanza=f"{pv['n']}.", clef=t['clef']).replace('indent = 0', 'indent = 0 ragged-right = ##t')
    return '\\markup \\column {\n%s\n}' % score


def gloria_verses():
    """Gloria Patri verses, unnumbered (sung to the whole chant, single or double)."""
    if not os.path.exists(GLORIA):
        return []
    doc = pointed.load(GLORIA)
    return [dict(v, n='', dagger=False) for v in doc['verses']]


def choir_ly(sunday, psalms, chants, tags, outdir, reprints=frozenset()):
    """reprints: set of (psalm index, verse number) before which the current chant is printed again."""
    L = header(outdir)
    for name, tag in tags.items():
        L += ['% ---- chant ' + name, prefixed(chants[name], tag)[0], '']
    prev = (None, None)
    last = None
    for pi, ps in enumerate(psalms):
        for si, sec in enumerate(ps['sections']):
            c = chants[sec['chant']]
            head = music_markup(c, tags.get(sec['chant']))
            L.append(f'% ==== {ps["doc"]["title"]}: {sec["chant"]} from verse {sec["verses"][0]["n"]}')
            # the same chant carrying on into the next section of one psalm line (119:1-16) is not printed again
            cont = si == 0 and prev == (ps['spec'], sec['chant'])
            if not cont:
                L.append(head)
            prev = (ps['spec'], sec['chant'])
            last = c
            if si == 0:
                L.append(emit.title_markup(ps['doc']))
            for vi, v in enumerate(sec['verses']):
                if vi > 0 and (pi, v['n']) in reprints:
                    L += ['% chant reprinted at the top of the page', '\\pageBreak', head]
                if c.get('tone'):
                    pv = tones.point_verse(v, c['tone'], first=(vi == 0 and not cont) or ps['every'])
                    L.append(tones.verse_markup(pv))          # every verse pointed in words; the tone is printed above
                else:
                    L.append(emit.verse_markup(v))
    if sunday['gloria']:
        L.append('% ==== Gloria Patri')
        for v in gloria_verses():
            L.append(tones.verse_markup(tones.point_verse(v, last['tone'])) if last and last.get('tone') else emit.verse_markup(v))
    return '\n'.join(L) + '\n'


def page_texts(pdf):
    """The text of each page (poppler's pdftotext if installed, otherwise the pypdf package)."""
    if shutil.which('pdftotext'):
        out = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout
        return out.split('\f')
    try:
        import pypdf
        return [p.extract_text() or '' for p in pypdf.PdfReader(pdf).pages]
    except ImportError:
        print('  note: install pypdf (pip install pypdf) to have chants reprinted at the top of a page')
        return []


def find_reprints(pdf, psalms):
    """(psalm, verse) for each verse that opens a page while its chant is on an earlier page. A page's top verse
    belongs to the psalm whose title came last before it (two psalms may share verse numbers)."""
    need, at = set(), -1
    norm = lambda t: re.sub(r'\s+', ' ', t)
    for pno, page in enumerate(page_texts(pdf)):
        lines = [l.strip() for l in page.splitlines() if l.strip() and not l.strip().startswith('/')]
        top = lines[0] if lines else ''
        m = re.match(r'^†?\s*(\d+)\s*[A-Z\u201c\u2018"\'\u2014]', top)
        if pno and m and at >= 0:
            n = int(m.group(1))
            if any(v['n'] == n for sec in psalms[at]['sections'] for v in sec['verses'][1:]):
                need.add((at, n))
        text = norm(page)
        pos = 0
        while at + 1 < len(psalms):                    # the titles on this page, in order
            i = text.find(norm(psalms[at + 1]['doc']['title']), pos)
            if i < 0:
                break
            at, pos = at + 1, i + 1
    return need


def build_pdf(exe, sunday, psalms, chants, tags, outdir, base):
    ly = os.path.join(outdir, base + '.ly')
    reprints = set()
    for _ in range(12):
        open(ly, 'w', encoding='utf-8').write(choir_ly(sunday, psalms, chants, tags, outdir, frozenset(reprints)))
        run_lilypond(exe, ly, os.path.join(outdir, base))
        if not sunday['reprint']:
            break
        more = find_reprints(os.path.join(outdir, base + '.pdf'), psalms) - reprints
        if not more:
            break
        reprints.add(min(more))           # one at a time: each moves the pages after it
    return ly, sorted(reprints)


def trim(im):
    """The picture cut to what's printed on it (LilyPond's crop keeps blank margins, such as the text's indent)."""
    from PIL import ImageChops
    box = ImageChops.invert(im.convert('L')).point(lambda p: 255 if p > 24 else 0).getbbox()
    return im.crop(box) if box else im


def build_images(exe, sunday, psalms, chants, tags, outdir, dpi=400):
    from PIL import Image
    adir = os.path.join(outdir, 'admin')
    if os.path.isdir(adir):
        shutil.rmtree(adir)
    os.makedirs(adir)
    tmp = tempfile.mkdtemp(dir=outdir, prefix='.img_')
    made, k = [], 0
    prev = (None, None)
    for pi, ps in enumerate(psalms):
        for si, sec in enumerate(ps['sections']):
            c = chants[sec['chant']]
            cont = si == 0 and prev == (ps['spec'], sec['chant'])      # as in the PDF: the same tone carrying on
            prev = (ps['spec'], sec['chant'])
            vs = sec['verses']
            tv = list(vs)
            if sunday['gloria'] and pi == len(psalms) - 1 and si == len(ps['sections']) - 1:
                tv += gloria_verses()
            title = emit.title_line(ps['doc']) if si == 0 else None
            if c.get('tone'):
                jobs = [('tone_' + c['tone']['label'].replace('Tone ', '').replace(' ', ''), [music_markup(c, None)])]
                pvs = [tones.point_verse(v, c['tone'], first=(vi == 0 and not cont) or (ps['every'] and v['n'] != ''))
                       for vi, v in enumerate(tv)]
                body = [tones.single_block(title, pvs)]
            else:
                defs, score = prefixed(c, 'ch')
                jobs = [('chant_' + sec['chant'], [defs, chant_markup(c, score)])]
                body = [emit.single_block(title, tv)]
            rng = 'v%d-%d' % (vs[0]['n'], vs[-1]['n']) if len(vs) > 1 else 'v%d' % vs[0]['n']
            label = ps['doc']['title'].replace('Psalm ', 'ps').replace(': Part ', 'p').replace(' ', '')
            jobs.append((f'text_{label}_{rng}', body))
            for name, blocks in jobs:
                k += 1
                stem = '%02d_%s' % (k, re.sub(r'[^A-Za-z0-9_-]', '', name))      # no dots: LilyPond trims them
                ly = os.path.join(tmp, stem + '.ly')
                open(ly, 'w', encoding='utf-8').write('\n'.join(header(tmp, '  page-breaking = #ly:one-page-breaking') + blocks) + '\n')
                run_lilypond(exe, ly, os.path.join(tmp, stem), '-dcrop', '-dresolution=%d' % dpi, '--png')
                png = os.path.join(tmp, stem + '.cropped.png')
                im = Image.open(png)
                if im.mode in ('RGBA', 'LA', 'P'):
                    im = im.convert('RGBA')
                    bg = Image.new('RGB', im.size, 'white')
                    bg.paste(im, mask=im.split()[-1])
                    im = bg
                else:
                    im = im.convert('RGB')
                im = trim(im)                                     # -dcrop keeps the page's indent: cut to the ink
                pad = dpi // 20                                   # a little white border
                out = Image.new('RGB', (im.width + 2 * pad, im.height + 2 * pad), 'white')
                out.paste(im, (pad, pad))
                jpg = os.path.join(adir, stem + '.jpg')
                out.save(jpg, quality=95, dpi=(dpi, dpi))
                made.append(jpg)
    shutil.rmtree(tmp)
    return made


# ================================================================== main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('sunday')
    ap.add_argument('--pdf-only', action='store_true')
    ap.add_argument('--check', action='store_true', help='only print the checks')
    ap.add_argument('--out', help='output folder (default output/<date>)')
    args = ap.parse_args()

    sunday = parse_sunday(args.sunday)
    if not sunday['choir']:
        print('No choir this week (choir: no): the psalm is said, so there is nothing to build.')
        return
    if not sunday['items']:
        raise SystemExit(f'{args.sunday}: no psalm: line, so there is nothing to build')
    psalms = plan(sunday)
    names = []
    for ps in psalms:
        for sec in ps['sections']:
            if sec['chant'] not in names:
                names.append(sec['chant'])
    chants = {n: load_music(n, sunday['chant_music'].get(paths.split_chant(n)[0]) if not is_tone(n) else None) for n in names}
    real = [n for n in names if not is_tone(n)]
    tags = {n: 'ch' + 'abcdefghijklmnopqrstuvwxyz'[i] for i, n in enumerate(real)}

    print('\n'.join(checks(sunday, psalms, chants)))
    if args.check:
        return

    exe = lilypond_exe()
    ver = lilypond_version(exe)
    if ver != PINNED_LILYPOND:
        print(f'  note: LilyPond {ver} (the style is tuned for {PINNED_LILYPOND}; spacing may differ slightly)')

    name = os.path.splitext(os.path.basename(args.sunday))[0]      # e.g. 2026-12-24 or 2026-12-24-midnight
    outdir = os.path.abspath(args.out or os.path.join(paths.OUTPUT, name))
    os.makedirs(outdir, exist_ok=True)
    base = 'psalm_' + name
    ly, rep = build_pdf(exe, sunday, psalms, chants, tags, outdir, base)
    if rep:
        print('  chant reprinted at the top of the page before verse ' + ', '.join(str(n) for _, n in rep))
    print('PDF:    ' + os.path.relpath(os.path.join(outdir, base + '.pdf'), os.getcwd()))
    if not args.pdf_only:
        imgs = build_images(exe, sunday, psalms, chants, tags, outdir)
        print('Images: ' + ', '.join(os.path.basename(i) for i in imgs))


if __name__ == '__main__':
    main()

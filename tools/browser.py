#!/usr/bin/env python3
"""Build the chant browser: site/index.html, opened straight from your folder (no server needed).

    python tools/browser.py            # refresh data; draw notation for new or changed chants
    python tools/browser.py --redraw   # redraw every chant's notation

Reads the chants and catalogs (chants/, parish/chants/), parish/chant_notes.csv, texts/, moods.txt,
parish/legacy/history.csv and parish/sundays/. Writes parish/site/ (or site/ without a parish folder).
"""
import argparse, csv, glob, json, os, re, shutil, subprocess, sys, tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import build, chantinfo, lectionary, paths, pointed       # noqa: E402
import datetime as dt
SITE = paths.SITE


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def vocabulary():
    groups = []
    for line in paths.read(os.path.join(ROOT, 'moods.txt')).splitlines():
        line = line.split('#', 1)[0].strip()
        if ':' in line:
            g, tags = line.split(':', 1)
            groups.append({'group': g.strip(), 'tags': [t.strip() for t in tags.split(',') if t.strip()]})
    return groups


def tags(s):
    return [t.strip() for t in re.split(r'[;,]', s or '') if t.strip()]


# ------------------------------------------------------------- notation
def draw(exe, name, out_png, c=None):
    """The picture of a chant for the browser (c: the chant already read, e.g. edited or transposed)."""
    c = c or build.read_chant(name)
    defs, score = build.prefixed(c, 'ch')
    m = re.search(r'\\score\s*\{', score)
    score = score[m.start():build._brace_block(score, m.end() - 1)]      # the bare score, without the centring markup
    tmp = tempfile.mkdtemp()
    ly = os.path.join(tmp, 'c.ly')
    open(ly, 'w', encoding='utf-8').write('\n'.join([
        '\\version "2.24.0"', '\\paper { indent = 0 paper-width = 320\\mm line-width = 300\\mm ragged-right = ##t }',
        '\\header { tagline = ##f }', defs, score]) + '\n')
    r = subprocess.run([exe, '--png', '-dcrop', '-dresolution=220', '-dno-point-and-click', '-o', os.path.join(tmp, 'c'), ly],
                       capture_output=True, text=True)
    src = os.path.join(tmp, 'c.cropped.png')
    ok = r.returncode == 0 and os.path.exists(src)
    if ok:
        shutil.copy(src, out_png)
    else:
        sys.stderr.write(f'  could not draw {name}\n{r.stderr[-600:]}\n')
    shutil.rmtree(tmp)
    return ok


# ------------------------------------------------------------- history
def history():
    rows = [dict(r, source='legacy') for r in read_csv(paths.LEGACY_HISTORY)]
    for path in sorted(glob.glob(os.path.join(paths.SUNDAYS, '[!_]*.txt'))):
        try:
            s = build.parse_sunday(path)
            if not s['sung'] or not s['date']:
                continue
            if not s['choir']:                      # no choir: the psalms, said, with no chant
                for it in s['items']:
                    for path_, take in build.resolve(it['spec']):
                        vs = take or [v['n'] for v in pointed.load(path_)['verses']]
                        rows.append({'date': s['date'], 'text': os.path.basename(path_)[:-4], 'chant': '', 'source': 'new',
                                     'verses': f'{vs[0]}-{vs[-1]}' if len(vs) > 1 else str(vs[0]), 'note': 'no choir that week'})
                continue
            for ps in build.plan(s):
                name = ps['id']
                for sec in ps['sections']:
                    if sec['chant'] in ('???', '?', ''):
                        continue
                    vs = sec['verses']
                    rng = f"{vs[0]['n']}-{vs[-1]['n']}" if len(vs) > 1 else str(vs[0]['n'])
                    rows.append({'date': s['date'], 'text': name, 'verses': rng, 'chant': sec['chant'],
                                 'note': s['service'] if s['service'] != 'Eucharist' else '', 'source': 'new'})
        except SystemExit as e:
            sys.stderr.write(f'  skipped {os.path.basename(path)}: {e}\n')
    rows += schedule_history({r['date'][:10] for r in rows})
    for r in rows:                            # one name per chant: 'Turle-5' was Turle-2 a tone down
        c = r.get('chant') or ''
        if c and not c.startswith('tone:') and c not in ('?', '???'):
            base, shift = paths.split_chant(c)
            if shift:
                r['shift'] = shift
            r['chant'] = base
    rows.sort(key=lambda r: r['date'])
    return rows


def acp_numbers():
    """{ACP number: (chant, the psalm the ACP sets it to)} from the catalogs: a Source of 'ACP 001, 107, 181'
    with ACP Psalm '1, 50, 80' gives 1 -> Psalm 1, 107 -> 50, 181 -> 80. The parts of one psalm count once
    ('37-1, 37-2'); where the numbers and psalms don't then pair up, only the first number is taken (no guessing)."""
    out = {}
    for r in paths.catalog() + [dict(r, Chant=r['Alias'], **{'ACP Psalm': ''}) for r in paths.alias_rows()]:
        m = re.search(r'ACP\s*([\d,\s]+)', r.get('Source', ''))
        if not m:
            continue
        psalms = []
        for x in (r.get('ACP Psalm') or '').split(','):
            x = x.strip()
            if x and not (psalms and x.split('-')[0] == psalms[-1].split('-')[0]):
                psalms.append(x)
        numbers = [int(n) for n in re.findall(r'\d+', m.group(1))]
        pairs = zip(numbers, psalms) if len(numbers) == len(psalms) else zip(numbers[:1], psalms[:1] or [''])
        for n, psalm in pairs:
            out.setdefault(n, (r['Chant'], psalm))
    return out


def schedule_history(have):
    """Psalms from the imported record (parish/schedule/schedule.csv) on dates the history doesn't cover."""
    path = os.path.join(paths.HOME, 'schedule', 'schedule.csv')
    acp = acp_numbers()
    out, today = [], dt.date.today().isoformat()
    for r in read_csv(path):
        if r['slot'] != 'Psalm' or r['date'] in have or r['date'] > today:
            continue
        m = re.match(r'^(.*?)\s*\(([^)]*)\)\s*$', r['item'])
        spec, music = (m.group(1).strip(), m.group(2).strip()) if m else (r['item'].strip(), '')
        chant, note = '', 'from the imported record'
        if music.upper() == 'ACP' and spec.isdigit():           # an ACP number: chant and psalm from the catalog
            if int(spec) not in acp:
                continue
            chant, psalm = acp[int(spec)]
            pm = re.match(r'(\d+)(?:-(\d+))?', psalm)
            spec = (pm.group(1) + (f' Part {pm.group(2)}' if pm.group(2) else '')) if pm else ''
        elif music.lower().startswith('tone'):
            chant = 'tone:' + music[4:].replace('.', '').replace(' ', '')
        elif music and music.upper() not in ('N/A', 'ACP'):
            chant = music
        try:
            segs = build.resolve(spec.replace(' ', '') if ':' in spec else spec)
        except SystemExit:
            continue
        for path_, take in segs:
            vs = take or [v['n'] for v in pointed.load(path_)['verses']]
            out.append({'date': r['date'], 'text': os.path.basename(path_)[:-4],
                        'verses': f'{vs[0]}-{vs[-1]}' if len(vs) > 1 else str(vs[0]),
                        'chant': chant, 'source': 'schedule',      # no chant: the psalm was said (no choir that week)
                        'note': note if chant else 'no chant setting (no choir that week), from the imported record'})
    return out


def gloria_body():
    path = paths.text_file('Gloria') or os.path.join(ROOT, 'texts', 'Gloria.txt')
    if not os.path.exists(path):
        return []
    doc = pointed.load(path)
    return [[v['n'], 0, [[ln['text'], ln['half'], int(ln['wrap'])] for ln in v['lines']]] for v in doc['verses']]


def unconfirmed():
    """Sunday files whose date has passed but aren't marked sung yet."""
    out = []
    today = dt.date.today().isoformat()
    for p in sorted(glob.glob(os.path.join(paths.SUNDAYS, '[!_]*.txt'))):
        try:
            sd = build.parse_sunday(p)
        except SystemExit:
            continue
        if sd['date'] and not sd['sung'] and sd['date'] <= today:
            out.append({'name': os.path.basename(p)[:-4], 'date': sd['date'],
                        'psalms': [it['spec'] for it in sd['items']],
                        'chants': [c for it in sd['items'] for c, _ in it['chants']]})
    return out


# ------------------------------------------------------------- texts
def changed_verses(name, doc):
    """{verse: its pointing before the browser first changed it} for the verses that differ now (paths.ORIGINALS)."""
    f = os.path.join(paths.ORIGINALS, name + '.txt')
    if not os.path.exists(f):
        return {}
    now = {v['n']: v for v in doc['verses']}
    return {v['n']: [v['n'], int(v['dagger']), [[ln['text'], ln['half'], int(ln['wrap'])] for ln in v['lines']]]
            for v in pointed.load(f)['verses'] if v['n'] in now and (v['lines'], v['dagger']) != (now[v['n']]['lines'], now[v['n']]['dagger'])}


def texts():
    moods = {}
    for r in read_csv(os.path.join(ROOT, 'texts', 'moods.csv')):
        moods.setdefault(r['text'], []).append({'verses': r['verses'], 'mood': tags(r['mood']),
                                                'type': r.get('type', ''), 'note': r.get('note', '')})
    out = []
    for path in [paths.text_file(n) for n in paths.text_names()]:
        name = os.path.splitext(os.path.basename(path))[0]
        if name == 'Gloria':
            continue
        doc = pointed.load(path)
        nums = [v['n'] for v in doc['verses']]
        first = doc['verses'][0]['lines'][0]['text'] if doc['verses'] else ''
        first = re.sub(r'\s+[|.*]\s*|\s*\*\s*|=', ' ', first)
        first = re.sub(r'- -|-\s+-', '', first)
        first = re.sub(r'\s+', ' ', first).strip()
        out.append({'id': name, 'title': doc['title'], 'latin': doc.get('latin') or '',
                    'verses': [min(nums), max(nums)] if nums else None, 'first': first,
                    'draft': any('unpointed' in c.lower() for c in doc['comments']),
                    'noGloria': any(c.lower().startswith('no gloria patri') for c in doc['comments']),
                    'body': [[v['n'], int(v['dagger']), [[ln['text'], ln['half'], int(ln['wrap'])] for ln in v['lines']]]
                             for v in doc['verses']],
                    'sections': moods.get(name, []), 'orig': changed_verses(name, doc)})
    def order(t):
        m = re.match(r'(Psalm|Canticle)_(\d+)', t['id'])
        return (0 if m.group(1) == 'Psalm' else 1, int(m.group(2)), t['verses'][0] if t['verses'] else 0)
    out.sort(key=order)
    return out


# ------------------------------------------------------------- calendar
def calendar(weeks=110):
    """Sundays and principal feasts from two weeks ago to two years ahead, with the appointed psalms."""
    rows = lectionary.table()
    start = dt.date.today() - dt.timedelta(days=14)
    planned = {}
    for p in glob.glob(os.path.join(paths.SUNDAYS, '[!_]*.txt')):
        try:
            sd = build.parse_sunday(p)
            planned.setdefault(sd['date'], []).append({'name': os.path.basename(p)[:-4], 'sung': sd['sung'], 'choir': sd['choir'],
                'chants': [c for it in sd['items'] for c, _ in it['chants'] if c not in ('???', '?')],
                'psalms': [it['spec'] for it in sd['items']]})
        except SystemExit:
            pass
    out, d = [], start
    feasts = {'christmas_eve', 'christmas_day', 'holy_name', 'epiphany', 'presentation', 'ash_wednesday',
              'maundy_thursday', 'good_friday', 'easter_vigil', 'ascension', 'transfiguration', 'all_saints'}
    if lectionary.PARISH.get('patronal'):
        feasts.add(lectionary.PARISH['patronal'].split()[1])       # the patronal feast, on whatever day
    while d < start + dt.timedelta(weeks=weeks):
        key, label = lectionary.day_of(d)
        if d.weekday() == 6 or key in feasts:
            a = lectionary.appointed(d, rows)
            specs = [(s, '') for s in ([a['psalm']] if a['psalm'] else []) + a['alt']]
            if (d.month, d.day) == (12, 24) and key != 'christmas_eve':       # Advent 4 in the morning, Christmas Eve at night
                ce = lectionary.appointed(d, rows, 'christmas_eve')
                specs += [(s, 'Christmas Eve') for s in ([ce['psalm']] if ce['psalm'] else []) + ce['alt']]
            opts = []
            for i, (spec, also) in enumerate(specs):
                spec = spec.replace('Ps. ', '').strip()
                try:
                    segs = build.resolve(spec)
                    texts = [os.path.basename(p)[:-4] for p, _ in segs]
                    verses = None if any(t is None for _, t in segs) else [v for _, t in segs for v in t]
                    err = ''
                except SystemExit as e:
                    texts, verses, err = [], None, str(e)
                track = also
                if not also and key and key.startswith('proper') and a['alt']:
                    track = 'Track 1' if i == 0 else ('Track 2' if i == 1 else '')
                opts.append({'spec': spec, 'texts': texts, 'verses': verses, 'track': track, 'error': err})
            out.append({'date': d.isoformat(), 'label': a['label'], 'year': a['year'], 'options': opts,
                        'link': lectionary.link(d, key),
                        'planned': planned.get(d.isoformat(), [])})
        d += dt.timedelta(days=1)
    return out


# ------------------------------------------------------------- main
def service_data():
    """Orders of service, hymnals, past repertoire, the music library, anthem texts, and every service on record,
    for the planner."""
    import service
    by_date = {}               # every service, by name: its file's name, or its date (and occasion, two in a day)
    for e in service.all_services():
        by_date[e['name']] = {'date': e['date'], 'order': e['order'], 'items': e['items'], 'source': e['source'],
                              'psalms': [spec + (f" ({', '.join(c.replace('tone:', 'Tone ') for c in ch)})" if ch else '')
                                         for spec, ch in e.get('psalms', [])]}
    # which lectionary day each date was or will be, to find the same Sunday in earlier years
    lect, rows = {}, lectionary.table()
    days = {e['date'] for e in by_date.values()} | {h['date'][:10] for h in history() if h.get('date')} | \
        {(dt.date.today() + dt.timedelta(days=i)).isoformat() for i in range(-14, 800)}
    colors, seasons = {}, {}
    for d in sorted(days):
        try:
            seasons[d] = lectionary.season(dt.date.fromisoformat(d))
            a = lectionary.appointed(dt.date.fromisoformat(d), rows)
            colors[d] = lectionary.color(dt.date.fromisoformat(d), a.get('key'))
        except Exception:
            continue
        if a.get('key'):
            lect[d] = [a['key'], a['year'], a['label'], lectionary.link(dt.date.fromisoformat(d), a['key'])]
    import plugins, library
    return {'lect': lect, 'colors': colors, 'seasons': seasons, 'library': library.page_data(), 'shades': lectionary.shades(), 'orders': service.ORDERS, 'hymnals': service.hymnals(), 'repertoire': service.repertoire(),
            'hymnHistory': service.hymn_history(), 'anthems': service.anthems(), 'byDate': by_date,
            'lessons': service.lessons(), 'meta': service.META,
            'plugins': plugins.data(), 'pluginKeys': sorted(plugins.sunday_keys()),
            'linksSignature': lectionary.links_signature()}


# ------------------------------------------------------------- plainchant psalm tones
# the spirit of each mode ("Spirit of the Gregorian modes", from Singing the Gregorian Modes)
TONE_CHARACTER = {1: 'Gravis: peace, tranquility, equilibrium',
                  2: 'Tristis: gravity, somber (transposed up a fifth it may express a certain joy, as in Haec dies)',
                  3: 'Mysticus: humble dignity',
                  4: 'Harmonicus: well ordered, "the mode without an end"',
                  5: 'Laetus: trumpeting, firmness',
                  6: 'Devotus: simple joy, confidence, filial piety',
                  7: 'Angelicus: exaltation, triumphant joy, enthusiasm',
                  8: 'Perfectus: certitude, stability, affirmation'}


def tone_voices(t):
    """The tone as notes for the browser's playback: intonation, reciting note, mediant | reciting note, ending."""
    import tones
    evs, at = [], 0.0
    for part in ('mediant', 'termination'):
        f = tones.formula(t[part])
        toks = (f['intonation'] if part == 'mediant' else []) + [f['tenor']] + f['cadence']
        for i, tk in enumerate(toks):
            for j, (letter, flat) in enumerate(tk['notes']):
                m = tones.to_pitch(letter, t['clef']) - 24 - (1 if flat else 0)    # the C line sounds as middle C
                last = part == 'termination' and i == len(toks) - 1 and j == len(tk['notes']) - 1
                du = 0.62 if tk is f['tenor'] else (0.42 if last else 0.14)
                evs.append([m, round(at, 3), du])
                at += du
        at += 0.18
    return {'chant': evs}


def draw_tone(exe, t, out_png, parts=('mediant', 'termination')):
    import tones
    tmp = tempfile.mkdtemp()
    ly = os.path.join(tmp, 't.ly')
    open(ly, 'w', encoding='utf-8').write('\n'.join([
        '\\version "2.24.0"', '\\paper { indent = 0 paper-width = 320\\mm line-width = 300\\mm ragged-right = ##t }',
        '\\header { tagline = ##f }', tones.score_ly(tones.formula_score(t, parts), clef=t['clef'])]) + '\n')
    r = subprocess.run([exe, '--png', '-dcrop', '-dresolution=220', '-dno-point-and-click', '-o', os.path.join(tmp, 't'), ly],
                       capture_output=True, text=True)
    src = os.path.join(tmp, 't.cropped.png')
    ok = r.returncode == 0 and os.path.exists(src)
    if ok:
        shutil.copy(src, out_png)
    else:
        sys.stderr.write(f"  could not draw {t['label']}\n{r.stderr[-600:]}\n")
    shutil.rmtree(tmp)
    return ok


ROMAN_NUM = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII']
SINGLE_ENDING = {'2': 'D', '5': 'a', '6': 'F'}           # the Liber's letter for tones with one ending


def tone_groups():
    """Each tone of the psalm-tone table with its endings: [(key, label, mode, [(name, ending), ...])].
    name is what's typed in a chant box ("tone 1g2"); every ending of a tone shares its mediant."""
    import tones
    out = []
    for key, t in tones.TONES.items():
        n = key.split('.')[0]
        if n == 'per':
            out.append((key, 'Tonus peregrinus', 0, [('per', '')]))
            continue
        alt = 'alt' in key
        terms = t.get('terminations') or {SINGLE_ENDING.get(n, ''): t['termination']}
        label = f'Tone {ROMAN_NUM[int(n)]}' + (' (alternative mediant)' if alt else '')
        names = []
        for e in terms:
            name = '6alt' if alt and n == '6' else f'{n}{e}'          # 4c, 4A* find Tone IV's alternative by themselves
            names.append((name, e))
        out.append((key, label, int(n), names))
    return out


def tones_data(redraw=False):
    """-> (endings, groups): every tone-and-ending as typed, with its notes for playback and a picture of the
    ending; and every tone with a picture of its intonation and mediant, which its endings share."""
    import tones
    src = max(os.path.getmtime(os.path.join(ROOT, 'reference', 'psalm_tones.json')), os.path.getmtime(tones.__file__))
    endings, groups, exe = [], [], None

    def picture(file, t, parts):
        nonlocal exe
        img = os.path.join(SITE, 'notation', file)
        if redraw or not os.path.exists(img) or os.path.getmtime(img) < src:
            try:
                exe = exe or build.lilypond_exe()
                draw_tone(exe, t, img, parts)
            except SystemExit:
                pass
        return file if os.path.exists(img) else ''

    for key, label, mode, names in tone_groups():
        good = []
        for name, e in names:
            try:
                t = tones.tone(name)
            except SystemExit:
                continue
            safe = re.sub(r'[^A-Za-z0-9]', '_', name)
            endings.append({'name': name, 'ending': e or ('' if mode else 'peregrinus'), 'group': key, 'label': t['label'],
                            'mode': mode, 'clef': t['clef'], 'voices': tone_voices(t),
                            'img': picture(f'tone_end_{safe}.png', t, ('termination',) if mode else ('mediant', 'termination'))})
            good.append(name)
        if not good:
            continue
        first = tones.tone(good[0])
        groups.append({'key': key, 'label': label, 'mode': mode, 'endings': good,
                       'character': TONE_CHARACTER.get(mode, 'the pilgrim tone: a different reciting note in each half; '
                                                             'traditionally for Psalm 114, In exitu Israel'),
                       'img': picture('tone_med_' + re.sub(r'[^A-Za-z0-9]', '_', key) + '.png', first, ('mediant',)) if mode else ''})
    return endings, groups


PAGE = os.path.join(TOOLS, 'browser')       # the page: page.html, style.css and js/*.js, put together into one file


def page_html():
    """index.html: page.html with style.css, the scripts in js/ (in the order of their numbers; they share one
    scope, so a later file may use what an earlier one defines) and the parish's plugin scripts, inline."""
    import plugins
    read = lambda *p: paths.read(os.path.join(PAGE, *p))
    js = ''.join(f'\n// ===== {f} =====\n' + read('js', f) for f in sorted(os.listdir(os.path.join(PAGE, 'js'))) if f.endswith('.js'))
    fonts = os.path.relpath(os.path.join(ROOT, 'style', 'fonts'), SITE).replace(os.sep, '/')
    safe = lambda t: t.replace('</script', '<\\/script')
    return (read('page.html').replace('/*STYLE*/', read('style.css').replace('../style/fonts', fonts))
            .replace('/*SCRIPT*/', safe(js)).replace('/*PLUGINS*/', safe(plugins.scripts())))


JUNIOR = re.compile(r'\(?\b(?:jr|jun|junior)\b\.?\)?', re.I)


def label_chants(chants):
    """How a chant is named on screen, as service sheets name them: 'Turle in D minor'; a number in brackets
    where one composer has two in the same key ('Goss in F (2)'), in the order of the file names."""
    def nat(c):
        m = re.match(r'^(.*?)-?(\d+)$', c['id'])
        return (m.group(1), int(m.group(2))) if m else (c['id'], 0)
    full = {}
    for c in chants:
        full.setdefault(c['composer'].split(',')[0].strip(), set()).add(c['composer'].strip())
    for c in chants:
        last, _, first = c['composer'].partition(',')
        who = last.strip() or nat(c)[0]
        given = JUNIOR.sub(' ', first)
        if len(full.get(last.strip(), ())) > 1 and given.strip(' ,()'):   # G. Elvey and S. Elvey
            who = ' '.join(w[0] + '.' for w in given.replace('.', ' ').replace(',', ' ').split()) + ' ' + who
            if given != first: who += ' Jr.'                            # R. Woodward Jr., J. Camidge Jr.
        k = re.sub(r'([A-G])b', r'\1♭', c['key'] or '').replace('#', '♯')
        mode = (c['mode'] or '').lower()
        c['label'] = f"{who} in {k}" + (' minor' if mode.startswith('min') else '') if k else who
    same = {}
    for c in sorted(chants, key=nat):
        same.setdefault(c['label'], []).append(c)
    for group in same.values():
        if len(group) > 1:
            for i, c in enumerate(group, 1):
                c['label'] += f' ({i})'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--redraw', action='store_true')
    args = ap.parse_args()
    os.makedirs(os.path.join(SITE, 'notation'), exist_ok=True)

    exe = None
    chants = []
    drawn = failed = 0
    for row in paths.catalog():
        name = row['Chant']
        ly = paths.chant_file(name)
        if not ly:
            sys.stderr.write(f'  catalog lists {name}, but {name}.ly is missing\n')
            continue
        img = os.path.join(SITE, 'notation', name + '.png')
        if args.redraw or not os.path.exists(img) or os.path.getmtime(img) < os.path.getmtime(ly):
            exe = exe or build.lilypond_exe()
            if draw(exe, name, img):
                drawn += 1
            else:
                failed += 1
        info = chantinfo.info(ly)
        rating = row.get('Rating', '').strip()
        chants.append({
            'id': name, 'composer': row.get('Composer', ''), 'years': row.get('Years', ''),
            'key': row.get('Key') or info['key'].replace('♯', '#').replace('♭', 'b'),
            'mode': row.get('Mode') or info['mode'].capitalize(),
            'double': (row.get('Single/Double') or ('Double' if info['double'] else 'Single')) == 'Double',
            'range': info['range'], 'rating': int(rating) if rating.isdigit() else None,
            'mood': tags(row.get('Mood')), 'notes': row.get('Notes', ''), 'pins': ['favorite' if x == 'favourite' else x for x in tags(row.get('Pin'))],
            'source': row.get('Source', ''), 'acp': row.get('ACP Psalm', ''),
            'img': os.path.exists(img), 'voices': info['voices'],
            'private': row['private'],
        })
    label_chants(chants)
    tone_endings, tone_groups_data = tones_data(args.redraw)
    data = {'aliases': paths.aliases(), 'vocabulary': vocabulary(), 'chants': chants, 'tones': tone_endings, 'toneGroups': tone_groups_data, 'texts': texts(), 'history': history(), 'calendar': calendar(),
            'unconfirmed': unconfirmed(), 'gloria': gloria_body(), 'service': service_data(),
            'parish': {'name': lectionary.PARISH.get('name', ''), 'track': lectionary.PARISH.get('track', '2'),
                       'optional': build.optional_default()},
            'demo': bool(os.environ.get('PSALTER_DEMO')),      # the copy on GitHub Pages (.github/workflows/pages.yml)
            }
    with open(os.path.join(SITE, 'data.js'), 'w', encoding='utf-8') as fh:
        fh.write('window.PSALTER = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')
    open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8').write(page_html())
    tagged = sum(1 for c in chants if c['mood'])
    print(f'{len(chants)} chants ({tagged} with moods), {len(data["texts"])} texts, {len(data["history"])} history rows')
    if drawn or failed:
        print(f'notation drawn for {drawn} chant(s)' + (f', {failed} failed' if failed else ''))
    print('open ' + os.path.relpath(os.path.join(SITE, 'index.html'), os.getcwd()))


if __name__ == '__main__':
    main()

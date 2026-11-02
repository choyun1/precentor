#!/usr/bin/env python3
"""The music library: the anthems (and other pieces) a parish has, so the planner can suggest them.

    python tools/library.py                  # what's in the library, by season
    python tools/library.py from-record      # start a library from every anthem already sung
    python tools/library.py scan             # look through the score folders for PDFs not in the library

The library is optional, and needs no particular way of keeping music. It is one spreadsheet,
parish/library/catalog.csv (UTF-8), one row per piece, and every column but Title may be left empty:

    Composer, Title, Catalog no.   who and what; Years (1852-1924) completes "Title - Composer (dates)"
    Format                         PDF, Octavo or Book (a piece can be a PDF and have octavos too)
    Season, Occasion               when it fits: advent christmas epiphany lent holy_week easter pentecost,
                                   or empty for any time; Occasion is a day or feast, e.g. Ascension
    File                           a PDF's path inside a score folder (any folders, any depth)
    Location, Copies, Publisher no.  where the paper copies are, how many, and the number to order more by
    Voicing, Words, Notes          e.g. SATB, organ; Words names its file in parish/anthems/

How someone keeps their scores goes in parish/library/library.txt, with the parish's other files. Every line
is optional:

    catalog:         D:/Music/catalog.csv                       # keep the catalog somewhere else
    score folders:   ~/Sync/Music/Sacred; D:/Music/Sacred       # where the PDFs are: ~ is your home folder on
                                                                # each computer, and a folder a computer
                                                                # doesn't have is passed over there
    names:           {composer}-{title}                         # how a PDF's name reads (_ for spaces)
    file new pdfs:   {season}/{composer}-{title}.pdf            # where a PDF added in the planner goes
    folder seasons:  Advent = advent, Christmas = christmas, General = any   # a folder suggests a season
    skip folders:    Hymns, Chant_resources
"""
import csv, datetime as dt, os, re, shutil, sys, unicodedata

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths   # noqa: E402

COLUMNS = ['Composer', 'Title', 'Catalog no.', 'Years', 'Format', 'Season', 'Occasion', 'Voicing', 'File',
           'Location', 'Copies', 'Publisher no.', 'Words', 'Notes']
FORMATS = ('PDF', 'Octavo', 'Book')
SEASONS = ('advent', 'christmas', 'epiphany', 'lent', 'holy_week', 'easter', 'pentecost')
DIR = os.path.join(paths.HOME, 'library')


# ------------------------------------------------------------------ settings
def _settings_file(path, out):
    if os.path.exists(path):
        for line in paths.read(path).splitlines():
            if line.lstrip().startswith('#'):
                continue
            k, sep, v = re.sub(r'\s+#.*$', '', line).partition(':')
            if sep and k.strip() and not re.fullmatch(r'[A-Za-z]', k.strip()):   # C:\... is a path, not a key
                out[k.strip().lower()] = v.strip()
    return out


def settings():
    return _settings_file(os.path.join(DIR, 'library.txt'), {})


def _list(v, sep=r'[;,]'):
    return [x.strip() for x in re.split(sep, v or '') if x.strip()]


def catalog_file(s=None):
    s = settings() if s is None else s
    return os.path.expanduser(s['catalog']) if s.get('catalog') else os.path.join(DIR, 'catalog.csv')


def score_folders(s=None):
    s = settings() if s is None else s
    """The score folders this computer has: list each computer's, and each uses its own."""
    return [p for p in (os.path.expanduser(f) for f in _list(s.get('score folders'), r';')) if os.path.isdir(p)]


def folder_seasons(s=None):
    """'Advent = advent, Christmas = christmas epiphany, General = any' -> {'advent': 'advent', ...} (first season)"""
    s = settings() if s is None else s
    out = {}
    for pair in _list(s.get('folder seasons'), r',|;'):
        k, _, v = pair.partition('=')
        v = (v.split() or [''])[0].lower()
        out[k.strip().lower()] = '' if v in ('any', 'all', '') else v
    return out


# ------------------------------------------------------------------ the catalog
def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', s.lower())


def surname(composer):
    name = re.sub(r'\(.*?\)', '', composer or '').strip()
    return norm(name.split()[-1]) if name else ''


def read(path=None):
    path = path or catalog_file()
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig', newline='') as fh:
        rows = [{c: (r.get(c) or '').strip() for c in COLUMNS} | {k: (v or '').strip() for k, v in r.items() if k and k not in COLUMNS}
                for r in csv.DictReader(fh)]
    return [r for r in rows if r['Title']]


def in_git(path):
    """Whether the catalog is in the parish's (git) folder, so Undo covers it."""
    import history
    p = os.path.abspath(path)
    return p.startswith(os.path.abspath(paths.HOME) + os.sep) and bool(history.repo_of(p))


def write(rows, path=None):
    """Write the catalog; a copy of the old one is kept (in backups/ beside it) when it isn't in git."""
    path = path or catalog_file()
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    if os.path.exists(path) and not in_git(path):
        b = os.path.join(os.path.dirname(path), 'backups')
        os.makedirs(b, exist_ok=True)
        shutil.copy2(path, os.path.join(b, dt.datetime.now().strftime('catalog-%Y%m%d-%H%M%S.csv')))
    extra = [k for r in rows for k in r if k not in COLUMNS]
    cols = COLUMNS + list(dict.fromkeys(extra))
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (surname(r['Composer']), norm(r['Title']))))
    return path


def piece(r):
    """The planner's way of writing it: 'Title - Composer (dates)'."""
    comp = r['Composer'] + (f" ({r['Years']})" if r.get('Years') and r['Composer'] else '')
    return f"{r['Title']} - {comp}" if comp else r['Title']


def split_piece(value):
    title, sep, composer = (value or '').rpartition(' - ')
    if not sep:
        return value.strip(), '', ''
    m = re.search(r'\s*\(([^)]*\d[^)]*)\)\s*$', composer)
    return title.strip(), composer[:m.start()].strip() if m else composer.strip(), m.group(1) if m else ''


def find(rows, value):
    """The row for 'Title - Composer (dates)', or None. Byrd's Ave verum is not Mozart's."""
    title, composer, _ = split_piece(value)
    hits = [r for r in rows if norm(r['Title']) == norm(title)]
    if composer:
        hits = [r for r in hits if surname(r['Composer']) == surname(composer)]
    return hits[0] if hits else None


def clean(row):
    """A row as the planner sent it, checked."""
    r = {c: (row.get(c) if isinstance(row.get(c), str) else '').strip() for c in COLUMNS}
    if not r['Title']:
        raise ValueError('a piece needs a title')
    if r['Format'] and r['Format'] not in FORMATS:
        raise ValueError('Format is PDF, Octavo or Book')
    r['Season'] = r['Season'].lower().replace(' ', '_')
    if r['Season'] and r['Season'] not in SEASONS:
        raise ValueError('Season is one of ' + ', '.join(SEASONS) + ', or empty for any time')
    if r['Copies'] and not r['Copies'].isdigit():
        raise ValueError('Copies is a number')
    return r


def add(row, rows=None):
    """Add a piece, or fill in the empty fields of the one already there (nothing written is replaced).
    -> (rows, the row, new?)"""
    rows = read() if rows is None else rows
    new = clean(row)
    old = find(rows, piece(new))
    if old:
        old.update({k: v for k, v in new.items() if v and not old.get(k)})
        return rows, old, False
    rows.append(new)
    return rows, new, True


# ------------------------------------------------------------------ starting from the record
def season_of(dates):
    """The season a piece belongs to, from the dates it was sung: one season for most of them, else '' (any time).
    The season after Pentecost is half the year, so a piece sung then is taken as for any time."""
    import lectionary
    seen = [lectionary.season(dt.date.fromisoformat(d[:10])) for d in dates if re.match(r'\d{4}-\d\d-\d\d', d)]
    if not seen:
        return ''
    best = max(set(seen), key=seen.count)
    return best if best != 'pentecost' and seen.count(best) / len(seen) >= 0.75 else ''


def from_record(rows=None, repertoire=None):
    """A row for every anthem already sung that isn't in the library. -> (rows, how many added)"""
    import service
    rows = read() if rows is None else rows
    rep = service.repertoire() if repertoire is None else repertoire
    n = 0
    for item, dates in rep.get('anthem', []):
        if service.hymns(item) or find(rows, item):
            continue
        title, composer, years = split_piece(item)
        rows.append({c: '' for c in COLUMNS} | {'Title': title, 'Composer': composer, 'Years': years,
                                                 'Season': season_of(dates)})
        n += 1
    return rows, n


# ------------------------------------------------------------------ PDFs in the score folders
CATALOG_NO = re.compile(r'^((?:Op|BWV|HWV|SWV|SV|KV|K|RV|WAB|Hob|D|TWV|BuxWV|ZWV|Z)\.?_?\d+[a-z]?(?:_\d+)?)-(.+)$', re.I)


def parse_name(filename, pattern='{composer}-{title}'):
    """'Fauré-Op_048-Requiem.pdf' -> {Composer: Fauré, Catalog no.: Op. 48, Title: Requiem}. A name that doesn't
    fit the pattern becomes the title alone."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    pat = os.path.splitext(pattern)[0] if pattern.lower().endswith('.pdf') else pattern
    rx = re.escape(pat)
    for k in ('composer', 'title', 'catalog', 'season'):
        rx = rx.replace(re.escape('{' + k + '}'), f'(?P<{k}>.+?)' if k != 'title' else f'(?P<{k}>.+)')
    m = re.fullmatch(rx, stem)
    got = {k: v for k, v in (m.groupdict() if m else {'title': stem}).items()}
    out = {'Composer': got.get('composer', ''), 'Title': got.get('title', stem), 'Catalog no.': got.get('catalog', '')}
    if not out['Catalog no.']:
        c = CATALOG_NO.match(out['Title'])
        if c:
            out['Catalog no.'], out['Title'] = c.group(1), c.group(2)
    if out['Catalog no.']:
        p = re.match(r'([A-Za-z]+)\.?_?0*(\d.*)$', out['Catalog no.'])
        if p:
            letters = p.group(1)
            out['Catalog no.'] = (letters.capitalize() + '.' if letters.lower() == 'op' else letters.upper()
                                  if len(letters) <= 3 else letters) + ' ' + p.group(2).replace('_', '/')
    for k in out:
        out[k] = re.sub(r'\s+', ' ', out[k].replace('_', ' ')).strip()
    out['Composer'] = re.sub(r'\s+([A-Z])$', r', \1', out['Composer'])        # Thomson_R -> Thomson, R
    return out


def _files(folder, skip):
    for d, subs, files in os.walk(folder):
        subs[:] = sorted(s for s in subs if s.lower() not in skip and not s.startswith(('.', '_')) and s != 'backups')
        for f in sorted(files):
            if f.lower().endswith('.pdf'):
                yield os.path.relpath(os.path.join(d, f), folder).replace(os.sep, '/')


def scan(rows=None, s=None):
    """What's in the score folders and not in the catalog, and the other way about.
    -> {'new': [draft rows], 'moved': [[row's file, where it is now]], 'missing': [files]}"""
    s = settings() if s is None else s
    rows = read() if rows is None else rows
    skip = {x.lower() for x in _list(s.get('skip folders'))}
    seasons, pattern = folder_seasons(s), s.get('names') or '{composer}-{title}'
    found = [f for folder in score_folders(s) if os.path.isdir(folder) for f in _files(folder, skip)]
    have = {r['File'] for r in rows if r['File']}
    by_name = {}
    for f in found:
        by_name.setdefault(os.path.basename(f).lower(), []).append(f)
    out = {'new': [], 'moved': [], 'missing': []}
    for r in rows:
        if r['File'] and r['File'] not in found:
            elsewhere = [f for f in by_name.get(os.path.basename(r['File']).lower(), []) if f not in have]
            (out['moved'].append([r['File'], elsewhere[0]]) if len(elsewhere) == 1 else out['missing'].append(r['File']))
    moved_to = {b for _, b in out['moved']}
    for f in found:
        if f in have or f in moved_to:
            continue
        top = f.split('/')[0].lower() if '/' in f else ''
        draft = {c: '' for c in COLUMNS} | parse_name(f, pattern) | {'Format': 'PDF', 'File': f, 'Season': seasons.get(top, '')}
        same = find(rows, piece(draft))
        out['new'].append(draft | ({'Matches': piece(same)} if same else {}))     # keeping it gives that row its PDF
    return out


def apply_moves(rows, moved):
    for old, new in moved:
        for r in rows:
            if r['File'] == old:
                r['File'] = new
    return rows


def score_path(file, s=None):
    """The PDF a row's File names, on this computer; never anything outside a score folder."""
    for folder in score_folders(s):
        p = os.path.realpath(os.path.join(folder, file))
        if p.startswith(os.path.realpath(folder) + os.sep) and os.path.isfile(p):
            return p
    return None


def place_pdf(row, data, s=None):
    """Put a PDF added in the planner into the first score folder, named by the 'file new pdfs' rule (or as it
    came). -> its File path"""
    s = settings() if s is None else s
    folders = score_folders(s)
    if not folders:
        raise ValueError('no score folder is set: add "score folders:" to parish/library/library.txt')
    if not data.startswith(b'%PDF'):
        raise ValueError('that file is not a PDF')
    rule = s.get('file new pdfs') or '{composer}-{title}.pdf'
    us = lambda v: re.sub(r'[\\/:*?"<>|]', '', re.sub(r'\s+', '_', (v or '').strip()))
    vals = {'composer': us(row['Composer']) or 'Anonymous', 'title': us(row['Title']),
            'catalog': us(row['Catalog no.'].replace('.', '')), 'season': ''}
    # {season}: the folder that holds this season's music, as the person named it (folder seasons:), if there is one
    fs = folder_seasons(s)
    here = sorted(os.listdir(folders[0])) if os.path.isdir(folders[0]) else []
    vals['season'] = next((f for f in here if os.path.isdir(os.path.join(folders[0], f))
                           and fs.get(f.lower(), None) == row['Season']), '')
    rel = re.sub(r'/+', '/', rule.format(**vals)).strip('/')
    rel = re.sub(r'(^|/)[-_]+|[-_]+(?=\.pdf$)|(?<=-)-+', r'\1', rel)       # what an empty {catalog} leaves behind
    if not rel.lower().endswith('.pdf'):
        rel += '.pdf'
    dest = os.path.realpath(os.path.join(folders[0], rel))
    if not dest.startswith(os.path.realpath(folders[0]) + os.sep):
        raise ValueError('that name would go outside the score folder')
    if os.path.exists(dest):
        raise ValueError(f'there is already a {rel}')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, 'wb').write(data)
    return rel


# ------------------------------------------------------------------ for the page
def folder_status(s=None):
    """Whether this computer has a score folder, or which listed ones it looked for. The page is built once and
    committed, so the launcher tells it again on each computer (serve.py's /api/ping)."""
    s = settings() if s is None else s
    found = score_folders(s)
    return {'folders': bool(found),
            'unfound': [] if found else [os.path.expanduser(f) for f in _list(s.get('score folders'), r';')]}


def page_data():
    s = settings()
    return {'rows': read(), **folder_status(s), 'seasons': list(SEASONS), 'formats': list(FORMATS),
            'where': os.path.relpath(catalog_file(s), paths.HOME).replace(os.sep, '/')
            if catalog_file(s).startswith(paths.HOME) else catalog_file(s)}


def main():
    a = sys.argv[1:]
    if a and a[0] == 'from-record':
        rows, n = from_record()
        print(f'{n} pieces added from the record -> {write(rows)}')
    elif a and a[0] == 'scan':
        r = scan()
        for x in r['new']:
            print('new:    ', x['File'], '->', piece(x), f"({x['Season'] or 'any time'})")
        for old, new in r['moved']:
            print('moved:  ', old, '->', new)
        for f in r['missing']:
            print('missing:', f)
        if not score_folders():
            print('no score folders set on this computer (score folders: in parish/library/library.txt)')
    else:
        rows = read()
        for season in SEASONS + ('',):
            these = [r for r in rows if r['Season'] == season]
            if these:
                print(f'{season or "any time"} ({len(these)})')
                for r in these:
                    print('   ', piece(r), f"[{r['Format']}]" if r['Format'] else '')
        if not rows:
            print('no library yet:', catalog_file())


if __name__ == '__main__':
    main()

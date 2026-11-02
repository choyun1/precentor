"""Where things live.

Precentor (this folder) is the general part: tools, style, texts, public-domain chants, lectionary,
tones. Everything belonging to one parish lives in its own folder, `parish/` inside this one
(its own private git repository):

    parish/parish.txt          name, lectionary track, patronal feast, Christmas psalms
    parish/chant_notes.csv     your ratings, mood tags and notes on every chant
    parish/chants/             chants you may not publish (still under copyright), with catalog.csv
    parish/sundays/            one file per Sunday or service
    parish/output/             the PDFs and images built from them
    parish/site/               the chant browser, built for this parish
    parish/legacy/             anything from before (old files, history.csv)

Without a parish folder the tools still work, using the precentor folder for those things.
"""
import csv, functools, os, re

CORE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_p = os.path.join(CORE, 'parish')
PARISH = _p if os.path.isdir(_p) else None
HOME = PARISH or CORE                       # where the parish's own files go

PARISH_TXT = os.path.join(HOME, 'parish.txt')
NOTES = os.path.join(HOME, 'chant_notes.csv')
SUNDAYS = os.path.join(HOME, 'sundays')
OUTPUT = os.path.join(HOME, 'output')
SITE = os.path.join(HOME, 'site')
LEGACY_HISTORY = os.path.join(HOME, 'legacy', 'history.csv')
CHANT_DIRS = [os.path.join(CORE, 'chants')] + ([os.path.join(PARISH, 'chants')] if PARISH else [])
# psalm texts: the general folder has the 1979 BCP words (unpointed unless the pointing may be published);
# a parish's own pointed copies, in parish/texts/, take their place
TEXT_DIRS = [os.path.join(CORE, 'texts')] + ([os.path.join(PARISH, 'texts')] if PARISH else [])
OWN_TEXTS = TEXT_DIRS[-1]                   # where pointing done in the browser is saved
ORIGINALS = os.path.join(OWN_TEXTS, 'originals')   # each text as it was before its first change in the browser

CATALOG_COLUMNS = ['Chant', 'Composer', 'Years', 'Key', 'Mode', 'Single/Double', 'Source', 'ACP Psalm']
NOTE_COLUMNS = ['Chant', 'Rating', 'Mood', 'Notes', 'Pin']    # Pin: favorite, to try, to check


def read(path):
    """A text file's contents (UTF-8)."""
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def text_file(name):
    """The text a name refers to (e.g. Psalm_019): the parish's pointed copy if it has one."""
    for d in reversed(TEXT_DIRS):
        p = os.path.join(d, name + '.txt')
        if os.path.exists(p):
            return p
    return None


def text_names():
    """Every text, by name, from both folders."""
    out = set()
    for d in TEXT_DIRS:
        if os.path.isdir(d):
            out |= {f[:-4] for f in os.listdir(d) if f.endswith('.txt')}
    return sorted(out)


def chant_file(name):
    for d in reversed(CHANT_DIRS):           # a parish copy wins over the public one
        p = os.path.join(d, name + '.ly')
        if os.path.exists(p):
            return p
    return None


def alias_rows():
    """The rows of each chants/aliases.csv: Alias, Chant, Shift, Source."""
    out = []
    for d in CHANT_DIRS:
        p = os.path.join(d, 'aliases.csv')
        if os.path.exists(p):
            with open(p, encoding='utf-8', newline='') as fh:
                out += list(csv.DictReader(l for l in fh if not l.startswith('#')))
    return out


@functools.lru_cache(maxsize=None)
def aliases():
    """{old name: (the chant it is, semitones)}: chants that were copies of others (chants/aliases.csv)."""
    out = {}
    for r in alias_rows():
        try:
            out[r['Alias'].strip()] = (r['Chant'].strip(), int(r.get('Shift') or 0))
        except ValueError:
            pass
    return out


SHIFT = re.compile(r'^(.*?)\s+(up|down)\s+(\d+)$', re.I)


def split_chant(name):
    """'Turle-2 down 2' -> ('Turle-2', -2); an old name stands for the chant it was a copy of:
    'Turle-5' -> ('Turle-2', -2)."""
    name = (name or '').strip()
    shift = 0
    m = SHIFT.match(name)
    if m:
        name, shift = m.group(1).strip(), int(m.group(3)) * (1 if m.group(2).lower() == 'up' else -1)
    base, extra = aliases().get(name, (name, 0))
    return base, shift + extra


def chant_name(base, shift=0):
    """('Turle-2', -2) -> 'Turle-2 down 2' (as a Sunday file writes it)."""
    return base if not shift else f"{base} {'up' if shift > 0 else 'down'} {abs(shift)}"


def canonical(name):
    """Any way of naming a chant -> the one way: 'Turle-5' -> 'Turle-2 down 2'."""
    return name if not name or name.startswith('tone:') or name in ('?', '???') else chant_name(*split_chant(name))


def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def catalog():
    """Every chant: the facts from each catalog.csv, plus your rating, mood and notes."""
    rows, seen = [], {}
    for d in CHANT_DIRS:
        for r in _read(os.path.join(d, 'catalog.csv')):
            r = {k: r.get(k, '') for k in CATALOG_COLUMNS}
            r['private'] = d != CHANT_DIRS[0]
            if r['Chant'] in seen:
                rows[seen[r['Chant']]] = r
            else:
                seen[r['Chant']] = len(rows)
                rows.append(r)
    notes = {r['Chant']: r for r in _read(NOTES)}
    for old, (chant, _) in aliases().items():          # notes kept under a chant's old name join its own
        if old in notes:
            n, o = notes.setdefault(chant, {'Chant': chant}), notes.pop(old)
            for k in ('Rating', 'Notes'):
                if not (n.get(k) or '').strip():
                    n[k] = o.get(k, '')
                elif k == 'Notes' and (o.get(k) or '').strip() and o[k].strip() not in n[k]:
                    n[k] = f"{n[k].strip()} ({old}: {o[k].strip()})"
            for k in ('Mood', 'Pin'):
                tags = [t.strip() for t in re.split(r'[;,]', n.get(k) or '') if t.strip()]
                tags += [t.strip() for t in re.split(r'[;,]', o.get(k) or '') if t.strip() and t.strip() not in tags]
                n[k] = '; '.join(tags)
    for r in rows:
        n = notes.get(r['Chant'], {})
        for k in NOTE_COLUMNS[1:]:
            r[k] = n.get(k, '')
    return rows


def write_notes(rows):
    """rows: dicts with Chant, Rating, Mood, Notes, Pin."""
    os.makedirs(os.path.dirname(NOTES), exist_ok=True)
    with open(NOTES, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, NOTE_COLUMNS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            if any((r.get(k) or '').strip() for k in NOTE_COLUMNS[1:]):
                w.writerow(r)

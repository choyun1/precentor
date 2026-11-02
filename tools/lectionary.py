#!/usr/bin/env python3
"""Which day of the church year a date is, and the psalm the Revised Common Lectionary appoints for it.

    python tools/lectionary.py 2026-11-08          # one date
    python tools/lectionary.py 2026-11-08 8        # the next 8 Sundays from that date

The psalm table is reference/rcl_psalms.csv (Episcopal edition, 1979 BCP numbering).
"""
import csv, datetime as dt, os, re, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
D = dt.date
ONE = dt.timedelta(days=1)


def easter(y):
    """Gregorian Easter (anonymous algorithm)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return D(y, month, day)


def sunday_on_or_after(d):
    return d + dt.timedelta(days=(6 - d.weekday()) % 7)


def advent1(y):
    """First Sunday of Advent: the Sunday from 27 November to 3 December."""
    return sunday_on_or_after(D(y, 11, 27))


def lect_year(d):
    """A, B or C: the year that began on the First Sunday of Advent before (or on) this date."""
    y = d.year if d >= advent1(d.year) else d.year - 1
    return 'ABC'[(y + 1) % 3 - 1] if (y + 1) % 3 else 'C'


NAMES = {
    'advent': 'Advent {n}', 'christmas_sunday1': 'First Sunday after Christmas',
    'christmas_sunday2': 'Second Sunday after Christmas', 'epiphany1': 'First Sunday after the Epiphany (Baptism of Our Lord)',
    'epiphany_last': 'Last Sunday after the Epiphany', 'lent': 'Lent {n}', 'palm_sunday': 'Palm Sunday',
    'easter': 'Easter Day', 'pentecost': 'Day of Pentecost', 'trinity': 'Trinity Sunday', 'easter_n': 'Easter {n}',
    'christmas_eve': 'Christmas Eve',
}


def day_of(d):
    """-> (key, label) for a date: Sundays plus the principal fixed and movable feasts."""
    y = d.year
    E = easter(y)
    fixed = {(12, 24): ('christmas_eve', 'Christmas Eve'), (12, 25): ('christmas_day', 'Christmas Day'),
             (1, 1): ('holy_name', 'The Holy Name'), (1, 6): ('epiphany', 'The Epiphany'),
             (2, 2): ('presentation', 'The Presentation'),
             (8, 6): ('transfiguration', 'The Transfiguration'), (11, 1): ('all_saints', "All Saints' Day")}
    pat = PARISH.get('patronal')
    if pat:
        md, key, *name = pat.split()
        mo, dy = (int(x) for x in md.split('-'))
        fixed[(mo, dy)] = (key, ' '.join(name) + ' (patronal)')
    movable = {E - dt.timedelta(days=46): ('ash_wednesday', 'Ash Wednesday'),
               E - dt.timedelta(days=3): ('maundy_thursday', 'Maundy Thursday'),
               E - dt.timedelta(days=2): ('good_friday', 'Good Friday'),
               E - ONE: ('easter_vigil', 'The Great Vigil of Easter'),
               E + dt.timedelta(days=39): ('ascension', 'Ascension Day')}
    if d in movable:
        return movable[d]
    if (d.month, d.day) in fixed and not (d.month == 12 and d.day == 24):
        return fixed[(d.month, d.day)]
    if d.weekday() != 6:
        if (d.month, d.day) in fixed:
            return fixed[(d.month, d.day)]
        return None, d.strftime('%A')
    # Sundays
    a1 = advent1(y)
    if d >= a1:
        n = (d - a1).days // 7 + 1
        if d < D(y, 12, 25):
            return f'advent{n}', f'Advent {n}'
        return 'christmas_sunday1', 'First Sunday after Christmas'
    if d < D(y, 1, 6):
        return ('christmas_sunday1', 'First Sunday after Christmas') if d.day <= 1 else \
               ('christmas_sunday2', 'Second Sunday after Christmas')
    ash = E - dt.timedelta(days=46)
    if d < ash:
        ep1 = sunday_on_or_after(D(y, 1, 7))
        if d == ash - dt.timedelta(days=3):
            return 'epiphany_last', 'Last Sunday after the Epiphany'
        n = (d - ep1).days // 7 + 1
        label = 'First Sunday after the Epiphany' if n == 1 else f'Epiphany {n}'
        return f'epiphany{n}', label
    if d < E:
        n = (d - (ash + dt.timedelta(days=4))).days // 7 + 1
        return ('palm_sunday', 'Palm Sunday') if n == 6 else (f'lent{n}', f'Lent {n}')
    if d == E:
        return 'easter', 'Easter Day'
    if d < E + dt.timedelta(days=49):
        n = (d - E).days // 7 + 1
        return f'easter{n}', f'Easter {n}'
    if d == E + dt.timedelta(days=49):
        return 'pentecost', 'Day of Pentecost'
    if d == E + dt.timedelta(days=56):
        return 'trinity', 'Trinity Sunday'
    # Propers: Proper n is the Sunday closest to 11 May + 7(n-1) days
    for n in range(1, 30):
        anchor = D(y, 5, 11) + dt.timedelta(days=7 * (n - 1))
        if abs((d - anchor).days) <= 3:
            return f'proper{n}', f'Proper {n}'
    return None, 'Sunday'


def load_parish():
    """parish.txt: the settings specific to one church (name, track, patronal feast, Christmas psalms)."""
    out = {'name': '', 'track': '2'}
    import paths
    path = paths.PARISH_TXT
    if os.path.exists(path):
        for line in paths.read(path).splitlines():
            line = re.sub(r'#(?!(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b).*', '', line).strip()   # a comment (not a color: #6aa84f)
            if ':' in line:
                k, v = line.split(':', 1)
                out[k.strip().lower()] = v.strip()
    return out


PARISH = load_parish()
HOUSE = {}
for _k, _default in (('christmas_eve', 'christmas1 christmas2 christmas3'), ('christmas_day', 'christmas1 christmas2 christmas3')):
    _order = PARISH.get(_k, _default).split()
    HOUSE[_k] = (_order[0], _order[1:])


def table():
    path = os.path.join(ROOT, 'reference', 'rcl_psalms.csv')
    rows = {}
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding='utf-8')):
            for yr in r['year']:
                rows[(r['day'], yr)] = r
    return rows


# ------------------------------------------------------------------ links to the Episcopal Church's lectionary
SITE = 'https://lectionary.episcopalchurch.org'
_links = None


def links():
    """reference/lectionary_links.csv: (key, year) -> the site's page number for that day (filled in by
    tools/lectionary_links.py, which reads the site's month pages)."""
    global _links
    if _links is None:
        p = os.path.join(ROOT, 'reference', 'lectionary_links.csv')
        _links = {(r['key'], r['year']): r['post'] for r in csv.DictReader(open(p, encoding='utf-8'))} \
            if os.path.exists(p) else {}
    return _links


def links_signature():
    """Which version of the link table Precentor was built with (so the launcher can tell)."""
    import hashlib
    p = os.path.join(ROOT, 'reference', 'lectionary_links.csv')
    return hashlib.md5(open(p, 'rb').read()).hexdigest()[:12] if os.path.exists(p) else ''


def office_year(d):
    """The Daily Office year, I or II: Year One begins at Advent before an odd-numbered year."""
    y = d.year + 1 if d >= advent1(d.year) else d.year
    return 'I' if y % 2 else 'II'


def link(d, key=None):
    """The page for this date on lectionary.episcopalchurch.org: the day itself when its page number is
    known, else that month's calendar."""
    if key is None:
        key = day_of(d)[0]
    key = {'christmas_eve': 'christmas_day'}.get(key, key)        # the site keeps Christmas Eve under Christmas Day I
    post = links().get((key, lect_year(d))) if key else None
    if post:
        from urllib.parse import quote
        return f'{SITE}/lectionary-post/{post}?date={d.isoformat()}&year=' + quote(f'Year {lect_year(d)} / {office_year(d)}', safe='')
    return f'{SITE}/{d.year}/{d.month}'


# ------------------------------------------------------------- liturgical colors
# The customary colors of the Episcopal Church, by season, with the feasts that take their own.
# A parish changes any of them in parish.txt:
#     season_colors: advent = purple, easter = gold      # advent christmas epiphany lent holy_week easter pentecost
#     day_colors:    good_friday = red, all_saints = green   # by the day's key (as in reference/rcl_psalms.csv)
#     color_shades:  blue = #3c5aa6                       # how each color is drawn
SEASON_COLORS = {'advent': 'blue', 'christmas': 'white', 'epiphany': 'green', 'lent': 'purple',
                 'holy_week': 'red', 'easter': 'white', 'pentecost': 'green'}
_WHITE = ('christmas_eve christmas_day holy_name epiphany epiphany1 epiphany_last presentation annunciation '
          'easter_vigil easter ascension trinity transfiguration all_saints proper29 visitation st_mary_the_virgin '
          'nativity_of_st_john_baptist st_john confession_of_st_peter conversion_of_st_paul st_joseph '
          'st_mary_magdalene st_michael_and_all_angels thanksgiving')
_RED = ('palm_sunday palm_sunday_palms monday_holy_week tuesday_holy_week wednesday_holy_week maundy_thursday '
        'pentecost pentecost_vigil holy_innocents st_stephen st_andrew st_thomas st_matthias st_mark '
        'st_philip_and_st_james st_barnabas st_peter_and_st_paul st_james st_bartholomew holy_cross st_matthew '
        'st_luke st_simon_and_st_jude st_james_of_jerusalem')
DAY_COLORS = dict([(k, 'white') for k in _WHITE.split()] + [(k, 'red') for k in _RED.split()] +
                  [('ash_wednesday', 'purple'), ('good_friday', 'black'), ('holy_saturday', 'black')])
SHADES = {'blue': '#3d5a9e', 'purple': '#674ea7', 'white': '#ffffff', 'gold': '#f1c232', 'green': '#6aa84f',
          'red': '#cc0000', 'black': '#000000', 'rose': '#e6a5b8'}


def _pairs(v):
    return {k.strip().lower(): x.strip() for k, x in (p.split('=', 1) for p in v.split(',') if '=' in p)}


def season(d):
    """advent, christmas, epiphany, lent, holy_week, easter or pentecost (the season after Pentecost)."""
    y, E = d.year, easter(d.year)
    if d >= advent1(y):                       # Christmas from Christmas Eve, unless the 24th is Advent 4, a Sunday
        return 'advent' if d < D(y, 12, 24) or (d == D(y, 12, 24) and d.weekday() == 6) else 'christmas'
    if d < D(y, 1, 6):
        return 'christmas'
    if d < E - dt.timedelta(days=46):
        return 'epiphany'
    if d < E - dt.timedelta(days=7):
        return 'lent'
    if d < E - ONE:
        return 'holy_week'
    if d < E + dt.timedelta(days=49):
        return 'easter'
    return 'pentecost' if d > E + dt.timedelta(days=49) else 'easter'


def color(d, key=None):
    """The liturgical color of a date: its feast's, else its season's (parish.txt can change either)."""
    if key is None:
        key = day_of(d)[0]
    days = dict(DAY_COLORS, **_pairs(PARISH.get('day_colors', '')))
    if key is None and (d.month, d.day) == (12, 24):    # a weekday Christmas Eve (a Sunday the 24th is Advent 4)
        key = 'christmas_eve'
    if key and key in days:
        return days[key]
    seasons = dict(SEASON_COLORS, **_pairs(PARISH.get('season_colors', '')))
    return seasons.get(season(d), 'green')


def shades():
    """{color: '#rrggbb'}"""
    def six(v):                                   # '#fff' -> '#ffffff'
        v = v.lstrip('#')
        return '#' + (''.join(c * 2 for c in v) if len(v) == 3 else v).lower()
    return dict(SHADES, **{k: six(v) for k, v in _pairs(PARISH.get('color_shades', '')).items()})


def appointed(d, rows=None, key=None):
    """-> dict(date, key, label, year, psalm, alt) for a date (or for another day kept on it: key='christmas_eve'
    for a Christmas Eve that falls on Advent 4)."""
    rows = rows if rows is not None else table()
    key, label = (key, NAMES.get(key, key.replace('_', ' ').title())) if key else day_of(d)
    yr = lect_year(d)
    if key in HOUSE:
        main, others = HOUSE[key]
        r = rows.get((main, yr))
        alts = [rows[(o, yr)]['psalm'] for o in others if (o, yr) in rows]
        return {'date': d.isoformat(), 'key': key, 'label': label, 'year': yr,
                'psalm': r['psalm'] if r else None, 'alt': alts}
    r = rows.get((key, yr)) if key else None
    return {'date': d.isoformat(), 'key': key, 'label': label, 'year': yr,
            'psalm': r['psalm'] if r else None,
            'alt': [a.strip() for a in r['alt'].split('|') if a.strip()] if r and r.get('alt') else []}


def main():
    d = D.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else D.today()
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rows = table()
    if n > 1:
        d = sunday_on_or_after(d)
    for i in range(n):
        a = appointed(d + dt.timedelta(days=7 * i), rows)
        fmt = lambda p: ('Psalm ' + p) if p and p[0].isdigit() else (p or '?')
        if a['key'] and a['key'].startswith('proper') and a['alt']:
            # the table's order: Track 1's psalm, Track 2's, then the others (Track 1's alternatives, nearly always)
            what = f"Track 1: {fmt(a['psalm'])}" + ''.join(f' or {fmt(x)}' for x in a['alt'][1:]) + \
                   f"   Track 2: {fmt(a['alt'][0])}"
        else:
            what = fmt(a['psalm']) + ''.join(f'  or {fmt(x)}' for x in a['alt'])
        print(f"{a['date']}  {a['label']:<38} Year {a['year']}  {what}")


if __name__ == '__main__':
    main()

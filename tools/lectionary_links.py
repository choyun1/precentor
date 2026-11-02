#!/usr/bin/env python3
"""Find the page for each Sunday and feast on lectionary.episcopalchurch.org, for links to it.

    python tools/lectionary_links.py            # read the site's month pages, update the table
    python tools/lectionary_links.py 2025 2028  # the months from Advent 2025 to the end of 2028

The site gives each day's page a number (lectionary-post/89 is Proper 21, Year A), which can only be
found on its month pages (lectionary.episcopalchurch.org/2026/9). This reads them, matches each Sunday
and feast to the day Precentor's lectionary has for that date, and keeps the numbers in
reference/lectionary_links.csv, saving after each month (so stopping it keeps what it found). One
three-year cycle is enough, since the same page serves the same day every third year. The site keeps
no months before December 2025, so by default this reads from Advent last year to the end of the
year after next, which covers Years A, B and C. A day still missing links to its month's calendar
instead. Run it again if the site changes.
"""
import csv, datetime as dt, html, os, re, sys, time, urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import lectionary   # noqa: E402

OUT = os.path.join(ROOT, 'reference', 'lectionary_links.csv')
ANCHOR = re.compile(r'<a\b[^>]*href="[^"]*lectionary-post/(\d+)\?date=(\d{4}-\d{2}-\d{2})(?:&amp;|&)year=([^"]*)"[^>]*>(.*?)</a>',
                    re.S | re.I)
STOP = {'the', 'of', 'a', 'b', 'c', 'day', 'and', 'in', 'our', 'lord', 'saint'}


def month_page(y, m):
    req = urllib.request.Request(f'{lectionary.SITE}/{y}/{m}', headers={'User-Agent': 'precentor (lectionary links)'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8', 'replace')


def anchors(page):
    """-> [(post, date, year, title)]"""
    out = []
    for post, date, year, text in ANCHOR.findall(page):
        title = html.unescape(re.sub(r'<[^>]+>', ' ', text))
        out.append((post, date, html.unescape(year).replace('%20', ' ').replace('%2F', '/'), ' '.join(title.split())))
    return out


def words(s):
    return {w for w in re.findall(r'[a-z]+', s.lower()) if w not in STOP}


def best(cands, label, d):
    """The link for the appointed day among a date's links (a saint may share the date)."""
    def score(c):
        post, date, year, title = c
        sc = 10 * len(words(label) & words(title))       # the day's own name first (All Saints on a Sunday)
        if d.weekday() == 6 and 'sunday' in title.lower():
            sc += 2
        if '/' in year:                       # Sundays and the principal feasts carry the office year too
            sc += 1
        return sc
    return max(cands, key=score)


def main():
    a = [int(x) for x in sys.argv[1:3]]
    today = dt.date.today()
    first = a[0] if a else today.year - 1
    last = a[1] if len(a) > 1 else today.year + 2
    rows = lectionary.table()
    found = {}
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT, encoding='utf-8')):
            found[(r['key'], r['year'])] = (r['post'], r['title'])
    months = [(first, 11), (first, 12)] + [(y, m) for y in range(first + 1, last + 1) for m in range(1, 13)]
    new = 0

    def save():
        with open(OUT, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(['key', 'year', 'post', 'title'])
            for (k, yr), (post, title) in sorted(found.items(), key=lambda x: (x[0][1], x[0][0])):
                w.writerow([k, yr, post, title])
    try:
        for y, m in months:
            new += read_month(y, m, rows, found)
            save()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('stopped: what was found so far is saved')
    keys = {(k, yr) for (k, yr) in rows}
    print(f'{len(found)} days linked ({new} new or changed); {len(keys - set(found))} of the psalm table\'s days not yet seen')
    import subprocess                               # Precentor's links are made when it's built
    print('rebuilding Precentor…')
    subprocess.run([sys.executable, os.path.join(TOOLS, 'browser.py')], cwd=ROOT)


def read_month(y, m, rows, found):
    """Add one month's Sundays and feasts to found; returns how many were new or changed."""
    new = 0
    try:
        page = month_page(y, m)
    except Exception as e:
        print(f'{y}-{m:02d}: could not read ({e})')
        return 0
    by_date = {}
    for c in anchors(page):
        by_date.setdefault(c[1], []).append(c)
    for date, cands in by_date.items():
        d = dt.date.fromisoformat(date)
        ap = lectionary.appointed(d, rows)
        if not ap['key']:
            continue
        post, _, _, title = best(cands, ap['label'], d)
        k = (ap['key'], ap['year'])
        if found.get(k, (None,))[0] != post:
            new += 1
        found[k] = (post, title)
    print(f'{y}-{m:02d}: {len(by_date)} days')
    return new


if __name__ == '__main__':
    main()

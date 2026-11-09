#!/usr/bin/env python3
"""Run Precentor with its Service planner switched on.

    python tools/serve.py           # opens http://localhost:8765 in your web browser; Ctrl+C to stop

With this running, the browser can save chant tags straight to your chant notes, write Sunday
files, run the checks, and build the PDF and images with one click. It only listens on your own
computer (localhost), answers only pages it served itself, and shows only the site, the built
output and the fonts. Opening site/index.html directly still works, without those buttons.

Each request the page can make is one function below, listed in ROUTES; a parish's plugins add
their own (tools/plugins.py). Every save is recorded for Undo (tools/history.py).
"""
import csv, datetime as dt, io, http.server, json, os, re, subprocess, sys, threading, urllib.parse, webbrowser

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
PORT = int(os.environ.get('PRECENTOR_PORT') or os.environ.get('PSALTER_PORT') or '8765')
PY = sys.executable
sys.path.insert(0, TOOLS)
import paths, history   # noqa: E402
SITE_URL = '/' + os.path.relpath(paths.SITE, ROOT).replace(os.sep, '/') + '/index.html'
SERVED = [paths.SITE, paths.OUTPUT, os.path.join(ROOT, 'style')]     # the only folders a page may read
MAX_BODY = 20 * 1024 * 1024


# ------------------------------------------------------------------ running the tools
def run(args, timeout=900):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')    # Windows' console code page can't print ✓
    r = subprocess.run([PY, os.path.join(TOOLS, args[0])] + args[1:], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.returncode, (r.stdout + ('\n' + r.stderr if r.stderr.strip() else '')).strip()


REBUILD = threading.Lock()


def rebuild(what='Precentor'):
    """Rebuild Precentor's pages, then record them (out of the History list)."""
    with REBUILD:
        code, out = run(['browser.py'])
    history.record_generated(what)
    return code, out


def rebuild_later(what='Precentor'):
    threading.Thread(target=lambda: rebuild(what), daemon=True).start()


# ------------------------------------------------------------------ checking what the page sends
def safe_name(name):
    """A file name the page may use: letters, digits, - and _; nothing that reaches another folder."""
    name = name.strip() if isinstance(name, str) else ''
    if not name or name.startswith(('.', '-')) or not all(c.isalnum() or c in '-_' for c in name):
        raise ValueError('file names may use letters, digits, - and _ only')
    return name


def text_arg(data, key, required=True):
    v = data.get(key)
    if v is None and not required:
        return ''
    if not isinstance(v, str):
        raise ValueError(f'{key} must be text')
    return v


def sunday_path(data):
    return os.path.join(paths.SUNDAYS, safe_name(data.get('name')) + '.txt')


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, '/')


# ------------------------------------------------------------------ the requests
def api_notes(data):
    """Chant notes (rating, mood, notes, pin) for every chant, as csv."""
    reader = csv.DictReader(io.StringIO(text_arg(data, 'csv')))
    if 'Chant' not in (reader.fieldnames or []):
        raise ValueError('the notes have no Chant column')
    rows = list(reader)
    before = paths._read(paths.NOTES)
    paths.write_notes(rows)
    history.record([paths.NOTES], history.describe_notes(before, paths._read(paths.NOTES)))
    code, out = rebuild()                 # the notes are saved; this only refreshes the page
    return {'ok': True, 'rebuilt': code == 0, 'log': out}


def api_sunday(data):
    """Write a Sunday file."""
    text, fp = text_arg(data, 'text'), sunday_path(data)
    os.makedirs(paths.SUNDAYS, exist_ok=True)
    new = not os.path.exists(fp)
    with open(fp, 'w', encoding='utf-8') as fh:
        fh.write(text)
    history.record([fp], ('New service: ' if new else 'Service: ') + os.path.basename(fp)[:-4])
    return {'ok': True, 'path': rel(fp)}


def api_sung(data):
    """Mark a Sunday as sung (it then counts in the history), or not."""
    fp = sunday_path(data)
    if not os.path.exists(fp):
        raise ValueError(f'no Sunday file {os.path.basename(fp)}')
    yes = data.get('sung', True) is not False
    lines = [l for l in paths.read(fp).splitlines() if not l.strip().lower().startswith('sung:')]
    if yes:
        lines.append('sung:    yes')
    open(fp, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    history.record([fp], ('Marked as sung: ' if yes else 'Marked as not sung: ') + os.path.basename(fp)[:-4])
    rebuild()
    return {'ok': True}


def api_commit(data):
    """Sync with GitHub: bring in what's new there, send what's new here."""
    msg = (data.get('message') if isinstance(data.get('message'), str) else '') or 'Changes made outside Precentor'
    P = history.PROGRESS
    P.update(done=0, total=history.SYNC_STEPS * len(history.repos()), step='starting')
    try:
        with REBUILD:                                 # not while a rebuild is writing the pages
            ok, log = history.sync(msg.strip())
        if ok and (history.STALE.pop('site', None) or page_out_of_date()):   # (or an update came in)    # pages built on both sides: build them afresh, and send those too
            P.update(total=P['total'] * 2 + 1)
            history.step('building the pages again with what came in')
            rebuild('after bringing in changes')
            with REBUILD:
                history.sync(msg.strip())
    finally:
        P.update(done=P['total'], step='done')
    if ok and code_changed():                        # the update brought new tools: this launcher still runs the old
        threading.Timer(0.5, restart).start()
        return {'ok': ok, 'log': log, 'restarting': True}
    return {'ok': ok, 'log': log}


def code_changed():
    """Whether the tools have changed since this launcher started (a Sync brought in an update)."""
    import browser
    return SERVING.get('code') not in (None, browser.page_signature())


def api_undo(data):
    ok, msg = history.undo(text_arg(data, 'repo'), text_arg(data, 'sha'))
    if not ok:
        return {'ok': False, 'error': msg}
    code, _ = rebuild('after an undo')
    return {'ok': True, 'undid': msg, 'rebuilt': code == 0}


def api_anthem(data):
    """Keep an anthem's words (parish/anthems/)."""
    import service
    one_line = lambda k: ' '.join(text_arg(data, k, required=False).split())
    title = one_line('title')
    if not title:
        raise ValueError('the anthem needs a title')
    f = service.write_anthem(title, one_line('composer'), one_line('source'), text_arg(data, 'text', required=False))
    history.record([f], 'Anthem words: ' + title)
    rebuild_later()
    return {'ok': True, 'file': rel(f)}


def api_open(data):
    """Open a Sunday's output folder on this computer."""
    name = safe_name(data.get('name'))
    folder = os.path.join(paths.OUTPUT, name, safe_name(data['sub']) if data.get('sub') else '')
    if not os.path.isdir(folder):
        raise ValueError('nothing built yet for ' + name)
    if sys.platform.startswith('win'):
        os.startfile(folder)
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', folder])
    return {'ok': True}


# ------------------------------------------------------------------ the music library (tools/library.py)
def _save_library(rows, message):
    import library
    f = library.write(rows)
    if library.in_git(f):                  # elsewhere (beside the scores) a dated copy is kept instead
        history.record([f], message)
    rebuild_later('the music library')
    return f


def api_library_add(data):
    """Add a piece to the library, or fill in the one there; with a PDF (base64), put it in the score folder."""
    import base64, library
    row = data.get('row') if isinstance(data.get('row'), dict) else {}
    rows, r, new = library.add(row)
    if data.get('pdf'):
        if r['File']:
            raise ValueError(f"{library.piece(r)} already has a PDF: {r['File']}")
        r['File'], r['Format'] = library.place_pdf(r, base64.b64decode(text_arg(data, 'pdf'))), r['Format'] or 'PDF'
    _save_library(rows, ('Library: added ' if new else 'Library: ') + library.piece(r))
    return {'ok': True, 'row': r, 'new': new}


def api_library_from_record(data):
    """Start (or add to) the library from every anthem and organ piece already done."""
    import library
    rows, n = library.from_record()
    if n:
        _save_library(rows, f'Library: {n} pieces from the record')
    return {'ok': True, 'added': n, 'rows': library.rows_for_page(rows)}


def api_library_scan(data):
    """PDFs in the score folders not yet in the library (and files that moved or went missing)."""
    import library
    return {'ok': True, **library.scan()}


def api_library_keep(data):
    """Keep what a scan found: new rows (as checked on the page) and the files that moved."""
    import library
    rows = library.read()
    library.apply_moves(rows, [m for m in data.get('moved') or [] if isinstance(m, list) and len(m) == 2])
    n = 0
    for row in data.get('rows') or []:
        if isinstance(row, dict):
            rows, _, new = library.add(row, rows)
            n += new
    _save_library(rows, f'Library: {n} new PDFs from the score folders')
    return {'ok': True, 'added': n, 'rows': library.rows_for_page(rows)}


def api_score(data):
    """Open a piece's PDF on this computer."""
    import library
    p = library.score_path(text_arg(data, 'file'))
    if not p:
        raise ValueError('that PDF is not in a score folder on this computer')
    if sys.platform.startswith('win'):
        os.startfile(p)
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', p])
    return {'ok': True}


def api_text(data):
    """One verse's pointing: checked (check: true, for this Sunday's own pointing, nothing saved), or saved into the
    text, after checking it keeps one * and the BCP's words. The text as it was before its first change is kept
    (parish/texts/originals/), so the original pointing can always be put back."""
    import pointed, check_texts, shutil
    name, n = safe_name(data.get('id')), str(data.get('n'))
    src = paths.text_file(name)
    if not src:
        raise ValueError(f'no text {name}')
    try:
        new = pointed.parse('x\n' + text_arg(data, 'block'))['verses']
    except Exception as e:
        return {'ok': False, 'error': f'cannot read the verse: {e}'}
    if len(new) != 1 or str(new[0]['n']) != n:
        return {'ok': False, 'error': 'keep exactly one verse, with the same number'}
    v = new[0]
    shown = [v['n'], int(v['dagger']), [[l['text'], l['half'], int(l['wrap'])] for l in v['lines']]]
    problems = check_texts.verse_problems(name + '.txt', v)
    if problems:
        return {'ok': False, 'error': '; '.join(problems)}
    if data.get('check'):
        return {'ok': True, 'verse': shown}
    doc = pointed.load(src)
    doc['comments'] = [c for c in doc['comments'] if 'unpointed' not in c.lower()]
    i = next((k for k, x in enumerate(doc['verses']) if str(x['n']) == n), None)
    if i is None:
        raise ValueError(f'{name} has no verse {n}')
    doc['verses'][i] = v
    path = os.path.join(paths.OWN_TEXTS, name + '.txt')        # pointing is the parish's own: saved there
    original = os.path.join(paths.ORIGINALS, name + '.txt')
    os.makedirs(paths.ORIGINALS, exist_ok=True)
    kept = []
    if not os.path.exists(original):
        shutil.copy(src, original)
        kept = [original]
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(pointed.write(doc))
    history.record([path] + kept, f"Pointing: {name.replace('_', ' ')} v. {n}")
    rebuild_later()
    return {'ok': True, 'verse': shown}


def api_check(data):
    code, out = run(['build.py', sunday_path(data), '--check'])
    return {'ok': code == 0, 'log': out}


def api_build(data):
    """Build a Sunday's PDF (and images): the files made, for links."""
    fp = sunday_path(data)
    name = os.path.basename(fp)[:-4]
    code, out = run(['build.py', fp] + (['--pdf-only'] if data.get('pdfOnly') else []))
    outdir = os.path.join(paths.OUTPUT, name)
    files = sorted(rel(os.path.join(dp, f)) for dp, _, fs in os.walk(outdir) for f in fs
                   if f.endswith(('.pdf', '.jpg'))) if os.path.isdir(outdir) else []
    if code == 0:
        rebuild('built ' + name)                 # refresh history and "coming up"
    return {'ok': code == 0, 'log': out, 'files': files}


# ------------------------------------------------------------------ editing chants (tools/chantedit.py)
def chant_name(data, key='name'):
    name = safe_name(data.get(key))
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*-\d+', name):
        raise ValueError('a chant is named like its composer and a number: Turle-7')
    return name


def chant_text(data):
    """The chant's file with the editor's parts put in: the saved file, or a new one from the template."""
    import chantedit
    name = chant_name(data)
    f = paths.chant_file(name)
    text = paths.read(f) if f else chantedit.template(text_arg(data, 'credit', required=False))
    if not isinstance(data.get('parts'), dict) or data['parts'] == chantedit.parts(text):
        return name, text                          # nothing changed: the file as it is, spacing and all
    return name, chantedit.apply(text, data['parts'])


def api_chant_open(data):
    """What the music editor shows of a chant (or of a new one)."""
    import chantedit
    name, text = chant_text(data)
    return {'ok': True, 'exists': bool(paths.chant_file(name)), 'parts': chantedit.parts(text)}


def api_chant_preview(data):
    """A picture of the chant as edited (or of a saved one, transposed), its notes for Play, and what's amiss."""
    import chantedit
    name, text = chant_text(data)
    shift = data.get('shift') or 0
    if not isinstance(shift, int) or abs(shift) > 11:
        raise ValueError('shift: whole semitones, -11 to 11')
    problems, facts = chantedit.check(text)
    img, err = chantedit.render(text, shift)
    return {'ok': img is not None, 'img': img and '/api/chant/img?f=' + img, 'error': err, 'problems': problems,
            'voices': facts and facts['voices'], 'double': facts and facts['double'],
            'half': facts and facts['half']}


def api_chant_save(data):
    """Save a chant's notes (a new chant: its file and its catalog row)."""
    import chantedit
    name, text = chant_text(data)
    new = not paths.chant_file(name)
    private = bool(data.get('private'))
    if new and data.get('details') is None:
        raise ValueError('a new chant needs its details (composer, key…)')
    f, problems = chantedit.save_music(name, text, private)
    files = [f]
    if new or isinstance(data.get('details'), dict):
        files.append(chantedit.save_details(name, data.get('details') or {}, private))
    history.record(files, ('New chant: ' if new else 'Chant music: ') + name)
    rebuild_later()
    return {'ok': True, 'problems': problems, 'file': rel(f)}


def api_chant_details(data):
    """A chant's facts in its catalog: composer, years, key, mode, single/double, source, ACP psalm."""
    import chantedit
    name = chant_name(data)
    if not paths.chant_file(name):
        raise ValueError(f'no chant {name}')
    fields = data.get('fields')
    if not isinstance(fields, dict):
        raise ValueError('fields: the facts to write')
    p = chantedit.save_details(name, fields)
    history.record([p], 'Chant details: ' + name)
    rebuild_later()
    return {'ok': True}


def api_chant_import(data):
    """A new chant's notes, key, time and composer from a MusicXML file (nothing saved: it opens in the editor)."""
    import base64, binascii, musicxml
    if not isinstance(data.get('file'), str):
        raise ValueError('file: the MusicXML file, base64')
    try:
        raw = base64.b64decode(data['file'], validate=True)
    except binascii.Error:
        raise ValueError('file: not base64')
    filename = data.get('filename') if isinstance(data.get('filename'), str) else ''
    name = os.path.basename(filename)[:80] or 'the file'
    try:
        parts, info = musicxml.to_parts(raw, filename)
    except ValueError as e:                      # a score it can't make a chant of says why
        return {'ok': False, 'error': f'{name}: {e}'}
    except Exception as e:                       # a fault in the importer: said so, with the details here
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': f'{name}: the importer failed ({type(e).__name__}: {e}); '
                                      'the launcher\'s window has the details'}
    return {'ok': True, 'parts': parts, 'composer': info['composer'], 'title': info['title'], 'warnings': info['warnings']}


def get_chant_img(q):
    import chantedit
    f = os.path.basename(q.get('f', [''])[0])
    p = os.path.join(chantedit.PREVIEWS, f)
    if not re.fullmatch(r'[0-9a-f]{16}\.png', f) or not os.path.exists(p):
        raise ValueError('no such picture')
    return p


ROUTES = {'/api/chant/open': api_chant_open, '/api/chant/preview': api_chant_preview, '/api/chant/save': api_chant_save,
          '/api/chant/details': api_chant_details, '/api/chant/import': api_chant_import,
          '/api/notes': api_notes, '/api/sunday': api_sunday, '/api/sung': api_sung, '/api/commit': api_commit,
          '/api/undo': api_undo, '/api/anthem': api_anthem, '/api/open': api_open, '/api/score': api_score,
          '/api/library/add': api_library_add, '/api/library/from-record': api_library_from_record,
          '/api/library/scan': api_library_scan, '/api/library/keep': api_library_keep, '/api/text': api_text,
          '/api/check': api_check, '/api/build': api_build}


def get_sunday(q):
    fp = os.path.join(paths.SUNDAYS, safe_name(q.get('name', [''])[0]) + '.txt')
    return {'exists': os.path.exists(fp), 'text': paths.read(fp) if os.path.exists(fp) else ''}


def api_setup(data):
    """The first run: make parish/ from the template with these settings, then start again in it."""
    import setup
    if paths.PARISH:
        raise ValueError('there is a parish folder already')
    done = setup.make_parish(text_arg(data, 'name'), str(data.get('track') or '2'), data.get('patronal') or '',
                             data.get('optionalVerses') or 'sing')
    threading.Timer(0.5, restart).start()            # paths are worked out once, at the start
    return {'ok': True, 'done': done, 'url': '/parish/site/index.html'}


SERVING = {}


def restart():
    """Stop serving; main() then starts the launcher again (see the end of main)."""
    SERVING['restart'] = True
    SERVING['srv'].shutdown()


def get_ping(q):
    if paths.PARISH:
        import library                              # the built page may come from another computer
        return {'ok': True, 'setup': False, 'library': library.folder_status()}
    import setup                                    # no parish folder yet: what the first-run form offers
    return {'ok': True, 'setup': True, 'feasts': [{'key': k, 'name': n, 'date': md} for md, k, n in setup.FEASTS]}


ROUTES['/api/setup'] = api_setup
GETS = {'/api/sync/progress': lambda q: dict(history.PROGRESS), '/api/ping': get_ping, '/api/git': lambda q: {'repos': history.pending()},
        '/api/history': lambda q: {'changes': history.changes()}, '/api/sunday': get_sunday}


# ------------------------------------------------------------------ the server
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, fmt, *args):
        pass

    def reply(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):     # the page was closed or reloaded before the answer came
            pass

    def ours(self):
        """Only this computer's own pages: the Host must be localhost (no DNS rebinding), and a request that
        says where it comes from must come from localhost (another website can't drive the planner)."""
        host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]')
        if host not in ('localhost', '127.0.0.1', '::1'):
            return False
        origin = self.headers.get('Origin')
        if origin and urllib.parse.urlparse(origin).hostname not in ('localhost', '127.0.0.1', '::1'):
            return False
        return True

    def do_GET(self):
        if not self.ours():
            return self.reply({'error': 'local pages only'}, 403)
        u = urllib.parse.urlparse(self.path)
        if u.path == '/':
            self.send_response(302)
            self.send_header('Location', SITE_URL)
            self.end_headers()
            return
        if u.path == '/api/chant/img':                 # a picture of a chant being edited (not in the site)
            try:
                body = open(get_chant_img(urllib.parse.parse_qs(u.query)), 'rb').read()
            except ValueError as e:
                return self.reply({'error': str(e)}, 404)
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'max-age=86400')
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path in GETS:
            try:
                return self.reply(GETS[u.path](urllib.parse.parse_qs(u.query)))
            except ValueError as e:
                return self.reply({'error': str(e)}, 400)
        if u.path == SITE_URL and not REBUILD.locked() and built_before_today():
            rebuild('on a new day')
        target = os.path.realpath(self.translate_path(u.path))
        if not any(target == os.path.realpath(d) or target.startswith(os.path.realpath(d) + os.sep) for d in SERVED):
            return self.reply({'error': 'not found'}, 404)
        return super().do_GET()

    def do_POST(self):
        if not self.ours():
            return self.reply({'error': 'local pages only'}, 403)
        if (self.headers.get('Content-Type') or '').split(';')[0].strip() != 'application/json':
            return self.reply({'error': 'send JSON'}, 415)          # a form on another site can't send JSON
        path = urllib.parse.urlparse(self.path).path
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 <= n <= MAX_BODY:
                raise ValueError('bad length')
            data = json.loads(self.rfile.read(n).decode('utf-8') or '{}')
            if not isinstance(data, dict):
                raise ValueError('bad request')
        except (ValueError, UnicodeDecodeError):
            return self.reply({'error': 'bad request'}, 400)
        try:
            handler = ROUTES.get(path)
            if handler:
                return self.reply(handler(data))
            import plugins                      # a parish plugin's own requests (parish/plugins/)
            handler = plugins.routes().get(path)
            if handler:
                return self.reply(handler(data, {'safe_name': safe_name, 'root': ROOT, 'record': history.record,
                                                 'rebuild': rebuild}))
        except (KeyError, ValueError) as e:
            return self.reply({'error': str(e)}, 400)
        except subprocess.TimeoutExpired:
            return self.reply({'error': 'timed out'}, 500)
        except Exception as e:                  # anything else: say what, so the page isn't left waiting
            return self.reply({'error': f'{type(e).__name__}: {e}'}, 500)
        return self.reply({'error': 'unknown request'}, 404)


class Server(http.server.ThreadingHTTPServer):
    request_queue_size = 32

    def handle_error(self, request, client_address):
        """A page closed or reloaded mid-request (BrokenPipe) is normal: say nothing; anything else, as usual."""
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


def page_out_of_date():
    """Whether the page was built by other code than this (a Sync brought in an update, say)."""
    import browser
    p = os.path.join(paths.SITE, 'data.js')
    return os.path.exists(p) and f'"pageSignature":"{browser.page_signature()}"' not in paths.read(p)


def built_before_today():
    """Whether the page was built on an earlier day: a Sunday may have passed since (its "Mark as sung", the
    imported record's psalm for it, what's coming up), so it is built again before it is shown."""
    p = os.path.join(paths.SITE, 'data.js')
    return os.path.exists(p) and f'"builtOn":"{dt.date.today().isoformat()}"' not in paths.read(p)


def main():
    history.ensure()
    if not os.path.exists(os.path.join(paths.SITE, 'data.js')):
        print('building the browser first…')
        rebuild()
    import lectionary
    if len(lectionary.links()) < 100:               # first run: find the lectionary site's pages, in the background
        threading.Thread(target=lambda: run(['lectionary_links.py']), daemon=True).start()
    elif f'"linksSignature":"{lectionary.links_signature()}"' not in paths.read(os.path.join(paths.SITE, 'data.js')):
        print('updating the links to the lectionary…')        # the table changed since the page was built
        rebuild()
    if page_out_of_date():
        print('the code has changed since the page was built: building it again…')
        rebuild('after an update')
    elif built_before_today():
        print('a new day since the page was built: building it again…')
        rebuild('on a new day')
    import browser
    SERVING['code'] = browser.page_signature()       # what this launcher is running (see code_changed)
    srv = SERVING['srv'] = Server(('127.0.0.1', PORT), Handler)
    url = f'http://localhost:{PORT}{SITE_URL}'
    print(f'Precentor with the Service planner: {url}\n(Ctrl+C to stop)')
    if '--no-open' not in sys.argv:                  # (not when starting again after the first-run setup)
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped')
        return
    srv.server_close()
    if SERVING.get('restart'):                       # after the first-run setup, or a Sync that brought new tools
        sys.exit(RESTART)                            # supervise() starts a fresh one


RESTART = 3                                          # main()'s exit code for "start me again"


def install_packages():
    """What the launchers do before starting: the Python packages the tools and the plugins need (quick when
    nothing is missing). Run again before a restart, since an update may need a new one."""
    for r in [os.path.join(ROOT, 'requirements.txt')] + sorted(
            os.path.join(paths.PARISH, 'plugins', p, 'requirements.txt') for p in
            (os.listdir(os.path.join(paths.PARISH, 'plugins')) if paths.PARISH and
             os.path.isdir(os.path.join(paths.PARISH, 'plugins')) else [])):
        if os.path.exists(r) and subprocess.call([PY, '-m', 'pip', 'install', '-q', '--disable-pip-version-check',
                                                  '-r', r]) != 0:
            print(f'could not install the packages in {rel(r)} (see above)')


def supervise():
    """Run the launcher (main) in a process of its own, and start a fresh one each time it asks to be started again:
    one copy at a time, whatever the computer (Windows has no exec, and a copy started from inside the old one
    would keep the old one waiting, memory and all)."""
    args = [a for a in sys.argv[1:] if a != '--serve']
    while True:
        child = subprocess.Popen([PY, os.path.abspath(__file__), '--serve'] + args)
        if os.name != 'nt':                          # stopped from outside (kill): stop the one it runs too
            import signal
            signal.signal(signal.SIGTERM, lambda *a: (child.terminate(), sys.exit(0)))
        while True:
            try:
                code = child.wait()
                break
            except KeyboardInterrupt:                # Ctrl+C reaches both: let that one finish what it's saving
                continue
        if code != RESTART:
            return code
        print('starting again…')
        install_packages()
        if '--no-open' not in args:                  # the page is open already
            args.append('--no-open')


if __name__ == '__main__':
    sys.exit(main() if '--serve' in sys.argv else supervise())

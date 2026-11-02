"""A change history for what the launcher saves, so any change can be undone with one click.

Every save the chant browser makes (a Sunday, chant notes, a verse's pointing, an anthem's words, marking a
service as sung) is recorded at once as a git commit on this computer, with a one-line description. The
browser's Undo button reverts the latest one, and History lists the recent ones, each with its own Undo
(a revert: a new commit that puts things back, so nothing is ever lost). "Sync with GitHub" then only has
to bring in changes from GitHub and send these up.

What the tools make from those files (the parish's site/ and output/) is recorded too, as "generated"
commits that History leaves out; after an undo the browser is simply rebuilt.
"""
import os, re, subprocess, sys, threading, time

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths   # noqa: E402

GENERATED = 'Generated: '                  # commits of rebuilt pages and built PDFs, left out of History
MARK = 'Recorded by the chant browser.'   # in the body of each change History lists (and only those)
GENERATED_DIRS = ('site/', 'output/')      # rebuilt from the rest, so a clash in them doesn't matter
STALE = {}                                 # 'site': True when a sync took GitHub's copy of the generated pages
LOCK = threading.RLock()                   # one git command at a time (rebuilds run in the background)
WHO = ['-c', 'user.name=Psalter', '-c', 'user.email=psalter@localhost']   # if git doesn't know who you are


def git(d, *args):
    """Run git in folder d -> (exit code, output). Waits a moment and tries again while another program holds
    git's lock (an editor checking the folder, say), so a save isn't left unrecorded."""
    for attempt in range(6):
        try:
            with LOCK:
                r = subprocess.run(['git'] + (WHO if not known(d) else []) + list(args), cwd=d,
                                   capture_output=True, text=True)
        except OSError:                                    # no git on this computer
            return 1, 'git is not installed'
        out = (r.stdout or '') + (r.stderr or '')
        if r.returncode == 0 or 'index.lock' not in out:
            return r.returncode, out
        time.sleep(0.5)
    return r.returncode, out


def names(out):
    """File names from git's -z output (names may have spaces)."""
    return [f for f in out.split('\0') if f]


_KNOWN = {}


def known(d):
    if d not in _KNOWN:
        try:
            r = subprocess.run(['git', 'config', 'user.email'], cwd=d, capture_output=True, text=True)
            _KNOWN[d] = bool(r.stdout.strip())
        except OSError:
            _KNOWN[d] = True
    return _KNOWN[d]


def ensure():
    """Start a history in the parish folder if it isn't a git repository yet (a local one: nothing is sent)."""
    if not paths.PARISH or is_repo(paths.PARISH):
        return
    if git(paths.PARISH, 'init', '-q')[0] == 0:
        git(paths.PARISH, 'add', '-A')
        git(paths.PARISH, 'commit', '-q', '-m', GENERATED + 'the history starts here')


def is_repo(d):
    return bool(d) and os.path.exists(os.path.join(d, '.git'))      # a folder, or a file (a worktree, a submodule)


def repo_of(path):
    path = os.path.abspath(path)
    if paths.PARISH and path.startswith(os.path.abspath(paths.PARISH) + os.sep):
        return paths.PARISH if is_repo(paths.PARISH) else None
    return paths.CORE if is_repo(paths.CORE) else None


def record(files, message):
    """Commit just these files (they may be new, or deleted) with this description. Quietly does nothing
    outside git, or for a file git is told to ignore."""
    by = {}
    for f in files:
        d = repo_of(f)
        if d:
            by.setdefault(d, []).append(os.path.relpath(f, d))
    with LOCK:
        for d, rel in by.items():
            git(d, 'add', '-A', '--', *rel)
            if git(d, 'diff', '--cached', '--quiet', '--', *rel)[0] != 0:          # something to record
                git(d, 'commit', '-q', '-m', message, '-m', MARK, '--', *rel)


def record_generated(what):
    """After a rebuild or a build: commit the parish's generated folders, out of the History list."""
    if not is_repo(paths.PARISH):
        return
    folders = [f for f in ('site', 'output') if os.path.isdir(os.path.join(paths.PARISH, f))]
    if not folders:
        return
    with LOCK:
        git(paths.PARISH, 'add', '-A', '--', *folders)
        if git(paths.PARISH, 'diff', '--cached', '--quiet', '--', *folders)[0] != 0:
            git(paths.PARISH, 'commit', '-q', '-m', GENERATED + what, '--', *folders)


def repos():
    out = []
    for d, name in ((paths.PARISH, 'parish'), (paths.CORE, 'precentor')):
        if is_repo(d):
            out.append((d, name))
    return out


def changes(limit=25):
    """The recent changes, newest first: [{repo, sha, time, message, pushed}]."""
    out = []
    for d, name in repos():
        code, unpushed = git(d, 'rev-list', '@{u}..HEAD')
        ahead = set(unpushed.split()) if code == 0 else set()
        code, log = git(d, 'log', f'-{limit}', '--no-merges', '--fixed-strings', '--grep', MARK,
                        '--format=%H%x09%ct%x09%s')
        for line in log.splitlines() if code == 0 else []:
            sha, t, msg = line.split('\t', 2)
            out.append({'repo': name, 'sha': sha, 'time': int(t), 'message': msg,
                        'pushed': bool(upstream(d)) and sha not in ahead})
    out.sort(key=lambda c: -c['time'])
    return out[:limit]


def upstream(d):
    return git(d, 'rev-parse', '--abbrev-ref', '@{u}')[0] == 0


def undo(repo, sha):
    """Put back what that change changed, as a new change. Returns (ok, message)."""
    d = dict((n, dd) for dd, n in repos()).get(repo)
    if not d:
        return False, 'no such repository'
    if not re.fullmatch(r'[0-9a-f]{7,40}', str(sha)):          # a change's id, and nothing else, reaches git
        return False, 'no such change'
    code, body = git(d, 'log', '-1', '--format=%B', sha, '--')
    if code != 0 or MARK not in body:
        return False, 'only changes made in the chant browser can be undone here'
    msg = body.strip().splitlines()[0]
    files = names(git(d, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', '--root', sha)[1])
    with LOCK:
        code, out = git(d, 'revert', '--no-commit', sha)
        if code == 0 and git(d, 'diff', '--cached', '--quiet', '--', *files)[0] == 0:
            git(d, 'revert', '--abort')
            return False, 'that change has been undone already'
        if code == 0:
            base = msg.split(': ', 1)[1] if msg.startswith(('Undid: ', 'Redid: ')) else msg
            new = ('Redid: ' if msg.startswith('Undid: ') else 'Undid: ') + base       # an undo can be undone
            code, out = git(d, 'commit', '-q', '-m', new, '-m', MARK, '--', *files)   # only what it touched
        if code != 0:
            git(d, 'revert', '--abort')
            if 'would be overwritten' in out or 'local changes' in out:
                return False, ('that file has changes not yet recorded (made outside the browser?): '
                               'save them to GitHub first, then undo')
            return False, ('a later change touched the same lines, so this one cannot be undone by itself: '
                           'undo the later one first')
    return True, msg.strip()


def pending():
    """Files changed but not recorded, and recorded changes not yet on GitHub, per repository."""
    out = []
    for d, name in repos():
        code, st = git(d, 'status', '--porcelain', '-z')
        files = [e[3:] for e in names(st) if len(e) > 3 and e[2] == ' '] if code == 0 else []
        code, ahead = git(d, 'rev-list', '--count', '@{u}..HEAD')
        out.append({'repo': name, 'files': files, 'unpushed': int(ahead.strip() or 0) if code == 0 else 0,
                    'online': upstream(d)})
    return out


PROGRESS = {'done': 0, 'total': 0, 'step': ''}      # how far a sync has got, for the page's progress bar
SYNC_STEPS = 4                                        # for each folder: save, fetch, merge, send


def step(what):
    PROGRESS.update(done=min(PROGRESS['done'] + 1, PROGRESS['total'] or 1), step=what)


def sync(message):
    """Sync with GitHub: record anything changed by hand, bring in GitHub's changes, send ours. -> (ok, log)"""
    log = []
    with LOCK:
        return _sync(message, log)


def _sync(message, log):
    for d, name in repos():
        step(f'{name}: saving what changed here')
        code, st = git(d, 'status', '--porcelain')
        if st.strip():
            git(d, 'add', '-A')
            git(d, 'commit', '-q', '-m', message)
        if not upstream(d):                                          # a history kept only on this computer
            log.append(f'{name}: kept on this computer only (no GitHub copy is set up for this folder)')
            PROGRESS['done'] += SYNC_STEPS - 1
            continue
        step(f'{name}: asking GitHub what is new')
        code, out = git(d, 'fetch', '-q')
        if code != 0:
            return False, f'{name}: could not reach GitHub:\n{out.strip()}'
        code, before = git(d, 'rev-list', '--count', 'HEAD..@{u}')
        step(f'{name}: bringing in the changes')
        code, out = git(d, 'merge', '--no-edit', '-q', '@{u}')
        if code != 0:
            clash = names(git(d, 'diff', '--name-only', '-z', '--diff-filter=U')[1])
            if clash and all(f.startswith(GENERATED_DIRS) for f in clash):
                git(d, 'checkout', '--theirs', '--', *clash)       # they'll be rebuilt from the merged files
                git(d, 'add', '--', *clash)
                code, out = git(d, 'commit', '-q', '--no-edit')
                STALE['site'] = True
            if code != 0:
                git(d, 'merge', '--abort')
                which = ', '.join(clash[:5]) if clash else ''
                return False, (f'{name}: could not bring in the changes from GitHub'
                               + (f' (the same lines were changed here and there: {which})' if which else '')
                               + f':\n{out.strip()}')
        came = int(before.strip() or 0) if before.strip().isdigit() else 0
        if came:
            log.append(f"{name}: brought in {came} change{'s' if came != 1 else ''} from GitHub")
            STALE['site'] = True                       # build the pages again with what came in
            if d == paths.CORE:
                log.append('(the tools were updated: stop the launcher and start it again to use them)')
        code, ahead = git(d, 'rev-list', '--count', '@{u}..HEAD')
        n = int(ahead.strip() or 0) if code == 0 else 0
        step(f'{name}: sending yours to GitHub')
        if n:
            code, out = git(d, 'push', '-q')
            if code != 0 and d == paths.CORE and paths.PARISH:      # the tools are someone else's: bringing in is enough
                log.append(f'{name}: {n} change(s) of your own to the tools, kept here (GitHub would not take them)')
                continue
            if code != 0:
                return False, f'{name}: could not send to GitHub:\n{out.strip()}'
            log.append(f"{name}: {n} change{'s' if n != 1 else ''} saved to GitHub")
    return True, '\n'.join(log) or 'Already in sync with GitHub.'


def describe_notes(before, after):
    """'Chant notes: Goss-1 pin, Turle rating' from the rows before and after a save."""
    old = {r.get('Chant'): r for r in before}
    bits = []
    for r in after:
        o = old.pop(r.get('Chant'), {})
        what = [k.lower() for k in ('Rating', 'Mood', 'Notes', 'Pin') if (o.get(k) or '') != (r.get(k) or '')]
        if what:
            bits.append(f"{r.get('Chant')} {', '.join(what)}")
    bits += [f'{c} removed' for c in old]
    if not bits:
        return 'Chant notes'
    return 'Chant notes: ' + '; '.join(bits[:3]) + (f' and {len(bits) - 3} more' if len(bits) > 3 else '')

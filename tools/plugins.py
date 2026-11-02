"""Plugins: things one parish adds to the planner without changing the tools.

A plugin is a folder in parish/plugins/ (say parish/plugins/newsletter/) with up to three files:

    plugin.txt    what it adds to the plain-text files, so they still read without it:
                      sunday keys:     flowers, flowers by    # extra lines a Sunday file may have
                      order settings:  newsletter heading     # extra lines under an order of service
    plugin.py     Python, run by the launcher:
                      ROUTES = {'/api/newsletter': handler}   # handler(data, ctx) -> dict, answered as JSON
                      def data(): return {...}                # handed to the page as SV.plugins['newsletter']
    plugin.js     JavaScript added to the chant browser page. It can add to the Service planner through
                  PLUGINS.cards (functions returning a card's HTML, shown under the rest of the service),
                  PLUGINS.rows (more rows at the end of the rest of the service), PLUGINS.changed (called
                  when the service changes) and PLUGINS.reset (called when another day is opened). A plugin's
                  Sunday keys are kept in B.extra[key] (a string; several lines joined by newlines).

The order settings are read into service.META[order][setting]. The folder is put on sys.path, so a
plugin can keep more modules beside plugin.py. ctx gives handlers safe_name(name), root (the precentor folder),
record(files, message) (to record a change for Undo) and rebuild() (to rebuild the page).
"""
import importlib.util, os, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths   # noqa: E402


def folders():
    d = os.path.join(paths.PARISH, 'plugins') if paths.PARISH else None
    if not d or not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in sorted(os.listdir(d))
            if os.path.isdir(os.path.join(d, f)) and not f.startswith(('.', '_'))]


def _manifest(folder):
    out = {}
    p = os.path.join(folder, 'plugin.txt')
    if os.path.exists(p):
        for line in paths.read(p).splitlines():
            k, sep, v = line.split('#', 1)[0].partition(':')
            if sep:
                out[k.strip().lower()] = [x.strip().lower() for x in v.split(',') if x.strip()]
    return out


def sunday_keys():
    return {k for f in folders() for k in _manifest(f).get('sunday keys', [])}


def order_settings():
    return {k for f in folders() for k in _manifest(f).get('order settings', [])}


_modules = None
ERRORS = {}                  # plugins that failed to load: {name: what went wrong}


def modules():
    """{name: module} of the plugins that have a plugin.py. One that fails to load is left out (and noted in
    ERRORS); the others still load."""
    global _modules
    if _modules is None:
        _modules = {}
        for f in folders():
            p = os.path.join(f, 'plugin.py')
            if not os.path.exists(p):
                continue
            if f not in sys.path:
                sys.path.insert(0, f)
            name = os.path.basename(f)
            try:
                spec = importlib.util.spec_from_file_location(f'precentor_plugin_{name}', p)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            except Exception as e:
                ERRORS[name] = f'{type(e).__name__}: {e}'
                sys.stderr.write(f'  plugin {name} did not load: {ERRORS[name]}\n')
                continue
            _modules[name] = mod
    return _modules


def routes():
    return {path: fn for m in modules().values() for path, fn in getattr(m, 'ROUTES', {}).items()}


def data():
    out = {}
    for name, m in modules().items():
        if hasattr(m, 'data'):
            try:
                out[name] = m.data()
            except Exception as e:                       # a broken plugin shouldn't stop the page
                out[name] = {'error': str(e)}
    out.update({name: {'error': err} for name, err in ERRORS.items()})
    return out


def scripts():
    """The plugins' JavaScript, to add to the page."""
    out = []
    for f in folders():
        p = os.path.join(f, 'plugin.js')
        if os.path.exists(p):
            out.append(f'// plugin: {os.path.basename(f)}\n' + paths.read(p))
    return '\n'.join(out)

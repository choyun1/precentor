"""Small secrets (a plugin's password or web address) kept on this computer, never in a repository.

In the computer's own password store (Windows Credential Manager, the macOS Keychain) when the `keyring`
package is installed, otherwise in ~/.precentor/<name>.json, readable only by you.

A secret kept under the old name (psalter-..., ~/.psalter/, from before the project was called Precentor) is
moved to the new one the first time it is asked for.
"""
import json, os

DIR = os.path.join(os.path.expanduser('~'), '.precentor')
OLD_DIR = os.path.join(os.path.expanduser('~'), '.psalter')


def _keyring():
    try:
        import keyring
        keyring.get_keyring()
        return keyring
    except Exception:
        return None


def _file(service, folder=None):
    return os.path.join(folder or DIR, service.replace('precentor-', '').replace('psalter-', '') + '.json')


def get(service, key):
    v = _get(service, key)
    if v is None and service.startswith('precentor-'):          # kept under the old name: move it over
        old = 'psalter-' + service[len('precentor-'):]
        v = _get(old, key, OLD_DIR)
        if v is not None:
            put(service, key, v)
            _forget(old, key, OLD_DIR)                          # or a later forget() would bring it back
    return v


def _get(service, key, folder=None):
    kr = _keyring()
    if kr:
        try:
            v = kr.get_password(service, key)
            if v:
                return v
        except Exception:
            pass
    f = _file(service, folder)
    if os.path.exists(f):
        try:
            with open(f) as fh:
                return json.load(fh).get(key)
        except ValueError:
            return None
    return None


def put(service, key, value):
    """Keep a value; returns where it went."""
    kr = _keyring()
    if kr:
        try:
            kr.set_password(service, key, value)
            return "your computer's password store"
        except Exception:
            pass
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    f, data = _file(service), {}
    if os.path.exists(f):
        try:
            with open(f) as fh:
                data = json.load(fh)
        except ValueError:
            pass
    data[key] = value
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as fh:
        json.dump(data, fh)
    os.chmod(f, 0o600)                       # only you may read it, even if the file was there before
    return f


def forget(service, key):
    """Remove a value, and any copy under the old name (else get() would move it back)."""
    _forget(service, key)
    if service.startswith('precentor-'):
        _forget('psalter-' + service[len('precentor-'):], key, OLD_DIR)


def _forget(service, key, folder=None):
    kr = _keyring()
    if kr:
        try:
            kr.delete_password(service, key)
        except Exception:
            pass
    f = _file(service, folder)
    if os.path.exists(f):
        try:
            with open(f) as fh:
                data = json.load(fh)
        except ValueError:
            data = {}
        data.pop(key, None)
        with open(f, 'w') as fh:
            json.dump(data, fh)

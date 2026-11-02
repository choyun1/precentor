"""Make your parish folder (parish/) the first time: from the template, parish.example/, with your settings.

    python tools/setup.py          # asks a few questions
    (or: open the launcher; with no parish folder yet, the chant browser asks the same questions)

It writes parish/parish.txt (name, lectionary track, patronal feast, bracketed verses) and makes the folder
a git repository of its own, so the chant browser can undo changes and you can keep it on GitHub (privately)
with "Sync". Everything else in parish.txt (colors, Christmas psalms, plugins) can be changed later by hand.
"""
import os, re, shutil, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import paths   # noqa: E402

TEMPLATE = os.path.join(paths.CORE, 'parish.example')
TARGET = os.path.join(paths.CORE, 'parish')

# feasts a church may be named for, with a fixed date and their own psalm in the lectionary (reference/rcl_psalms.csv)
FEASTS = [
    ('01-01', 'holy_name', 'The Holy Name'), ('01-06', 'epiphany', 'The Epiphany'),
    ('01-18', 'confession_of_st_peter', 'The Confession of Saint Peter'),
    ('01-25', 'conversion_of_st_paul', 'The Conversion of Saint Paul'), ('02-02', 'presentation', 'The Presentation'),
    ('02-24', 'st_matthias', 'Saint Matthias'), ('03-19', 'st_joseph', 'Saint Joseph'),
    ('03-25', 'annunciation', 'The Annunciation'), ('04-25', 'st_mark', 'Saint Mark'),
    ('05-01', 'st_philip_and_st_james', 'Saint Philip and Saint James'), ('05-31', 'visitation', 'The Visitation'),
    ('06-11', 'st_barnabas', 'Saint Barnabas'), ('06-24', 'nativity_of_st_john_baptist', 'The Nativity of Saint John the Baptist'),
    ('06-29', 'st_peter_and_st_paul', 'Saint Peter and Saint Paul'), ('07-22', 'st_mary_magdalene', 'Saint Mary Magdalene'),
    ('07-25', 'st_james', 'Saint James'), ('08-06', 'transfiguration', 'The Transfiguration'),
    ('08-15', 'st_mary_the_virgin', 'Saint Mary the Virgin'), ('08-24', 'st_bartholomew', 'Saint Bartholomew'),
    ('09-14', 'holy_cross', 'Holy Cross Day'), ('09-21', 'st_matthew', 'Saint Matthew'),
    ('09-29', 'st_michael_and_all_angels', 'Saint Michael and All Angels'), ('10-18', 'st_luke', 'Saint Luke'),
    ('10-23', 'st_james_of_jerusalem', 'Saint James of Jerusalem'), ('10-28', 'st_simon_and_st_jude', 'Saint Simon and Saint Jude'),
    ('11-01', 'all_saints', "All Saints' Day"), ('11-30', 'st_andrew', 'Saint Andrew'), ('12-21', 'st_thomas', 'Saint Thomas'),
    ('12-26', 'st_stephen', 'Saint Stephen'), ('12-27', 'st_john', 'Saint John'), ('12-28', 'holy_innocents', 'The Holy Innocents'),
]


def settings_text(template, name, track='2', patronal='', optional_verses='sing'):
    """The template's parish.txt with these settings in place (its comments kept)."""
    name = re.sub(r'[\r\n#]+', ' ', name).strip()
    if not name:
        raise ValueError("the parish's name, please")
    if str(track) not in ('1', '2'):
        raise ValueError('track: 1 or 2')
    if optional_verses not in ('sing', 'leave out'):
        raise ValueError('optional verses: "sing" or "leave out"')
    feast = next((f for f in FEASTS if f[1] == patronal), None)
    if patronal and not feast:
        raise ValueError(f'no feast {patronal!r} with its own psalm; leave the patronal feast empty, or add it to parish.txt by hand')
    out = re.sub(r'(?m)^name:.*$', lambda m: f'name:          {name}', template)
    out = re.sub(r'(?m)^track:.*$', lambda m: f'track:         {track}', out)
    out = re.sub(r'(?m)^optional_verses:.*$', lambda m: f'optional_verses: {optional_verses}', out)
    if feast:
        out = re.sub(r'(?m)^# ?patronal:.*$', lambda m: f'patronal:      {feast[0]} {feast[1]} {feast[2]}', out)
    return out


def make_parish(name, track='2', patronal='', optional_verses='sing', target=TARGET):
    """Copy the template to parish/ with these settings; make it a git repository. -> what was done, in words."""
    if os.path.exists(target):
        raise ValueError('there is a parish folder already')
    text = settings_text(paths.read(os.path.join(TEMPLATE, 'parish.txt')), name, track, patronal, optional_verses)
    shutil.copytree(TEMPLATE, target, ignore=shutil.ignore_patterns('__pycache__', '.git'))
    sundays = os.path.join(target, 'sundays')    # (not in a fresh download of the template: git ignores sundays/)
    os.makedirs(sundays, exist_ok=True)
    for f in os.listdir(sundays):                 # an example Sunday in the template isn't yours
        if f.endswith('.txt'):
            os.remove(os.path.join(sundays, f))
    with open(os.path.join(target, 'parish.txt'), 'w', encoding='utf-8') as fh:
        fh.write(text)
    drawn = os.path.join(paths.CORE, 'site', 'notation')         # chants drawn already (without a parish folder)
    if os.path.isdir(drawn):
        shutil.copytree(drawn, os.path.join(target, 'site', 'notation'))    # (keeping their times: not redrawn)
    done = [f'Made {os.path.relpath(target, paths.CORE)}/ for {name}.']
    import subprocess
    try:
        import history
        subprocess.run(['git', 'init', '-q', '-b', 'main'], cwd=target, check=True, capture_output=True)
        history.git(target, 'add', '-A')
        code, out = history.git(target, 'commit', '-q', '-m', 'A new parish folder, from parish.example')
        done.append('It keeps a record of every change (git), for Undo.' if code == 0 else 'Could not record it in git: ' + out)
    except (OSError, subprocess.CalledProcessError):
        done.append("Git isn't installed, so there's no Undo or Sync until it is (git-scm.com); everything else works.")
    return done


def ask(question, default='', choices=None):
    while True:
        a = input(f'{question}{f" [{default}]" if default else ""}: ').strip() or default
        if not choices or a in choices:
            return a
        print('  one of: ' + ', '.join(choices))


def main():
    if os.path.exists(TARGET):
        sys.exit(f'There is a parish folder already ({TARGET}); edit its parish.txt to change the settings.')
    print('Your parish folder: a few questions (Enter keeps the suggestion).\n')
    name = ask("The parish's name (as on a service leaflet)")
    track = ask('Season after Pentecost: which lectionary track do you use, 1 or 2?', '2', ['1', '2'])
    print('Patronal feast: the number from this list, or Enter for none.')
    for i, (md, _, title) in enumerate(FEASTS, 1):
        print(f'  {i:>2}  {title} ({md})')
    n = ask('Patronal feast', '', [''] + [str(i) for i in range(1, len(FEASTS) + 1)])
    verses = ask('Verses the lectionary puts in brackets: sing, or leave out?', 'sing', ['sing', 'leave out'])
    for line in make_parish(name, track, FEASTS[int(n) - 1][1] if n else '', verses):
        print(line)
    print('Open the launcher (precentor.sh, or Precentor.bat on Windows) to start planning.')


if __name__ == '__main__':
    main()

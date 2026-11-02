"""Checks of the tools' logic, quick to run and needing no LilyPond:

    python -m unittest discover tests

Each test names the behavior it guards; most came from bugs found once, so they stay fixed.
"""
import datetime as dt, os, re, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build, chantedit, emit, history, lectionary, paths, service   # noqa: E402

D = dt.date.fromisoformat


class Calendar(unittest.TestCase):
    def test_days(self):
        for date, key in [('2026-11-29', 'advent1'), ('2026-12-24', 'christmas_eve'), ('2023-12-24', 'advent4'),
                          ('2027-02-10', 'ash_wednesday'), ('2027-03-27', 'easter_vigil'), ('2027-05-16', 'pentecost'),
                          ('2026-11-22', 'proper29'), ('2026-11-01', 'all_saints'), ('2028-08-06', 'transfiguration')]:
            self.assertEqual(lectionary.day_of(D(date))[0], key, date)

    def test_years(self):
        self.assertEqual(lectionary.lect_year(D('2026-11-29')), 'B')
        self.assertEqual(lectionary.lect_year(D('2026-11-22')), 'A')
        self.assertEqual(lectionary.office_year(D('2026-11-29')), 'I')

    def test_colors(self):
        self.assertEqual(lectionary.color(D('2023-12-24')), lectionary.SEASON_COLORS['advent'])  # Advent 4, a Sunday
        self.assertEqual(lectionary.color(D('2026-12-24')), 'white')                               # Christmas Eve
        self.assertEqual(lectionary.color(D('2026-11-01')), 'white')                               # All Saints
        self.assertEqual(lectionary.color(D('2027-03-26')), 'black')                               # Good Friday
        self.assertEqual(lectionary.color(D('2027-06-27')), 'green')

    def test_christmas_eve_kept_on_advent_4(self):
        a = lectionary.appointed(D('2028-12-24'), key='christmas_eve')
        self.assertEqual(a['label'], 'Christmas Eve')
        self.assertTrue(a['psalm'])

    def test_parish_txt_keeps_colors(self):
        strip = lambda line: re.sub(r'#(?!(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b).*', '', line).strip()
        self.assertEqual(strip('color_shades: white = #fff, gold = #fff2cc  # a note'),
                         'color_shades: white = #fff, gold = #fff2cc')


class Psalms(unittest.TestCase):
    def test_two_psalms_as_one(self):
        self.assertEqual([os.path.basename(p) for p, _ in build.resolve('42 and 43')], ['Psalm_042.txt', 'Psalm_043.txt'])

    def test_optional_verses(self):
        self.assertEqual(build.parse_verses('1-8,(9-11),12', optional=False), [1, 2, 3, 4, 5, 6, 7, 8, 12])
        self.assertEqual(build.parse_verses('1-3,21c'), [1, 2, 3, 21])

    def test_roman_part(self):
        self.assertTrue(build.resolve('89 Part I')[0][0].endswith('Psalm_089_Part_1.txt'))

    def plan(self, text):
        f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False)
        f.write(text)
        f.close()
        try:
            return build.plan(build.parse_sunday(f.name))
        finally:
            os.unlink(f.name)

    def test_a_late_first_chant_is_refused(self):
        with self.assertRaises(SystemExit):
            self.plan('psalm: 23\nchant: Turle-2 from 3\n')

    def test_the_chant_before_carries_on(self):
        ps = self.plan('psalm: 23\nchant: Turle-2\npsalm: 24\nchant: Goss-1 from 5\n')
        self.assertEqual([(s['chant'], s['verses'][0]['n']) for s in ps[1]['sections']], [('Turle-2', 1), ('Goss-1', 5)])

    def test_this_sundays_pointing(self):
        ps = self.plan('psalm: 23\nchant: Turle-2\nverse:   1  The | LORD is my | shepherd; *\n'
                       '              I shall | not be | in | want.\n')
        v1 = ps[0]['sections'][0]['verses'][0]
        self.assertEqual(v1['lines'][0]['text'], 'The | LORD is my | shepherd; *')
        self.assertEqual(v1['lines'][1]['half'], 2)
        import check_texts
        self.assertEqual(check_texts.verse_problems('Psalm_023.txt', v1), [])
        wrong = dict(v1, lines=[dict(v1['lines'][0], text='The | LORD is my | shepherd;'), v1['lines'][1]])
        self.assertTrue(check_texts.verse_problems('Psalm_023.txt', wrong))      # no *

    def test_this_services_music(self):
        """music: lines change a chant's voices for one service (an empty one silent), never the chant's file."""
        f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False)
        f.write('psalm: 23\nchant: Turle-2 down 2\nmusic:   A_notes silent\n'
                'music:   S_notes g\' a2 | d,4 e | f2 \\bar "||" g2 | a4 a | a d | d cis | \\bar "||" '
                'd2 | c4 bes | a2 \\bar "||" a2 | a4 g | f e | d2 | \\bar "||"\n')
        f.close()
        try:
            s = build.parse_sunday(f.name)
        finally:
            os.unlink(f.name)
        music = s['chant_music']['Turle-2']
        self.assertIsNone(music['A_notes'])
        self.assertEqual(music['S_notes'][0], "g'")
        before = paths.read(paths.chant_file('Turle-2'))
        c = build.load_music('Turle-2 down 2', music)
        self.assertIn('\\transpose d c', c['score'])
        self.assertEqual(paths.read(paths.chant_file('Turle-2')), before)           # the chant itself untouched
        text = chantedit.service_text(before, music)
        alto = re.search(r'A_notes = .*?\n}', text, re.S).group(0)
        self.assertNotRegex(alto.split('{', 1)[1], r'(?<![\\\w])[a-g]')               # silent: spacers only
        self.assertEqual(chantedit.check(text)[0], [])
        report = '\n'.join(build.checks(s, build.plan(s), {'Turle-2 down 2': c}))
        self.assertIn('Turle-2: music changed for this service (alto silent, soprano)', report)
        with self.assertRaises(SystemExit):                                         # a music: line needs a chant
            self.plan('psalm: 23\nmusic: A_notes silent\n')

    def test_a_bar_too_long(self):
        text = paths.read(paths.chant_file('Turle-2'))
        p = chantedit.parts(text)
        p['voices'][0]['body'] = p['voices'][0]['body'].replace('a2', 'a1', 1)
        self.assertIn('Soprano: bar 1 is too long for 2/4', chantedit.check(chantedit.apply(text, p))[0])
        self.assertEqual(chantedit.spacers('a2 | <d fis>4 e~ | d?2 \\bar "||" r4 bes, |'), 's2 | s4 s | s2 \\bar "||" s4 s |')

    def test_changes_out_of_order_are_refused(self):
        with self.assertRaises(SystemExit):
            self.plan('psalm: 23\nchant: Turle-2\nchant: Goss-1 from 4\nchant: Smart-1 from 2\n')


class Chants(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(paths.canonical('Turle-5'), 'Turle-2 down 2')
        self.assertEqual(paths.canonical('Turle-5 up 2'), 'Turle-2')
        self.assertEqual(paths.split_chant('Goss-6'), ('Goss-3', 4))

    def test_transposed_key(self):
        c = build.load_music('Turle-2 down 2')
        self.assertEqual(c['key'][2], 'C')
        self.assertIn('\\transpose d c', c['score'])
        self.assertEqual(build.load_music('Attwood-1 up 1')['key'][2], 'A')

    def test_held_yahweh(self):
        self.assertIn('\\scs "A"', emit.word_markup('=YAHWEH'))
        self.assertIn('\\scs "S"', emit.word_markup("=GOD'S"))

    def test_junior_labels(self):
        import browser
        cs = [dict(id=i, composer=c, key='Ab', mode='Major') for i, c in (
            ('WoodwardG-1', 'Woodward, George'), ('WoodwardJr-1', 'Woodward, Jr., Richard'),
            ('Camidge-1', 'Camidge, Matthew'), ('CamidgeJr-1', 'Camidge, John Jr.'),
            ('CooperJr-1', 'Cooper, George (junior)'))]
        browser.label_chants(cs)
        self.assertEqual([c['label'] for c in cs], ['G. Woodward in A♭', 'R. Woodward Jr. in A♭',
                                                    'M. Camidge in A♭', 'J. Camidge Jr. in A♭', 'Cooper in A♭'])


class ChantEditing(unittest.TestCase):
    def test_parts_round_trip(self):
        text = paths.read(paths.chant_file('Turle-2'))
        p = chantedit.parts(text)
        self.assertEqual([v['var'] for v in p['voices']], ['S_notes', 'A_notes', 'T_notes', 'B_notes'])
        self.assertEqual(chantedit.parts(chantedit.apply(text, p)), p)

    def test_an_edit_lands(self):
        text = paths.read(paths.chant_file('Turle-2'))
        p = chantedit.parts(text)
        p['key'] = {'tonic': 'c', 'mode': 'minor'}
        p['voices'][0]['body'] = 'c2 | ' + p['voices'][0]['body']      # a bar too many in the soprano's first phrase
        out = chantedit.apply(text, p)
        self.assertIn('\\key c \\minor', out)
        self.assertTrue(chantedit.check(out)[0])            # said so

    def test_the_template_is_a_good_double_chant(self):
        problems, facts = chantedit.check(chantedit.template('A. N. Other (1900-1990)'))
        self.assertEqual(problems, [])
        self.assertTrue(facts['double'])

    def test_bad_input(self):
        text = chantedit.template()
        with self.assertRaises(ValueError):
            chantedit.apply(text, {'key': {'tonic': 'h', 'mode': 'major'}})
        with self.assertRaises(ValueError):
            chantedit.apply(text, {'voices': [{'var': 'S_notes', 'start': "c''", 'body': 'c2 { d'}]})


def musicxml(voices, closed=False, double_bars=True, fifths=1, chords=False):
    """A small partwise MusicXML score from {voice: [bars: [(step, alter, octave, quarters)]]}, as an editor exports it:
    four parts, or (closed) two staves with two voices each, or (chords) two staves of two-note chords."""
    closed = closed or chords
    def note(step, alter, octave, q, staff, voice, chord=False):
        return (f"<note>{'<chord/>' if chord else ''}<pitch><step>{step}</step>{f'<alter>{alter}</alter>' if alter else ''}"
                f"<octave>{octave}</octave></pitch><duration>{int(q * 2)}</duration><voice>{voice}</voice>"
                f"{f'<staff>{staff}</staff>' if closed else ''}</note>")
    names = list(voices)
    layout = [[(names[0], 1, 1), (names[1], 1, 2)], [(names[2], 2, 3), (names[3], 2, 4)]] if closed else \
             [[(n, 1, 1)] for n in names]
    n_bars = len(voices[names[0]])
    parts, plist = [], []
    for pi, group in enumerate(layout):
        pid = f'P{pi + 1}'
        plist.append(f'<score-part id="{pid}"><part-name>{group[0][0]}</part-name></score-part>')
        measures = []
        for b in range(n_bars):
            body = ''
            if b == 0:
                body += (f'<attributes><divisions>2</divisions><key><fifths>{fifths}</fifths><mode>major</mode></key>'
                         f'<time><beats>2</beats><beat-type>4</beat-type></time>{"<staves>2</staves>" if closed else ""}</attributes>')
            if chords:                             # the two voices of a staff on one stem: <note/><note><chord/>…
                (hi, staff, _), (lo, _, _) = group
                body += ''.join(note(*u, staff, 1) + note(*l, staff, 1, chord=True)
                                for u, l in zip(voices[hi][b], voices[lo][b]))
            else:
                for gi, (name, staff, voice) in enumerate(group):
                    if gi:
                        body += '<backup><duration>4</duration></backup>'
                    body += ''.join(note(*n, staff, voice) for n in voices[name][b])
            if double_bars and b in (2, n_bars - 1):
                body += '<barline location="right"><bar-style>light-light</bar-style></barline>'
            measures.append(f'<measure number="{b + 1}">{body}</measure>')
        parts.append(f'<part id="{pid}">' + ''.join(measures) + '</part>')
    return ('<?xml version="1.0"?><score-partwise version="3.1"><identification>'
            '<creator type="composer">A. N. Other (1850-1920)</creator></identification>'
            f'<part-list>{"".join(plist)}</part-list>{"".join(parts)}</score-partwise>').encode()


H, Q = 2, 1      # a half note and a quarter, in quarters
SATB = {         # a single chant in G: 3 bars + 4 bars
    'Soprano': [[('B', 0, 4, H)], [('C', 0, 5, Q), ('B', 0, 4, Q)], [('A', 0, 4, H)],
                [('D', 0, 5, H)], [('C', 0, 5, Q), ('B', 0, 4, Q)], [('A', 0, 4, Q), ('F', 1, 4, Q)], [('G', 0, 4, H)]],
    'Alto': [[('G', 0, 4, H)], [('G', 0, 4, Q), ('G', 0, 4, Q)], [('F', 1, 4, H)],
             [('G', 0, 4, H)], [('E', 0, 4, Q), ('D', 0, 4, Q)], [('E', 0, 4, Q), ('D', 0, 4, Q)], [('D', 0, 4, H)]],
    'Tenor': [[('D', 0, 4, H)], [('E', 0, 4, Q), ('D', 0, 4, Q)], [('D', 0, 4, H)],
              [('B', 0, 3, H)], [('C', 0, 4, Q), ('G', 0, 3, Q)], [('C', 0, 4, Q), ('A', 0, 3, Q)], [('B', 0, 3, H)]],
    'Bass': [[('G', 0, 3, H)], [('C', 0, 3, Q), ('G', 0, 2, Q)], [('D', 0, 3, H)],
             [('G', 0, 2, H)], [('A', 0, 2, Q), ('B', 0, 2, Q)], [('C', 0, 3, Q), ('D', 0, 3, Q)], [('G', 0, 2, H)]],
}


class MusicXML(unittest.TestCase):
    def check_import(self, data):
        import musicxml
        parts, info = musicxml.to_parts(data, 'x.musicxml')
        self.assertEqual(info['composer'], 'A. N. Other (1850-1920)')
        self.assertEqual(parts['key'], {'tonic': 'g', 'mode': 'major'})
        self.assertEqual(parts['time'], '2/4')
        text = chantedit.apply(chantedit.template(info['composer']), parts)
        problems, facts = chantedit.check(text)
        self.assertEqual(problems, [])
        self.assertFalse(facts['double'])
        return parts

    def test_four_parts(self):
        parts = self.check_import(musicxml(SATB))
        sop = parts['voices'][0]
        self.assertEqual(sop['body'].split('\n')[0], 'b2 | c4 b | a2 \\bar "||"')
        self.assertIn('fis', sop['body'])

    def test_closed_score(self):
        self.assertEqual(self.check_import(musicxml(SATB, closed=True)), self.check_import(musicxml(SATB)))

    def test_chords_on_one_stem(self):
        self.assertEqual(self.check_import(musicxml(SATB, chords=True)), self.check_import(musicxml(SATB)))

    def test_phrases_without_double_bars(self):
        self.assertEqual(self.check_import(musicxml(SATB, double_bars=False)), self.check_import(musicxml(SATB)))

    def test_compressed_mxl(self):
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>')
            z.writestr('score.xml', musicxml(SATB))
        self.check_import(buf.getvalue())

    def test_too_few_voices(self):
        import musicxml as mx
        with self.assertRaises(ValueError):
            mx.to_parts(b'<score-partwise><part-list/></score-partwise>')
        with self.assertRaises(ValueError):
            mx.to_parts(b'<score-timewise/>')


def N(name, q, voice=1, staff=None, chord=False, tie=False, extra='', rest=False, hidden=False):
    """One MusicXML <note> ("fis4" names: step, alteration, octave as F#4): q in quarters, 2 divisions each."""
    if rest:
        pitch = '<rest/>'
    else:
        m = re.fullmatch(r'([A-G])(#|b)?(\d)', name)
        alter = {'#': 1, 'b': -1}.get(m.group(2), 0)
        pitch = f"<pitch><step>{m.group(1)}</step>{f'<alter>{alter}</alter>' if alter else ''}<octave>{m.group(3)}</octave></pitch>"
    hide = ' print-object="no"' if hidden else ''
    tied = '<tie type="start"/>' if tie else ''
    on = f'<staff>{staff}</staff>' if staff else ''
    return (f"<note{hide}>{extra}{'<chord/>' if chord else ''}{pitch}<duration>{int(q * 2)}</duration>"
            f"{tied}<voice>{voice}</voice>{on}</note>")


def BACK(q):
    return f'<backup><duration>{int(q * 2)}</duration></backup>'


def score(parts, fifths=1, mode='major', time=('2', '4'), staves=None):
    """parts: [(name, [measure contents])]: a partwise MusicXML score (bytes)."""
    plist, body = '', ''
    for i, (name, ms) in enumerate(parts):
        plist += f'<score-part id="P{i + 1}"><part-name>{name}</part-name></score-part>'
        attrs = (f'<attributes><divisions>2</divisions><key><fifths>{fifths}</fifths><mode>{mode}</mode></key>'
                 f'<time><beats>{time[0]}</beats><beat-type>{time[1]}</beat-type></time>'
                 f'{f"<staves>{staves}</staves>" if staves else ""}</attributes>')
        body += f'<part id="P{i + 1}">' + ''.join(
            f'<measure number="{k + 1}">{attrs if k == 0 else ""}{m}</measure>' for k, m in enumerate(ms)) + '</part>'
    return (f'<?xml version="1.0"?><score-partwise><part-list>{plist}</part-list>{body}</score-partwise>').encode()


DBL = '<barline location="right"><bar-style>light-light</bar-style></barline>'
# Turle-2's first phrase, as plain bars of absolute notes: soprano, alto, tenor, bass
PHRASE = {'S': [['A4:2'], ['D4:1', 'E4:1'], ['F4:2']], 'A': [['D4:2'], ['D4:1', 'C#4:1'], ['D4:2']],
          'T': [['F3:2'], ['A3:1', 'A3:1'], ['A3:2']], 'B': [['D3:2'], ['F3:1', 'A3:1'], ['D3:2']]}


def bar(notes, **k):
    return ''.join(N(*(n.split(':')[0], float(n.split(':')[1])), **k) for n in notes)


class MusicXMLScores(unittest.TestCase):
    """What real scores do, beyond the tidy layouts."""
    def imp(self, data):
        import musicxml
        return musicxml.to_parts(data)

    def notes(self, parts):
        """{voice: [(midi…, start, length)]} of the imported chant, by the chant files' own reader."""
        from chantparse import load_chant
        c = load_chant(chantedit.apply(chantedit.template(), parts), is_text=True)
        return {v[0]: [tuple(sorted(h.midi for h in (n if isinstance(n, list) else [n]))) + (n[0].start if isinstance(n, list) else n.start,)
                       for n in ns] for v, (ns, _) in c['voices'].items()}

    def four_parts(self, phrase=PHRASE, names=('Soprano', 'Alto', 'Tenor', 'Bass'), last=DBL):
        return score([(nm, [bar(b) + (last if i == 2 else '') for i, b in enumerate(phrase[v])])
                      for nm, v in zip(names, 'SATB')])

    def test_reference(self):
        parts, info = self.imp(self.four_parts())
        self.assertEqual(parts['voices'][0]['body'], 'a2 | d,4 e | f2 \\bar "||"')
        self.assertEqual(info['warnings'], [])

    def test_musescore_closed_score_with_unison(self):
        """One part, two staves; voices 1-2 on the upper staff and 5-6 on the lower (MuseScore's numbering);
        in the first bar the alto sings with the soprano (no voice 2), and in the second it has hidden rests."""
        P = PHRASE
        ms = [bar(P['S'][0], voice=1, staff=1) + BACK(2) + bar(P['T'][0], voice=5, staff=2) + BACK(2) + bar(P['B'][0], voice=6, staff=2),
              bar(P['S'][1], voice=1, staff=1) + BACK(2) + N('', 2, voice=2, staff=1, rest=True, hidden=True) + BACK(2)
              + bar(P['T'][1], voice=5, staff=2) + BACK(2) + bar(P['B'][1], voice=6, staff=2),
              bar(P['S'][2], voice=1, staff=1) + BACK(2) + bar(P['A'][2], voice=2, staff=1) + BACK(2)
              + bar(P['T'][2], voice=5, staff=2) + BACK(2) + bar(P['B'][2], voice=6, staff=2) + DBL]
        parts, _ = self.imp(score([('Choir', ms)], staves=2))
        got, ref = self.notes(parts), self.notes(self.imp(self.four_parts())[0])
        self.assertEqual(got['S'], ref['S'])
        self.assertEqual(got['A'][:3], got['S'][:3])            # unison where the alto had no notes of its own
        self.assertEqual(got['A'][3:], ref['A'][3:])
        self.assertEqual((got['T'], got['B']), (ref['T'], ref['B']))

    def test_the_higher_voice_is_the_upper_one(self):
        """Voice 1 isn't always the top one (Finale may put the alto there): the higher line is taken as the soprano."""
        P = PHRASE
        ms = [bar(P['A'][k]) + BACK(2) + bar(P['S'][k], voice=2) for k in range(3)]
        lo = [bar(P['T'][k]) + BACK(2) + bar(P['B'][k], voice=2) for k in range(3)]
        parts, _ = self.imp(score([('Upper', ms), ('Lower', lo)]))
        self.assertEqual(self.notes(parts), self.notes(self.imp(self.four_parts())[0]))

    def test_chords_and_voices_mixed_in_a_staff(self):
        P = PHRASE
        def chords(hi, lo):        # two voices on one stem, as chords
            return ''.join(N(a.split(':')[0], float(a.split(':')[1])) + N(b.split(':')[0], float(b.split(':')[1]), chord=True)
                           for a, b in zip(hi, lo))
        upper = [chords(P['S'][0], P['A'][0]), bar(P['S'][1]) + BACK(2) + bar(P['A'][1], voice=2), chords(P['S'][2], P['A'][2]) + DBL]
        lower = [chords(P['T'][k], P['B'][k]) for k in range(3)]
        parts, _ = self.imp(score([('Women', upper), ('Men', lower)]))
        self.assertEqual(self.notes(parts), self.notes(self.imp(self.four_parts())[0]))

    def test_a_divided_voice_stays_divided(self):
        P = dict(PHRASE, S=[['A4:2'], ['D4:1', 'E4:1'], ['F4:2']])
        data = self.four_parts(P).replace(b'<pitch><step>F</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice></note>',
                                          b'<pitch><step>F</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice></note>'
                                          b'<note><chord/><pitch><step>A</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice></note>', 1)
        parts, _ = self.imp(data)
        self.assertIn("<a f>2", parts['voices'][0]['body'])     # top note first, as in the chant files

    def test_an_organ_part_is_left_out(self):
        organ = [bar(['D4:2']) + BACK(2) + bar(['A3:2'], voice=2)] * 3
        parts, info = self.imp(score([(n, [bar(b) + (DBL if i == 2 else '') for i, b in enumerate(PHRASE[v])])
                                      for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')] + [('Organ', organ)]))
        self.assertTrue(any('leaving out Organ' in w for w in info['warnings']))
        self.assertEqual(self.notes(parts), self.notes(self.imp(self.four_parts())[0]))

    def test_parts_by_their_names(self):
        rev = score([(nm, [bar(b) + (DBL if i == 2 else '') for i, b in enumerate(PHRASE[v])])
                     for nm, v in (('Bass', 'B'), ('Tenor', 'T'), ('Alto', 'A'), ('Soprano', 'S'))])
        parts, info = self.imp(rev)
        self.assertEqual(self.notes(parts), self.notes(self.imp(self.four_parts())[0]))
        self.assertEqual(info['warnings'], [])

    def test_voices_by_name_among_instruments(self):
        flute = [bar(['D5:2'])] * 3
        named = score([('Flute', flute)] + [(n, [bar(b) + (DBL if i == 2 else '') for i, b in enumerate(PHRASE[v])])
                                            for n, v in zip(('Soprano', 'Alto', 'Tenor', 'Bass'), 'SATB')])
        parts, info = self.imp(named)
        self.assertEqual(self.notes(parts), self.notes(self.imp(self.four_parts())[0]))
        self.assertTrue(any('leaving out Flute' in w for w in info['warnings']), info['warnings'])
        P = PHRASE                                                  # two staves named for two voices each, organ first
        closed = score([('Organ', flute)] + [(nm, [bar(P[hi][k]) + BACK(2) + bar(P[lo][k], voice=2) for k in range(3)])
                                            for nm, hi, lo in (('S. A.', 'S', 'A'), ('Tenor/Bass', 'T', 'B'))])
        self.assertEqual(self.notes(self.imp(closed)[0]), self.notes(self.imp(self.four_parts())[0]))

    def test_a_voice_resting_a_bar(self):
        rest = score([(n, [bar(b) if not (v == 'A' and i == 1) else N('', 2, rest=True) for i, b in enumerate(PHRASE[v])])
                      for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')])
        alto = self.imp(rest)[0]['voices'][1]['body']
        self.assertEqual(alto, 'd2 | r | d \\bar "||"')
        silent = score([(n, [bar(b) for b in PHRASE[v]] + [N('', 2, rest=True)] + [bar(b) for b in PHRASE[v]])
                        for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')])            # all rest: a phrase's end
        body = self.imp(silent)[0]['voices'][0]['body']
        self.assertEqual([line.count('|') for line in body.split('\n')], [4, 4], body)

    def test_phrase_ends(self):
        two = {v: b + b for v, b in PHRASE.items()}                          # 6 bars: two phrases of 3
        left = score([(n, [bar(b) + ('<barline location="left"><bar-style>light-light</bar-style></barline>' if i == 3 else '')
                           for i, b in enumerate(two[v])]) for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')])
        empty = score([(n, [bar(b) for b in two[v][:3]] + [''] + [bar(b) for b in two[v][3:]]) for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')])
        for data in (left, empty):                                           # a barline on the left; an empty bar
            body = self.imp(data)[0]['voices'][0]['body']
            self.assertEqual([line.count('|') for line in body.split('\n')], [4, 4], body)     # 3 bars + the end, twice

    def test_ties_grace_notes_and_lengths(self):
        P = dict(PHRASE, S=[['A4:2'], ['D4:1', 'E4:1'], ['F4:2']])
        data = self.four_parts(P).replace(b'<note><pitch><step>A</step><octave>4</octave>',
                                          b'<note><grace/><pitch><step>B</step><octave>4</octave></pitch><voice>1</voice></note>'
                                          b'<note><pitch><step>A</step><octave>4</octave>', 1)
        data = data.replace(b'<note><pitch><step>D</step><octave>4</octave>',                   # and a cue note
                            b'<note><cue/><pitch><step>G</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice></note>'
                            + BACK(2).encode() + b'<note><pitch><step>D</step><octave>4</octave>', 1)
        parts, info = self.imp(data)
        self.assertTrue(parts['voices'][0]['body'].startswith('a2 | d,4 e |'), parts['voices'][0]['body'])   # left out
        tied = score([(n, [bar(['A4:2'], tie=(v == 'S')) if i == 0 else bar(b) for i, b in enumerate(PHRASE[v])])
                      for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')])
        self.assertTrue(self.imp(tied)[0]['voices'][0]['body'].startswith('a2~ |'))
        short = score([(n, [bar(b) if not (v == 'A' and i == 1) else bar(['D4:1']) for i, b in enumerate(PHRASE[v])])
                       for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')])
        self.assertIn("Alto: bar 2 doesn't add up to 2/4", self.imp(short)[1]['warnings'])

    def test_what_a_chant_cant_have(self):
        import musicxml
        triplet = self.four_parts().replace(b'<duration>2</duration>', b'<duration>1</duration>', 1)    # odd lengths
        triplet = triplet.replace(b'<divisions>2</divisions>', b'<divisions>3</divisions>', 1)
        three = score([('Choir', [N('A4', 2) + N('F4', 2, chord=True) + N('D4', 2, chord=True)] * 3)])
        voices3 = score([('Choir', [N('A4', 2) + BACK(2) + N('F4', 2, voice=2) + BACK(2) + N('D4', 2, voice=3)] * 3)])
        for data, says in ((triplet, 'unusual length'), (three, 'chord of 3 notes'), (voices3, 'a staff with 3 voices'),
                           (score([('S', [bar(['A4:2'])] * 3)]), 'found 1 voice'), (b'', 'not a MusicXML'),
                           (b'<html><body>hi</body></html>', 'not a MusicXML score'), (b'PK\x03\x04junk', 'zip'),
                           (b'<score-timewise/>', 'timewise')):
            with self.assertRaises(ValueError) as e:
                musicxml.to_parts(data)
            self.assertIn(says, str(e.exception))

    def test_encodings_and_wrappers(self):
        import io, zipfile
        plain = self.four_parts()
        ref = self.imp(plain)[0]
        fancy = plain.replace(b'<?xml version="1.0"?>', b'<?xml version="1.0" encoding="UTF-16"?>\n<!DOCTYPE score-partwise PUBLIC '
                              b'"-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">')
        fancy = fancy.replace(b'<score-partwise>', b'<score-partwise xmlns="http://www.musicxml.org/ns" version="4.0">')
        self.assertEqual(self.imp(fancy.decode().encode('utf-16'))[0], ref)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:                                 # an .mxl without its container file
            z.writestr('score.musicxml', plain)
        self.assertEqual(self.imp(buf.getvalue())[0], ref)

    def test_a_zip_bomb_is_refused(self):
        import io, zipfile, musicxml
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:      # 1 MB that would expand to 1 GB
            with z.open('score.xml', 'w') as f:
                for _ in range(256):
                    f.write(b'\0' * (4 << 20))
        with self.assertRaises(ValueError) as e:
            musicxml.to_parts(buf.getvalue())
        self.assertIn('over 20 MB', str(e.exception))

    def test_xml_attacks_are_refused(self):
        import musicxml
        laughs = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa">' + b''.join(
            b'<!ENTITY %c "%s">' % (98 + i, (b'&%c;' % (97 + i)) * 10) for i in range(8)) +
            b']><score-partwise><work><work-title>&i;</work-title></work></score-partwise>')
        local_file = (b'<?xml version="1.0"?><!DOCTYPE s [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
                      b'<score-partwise><work><work-title>&x;</work-title></work></score-partwise>')
        for data in (laughs, local_file):                                # nothing expanded, nothing read
            with self.assertRaises(ValueError):
                musicxml.to_parts(data)

    def test_key_and_time(self):
        parts, info = self.imp(score([(n, [bar(b) for b in PHRASE[v]]) for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')],
                                     fifths=-1, mode='minor'))
        self.assertEqual(parts['key'], {'tonic': 'd', 'mode': 'minor'})
        changed = score([(n, [bar(b) if i != 1 else '<attributes><key><fifths>2</fifths></key><time><beats>3</beats>'
                              '<beat-type>4</beat-type></time></attributes>' + bar(b) for i, b in enumerate(PHRASE[v])])
                         for n, v in zip(('S', 'A', 'T', 'B'), 'SATB')])
        w = self.imp(changed)[1]['warnings']
        self.assertTrue(any('key changes' in x for x in w) and any('time changes' in x for x in w), w)


class Service(unittest.TestCase):
    def test_service_music_with_a_space(self):
        self.assertEqual(service.hymn('S 278')['number'], 'S278')
        self.assertEqual(service.hymn('LEVAS 114')['book'], 'LEVAS')
        self.assertIsNone(service.hymn('Sanctus - William Byrd'))

    def test_anthems_by_composer(self):
        lib = [{'title': 'Ave verum corpus', 'composer': 'W. A. Mozart (1756-1791)', 'file': 'ave-mozart'}]
        self.assertIsNone(service.find_anthem('Ave verum corpus - William Byrd', lib))
        self.assertEqual(service.find_anthem('Ave verum corpus - W. A. Mozart', lib)['file'], 'ave-mozart')



class Library(unittest.TestCase):
    """The music library (tools/library.py): no particular folders, no catalog needed."""
    def setUp(self):
        import library
        self.L, self.d = library, tempfile.mkdtemp()
        self.rows = lambda *r: [{c: '' for c in library.COLUMNS} | x for x in r]

    def tearDown(self):
        subprocess.run(['rm', '-rf', self.d])

    def test_names_of_pdfs(self):
        p = self.L.parse_name
        self.assertEqual(p('Fauré-Op_048-Requiem.pdf'), {'Composer': 'Fauré', 'Title': 'Requiem', 'Catalog no.': 'Op. 48'})
        self.assertEqual(p('Monteverdi-SV_259-Beatus_vir.pdf')['Catalog no.'], 'SV 259')
        self.assertEqual(p('a scan.pdf'), {'Composer': '', 'Title': 'a scan', 'Catalog no.': ''})   # no pattern: title only
        self.assertEqual(p('Requiem (Faure).pdf', '{title} ({composer})')['Composer'], 'Faure')

    def test_same_title_other_composer(self):
        rows = self.rows({'Title': 'Ave verum corpus', 'Composer': 'William Byrd'})
        self.assertIsNone(self.L.find(rows, 'Ave verum corpus - W. A. Mozart (1756-1791)'))
        self.assertIs(self.L.find(rows, 'Ave verum corpus - Byrd'), rows[0])
        rows, r, new = self.L.add({'Title': 'Ave verum corpus', 'Composer': 'Byrd', 'Copies': '24'}, rows)
        self.assertFalse(new)
        self.assertEqual((len(rows), r['Copies'], r['Composer']), (1, '24', 'William Byrd'))   # filled in, not doubled
        for bad in ({'Title': ''}, {'Title': 'X', 'Season': 'summer'}, {'Title': 'X', 'Format': 'Vinyl'}):
            with self.assertRaises(ValueError):
                self.L.add(bad, rows)

    def test_from_what_was_sung(self):
        rep = {'anthem': [['Hodie - Sweelinck', ['2024-12-24', '2025-12-25']],
                          ['O taste and see - Ralph Vaughan Williams (1872-1958)', ['2025-03-02', '2025-07-13', '2025-10-05']],
                          ['390', ['2025-01-05']], ['???', ['2025-02-02']], ['TBD', ['2025-02-09']]]}
        rows, n = self.L.from_record([], rep)
        self.assertEqual(n, 2)                                  # a hymn number isn't a piece, nor '???'
        self.assertEqual(rows[0]['Season'], 'christmas')
        self.assertEqual((rows[1]['Season'], rows[1]['Years']), ('', '1872-1958'))   # all year round: any time
        self.assertEqual(self.L.from_record(rows, rep)[1], 0)

    def test_dates_with_a_dash(self):
        self.assertEqual(self.L.split_piece('Song for Athene - John Tavener (1944 - 2013)'),
                         ('Song for Athene', 'John Tavener', '1944-2013'))
        self.assertEqual(self.L.split_piece('Hodie - Sweelinck'), ('Hodie', 'Sweelinck', ''))
        self.assertEqual(self.L.split_piece('Anthem (1990)'), ('Anthem (1990)', '', ''))

    def test_pdfs_found_for_pieces(self):
        os.makedirs(os.path.join(self.d, 'Advent'))
        for f in ('Advent/Tallis-Audivi_vocem.pdf', 'Thomson_R-My_Shepherd_Will_Supply_My_Need.pdf', 'Byrd-Ave_verum.pdf'):
            open(os.path.join(self.d, f), 'wb').write(b'%PDF')
        rows = self.rows({'Title': 'Audivi vocem de caelo', 'Composer': 'Thomas Tallis', 'Years': 'c. 1505-1585'},
                         {'Title': 'My Shepherd will supply my need', 'Composer': 'Virgil Thomson'},
                         {'Title': 'Ave verum corpus', 'Composer': 'W. A. Mozart'},          # Byrd's isn't Mozart's
                         {'Title': 'Hodie', 'File': 'Hodie.pdf'})                             # not on this computer
        got = self.L.pdfs(rows, {'score folders': self.d})
        self.assertEqual(got, {'Audivi vocem de caelo - Thomas Tallis (c. 1505-1585)': 'Advent/Tallis-Audivi_vocem.pdf',
                               'My Shepherd will supply my need - Virgil Thomson': 'Thomson_R-My_Shepherd_Will_Supply_My_Need.pdf'})
        self.assertEqual(self.L.pdfs(rows, {}), {})

    def test_any_folders(self):
        for f in ('Lent/Farrant-Hide_not_thou_thy_face.pdf', 'Byrd-Vigilate.pdf', 'Hymns/x.pdf', 'General/Tallis-If_ye_love_me.pdf'):
            os.makedirs(os.path.dirname(os.path.join(self.d, f)), exist_ok=True)
            open(os.path.join(self.d, f), 'wb').write(b'%PDF-1.4')
        s = {'score folders': self.d, 'skip folders': 'Hymns', 'folder seasons': 'Lent = lent, General = any'}
        rows = self.rows({'Title': 'If ye love me', 'Composer': 'Tallis', 'File': 'Tallis-If_ye_love_me.pdf'},
                         {'Title': 'Gone', 'File': 'Gone.pdf'})
        r = self.L.scan(rows, s)
        self.assertEqual(sorted(x['File'] for x in r['new']), ['Byrd-Vigilate.pdf', 'Lent/Farrant-Hide_not_thou_thy_face.pdf'])
        self.assertEqual([x['Season'] for x in r['new'] if x['Composer'] == 'Farrant'], ['lent'])
        self.assertEqual(r['moved'], [['Tallis-If_ye_love_me.pdf', 'General/Tallis-If_ye_love_me.pdf']])
        self.assertEqual(r['missing'], ['Gone.pdf'])
        rows.append(self.rows({'Title': 'Vigilate', 'Composer': 'William Byrd', 'Format': 'Octavo'})[0])
        self.assertEqual([x.get('Matches') for x in self.L.scan(rows, s)['new'] if x['Title'] == 'Vigilate'],
                         ['Vigilate - William Byrd'])                    # the octavos' piece gets its PDF
        self.assertIsNone(self.L.score_path('../' + os.path.basename(self.d) + '/Byrd-Vigilate.pdf', {'score folders': self.d + '/Lent'}))
        self.assertTrue(self.L.score_path('Byrd-Vigilate.pdf', s))
        self.assertEqual(self.L.scan(rows, {})['new'], [])                 # no score folders: nothing to look at
        other = {'score folders': '/no/such/computer; ' + self.d}               # each computer uses the folder it has
        self.assertEqual(self.L.score_folders(other), [self.d])
        from unittest import mock
        with mock.patch.object(self.L, 'settings', return_value={'score folders': '/no/such/computer'}), \
                mock.patch.object(self.L, 'read', return_value=[]):
            self.assertEqual(self.L.page_data()['unfound'], ['/no/such/computer'])   # the page says which folder it looked for
        with mock.patch.object(self.L, 'settings', return_value=other), mock.patch.object(self.L, 'read', return_value=[]):
            self.assertEqual(self.L.page_data()['unfound'], [])
        import serve                                                    # a page built elsewhere hears from this computer
        with mock.patch.object(self.L, 'settings', return_value=other), mock.patch.object(serve.paths, 'PARISH', self.d), \
                mock.patch.object(self.L, 'read', return_value=[]):
            self.assertEqual(serve.get_ping({})['library'], {'folders': True, 'pdfs': {}, 'unfound': []})

    def test_adding_a_pdf(self):
        os.makedirs(os.path.join(self.d, 'Easter'))
        s = {'score folders': self.d, 'folder seasons': 'Easter = easter', 'file new pdfs': '{season}/{composer}-{catalog}-{title}.pdf'}
        r = self.L.clean({'Title': 'Rise up my love', 'Composer': 'Healey Willan', 'Season': 'easter'})
        self.assertEqual(self.L.place_pdf(r, b'%PDF-1.4', s), 'Easter/Healey_Willan-Rise_up_my_love.pdf')
        r = self.L.clean({'Title': 'Vigilate', 'Composer': 'Byrd', 'Season': 'advent'})   # no Advent folder: the top
        self.assertEqual(self.L.place_pdf(r, b'%PDF-1.4', s), 'Byrd-Vigilate.pdf')
        for data, row in ((b'not a pdf', r), (b'%PDF', r)):                # not a PDF; one already there
            with self.assertRaises(ValueError):
                self.L.place_pdf(row, data, s)
        self.assertNotIn('/', self.L.place_pdf(self.L.clean({'Title': '../../x', 'Composer': 'a/b'}), b'%PDF', s))

    def test_settings_and_round_trip(self):
        import library
        open(os.path.join(self.d, 'library.txt'), 'w').write('# a comment\nscore folders: C:\\Music\\Sacred; D:/More   # two\n')
        self.assertEqual(library._settings_file(os.path.join(self.d, 'library.txt'), {})['score folders'], 'C:\\Music\\Sacred; D:/More')
        f = os.path.join(self.d, 'catalog.csv')
        rows = self.rows({'Title': 'Requiem', 'Composer': 'Fauré', 'Format': 'PDF', 'Mine': 'kept'})
        library.write(rows, f)
        back = library.read(f)
        self.assertEqual((back[0]['Composer'], back[0]['Mine']), ('Fauré', 'kept'))   # accents, and columns of your own
        library.write(back, f)
        self.assertEqual(len(os.listdir(os.path.join(self.d, 'backups'))), 1)          # not in git: a copy is kept



class Keystore(unittest.TestCase):
    def test_a_secret_under_the_old_name_is_moved(self):
        import keystore
        d = tempfile.mkdtemp()
        saved = keystore.DIR, keystore.OLD_DIR, keystore._keyring
        keystore.DIR, keystore.OLD_DIR, keystore._keyring = os.path.join(d, 'new'), os.path.join(d, 'old'), lambda: None
        try:
            os.makedirs(keystore.OLD_DIR)
            open(os.path.join(keystore.OLD_DIR, 'gmail.json'), 'w').write('{"music@example.org": "app password"}')
            self.assertEqual(keystore.get('precentor-gmail', 'music@example.org'), 'app password')
            self.assertTrue(os.path.exists(os.path.join(keystore.DIR, 'gmail.json')))        # now kept under the new name
            self.assertIsNone(keystore.get('precentor-gmail', 'someone@else.org'))
        finally:
            keystore.DIR, keystore.OLD_DIR, keystore._keyring = saved
            subprocess.run(['rm', '-rf', d])

class Setup(unittest.TestCase):
    def test_settings(self):
        import setup
        t = setup.settings_text(paths.read(os.path.join(setup.TEMPLATE, 'parish.txt')), "St. Mary's, Anytown", '1',
                                'st_mary_the_virgin', 'leave out')
        self.assertIn("name:          St. Mary's, Anytown", t)
        self.assertRegex(t, r'(?m)^track:\s+1$')
        self.assertRegex(t, r"(?m)^patronal:\s+08-15 st_mary_the_virgin Saint Mary the Virgin$")
        self.assertRegex(t, r'(?m)^optional_verses: leave out$')
        self.assertIn('# season_colors:', t)                       # the template's comments are kept
        for bad in (('', '2', ''), ('X', '3', ''), ('X', '2', 'st_nobody')):
            with self.assertRaises(ValueError):
                setup.settings_text(t, *bad)

    def test_every_feast_has_its_psalm(self):
        import csv, setup
        with open(os.path.join(ROOT, 'reference', 'rcl_psalms.csv'), encoding='utf-8') as fh:
            keys = {r['day'] for r in csv.DictReader(fh)}
        self.assertEqual([k for _, k, _ in setup.FEASTS if k not in keys], [])

    def test_the_folder(self):
        import setup
        d = os.path.join(tempfile.mkdtemp(), 'parish')
        try:
            setup.make_parish('St. Test', target=d)
            self.assertTrue(os.path.isdir(os.path.join(d, '.git')))
            self.assertEqual([f for f in os.listdir(os.path.join(d, 'sundays')) if f.endswith('.txt')], [])
            with self.assertRaises(ValueError):
                setup.make_parish('St. Test', target=d)            # never over an existing folder
        finally:
            subprocess.run(['rm', '-rf', os.path.dirname(d)])


class Server(unittest.TestCase):
    def test_lilypond_found_where_it_was_unzipped(self):
        import build
        from unittest import mock
        home = tempfile.mkdtemp()
        for v in ('2.24.4', '2.26.0'):
            os.makedirs(os.path.join(home, 'Downloads', f'lilypond-{v}', 'bin'))
            open(os.path.join(home, 'Downloads', f'lilypond-{v}', 'bin', 'lilypond.exe'), 'w').close()
        with mock.patch.dict(os.environ, {'HOME': home, 'USERPROFILE': home}):
            self.assertEqual(build.installed_lilyponds()[0],
                             os.path.join(home, 'Downloads', 'lilypond-2.26.0', 'bin', 'lilypond.exe'))   # the newest

    def test_the_emailed_pictures_are_cut_to_the_ink(self):
        import build
        from PIL import Image
        im = Image.new('RGB', (400, 100), 'white')
        im.paste((0, 0, 0), (150, 20, 380, 80))                          # text set in from the left, as LilyPond leaves it
        self.assertEqual(build.trim(im).size, (230, 60))
        self.assertEqual(build.trim(Image.new('RGB', (10, 10), 'white')).size, (10, 10))

    def test_a_sync_that_brings_new_tools_restarts_the_launcher(self):
        import browser, serve
        from unittest import mock
        with mock.patch.dict(serve.SERVING, {'code': browser.page_signature()}):
            self.assertFalse(serve.code_changed())
        with mock.patch.dict(serve.SERVING, {'code': 'older'}):
            self.assertTrue(serve.code_changed())
        with mock.patch.dict(serve.SERVING, {}, clear=True):
            self.assertFalse(serve.code_changed())                       # not started by main(): nothing to compare

    def test_a_tool_can_print_a_check_mark_on_windows(self):
        import serve, tempfile
        from unittest import mock
        d = tempfile.mkdtemp()
        open(os.path.join(d, 'tick.py'), 'w', encoding='utf-8').write("print('\u2713 fine')\n")
        # Windows runs a tool's piped output in its code page (cp1252), which has no check mark
        with mock.patch.object(serve, 'TOOLS', d), mock.patch.dict(os.environ, {'PYTHONIOENCODING': 'cp1252'}):
            self.assertEqual(serve.run(['tick.py']), (0, '\u2713 fine'))

    def test_file_names(self):
        import serve
        self.assertEqual(serve.safe_name('2026-12-24-midnight'), '2026-12-24-midnight')
        for bad in ('../../etc/passwd', '/tmp/x', '.hidden', '-rf', None, 5, ''):
            with self.assertRaises(ValueError):
                serve.safe_name(bad)

    def test_a_page_built_by_other_code_is_rebuilt(self):
        import browser, serve
        d = tempfile.mkdtemp()
        saved = paths.SITE
        try:
            paths.SITE = d
            self.assertFalse(serve.page_out_of_date())                   # nothing built yet: built anyway
            open(os.path.join(d, 'data.js'), 'w').write('window.PRECENTOR = {"pageSignature":"0000"};\n')
            self.assertTrue(serve.page_out_of_date())
            open(os.path.join(d, 'data.js'), 'w').write(f'window.PRECENTOR = {{"pageSignature":"{browser.page_signature()}"}};\n')
            self.assertFalse(serve.page_out_of_date())
        finally:
            paths.SITE = saved
            subprocess.run(['rm', '-rf', d])


class ImportedRecord(unittest.TestCase):
    def test_every_acp_number_of_a_chant(self):
        """'ACP 001, 107, 181' once gave only ACP 1, so a record of ACP 181 went to whichever chant had it first."""
        import browser
        acp = browser.acp_numbers()
        self.assertEqual(acp[1], ('Battishill-1', '1'))
        self.assertEqual(acp[181], ('Battishill-1', '80'))
        self.assertEqual(acp[182], ('Davies-2', '80'))
        self.assertEqual(acp[132], ('Elgar-1', '59'))
        rows = [{'Chant': 'X-1', 'Source': 'ACP 008, 081, 193', 'ACP Psalm': '4, 37-1, 37-2, 85'},
                {'Chant': 'Y-1', 'Source': 'ACP 184, 216', 'ACP Psalm': '81'}]
        real = paths.catalog
        paths.catalog = lambda: rows
        try:
            acp = browser.acp_numbers()
        finally:
            paths.catalog = real
        self.assertEqual((acp[81], acp[193]), (('X-1', '37-1'), ('X-1', '85')))     # a psalm's parts count once
        self.assertEqual(acp[184], ('Y-1', '81'))
        self.assertNotIn(216, acp)                                                # not paired up: not guessed


class ImportEndpoint(unittest.TestCase):
    def test_answers(self):
        import base64, serve, musicxml
        b64 = lambda b: base64.b64encode(b).decode()
        j = serve.api_chant_import({'filename': 'c.musicxml', 'file': b64(musicxml_score := musicxml_bytes())})
        self.assertTrue(j['ok'])
        self.assertEqual([v['var'] for v in j['parts']['voices']], ['S_notes', 'A_notes', 'T_notes', 'B_notes'])
        self.assertEqual(j['warnings'], [])
        j = serve.api_chant_import({'filename': '../../etc/x.musicxml', 'file': b64(b'<html/>')})
        self.assertFalse(j['ok'])
        self.assertTrue(j['error'].startswith('x.musicxml: '), j['error'])          # the name only, never a path
        for bad in ({'file': 5}, {'file': 'not base64!'}, {}):
            with self.assertRaises(ValueError):
                serve.api_chant_import(bad)
        real = musicxml.to_parts
        musicxml.to_parts = lambda *a: {}['a fault in the importer']
        try:
            j = serve.api_chant_import({'filename': 'c.musicxml', 'file': b64(musicxml_score)})
        finally:
            musicxml.to_parts = real
        self.assertFalse(j['ok'])
        self.assertIn('the importer failed (KeyError', j['error'])


def musicxml_bytes():
    return musicxml(SATB)


class History(unittest.TestCase):
    """Record, undo, undo the undo: in a throwaway git repository standing in for the parish folder."""
    def setUp(self):
        self.d = tempfile.mkdtemp()
        subprocess.run(['git', 'init', '-q'], cwd=self.d, check=True)
        for k, v in (('user.name', 'T'), ('user.email', 't@t')):
            subprocess.run(['git', 'config', k, v], cwd=self.d, check=True)
        self.saved = paths.PARISH, paths.CORE
        paths.PARISH, paths.CORE = self.d, self.d

    def tearDown(self):
        paths.PARISH, paths.CORE = self.saved
        subprocess.run(['rm', '-rf', self.d])

    def write(self, name, text):
        p = os.path.join(self.d, name)
        open(p, 'w').write(text)
        return p

    def test_undo_and_redo(self):
        f = self.write('a.txt', 'one\n')
        history.record([f], 'New service: a')
        self.write('a.txt', 'two\n')
        history.record([f], 'Service: a')
        last = history.changes()[0]
        self.assertEqual(last['message'], 'Service: a')
        self.assertTrue(history.undo('parish', last['sha'])[0])
        self.assertEqual(paths.read(f), 'one\n')
        self.assertEqual(history.changes()[0]['message'], 'Undid: Service: a')
        self.assertFalse(history.undo('parish', last['sha'])[0])            # already undone
        self.assertTrue(history.undo('parish', history.changes()[0]['sha'])[0])
        self.assertEqual(paths.read(f), 'two\n')
        self.assertEqual(history.changes()[0]['message'], 'Redid: Service: a')

    def test_changes_from_before_the_rename_can_be_undone(self):
        f = self.write('a.txt', 'one\n')
        history.record([f], 'New service: a')
        self.write('a.txt', 'two\n')
        subprocess.run(['git', 'commit', '-q', '-am', 'Service: a', '-m', 'Recorded by the chant browser.'], cwd=self.d, check=True)
        last = history.changes()[0]
        self.assertEqual(last['message'], 'Service: a')
        self.assertTrue(history.undo('parish', last['sha'])[0])
        self.assertEqual(paths.read(f), 'one\n')

    def test_a_sync_reports_its_progress(self):
        """Each step of a sync moves the bar on (save, ask GitHub, bring in, send), ending at the last."""
        remote = tempfile.mkdtemp()
        subprocess.run(['git', 'init', '-q', '--bare', remote], check=True)
        f = self.write('a.txt', 'one\n')
        history.record([f], 'New service: a')
        for args in (['remote', 'add', 'origin', remote], ['push', '-q', '-u', 'origin', 'HEAD']):
            subprocess.run(['git'] + args, cwd=self.d, check=True, capture_output=True)
        self.write('a.txt', 'two\n')
        seen = []
        real = history.step
        history.step = lambda what: (real(what), seen.append((history.PROGRESS['done'], what)))
        history.PROGRESS.update(done=0, total=history.SYNC_STEPS * len(history.repos()))
        try:
            ok, log = history.sync('by hand')
        finally:
            history.step = real
            subprocess.run(['rm', '-rf', remote])
        self.assertTrue(ok, log)
        self.assertEqual([d for d, _ in seen], list(range(1, len(seen) + 1)))       # one step at a time
        self.assertEqual(len(seen), history.PROGRESS['total'])                        # all of them
        self.assertIn('sending yours to GitHub', seen[-1][1])

    def test_only_a_change_id_reaches_git(self):
        self.assertEqual(history.undo('parish', '--output=/tmp/x'), (False, 'no such change'))
        self.assertEqual(history.undo('parish', 'HEAD~2..HEAD'), (False, 'no such change'))

    def test_an_undo_commits_only_its_own_files(self):
        f = self.write('a.txt', 'one\n')
        history.record([f], 'New service: a')
        sha = history.changes()[0]['sha']
        g = self.write('b.txt', 'staged by hand\n')
        subprocess.run(['git', 'add', g], cwd=self.d, check=True)
        history.undo('parish', sha)
        shown = subprocess.run(['git', 'show', '--name-only', '--format=', 'HEAD'], cwd=self.d,
                               capture_output=True, text=True).stdout.split()
        self.assertEqual(shown, ['a.txt'])


if __name__ == '__main__':
    unittest.main()

"""Plain pointed text (.txt) -> LilyPond markup in ACP style.

The output uses the markup commands defined in style/psalm-style.ily:
  \\acpbar  \\acpbarin  \\grp  \\held  \\scs  \\vstart  \\ind  \\emptybar
"""
import re
import pyphen
try:
    import pronouncing
except ImportError:          # syllable counts fall back to hyphenation only
    pronouncing = None

from pointed import tokens, SMALLCAPS

HY = pyphen.Pyphen(lang='en_US')
VOWEL = 'aeiouyAEIOUY'


# ------------------------------------------------------------ syllable count
def syllables(words):
    n = 0
    for w in words:
        for part in re.findall(r"[A-Za-z']+", w):
            core = re.sub(r"'s$|'S$|'$", '', part)
            if not core:
                continue
            if core.upper() in SMALLCAPS:
                n += 1 if core.upper() != 'YAHWEH' else 2
                continue
            ph = pronouncing.phones_for_word(core.lower()) if pronouncing else []
            n += pronouncing.syllable_count(ph[0]) if ph else len(HY.inserted(core.lower()).split('-'))
    return n


# -------------------------------------------------------------- word markup
def lystr(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def curly(w):
    """Straight quotes -> typographic quotes, judged by position in the word."""
    w = re.sub(r'^"', '“', w)
    w = re.sub(r"^'(?=[A-Za-z=])", '‘', w)
    w = re.sub(r'(?<=“)\'(?=[A-Za-z=])', '‘', w)
    w = w.replace("'\"", '’ ”')     # nested close: ’ ”
    w = w.replace('"', '”')
    w = w.replace("'", '’')
    return w


def _text(s):
    """A run of plain text with LORD / GOD / YAHWEH set in small caps -> list of markup pieces."""
    out = []
    pat = re.compile(r"\b(%s)(?=\b|['’])" % '|'.join(SMALLCAPS))
    pos = 0
    for m in pat.finditer(s):
        if m.start() > pos:
            out.append(lystr(s[pos:m.start()]))
        word = m.group(1)
        out.append(lystr(word[0]))
        out.append('\\scs ' + lystr(word[1:]))
        pos = m.end()
        # an 'S after a small-caps word is small caps too (LORD'S); 's stays lower case
        sm = re.match("([’'])S\\b", s[pos:])
        if sm:
            out.append(lystr('’'))
            out.append('\\scs ' + lystr('S'))
            pos += 2
    if pos < len(s):
        out.append(lystr(s[pos:]))
    return out


def _rest_after_caps(rest):
    """What follows a held small-caps word: GOD'S keeps its 'S in small caps (as _text does), the rest as text."""
    sm = re.match("([’'])S\\b", rest)
    return ([lystr('’'), '\\scs ' + lystr('S')] + _text(rest[2:])) if sm else _text(rest)


def _cat(pieces):
    pieces = [p for p in pieces if p not in ('""',)]
    if len(pieces) == 1:
        return pieces[0]
    return '\\concat { ' + ' '.join(pieces) + ' }'


def word_markup(w):
    """One pointed-text word -> markup (held mark, small caps, quotes)."""
    if w == '—' or w == '—':
        return '\\emptybar'
    w = curly(w)
    m = re.match(r'^([“‘]*)=(.*)$', w)
    if not m:
        return _cat(_text(w))
    lead, word = m.groups()
    vm = re.match(r'^((?:[yY](?=[aeiouAEIOU]))?[^%s]*)([%s])(.*)$' % (VOWEL, VOWEL), word)    # YAHWEH: the A
    if not vm:
        return _cat(_text(lead + word))
    pre, vow, post = vm.groups()
    sc = re.match(r'^(%s)' % '|'.join(SMALLCAPS), word)
    if sc:      # held small-caps word: mark goes over the small-cap vowel
        cap = sc.group(1)
        return '\\held %s %s %s' % (
            _cat([lystr(lead + cap[0])] + (['\\scs ' + lystr(cap[1:cap.index(vow, 1)])] if cap.index(vow, 1) > 1 else [])),
            '\\scs ' + lystr(vow),
            _cat(['\\scs ' + lystr(cap[cap.index(vow, 1) + 1:])] + _rest_after_caps(word[len(cap):])))
    return '\\held %s %s %s' % (_cat([lystr(lead)] + _text(pre)) if (lead or pre) else '""',
                                lystr(vow), _cat(_text(post)) if post else '""')


# -------------------------------------------------------------- line markup
def line_markup(text):
    """Pointed text of one printed line -> the body of a \\line { } (without indentation)."""
    toks = tokens(text)
    segs, cur = [], []
    for t in toks:
        if t == '|':
            segs.append(cur)
            cur = []
        else:
            cur.append(t)
    segs.append(cur)

    items = []          # dict(words, grp, bar)
    for si, seg in enumerate(segs):
        groups, g = [], []
        for t in seg:
            if t == '.':
                groups.append(g)
                g = []
            else:
                g.append(t)
        groups.append(g)
        split_bar = len(groups) > 1
        first = True
        for g in groups:
            if not g:
                continue
            if split_bar and si > 0 and syllables(g) >= 2:
                items.append({'words': g, 'grp': True, 'bar': first})
            else:
                for k, w in enumerate(g):
                    items.append({'words': [w], 'grp': False, 'bar': si > 0 and first and k == 0})
            first = False

    out = []            # dict(mk, tail)
    for it in items:
        words = list(it['words'])
        prev_tail = out[-1]['tail'] if out else ''
        glue = prev_tail.endswith('-') and words[0].lstrip('=').startswith('-')     # split word: re- | -vives
        keep_hyphen = prev_tail.endswith('-') and not glue                        # hyphenated: loving- | kindness
        if glue:
            words[0] = re.sub(r'^(=?)-', r'\1', words[0])
        tail = words[-1]
        mks = [word_markup(w) for w in words]
        mk = ('\\grp \\line { ' + ' '.join(mks) + ' }') if it['grp'] else ' '.join(mks)
        if glue or keep_hyphen:
            prev = out[-1]
            if glue:
                prev['mk'] = _strip_hyphen(prev['mk'])
            bar = '\\acpbarin ' if it['bar'] else ''
            prev['mk'] = '\\concat { ' + prev['mk'] + ' ' + bar + mk + ' }'
            prev['tail'] = tail
        else:
            if it['bar']:
                mk = '\\concat { \\acpbar ' + mk + ' }'
            out.append({'mk': mk, 'tail': tail})
    return ' '.join(o['mk'] for o in out)


def _strip_hyphen(mk):
    """Remove the trailing hyphen of a split word from its markup."""
    i = mk.rfind('-"')
    if i < 0:
        return mk
    return mk[:i] + mk[i + 1:]


# --------------------------------------------------------------- whole psalm
def verse_lines(v):
    lines = []
    for i, ln in enumerate(v['lines']):
        body = line_markup(ln['text'])
        if i == 0:
            lead = '\\vstart %s ##%s' % (lystr(str(v['n'])), 't' if v['dagger'] else 'f')
        elif ln['wrap']:
            lead = "\\ind #'wrap"
        elif ln['half'] == 1:
            lead = "\\ind #'flex"
        else:
            lead = "\\ind #'second"
        lines.append('  \\line { %s %s }' % (lead, body))
    return lines


def verse_markup(v):
    """One verse as its own block (page breaks fall between verses)."""
    return '\\markup \\psalmtext {\n' + '\n'.join(verse_lines(v)) + '\n}'


def single_block(blocks_title, verses):
    """Title (optional) and verses in one markup: used for images, which must not be split."""
    rows = []
    for i, v in enumerate(verses):
        if i:
            rows.append('  \\versegap')
        rows += verse_lines(v)
    text = '\\psalmtext {\n' + '\n'.join(rows) + '\n}'
    if not blocks_title:
        return '\\markup ' + text
    # the title stays its own size; only the verses are set at text-size
    return ('\\markup { \\override #(cons \'baseline-skip line-spacing) \\column {\n  ' + blocks_title +
            '\n  \\vspace #(* 0.5 verse-gap)\n' + text + '\n} }')


def title_line(doc, show_latin=True):
    return '\\psalmtitle %s %s' % (lystr(doc['title']), lystr(doc['latin'] if (show_latin and doc.get('latin')) else ''))


def title_markup(doc, show_latin=True):
    t = '\\psalmtitle %s %s' % (lystr(doc['title']), lystr(doc['latin'] if (show_latin and doc.get('latin')) else ''))
    return '\\markup { ' + t + ' }'


def psalm_markup(doc, first=None, last=None, title=True):
    """Markup blocks for a psalm, optionally limited to verses first..last."""
    blocks = [title_markup(doc)] if title else []
    for v in doc['verses']:
        if (first is None or v['n'] >= first) and (last is None or v['n'] <= last):
            blocks.append(verse_markup(v))
    return '\n'.join(blocks)

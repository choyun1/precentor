# Precentor repo notes

- Texts in `texts/*.txt` are the 1979 BCP words, unpointed, and must match it word for word; run `python tools/check_texts.py` after any text edit.
- Never add pointing copied from a printed psalter (the Anglican Chant Psalter and others are under copyright) to `texts/`. A parish's own pointed copies go in `parish/texts/`, which take the place of the unpointed ones.
- Only public-domain chants go in `chants/` (with a row in `chants/catalog.csv`); anything still under copyright goes in a parish's `parish/chants/`.
- Mood vocabulary lives in `moods.txt`; use only those tags in `texts/moods.csv` and the Mood column of a parish's chant notes.
- `parish/` is each user's own folder (often its own private repository) and is never committed here; `parish.example/` is the template. `tools/paths.py` says where everything is.
- Anything specific to one parish (name, track, orders of service, plugins such as an email to the office or a music schedule spreadsheet) belongs in its `parish/` folder, not in code.
- Never store a password, web-app address or secret (a plugin's either) in a repository; `tools/keystore.py` keeps them in the OS keyring or `~/.precentor/`.
- Use American spelling everywhere (favorite, color, catalog; St. Peter's), as the Episcopal Church does.
- After changing the tools, run `python -m unittest discover tests` (quick, no LilyPond); add a test there for any bug fixed.
- The chant browser page is `tools/browser/` (page.html, style.css, js/ by tab); `tools/browser.py` puts it into one file.

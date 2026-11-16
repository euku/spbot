# Recorded talk pages for the archive bot

Each `*.wiki` file is the wikitext of a real talk page at the time of a dry run of
`archive-resolved-bot.py` on Toolforge (2026-11-16). `cases.json` holds per page:
project, title, revision (`source` links to it), last editor/time, the time of the run
(`now`) and what the bot reported in that run (`expected`: report table, edit summaries,
followed redirects, refused main-namespace targets, option errors).
`tests/test_archive_fixtures.py` replays every page offline and compares.

The pages were chosen to differ in their settings (target variables, level, timeout,
TIMECOMPARE, redirects, error cases) and in their localization (de, en/commons,
enwikisource, incubator, it, ja, meta, vi, wikidata).

**License:** the page texts are taken from Wikimedia projects and are licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); the authors are listed
in the version history of the revision linked as `source` in `cases.json`.

## Re-recording

1. Dry run the bot as the tool for each page, e.g.
   `pyvenv/bin/python src/userscripts/archive-resolved-bot.py -simulate -dryrun -project:<p> -page:<title>`,
   writing all output into one file with a line `@@@@ new|<project>|<title>` before each run
   and `@@@@ exit=<code>` after it.
2. `python3 build_fixtures.py <that file> tests/fixtures/archive` (edit `CASES` in the script)
   fetches the revision current at the time of each run and writes `*.wiki` and `cases.json`.

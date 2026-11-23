# SpBot

Scripts of the Wikimedia bot account [SpBot](https://de.wikipedia.org/wiki/Benutzer:SpBot),
running as scheduled jobs on Toolforge (tool `spbot`). Pywikibot is installed
from PyPI (see `requirements.txt`), not vendored.

## Layout on Toolforge (`/data/project/spbot`)

- `bot/` – this repository
- `pyvenv/` – venv, created with `bot/bootstrap_venv.sh` inside the job image
- `.pywikibot/` – pywikibot base dir (`user-config.py`, cookies, throttle file);
  found automatically because it is `~/.pywikibot` of the tool account
- `logs/` – job logs; the scripts write their own logs relative to the
  working directory, so jobs must run with the tool home as working directory
- `toolforge-jobs.yaml` → `bot/jobs/toolforge-jobs.yaml`
- `www/python/src` → `bot/web` and `www/python/venv` – the status web page (see below)

## Settings that used to be patches in the pywikibot checkout

Put these into `~/.pywikibot/user-config.py`:

```python
password_file = '...'   # BotPassword file
put_throttle = 0        # no waiting between edits
minthrottle = 0
```

## Running a script manually

```sh
pyvenv/bin/python bot/userscripts/archive-resolved-bot.py -project:dewikipedia -page:Benutzer_Diskussion:Werner_von_Basil -dryrun
pyvenv/bin/python -m unittest discover -s bot/userscripts -p 'test_pers_bek*'
```

## Tests

`tests/` holds unit tests (pytest) that run without wiki access, also in GitHub CI
(`.github/workflows/tests.yml`). See `tests/README.md`.

## Status web page (https://spbot.toolforge.org/)

`web/` is a Flask app (webservice `python3.13`), in the style of pb.toolforge.org. It only reads:

- `jobs/toolforge-jobs.yaml` and the job logs (`logs/`, `logs/YYYY-MM-DD/`) for the services overview,
- the run summaries of the archive bot: `logs/archive-resolved-<project>.jsonl`, one JSON line
  per page with the options, the sections and the decision (written by
  `userscripts/archive_resolved/summary.py` in every full run, not for `-page` runs; `-nosummary`
  switches it off), and `logs/archive-runs.jsonl` (one line per run). Pages that were not edited and
  where no section is due are not read again for up to a week (`unchanged`, see
  `userscripts/archive_resolved/state.py`; `-full` reads all pages),
- the wiki replicas (bot flag, blocks, edits of SpBot), cached for 15 minutes.

`/archive?project=<project>&page=<title>` shows the last bot run of one page. The archive templates
can link there, e.g. `https://spbot.toolforge.org/archive?project=dewikipedia&page={{FULLPAGENAMEE}}`.

Setup (once): `mkdir -p ~/www/python && ln -s ~/bot/web ~/www/python/src`, create the venv in the
webservice image (`python3 -m venv ~/www/python/venv && ~/www/python/venv/bin/pip install -r ~/bot/web/requirements.txt`),
then `toolforge webservice python3.13 start`. After code changes: `toolforge webservice restart`.

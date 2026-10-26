# SpBot

Scripts of the Wikimedia bot account [SpBot](https://de.wikipedia.org/wiki/Benutzer:SpBot),
running as scheduled jobs on Toolforge (tool `spbot`). Pywikibot is installed
from PyPI (see `requirements.txt`), not vendored.

## Layout on Toolforge (`/data/project/spbot`)

- `src/` – this repository
- `pyvenv-standalone/` – venv, created with `src/bootstrap_venv.sh` inside the job image
- `.pywikibot/` – pywikibot base dir (`user-config.py`, cookies, throttle file);
  found automatically because it is `~/.pywikibot` of the tool account
- `logs/` – job logs; the scripts write their own logs relative to the
  working directory, so jobs must run with the tool home as working directory
- `toolforge-jobs.yaml` → `src/jobs/toolforge-jobs.yaml`

## Settings that used to be patches in the pywikibot checkout

Put these into `~/.pywikibot/user-config.py`:

```python
password_file = '...'   # BotPassword file
put_throttle = 0        # no waiting between edits
minthrottle = 0
```

## Running a script manually

```sh
pyvenv-standalone/bin/python src/userscripts/archive-resolved-bot.py -project:dewikipedia -page:Benutzer_Diskussion:Werner_von_Basil -dryrun
pyvenv-standalone/bin/python -m unittest discover -s src/userscripts -p 'test_pers_bek*'
```

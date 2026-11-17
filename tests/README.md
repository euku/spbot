# Tests

Unit tests for `userscripts/archive-resolved-bot.py` (package `userscripts/archive_resolved`)
and the status web page `web/` (`test_web.py`, skipped without Flask).
They need no wiki access and no user-config: `pywikibot.Page` is replaced by a fake
(`conftest.py`), the current time is fixed. They run in GitHub CI on every push.

On the Toolforge bastion (pytest is not in the tool venv, install it into a scratch dir):

```sh
pyvenv/bin/python -m pip install --target /tmp/$USER-pylib pytest flask
cd bot && PYTHONPATH=/tmp/$USER-pylib ../pyvenv/bin/python -m pytest -q tests
```

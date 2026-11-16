"""
Shared test setup for the archive-resolved bot.

- pywikibot runs without user-config.py and without network access
- all times are UTC (the bot uses time.mktime/localtime)
- FakeSite/FakePage replace pywikibot.Page, so nothing is written to a wiki
"""
import os
import sys
import time
from datetime import datetime
from types import SimpleNamespace

os.environ["PYWIKIBOT_NO_USER_CONFIG"] = "1"
os.environ["TZ"] = "UTC"
time.tzset()

USERSCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "userscripts")
if USERSCRIPTS not in sys.path:
    sys.path.insert(0, USERSCRIPTS)

import pytest  # noqa: E402
import pywikibot  # noqa: E402
from archive_resolved import core  # noqa: E402
from archive_resolved_localization.local_bot_factory import LocalBotFactory  # noqa: E402

BOT_USER = "SpBot"
# fixed "now" for all age calculations
NOW = datetime(2026, 11, 16, 12, 0)


class FakeRevision:
    def __init__(self, user, timestamp):
        self.user = user
        self.timestamp = timestamp


class FakePage:
    """Minimal stand-in for pywikibot.Page; one instance per title (see FakeSite.page)."""

    def __init__(self, site, title, text=None, namespace=None):
        self.site = site
        self._title = title
        self._exists = text is not None
        self.text = text or ""
        self._namespace = namespace
        self.redirectTo = None       # title of the redirect target
        self.protected = False
        self.saveError = None        # exception raised by save()
        self.saveErrorAfterWrite = False  # save() stores the text and raises anyway (e.g. timeout)
        self.saves = []              # (text, summary)
        self.latest_revision = FakeRevision("Somebody", datetime(2026, 11, 15, 8, 30))

    def title(self):
        return self._title

    def exists(self):
        return self._exists

    def get(self, force=False):
        if not self._exists:
            raise pywikibot.exceptions.NoPageError(self)
        return self.text

    def namespace(self):
        if self._namespace is not None:
            return self._namespace
        return 1 if ":" in self._title else 0

    def botMayEdit(self):
        return not self.protected

    def isRedirectPage(self):
        return self.redirectTo is not None

    def getRedirectTarget(self):
        return self.site.page(self.redirectTo)

    def _store(self, text, summary):
        self.saves.append((text, summary))
        self.text = text
        self._exists = True
        self.latest_revision = FakeRevision(BOT_USER, NOW)

    def save(self, summary=None, minor=False, force=False, **kwargs):
        if self.saveError is not None:
            if self.saveErrorAfterWrite:
                self._store(self.text, summary)
            raise self.saveError
        self._store(self.text, summary)

    def put(self, newtext, summary=None, **kwargs):
        self.text = newtext
        self.save(summary)


class FakeSite:
    def __init__(self):
        self.pages = {}

    def username(self):
        return BOT_USER

    def page(self, title, text=None):
        """Returns the page with this title; text != None creates/overwrites it as existing page."""
        if title not in self.pages:
            self.pages[title] = FakePage(self, title)
        page = self.pages[title]
        if text is not None:
            page.text = text
            page._exists = True
        return page

    def saved(self):
        """All saves as {title: [(text, summary), ...]}"""
        return {t: p.saves for t, p in self.pages.items() if p.saves}


def makeBot(project="dewikipedia", dryRun=False):
    return SimpleNamespace(localBot=LocalBotFactory().createLocalBot(project),
                           site=FakeSite(), dryRun=dryRun)


def makeDoc(text, bot=None, title="Benutzer Diskussion:Test", now=NOW):
    bot = bot or makeBot()
    return core.WikiDocument(text, title, datetime(2026, 11, 15, 8, 30), "Somebody", bot, now)


@pytest.fixture(autouse=True)
def fakePywikibotPage(monkeypatch):
    """pywikibot.Page(site, title) -> site.page(title); no sleeping in executeArchiving."""
    monkeypatch.setattr(pywikibot, "Page", lambda site, title: site.page(title))
    monkeypatch.setattr(core, "sleep", lambda seconds: None)

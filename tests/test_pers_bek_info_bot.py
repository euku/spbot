"""Tests for pers-bek-info-bot.py; nothing is read from a database or written to a wiki."""
import datetime
import os
import sys
import types

os.environ.setdefault("PYWIKIBOT_NO_USER_CONFIG", "1")

import pytest  # noqa: E402
import pywikibot  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "userscripts", "pers-bek-info-bot.py")
DATE = datetime.datetime(2026, 11, 23)


class Site:
    def __init__(self):
        self.pages = {}
        self.edits = []  # (title, appended text)

    def editpage(self, page, summary, appendtext, **kwargs):
        self.edits.append((page.title(), appendtext))


class Page:
    def __init__(self, site, title):
        self.site, self._title = site, title.replace("_", " ")

    def title(self):
        return self._title

    def namespace(self):
        return 3 if self._title.startswith("Benutzer Diskussion:") else 2

    def get(self):
        text = self.site.pages.get(self._title)
        if text is None:
            raise pywikibot.exceptions.NoPageError(self)
        if text.startswith("#"):
            raise pywikibot.exceptions.IsRedirectPageError(self)
        return text

    def getRedirectTarget(self):
        return Page(self.site, self.site.pages[self._title][1:])


class DB:
    def __init__(self, rows):
        self.rows = rows

    def get_yesterdays_confirmations_sorted_by_confirmed(self, day, delta):
        return [(was, has, None) for was, has in self.rows]


@pytest.fixture
def site():
    return Site()


@pytest.fixture
def m(monkeypatch, site):
    bot_api = types.ModuleType("bot_api")
    bot_api.BotDatabase = None
    monkeypatch.setitem(sys.modules, "bot_api", bot_api)
    mod = types.ModuleType("pers_bek_info_bot")
    with open(SCRIPT, encoding="utf-8") as f:
        exec(compile(f.read(), SCRIPT, "exec"), mod.__dict__)
    monkeypatch.setattr(pywikibot, "Site", lambda *a, **k: site)
    monkeypatch.setattr(pywikibot, "Page", Page)
    mod.usersToCheck = lambda: ["A", "B", "C", "D"]
    return mod


def talk(name):
    return "Benutzer Diskussion:" + name


def test_message(m, site):
    site.pages[talk("A")] = "Hallo"
    m.informUser("A", ["X"], DATE)
    [(title, text)] = site.edits
    assert title == talk("A")
    assert text.startswith("\n== neue Bestätigung am 23.11.2026 ==\nHallo! Du hast gestern eine neue Bestätigung von "
                           "{{noping|X|X}} bei")
    assert text.endswith("Gruß --~~~~")


def test_message_for_several_confirmations(m, site):
    site.pages[talk("A")] = "{{Autoarchiv-Erledigt|Alter=1}}"
    m.informUser("A", ["X", "Y", "Z"], DATE)
    [(title, text)] = site.edits
    assert "== neue Bestätigungen am 23.11.2026 ==" in text
    assert "gestern neue Bestätigungen von {{noping|X|X}}, {{noping|Y|Y}} und {{noping|Z|Z}} bei" in text
    assert text.endswith("\n{{Erledigt|1=~~~~}}")


def test_only_opt_in_users_are_informed(m, site):
    assert m.run(DB([("A", "X"), ("Nicht dabei", "X"), ("A", "Y")])) == 0
    assert [title for title, text in site.edits] == [talk("A")]


def test_redirect_to_the_new_name_is_followed(m, site):
    site.pages[talk("A")] = "#" + talk("Neu")
    site.pages[talk("Neu")] = "Hallo"
    assert m.run(DB([("A", "X")])) == 0
    assert [title for title, text in site.edits] == [talk("Neu")]


def test_one_failure_does_not_stop_the_others(m, site):
    site.pages[talk("A")] = "#Benutzer:A"   # no talk page
    site.pages[talk("B")] = "#" + talk("B2")
    site.pages[talk("B2")] = "#" + talk("B")   # double redirect
    assert m.run(DB([("A", "X"), ("B", "X"), ("C", "X"), ("D", "X")])) == 2
    assert [title for title, text in site.edits] == [talk("C"), talk("D")]


def test_no_second_message_for_the_same_day(m, site):
    site.pages[talk("A")] = "== neue Bestätigung am 23.11.2026 ==\nHallo!"
    m.informUser("A", ["X"], DATE)
    assert site.edits == []


def test_dry_run(m, site):
    m.DONOTSAVE = True
    m.informUser("A", ["X"], DATE)
    assert site.edits == []


@pytest.mark.parametrize("arg", ["--dryrun", "-dry-run", "-x"])
def test_unknown_argument(m, monkeypatch, arg):
    monkeypatch.setattr(pywikibot, "handle_args", lambda: [arg])
    m.BotDatabase = None   # would fail
    assert m.main() == 2

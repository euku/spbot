"""Tests for bot-stats.py (page layout, status colors, cache).

Nothing is fetched from or written to a wiki.

Run: pytest tests/test_bot_stats.py
"""
import importlib.util
import json
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("PYWIKIBOT_NO_USER_CONFIG", "1")

from pywikibot import Timestamp  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "userscripts", "bot-stats.py")
spec = importlib.util.spec_from_file_location("bot_stats", SCRIPT)
bs = importlib.util.module_from_spec(spec)
sys.modules["bot_stats"] = bs  # needed by @dataclass
spec.loader.exec_module(bs)

NOW = Timestamp(2026, 11, 18, 4, 0)


def ts(days_ago):
    return Timestamp.fromtimestamp(NOW.timestamp() - days_ago * 86400)


def bot(name="ExampleBot", editcount=10, flagged=True, **kwargs):
    kwargs.setdefault("registration", Timestamp(2020, 1, 2))
    kwargs.setdefault("last_edit", ts(1))
    return bs.BotInfo(name=name, editcount=editcount, flagged=flagged, **kwargs)


# --- status and colors ---

def test_status_by_age():
    assert bs.status(bot(last_edit=ts(91)), NOW) == ("aktiv", "DBF3EC")
    assert bs.status(bot(last_edit=ts(92)), NOW) == ("inaktiv", "FDF6D8")
    assert bs.status(bot(last_edit=ts(183)), NOW) == ("inaktiv", "FBEEBF")
    assert bs.status(bot(last_edit=ts(366)), NOW) == ("inaktiv", "FBDFC5")
    assert bs.status(bot(last_edit=None), NOW) == ("inaktiv", "C0E6FF")


def test_status_former_and_unflagged():
    assert bs.status(bot(flagged=False), NOW) == ("ehemalig", "E5C0C0")
    assert bs.status(bot(flagged=False, unflagged_bot=True), NOW) == ("aktiv (ohne Flag)", "DBF3EC")


def test_all_colors_differ():
    colors = [c for _, _, c, _ in bs.ACTIVITY] + [bs.NO_EDIT[1], bs.FORMER[1]]
    assert len(set(colors)) == len(colors)


# --- rows and page ---

def test_row_has_dark_text_color():
    row = bs.format_row(1, bot(), NOW)
    assert 'style="background:#DBF3EC; color:#202122"' in row


def test_row_formats():
    row = bs.format_row(3, bot("A B", editcount=1234567, registration=None,
                               first_edit=Timestamp(2009, 5, 6)), NOW)
    assert row.startswith("|-\n|3||[[Benutzer:A B|A B]]||")
    assert "||[[Spezial:Beiträge/A B|B]]||1.234.567||" in row
    assert row.endswith("||2009-05-06 *\n")


def test_row_last_edit_placeholders():
    assert "||0||-||" in bs.format_row(1, bot(editcount=0, last_edit=None), NOW)
    assert "||8||?||" in bs.format_row(1, bot(editcount=8, last_edit=None), NOW)
    assert bs.format_row(1, bot(registration=None), NOW).endswith("||?\n")


def test_sort_by_editcount_then_name():
    bots = [bot("B", 5), bot("C", 9), bot("A", 5)]
    assert [b.name for b in bs.sort_bots(bots)] == ["C", "A", "B"]


def test_page_splits_current_and_former():
    page = bs.build_page([bot("Old", 100, flagged=False), bot("New", 7),
                          bot("Beitragszahlen", 3, flagged=False, unflagged_bot=True)], NOW)
    current, former = page.split("== Ehemalige Bots ==")
    assert "[[Benutzer:New|New]]" in current and "[[Benutzer:Old|Old]]" not in current
    assert "aktiv (ohne Flag)" in current
    assert "|1||[[Benutzer:Old|Old]]" in former  # numbering starts again
    assert "Gesamtbearbeitungen durch diese Bots: 10\n" in current
    assert "Gesamtbearbeitungen aller aufgeführten Bots: 110" in former
    assert "Benutzterkonto" not in page
    for _, remark, color, text in bs.ACTIVITY:
        assert text in page
    assert page.endswith("[[Kategorie:Wikipedia:Bots]]")


# --- cache ---

def test_cache_roundtrip(tmp_path):
    path = tmp_path / "data" / "cache.json"
    cache = bs.BotCache(path)
    assert cache.names() == set() and cache.rights_log_until is None
    cache.revoked = {"B", "A"}
    cache.flagged = {"C"}
    cache.rights_log_until = "2026-11-18T04:00:00Z"
    cache.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["revoked"] == ["A", "B"]
    again = bs.BotCache(path)
    assert again.names() == {"A", "B", "C"}
    assert again.rights_log_until == "2026-11-18T04:00:00Z"
    assert not (tmp_path / "data" / "cache.json.tmp").exists()


class FakeEvent:
    def __init__(self, title, old, new, when, action="rights", hidden=False):
        self.data = {} if hidden else {"title": "Benutzer:" + title}
        self.oldgroups, self.newgroups = old, new
        self._action, self._when = action, when

    def action(self):
        return self._action

    def timestamp(self):
        return self._when

    def page(self):
        return SimpleNamespace(title=lambda with_ns=True: self.data["title"].split(":", 1)[1])


def test_revoked_bot_names():
    events = [
        FakeEvent("Removed", ["bot"], [], Timestamp(2026, 11, 17)),
        FakeEvent("Hidden", ["bot"], [], Timestamp(2026, 11, 16), hidden=True),
        FakeEvent("Added", [], ["bot"], Timestamp(2026, 11, 15)),
        FakeEvent("Auto", ["bot"], [], Timestamp(2026, 11, 14), action="autopromote"),
        FakeEvent("Other", ["bot", "sysop"], ["bot"], Timestamp(2026, 11, 13)),
    ]
    names, newest = bs.revoked_bot_names(events)
    assert names == {"Removed"}
    assert newest == "2026-11-17T00:00:00Z"
    assert bs.revoked_bot_names([]) == (set(), None)


class FakeSite:
    def __init__(self, events, group):
        self.events, self.group, self.calls = events, group, []

    def logevents(self, logtype, end=None):
        self.calls.append(end)
        return iter(self.events)

    def allusers(self, group):
        return ({"name": n} for n in self.group)


def make_updater(site, rebuild=False):
    updater = bs.BotStatsUpdater.__new__(bs.BotStatsUpdater)
    updater._site = site
    updater.opt = SimpleNamespace(rebuild=rebuild)
    return updater


def test_update_cache_incremental_keeps_expired_flags(tmp_path, monkeypatch):
    cache = bs.BotCache(tmp_path / "c.json")
    cache.rights_log_until = "2026-11-01T00:00:00Z"
    cache.revoked, cache.flagged = {"OldRevoked"}, {"Expired"}
    site = FakeSite([FakeEvent("NewRevoked", ["bot"], [], Timestamp(2026, 11, 10))], ["Current"])
    monkeypatch.setattr(bs.BotStatsUpdater, "site", property(lambda self: self._site))
    make_updater(site).update_cache(cache)
    assert site.calls == [Timestamp(2026, 11, 1)]  # only entries since the last run
    assert cache.revoked == {"OldRevoked", "NewRevoked"}
    assert cache.flagged == {"Expired", "Current"}
    assert cache.rights_log_until == "2026-11-10T00:00:00Z"


def test_update_cache_rebuild(tmp_path, monkeypatch):
    cache = bs.BotCache(tmp_path / "c.json")
    cache.rights_log_until = "2026-11-01T00:00:00Z"
    cache.revoked, cache.flagged = {"Stale"}, {"Expired"}
    site = FakeSite([], [])
    monkeypatch.setattr(bs.BotStatsUpdater, "site", property(lambda self: self._site))
    make_updater(site, rebuild=True).update_cache(cache)
    assert site.calls == [None]  # whole log
    assert cache.revoked == set()
    assert cache.flagged == {"Expired"}  # can not be rebuilt, stays
    assert cache.rights_log_until == "2026-11-01T00:00:00Z"

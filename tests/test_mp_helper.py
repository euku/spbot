"""Tests for mp-helper.py (rendering, edit summaries, API retries, error handling).

Nothing is fetched from the mp API or written to a wiki (FakeSite from conftest.py).

Run: pytest tests/test_mp_helper.py
"""
import datetime
import importlib.util
import os
import sys

os.environ.setdefault("PYWIKIBOT_NO_USER_CONFIG", "1")

import pytest  # noqa: E402
import pywikibot  # noqa: E402
import requests  # noqa: E402
from conftest import FakeSite  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "userscripts", "mp-helper.py")
spec = importlib.util.spec_from_file_location("mp_helper", SCRIPT)
mp = importlib.util.module_from_spec(spec)
sys.modules["mp_helper"] = mp
spec.loader.exec_module(mp)

NOW = datetime.datetime(2026, 11, 19, 12, 0, tzinfo=datetime.UTC)
BASE = "https://mp.example/api/v1"


def mentee(name, mentor="Mentor", status="ok", type_=2, start="2026-11-04T10:00:00"):
    return {"mentee": name, "mentor": mentor, "status": status, "type": type_, "start": start}


def archive(year=2026, month=11, mentorings=(), first_number=5):
    return {"year": year, "month": month, "first_number": first_number, "mentorings": list(mentorings)}


COUNTS = {"mentees_total": 1234, "active_mentors": 42}


class FakeResponse:
    def __init__(self, status=200, data=None, text=None):
        self.status_code = status
        self._data = data
        self.text = text if text is not None else str(data)

    def json(self):
        if self._data is None:
            raise requests.JSONDecodeError("Expecting value", self.text, 0)
        return self._data


class FakeSession:
    """Answers GET requests from a dict path -> list of responses (or exceptions), in order."""

    def __init__(self, answers):
        self.answers = {path: list(a) for path, a in answers.items()}
        self.calls = []

    def get(self, url, timeout):
        path = url[len(BASE) + 1:]
        self.calls.append((path, timeout))
        answer = self.answers[path].pop(0) if len(self.answers[path]) > 1 else self.answers[path][0]
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture(autouse=True)
def noSleep(monkeypatch):
    monkeypatch.setattr(mp.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(mp, "utcnow", lambda: NOW)


def okSession(mentees, archives=None, counts=COUNTS):
    archives = archives or {(2026, 11): archive()}
    answers = {"mentees": [FakeResponse(data=mentees)], "counts": [FakeResponse(data=counts)]}
    for (year, month), data in archives.items():
        answers[f"archive/{year}/{month}"] = [FakeResponse(data=data)]
    return FakeSession(answers)


# --- rendering ---

def test_render_list_counts_and_rows():
    text = mp.renderActiveMenteeList([
        mentee("A", status="ok"), mentee("B", status="long", type_=1),
        mentee("C", status="critical", type_=None), mentee("D", status="critical")])
    assert "'''4''' Mentees" in text
    assert "Davon haben 2 (50%) den Status rot" in text
    assert "und 1 (25%) den Status orange" in text
    assert "{{MP-NB|Eintritt=2026-11-4|Mentee=A|Mentor=Mentor|Status=grün|Typ=Wunschmentor}}" in text
    assert "|Mentee=B|Mentor=Mentor|Status=orange|Typ=Zufall}}" in text
    assert "|Mentee=C|Mentor=Mentor|Status=rot|Typ=nicht gesetzt}}" in text
    assert text.endswith("\n|}")


def test_render_list_unknown_status_does_not_crash():
    text = mp.renderActiveMenteeList([mentee("A", status="paused")])
    assert "|Status=grün|" in text


def test_render_archive():
    text = mp.renderArchiveMonth(archive(mentorings=[
        {"mentee": "A", "mentor": "M", "type": 1, "start": "2026-01-02", "stop": "2026-11-03"},
        {"mentee": "B", "mentor": "M", "type": None, "start": "2025-12-31", "stop": "2026-11-30"}]))
    assert "<h5>November 2026: (<span style='color:red'>2</span>)</h5>" in text
    assert '<ol start="5">' in text
    assert "<li>02.01.2026 / 03.11.2026: [N] [[Spezial:Beiträge/A|A]] ([[Benutzer:M|M]])</li>" in text
    assert "<li>31.12.2025 / 30.11.2026:  [[Spezial:Beiträge/B|B]]" in text


def test_render_empty_archive_starts_at_zero():
    assert '<ol start="0">' in mp.renderArchiveMonth(archive())


# --- edit summary ---

def test_change_summary():
    old = mp.renderActiveMenteeList([mentee("A"), mentee("B", mentor="X")])
    assert mp.changeSummary(old, [mentee("A"), mentee("C")]) == \
        "+[[:User:C|C]] ([[:User:Mentor|Mentor]]) -[[:User:B|B]] ([[:User:X|X]])"
    assert mp.changeSummary(old, [mentee("A"), mentee("B", mentor="X")]) == ""


def test_change_summary_is_shortened():
    many = [mentee(f"Neuling{i:03d}") for i in range(100)]
    summary = mp.changeSummary("", many)
    assert len(summary) <= mp.SUMMARY_MAX_LENGTH
    assert summary.startswith("+[[:User:Neuling000|Neuling000]]")
    shown = summary.count("[[:User:Neuling")
    assert summary.endswith(f" … und {100 - shown} weitere")


# --- archive months ---

@pytest.mark.parametrize("day, expected", [
    (1, [(2026, 10), (2026, 11)]),
    (3, [(2026, 10), (2026, 11)]),
    (4, [(2026, 11)]),
])
def test_archive_months(day, expected):
    assert mp.archiveMonths(datetime.date(2026, 11, day)) == expected


def test_archive_months_turn_of_year():
    assert mp.archiveMonths(datetime.date(2027, 1, 1)) == [(2026, 12), (2027, 1)]


# --- API ---

def test_api_retries_on_5xx_and_invalid_json():
    session = FakeSession({"counts": [FakeResponse(502, text="Bad Gateway"),
                                      FakeResponse(200, data=None, text="<html>"),
                                      FakeResponse(data=COUNTS)]})
    assert mp.api_get(session, BASE, "counts") == COUNTS
    assert len(session.calls) == 3


def test_api_no_retry_on_4xx():
    session = FakeSession({"counts": [FakeResponse(404, text="not found")]})
    with pytest.raises(mp.ApiError, match="HTTP 404"):
        mp.api_get(session, BASE, "counts")
    assert len(session.calls) == 1


def test_api_gives_up_after_retries():
    session = FakeSession({"counts": [requests.ConnectionError("refused")]})
    with pytest.raises(mp.ApiError, match="refused"):
        mp.api_get(session, BASE, "counts")
    assert len(session.calls) == 1 + len(mp.HTTP_RETRIES)


def test_api_timeouts():
    session = okSession([mentee("A")])
    mp.api_get(session, BASE, "mentees")
    mp.api_get(session, BASE, "counts")
    assert session.calls == [("mentees", 120), ("counts", mp.HTTP_TIMEOUT_DEFAULT)]


def test_api_respects_deadline():
    session = FakeSession({"counts": [requests.ConnectionError("refused")]})
    # enough time for the first attempt only
    deadline = NOW + datetime.timedelta(seconds=mp.HTTP_TIMEOUT_DEFAULT + 5)
    with pytest.raises(mp.ApiError, match="Zeitbudget"):
        mp.api_get(session, BASE, "counts", deadline)
    assert len(session.calls) == 1


# --- complete run ---

def test_run_writes_everything():
    site = FakeSite()
    assert mp.run(site, okSession([mentee("A")]), BASE, False, NOW)
    saved = site.saved()
    assert saved[mp.mentorenProgrammMenteeliste][0][1] == "Update +[[:User:A|A]] ([[:User:Mentor|Mentor]])"
    assert saved[mp.mentorenProgrammMenteeArchiv + "2026 November"][0][1] == "neues Archiv"
    assert saved[mp.anzahlAllerBetreutenMentees][0] == ("1234", "Anzahl bisheriger Mentees: 1234")
    assert saved[mp.anzahlAllerZurzeitBetreuendenMentoren][0][0] == "42"


def test_run_twice_changes_nothing():
    site = FakeSite()
    mp.run(site, okSession([mentee("A")]), BASE, False, NOW)
    site.saveLog.clear()
    assert mp.run(site, okSession([mentee("A")]), BASE, False, NOW)
    assert site.saveLog == []


def test_count_page_waits_23_hours():
    site = FakeSite()
    page = site.page(mp.anzahlAllerBetreutenMentees, "1000")
    page.latest_revision.timestamp = datetime.datetime(2026, 11, 19, 1, 0)  # 11 h ago
    assert mp.writeCount(site, page.title(), 1234, "%s", False, NOW)
    assert page.saves == []
    assert mp.writeCount(site, page.title(), 1234, "%s", True, NOW)
    assert page.saves == [("1234", "1234")]


def test_save_error_does_not_stop_the_run():
    site = FakeSite()
    listPage = site.page(mp.mentorenProgrammMenteeliste)
    listPage.saveError = pywikibot.exceptions.LockedPageError(listPage)
    assert not mp.run(site, okSession([mentee("A")]), BASE, False, NOW)
    assert listPage.saves == []
    assert mp.anzahlAllerBetreutenMentees in site.saved()


def test_api_error_fails_the_run():
    site = FakeSite()
    session = FakeSession({"mentees": [FakeResponse(503, text="down")]})
    assert not mp.run(site, session, BASE, False, NOW)
    assert site.saveLog == []


def test_empty_mentee_list_is_not_written():
    site = FakeSite()
    assert not mp.run(site, okSession([]), BASE, False, NOW)
    assert mp.mentorenProgrammMenteeliste not in site.saved()


# --- failure counter ---

def test_failure_counter(tmp_path):
    path = str(tmp_path / ".mp-helper-failures")
    codes = [mp.recordRun(False, path) for _ in range(mp.FAILURE_MAIL_AFTER + mp.FAILURE_MAIL_EVERY)]
    assert codes.count(1) == 2
    assert codes[mp.FAILURE_MAIL_AFTER - 1] == 1
    assert codes[-1] == 1
    assert mp.recordRun(True, path) == 0
    assert not os.path.exists(path)
    assert mp.recordRun(False, path) == 0
    assert mp.readFailures(path) == 1


@pytest.mark.parametrize("arg", ["-dryrun", "--dry-run", "-x"])
def test_unknown_argument_does_nothing(monkeypatch, arg):
    monkeypatch.setattr(pywikibot, "handle_args", lambda: [arg])
    monkeypatch.setattr(pywikibot, "Site", None)   # would fail
    assert mp.main() == 2

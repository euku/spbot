"""Tests for skipping unchanged pages where nothing is due (archive_resolved/state.py)."""
import gzip
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from archive_resolved import bot as botModule
from archive_resolved import core
from archive_resolved import state as stateModule
from archive_resolved import summary as summaryModule
from archive_resolved.state import DUE_BUFFER, REREAD_DAYS, RunState, codeFiles, codeVersion, rereadWeek
from archive_resolved.summary import RunSummary, formatTime
from archive_resolved_localization.local_bot_factory import LocalBotFactory
from conftest import NOW, USERSCRIPTS, FakeRevision, makeBot, makeDoc
from test_archive_execute import OPEN, PAGE
from test_archive_fixtures import CASES, parseTime, setUp

UTC = timezone.utc
NOW_UTC = NOW.replace(tzinfo=UTC)
LEMMA = "|Ziel='((Lemma))/Archiv/((Jahr))'"


def examined(options, text, now=NOW, bot=None):
    doc = makeDoc("{{Autoarchiv-Erledigt|" + options + LEMMA + "}}\n" + text, bot=bot, now=now)
    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    doc.prepareArchiving()
    return doc


RESOLVED = "== A ==\nFrage --A 10:00, 1. Nov. 2026 (CET)\n{{Erledigt|1=--A 13:00, 15. Nov. 2026 (CET)}}\n"


# ---------------------------------------------------------------- nextDue

def test_next_due_resolved():
    # 13:00 CET = 12:00 UTC
    assert examined("Alter=3", RESOLVED).nextDue() == datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def test_next_due_time_compare_resolved_uses_resolved_time_too():
    assert examined("Alter=3|Zeitvergleich=erledigt", RESOLVED).nextDue() == datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def test_next_due_timeout_counts_from_newest_signature():
    text = "== A ==\nFrage --A 10:00, 1. Nov. 2026 (CET)\nAntwort --B 11:00, 10. Nov. 2026 (CET)\n"
    assert examined("Alter=3|Zeitbeschränkung=30", text).nextDue() == datetime(2026, 12, 10, 10, 0, tzinfo=UTC)


def test_next_due_is_the_earliest_of_all_sections_and_rules():
    text = RESOLVED + "== B ==\nFrage --A 13:00, 12. Nov. 2026 (CET)\n"
    assert examined("Alter=3|Zeitbeschränkung=5", text).nextDue() == datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("minutes", [0, 3])
def test_next_due_resolved_just_before_the_run(minutes):
    """An age of (nearly) 0 is not "not resolved", although the summary shows it like that (rounded)."""
    now = datetime(2026, 11, 15, 12, minutes)
    doc = examined("Alter=1", RESOLVED, now=now)
    assert not doc.hasWorkToDo()
    assert doc.nextDue() == datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("options, text", [
    ("Alter=3", ""),                                                             # no sections
    ("Alter=3", OPEN),                                                           # not resolved
    ("Alter=3|Zeitbeschränkung=30", "== A ==\nohne Signatur\n"),
    ("Alter=3", RESOLVED.replace("Frage", "{{Nicht archivieren}} Frage")),
    ("Alter=99999999999", RESOLVED),                                             # out of range for a date
    ("Alter=inf", RESOLVED),
])
def test_next_due_never(options, text):
    doc = examined(options, text)
    assert not doc.hasWorkToDo()
    assert doc.nextDue() is None


def assertMatchesExamination(text, title, bot, start, days):
    """Examines the page at many times: nothing gets archived before nextDue - DUE_BUFFER, something does after it."""
    def at(now):
        doc = makeDoc(text, bot=bot, title=title, now=now)
        doc.findOptions()
        doc.divideIntoSlices()
        doc.examineDiscussions()
        return doc, any(d.shouldBeArchived(doc.thresholdAgeResolvedTemplate, doc.thresholdAgeByTimeout)
                        for d in doc.listDiscussions)
    doc, due = at(start)
    if due:
        return False
    nextDue = doc.nextDue()
    if nextDue is None:
        assert not any(at(start + timedelta(days=d))[1] for d in range(0, days, 7))
        return True
    nextDue = nextDue.replace(tzinfo=None)
    for before in (timedelta(0), timedelta(minutes=1), timedelta(hours=1), timedelta(days=1)):
        time = nextDue - DUE_BUFFER - before
        if time >= start:
            assert not at(time)[1], f"due too early: {time}, nextDue {nextDue}"
    assert at(nextDue + DUE_BUFFER)[1], f"not due at {nextDue}"
    return True


@pytest.mark.parametrize("start", [datetime(2026, 3, 27, 12), datetime(2026, 10, 23, 12), NOW])
@pytest.mark.parametrize("options", ["Alter=0", "Alter=3", "Alter=7.5|Zeitbeschränkung=14", "Alter=30|Zeitbeschränkung=1"])
def test_next_due_matches_the_examination(start, options):
    """Also at the change between summer and winter time (29 March and 25 October 2026)."""
    for hours in range(1, 24 * 4, 5):
        stamp = (start - timedelta(hours=hours)).strftime("%H:%M, %-d. ") \
            + ["Jan.", "Feb.", "Mär.", "Apr.", "Mai", "Jun.", "Jul.", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."][
                (start - timedelta(hours=hours)).month - 1] + " 2026 (CET)"
        for body in (f"Frage --A {stamp}\n", f"Frage --A {stamp}\n{{{{Erledigt|1=--A {stamp}}}}}\n"):
            text = "{{Autoarchiv-Erledigt|" + options + LEMMA + "}}\n== A ==\n" + body
            assertMatchesExamination(text, "Benutzer Diskussion:Test", makeBot(), start, 60)


@pytest.mark.parametrize("case", CASES, ids=[c["file"][:-5] for c in CASES])
def test_next_due_matches_the_examination_of_real_pages(case):
    bot, _, doc = setUp(case)
    try:
        doc.findOptions()
    except core.OptionsError:
        return
    checked = [assertMatchesExamination(doc.originalText, case["title"], bot,
                                        parseTime(case["now"]) - timedelta(days=days), 100)
               for days in (0, 1, 2, 3, 5, 8, 13, 21, 34, 100, 3000)]
    assert any(checked)


# ---------------------------------------------------------------- the state file and the run

TITLE = "Benutzer Diskussion:Test"
OTHER = "Benutzer Diskussion:Zwei"
NOTHING = "{{Autoarchiv-Erledigt|Alter=3" + LEMMA + "}}\n" + OPEN


class Clock:
    """Replaces datetime in the modules of the bot."""
    def __init__(self, time):
        self.time = time

    def now(self, tz=None):
        return self.time if tz else self.time.replace(tzinfo=None)

    def __getattr__(self, name):
        return getattr(datetime, name)

    def __call__(self, *args, **kwargs):
        return datetime(*args, **kwargs)


@pytest.fixture
def clock(monkeypatch):
    clock = Clock(NOW_UTC)
    for module in (core, stateModule, summaryModule):
        monkeypatch.setattr(module, "datetime", clock)
    return clock


class Wiki:
    """Full runs on a FakeSite; read: the titles that were preloaded in the last run."""
    def __init__(self, logDir, monkeypatch):
        self.logDir = logDir
        self.bot = makeBot()
        self.titles = []
        self.read = []
        monkeypatch.setattr(botModule.pagegenerators, "PreloadingGenerator", self._preload)

    def _preload(self, pages, groupsize):
        for page in pages:
            self.read.append(page.title())
            yield page

    def page(self, title, text):
        if title not in self.titles:
            self.titles.append(title)
        page = self.bot.site.page(title, text)
        page.latest_revision = FakeRevision("Somebody", NOW)
        return page

    def run(self, full=False, code="v1"):
        self.read = []
        r = object.__new__(botModule.ArchiveRobot)
        r.dryRun, r.localBot, r.site = False, self.bot.localBot, self.bot.site
        r.saveLocalLogFile, r.localLogFile = False, None
        r.state = RunState() if full else r._loadState(str(self.logDir), "dewikipedia", code)
        r.summary = RunSummary(str(self.logDir / "archive-resolved-dewikipedia.jsonl"), "dewikipedia", False, code=code)
        r.generator = [self.bot.site.page(t) for t in self.titles]
        r.run()
        return self.records()

    def records(self):
        """The records of the last run: (run, {title: page record}, end)"""
        with open(self.logDir / "archive-resolved-dewikipedia.jsonl", encoding="utf-8") as f:
            records = []
            for line in f:
                try:
                    records.append(json.loads(line))
                except ValueError:
                    pass
            records = [r for r in records if isinstance(r, dict)]
        start = max(i for i, r in enumerate(records) if r["type"] == "run")
        return records[start], {r["title"]: r for r in records[start:] if r["type"] == "page"}, records[-1]


@pytest.fixture
def wiki(tmp_path, monkeypatch, clock):
    """The weeks of all pages begin on the day of NOW, so the weekly reading does not interfere for 7 days."""
    monkeypatch.setattr(stateModule, "rereadWeek", lambda title, time: (time.date() - NOW.date()).days // REREAD_DAYS)
    return Wiki(tmp_path, monkeypatch)


@pytest.fixture
def spreadWiki(tmp_path, monkeypatch, clock):
    """With the real rereadWeek()."""
    return Wiki(tmp_path, monkeypatch)


def test_unchanged_page_is_not_read_again(wiki, clock):
    wiki.page(TITLE, NOTHING)
    _, pages, end = wiki.run()
    assert wiki.read == [TITLE] and end["unchanged"] == 0
    assert "unchanged" not in pages[TITLE] and pages[TITLE]["nextDue"] is None
    first = pages[TITLE]
    clock.time += timedelta(days=1)
    run, pages, end = wiki.run()
    assert wiki.read == []
    assert run["code"] == "v1"
    assert end["pages"] == 1 and end["unchanged"] == 1 and end["byStatus"] == {"nothing": 1} and end["complete"] is True
    record = pages[TITLE]
    assert record["unchanged"] is True and record["checked"] == first["checked"] == "2026-11-16T12:00:00Z"
    assert record["time"] == "2026-11-17T12:00:00Z"
    assert list(record)[:2] == ["type", "title"]   # the status page looks for this
    assert record["sections"][0]["firstAge"] == round(first["sections"][0]["firstAge"] + 1, 2)
    assert record["options"] == first["options"]
    # and once more from the record that was carried over
    clock.time += timedelta(days=1)
    _, pages, _ = wiki.run()
    assert wiki.read == [] and pages[TITLE]["sections"][0]["firstAge"] == round(first["sections"][0]["firstAge"] + 2, 2)


def test_edited_page_is_read_again(wiki, clock):
    wiki.page(TITLE, NOTHING)
    wiki.page(OTHER, NOTHING)
    wiki.run()
    wiki.page(OTHER, NOTHING + "\nneu")
    _, pages, end = wiki.run()
    assert wiki.read == [OTHER]
    assert set(pages) == {TITLE, OTHER} and end["pages"] == 2 and end["unchanged"] == 1


def test_due_page_is_read_and_archived(wiki, clock):
    wiki.page(TITLE, "{{Autoarchiv-Erledigt|Alter=3" + LEMMA + "}}\n" + RESOLVED)   # due on 18 November, 12:00 UTC
    wiki.run()
    clock.time = datetime(2026, 11, 18, 9, 59, tzinfo=UTC)
    assert wiki.run()[1][TITLE]["nextDue"] == "2026-11-18T12:00:00Z" and wiki.read == []
    clock.time = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)    # DUE_BUFFER
    assert wiki.run()[1][TITLE]["status"] == "nothing" and wiki.read == [TITLE]
    clock.time = datetime(2026, 11, 18, 12, 1, tzinfo=UTC)
    assert wiki.run()[1][TITLE]["status"] == "archived" and wiki.read == [TITLE]
    # an archived page is read again, its state is not known
    assert wiki.run()[1][TITLE]["status"] == "nothing" and wiki.read == [TITLE]
    wiki.run()
    assert wiki.read == []


def test_errors_and_skipped_pages_are_always_read(wiki):
    wiki.page(TITLE, "{{Autoarchiv-Erledigt|Alter=abc" + LEMMA + "}}\n")
    wiki.page(OTHER, PAGE).protected = True
    for _ in range(2):
        _, pages, _ = wiki.run()
        assert wiki.read == [TITLE, OTHER]
        assert pages[TITLE]["status"] == "optionserror" and pages[OTHER]["status"] == "skipped"
        assert "revid" not in pages[TITLE] and "revid" not in pages[OTHER]


def test_full_run_and_other_code_read_everything(wiki):
    wiki.page(TITLE, NOTHING)
    wiki.run()
    wiki.run(full=True)
    assert wiki.read == [TITLE]
    wiki.run(code="v2")
    assert wiki.read == [TITLE]
    wiki.run(code="v2")
    assert wiki.read == []


def test_every_page_is_read_once_a_week(spreadWiki, clock):
    """Each day a part of the pages, each page every 7 days (after the first time)."""
    titles = [f"Diskussion:Seite {i}" for i in range(70)]
    for title in titles:
        spreadWiki.page(title, NOTHING)
    spreadWiki.run()
    assert spreadWiki.read == titles
    days = {title: [] for title in titles}
    perDay = []
    for day in range(1, 22):
        clock.time += timedelta(days=1)
        _, pages, end = spreadWiki.run()
        assert set(pages) == set(titles) and end["unchanged"] == len(titles) - len(spreadWiki.read)
        perDay.append(len(spreadWiki.read))
        for title in spreadWiki.read:
            days[title].append(day)
    assert all(1 <= d[0] <= 7 and d == [d[0], d[0] + 7, d[0] + 14] for d in days.values())
    assert all(0 < n < 25 for n in perDay)


def test_reread_time_of_day_and_missed_runs(spreadWiki, clock):
    """A run that starts a bit earlier or later than the last one does not shift the day; missed runs are made up."""
    spreadWiki.page(TITLE, NOTHING)
    spreadWiki.run()
    first = next(d for d in range(1, 8) if rereadWeek(TITLE, NOW_UTC + timedelta(days=d)) != rereadWeek(TITLE, NOW_UTC))
    for day in range(1, first):
        clock.time = NOW_UTC + timedelta(days=day, minutes=7 * (-1) ** day)
        spreadWiki.run()
        assert spreadWiki.read == []
    clock.time = NOW_UTC + timedelta(days=first, minutes=-9)
    spreadWiki.run()
    assert spreadWiki.read == [TITLE]
    clock.time = NOW_UTC + timedelta(days=first, hours=3)      # same day
    spreadWiki.run()
    assert spreadWiki.read == []
    clock.time = NOW_UTC + timedelta(days=first + 8)           # the day of the week was missed
    spreadWiki.run()
    assert spreadWiki.read == [TITLE]


def test_reread_week_spreads_the_pages_evenly():
    days = Counter()
    for i in range(7000):
        title = f"Diskussion:Seite {i}"
        changes = [d for d in range(1, REREAD_DAYS + 1)
                   if rereadWeek(title, NOW_UTC + timedelta(days=d)) != rereadWeek(title, NOW_UTC + timedelta(days=d - 1))]
        assert len(changes) == 1
        days[changes[0]] += 1
    assert set(days) == set(range(1, REREAD_DAYS + 1))
    assert all(850 < n < 1150 for n in days.values())


def test_reread_week_is_the_same_in_every_process():
    assert [rereadWeek(t, datetime(2026, 11, 16, 12, tzinfo=UTC)) for t in (TITLE, OTHER, "토론:가")] == [105705, 105705, 105705]


def test_state_from_the_day_directories(wiki, clock):
    wiki.page(TITLE, NOTHING)
    wiki.run()
    path = wiki.logDir / "archive-resolved-dewikipedia.jsonl"
    day = wiki.logDir / "2026-11-16"
    day.mkdir()
    path.rename(day / path.name)
    clock.time += timedelta(days=1)
    wiki.run()
    assert wiki.read == []
    path.unlink()
    with open(day / path.name, "rb") as f:
        (day / (path.name + ".gz")).write_bytes(gzip.compress(f.read()))
    (day / path.name).unlink()
    wiki.run()
    assert wiki.read == []


def test_broken_state_means_reading_everything(wiki):
    wiki.page(TITLE, NOTHING)
    wiki.run()
    path = wiki.logDir / "archive-resolved-dewikipedia.jsonl"
    lines = path.read_text(encoding="utf-8").replace('"nextDue":null', '"nextDue":"kaputt"')
    path.write_text(lines + '[1]\n{"type":"page","tit', encoding="utf-8")
    _, pages, end = wiki.run()
    assert wiki.read == [TITLE] and end["complete"] is True


def test_page_without_known_revision_is_read():
    line = json.dumps({"revid": 5, "nextDue": None, "checked": formatTime(NOW_UTC), "time": formatTime(NOW_UTC)})
    state = RunState({TITLE: line.encode()})
    assert state.unchanged(TITLE, 5, NOW_UTC) is not None
    assert state.unchanged(TITLE, None, NOW_UTC) is None
    assert state.unchanged(TITLE, 6, NOW_UTC) is None
    assert state.unchanged(OTHER, 5, NOW_UTC) is None
    assert state.unchanged(TITLE, 5, NOW_UTC + timedelta(days=REREAD_DAYS)) is None
    assert state.unchanged(TITLE, 5, NOW_UTC - timedelta(minutes=1)) is None   # clock went back


# ---------------------------------------------------------------- code version

PROJECTS = ["dewikipedia", "cswikipedia", "enwikisource", "itwikipedia", "jawikipedia", "kowikipedia", "viwikipedia",
            "simplewikipedia", "commons", "meta", "incubator"]


def localBot(project):
    return LocalBotFactory().createLocalBot(project)


@pytest.fixture
def sources(tmp_path):
    """A copy of the bot code that can be changed."""
    for directory in ("archive_resolved", "archive_resolved_localization"):
        shutil.copytree(os.path.join(USERSCRIPTS, directory), tmp_path / directory,
                        ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def changedProjects(sources, path):
    """The projects whose code version changes with the file."""
    before = {p: codeVersion(localBot(p), str(sources)) for p in PROJECTS}
    with open(sources / path, "a", encoding="utf-8") as f:
        f.write("\n")
    return [p for p in PROJECTS if codeVersion(localBot(p), str(sources)) != before[p]]


def test_code_version_is_stable(sources):
    for project in PROJECTS:
        version = codeVersion(localBot(project))
        assert version == codeVersion(localBot(project)) == codeVersion(localBot(project), str(sources))
        assert len(version) == 16


@pytest.mark.parametrize("name", ["core", "bot", "state", "summary"])
def test_code_version_of_all_projects_depends_on_the_bot(sources, name):
    assert changedProjects(sources, f"archive_resolved/{name}.py") == PROJECTS


def test_code_version_of_all_projects_depends_on_the_common_localization(sources):
    assert changedProjects(sources, "archive_resolved_localization/local_bot.py") == PROJECTS


@pytest.mark.parametrize("name, projects", [
    ("de", ["dewikipedia"]),
    ("ko", ["kowikipedia"]),
    ("vi", ["viwikipedia"]),
    ("meta", ["meta"]),
    ("incubator", ["incubator"]),
])
def test_code_version_depends_on_the_own_language_only(sources, name, projects):
    assert changedProjects(sources, f"archive_resolved_localization/{name}.py") == projects


def test_code_version_depends_on_the_inherited_language(sources):
    changed = changedProjects(sources, "archive_resolved_localization/en.py")
    assert {"enwikisource", "simplewikipedia", "commons", "meta", "incubator"} <= set(changed)
    assert not {"dewikipedia", "jawikipedia", "kowikipedia", "viwikipedia", "itwikipedia"} & set(changed)


@pytest.mark.parametrize("name", ["messages.json", "messages.py", "local_bot_factory.py"])
def test_code_version_does_not_depend_on_texts(sources, name):
    assert changedProjects(sources, f"archive_resolved_localization/{name}") == []


def test_code_version_depends_on_the_class():
    """The factory is not part of the version, but the class it chooses."""
    versions = {p: codeVersion(localBot(p)) for p in PROJECTS}
    assert versions["commons"] == versions["enwikisource"] == versions["simplewikipedia"]
    assert len({versions[p] for p in ("commons", "meta", "incubator", "dewikipedia", "kowikipedia")}) == 5


@pytest.mark.parametrize("project", PROJECTS)
def test_code_files_contain_the_whole_class(project):
    """Every class the LocalBot inherits from is in a file of the version."""
    names = {os.path.basename(p) for p in codeFiles(localBot(project))}
    for cls in type(localBot(project)).__mro__[:-1]:
        assert cls.__module__.split(".")[-1] + ".py" in names

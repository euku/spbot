"""Tests for writing archive and talk pages (executeArchiving) and ArchiveRobot, against a FakeSite."""
import pytest
import pywikibot

from archive_resolved import bot as botModule
from archive_resolved import core
from conftest import NOW, FakeRevision, makeBot, makeDoc

ORIGIN = "Benutzer Diskussion:Test"
ARCHIVE = "Benutzer Diskussion:Test/Archiv/2026"
OPTIONS = "{{Autoarchiv-Erledigt|Alter=3|Ziel='((Lemma))/Archiv/((Jahr))'}}\n"
OLD = ("== Alt ==\nFrage --A 10:00, 1. Nov. 2026 (CET)\n"
       "{{Erledigt|1=--A 12:00, 5. Nov. 2026 (CET)}}\n")
OLD_ARCHIVED = ("== Alt ==\nFrage --A 10:00, 1. Nov. 2026 (CET)\n"
                ":<small>Archivierung dieses Abschnittes wurde gewünscht von: --A 12:00, 5. Nov. 2026 (CET)</small>\n")
OPEN = "== Offen ==\nFrage --A 10:00, 15. Nov. 2026 (CET)\n"
PAGE = OPTIONS + OLD + OPEN


def run(bot, text=PAGE, title=ORIGIN):
    """Like ArchiveRobot._runOnPage for one page, returns the WikiDocument."""
    bot.site.page(title, text)
    doc = prepare(bot, text, title)
    if doc.hasWorkToDo():
        doc.executeArchiving()
    return doc


def prepare(bot, text, title=ORIGIN):
    """The document of the current revision of the page, up to executeArchiving()."""
    doc = makeDoc(text, bot=bot, title=title)
    doc.revid = bot.site.page(title).latest_revision.revid
    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    doc.prepareArchiving()
    return doc


def editByOther(page, text):
    page.text = text
    page.latest_revision = FakeRevision("Other", NOW)


def test_archive_new_page():
    bot = makeBot()
    run(bot)
    saved = bot.site.saved()
    assert set(saved) == {ARCHIVE, ORIGIN}
    [(archiveText, archiveSummary)] = saved[ARCHIVE]
    assert archiveText == "{{Archiv}}\n\n" + OLD_ARCHIVED
    assert archiveSummary == (f"Archiviere 1 Abschnitt von [[{ORIGIN}]]"
                              f" (ab Abschnitt [[{ARCHIVE}#Alt|Alt]])")
    [(originText, originSummary)] = saved[ORIGIN]
    assert originText == OPTIONS + OPEN
    assert originSummary.startswith(f"Archiviere 1 Abschnitt: 1 nach [[{ARCHIVE}]] (ab Abschnitt [[{ARCHIVE}#Alt|Alt]])")
    assert " - letzte Bearbeitung: [[:User:Somebody|Somebody]], 2026-11-15 " in originSummary


def test_archive_appends_to_existing_page():
    bot = makeBot()
    bot.site.page(ARCHIVE, "{{Archiv}}\n\n== Früher ==\nalt")
    run(bot)
    assert bot.site.page(ARCHIVE).text == "{{Archiv}}\n\n== Früher ==\nalt\n\n" + OLD_ARCHIVED


def test_nothing_to_do():
    bot = makeBot()
    run(bot, OPTIONS + OPEN)
    assert bot.site.saved() == {}


def test_dry_run_saves_nothing():
    bot = makeBot(dryRun=True)
    doc = run(bot)
    assert bot.site.saved() == {}
    assert doc.modifiedText == OPTIONS + OPEN


def test_origin_protected():
    bot = makeBot()
    bot.site.page(ORIGIN, PAGE).protected = True
    run(bot)
    assert bot.site.saved() == {}


def test_archive_protected():
    bot = makeBot()
    bot.site.page(ARCHIVE).protected = True
    run(bot)
    assert bot.site.saved() == {}


def test_archive_in_main_namespace_is_refused():
    bot = makeBot()
    run(bot, PAGE.replace("((Lemma))/Archiv/((Jahr))", "Archiv ((Jahr))"))
    assert bot.site.saved() == {}


def test_archive_redirect_to_subpage_is_followed():
    bot = makeBot()
    moved = ORIGIN + "/Archiv/2026 neu"
    bot.site.page(ARCHIVE, "#WEITERLEITUNG [[x]]").redirectTo = moved
    bot.site.page(moved, "{{Archiv}}")
    run(bot)
    saved = bot.site.saved()
    assert set(saved) == {moved, ORIGIN}
    assert saved[moved][0][0] == "{{Archiv}}\n\n" + OLD_ARCHIVED
    assert bot.site.page(ARCHIVE).text == "#WEITERLEITUNG [[x]]"


def test_archive_redirect_summaries_name_the_real_page():
    """ElBe: Archiv/2025 redirects to Archiv/2026; both targets are merged into one save."""
    bot = makeBot()
    options = "{{Autoarchiv-Erledigt|Alter=3|Ziel='((Lemma))/Archiv/((Jahr))'}}\n"
    old2025 = ("== Älter ==\nFrage --A 10:00, 1. Nov. 2025 (CET)\n"
               "{{Erledigt|1=--A 12:00, 5. Nov. 2026 (CET)}}\n")
    moved = ORIGIN + "/Archiv/2026"
    bot.site.page(ORIGIN + "/Archiv/2025", "#WEITERLEITUNG [[x]]").redirectTo = moved
    bot.site.page(moved, "{{Archiv}}")
    run(bot, options + old2025 + OLD + OPEN)
    saved = bot.site.saved()
    assert set(saved) == {moved, ORIGIN}
    [(archiveText, archiveSummary)] = saved[moved]
    assert archiveSummary == f"Archiviere 2 Abschnitte von [[{ORIGIN}]] (ab Abschnitt [[{moved}#Älter|Älter]])"
    assert archiveText.startswith("{{Archiv}}\n\n== Älter ==") and "== Alt ==" in archiveText
    [(originText, originSummary)] = saved[ORIGIN]
    assert originText == options + OPEN
    assert originSummary.startswith(f"Archiviere 2 Abschnitte: 2 nach [[{moved}]] (ab Abschnitt [[{moved}#Älter|Älter]])")
    assert "/Archiv/2025" not in originSummary


@pytest.mark.parametrize("title, target", [
    # Lars2019: the template was archived, the archive page archived into a subpage of itself
    (ORIGIN + "/Archiv/2026/11", "((Lemma))/Archiv/((Jahr))/((Monat:##))"),
    (ORIGIN + "/Archiv/2026/11/Archiv/2026/11", "((Lemma))/Archiv/((Jahr))/((Monat:##))"),
    (ORIGIN + "/Archiv/2025/12", "((Lemma))/Archiv/((Jahr))/((Monat:##))"),
    (ORIGIN + "/Archiv/2026/November", "((Lemma))/Archiv/((Jahr))/((Monat:Lang))"),
    (ORIGIN + "/Archiv/2025/Dezember", "((Lemma))/Archiv/((Jahr))/((Monat:Lang))"),
    (ORIGIN + "/2025/Mrz", "((Lemma))/((Jahr))/((Monat:Kurz))"),
    (ORIGIN + "/Archiv/2026/IV", "((Lemma))/Archiv/((Jahr))/((Quartal:I))"),
    (ORIGIN + "/Archiv/2026", "Benutzer Diskussion:Test/Archiv/((Jahr))"),  # into itself
])
def test_archive_page_does_not_archive_into_itself(title, target):
    bot = makeBot()
    run(bot, "{{Autoarchiv-Erledigt|Alter=3|Ziel='%s'}}\n" % target + OLD + OPEN, title=title)
    assert bot.site.saved() == {}


@pytest.mark.parametrize("title, target, archive", [
    (ORIGIN, "((Lemma))/Archiv/((Jahr))/((Monat:##))", "/Archiv/2026/11"),
    ("Benutzer Diskussion:Archiv/2026/11", "((Lemma))/Archiv/((Jahr))/((Monat:##))", "/Archiv/2026/11"),
    # commons, MediaWiki talk:Gadget-AjaxQuickDelete.js/auto-errors
    ("Benutzer Diskussion:Test/auto-errors", "((Lemma))/((Jahr))-((Monat:##))", "/2026-11"),
    # subpages that only look a bit like a variable value
    ("Benutzer Diskussion:Test/Baustelle2", "((Lemma))/((Jahr))", "/2026"),
    ("Benutzer Diskussion:Test/2024 election", "((Lemma))/((Jahr))", "/2026"),
    ("Benutzer Diskussion:Test/vi", "((Lemma))/((Jahr))", "/2026"),
    ("Benutzer Diskussion:Test/Mai-Treffen", "((Lemma))/((Monat:Lang))", "/November"),
])
def test_normal_pages_are_not_mistaken_for_archives(title, target, archive):
    bot = makeBot()
    run(bot, "{{Autoarchiv-Erledigt|Alter=3|Ziel='%s'}}\n" % target + OLD + OPEN, title=title)
    assert set(bot.site.saved()) == {title, title + archive}


def test_archive_target_with_invalid_title_is_reported():
    """e.g. a title over 255 bytes; pywikibot raises InvalidTitleError when the page is used."""
    bot = makeBot()

    def invalid():
        raise pywikibot.exceptions.InvalidTitleError("too long")
    bot.site.page(ARCHIVE).isRedirectPage = invalid
    with pytest.raises(core.WrongOptions):
        run(bot)
    assert bot.site.saved() == {}


def test_archive_redirect_outside_origin_is_not_followed():
    bot = makeBot()
    bot.site.page(ARCHIVE, "#WEITERLEITUNG [[x]]").redirectTo = "Benutzer Diskussion:Anderer/Archiv"
    bot.site.page("Benutzer Diskussion:Anderer/Archiv", "{{Archiv}}")
    run(bot)
    assert bot.site.saved() == {}


@pytest.mark.parametrize("error", [pywikibot.exceptions.EditConflictError, pywikibot.exceptions.LockedPageError])
def test_archive_save_error_keeps_origin(error):
    bot = makeBot()
    bot.site.page(ARCHIVE).saveError = error(bot.site.page(ARCHIVE))
    run(bot)
    assert bot.site.saved() == {}
    assert bot.site.page(ORIGIN).text == PAGE


def test_unexpected_archive_error_keeps_origin_and_raises():
    """Regression test for 5b88c01: don't clear the origin page if the archive was not saved."""
    bot = makeBot()
    bot.site.page(ARCHIVE).saveError = TimeoutError("timeout")
    with pytest.raises(TimeoutError):
        run(bot)
    assert bot.site.page(ORIGIN).text == PAGE
    assert bot.site.saved() == {}


def test_unexpected_archive_error_but_saved_after_all():
    """The save went through on the server although the client got an error: go on with the origin page."""
    bot = makeBot()
    bot.site.page(ARCHIVE).saveError = TimeoutError("timeout")
    bot.site.page(ARCHIVE).saveErrorAfterWrite = True
    run(bot)
    assert bot.site.page(ARCHIVE).text == "{{Archiv}}\n\n" + OLD_ARCHIVED
    assert bot.site.page(ORIGIN).text == OPTIONS + OPEN


def test_edit_since_reading_is_not_overwritten():
    bot = makeBot()
    page = bot.site.page(ORIGIN, PAGE)
    doc = prepare(bot, PAGE)
    editByOther(page, PAGE + "neuer Beitrag\n")
    doc.executeArchiving()
    assert bot.site.saved() == {}   # neither the archive nor the page itself
    assert page.text == PAGE + "neuer Beitrag\n"
    assert (doc.outcome, doc.outcomeKey) == ('skipped', 'skip.origin_changed')


def test_edit_while_saving_the_archive_is_not_overwritten():
    bot = makeBot()
    page = bot.site.page(ORIGIN, PAGE)
    doc = prepare(bot, PAGE)
    archive = bot.site.page(ARCHIVE)
    store = archive._store

    def storeAndEdit(text, summary):
        store(text, summary)
        editByOther(page, PAGE + "neuer Beitrag\n")
    archive._store = storeAndEdit
    doc.executeArchiving()
    assert set(bot.site.saved()) == {ARCHIVE}
    assert page.text == PAGE + "neuer Beitrag\n"
    assert (doc.outcome, doc.outcomeKey) == ('skipped', 'skip.origin_conflict')


def test_deleted_page_is_not_recreated():
    bot = makeBot()
    page = bot.site.page(ORIGIN, PAGE)
    doc = prepare(bot, PAGE)
    page._exists = False
    doc.executeArchiving()
    assert bot.site.saved() == {}
    assert doc.outcomeKey == 'skip.origin_changed'


@pytest.mark.parametrize("error", [pywikibot.exceptions.EditConflictError, pywikibot.exceptions.NoCreateError])
def test_conflict_reported_by_the_server(error):
    bot = makeBot()
    page = bot.site.page(ORIGIN, PAGE)
    doc = prepare(bot, PAGE)
    page.saveError = error(page)
    doc.executeArchiving()
    assert (doc.outcome, doc.outcomeKey) == ('skipped', 'skip.origin_conflict')


# two old sections that go to two archive pages (the first one to ARCHIVE/Nov)
TWO_TARGETS = OPTIONS.replace("((Jahr))", "((Jahr))/((Monat:Kurz))") + OLD + (
    "== Okt ==\nq --A 10:00, 1. Okt. 2026 (CEST)\n{{Erledigt|1=--A 10:00, 2. Okt. 2026 (CEST)}}\n") + OPEN
NOV, OKT = ARCHIVE + "/Nov", ARCHIVE + "/Okt"


@pytest.mark.parametrize("error", [TimeoutError("x"), "conflict", "locked"])
def test_failing_second_archive_makes_no_copies(error):
    bot = makeBot()
    okt = bot.site.page(OKT)
    okt.saveError = {"conflict": pywikibot.exceptions.EditConflictError(okt),
                     "locked": pywikibot.exceptions.LockedPageError(okt)}.get(error, error)
    for _ in range(3):
        try:
            run(bot, TWO_TARGETS)
        except TimeoutError:
            pass
        assert bot.site.page(ORIGIN).text == TWO_TARGETS
    assert len(bot.site.page(NOV).saves) == 1
    assert bot.site.page(NOV).text.count("== Alt ==") == 1
    # the next run without the error finishes the job
    okt.saveError = None
    doc = run(bot, TWO_TARGETS)
    assert doc.outcome == 'archived'
    assert len(bot.site.page(NOV).saves) == 1
    assert bot.site.page(OKT).text.count("== Okt ==") == 1
    assert bot.site.page(ORIGIN).text.endswith(OPEN) and "== Alt ==" not in bot.site.page(ORIGIN).text


def test_failing_first_archive_leaves_the_second_alone():
    bot = makeBot()
    nov = bot.site.page(NOV)
    nov.saveError = pywikibot.exceptions.LockedPageError(nov)
    run(bot, TWO_TARGETS)
    assert bot.site.saved() == {}


def test_too_big_archive_is_found_before_saving():
    bot = makeBot()
    bot.site.siteinfo = {'maxarticlesize': 1000}
    bot.site.page(OKT, "ä" * 450)   # 900 bytes
    doc = run(bot, TWO_TARGETS)
    assert bot.site.saved() == {}
    assert (doc.outcome, doc.outcomeKey, doc.outcomeArgs) == ('skipped', 'error.too_big', {'target': OKT})


def test_main_namespace_is_found_before_saving():
    bot = makeBot()
    bot.site.page(OKT)._namespace = 0
    doc = run(bot, TWO_TARGETS)
    assert bot.site.saved() == {}
    assert doc.outcomeKey == 'skip.main_namespace'


def test_new_section_next_to_one_already_archived():
    """Only the missing section is added; the summary counts only this one."""
    bot = makeBot()
    bot.site.page(ARCHIVE, "{{Archiv}}\n\n" + OLD_ARCHIVED.rstrip())
    new = OLD.replace("== Alt ==", "== Neu ==")
    run(bot, OPTIONS + OLD + new + OPEN)
    [(text, summary)] = bot.site.saved()[ARCHIVE]
    assert text.count("== Alt ==") == 1 and text.count("== Neu ==") == 1
    assert summary.startswith("Archiviere 1 Abschnitt von")


@pytest.mark.parametrize("archived", [
    OLD_ARCHIVED + "noch eine Antwort --B 10:00, 7. Nov. 2026 (CET)\n",   # goes on
    "x" + OLD_ARCHIVED,                                                    # not at the start of a line
])
def test_similar_section_in_the_archive_is_no_copy(archived):
    bot = makeBot()
    bot.site.page(ARCHIVE, "{{Archiv}}\n\n" + archived)
    run(bot)
    assert bot.site.page(ARCHIVE).text.count("== Alt ==") == 2


def test_two_targets_summaries():
    text = OPTIONS.replace("((Jahr))", "((Jahr))/((Monat:Kurz))") + OLD + (
        "== Okt ==\nq --A 10:00, 1. Okt. 2026 (CEST)\n{{Erledigt|1=--A 10:00, 2. Okt. 2026 (CEST)}}\n") + OPEN
    bot = makeBot()
    run(bot, text)
    nov, okt = ARCHIVE + "/Nov", ARCHIVE + "/Okt"
    saved = bot.site.saved()
    assert set(saved) == {nov, okt, ORIGIN}
    originSummary = saved[ORIGIN][0][1]
    # with several targets the "(ab Abschnitt ...)" part is left out of the summary of the origin page
    assert originSummary.startswith(f"Archiviere 2 Abschnitte: 1 nach [[{nov}]], 1 nach [[{okt}]] - letzte Bearbeitung")


# ---------------------------------------------------------------- ArchiveRobot

def test_parse_args():
    assert botModule.parseArgs([]) == {'dryRun': False, 'project': 'dewikipedia', 'page': None,
                                       'saveLocalLogFile': False, 'summary': True, 'full': False}
    assert botModule.parseArgs(['-dryrun', '-project:commons', '-page:User talk:Foo bar']) == \
        {'dryRun': True, 'project': 'commons', 'page': 'User talk:Foo bar', 'saveLocalLogFile': False,
         'summary': True, 'full': False}
    assert botModule.parseArgs(['-full'])['full'] is True
    assert botModule.parseArgs(['-nosummary'])['summary'] is False
    assert botModule.parseArgs(['-project'])['project'] is None
    with pytest.raises(core.ArchivingError):
        botModule.parseArgs(['-page'])


@pytest.mark.parametrize("arg", ['-xyz', '--dryrun', '-dry-run', '--dry-run', '-dry', 'dryrun', '-projects:x', '-pages:x'])
def test_unknown_argument_stops_the_bot(arg):
    with pytest.raises(core.ArchivingError):
        botModule.parseArgs(['-project:commons', arg])


def robot(bot):
    r = object.__new__(botModule.ArchiveRobot)
    r.dryRun, r.localBot, r.site = bot.dryRun, bot.localBot, bot.site
    r.saveLocalLogFile, r.localLogFile = False, None
    return r


def test_robot_reports_wrong_options_on_page():
    bot = makeBot()
    page = bot.site.page(ORIGIN, "{{Autoarchiv-Erledigt|Alter=3}}\n== A ==\n")
    robot(bot)._runOnPage(page)
    [(text, summary)] = page.saves
    assert text.startswith("{{Autoarchiv-Erledigt|Alter=3}}\n== A ==\n\n\n== Archivierung konnte nicht durchgeführt werden ==")
    # the reason in the language of the wiki, followed by a space before the next sentence
    assert "festgestellt. Der Parameter 'ZIEL' fehlt. Beachte bitte" in text
    assert "<<" not in text   # no pywikibot color codes on the wiki
    assert summary == "Berichte Fehler"
    # no second report while the error category is still on the page
    robot(bot)._runOnPage(page)
    assert len(page.saves) == 1


def test_robot_reports_invalid_option_value_on_page():
    bot = makeBot()
    page = bot.site.page(ORIGIN, "{{Autoarchiv-Erledigt|Alter=7d|Ziel=X/Y}}\n== A ==\n")
    robot(bot)._runOnPage(page)
    [(text, summary)] = page.saves
    assert "'ALTER' muss eine Zahl sein, nicht '<nowiki>7d</nowiki>'." in text
    assert "[[" + bot.localBot.errorCategory + "]]" in text


def test_robot_skips_excluded_pages():
    bot = makeBot()
    page = bot.site.page("Vorlage:Erledigt", PAGE)
    robot(bot)._runOnPage(page)
    assert bot.site.saved() == {}


def test_robot_survives_unreadable_page():
    """Regression: an error before the WikiDocument exists must not end in UnboundLocalError."""
    bot = makeBot()
    robot(bot)._runOnPage(bot.site.page("Benutzer Diskussion:Gibt es nicht"))
    assert bot.site.saved() == {}


def test_save_report_writes_utf8(tmp_path):
    doc = makeDoc(PAGE)
    doc.reportText = "== Bericht ==\nÄrger"
    logFile = tmp_path / "archiv.log"
    doc.saveReport(True, str(logFile))
    doc.saveReport(False, str(logFile))
    assert logFile.read_text(encoding="utf-8") == "== Bericht ==\nÄrger\n"

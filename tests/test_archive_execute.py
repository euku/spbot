"""Tests for writing archive and talk pages (executeArchiving) and ArchiveRobot, against a FakeSite."""
import pytest
import pywikibot

from archive_resolved import bot as botModule
from archive_resolved import core
from conftest import makeBot, makeDoc

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
    doc = makeDoc(text, bot=bot, title=title)
    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    doc.prepareArchiving()
    if doc.hasWorkToDo():
        doc.executeArchiving()
    return doc


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
    # month names are only recognized if they are the same (here: November); there is no
    # number in "Dezember" to tell it from a normal page name
    (ORIGIN + "/Archiv/2026/November", "((Lemma))/Archiv/((Jahr))/((Monat:Lang))"),
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
                                       'saveLocalLogFile': False}
    assert botModule.parseArgs(['-dryrun', '-project:commons', '-page:User talk:Foo bar', '-xyz']) == \
        {'dryRun': True, 'project': 'commons', 'page': 'User talk:Foo bar', 'saveLocalLogFile': False}
    assert botModule.parseArgs(['-project'])['project'] is None
    with pytest.raises(core.ArchivingError):
        botModule.parseArgs(['-page'])


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
    assert "'ZIEL' is missing." in text
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
    assert "'ALTER' must be a number, not '7d'." in text
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

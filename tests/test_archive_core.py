"""Tests for archive_resolved.core without any wiki access: options, sections, ages, targets."""
import time
from datetime import datetime, timedelta

import pytest

from archive_resolved import core
from conftest import NOW, makeBot, makeDoc

OPTIONS = "{{Autoarchiv-Erledigt|Alter=3|Ziel='((Lemma))/Archiv/((Jahr))'}}\n"

# NOW = 2026-11-16 12:00
PAGE = OPTIONS + """Einleitung bleibt stehen.

== Alt erledigt ==
Frage --[[Benutzer:A|A]] 10:00, 1. Nov. 2026 (CET)
:Antwort --[[Benutzer:B|B]] 11:00, 2. Nov. 2026 (CET)
{{Erledigt|1=--[[Benutzer:A|A]] 12:00, 5. Nov. 2026 (CET)}}

== Frisch erledigt ==
Frage --A 10:00, 14. Nov. 2026 (CET)
{{Erledigt|1=--A 09:00, 15. Nov. 2026 (CET)}}

== Offen ==
Frage --A 10:00, 1. Okt. 2026 (CEST)

== Nicht archivieren ==
{{Nicht archivieren}}
Frage --A 10:00, 1. Okt. 2026 (CEST)
{{Erledigt|1=--A 12:00, 2. Okt. 2026 (CEST)}}
"""


def prepared(text=PAGE, bot=None, title="Benutzer Diskussion:Test"):
    doc = makeDoc(text, bot=bot, title=title)
    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    doc.prepareArchiving()
    return doc


# ---------------------------------------------------------------- findOptions

def test_find_options_defaults():
    doc = makeDoc(PAGE)
    doc.findOptions()
    assert doc.thresholdAgeResolvedTemplate == 3.0
    assert doc.archivingTargetPattern == "((Lemma))/Archiv/((Jahr))"  # quotes removed
    assert doc.headlineLevel == 2
    assert doc.thresholdAgeByTimeout == 0


def test_find_options_all_parameters():
    doc = makeDoc("{{Vorlage:Autoarchiv-Erledigt |Alter = 7.5 |Ziel=((Lemma))/A |Ebene=3 |Zeitbeschränkung=30}}")
    doc.findOptions()
    assert doc.thresholdAgeResolvedTemplate == 7.5
    assert doc.archivingTargetPattern == "((Lemma))/A"
    assert doc.headlineLevel == 3
    assert doc.thresholdAgeByTimeout == 30.0


@pytest.mark.parametrize("text", [
    "Keine Vorlage",
    "<!-- {{Autoarchiv-Erledigt|Alter=3|Ziel=((Lemma))/A}} -->",
    "<nowiki>{{Autoarchiv-Erledigt|Alter=3|Ziel=((Lemma))/A}}</nowiki>",
    "{{Autoarchiv-Erledigt|Ziel=((Lemma))/A}}",   # Alter missing
    "{{Autoarchiv-Erledigt|Alter=3}}",            # Ziel missing
])
def test_find_options_missing(text):
    with pytest.raises(core.NoOptions):
        makeDoc(text).findOptions()


@pytest.mark.parametrize("text", [
    "{{Autoarchiv-Erledigt|Alter=drei|Ziel=((Lemma))/A}}",
    "{{Autoarchiv-Erledigt|Alter=3|Ziel=((Lemma))/A|Ebene=zwei}}",
])
def test_find_options_wrong_format(text):
    with pytest.raises(core.WrongOptions):
        makeDoc(text).findOptions()


def test_find_options_english():
    doc = makeDoc("{{Autoarchive resolved section|age=2|archive=((FULLPAGENAME))/Archive ((year))|level=3}}",
                  bot=makeBot("commons"))
    doc.findOptions()
    assert (doc.thresholdAgeResolvedTemplate, doc.archivingTargetPattern, doc.headlineLevel) == \
        (2.0, "((FULLPAGENAME))/Archive ((year))", 3)


# ---------------------------------------------------------------- divideIntoSlices

def titles(doc):
    return [d.getTitleClear() for d in doc.listDiscussions]


def test_divide_into_slices_level_2():
    doc = makeDoc(PAGE)
    doc.findOptions()
    doc.divideIntoSlices()
    assert titles(doc) == ["Alt erledigt", "Frisch erledigt", "Offen", "Nicht archivieren"]
    # the content of a section runs up to the next headline
    first = doc.listDiscussions[0]
    assert first.content.startswith("== Alt erledigt ==\n")
    assert first.content.endswith("2026 (CET)}}\n\n")


def test_divide_into_slices_subsections_belong_to_parent():
    text = OPTIONS + "== A ==\ntext\n=== A1 ===\nmehr\n== B ==\n=> kein Titel\nb\n"
    doc = makeDoc(text)
    doc.findOptions()
    doc.divideIntoSlices()
    assert titles(doc) == ["A", "B"]
    assert doc.listDiscussions[0].content == "== A ==\ntext\n=== A1 ===\nmehr\n"
    assert doc.listDiscussions[1].content == "== B ==\n=> kein Titel\nb\n"


def test_divide_into_slices_level_3_stops_at_level_2():
    text = "{{Autoarchiv-Erledigt|Alter=3|Ziel=((Lemma))/A|Ebene=3}}\n== Tag ==\n=== X ===\nx\n== Tag 2 ==\nz\n=== Y ===\ny\n"
    doc = makeDoc(text)
    doc.findOptions()
    doc.divideIntoSlices()
    assert titles(doc) == ["X", "Y"]
    assert doc.listDiscussions[0].content == "=== X ===\nx\n"   # "== Tag 2 ==" is not part of X


def test_headline_with_template_and_comment():
    text = OPTIONS + "== {{Q-|Q6501349|capitalization=ucfirst}} == <!-- Car parks -->\nx\n"
    doc = makeDoc(text)
    doc.findOptions()
    doc.divideIntoSlices()
    assert titles(doc) == ["{{Q-|Q6501349|capitalization=ucfirst}}"]


# ---------------------------------------------------------------- examine / shouldBeArchived

def test_examine_ages():
    doc = makeDoc(PAGE)
    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    old, fresh, open_, keep = doc.listDiscussions
    # signatures are local time (Europe/Berlin); the bot compares them with now + UTC offset (1 or 2 hours)
    assert old.getNumberOfContributions() == 3
    assert 15.0 < old.getFirstContributionAge() < 15.2
    assert 10.9 < old.getAgeByResolvedTemplate() < 11.1
    assert 1.0 < fresh.getAgeByResolvedTemplate() < 1.2
    assert open_.getAgeByResolvedTemplate() == 0
    assert keep.hasDoNotArchiveTmpl


@pytest.mark.parametrize("project, offsetHours, signature", [
    # NOW = 2026-11-16 12:00 UTC; each signature is exactly one day earlier in the wiki's local time
    ("dewikipedia", 1, "--A 13:00, 15. Nov. 2026 (CET)"),
    ("cswikipedia", 1, "--A 15. 11. 2026, 13:00 (CET)"),
    ("itwikipedia", 1, "--A 13:00, 15 nov 2026 (CET)"),
    ("kowikipedia", 9, "--A 2026년 11월 15일 (일) 21:00 (KST)"),
    ("jawikipedia", 0, "--A 2026年11月15日 (日) 12:00 (UTC)"),
    ("viwikipedia", 0, "--A 12:00, ngày 15 tháng 11 năm 2026 (UTC)"),
])
def test_signature_age_uses_local_time_of_the_wiki(project, offsetHours, signature):
    bot = makeBot(project)
    assert bot.localBot.getUtcDiff(NOW) == timedelta(hours=offsetHours)
    disc = core.Discussion("Test")
    ages, _ = disc._extractTimeStampsAndAges(bot, bot.localBot.timeStampRegEx, "q " + signature, NOW)
    assert ages == [pytest.approx(1.0)]


@pytest.mark.parametrize("project, at, hours", [
    ("dewikipedia", datetime(2026, 1, 15, 12, 0), 1),
    ("dewikipedia", datetime(2026, 7, 15, 12, 0), 2),
    ("dewikipedia", datetime(2026, 10, 25, 0, 59), 2),   # 02:59 CEST, the last minute of summer time
    ("dewikipedia", datetime(2026, 10, 25, 1, 0), 1),    # 02:00 CET
    ("kowikipedia", datetime(2026, 7, 15, 12, 0), 9),
    ("commons", datetime(2026, 7, 15, 12, 0), 0),
])
def test_utc_diff_at_a_given_time(project, at, hours):
    assert makeBot(project).localBot.getUtcDiff(at) == timedelta(hours=hours)


def test_examine_ignores_signatures_in_comments_and_nowiki():
    text = OPTIONS + ("== A ==\n<!-- {{Erledigt|1=--A 10:00, 1. Nov. 2026 (CET)}} -->\n"
                      "<nowiki>{{Erledigt|1=--A 10:00, 1. Nov. 2026 (CET)}}</nowiki>\n")
    doc = makeDoc(text)
    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    disc = doc.listDiscussions[0]
    assert disc.getNumberOfContributions() == 0
    assert disc.getAgeByResolvedTemplate() == 0


KO_OPTIONS = "{{완료된 토론 자동 보존|날짜=1|보존='((FULLPAGENAME))/보존'}}\n"
KO_SECTION = ("== A ==\nq --A 2026년 11월 1일 (일) 10:00 (KST)\n%s"
              "{{완료된 토론|1=--A 2026년 11월 2일 (월) 10:00 (KST)}}\n")


@pytest.mark.parametrize("keep", [
    # what {{subst:보존 방지}} leaves on the page
    "<!-- [[User:DoNotArchiveUntil]] 2036년 11월 17일 (월) 12:00 (KST) -->\n",
    "{{보존 방지}}\n",
    "{{틀:보존 방지|30}}\n",
])
def test_korean_do_not_archive(keep):
    doc = prepared(KO_OPTIONS + KO_SECTION % keep, bot=makeBot("kowikipedia"), title="사용자토론:Test")
    assert doc.listDiscussions[0].hasDoNotArchiveTmpl
    assert not doc.hasWorkToDo()


def test_korean_section_is_archived_without_marker():
    doc = prepared(KO_OPTIONS + KO_SECTION % "", bot=makeBot("kowikipedia"), title="사용자토론:Test")
    assert doc.archiveJobCounterByTarget == {"사용자토론:Test/보존": 1}


def test_english_do_not_archive_until_comment():
    text = ("{{Autoarchive resolved section|age=1|archive=((FULLPAGENAME))/Archive}}\n"
            "== A ==\nq --A 10:00, 1 November 2026 (UTC)\n"
            "<!-- [[User:DoNotArchiveUntil]] 19:24, 13 March 2035 (UTC) -->\n"
            "{{Section resolved|1=--A 10:00, 2 November 2026 (UTC)}}\n")
    doc = prepared(text, bot=makeBot("commons"), title="User talk:Test")
    assert doc.listDiscussions[0].hasDoNotArchiveTmpl
    assert not doc.hasWorkToDo()


@pytest.mark.parametrize("resolvedAge, lastAge, doNotArchive, timeout, expected", [
    (0, 100, False, 0, False),     # not resolved, no timeout
    (2.9, 0, False, 0, False),     # resolved, too young
    (3.1, 0, False, 0, True),      # resolved and old enough
    (3.1, 0, True, 0, False),      # {{Nicht archivieren}}
    (0, 30, False, 30, True),      # timeout reached
    (0, 29.9, False, 30, False),   # timeout not reached
    (0, 99, True, 30, False),      # timeout but {{Nicht archivieren}}
])
def test_should_be_archived(resolvedAge, lastAge, doNotArchive, timeout, expected):
    disc = core.Discussion("X")
    disc.ageByResolvedTemplate = resolvedAge
    disc.lastContributionAge = lastAge
    disc.hasDoNotArchiveTmpl = doNotArchive
    assert disc.shouldBeArchived(3.0, timeout) is expected


# ---------------------------------------------------------------- prepareArchiving

def test_prepare_archiving_removes_only_due_sections():
    doc = prepared()
    assert doc.numberOfDiscussionsToArchive == 1
    target = "Benutzer Diskussion:Test/Archiv/2026"
    assert list(doc.archiveJobTextByTarget) == [target]
    assert doc.archiveJobTextByTarget[target].startswith("== Alt erledigt ==\n")
    assert doc.archiveJobCounterByTarget[target] == 1
    assert doc.archiveJobFirstTitleByTarget[target] == "Alt_erledigt"
    assert "== Alt erledigt ==" not in doc.modifiedText
    for kept in ("Einleitung bleibt stehen.", "== Frisch erledigt ==", "== Offen ==", "== Nicht archivieren =="):
        assert kept in doc.modifiedText
    # nothing lost, nothing duplicated
    assert len(doc.modifiedText) + len(doc.archiveJobTextByTarget[target]) == len(PAGE)


def test_prepare_archiving_several_sections_and_targets():
    text = OPTIONS.replace("((Jahr))", "((Jahr))/((Monat:Kurz))") + (
        "== [[Foo|''Bar'']] ==\nq --A 10:00, 1. Okt. 2026 (CEST)\n{{Erledigt|1=--A 10:00, 2. Okt. 2026 (CEST)}}\n"
        "== Bleibt ==\nq --A 10:00, 1. Nov. 2026 (CET)\n"
        "== Okt 2 ==\nq --A 10:00, 3. Okt. 2026 (CEST)\n{{Erledigt|1=--A 10:00, 4. Okt. 2026 (CEST)}}\n"
        "== Nov ==\nq --A 10:00, 2. Nov. 2026 (CET)\n{{Erledigt|1=--A 10:00, 3. Nov. 2026 (CET)}}\n")
    doc = prepared(text)
    okt, nov = "Benutzer Diskussion:Test/Archiv/2026/Okt", "Benutzer Diskussion:Test/Archiv/2026/Nov"
    assert doc.archiveJobCounterByTarget == {okt: 2, nov: 1}
    assert doc.archiveJobFirstTitleByTarget[okt] == "Bar"     # link and markup removed
    assert "== Okt 2 ==" in doc.archiveJobTextByTarget[okt]
    assert doc.modifiedText == OPTIONS.replace("((Jahr))", "((Jahr))/((Monat:Kurz))") + \
        "== Bleibt ==\nq --A 10:00, 1. Nov. 2026 (CET)\n"


# ---------------------------------------------------------------- determineArchivingTarget

def target_for(pattern, firstContribution, project="dewikipedia", title="Diskussion:Foo"):
    doc = makeDoc("", bot=makeBot(project), title=title)
    doc.archivingTargetPattern = pattern
    disc = core.Discussion(title)
    disc.firstContribution = time.mktime(time.strptime(firstContribution, "%Y-%m-%d"))
    return disc.determineArchivingTarget(doc)


@pytest.mark.parametrize("pattern, date, expected", [
    ("((Lemma))/Archiv/((Jahr))", "2026-03-15", "Diskussion:Foo/Archiv/2026"),
    ("((Lemma))/((Jahr))/((Monat:Lang))", "2026-03-15", "Diskussion:Foo/2026/März"),
    ("((Lemma))/((Jahr))/((Monat:##))-((Tag:##))", "2026-03-05", "Diskussion:Foo/2026/03-05"),
    ("((FULLPAGENAME))/((Jahr))/Q((Quartal)) H((Halbjahr:I))", "2026-08-01", "Diskussion:Foo/2026/Q3 HII"),
    ("((Lemma))/((Jahr))/KW ((Woche:##))", "2026-11-16", "Diskussion:Foo/2026/KW 47"),
    # calendar week exceptions at the turn of the year: year (and month) of the ISO week are used
    ("((Lemma))/((Jahr))/KW ((Woche))", "2024-12-30", "Diskussion:Foo/2025/KW 1"),
    ("((Lemma))/((Jahr))/KW ((Woche))", "2027-01-01", "Diskussion:Foo/2026/KW 53"),
    ("((Lemma))/((Jahr))/((Monat:Kurz))/KW ((Woche))", "2024-12-30", "Diskussion:Foo/2025/Jan/KW 1"),
    ("((Lemma))/((Jahr))/((Monat:##))/KW ((Woche))", "2024-12-30", "Diskussion:Foo/2025/01/KW 1"),
    ("((Lemma))/((Jahr))/((Monat:Kurz))/KW ((Woche))", "2027-01-01", "Diskussion:Foo/2026/Dez/KW 53"),
    ("((Lemma))/((Jahr))/((Monat:##))/KW ((Woche:##))", "2021-01-03", "Diskussion:Foo/2020/12/KW 53"),
    ("((Lemma))/((Jahr))/((Monat:Lang))/KW ((Woche))", "2023-01-01", "Diskussion:Foo/2022/Dezember/KW 52"),
    # ... and quarter and half-year follow that month
    ("((Lemma))/((Jahr))/Q((Quartal)) H((Halbjahr))/KW ((Woche))", "2024-12-30", "Diskussion:Foo/2025/Q1 H1/KW 1"),
    ("((Lemma))/((Jahr))/Q((Quartal:I)) H((Halbjahr:##))/KW ((Woche))", "2027-01-01", "Diskussion:Foo/2026/QIV H02/KW 53"),
    ("((Lemma))/((Jahr))/Q((Quartal))/KW ((Woche))", "2026-12-28", "Diskussion:Foo/2026/Q4/KW 53"),
    # ... but not without a week variable
    ("((Lemma))/((Jahr))", "2024-12-30", "Diskussion:Foo/2024"),
])
def test_determine_archiving_target_de(pattern, date, expected):
    assert target_for(pattern, date) == expected


def test_determine_archiving_target_en():
    assert target_for("((FULLPAGENAME))/Archive ((year)) ((month:long))", "2026-02-02", "commons",
                      "User talk:Foo") == "User talk:Foo/Archive 2026 February"


@pytest.mark.parametrize("project, pattern, date, expected", [
    # 1 Jan 2027 is in week 53 of 2026, 30 Dec 2024 in week 1 of 2025 (all languages share the logic)
    ("commons", "((FULLPAGENAME))/((year))/((month:##))/((week))", "2027-01-01", "Foo/2026/12/53"),
    ("commons", "((FULLPAGENAME))/((year)) ((month:long)) W((week:##))", "2024-12-30", "Foo/2025 January W01"),
    ("jawikipedia", "((FULLPAGENAME))/((year))/((month:#))/((week))", "2027-01-01", "Foo/2026/12/53"),
    ("jawikipedia", "((FULLPAGENAME))/((month:short))/((week))", "2024-12-30", "Foo/01 月/1"),
    ("kowikipedia", "((FULLPAGENAME))/((년))/((월))/((주))", "2027-01-01", "Foo/2026/12/53"),
    ("commons", "((FULLPAGENAME))/((year)) Q((quarter)) H((half-year:i)) W((week))", "2027-01-01", "Foo/2026 Q4 Hii W53"),
    ("kowikipedia", "((FULLPAGENAME))/((년))/((분기))/((주))", "2024-12-30", "Foo/2025/1/1"),
])
def test_determine_archiving_target_turn_of_year(project, pattern, date, expected):
    assert target_for(pattern, date, project, "Foo") == expected


# ---------------------------------------------------------------- substSectionResolvedTempl

def test_subst_resolved_one_parameter():
    doc = makeDoc("")
    out = doc.substSectionResolvedTempl("x\n{{Erledigt|1=--[[Benutzer:A|A]] 12:00, 5. Nov. 2026 (CET)}}\n")
    assert out == ("x\n:<small>Archivierung dieses Abschnittes wurde gewünscht von: "
                   "--[[Benutzer:A|A]] 12:00, 5. Nov. 2026 (CET)</small>\n")


def test_subst_resolved_two_parameters():
    doc = makeDoc("")
    out = doc.substSectionResolvedTempl("{{erledigt|1=--A 12:00, 5. Nov. 2026 (CET)|2=Antwort gefunden}}")
    assert out == (":<small>Archivierung dieses Abschnittes wurde gewünscht von "
                   "--A 12:00, 5. Nov. 2026 (CET), Antwort gefunden</small>")


def test_subst_resolved_not_in_nowiki():
    doc = makeDoc("")
    text = "<nowiki>{{Erledigt|1=--A 12:00, 5. Nov. 2026 (CET)}}</nowiki>"
    assert doc.substSectionResolvedTempl(text) == text


# ---------------------------------------------------------------- report

def test_generate_report():
    doc = prepared()
    doc.generateReport()
    assert "Number of sections: '''4'''" in doc.reportText
    assert "Number of sections to archive: '''1'''" in doc.reportText
    assert "[[Benutzer Diskussion:Test/Archiv/2026|&rarr;]]" in doc.reportText


# ---------------------------------------------------------------- Zeitvergleich / timecompare

CLEARED_PAGE = """{{Autoarchiv-Erledigt|Alter=1|Ziel='((Lemma))/Archiv/((Jahr))/((Monat:##))'%s}}
== Lang offen ==
Frage --A 10:00, 20. Sep. 2026 (CEST)
{{Erledigt|1=--A 10:00, 3. Okt. 2026 (CEST)}}
:noch was --B 10:00, 1. Nov. 2026 (CET)
{{Erledigt|1=--A 10:00, 2. Nov. 2026 (CET)}}
== Ohne Erledigt ==
Frage --A 10:00, 20. Sep. 2026 (CEST)
"""


@pytest.mark.parametrize("options, cleared, timeout", [
    ("", False, 0),
    ("|Zeitvergleich=erledigt", True, 0),
    ("|Zeitvergleich = Erledigt ", True, 0),
    ("|Zeitvergleich=", False, 0),
    ("|Zeitvergleich=ältester", False, 0),
    ("|Zeitvergleich=erledigt|Zeitbeschränkung=14", True, 14.0),
    ("|Zeitbeschränkung=14", False, 14.0),
])
def test_find_options_time_comparator(options, cleared, timeout):
    doc = makeDoc(CLEARED_PAGE % options)
    doc.findOptions()
    assert doc.archivingUseTimeComparatorCleared is cleared
    assert doc.thresholdAgeByTimeout == timeout


@pytest.mark.parametrize("options, expectedTargets", [
    # default: oldest signature (September)
    ("", {"Benutzer Diskussion:Test/Archiv/2026/09": 1}),
    # Zeitvergleich=erledigt: newest {{Erledigt}} (November)
    ("|Zeitvergleich=erledigt", {"Benutzer Diskussion:Test/Archiv/2026/11": 1}),
    # a section without {{Erledigt}} (archived by timeout) falls back to the oldest signature
    ("|Zeitvergleich=erledigt|Zeitbeschränkung=30", {"Benutzer Diskussion:Test/Archiv/2026/11": 1,
                                                   "Benutzer Diskussion:Test/Archiv/2026/09": 1}),
])
def test_archiving_target_by_time_comparator(options, expectedTargets):
    doc = prepared(CLEARED_PAGE % options)
    assert doc.archiveJobCounterByTarget == expectedTargets


def test_timecompare_resolved_english():
    text = ("{{Autoarchive resolved section|age=1|archive=((FULLPAGENAME))/Archive/((year))-((month:##))|timecompare=resolved}}\n"
            "== A ==\nq --A 10:00, 30 September 2026 (UTC)\n{{Section resolved|1=--A 10:00, 2 November 2026 (UTC)}}\n")
    doc = prepared(text, bot=makeBot("meta"), title="Talk:Foo")
    assert list(doc.archiveJobCounterByTarget) == ["Talk:Foo/Archive/2026-11"]

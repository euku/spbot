"""Tests for archive_resolved_localization (project mapping, month names, target variables)."""
import re
import time

import pytest

from archive_resolved_localization.local_bot import LocalBot
from archive_resolved_localization.local_bot_factory import LocalBotFactory

# all projects from jobs/toolforge-jobs.yaml (+ the default)
PROJECTS = {
    "dewikipedia": ("de", "wikipedia", "LocalBotDe"),
    "dewiktionary": ("de", "wiktionary", "LocalBotDe"),
    "dewikisource": ("de", "wikisource", "LocalBotDe"),
    "dewikiversity": ("de", "wikiversity", "LocalBotDe"),
    "cswikipedia": ("cs", "wikipedia", "LocalBotCs"),
    "enwikisource": ("en", "wikisource", "LocalBotEn"),
    "simplewikipedia": ("simple", "wikipedia", "LocalBotEn"),
    "itwikipedia": ("it", "wikipedia", "LocalBotIt"),
    "jawikipedia": ("ja", "wikipedia", "LocalBotJa"),
    "kowikipedia": ("ko", "wikipedia", "LocalBotKo"),
    "viwikipedia": ("vi", "wikipedia", "LocalBotVi"),
    "commons": ("commons", "commons", "LocalBotEn"),
    "wikidata": ("wikidata", "wikidata", "LocalBotEn"),
    "wikimania": ("wikimania", "wikimania", "LocalBotEn"),
    "wikifunctions": ("wikifunctions", "wikifunctions", "LocalBotEn"),
    "species": ("species", "species", "LocalBotEn"),
    "meta": ("meta", "meta", "LocalBotMeta"),
    "incubator": ("incubator", "incubator", "LocalBotIncubator"),
}


@pytest.mark.parametrize("projectId", sorted(PROJECTS))
def test_factory_creates_expected_local_bot(projectId):
    code, family, className = PROJECTS[projectId]
    localBot = LocalBotFactory().createLocalBot(projectId)
    assert type(localBot).__name__ == className
    assert (localBot.projectCode, localBot.projectFamily) == (code, family)
    assert LocalBot.splitInCodeAndFamily(projectId) == (code, family)


def test_factory_rejects_unknown_project():
    with pytest.raises(ValueError):
        LocalBotFactory().createLocalBot("frwikipedia")


@pytest.mark.parametrize("projectId", sorted(PROJECTS))
def test_local_bot_is_complete(projectId):
    """Every project has all attributes the bot uses, and the regexes compile."""
    lb = LocalBotFactory().createLocalBot(projectId)
    for attr in ("timeStampRegEx", "optionsRegEx", "templDoNotArchive", "sectResolvedRegEx"):
        re.compile(getattr(lb, attr))
    for attr in ("archiveTemplateName", "headTemplate", "errorCategory", "errorText", "errorTextSummary",
                 "paramAge", "paramArchive", "paramLevel", "paramTimeComparator", "paramTimeComparatorCleared",
                 "paramTimeout",
                 "archiveSumTargetS", "archiveSumTargetP", "archiveSumOriginS", "archiveSumOriginP",
                 "archiveSumOriginMulti", "firstNewSectionInArchiveSummary", "archiveSumLastEdit",
                 "archiveOverallSummary", "sectResolved1P", "sectResolved2P"):
        assert isinstance(getattr(lb, attr), str), attr
    # a tuple of exact titles: a plain string would make "in" a substring check
    assert isinstance(lb.excludeList, tuple)
    assert lb.archiveTemplateName in lb.excludeList
    for title in lb.excludeList:
        assert "{" not in title and "}" not in title, title
    assert "%s" in lb.errorText
    # replacement list works and contains the week variables
    stamp = time.strptime("2026-03-15 12:00", "%Y-%m-%d %H:%M")
    replacements = dict(lb.getReplacementDict("Talk:Foo", stamp, "2026", "03"))
    for weekVar in lb._getAllWeekVariablesForTargetPath():
        assert weekVar in replacements
    assert "Talk:Foo" in [str(v) for v in replacements.values()]


@pytest.mark.parametrize("name, number", [
    ("Jan", 1), ("Mrz", 3), ("Mär", 3), ("März", 3), ("Mai", 5), ("Sept", 9), ("Okt", 10), ("Dezember", 12)])
def test_de_month_name_to_number(name, number):
    assert LocalBotFactory().createLocalBot("dewikipedia").convertMonthNameToNumber(name) == number


@pytest.mark.parametrize("name, number", [("Jan", 1), ("March", 3), ("Dec", 12)])
def test_en_month_name_to_number(name, number):
    assert LocalBotFactory().createLocalBot("commons").convertMonthNameToNumber(name) == number


@pytest.mark.parametrize("month, quarter, halfyear", [(1, "1", "1"), (3, "1", "1"), (4, "2", "1"),
                                                      (7, "3", "2"), (12, "4", "2")])
def test_quarter_and_halfyear(month, quarter, halfyear):
    lb = LocalBotFactory().createLocalBot("dewikipedia")
    stamp = time.strptime(f"2026-{month:02d}-10", "%Y-%m-%d")
    assert lb.getQuarterName(stamp, False, False) == quarter
    assert lb.getQuarterName(stamp, False, True) == "0" + quarter
    assert lb.getQuarterName(stamp, True, False) == ["i", "ii", "iii", "iv"][int(quarter) - 1]
    assert lb.getHalfyearName(stamp, False, False) == halfyear
    assert lb.getHalfyearName(stamp, True, False) == ["i", "ii"][int(halfyear) - 1]


@pytest.mark.parametrize("signature", [
    "12:34, 5. Nov. 2026 (CET)",
    "12:34, 15. Mär. 2026 (CET)",
    "09:05, 1. Okt. 2026 (CEST)",
    "23:59, 31. Dez. 2026 (MEZ)",
    "00:00, 7. Juli 2026 (MESZ)",
    "12:34, 5 Nov 2026 (UTC)",
])
def test_de_timestamp_regex(signature):
    lb = LocalBotFactory().createLocalBot("dewikipedia")
    m = re.search(lb.timeStampRegEx, "--[[Benutzer:A|A]] " + signature)
    assert m is not None
    lb.convertMonthNameToNumber(m.group("MM"))  # must not raise


@pytest.mark.parametrize("signature", ["12:34, 5 November 2026 (UTC)", "01:02, 15 Mar 2026 (UTC)"])
def test_en_timestamp_regex(signature):
    lb = LocalBotFactory().createLocalBot("commons")
    m = re.search(lb.timeStampRegEx, "--[[User:A|A]] " + signature)
    assert m is not None
    lb.convertMonthNameToNumber(m.group("MM"))


@pytest.mark.parametrize("projectId", sorted(PROJECTS))
def test_time_comparator_and_timeout_are_different_parameters(projectId):
    lb = LocalBotFactory().createLocalBot(projectId)
    assert lb.paramTimeComparator != lb.paramTimeout
    assert "COMAPARE" not in lb.paramTimeComparator   # old typo


@pytest.mark.parametrize("projectId, language", [
    ("dewikipedia", "de"), ("dewiktionary", "de"), ("cswikipedia", "cs"), ("itwikipedia", "it"),
    ("jawikipedia", "ja"), ("kowikipedia", "ko"), ("viwikipedia", "vi"), ("enwikisource", "en"),
    ("simplewikipedia", "en"), ("commons", "en"), ("meta", "en"), ("incubator", "en"),
])
def test_message_language_of_wiki(projectId, language):
    assert LocalBotFactory().createLocalBot(projectId).language == language


def test_messages_complete():
    """Every language has every message with the same placeholders (the status page uses them, too)."""
    from archive_resolved_localization.messages import MESSAGES
    en = MESSAGES["en"]
    assert set(MESSAGES) == {"cs", "de", "en", "it", "ja", "ko", "vi"}
    for code, texts in MESSAGES.items():
        assert set(texts) == set(en), code
        for key, text in texts.items():
            assert sorted(re.findall(r"{(\w+)}", text)) == sorted(re.findall(r"{(\w+)}", en[key])), (code, key)
            assert "<" not in text and ">" not in text, (code, key)   # plain text, also shown as HTML


@pytest.mark.parametrize("projectId, docPage", [
    ("cswikipedia", "Šablona:Archivace vyřešených sekcí/doc"),
    ("jawikipedia", "Template:Autoarchive resolved section/doc"),
    ("kowikipedia", "틀:완료된 토론 자동 보존/설명문서"),
    ("viwikipedia", "Bản mẫu:Autoarchive resolved section/doc"),
])
def test_doc_page_is_excluded(projectId, docPage):
    assert docPage in LocalBotFactory().createLocalBot(projectId).excludeList


def test_cs_first_new_section_summary_is_czech():
    lb = LocalBotFactory().createLocalBot("cswikipedia")
    assert lb.firstNewSectionInArchiveSummary == " (od sekce [[{firstNewSectionInArchiveLink}]])"

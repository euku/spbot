"""
Replays real talk pages (tests/fixtures/archive) against a FakeSite and compares the
result with a dry run of the bot on the live wikis (see tests/fixtures/archive/README.md).
"""
import json
import os
from datetime import datetime

import pytest
from pytz import timezone

from archive_resolved import core
from conftest import makeBot

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "archive")
with open(os.path.join(FIXTURES, "cases.json"), encoding="utf-8") as f:
    CASES = json.load(f)

AGE_TOLERANCE = 0.011  # report shows 2 decimals; run time is only known to the minute


def parseTime(value):
    return datetime.fromisoformat(value.rstrip("Z"))


def setUp(case):
    bot = makeBot(case["project"])
    now = parseTime(case["now"])
    # UTC offset of the wiki at the time of the recorded run (not at the time the test runs)
    offset = timezone(bot.localBot._getTimezone()).utcoffset(now)
    bot.localBot.getUtcDiff = lambda: offset
    with open(os.path.join(FIXTURES, case["file"]), encoding="utf-8") as f:
        text = f.read()
    page = bot.site.page(case["title"], text)
    for source, target in case["expected"]["redirects"].items():
        bot.site.page(source, "#REDIRECT [[%s]]" % target).redirectTo = target
        bot.site.page(target, "{{Archiv}}")
    doc = core.WikiDocument(text, case["title"], parseTime(case["lastEditTime"]), case["lastUser"], bot, now)
    return bot, page, doc


def mark(disc, doc):
    if disc.getAgeByResolvedTemplate() == 0.0:
        return ""
    return "archive" if disc.shouldBeArchived(doc.thresholdAgeResolvedTemplate, doc.thresholdAgeByTimeout) else "resolved"


@pytest.mark.parametrize("case", CASES, ids=[c["file"][:-5] for c in CASES])
def test_recorded_page(case):
    expected = case["expected"]
    bot, page, doc = setUp(case)

    if expected["error"]:
        with pytest.raises(core.NoOptions) as e:
            doc.findOptions()
        assert expected["error"] in e.value.getMsg()
        return

    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    doc.prepareArchiving()

    assert doc.numberDiscussions == expected["numberOfSections"]
    assert doc.numberOfDiscussionsToArchive == expected["numberToArchive"]
    assert len(doc.listDiscussions) == len(expected["rows"])
    for disc, row in zip(doc.listDiscussions, expected["rows"]):
        assert disc.getTitleClear() == row["headline"]
        assert disc.getNumberOfContributions() == row["signatures"]
        assert disc.determineArchivingTarget(doc) == row["target"]
        assert mark(disc, doc) == row["mark"], row["headline"]
        assert disc.getFirstContributionAge() == pytest.approx(row["firstAge"], abs=AGE_TOLERANCE)
        if row["resolvedAge"] is None:
            assert disc.getAgeByResolvedTemplate() == 0.0
        else:
            assert disc.getAgeByResolvedTemplate() == pytest.approx(row["resolvedAge"], abs=AGE_TOLERANCE)

    if doc.hasWorkToDo():
        doc.executeArchiving()
    assert [summary for _, summary in bot.site.saveLog] == expected["editComments"]
    if expected["mainNamespaceRefused"] or not expected["editComments"]:
        assert page.saves == []
    else:
        # the origin page lost exactly the archived sections
        [(newText, _)] = page.saves
        archived = sum(len(t) for t in doc.archiveJobTextByTarget.values())
        assert len(newText) == len(doc.originalText) - archived

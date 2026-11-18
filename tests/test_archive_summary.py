"""Tests for the run summary (archive_resolved/summary.py) written by ArchiveRobot."""
import json

import pywikibot

from archive_resolved import bot as botModule
from archive_resolved.summary import RunSummary, summaryPath
from conftest import makeBot
from test_archive_execute import ARCHIVE, OPEN, OPTIONS, ORIGIN, PAGE


def robot(bot, path):
    r = object.__new__(botModule.ArchiveRobot)
    r.dryRun, r.localBot, r.site = bot.dryRun, bot.localBot, bot.site
    r.saveLocalLogFile, r.localLogFile = False, None
    r.summary = RunSummary(path, 'dewikipedia', bot.dryRun, history=str(path) + '.history')
    return r


def records(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def test_summary_path():
    assert summaryPath('/x/logs', 'commons') == '/x/logs/archive-resolved-commons.jsonl'


def test_archived_page(tmp_path):
    path = tmp_path / 's.jsonl'
    bot = makeBot()
    r = robot(bot, path)
    r._runOnPage(bot.site.page(ORIGIN, PAGE))
    r.summary.end(True)
    run, page, end = records(path)
    assert run['type'] == 'run' and run['project'] == 'dewikipedia' and run['dryRun'] is False
    assert page['type'] == 'page' and page['title'] == ORIGIN and page['status'] == 'archived'
    assert page['options'] == {'ALTER': '3', 'ZIEL': "'((Lemma))/Archiv/((Jahr))'"}
    assert page['age'] == 3.0 and page['targetPattern'] == '((Lemma))/Archiv/((Jahr))' and page['level'] == 2
    assert page['toArchive'] == 1 and page['targets'] == {ARCHIVE: 1}
    assert [(s['title'], s['archive'], s['target']) for s in page['sections']] == \
        [('Alt', True, ARCHIVE), ('Offen', False, ARCHIVE)]
    assert page['sections'][0]['resolvedAge'] > 3 and page['sections'][1]['resolvedAge'] is None
    assert end['type'] == 'end' and end['complete'] is True and end['pages'] == 1
    assert end['archivedSections'] == 1 and end['byStatus'] == {'archived': 1}


def test_nothing_to_do_and_dry_run(tmp_path):
    path = tmp_path / 's.jsonl'
    bot = makeBot(dryRun=True)
    r = robot(bot, path)
    r._runOnPage(bot.site.page(ORIGIN, OPTIONS + OPEN))
    r._runOnPage(bot.site.page("Benutzer Diskussion:Zwei", PAGE))
    statuses = [rec.get('status') for rec in records(path)]
    assert statuses == [None, 'nothing', 'dryrun']
    assert records(path)[0]['dryRun'] is True


def test_skipped_protected_page(tmp_path):
    path = tmp_path / 's.jsonl'
    bot = makeBot()
    page = bot.site.page(ORIGIN, PAGE)
    page.protected = True
    robot(bot, path)._runOnPage(page)
    rec = records(path)[1]
    assert rec['status'] == 'skipped' and rec['messageKey'] == 'skip.protected' and rec['messageArgs'] == {}
    assert rec['message'] == 'Die Seite ist geschützt, der Bot darf sie nicht bearbeiten.'   # language of the wiki
    assert bot.site.saved() == {}


def test_skipped_protected_archive(tmp_path):
    path = tmp_path / 's.jsonl'
    bot = makeBot()
    bot.site.page(ARCHIVE, "{{Archiv}}\n").protected = True
    robot(bot, path)._runOnPage(bot.site.page(ORIGIN, PAGE))
    rec = records(path)[1]
    assert rec['status'] == 'skipped' and ARCHIVE in rec['message']


def test_options_error_and_excluded(tmp_path):
    path = tmp_path / 's.jsonl'
    bot = makeBot()
    r = robot(bot, path)
    r._runOnPage(bot.site.page(ORIGIN, "{{Autoarchiv-Erledigt|Alter=3}}\n== A ==\n"))
    r._runOnPage(bot.site.page("Vorlage:Erledigt", PAGE))
    opt, excl = records(path)[1:]
    assert opt['status'] == 'optionserror' and opt['message'] == "Der Parameter 'ZIEL' fehlt."
    assert opt['messageKey'] == 'opt.missing' and opt['messageArgs'] == {'param': 'ZIEL'}
    assert 'sections' not in opt   # no target pattern, nothing to show
    assert opt['options'] == {'ALTER': '3'}   # but what was given
    assert excl == {'type': 'page', 'title': 'Vorlage:Erledigt', 'time': excl['time'], 'status': 'excluded'}


def test_error_message_is_last_traceback_line(tmp_path):
    path = tmp_path / 's.jsonl'
    bot = makeBot()
    archive = bot.site.page(ARCHIVE)
    archive.saveError = pywikibot.exceptions.Error("contenttoobig")
    robot(bot, path)._runOnPage(bot.site.page(ORIGIN, PAGE))
    rec = records(path)[1]
    assert rec['status'] == 'error' and rec['messageKey'] == 'error.too_big'
    assert rec['messageArgs'] == {'target': ARCHIVE} and ARCHIVE in rec['message']
    assert rec['toArchive'] == 1


def test_error_saving_archive_page(tmp_path):
    path = tmp_path / 's.jsonl'
    bot = makeBot()
    bot.site.page(ARCHIVE).saveError = pywikibot.exceptions.Error("readonly")
    robot(bot, path)._runOnPage(bot.site.page(ORIGIN, PAGE))
    rec = records(path)[1]
    assert rec['messageKey'] == 'error.not_saved' and rec['messageArgs']['target'] == ARCHIVE
    assert 'readonly' in rec['messageArgs']['detail'] and rec['message'].startswith('Die Archivseite')


def test_unexpected_error(tmp_path, monkeypatch):
    path = tmp_path / 's.jsonl'
    bot = makeBot()
    def boom(self):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(botModule.WikiDocument, 'divideIntoSlices', boom)
    robot(bot, path)._runOnPage(bot.site.page(ORIGIN, PAGE))
    rec = records(path)[1]
    assert rec['status'] == 'error' and rec['messageKey'] == 'error.unexpected'
    assert rec['message'] == 'Unerwarteter Fehler: RuntimeError: kaputt'


def test_too_big_detection():
    class Api(Exception):
        code = 'contenttoobig'
    wrapped = pywikibot.exceptions.Error("Edit to page [[X]] failed")
    wrapped.__cause__ = Api("x")
    assert botModule._isTooBig(wrapped)
    assert botModule._isTooBig(pywikibot.exceptions.Error(
        "The text you have submitted is 2,075.263 kilobytes long, which is more than the maximum of 2,048 kilobytes."))
    assert not botModule._isTooBig(pywikibot.exceptions.Error("readonly"))


def test_unreadable_page_is_an_error(tmp_path):
    path = tmp_path / 's.jsonl'
    bot = makeBot()
    robot(bot, path)._runOnPage(bot.site.page("Benutzer Diskussion:Gibt es nicht"))
    rec = records(path)[1]
    assert rec['status'] == 'error' and 'sections' not in rec


def test_incomplete_run(tmp_path):
    path = tmp_path / 's.jsonl'
    summary = RunSummary(path, 'commons', False)
    summary.page('A', 'nothing')
    summary.end(False)
    end = records(path)[-1]
    assert end['complete'] is False and end['finished'] is None and end['byStatus'] == {'nothing': 1}
    [history] = records(tmp_path / 'archive-runs.jsonl')
    assert history == dict(end, project='commons', started=records(path)[0]['started'], dryRun=False)

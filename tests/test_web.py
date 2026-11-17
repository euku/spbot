"""Tests for the status web page (web/), with summary files written by the bot's RunSummary."""
import datetime
import gzip
import os
import sys

import pytest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
if WEB not in sys.path:
    sys.path.insert(0, WEB)

flask = pytest.importorskip('flask')

import config  # noqa: E402
import status  # noqa: E402
from app import app  # noqa: E402
from archive_resolved.summary import RunSummary  # noqa: E402
from conftest import makeBot  # noqa: E402
from test_archive_execute import ORIGIN, PAGE  # noqa: E402
from test_archive_summary import robot  # noqa: E402

JOBS = """\
# comment
- name: archive-resolved-dewikipedia
  command: pyvenv/bin/python bot/userscripts/archive-resolved-bot.py -project:dewikipedia
  image: python3.13
  schedule: "4   3   *   *   *"
  filelog-stdout: logs/archive-resolved-dewikipedia.out
  filelog-stderr: logs/archive-resolved-dewikipedia.err
- name: mp-helper
  command: pyvenv/bin/python bot/userscripts/mp-helper.py
  schedule: "*/20  *   *   *   *"
  filelog-stdout: logs/mp-helper.out
  filelog-stderr: logs/mp-helper.err
# - name: disabled
#   schedule: "5  5   *   *   *"
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    logs = tmp_path / 'logs'
    logs.mkdir()
    (tmp_path / 'jobs.yaml').write_text(JOBS, encoding='utf-8')
    monkeypatch.setattr(config, 'log_dir', str(logs))
    monkeypatch.setattr(config, 'jobs_file', str(tmp_path / 'jobs.yaml'))
    monkeypatch.setattr(config, 'venv_dir', str(tmp_path / 'venv'))
    monkeypatch.setattr(config, 'repo_dir', str(tmp_path / 'repo'))
    monkeypatch.setattr(config, 'replica_host', '')
    status._run_cache.clear()
    return tmp_path


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


def write_run(logs, path=None, pages=((ORIGIN, PAGE),), finish=True):
    """A real bot run on a FakeSite into logs/archive-resolved-dewikipedia.jsonl."""
    bot = makeBot()
    r = robot(bot, str(path or logs / 'archive-resolved-dewikipedia.jsonl'))
    r.summary.history = str(logs / 'archive-runs.jsonl')
    for title, text in pages:
        r._runOnPage(bot.site.page(title, text))
    if finish:
        r.summary.end(True)


def test_read_jobs_skips_comments(home):
    assert [j['name'] for j in status.read_jobs()] == ['archive-resolved-dewikipedia', 'mp-helper']
    assert status.archive_project(status.read_jobs()[0]) == 'dewikipedia'


@pytest.mark.parametrize('schedule, after, expected', [
    ('4 3 * * *', '2026-11-17 02:00', '2026-11-17 03:04'),
    ('4 3 * * *', '2026-11-17 03:04', '2026-11-18 03:04'),
    ('*/20 * * * *', '2026-11-17 02:41', '2026-11-17 03:00'),
    ('0 4 * * 3', '2026-11-17 12:00', '2026-11-18 04:00'),   # Wednesday
    ('1 3 */3 * *', '2026-11-17 12:00', '2026-11-19 03:01'),  # days 1, 4, ..., 19
    ('bad', '2026-11-17 12:00', None),
])
def test_next_run(schedule, after, expected):
    t = datetime.datetime.strptime(after, '%Y-%m-%d %H:%M').replace(tzinfo=status.UTC)
    result = status.next_run(schedule, t)
    assert (result.strftime('%Y-%m-%d %H:%M') if result else None) == expected


def test_latest_run_and_page(home):
    logs = home / 'logs'
    write_run(logs, pages=((ORIGIN, PAGE), ('Benutzer Diskussion:Zwei', "{{Autoarchiv-Erledigt|Alter=3}}\n")))
    run = status.latest_run('dewikipedia')
    assert run['end']['complete'] and set(run['pages']) == {ORIGIN, 'Benutzer Diskussion:Zwei'}
    assert status.page_record('dewikipedia', 'Benutzer_Diskussion:Test')[1]['status'] == 'archived'
    assert status.page_record('dewikipedia', 'Benutzer diskussion:test')[1]['title'] == ORIGIN
    assert status.find_pages('dewikipedia', 'zwei') == ['Benutzer Diskussion:Zwei']
    [row] = status.archive_overview()
    assert row['pages'] == 2 and row['archived'] == 1 and row['counts'] == {'archived': 1, 'optionserror': 1}
    assert row['history'][0]['archivedSections'] == 1


def test_running_and_older_gz_files(home):
    logs = home / 'logs'
    day = logs / '2026-11-16'
    day.mkdir()
    write_run(day, path=day / 'archive-resolved-dewikipedia.jsonl')
    raw = (day / 'archive-resolved-dewikipedia.jsonl').read_bytes()
    (day / 'archive-resolved-dewikipedia.jsonl.gz').write_bytes(gzip.compress(raw))
    os.remove(day / 'archive-resolved-dewikipedia.jsonl')
    write_run(logs, finish=False)  # today: still running
    run = status.latest_run('dewikipedia')
    assert run['end'] is None and status.run_state(run) == 'running'
    history = status.page_history('dewikipedia', ORIGIN)
    assert len(history) == 2 and all(h['status'] == 'archived' for h in history)


def test_section_reasons():
    page = {'age': 3.0, 'timeout': None}
    assert status.section_reason(page, {'archive': True, 'resolvedAge': 4.0})[0] == 'reason.resolved_old'
    assert status.section_reason(page, {'archive': False, 'resolvedAge': 1.0})[0] == 'reason.resolved_young'
    assert status.section_reason(page, {'archive': False, 'resolvedAge': None})[0] == 'reason.not_resolved'
    assert status.section_reason(page, {'doNotArchive': True})[0] == 'reason.do_not_archive'
    assert status.section_reason(dict(page, timeout=30.0), {'resolvedAge': None, 'lastAge': 5})[0] == \
        'reason.not_resolved_timeout'


def test_pages_render(home, client):
    logs = home / 'logs'
    write_run(logs)
    (logs / 'mp-helper.err').write_text('Traceback (most recent call last):\nKeyError: x\n', encoding='utf-8')
    html = client.get('/?uselang=de').get_data(as_text=True)
    assert 'Archivbot' in html and 'mp-helper' in html and 'KeyError' in html
    assert 'Replikat-Abfragen sind abgeschaltet' in html
    html = client.get('/archive').get_data(as_text=True)
    assert 'dewikipedia' in html and 'FULLPAGENAMEE' in html
    html = client.get('/archive?project=dewikipedia').get_data(as_text=True)
    assert ORIGIN in html and 'Benutzer Diskussion:Test/Archiv/2026' in html


def test_page_view_by_url_parameter(home, client):
    write_run(home / 'logs')
    response = client.get('/archive?project=dewikipedia&page=Benutzer_Diskussion:Test&uselang=en')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'archived: resolved for' in html and 'stays: not marked as resolved' in html
    assert "((Lemma))/Archiv/((Jahr))" in html
    assert 'href="https://de.wikipedia.org/wiki/Benutzer_Diskussion:Test"' in html


def test_page_view_unknown_page(home, client):
    write_run(home / 'logs')
    response = client.get('/archive?project=dewikipedia&page=Gibt es nicht')
    assert response.status_code == 404
    # a unique partial match redirects to the page
    response = client.get('/archive?project=dewikipedia&page=Test')
    assert response.status_code == 302
    assert response.headers['Location'] == '/archive?project=dewikipedia&page=Benutzer+Diskussion:Test'
    assert client.get('/archive?project=nowiki&page=x').status_code == 404


def test_escaping(home, client):
    title = 'Benutzer Diskussion:<script>'
    write_run(home / 'logs', pages=((title, PAGE),))
    html = client.get('/archive?project=dewikipedia&page=' + title).get_data(as_text=True)
    assert '<script>' not in html and '&lt;script&gt;' in html


def test_software_from_files(home):
    git = home / 'repo' / '.git'
    (git / 'refs' / 'heads').mkdir(parents=True)
    (git / 'HEAD').write_text('ref: refs/heads/main\n')
    (git / 'refs' / 'heads' / 'main').write_text('abc123\n')
    (home / 'venv' / 'lib' / 'python3.13' / 'site-packages' / 'pywikibot-11.9.0.dist-info').mkdir(parents=True)
    assert status.software() == {'commit': 'abc123', 'branch': 'main', 'pywikibot': '11.9.0', 'python': '3.13',
                                 'log_days': 0}

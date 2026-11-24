"""
Data of the status page: jobs and their logs, the archive run summaries
(written by userscripts/archive_resolved/summary.py), the bot account on the
wikis (wiki replicas) and the installed software. Only reads files and replicas.
"""
import datetime
import glob
import gzip
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import config
from wikis import BY_PROJECT, WIKIS

UTC = datetime.timezone.utc
DAY_DIR = re.compile(r'^\d{4}-\d{2}-\d{2}$')
LOG_TAIL_BYTES = 64 * 1024
LOG_TAIL_LINES = 15
PROBLEM_RE = re.compile(r'ERROR|CRITICAL|Traceback|Exception')


def now():
    return datetime.datetime.now(UTC)


def parse_time(value):
    """'2026-11-17T03:04:05Z' -> aware datetime (None stays None)."""
    if not value:
        return None
    return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)


# --- jobs ---------------------------------------------------------------------

def read_jobs(path=None):
    """The jobs of toolforge-jobs.yaml (a simple parser, no PyYAML); commented-out jobs are left out."""
    jobs = []
    with open(path or config.jobs_file, encoding='utf-8') as f:
        for line in f:
            if line.lstrip().startswith('#'):
                continue
            match = re.match(r'^\s*(-\s+)?([\w-]+):\s*(.*?)\s*$', line)
            if not match:
                continue
            new_item, key, value = match.groups()
            if new_item:
                jobs.append({})
            if jobs:
                jobs[-1][key] = value.strip('"\'')
    return [job for job in jobs if 'name' in job]


def archive_project(job):
    """'dewikipedia' for an archive-resolved job, else None."""
    match = re.search(r'archive-resolved-bot\.py\s+-project:(\w+)', job.get('command', ''))
    return match.group(1) if match else None


def _cron_field(field, low, high):
    values = set()
    for part in field.split(','):
        step = 1
        if '/' in part:
            part, step = part.split('/')
            step = int(step)
        if part == '*':
            start, end = low, high
        elif '-' in part:
            start, end = (int(x) for x in part.split('-'))
        else:
            start = end = int(part)
            if step != 1:
                end = high
        values.update(range(start, end + 1, step))
    return values


def next_run(schedule, after=None):
    """The next time (UTC) a 5-field cron schedule fires after *after*; None if it can't be parsed."""
    try:
        minute, hour, dom, month, dow = schedule.split()
        minutes, hours = _cron_field(minute, 0, 59), _cron_field(hour, 0, 23)
        doms, months = _cron_field(dom, 1, 31), _cron_field(month, 1, 12)
        dows = {d % 7 for d in _cron_field(dow, 0, 7)}
    except (ValueError, AttributeError):
        return None
    t = (after or now()).replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    day_any, dow_any = dom == '*', dow == '*'
    for _ in range(366 * 24 * 60):
        day_ok = t.day in doms if dow_any else (t.isoweekday() % 7 in dows if day_any else
                                                 t.day in doms or t.isoweekday() % 7 in dows)
        if t.month in months and day_ok:
            if t.hour in hours and t.minute in minutes:
                return t
            t += datetime.timedelta(minutes=1)
        else:
            t = (t + datetime.timedelta(days=1)).replace(hour=0, minute=0)
    return None


def interval(schedule):
    """Rough time between two runs, from the next two runs."""
    first = next_run(schedule)
    second = first and next_run(schedule, first)
    return (second - first) if second else None


def day_dirs(limit=None):
    """The day directories logs/YYYY-MM-DD, newest first."""
    try:
        names = sorted((n for n in os.listdir(config.log_dir) if DAY_DIR.match(n)), reverse=True)
    except OSError:
        return []
    return names[:limit] if limit else names


def find_log(name, days=9):
    """The newest copy of a log file: logs/<name>, else logs/<day>/<name>[.gz] of the last days
    (more than a week, for the weekly bot-stats job)."""
    candidates = [os.path.join(config.log_dir, name)]
    for day in day_dirs(days):
        candidates += [os.path.join(config.log_dir, day, name), os.path.join(config.log_dir, day, name + '.gz')]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _open_text(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='replace')
    return open(path, encoding='utf-8', errors='replace')


def _open_binary(path):
    return gzip.open(path, 'rb') if path.endswith('.gz') else open(path, 'rb')


def log_info(name):
    path = find_log(os.path.basename(name or ''))
    if path is None:
        return None
    try:
        stat = os.stat(path)
        if path.endswith('.gz'):
            with _open_text(path) as f:
                lines = f.read()[-LOG_TAIL_BYTES:].splitlines()
        else:
            with open(path, 'rb') as f:
                f.seek(max(0, stat.st_size - LOG_TAIL_BYTES))
                lines = f.read().decode('utf-8', 'replace').splitlines()
            if stat.st_size > LOG_TAIL_BYTES:
                lines = lines[1:]  # probably cut in the middle
    except OSError:
        return None
    modified = datetime.datetime.fromtimestamp(stat.st_mtime, UTC)
    return {'path': path, 'size': stat.st_size, 'modified': modified,
            'tail': lines[-LOG_TAIL_LINES:],
            'problems': [line for line in lines[-300:] if PROBLEM_RE.search(line)][-LOG_TAIL_LINES:]}


# the other services on the overview page (the archive jobs come from their run summaries,
# see archive_overview()); jobs are grouped by name
SERVICES = (
    ('sych', lambda job: job['name'] == 'archive-resolved-sych-bot-overview'),
    ('pb', lambda job: job['name'].startswith('pers-bek-')),
    ('mp', lambda job: job['name'] == 'mp-helper'),
    ('botstats', lambda job: job['name'].startswith('bot-stats')),
    ('login', lambda job: job['name'] == 'bot-login'),
    ('cleanup', lambda job: job['name'] == 'daily-log-cleanup'),
)


def job_status(job, at=None):
    at = at or now()
    logs = [log_info(job.get(key)) for key in ('filelog-stdout', 'filelog-stderr')]
    newest = max((log['modified'] for log in logs if log), default=None)
    every = interval(job.get('schedule', ''))
    # a log older than the interval plus some slack means the job did not run (or wrote nothing)
    slack = datetime.timedelta(hours=1) if every and every <= datetime.timedelta(hours=1) else datetime.timedelta(hours=3)
    stale = every is not None and (newest is None or at - newest > every + slack)
    silent = any(logs) and all(log['size'] == 0 for log in logs if log)
    problems = [line for log in logs if log for line in log['problems']]
    return dict(job, stdout=logs[0], stderr=logs[1], newest=newest, next=next_run(job.get('schedule', ''), at),
                stale=stale and not silent, problems=problems,
                state='stale' if stale and not silent else ('problems' if problems else 'ok'))


def services(jobs=None):
    """[(service key, [job status, ...], worst state)] in the order of SERVICES."""
    jobs = jobs if jobs is not None else read_jobs()
    result = []
    for key, matches in SERVICES:
        members = [job_status(job) for job in jobs if matches(job)]
        if members:
            result.append((key, members, worst(job['state'] for job in members)))
    return result


ORDER = ('ok', 'running', 'problems', 'stale', 'missing')


def worst(states):
    states = list(states)
    return max(states, key=ORDER.index) if states else 'missing'


# --- archive run summaries -------------------------------------------------------

def summary_files(project, days=None):
    """The summary files of a project, newest first: logs/ (today), then the day directories."""
    name = f'archive-resolved-{project}.jsonl'
    files = []
    path = os.path.join(config.log_dir, name)
    if os.path.isfile(path):
        files.append(path)
    for day in day_dirs(days):
        for candidate in (os.path.join(config.log_dir, day, name), os.path.join(config.log_dir, day, name + '.gz')):
            if os.path.isfile(candidate):
                files.append(candidate)
                break
    return files


_cache_lock = threading.Lock()
_run_cache = {}


# left out of the cached page records (the bulk of a summary file); page_record() reads them again
DETAIL_KEYS = ('sections', 'options')


def _summary_name(path):
    return os.path.basename(path).removesuffix('.gz')


def _last_run(path):
    """The last run in a summary file: {'run': header, 'end': end or None, 'path': path,
    'pages': {title: record without DETAIL_KEYS}}."""
    try:
        key = (path, os.stat(path).st_mtime, os.stat(path).st_size)
    except OSError:
        return None
    with _cache_lock:
        cached = _run_cache.get(path)
        if cached and cached[0] == key:
            return cached[1]
    run = None
    with _open_text(path) as f:
        for line in f:
            try:
                record = json.loads(line)
            except ValueError:
                continue  # a line cut off by a crash
            kind = record.get('type')
            if kind == 'run':
                run = {'run': record, 'end': None, 'pages': {}, 'path': path}
            elif run is None:
                continue
            elif kind == 'page':
                for detail in DETAIL_KEYS:
                    record.pop(detail, None)
                run['pages'][record['title']] = record
            elif kind == 'end':
                run['end'] = record
    with _cache_lock:
        # only one file per project: the path changes every night (daily-log-cleanup.sh)
        for old in [p for p in _run_cache if p != path and _summary_name(p) == _summary_name(path)]:
            del _run_cache[old]
        _run_cache[path] = (key, run)
    return run


def latest_run(project):
    for path in summary_files(project, days=3):
        run = _last_run(path)
        if run:
            return run
    return None


def run_state(run, job=None):
    """ok / running / problems / stale / missing for a run."""
    if run is None:
        return 'missing'
    started = parse_time(run['run'].get('started'))
    if run['end'] is None:
        # still running if it started within the last 6 hours, else it crashed
        return 'running' if started and now() - started < datetime.timedelta(hours=6) else 'problems'
    if not run['end'].get('complete'):
        return 'problems'
    if job is not None:
        every = interval(job.get('schedule', ''))
        if every and started and now() - started > every + datetime.timedelta(hours=3):
            return 'stale'
    by_status = run['end'].get('byStatus', {})
    return 'problems' if by_status.get('error') else 'ok'


def history(days=14):
    """End lines of logs/archive-runs.jsonl of the last days: {project: [record, ...]} newest first."""
    result = {}
    limit = now() - datetime.timedelta(days=days)
    try:
        with open(os.path.join(config.log_dir, 'archive-runs.jsonl'), encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                started = parse_time(record.get('started'))
                if started and started >= limit and not record.get('dryRun'):
                    result.setdefault(record.get('project'), []).append(record)
    except OSError:
        pass
    for records in result.values():
        records.sort(key=lambda r: r.get('started', ''), reverse=True)
    return result


def archive_overview(jobs=None, only=None):
    """One row per archive job (all wikis, or only the project *only*)."""
    jobs = jobs if jobs is not None else read_jobs()
    hist = history()
    rows = []
    for job in jobs:
        project = archive_project(job)
        if not project or (only and project != only):
            continue
        run = latest_run(project)
        counts = (run['end'] or {}).get('byStatus') if run and run['end'] else None
        if run and counts is None:  # running or crashed: count what is there
            counts = {}
            for record in run['pages'].values():
                counts[record['status']] = counts.get(record['status'], 0) + 1
        started = parse_time(run['run'].get('started')) if run else None
        finished = parse_time(run['end'].get('finished')) if run and run['end'] else None
        rows.append({'project': project, 'wiki': BY_PROJECT.get(project), 'job': job,
                     'minutes': int((finished - started).total_seconds() // 60) if started and finished else None,
                     'next': next_run(job.get('schedule', '')), 'run': run, 'state': run_state(run, job),
                     'counts': counts or {}, 'pages': len(run['pages']) if run else 0,
                     'archived': sum(r.get('toArchive', 0) for r in run['pages'].values()
                                     if r['status'] == 'archived') if run else 0,
                     'history': hist.get(project, [])})
    return rows


def find_pages(project, query, limit=50):
    """Titles of the latest run that contain *query* (case-insensitive, '_' = ' ')."""
    run = latest_run(project)
    if not run:
        return []
    needle = normalize_title(query).casefold()
    return sorted(t for t in run['pages'] if needle in t.casefold())[:limit]


def normalize_title(title):
    title = re.sub(r'[_\s]+', ' ', title or '').strip()
    return title


# how the line of a page starts in a summary file (see RunSummary.page)
_PAGE_LINE = re.compile(rb'\{"type":"page","title":("(?:[^"\\]|\\.)*"),"time":"([^"]*)","status":"(\w+)"')
# what a page history shows of a record
HISTORY_KEYS = ('toArchive', 'message', 'messageKey', 'messageArgs')
_index_cache = {}


def _page_index(path):
    """
    {title: [(offset of the line, time, status, HISTORY_KEYS of the record or None), ...]} of a summary
    file. Cached, so a page view does not read the whole files (20 MB a day for dewiki) again.
    Only lines of pages where something happened are parsed (a few of some thousand).
    """
    stat = os.stat(path)
    version = (stat.st_mtime, stat.st_size)
    with _cache_lock:
        cached = _index_cache.get(path)
        if cached and cached[0] == version:
            return cached[1]
    index = {}
    offset = 0
    with _open_binary(path) as f:
        for line in f:
            match = _PAGE_LINE.match(line)
            # a line without its end is still being written or was cut off by a crash
            if match and line.endswith(b'\n'):
                try:
                    title = json.loads(match.group(1))
                    details = None
                    if match.group(3) != b'nothing':
                        record = json.loads(line)
                        details = {key: record[key] for key in HISTORY_KEYS if key in record}
                except ValueError:
                    title = None
                if title is not None:
                    index.setdefault(sys.intern(title), []).append(
                        (offset, match.group(2).decode(), sys.intern(match.group(3).decode()), details))
            offset += len(line)
    with _cache_lock:
        _index_cache[path] = (version, index)
    return index


def _full_record(path, title, after=None):
    """The last full record of a page in a summary file (lines from the run started at *after*)."""
    entries = _page_index(path).get(title)
    if not entries or (after is not None and entries[-1][1] < after):
        return None
    with _open_binary(path) as f:
        f.seek(entries[-1][0])
        try:
            record = json.loads(f.readline())
        except ValueError:
            return None   # replaced since the index was made
    return record if record.get('title') == title else None


def page_record(project, title):
    """The full record of a page in the latest run; also finds the title with a capital first
    letter or in other case (if that is unique)."""
    run = latest_run(project)
    if not run:
        return None, None
    title = normalize_title(title)
    match = next((c for c in (title, title[:1].upper() + title[1:]) if c in run['pages']), None)
    if match is None:
        matches = [t for t in run['pages'] if t.casefold() == title.casefold()]
        match = matches[0] if len(matches) == 1 else None
    if match is None:
        return run, None
    try:
        record = _full_record(run['path'], match, run['run'].get('started'))
    except OSError:
        record = None
    return run, record or run['pages'][match]


def page_history(project, title, days=None):
    """What happened to a page (time, status, HISTORY_KEYS) in the summary files of the last days, newest first."""
    days = days or config.page_history_days
    files = summary_files(project, days=days)
    result = []
    for path in files:
        try:
            entries = _page_index(path).get(title, ())
        except (OSError, EOFError):
            continue
        result.extend(dict(details or {}, time=time, status=status) for _, time, status, details in reversed(entries))
    with _cache_lock:
        # forget the files of this project that are too old or were moved or compressed
        name = _summary_name(files[0]) if files else None
        for old in [p for p in _index_cache if _summary_name(p) == name and p not in files]:
            del _index_cache[old]
    result.sort(key=lambda r: r.get('time', ''), reverse=True)
    return result


def section_reason(page, section):
    """Why a section is (not) archived: (message key, values) for the page view."""
    if section.get('archiveTemplate'):
        return 'reason.archive_template', {}
    if section.get('doNotArchive'):
        return 'reason.do_not_archive', {}
    if section.get('archive'):
        if section.get('resolvedAge') and section['resolvedAge'] > page.get('age', 0):
            return 'reason.resolved_old', {'days': section['resolvedAge'], 'limit': page.get('age')}
        return 'reason.timeout', {'days': section.get('lastAge'), 'limit': page.get('timeout')}
    if section.get('resolvedAge'):
        return 'reason.resolved_young', {'days': section['resolvedAge'], 'limit': page.get('age')}
    if page.get('timeout'):
        return 'reason.not_resolved_timeout', {'days': section.get('lastAge'), 'limit': page.get('timeout')}
    return 'reason.not_resolved', {}


# --- bot account on the wikis (replicas) -----------------------------------------

_replica_cache = {'time': 0, 'data': None}


def _query_wiki(wiki, days=30):
    import pymysql  # only needed here
    result = {'wiki': wiki, 'error': None}
    try:
        conn = pymysql.connect(host=config.replica_host.format(dbname=wiki.dbname), database=wiki.dbname + '_p',
                               read_default_file=config.replica_cnf, charset='utf8mb4',
                               connect_timeout=5, read_timeout=15)
    except Exception as e:
        return dict(result, error=f'{type(e).__name__}: {e}')
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT user_id, user_editcount FROM user WHERE user_name = %s', (config.bot_user,))
            row = cur.fetchone()
            if row is None:
                return dict(result, error='no account')
            user_id, result['editcount'] = row
            cur.execute('SELECT ug_group FROM user_groups WHERE ug_user = %s', (user_id,))
            result['groups'] = sorted(g.decode() if isinstance(g, bytes) else g for (g,) in cur.fetchall())
            cur.execute('SELECT bl_expiry, bl_sitewide FROM block JOIN block_target ON bl_target = bt_id '
                        'WHERE bt_user = %s', (user_id,))
            result['blocks'] = [{'expiry': (e.decode() if isinstance(e, bytes) else e), 'sitewide': bool(s)}
                                for e, s in cur.fetchall()]
            cur.execute('SELECT actor_id FROM actor WHERE actor_name = %s', (config.bot_user,))
            row = cur.fetchone()
            result['last_edit'] = None
            result['per_day'] = {}
            if row:
                actor = row[0]
                cur.execute('SELECT rev_timestamp FROM revision_userindex WHERE rev_actor = %s '
                            'ORDER BY rev_timestamp DESC LIMIT 1', (actor,))
                row = cur.fetchone()
                if row:
                    stamp = row[0].decode() if isinstance(row[0], bytes) else row[0]
                    result['last_edit'] = datetime.datetime.strptime(stamp, '%Y%m%d%H%M%S').replace(tzinfo=UTC)
                since = (now() - datetime.timedelta(days=days - 1)).strftime('%Y%m%d000000')
                cur.execute('SELECT LEFT(rev_timestamp, 8), COUNT(*) FROM revision_userindex '
                            'WHERE rev_actor = %s AND rev_timestamp >= %s GROUP BY LEFT(rev_timestamp, 8)',
                            (actor, since))
                result['per_day'] = {(d.decode() if isinstance(d, bytes) else d): n for d, n in cur.fetchall()}
    except Exception as e:
        result['error'] = f'{type(e).__name__}: {e}'
    finally:
        conn.close()
    return result


def bot_accounts(days=30):
    """Bot account on every wiki, cached for config.replica_cache_seconds."""
    if not config.replica_host:
        return None
    with _cache_lock:
        if _replica_cache['data'] is not None and time.time() - _replica_cache['time'] < config.replica_cache_seconds:
            return _replica_cache['data']
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(_query_wiki, WIKIS))
    day_keys = [(now() - datetime.timedelta(days=i)).strftime('%Y%m%d') for i in range(days - 1, -1, -1)]
    for row in rows:
        per_day = row.get('per_day') or {}
        row['days'] = [per_day.get(d, 0) for d in day_keys]
        row['edits_7'] = sum(row['days'][-7:])
        row['edits_30'] = sum(row['days'])
        row['max_day'] = max(row['days'] or [0])
        row['bot_flag'] = 'bot' in (row.get('groups') or [])
    data = {'rows': rows, 'time': now(), 'day_keys': day_keys}
    with _cache_lock:
        _replica_cache.update(time=time.time(), data=data)
    return data


# --- software ----------------------------------------------------------------------

def git_head(repo=None):
    """(commit, branch) of the bot repository, read from .git without the git binary."""
    git = os.path.join(repo or config.repo_dir, '.git')
    try:
        with open(os.path.join(git, 'HEAD'), encoding='utf-8') as f:
            head = f.read().strip()
        if not head.startswith('ref: '):
            return head, None
        ref = head[5:]
        path = os.path.join(git, ref)
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                return f.read().strip(), ref.rsplit('/', 1)[-1]
        with open(os.path.join(git, 'packed-refs'), encoding='utf-8') as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref:
                    return parts[0], ref.rsplit('/', 1)[-1]
    except OSError:
        pass
    return None, None


def package_version(name, venv=None):
    """Version of a package in the bot venv, from its *.dist-info directory."""
    pattern = os.path.join(venv or config.venv_dir, 'lib', 'python*', 'site-packages', f'{name}-*.dist-info')
    for path in sorted(glob.glob(pattern)):
        return os.path.basename(path)[len(name) + 1:-len('.dist-info')]
    return None


def software():
    commit, branch = git_head()
    pythons = sorted(glob.glob(os.path.join(config.venv_dir, 'lib', 'python*')))
    return {'commit': commit, 'branch': branch, 'pywikibot': package_version('pywikibot'),
            'python': os.path.basename(pythons[-1])[len('python'):] if pythons else None,
            'log_days': len(day_dirs())}

"""
State of the last full run: which pages need not be read again.

A page where nothing was archived stays that way until somebody edits it or a section gets
old enough. The run summary (summary.py) stores both for every page with status "nothing":
"revid" (the examined revision) and "nextDue" (when the first section gets due, null = never
without an edit). A full run skips a page if its latest revision is still the same and nextDue
is not reached. Everything else (errors, skipped or archived pages, ...) is always read.

The state is only used if it was written by the same bot code (codeVersion) and if the page
was read within the last MAX_AGE, so every page is really read once a week. The option -full
ignores the state.
"""
import glob
import gzip
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from archive_resolved.summary import parseTime, summaryPath

# A page is read again when its nextDue is closer than this. Covers the change between
# summer and winter time (the age is calculated in the local time of the wiki).
DUE_BUFFER = timedelta(hours=2)
# A bit less than a week: a run starting at the same time of day 7 days later reads the page again.
MAX_AGE = timedelta(days=6, hours=12)

SOURCE_DIRS = ('archive_resolved', 'archive_resolved_localization')


def codeVersion() -> str:
    """Hash of the bot code (with messages.json); changed code may decide differently."""
    userscripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    digest = hashlib.sha256()
    for directory in SOURCE_DIRS:
        for path in sorted(glob.glob(os.path.join(userscripts, directory, '*'))):
            if path.endswith(('.py', '.json')):
                digest.update(os.path.relpath(path, userscripts).encode() + b'\0')
                with open(path, 'rb') as f:
                    digest.update(f.read() + b'\0')
    return digest.hexdigest()[:16]


def summaryFiles(logDir: str, project: str, now: datetime) -> list:
    """Summary files of a project, newest first: logs/, then the day directories (see daily-log-cleanup.sh)."""
    name = os.path.basename(summaryPath(logDir, project))
    candidates = [os.path.join(logDir, name)]
    for days in range(MAX_AGE.days + 2):
        day = (now - timedelta(days=days)).strftime('%Y-%m-%d')
        candidates += [os.path.join(logDir, day, name), os.path.join(logDir, day, name + '.gz')]
    return [path for path in candidates if os.path.isfile(path)]


def _readPages(path: str, code: str):
    """({title: line of the last record usable as state}, whether there is any page record in the file)"""
    pages, anyPage, sameCode = {}, False, False
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rb') as f:
        for line in f:
            try:
                record = json.loads(line)
            except ValueError:
                continue   # a line cut off by a crash
            if not isinstance(record, dict):
                continue
            if record.get('type') == 'run':
                sameCode = record.get('code') == code
            elif record.get('type') == 'page':
                anyPage = True
                title = record.get('title')
                if sameCode and record.get('status') == 'nothing' \
                        and all(key in record for key in ('revid', 'nextDue', 'checked', 'time')):
                    pages[title] = line
                else:
                    pages.pop(title, None)
    return pages, anyPage


class RunState:
    def __init__(self, pages: dict = None):
        """pages: {title: JSON line of the page record (bytes)}; kept as text because of the memory limit of the jobs"""
        self.pages = pages or {}

    @classmethod
    def load(cls, logDir: str, project: str, code: str, now: datetime = None):
        """
            The state from the newest summary file. Must be called before this run writes its own records.
        """
        now = now or datetime.now(timezone.utc)
        for path in summaryFiles(logDir, project, now):
            pages, anyPage = _readPages(path, code)
            if anyPage:
                return cls(pages)
        return cls()

    def unchanged(self, title: str, revid, now: datetime = None):
        """
            The last record of the page if it need not be read again, else None.
            revid: the latest revision of the page (None = unknown); now: aware datetime
        """
        line = self.pages.get(title)
        if line is None or not revid:
            return None
        now = now or datetime.now(timezone.utc)
        record = json.loads(line)
        if record['revid'] != revid:
            return None
        checked = parseTime(record['checked'])
        if not timedelta(0) <= now - checked < MAX_AGE:
            return None
        if record['nextDue'] is not None and now >= parseTime(record['nextDue']) - DUE_BUFFER:
            return None
        return record

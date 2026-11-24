"""
Machine-readable summary of an archive run, for the status web page (web/).

One JSON object per line (JSON Lines), appended while the bot runs, so the page
shows the progress of a running job and a crashed run is visible (no "end" line):

    {"type": "run",  "project": ..., "started": ..., "dryRun": ..., "code": ...}
    {"type": "page", "title": ..., "status": ..., ...}     one per page
    {"type": "end",  "finished": ..., "pages": ..., "byStatus": {...}, ...}

The file is logs/archive-resolved-<project>.jsonl next to the job's .out/.err;
daily-log-cleanup.sh moves it to logs/YYYY-MM-DD/ and gzips it later.
The "end" line (with project, started and dryRun) is also appended to
logs/archive-runs.jsonl, a small history of all runs that stays in place.

Page status values:
    nothing       nothing to archive
    archived      sections were archived (origin page saved)
    dryrun        would have archived (dry run)
    skipped       not archived for a reason given in "message" (protection, redirect, edit conflict, ...)
    optionserror  the template options are wrong or missing ("message")
    error         error while archiving ("message"; the details are in the .err log)
    excluded      on the exclude list of the project

Pages with status "nothing" also have "revid", "nextDue" and "checked": the state for the next
run (see state.py). A page that was skipped because of this state keeps its record, with the
current time, the ages moved on and "unchanged": true; "checked" is when it was really read.
"code" in the "run" line is the version of the bot code for the project (state.codeVersion).

"message" is in the language of the wiki; "messageKey" and "messageArgs" are the same
message as key + arguments of archive_resolved_localization/messages.json, so the status
page can show it in the language chosen there.
"""
import json
import os
from collections import Counter
from datetime import datetime, timezone

STATUSES = ('nothing', 'archived', 'dryrun', 'skipped', 'optionserror', 'error', 'excluded')


# records of unchanged pages are written together, opening the file (NFS) for each one takes too long
MAX_BUFFER = 200


def formatTime(time: datetime) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ')


def parseTime(text: str) -> datetime:
    return datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def utcnow() -> str:
    return formatTime(datetime.now(timezone.utc))


def summaryPath(logDir: str, project: str) -> str:
    return os.path.join(logDir, f'archive-resolved-{project}.jsonl')


def historyPath(summaryFile: str) -> str:
    return os.path.join(os.path.dirname(summaryFile), 'archive-runs.jsonl')


def documentRecord(wdoc) -> dict:
    """The options and the sections of a WikiDocument (after examineDiscussions/prepareArchiving)."""
    sections = []
    for number, disc in enumerate(wdoc.listDiscussions, 1):
        try:
            target = disc.determineArchivingTarget(wdoc) if wdoc.archivingTargetPattern else None
        except Exception:
            target = None
        sections.append({
            'n': number,
            'title': disc.getTitleClear(),
            'level': disc.getHeadlineLevel(),
            'firstAge': round(disc.getFirstContributionAge(), 2),
            'lastAge': round(disc.lastContributionAge, 2),
            'signatures': disc.getNumberOfContributions(),
            'resolvedAge': round(disc.getAgeByResolvedTemplate(), 2) or None,
            'doNotArchive': disc.hasDoNotArchiveTmpl,
            'archiveTemplate': disc.hasArchiveTemplate,
            'archive': disc.shouldBeArchived(wdoc.thresholdAgeResolvedTemplate, wdoc.thresholdAgeByTimeout),
            'target': target,
        })
    return {
        'options': getattr(wdoc, 'options', {}),
        'age': wdoc.thresholdAgeResolvedTemplate,
        'timeout': wdoc.thresholdAgeByTimeout or None,
        'targetPattern': wdoc.archivingTargetPattern,
        'level': wdoc.headlineLevel,
        'timeCompareResolved': wdoc.archivingUseTimeComparatorCleared,
        'lastEdit': wdoc.lastEditTime.strftime('%Y-%m-%dT%H:%M:%SZ') if wdoc.lastEditTime else None,
        'lastUser': wdoc.lastUser,
        'sections': sections,
        'toArchive': wdoc.numberOfDiscussionsToArchive,
        'targets': dict(wdoc.archiveJobCounterByTarget),
    }


def stateRecord(wdoc) -> dict:
    """What the next run needs to know to skip the page (see state.py); only if nothing was to be archived."""
    if not wdoc.revid or wdoc.examinedAt is None:
        return {}
    nextDue = wdoc.nextDue()
    return {'revid': wdoc.revid, 'nextDue': formatTime(nextDue) if nextDue else None,
            'checked': formatTime(wdoc.examinedAt)}


def _moveAges(record: dict, time: str):
    """Moves the ages of the sections on to the given time."""
    days = (parseTime(time) - parseTime(record['time'])).total_seconds() / 86400
    for section in record.get('sections', ()):
        if section.get('signatures'):   # without a signature the ages are 0
            section['firstAge'] = round(section['firstAge'] + days, 2)
            section['lastAge'] = round(section['lastAge'] + days, 2)
        if section.get('resolvedAge') is not None:
            section['resolvedAge'] = round(section['resolvedAge'] + days, 2)


class RunSummary:
    def __init__(self, path: str, project: str, dryRun: bool, history: str = None, code: str = None):
        """history: file for the end line of every run; None = archive-runs.jsonl next to path
        code: version of the bot code (state.codeVersion)"""
        self.path = path
        self.history = history or historyPath(path)
        self.project = project
        self.dryRun = dryRun
        self.started = utcnow()
        self.counts = Counter()
        self.archivedSections = 0
        self.pages = 0
        self.unchangedPages = 0
        self.buffer = []   # records of unchanged pages that are not written yet
        self._endCutOffLine()
        self._write({'type': 'run', 'project': project, 'started': self.started, 'dryRun': dryRun, 'code': code})

    @staticmethod
    def _line(record: dict) -> str:
        return json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n'

    def _endCutOffLine(self):
        """After a crash the file may end within a line; the next record must not be appended to it."""
        try:
            with open(self.path, 'rb+') as f:
                if f.seek(0, os.SEEK_END) > 0:
                    f.seek(-1, os.SEEK_END)
                    if f.read(1) != b'\n':
                        f.write(b'\n')
        except FileNotFoundError:
            pass

    def _write(self, record: dict, path: str = None):
        # whole lines per write and an immediate flush: a reader sees whole lines only
        self._flush()
        with open(path or self.path, 'a', encoding='utf-8') as f:
            f.write(self._line(record))

    def _flush(self):
        if self.buffer:
            lines, self.buffer = self.buffer, []
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(''.join(lines))

    def unchanged(self, record: dict):
        """A page that was not read because of its state: its last record stays valid."""
        time = utcnow()
        _moveAges(record, time)
        self.buffer.append(self._line(dict(record, time=time, unchanged=True)))
        self.pages += 1
        self.unchangedPages += 1
        self.counts[record['status']] += 1
        if len(self.buffer) >= MAX_BUFFER:
            self._flush()

    def page(self, title: str, status: str, message: str = None, wdoc=None,
             messageKey: str = None, messageArgs: dict = None):
        record = {'type': 'page', 'title': title, 'time': utcnow(), 'status': status}
        if message:
            record['message'] = message
        if messageKey:
            record['messageKey'] = messageKey
            record['messageArgs'] = messageArgs or {}
        if wdoc is not None and wdoc.archivingTargetPattern is not None:
            try:
                record.update(documentRecord(wdoc))
                if status == 'nothing':
                    record.update(stateRecord(wdoc))
            except Exception as e:  # never let the summary break the bot
                record['summaryError'] = repr(e)
        elif wdoc is not None and getattr(wdoc, 'options', None):
            record['options'] = wdoc.options   # e.g. a template error: show what was given
        self.pages += 1
        self.counts[status] += 1
        if status == 'archived':
            self.archivedSections += record.get('toArchive', 0)
        self._write(record)

    def end(self, finished: bool):
        record = {'type': 'end', 'finished': utcnow() if finished else None, 'complete': finished,
                  'pages': self.pages, 'unchanged': self.unchangedPages, 'archivedSections': self.archivedSections,
                  'byStatus': dict(self.counts)}
        self._write(record)
        self._write(dict(record, project=self.project, started=self.started, dryRun=self.dryRun), self.history)

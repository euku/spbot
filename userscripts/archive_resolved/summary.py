"""
Machine-readable summary of an archive run, for the status web page (web/).

One JSON object per line (JSON Lines), appended while the bot runs, so the page
shows the progress of a running job and a crashed run is visible (no "end" line):

    {"type": "run",  "project": ..., "started": ..., "dryRun": ...}
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
    error         unexpected error ("message" = last line of the traceback)
    excluded      on the exclude list of the project
"""
import json
import os
from collections import Counter
from datetime import datetime, timezone

STATUSES = ('nothing', 'archived', 'dryrun', 'skipped', 'optionserror', 'error', 'excluded')


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


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


class RunSummary:
    def __init__(self, path: str, project: str, dryRun: bool, history: str = None):
        """history: file for the end line of every run; None = archive-runs.jsonl next to path"""
        self.path = path
        self.history = history or historyPath(path)
        self.project = project
        self.dryRun = dryRun
        self.started = utcnow()
        self.counts = Counter()
        self.archivedSections = 0
        self.pages = 0
        self._write({'type': 'run', 'project': project, 'started': self.started, 'dryRun': dryRun})

    def _write(self, record: dict, path: str = None):
        # one line per write and an immediate flush: a reader sees whole lines only
        with open(path or self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')

    def page(self, title: str, status: str, message: str = None, wdoc=None):
        record = {'type': 'page', 'title': title, 'time': utcnow(), 'status': status}
        if message:
            record['message'] = message
        if wdoc is not None and wdoc.archivingTargetPattern is not None:
            try:
                record.update(documentRecord(wdoc))
            except Exception as e:  # never let the summary break the bot
                record['summaryError'] = repr(e)
        self.pages += 1
        self.counts[status] += 1
        if status == 'archived':
            self.archivedSections += record.get('toArchive', 0)
        self._write(record)

    def end(self, finished: bool):
        record = {'type': 'end', 'finished': utcnow() if finished else None, 'complete': finished,
                  'pages': self.pages, 'archivedSections': self.archivedSections,
                  'byStatus': dict(self.counts)}
        self._write(record)
        self._write(dict(record, project=self.project, started=self.started, dryRun=self.dryRun), self.history)

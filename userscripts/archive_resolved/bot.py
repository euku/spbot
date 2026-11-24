"""
ArchiveRobot: command line handling and the loop over all pages that use the
archive template. The page logic lives in archive_resolved.core.
"""
import os               # used for os.getcwd()
import sys
import traceback
import pywikibot        # Wikipedia-pybot-framework
from pywikibot import pagegenerators
from time import localtime, strftime
from archive_resolved_localization.local_bot_factory import LocalBotFactory
from archive_resolved.core import ArchivingError, OptionsError, WikiDocument
from archive_resolved.state import RunState, codeVersion
from archive_resolved.summary import RunSummary, summaryPath
from archive_resolved_localization.messages import formatMessage


def _isTooBig(exc) -> bool:
    """Whether the exception (or one it wraps) is MediaWiki's 'contenttoobig' (page larger than allowed)."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if getattr(exc, 'code', None) == 'contenttoobig' or 'contenttoobig' in str(exc) \
                or ('kilobytes long' in str(exc) and 'maximum' in str(exc)):
            return True
        exc = getattr(exc, 'reason', None) or exc.__cause__ or exc.__context__
    return False


def errorMessage(exc, wdoc, detail: str):
    """Message key + arguments for an unexpected error while working on a page."""
    target = getattr(wdoc, 'failedTarget', None)
    if target and _isTooBig(exc):
        return 'error.too_big', {'target': target}
    if target:
        return 'error.not_saved', {'target': target, 'detail': detail}
    return 'error.unexpected', {'detail': detail}


def parseArgs(args) -> dict:
    """
        Parses the bot specific arguments (the ones left over by pywikibot.handle_args()).
        Returns a dict with the keys dryRun, project, page, saveLocalLogFile, summary, full.
        project is None if '-project' was given without a value.
        An unknown argument stops the bot: it may be a misspelled '-dryrun'.
    """
    options = {'dryRun': False, 'project': 'dewikipedia', 'page': None, 'saveLocalLogFile': False, 'summary': True,
               'full': False}
    for arg in args:
        if arg == '-dryrun':
            options['dryRun'] = True
        elif arg == '-project' or arg.startswith('-project:'):
            options['project'] = arg[9:] if len(arg) > 8 else None
        elif arg == '-page' or arg.startswith('-page:'):
            if len(arg) == 5:
                raise ArchivingError("'-page' used but no page given")
            options['page'] = arg[6:]
        elif arg == '-nolocallog':
            options['saveLocalLogFile'] = False
        elif arg == '-nosummary':
            options['summary'] = False
        elif arg == '-full':
            options['full'] = True
        else:
            raise ArchivingError(f"unknown argument '{arg}'")
    return options


class ArchiveRobot:
    """
        A bot that can archive.
    """
    def __init__(self, args=None):
        """
            args: bot arguments; None = read them from the command line via pywikibot.handle_args()
        """
        options = parseArgs(pywikibot.handle_args() if args is None else args)
        self.dryRun = options['dryRun'] # Weather to save pages to wikipedia or not.... False means to save
        self.saveLocalLogFile = options['saveLocalLogFile']
        self.generator = None
        self.localBot = None
        self.summary = None
        self.state = RunState()
        currentProject = options['project']
        pageToWorkOn = options['page']
        if currentProject is None: # '-project' without value
            currentProject = pywikibot.input('Which project to work on? [dewikipedia, dewiktionary, dewikiversity, enwikisource, dewikisource, commons, wikidata, wikimania, species]')

        self.localBot = LocalBotFactory().createLocalBot(currentProject)
        self.site = pywikibot.Site(code=self.localBot.projectCode, fam=self.localBot.projectFamily)
        pywikibot.output(f'Created localbot with code={self.localBot.projectCode}, fam={self.localBot.projectFamily}')

        if pageToWorkOn != None:
            self.generator = [pywikibot.Page(self.site, pageToWorkOn)]
        else:
            mainTemplatePage = pywikibot.Page(self.site, self.localBot.archiveTemplateName)
            self.generator = mainTemplatePage.getReferences(False, True, True, False)
            logDir = os.path.join(os.getcwd(), 'logs')
            code = codeVersion(self.localBot)
            if not options['full']:
                self.state = self._loadState(logDir, currentProject, code)
            # summary for the status web page, only for full runs (a single -page run would replace it)
            if options['summary']:
                self.summary = RunSummary(summaryPath(logDir, currentProject), currentProject, self.dryRun, code=code)
        
        self.localLogFile = os.getcwd() + strftime(f"/logs/archiv-{currentProject}-%Y-%m-%d.log", localtime())

    @staticmethod
    def _loadState(logDir, project, code):
        """The state of the last run; empty (= read all pages) if it cannot be read."""
        try:
            state = RunState.load(logDir, project, code)
        except Exception:
            pywikibot.output("Could not read the state of the last run: " + traceback.format_exc())
            state = RunState()
        pywikibot.output(f"State of the last run: {len(state.pages)} pages")
        return state

    def _changedPages(self, pages):
        """
            Only the pages that must be read. The latest revision ID comes with the page list
            (pywikibot's PageGenerator asks for prop=info), so this needs no further requests.
        """
        for page in pages:
            try:
                # not latest_revision_id: this would load the revision if it were missing
                record = self.state.unchanged(page.title(), getattr(page, '_revid', None))
                if record is not None and self.summary is not None:
                    self.summary.unchanged(record)
            except Exception:
                pywikibot.output("Could not use the state of the last run: " + traceback.format_exc())
                record = None
            if record is None:
                yield page

    def _record(self, title, status, wdoc=None, key=None, args=None):
        """key/args: message (messages.json); recorded in the language of the wiki and as key"""
        summary = getattr(self, 'summary', None)
        if summary is None:
            return
        try:
            message = formatMessage(self.localBot.language, key, args) if key else None
            summary.page(title, status, message, wdoc, key, args)
        except Exception:
            pywikibot.output("Could not write the run summary: " + traceback.format_exc())

    def _runOnPage(self, page):
        wdoc = None
        try:
            if page.title() in self.localBot.excludeList:
                pywikibot.output("Skipping page: " + page.title())
                self._record(page.title(), 'excluded')
                return
            pywikibot.output("Check page: " + page.title())
            wdoc = WikiDocument.fromPage(page, self)
            wdoc.findOptions()
            wdoc.divideIntoSlices()
            wdoc.examineDiscussions()
            wdoc.prepareArchiving()
            wdoc.generateReport()
            wdoc.saveReport(self.saveLocalLogFile, self.localLogFile)
            if wdoc.hasWorkToDo():
                wdoc.executeArchiving()
                self._record(page.title(), wdoc.outcome or 'skipped', wdoc, wdoc.outcomeKey, wdoc.outcomeArgs)
            else:
                self._record(page.title(), 'nothing', wdoc)

        except OptionsError as no:
            # Write error report to the same page
                pywikibot.output("\t<<lightpurple>>Report error for %s<<default>>\n" % page.title())
                pywikibot.output("Reason was: " + no.getMsg())
                page = pywikibot.Page(self.site, page.title())
                if not self.dryRun and (page.get().find(self.localBot.errorCategory) == -1):
                    # paste only, if there is no such message; in the language of the wiki
                    hintMsg = no.getMsg(self.localBot.language, wiki=True) + ' '
                    page.put(page.get() + "\n\n" + (self.localBot.errorText % hintMsg), summary=self.localBot.errorTextSummary, bot=False, minor=False, force=False)
                if wdoc is not None:
                    wdoc.generateErrorReport()
                    wdoc.saveReport(self.saveLocalLogFile, self.localLogFile)
                self._record(page.title(), 'optionserror', wdoc, no.key, no.msgArgs)
        except BaseException as exc:  # like the former bare except: record everything
            pywikibot.output("\n<<lightpurple>>Error at %s<<default>> skip page\n" % page.title())
            pywikibot.output("Unexpected error: " + str(traceback.format_exc()))
            if wdoc is not None:
                wdoc.generateErrorReport()
                wdoc.saveReport(self.saveLocalLogFile, self.localLogFile)
            lastLine = (traceback.format_exc().strip().splitlines()[-1:] or [''])[0][:500]
            key, args = errorMessage(exc, wdoc, lastLine)
            self._record(page.title(), 'error', wdoc, key, args)

    def run(self):
        """
             Begin archiving
        """
        self.generator = pagegenerators.PreloadingGenerator(self._changedPages(self.generator), groupsize = 5)
        finished = False
        try:
            for page in self.generator:
                try:
                    self._runOnPage(page)
                except:
                    # Catch everything and don't let the bot stop.
                    # This can happen when an exception was raised inside the exception handling.
                    pywikibot.output(f"\n<<lightpurple>>Unexpected error: {str(sys.exc_info())}<<default>>\n")
            finished = True
        finally:
            if self.summary is not None:
                try:
                    self.summary.end(finished)
                except Exception:
                    pywikibot.output("Could not write the run summary: " + traceback.format_exc())

        # Everything is done, so stop it
        pywikibot.output("# Bot finished #")


def main():
    try:
        bot = ArchiveRobot()
        bot.run()
    finally:
        pywikibot.stopme()

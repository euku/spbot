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
from archive_resolved.summary import RunSummary, summaryPath


def parseArgs(args) -> dict:
    """
        Parses the bot specific arguments (the ones left over by pywikibot.handle_args()).
        Returns a dict with the keys dryRun, project, page, saveLocalLogFile, summary.
        project is None if '-project' was given without a value.
    """
    options = {'dryRun': False, 'project': 'dewikipedia', 'page': None, 'saveLocalLogFile': False, 'summary': True}
    for arg in args:
        if arg == '-dryrun':
            options['dryRun'] = True
        elif arg.startswith('-project'):
            options['project'] = arg[9:] if len(arg) > 8 else None
        elif arg.startswith('-page'):
            if len(arg) == 5:
                raise ArchivingError("'-page' used but no page given")
            options['page'] = arg[6:]
        elif arg == '-nolocallog':
            options['saveLocalLogFile'] = False
        elif arg == '-nosummary':
            options['summary'] = False
        else:
            pywikibot.output(arg + " was ignored")
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
            # summary for the status web page, only for full runs (a single -page run would replace it)
            if options['summary']:
                self.summary = RunSummary(summaryPath(os.path.join(os.getcwd(), 'logs'), currentProject),
                                          currentProject, self.dryRun)
        
        self.localLogFile = os.getcwd() + strftime(f"/logs/archiv-{currentProject}-%Y-%m-%d.log", localtime())

    def _record(self, title, status, message=None, wdoc=None):
        summary = getattr(self, 'summary', None)
        if summary is None:
            return
        try:
            summary.page(title, status, message, wdoc)
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
                self._record(page.title(), wdoc.outcome or 'skipped', wdoc.outcomeMessage, wdoc)
            else:
                self._record(page.title(), 'nothing', None, wdoc)

        except OptionsError as no:
            # Write error report to the same page
                pywikibot.output("\t<<lightpurple>>Report error for %s<<default>>\n" % page.title())
                hintMsg = no.getMsg() or ''
                pywikibot.output("Reason was: " + hintMsg)
                page = pywikibot.Page(self.site, page.title())
                if not self.dryRun and (page.get().find(self.localBot.errorCategory) == -1):
                    # paste only, if there is no such message
                    page.put(page.get() + "\n\n" + (self.localBot.errorText % hintMsg), summary=self.localBot.errorTextSummary, bot=False, minor=False, force=False)
                if wdoc is not None:
                    wdoc.generateErrorReport()
                    wdoc.saveReport(self.saveLocalLogFile, self.localLogFile)
                self._record(page.title(), 'optionserror', hintMsg, wdoc)
        except:
            pywikibot.output("\n<<lightpurple>>Error at %s<<default>> skip page\n" % page.title())
            pywikibot.output("Unexpected error: " + str(traceback.format_exc()))
            if wdoc is not None:
                wdoc.generateErrorReport()
                wdoc.saveReport(self.saveLocalLogFile, self.localLogFile)
            lastLine = traceback.format_exc().strip().splitlines()[-1:] or ['']
            self._record(page.title(), 'error', lastLine[0][:500], wdoc)

    def run(self):
        """
             Begin archiving
        """
        self.generator = pagegenerators.PreloadingGenerator(self.generator, groupsize = 5)
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

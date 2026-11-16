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
from archive_resolved.core import ArchivingError, NoOptions, WikiDocument


def parseArgs(args) -> dict:
    """
        Parses the bot specific arguments (the ones left over by pywikibot.handle_args()).
        Returns a dict with the keys dryRun, project, page, saveLocalLogFile.
        project is None if '-project' was given without a value.
    """
    options = {'dryRun': False, 'project': 'dewikipedia', 'page': None, 'saveLocalLogFile': False}
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
        
        self.localLogFile = os.getcwd() + strftime(f"/logs/archiv-{currentProject}-%Y-%m-%d.log", localtime())

    def _runOnPage(self, page):
        try:
            if page.title() in self.localBot.excludeList:
                pywikibot.output("Skipping page: " + page.title())
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

        except NoOptions as no:
            # Write error report to the same page
                pywikibot.output("\t<<lightpurple>>Report error for %s<<default>>\n" % page.title())
                hintMsg = no.getMsg() if no.getMsg() != None else ''
                pywikibot.output("Reason was: " + hintMsg)
                page = pywikibot.Page(self.site, page.title())
                if not self.dryRun and (page.get().find(self.localBot.errorCategory) == -1):
                    # paste only, if there is no such message
                    page.put(page.get() + "\n\n" + (self.localBot.errorText % hintMsg), summary=self.localBot.errorTextSummary, bot=False, minor=False, force=False)
                wdoc.generateErrorReport()
                wdoc.saveReport(self.saveLocalLogFile, self.localLogFile)
        except:
            pywikibot.output("\n<<lightpurple>>Error at %s<<default>> skip page\n" % page.title())
            pywikibot.output("Unexpected error: " + str(traceback.format_exc()))
            wdoc.generateErrorReport()
            wdoc.saveReport(self.saveLocalLogFile, self.localLogFile)

    def run(self):
        """
             Begin archiving
        """
        self.generator = pagegenerators.PreloadingGenerator(self.generator, groupsize = 5)
        for page in self.generator:
            try:
                self._runOnPage(page)
            except:
                # Catch everything and don't let the bot stop.
                # This can happen when an exception was raised inside the exception handling.
                pywikibot.output(f"\n<<lightpurple>>Unexpected error: {str(sys.exc_info())}<<default>>\n")
        
        # Everything is done, so stop it
        pywikibot.output("# Bot finished #")


def main():
    try:
        bot = ArchiveRobot()
        bot.run()
    finally:
        pywikibot.stopme()

"""
Core of the archive-resolved bot: parsing of talk pages, deciding which sections
to archive and writing them to their archive pages.

All site access goes through ``bot.site`` (and pywikibot.Page on it), so the
classes can be tested with a fake site.
"""
import re               # Used for regular expressions
import traceback
import pywikibot        # Wikipedia-pybot-framework
from pywikibot import textlib
from time import localtime, sleep, strftime, mktime    # strftime-Function and related
from datetime import datetime

#
# Local exceptions
#
class ArchivingError(Exception):
    """Archiving error"""

class NoOptions(ArchivingError):
    def __init__(self, msg=None):
        pywikibot.output("\t *** No archive template found or wrong format ***\n")
        self.msg = msg

    def getMsg(self):
        return self.msg

class WrongOptions(ArchivingError):
    def __init__(self):
        pywikibot.output("\t *** Parameters have a wrong format ***\n")

#
# *** DECLARATIONS ***
#
class Discussion:
    def __init__(self, pageOriginName: str):
        self.titleOffsetStart    = 0      # offset, where title of disc starts
        self.title               = ""     # Title of disc
        self.titleClear          = ""
        self.hasDoNotArchiveTmpl = False  # is a temple used for this section, that denies archiving
        self.contentOffsetStart  = 0      # offset, where text starts
        self.contentOffsetEnd    = 0      # offset, where text ends
        self.content             = ""     # content of disc/section
        self.firstContributionAge = 0.0    # How old is the discussion? in days
        self.lastContributionAge = 0.0     # How old is the last timestamp? in days
        self.timestampClearedFlag= None    # The timestamp found in the clead template
        self.ageByResolvedTemplate = 0     # How long this discussion has a resolved flag in days. 0 if not resolved
        self.numberOfContributions = 0     # How many contributions were made to this discussion
        self.firstContribution   = None    # Date of the first contribution
        self.headlineLevel       = 0       # depth of headline-level
        self.pageOrigin          = pageOriginName # Name of the Page the discussion is from

    def __repr__(self):
        pass

    def setTitle(self, title, titleClear = ""):
        """
        Sets the Titletext of a discussion.
        """
        self.title = title
        self.titleClear = titleClear.strip()

    def getTitle(self):
        return self.title
    
    def getTitleClear(self):
        return self.titleClear

    def setTitleOffsetStart(self, titleOffsetStart):
        """
        Sets the offset where a title starts.
        """
        self.titleOffsetStart = titleOffsetStart

    def getTitleOffsetStart(self):
        """
        Returns the offset where a title starts.
        """
        return self.titleOffsetStart

    def setContentOffsetStart(self, contentOffsetStart):
        self.contentOffsetStart = contentOffsetStart

    def setContentOffsetEnd(self, contentOffsetEnd):
        self.contentOffsetEnd = contentOffsetEnd

    def getContentOffsetEnd(self):
        return self.contentOffsetEnd

    def retrieveContent(self, text):
        self.content = text[self.titleOffsetStart:self.contentOffsetEnd]

    def setContent(self, content = ""):
        self.content = content

    def setHeadlineLevel(self, headlineLevel):
        self.headlineLevel = headlineLevel

    def getHeadlineLevel(self):
        return self.headlineLevel

    def examine(self, bot, now: datetime = None):
        """
            now: current time (naive, UTC); defaults to datetime.now(). Tests pass a fixed value.
        """
        # Extract dates from content
        if now is None:
            now = datetime.now()
        clearedContent = WikiDocument.removeCommentsAndOther(self.content)
        self._examineAllTimestamps(bot, clearedContent, now)
        self._examineAllResolvedTemplate(bot, clearedContent, now)

        doNotArchivePattern = re.compile(bot.localBot.templDoNotArchive, re.IGNORECASE)
        # using original self.content because for EN and commons there is not visible template but you can find this in the code:
        # <!-- [[User:DoNotArchiveUntil]] 19:24, 13 March 2035 (UTC) -->
        self.hasDoNotArchiveTmpl = doNotArchivePattern.search(self.content) != None

    def _extractTimeStampsAndAges(self, bot, regex: str, clearedContent: str, now: datetime):
        """
            agesList: a float value for each signature. Unit: day
            timestampList: a float value for each signature. Unit: microseconds since 1970-01-01
        """
        agesList = []
        timestampList = []
        today = mktime((now + bot.localBot.getUtcDiff()).timetuple())
        matches = re.compile(regex, re.IGNORECASE | re.DOTALL).finditer(clearedContent)
        for m in matches:
            hh, mm, dd, MM, YY = m.group('hh'), m.group('mm'), m.group('dd'), m.group('MM'), m.group('yyyy')
            try:
               dateToCheck = mktime((int(YY), int(bot.localBot.convertMonthNameToNumber(MM)), int(dd),\
                                     int(hh), int(mm), 0, 0, 0, 0))  # microsec. since 1970
               actualAgeInDays = (today - dateToCheck)/60/60/24
               agesList.append(actualAgeInDays)
               timestampList.append(dateToCheck)
            except ValueError as e:
                pywikibot.output("<<lightpurple>>Error in _extractTimeStampsAndAges():")
                pywikibot.output(e)
                pywikibot.output("<<default>>")
            except:
               # date was invalid, we don't care
               raise
        return agesList, timestampList

    def _examineAllResolvedTemplate(self, bot, clearedContent: str, now: datetime):
        # Now examine if discussion has a "cleared" flag and
        sectResolvedPattern = r"\{\{\s{0,50}" + bot.localBot.sectResolvedRegEx + r"\s{0,50}\|.*?" + bot.localBot.timeStampRegEx + r".*?\}\}"
        agesList, timestampList = self._extractTimeStampsAndAges(bot, sectResolvedPattern, clearedContent, now)
        if agesList != []:
            self.ageByResolvedTemplate = min(agesList)

    def _examineAllTimestamps(self, bot, clearedContent: str, now: datetime):
        agesList, timestampList = self._extractTimeStampsAndAges(bot, bot.localBot.timeStampRegEx, clearedContent, now)
        if agesList != [] and timestampList != []:
            self.firstContribution = timestampList[0]
            self.firstContributionAge = agesList[0]
            self.lastContributionAge = min(agesList)
            self.numberOfContributions = len(agesList) # 1 date = 1 contribution

    def shouldBeArchived(self, thresholdAgeResolvedTemplate: float, thresholdAgeByTimeout: float) -> bool:
        return not self.hasDoNotArchiveTmpl \
            and (self.ageByResolvedTemplate > thresholdAgeResolvedTemplate \
                    or (thresholdAgeByTimeout > 0 and self.lastContributionAge >= thresholdAgeByTimeout) \
                )

    def getAgeByResolvedTemplate(self) -> float:
        return self.ageByResolvedTemplate

    def getFirstContributionAge(self) -> float:
        return self.firstContributionAge

    def getNumberOfContributions(self) -> int:
        return self.numberOfContributions

    def determineArchivingTarget(self, wikiDoc):
        """
            Substitutes the variables of parameter target to a path.
        """
        targetPath = wikiDoc.archivingTargetPattern
        bot = wikiDoc.bot
        if wikiDoc.archivingUseTimeComparatorCleared:
            timestampToUse = localtime(self.timestampClearedFlag)
        else:
            timestampToUse = localtime(self.firstContribution)

        # The year of the calendar week and year of the original date are not the same.
        isCalendarWeekException = strftime("%Y", timestampToUse) != strftime("%G", timestampToUse)

        usingWeekVar = False
        for weekVar in bot.localBot._getAllWeekVariablesForTargetPath():
            if weekVar in targetPath:
                usingWeekVar = True
                break

        exchangeMonthAndYear = isCalendarWeekException and usingWeekVar
        # If we use ((week)) which month does it belong to? 1 or 12?
        monthNumberToUse = strftime("%m", timestampToUse)
        if exchangeMonthAndYear and monthNumberToUse == "12":
            monthNumberToUse = "1"
        elif exchangeMonthAndYear and monthNumberToUse == "1":
            monthNumberToUse = "12"
        
        yearToUse = strftime("%G" if exchangeMonthAndYear else "%Y", timestampToUse)
        for old, new in bot.localBot.getReplacementDict(self.pageOrigin, timestampToUse, yearToUse, monthNumberToUse):
            targetPath = targetPath.replace(old, str(new))
        return targetPath

class WikiDocument:
    def __init__(self, text: str, title: str, lastEditTime, lastUser: str, bot, now: datetime = None):
        """
            text, title: wikitext and title of the talk page
            lastEditTime, lastUser: timestamp (datetime, UTC) and user of the latest revision
            bot: the ArchiveRobot (needs .site, .localBot, .dryRun)
            now: current time (naive, UTC) for the age calculation; None = datetime.now()
        """
        self.numberDiscussions   = 0                  # Number of Discussions on page
        self.originalText        = text               # The original Text of the wikipage
        self.modifiedText        = self.originalText  # The text that should be saved to the original talk page (after modification/archiving)
        self.sliceOffset         = 0                  # When a slice gets extracted the offset changes
        self.reportText          = ""                 # Text to save into report file
        self.listDiscussions     = []                 # A list containing the discussions
        self.thresholdAgeResolvedTemplate= 0.0        # Number of days, after a discussion will be archived with template {{section resolved}}
        self.thresholdAgeByTimeout = 0                # if this parameter x is bigger than 0, archiving will be triggered after x days
        self.archivingTargetPattern     = None        # Target where discussions will be archived to
                                                      # Should be equal to [[Vorlage:Autoarchiv]] on de
        self.archivingUseTimeComparatorCleared = False# declares the timestamp that is used for the target.
                                                        # True: the one in the resolved template False: the oldest one
        self.headlineLevel       = 2                  # level of headline to work on (no. of "=")
        self.numberOfDiscussionsToArchive = 0         # Number of discussions that will be archived
        self.archiveJobTextByTarget    = {}           # Dict in which archive text will be stored in
        self.archiveJobCounterByTarget  = {}          # Number of archived discs per container
        self.archiveJobFirstTitleByTarget = {}        # The first section title that is going to this page

        self.originPageName      = title              # Current page
        self.lastEditTime        = lastEditTime       # last edit time
        self.lastUser            = lastUser           # last editor
        self.bot                 = bot
        self.now                 = now

    @classmethod
    def fromPage(cls, page, bot, now: datetime = None):
        return cls(page.get(), page.title(), page.latest_revision.timestamp,
                   page.latest_revision.user, bot, now)

    def divideIntoSlices(self):
        """
            Divide the Original text by headlines ...
        """
        # Should match these variants
        # == 1.2. bla == 
        # ==_==
        # == {{Q-|Q6501349|capitalization=ucfirst}} == <!-- Car parks -->
        # === sub header ===
        # Note, it is {1,%s} because it must match header levels less the defined level. Otherwise = Bla = will be archived with == Blub ==.
        # It must not match higher levels === like this ===.
        # Also, it must match not match just text starting with => bla.
        regex = "(?P<title>^(?P<hls>[=]{1,%s})(?P<title_clear>[^=\n\r]+.+)(?P=hls))(.*?)$" % self.headlineLevel
        p = re.compile(regex, re.IGNORECASE|re.M)
        # ... and iterate through it
        headlineIterator = p.finditer(self.originalText)
        
        counter = 0
        possibleDiscs = []
        for singleHeadline in headlineIterator:
            possibleDiscs.append(Discussion(self.originPageName))
            possibleDiscs[counter].setTitleOffsetStart(singleHeadline.span()[0])
            possibleDiscs[counter].setContentOffsetStart(singleHeadline.span()[1])
            possibleDiscs[counter].setTitle(singleHeadline.group('title'), singleHeadline.group('title_clear'))
            possibleDiscs[counter].setHeadlineLevel(singleHeadline.group('hls').count("="))

            if counter > 0:
                possibleDiscs[counter - 1].setContentOffsetEnd(possibleDiscs[counter].getTitleOffsetStart())
                possibleDiscs[counter - 1].retrieveContent(self.originalText)
            counter += 1
        if (len(possibleDiscs) != 0):
            possibleDiscs[counter - 1].setContentOffsetEnd(len(self.originalText))
            possibleDiscs[counter - 1].retrieveContent(self.originalText)

        for i in possibleDiscs:
            if i.getHeadlineLevel() == self.headlineLevel:
                self.listDiscussions.append(i)
                self.numberDiscussions += 1

    def examineDiscussions(self):
        for singleDiscussion in self.listDiscussions:
            singleDiscussion.examine(self.bot, self.now)

    def generateErrorReport(self):
        logText = (f"== [[{self.originPageName}]] ==\n")
        logText += "Bot run at " + strftime("%Y-%m-%d um %H:%M\n", localtime())
        logText += "ERROR!\n"
        pywikibot.output(logText)
        self.reportText = logText

    def generateReport(self):
        """
            Generates a report for each visited page in Wiki syntax
        """
        logText = (f"== [[{self.originPageName}]] ==\n")
        logText += "Bot run at " + strftime("%Y-%m-%d um %H:%M\n", localtime())
        logText += "* Archiving starts after '''%03.1f days'''\n" % self.thresholdAgeResolvedTemplate
        logText += "* Target pattern: '''%s'''\n" % self.archivingTargetPattern
        logText += "* On headline level '''%d'''\n" % self.headlineLevel
        logText += "* Number of sections: '''%d'''\n" % self.numberDiscussions
        logText += "* Number of sections to archive: '''%d'''\n" % self.numberOfDiscussionsToArchive
        logText += "{| class=\"wikitable\"\n|-\n! lfd. Nr. !! Headline !! Age of oldest signature !! Num. of signatures !! Age of 'resolved' !! Target"

        counter = 0 # lfd. Nr.
        numOfContribution = 0
        for discussion in self.listDiscussions:
            counter       += 1
            headline      = discussion.getTitleClear()
            firstContributionAge  = discussion.getFirstContributionAge()
            numOfContribution     = discussion.getNumberOfContributions()
            # where it would be archived to
            targetArchive = discussion.determineArchivingTarget(self)

            if discussion.getAgeByResolvedTemplate() == 0.0:
                resolvedByTemplateAge = "-"
                headlineColor = ""
            else:
                resolvedByTemplateAge = "%03.2f" % discussion.getAgeByResolvedTemplate()
                if discussion.shouldBeArchived(self.thresholdAgeResolvedTemplate, self.thresholdAgeByTimeout):
                    headlineColor = " style=\"background-color:#ffcbcb;\" "
                else:
                    headlineColor = " style=\"background-color:#b9ffc5;\" "

            logText += "\n|-%s\n| %d || %s || %03.2f || %d || %s || [[%s|&rarr;]]" % (headlineColor, counter, headline, firstContributionAge, numOfContribution, resolvedByTemplateAge, targetArchive)

        logText += "\n|}\n"
        pywikibot.output(logText)
        self.reportText = logText

    def saveReport(self, saveLocalLogs: bool, localLogFilePath: str):
        if saveLocalLogs:
            pywikibot.output("Save local file ... ")
            fd = open(localLogFilePath, 'a')
            writeMe = self.reportText + "\n" 
            writeMe = writeMe.encode('utf-8')
            fd.write(writeMe)
            fd.close()
            pywikibot.output("Done.\n")

    def prepareArchiving(self):
        for discussion in self.listDiscussions:
            if discussion.shouldBeArchived(self.thresholdAgeResolvedTemplate, self.thresholdAgeByTimeout):
                self._prepareDiscussionForArchiving(discussion)

    def substSectionResolvedTempl(self, originalText):
        """
            Substitutes the templates
        """
        # subst erledigt
        old = re.compile(r"\{\{\ {0,5}" + self.bot.localBot.sectResolvedRegEx + r"\ {0,5}\|(?:1=)?([^}]*?" + self.bot.localBot.timeStampRegEx + r")\ *?\|(?:2=.*?)?([^}]*?)\ *\}\}", re.UNICODE | re.DOTALL)
        originalText = textlib.replaceExcept(originalText, old, self.bot.localBot.sectResolved2P, ["comment", "nowiki"])
        
        old = re.compile(r"\{\{\ {0,5}" + self.bot.localBot.sectResolvedRegEx + r"\ {0,5}\|(?:1=)?([^}]*?[^}|*]?" + self.bot.localBot.timeStampRegEx + r")\ *?\}\}", re.UNICODE | re.DOTALL)
        return textlib.replaceExcept(originalText, old, self.bot.localBot.sectResolved1P, ["comment", "nowiki"])

    def _showDiffs(self, pageName: str, originalText: str, modifiedText: str):
        if originalText != modifiedText:
            pywikibot.output(f"Diff of [[{pageName}]]:")
            pywikibot.output("#"*80)
            pywikibot.showDiff(originalText, modifiedText)
            pywikibot.output("#"*80)

    def _targetWasSaved(self, targetPageName: str, expectedText: str) -> bool:
        try:
            freshPage = pywikibot.Page(self.bot.site, targetPageName)
            if not freshPage.exists():
                return False
            return (freshPage.latest_revision.user == self.bot.site.username()
                    and freshPage.get(force=True).rstrip() == expectedText.rstrip())
        except Exception:
            pywikibot.output(f"Could not verify [[{targetPageName}]]: {traceback.format_exc()}")
            return False

    def _resolveTargetPage(self, targetPageName: str):
        """Return the page to write the archive to, following a redirect only if it
        points to another subpage of the origin page (e.g. a moved archive).
        Returns None if the target is an unsafe redirect."""
        targetPage = pywikibot.Page(self.bot.site, targetPageName)
        if not targetPage.isRedirectPage():
            return targetPage
        redirectTarget = targetPage.getRedirectTarget()
        if redirectTarget.title().startswith(self.originPageName + '/') and not redirectTarget.isRedirectPage():
            pywikibot.output(f'[[{targetPageName}]] is a redirect, archiving into [[{redirectTarget.title()}]] instead')
            return redirectTarget
        pywikibot.output(f'<<lightpurple>>Skipping {self.originPageName} because archive [[{targetPageName}]] '
                         f'redirects to [[{redirectTarget.title()}]], which is not a subpage of the origin page.<<default>>')
        return None

    def executeArchiving(self):
        # first, check if we can edit all the pages
        if not pywikibot.Page(self.bot.site, self.originPageName).botMayEdit():
            pywikibot.output(f'<<lightpurple>>Skipping {self.originPageName} because it is protected.<<default>>')
            return
        for targetPageName, discussionsAsText in self.archiveJobTextByTarget.items():
            targetPage = self._resolveTargetPage(targetPageName)
            if targetPage is None:
                return
            if not targetPage.botMayEdit():
                pywikibot.output(f'<<lightpurple>>Skipping {targetPageName} because it is protected.<<default>>')
                return

        if len(self.archiveJobTextByTarget) >= 1:
            skipThisPage = False
            firstRemovedSectionFromSourceLink = ''
            for targetPageName, discussionsAsText in self.archiveJobTextByTarget.items():
                targetEditComment = ""
                firstNewSectionInArchive = self.archiveJobFirstTitleByTarget[targetPageName]
                firstNewSectionInArchiveLink = f'{targetPageName}#{firstNewSectionInArchive}|{firstNewSectionInArchive}'
                if firstRemovedSectionFromSourceLink == '':
                    firstRemovedSectionFromSourceLink = firstNewSectionInArchiveLink

                if self.archiveJobCounterByTarget[targetPageName] == 1:
                    targetEditComment = self.bot.localBot.archiveSumTargetS.format(sourcePage=self.originPageName)
                else:
                    targetEditComment = self.bot.localBot.archiveSumTargetP.format(
                                    numOfSections=self.archiveJobCounterByTarget[targetPageName],
                                    sourcePage=self.originPageName)
                if self.bot.localBot.firstNewSectionInArchiveSummary != '': # for projects without translation
                    targetEditComment += self.bot.localBot.firstNewSectionInArchiveSummary.format(firstNewSectionInArchiveLink=firstNewSectionInArchiveLink)
                
                newText = None
                try:
                    pywikibot.output(f"Opening page [[{targetPageName}]]")
                    targetPage = self._resolveTargetPage(targetPageName)
                    if targetPage is None:
                        skipThisPage = True
                        break
                    targetPageName = targetPage.title()
                    if self.bot.localBot.mustNotArchiveToMainNamespace() and targetPage.namespace() == 0:
                        pywikibot.output("Archiving into the (Main) namespace 0!")
                        skipThisPage = True
                    else:
                        if targetPage.exists():
                            newText = self.substSectionResolvedTempl(targetPage.get() + "\n\n" + discussionsAsText)
                        else:
                            newText = self.substSectionResolvedTempl(self.bot.localBot.headTemplate + "\n\n" + discussionsAsText)
                        
                        self._showDiffs(targetPageName, targetPage.text, newText)
                        if self.bot.dryRun:
                            pywikibot.output(f'Skipping {targetPageName} because of "dry run"')
                        else:
                            targetPage.text = newText
                            targetPage.save(targetEditComment, minor=True, force=True)
                        pywikibot.output(f'edit comment: {targetEditComment}')
                except pywikibot.exceptions.EditConflictError:
                    pywikibot.output("<<lightpurple>>Edit conflict!<<default>>")
                    skipThisPage = True
                except pywikibot.exceptions.LockedPageError:
                    pywikibot.output("<<lightpurple>>Page is locked!<<default>>")
                    skipThisPage = True
                except pywikibot.exceptions.InvalidTitleError:
                    # don't care, some bug in the title
                    pywikibot.output("<<lightpurple>>Page skipped because of pywikibot.exceptions.InvalidTitleError<<default>>")
                    skipThisPage = True
                except:
                    # workaround for https://sourceforge.net/tracker/?func=detail&aid=3588463&group_id=93107&atid=603138
                    pywikibot.output(f"\n<<lightpurple>>Error at {targetPageName}<<default>> skip page\n")
                    pywikibot.output(f"Unexpected error: {str(traceback.format_exc())}")
                    pywikibot.output(f"check if [[{targetPageName}]] was already saved")
                    # The save may have succeeded server-side despite the error (e.g. timeout).
                    # Only continue (and later remove the sections from the origin page) if the
                    # archive page now really contains our new text; otherwise abort this page
                    # so no discussions get lost.
                    if newText is None or self.bot.dryRun or not self._targetWasSaved(targetPageName, newText):
                        pywikibot.output(f"<<lightpurple>>[[{targetPageName}]] was NOT saved, origin page stays untouched<<default>>")
                        raise
                    pywikibot.output(f"[[{targetPageName}]] was saved after all")
            
            if skipThisPage:
                pywikibot.output(f'Skipping {self.originPageName} because "skipThisPage" is True')
            else:
                self._performArchivingOnOriginPage(firstRemovedSectionFromSourceLink)
                sleep(2)

    def _performArchivingOnOriginPage(self, firstRemovedSectionFromSourceLink: str):
        distributionComment = ''
        numberOfSectionsRemovedFromOrigin = 0
        for targetPageName, discussionsAsText in self.archiveJobTextByTarget.items():
            numberOfSectionsRemovedFromOrigin += self.archiveJobCounterByTarget[targetPageName]
            if distributionComment != '':
                distributionComment += ", "
            distributionComment += self.bot.localBot.archiveSumOriginMulti.format(
                            noOfDisuccionsToThisTarget=self.archiveJobCounterByTarget[targetPageName],
                            targetPageName=targetPageName)
                
        if numberOfSectionsRemovedFromOrigin == 1:
            numberOfSectionsRemovedFromOriginStr = self.bot.localBot.archiveSumOriginS
        else:
            numberOfSectionsRemovedFromOriginStr = self.bot.localBot.archiveSumOriginP.format(numberOfSectionsRemovedFromOrigin=numberOfSectionsRemovedFromOrigin)
        
        # add last contributor + time
        lastEditTime = self.lastEditTime + self.bot.localBot.getUtcDiff()
        lastEditTime = ("%s-%02d-%02d %02d:%02d" % (lastEditTime.year, lastEditTime.month, lastEditTime.day, lastEditTime.hour, lastEditTime.minute))
        lastEditComment = self.bot.localBot.archiveSumLastEdit % (self.lastUser, self.lastUser, lastEditTime)
        firstNewSectionInArchiveSummary = '' # fallback
        if len(self.archiveJobTextByTarget) == 1 and self.bot.localBot.firstNewSectionInArchiveSummary != '': # for projects without translation
            firstNewSectionInArchiveSummary = self.bot.localBot.firstNewSectionInArchiveSummary.format(firstNewSectionInArchiveLink=firstRemovedSectionFromSourceLink)
        
        archiveOverallSummary = self.bot.localBot.archiveOverallSummary.format(numberOfSectionsRemovedFromOriginStr=numberOfSectionsRemovedFromOriginStr,
                    distributionComment=distributionComment, firstNewSectionInArchiveSummary=firstNewSectionInArchiveSummary, lastEditComment=lastEditComment)
        
        self.modifiedText = self.bot.localBot.applyLocalModifications(self.modifiedText)
        try:
            originPage = pywikibot.Page(self.bot.site, self.originPageName)
            self._showDiffs(self.originPageName, originPage.text, self.modifiedText)

            if self.bot.dryRun:
                pywikibot.output(f'Skipping {self.originPageName} because of "dry run"')
                pywikibot.output(f'edit comment: {archiveOverallSummary}')
            else:
                originPage.text = self.modifiedText
                originPage.save(archiveOverallSummary, minor=True)
                pywikibot.output(f'edit comment: {archiveOverallSummary}')
        except pywikibot.exceptions.NoPageError:
            if not self.bot.dryRun:
                originPage.text = self.modifiedText
                originPage.save(archiveOverallSummary, minor=True)
            pywikibot.output(f'edit comment: {archiveOverallSummary}')
        except pywikibot.exceptions.EditConflictError:
            pywikibot.output(f'Skipping {self.originPageName} because of edit conflict')

    def _prepareDiscussionForArchiving(self, disc: Discussion):
        sliceStart = disc.getTitleOffsetStart() - self.sliceOffset
        sliceStop  = disc.getContentOffsetEnd() - self.sliceOffset
        sliceText  = self.modifiedText[sliceStart:sliceStop]
        headline = disc.getTitle()
        self.modifiedText  = self.modifiedText[:sliceStart] + self.modifiedText[sliceStop:]
        self.sliceOffset   = self.sliceOffset + len(sliceText)
        self.numberOfDiscussionsToArchive += 1
        target = disc.determineArchivingTarget(self)

        if target in self.archiveJobTextByTarget:
            self.archiveJobTextByTarget[target] += sliceText
            self.archiveJobCounterByTarget[target] += 1
        else:
            self.archiveJobTextByTarget[target] = sliceText
            self.archiveJobCounterByTarget[target] = 1
        
        if target not in self.archiveJobFirstTitleByTarget:
            # remove headline marker == abc ==
            headline = textlib.replaceExcept(headline, r"=+\s*(.*?)\s*=+\s*", "\\1", [])
            # [[abc|xyz]] -> yxz
            headline = textlib.replaceExcept(headline, r"\[\[[^\|\]]+?\|(.*?)\]\]", "\\1", [])
            # remove markup
            headline = headline.replace(' ', '_').replace('[[', '').replace(']]', '').replace("'''", '').replace("''", '')\
                    .replace('<s>', '').replace('</s>', '').replace('<nowiki>', '').replace('</nowiki>', '')\
                    .replace('<code>', '').replace('</code>', '').replace('<pre>', '').replace('</pre>', '')\
                    .replace('<sub>', '').replace('</sub>', '').replace('<sup>', '').replace('</sup>', '')
            self.archiveJobFirstTitleByTarget[target] = headline
    
    @staticmethod
    def removeCommentsAndOther(originalText: str) -> str:
        clearedContent = textlib.replaceExcept(originalText, r"(?s)<!\-\-.*?\-\->", "", [])
        clearedContent = textlib.replaceExcept(clearedContent, r"(?s)<nowiki>.*?</nowiki>", "", [])
        clearedContent = textlib.replaceExcept(clearedContent, r"(?s)<code>.*?</code>", "", [])
        return textlib.replaceExcept(clearedContent, r"(?s)<pre>.*?</pre>", "", [])

    def findOptions(self):
        """
        Looks for the template {{Autoarchiv-Erledigt}}
        """
        p = re.compile(self.bot.localBot.optionsRegEx, re.DOTALL)
        match = p.search(WikiDocument.removeCommentsAndOther(self.originalText))
        if match:
            allOptions = match.group('options')
            optionsDict = {}
            for x in allOptions.split("|"):
                y = x.split("=")
                if len(y) == 2:
                    optionsDict[y[0].strip().upper()] = y[1].strip()

            for nam, num in optionsDict.items():
                pywikibot.output("%s = %s" % (nam, num))              
            
            try:
                if self.bot.localBot.paramAge not in optionsDict:
                   raise NoOptions(f"<<lightpurple>>'{self.bot.localBot.paramAge}' is missing.<<default>>")
                if self.bot.localBot.paramArchive not in optionsDict:
                   raise NoOptions(f"<<lightpurple>>'{self.bot.localBot.paramArchive}' is missing.<<default>>")

                self.thresholdAgeResolvedTemplate    = float(optionsDict[self.bot.localBot.paramAge])
                self.archivingTargetPattern = optionsDict[self.bot.localBot.paramArchive].replace("'", "") # remove '
                if self.bot.localBot.paramLevel in optionsDict and optionsDict[self.bot.localBot.paramLevel] != '':
                    self.headlineLevel   = int(optionsDict[self.bot.localBot.paramLevel])
                else:
                    self.headlineLevel   = 2

                if self.bot.localBot.paramTimeComparator in optionsDict and optionsDict[self.bot.localBot.paramTimeComparator] != '':
                    self.archivingUseTimeComparatorCleared = (optionsDict[self.bot.localBot.paramTimeComparator] != None
                            and optionsDict[self.bot.localBot.paramTimeComparator] == self.bot.localBot.paramTimeComparatorCleared)
                if self.bot.localBot.paramTimeComparator in optionsDict and optionsDict[self.bot.localBot.paramTimeComparator] != '':
                    self.thresholdAgeByTimeout = float(optionsDict[self.bot.localBot.paramTimeComparator])
            except KeyError as ke:
                raise NoOptions()
            except ValueError:
                raise WrongOptions()

        else:
            raise NoOptions(f"<<lightpurple>>Main template not found.<<default>>")
    
    def hasWorkToDo(self):
        """
        Whether there is something to archive or not
        """
        return self.numberOfDiscussionsToArchive > 0

"""
Core of the archive-resolved bot: parsing of talk pages, deciding which sections
to archive and writing them to their archive pages.

All site access goes through ``bot.site`` (and pywikibot.Page on it), so the
classes can be tested with a fake site.
"""
import math
import re               # Used for regular expressions
import traceback
import pywikibot        # Wikipedia-pybot-framework
from pywikibot import textlib
from time import localtime, sleep, strftime, mktime    # strftime-Function and related
from datetime import datetime, timedelta
from pytz import timezone, utc
from archive_resolved_localization.local_bot import TEMPLATE_PREFIX
from archive_resolved_localization.messages import DEFAULT_LANGUAGE, formatMessage

# Markup whose content MediaWiki does not parse: comments (an unclosed one hides the
# rest of the page) and <nowiki>, <pre>, <code>, <syntaxhighlight>, <source> with any
# attributes and in any case. Self-closing <nowiki/> does not hide anything.
HIDDEN_MARKUP = re.compile(
    r"<!--.*?(?:-->|\Z)"
    r"|<(?P<tag>nowiki|pre|code|syntaxhighlight|source)(?:\s[^>]*)?(?<!/)>.*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL)


# The last line of a page if it belongs to the page and not to the last section: a category,
# a sort key or a magic word like __NOTOC__. Such lines stay on the page when the last section
# is archived.
# Names from the siteinfo of the wikis the bot runs on (namespace 14 with aliases, magic word
# defaultsort); magic words like __NOTOC__, __目次非表示__ or __목차숨김__ are matched by \w.
FOOTER_ITEM = (
    r"(?:\[\[\s*(?:Kategorie|Category|Kat|CAT|Kategoria|Categoria|Catégorie|Thể\ loại|분류|カテゴリ)\s*:[^\[\]\n]*\]\]"
    r"|\{\{\s*(?:DEFAULTSORT|DEFAULTSORTKEY|DEFAULTCATEGORYSORT|SORTIERUNG|KLÍČŘAZENÍ|デフォルトソート"
    r"|デフォルトソートキー|デフォルトカテゴリソート|기본정렬|XẾP_MẶC_ĐỊNH|XẾPMẶCĐỊNH)\s*[:：][^{}\n]*\}\}"
    r"|__\w+__)")
FOOTER_LINE = re.compile(r"(?:^|\n)[ \t]*" + FOOTER_ITEM + r"(?:[ \t]*" + FOOTER_ITEM + r")*[ \t]*\Z", re.IGNORECASE)

# nothing but comments and whitespace
COMMENTS_ONLY = re.compile(r"(?:\s*<!--.*?-->)*\s*", re.DOTALL)

# characters that are not allowed in page titles; a ((variable)) never produces them
INVALID_TITLE_CHARS = re.compile(r"[\[\]{}<>|#]")
# never archive into these namespaces: MediaWiki, Template, Module (pages there have an effect on other pages)
FORBIDDEN_TARGET_NAMESPACES = (8, 10, 828)
UTC_TIMESTAMP_END = re.compile(r"\(UTC\)\s*\Z", re.IGNORECASE)

#
# Local exceptions
#
class ArchivingError(Exception):
    """Archiving error"""

class OptionsError(ArchivingError):
    """The archive template is missing or has wrong parameters; the message is shown on the talk page.
    key/msgArgs: message in archive_resolved_localization/messages.json"""
    def __init__(self, key, **msgArgs):
        self.key = key
        self.msgArgs = msgArgs
        super().__init__(formatMessage(DEFAULT_LANGUAGE, key, msgArgs))

    def getMsg(self, language: str = DEFAULT_LANGUAGE, wiki: bool = False):
        return formatMessage(language, self.key, self.msgArgs, wiki)

class NoOptions(OptionsError):
    def __init__(self, key, **msgArgs):
        pywikibot.output("\t *** No archive template found or wrong format ***\n")
        super().__init__(key, **msgArgs)

class WrongOptions(OptionsError):
    def __init__(self, key, **msgArgs):
        pywikibot.output("\t *** Parameters have a wrong format ***\n")
        super().__init__(key, **msgArgs)

#
# *** DECLARATIONS ***
#
class Discussion:
    def __init__(self, pageOriginName: str):
        self.titleOffsetStart    = 0      # offset, where title of disc starts
        self.title               = ""     # Title of disc
        self.titleClear          = ""
        self.hasDoNotArchiveTmpl = False  # is a temple used for this section, that denies archiving
        self.hasArchiveTemplate  = False  # the archive template itself is in this section
        self.contentOffsetStart  = 0      # offset, where text starts
        self.contentOffsetEnd    = 0      # offset, where text ends
        self.content             = ""     # content of disc/section
        self.firstContributionAge = 0.0    # How old is the discussion? in days
        self.lastContributionAge = 0.0     # How old is the last timestamp? in days
        self.timestampClearedFlag= None    # The timestamp of the newest resolved template (seconds since 1970), None if not resolved
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
        # never archive the archive template: on the archive page it would archive again (recursively)
        # (only a real one with a target, not a mention like "{{Autoarchiv-Erledigt einbauen" followed by any }})
        template = re.search(bot.localBot.optionsRegEx, clearedContent, re.DOTALL)
        self.hasArchiveTemplate = template is not None and re.search(
            r"\|\s*" + re.escape(bot.localBot.paramArchive) + r"\s*=", template.group('options'), re.IGNORECASE) is not None

    def _extractTimeStampsAndAges(self, bot, regex: str, clearedContent: str, now: datetime):
        """
            agesList: a float value for each signature. Unit: day
            timestampList: a float value for each signature. Unit: microseconds since 1970-01-01
        """
        agesList = []
        timestampList = []
        today = mktime((now + bot.localBot.getUtcDiff(now)).timetuple())
        localTz = timezone(bot.localBot._getTimezone())
        timestampPattern = re.compile(bot.localBot.timeStampRegEx, re.IGNORECASE | re.DOTALL)
        matches = re.compile(regex, re.IGNORECASE | re.DOTALL).finditer(clearedContent)
        for m in matches:
            hh, mm, dd, MM, YY = m.group('hh'), m.group('mm'), m.group('dd'), m.group('MM'), m.group('yyyy')
            try:
               signatureTime = datetime(int(YY), int(bot.localBot.convertMonthNameToNumber(MM)), int(dd), int(hh), int(mm))
               # all times are local time of the wiki; a signature in UTC (e.g. "(UTC)" on dewiki) is converted
               if localTz.zone != "UTC" and UTC_TIMESTAMP_END.search(timestampPattern.search(m.group(0)).group(0)):
                   signatureTime = utc.localize(signatureTime).astimezone(localTz).replace(tzinfo=None)
               dateToCheck = mktime(signatureTime.timetuple()[:8] + (0,))  # seconds since 1970
               actualAgeInDays = (today - dateToCheck)/60/60/24
               agesList.append(actualAgeInDays)
               timestampList.append(dateToCheck)
            except ValueError as e:
                pywikibot.output("<<lightpurple>>Error in _extractTimeStampsAndAges():")
                pywikibot.output(e)
                pywikibot.output("<<default>>")
        return agesList, timestampList

    def _examineAllResolvedTemplate(self, bot, clearedContent: str, now: datetime):
        # Now examine if discussion has a "cleared" flag and
        sectResolvedPattern = r"\{\{\s{0,50}" + TEMPLATE_PREFIX + bot.localBot.sectResolvedRegEx + r"\s{0,50}\|.*?" + bot.localBot.timeStampRegEx + r".*?\}\}"
        agesList, timestampList = self._extractTimeStampsAndAges(bot, sectResolvedPattern, clearedContent, now)
        if agesList != []:
            self.ageByResolvedTemplate = min(agesList)
            self.timestampClearedFlag = max(timestampList)  # the newest resolved template

    def _examineAllTimestamps(self, bot, clearedContent: str, now: datetime):
        agesList, timestampList = self._extractTimeStampsAndAges(bot, bot.localBot.timeStampRegEx, clearedContent, now)
        if agesList != [] and timestampList != []:
            self.firstContribution = timestampList[0]
            self.firstContributionAge = agesList[0]
            self.lastContributionAge = min(agesList)
            self.numberOfContributions = len(agesList) # 1 date = 1 contribution

    def shouldBeArchived(self, thresholdAgeResolvedTemplate: float, thresholdAgeByTimeout: float) -> bool:
        return not self.hasDoNotArchiveTmpl and not self.hasArchiveTemplate \
            and (self.ageByResolvedTemplate > thresholdAgeResolvedTemplate \
                    or (thresholdAgeByTimeout > 0 and self.lastContributionAge >= thresholdAgeByTimeout) \
                )

    def daysUntilDue(self, thresholdAgeResolvedTemplate: float, thresholdAgeByTimeout: float):
        """
            In how many days (from the time of examine()) shouldBeArchived() gets true if nobody edits
            the section. None = never.
        """
        if self.hasDoNotArchiveTmpl or self.hasArchiveTemplate:
            return None
        days = []
        if self.timestampClearedFlag is not None:
            days.append(thresholdAgeResolvedTemplate - self.ageByResolvedTemplate)
        if thresholdAgeByTimeout > 0 and self.numberOfContributions > 0:
            days.append(thresholdAgeByTimeout - self.lastContributionAge)
        return min(days, default=None)

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
        if wikiDoc.archivingUseTimeComparatorCleared and self.timestampClearedFlag is not None:
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
        # If we use ((week)) which month does it belong to? 01 or 12?
        # Only the turn of the year is affected: 29-31 Dec in week 1 -> January of the next year,
        # 1-3 Jan in week 52/53 -> December of the previous year. strftime gives "01".."12", and
        # the month stays zero-padded like on every other day (ja/vi use it as is in ((month:short))).
        monthNumberToUse = strftime("%m", timestampToUse)
        if exchangeMonthAndYear:
            monthNumberToUse = "01" if monthNumberToUse == "12" else "12"

        yearToUse = strftime("%G" if exchangeMonthAndYear else "%Y", timestampToUse)
        for old, new in bot.localBot.getReplacementDict(self.pageOrigin, timestampToUse, yearToUse, monthNumberToUse):
            targetPath = targetPath.replace(old, str(new))
        return targetPath

class WikiDocument:
    def __init__(self, text: str, title: str, lastEditTime, lastUser: str, bot, now: datetime = None, revid: int = None):
        """
            text, title: wikitext and title of the talk page
            lastEditTime, lastUser: timestamp (datetime, UTC) and user of the latest revision
            bot: the ArchiveRobot (needs .site, .localBot, .dryRun)
            now: current time (naive, UTC) for the age calculation; None = datetime.now()
            revid: ID of the latest revision
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
        self.archiveJobSectionsByTarget = {}          # The same text as list of the single sections
        self.archiveJobCounterByTarget  = {}          # Number of archived discs per container
        self.archiveJobFirstTitleByTarget = {}        # The first section title that is going to this page

        self.originPageName      = title              # Current page
        self.lastEditTime        = lastEditTime       # last edit time
        self.lastUser            = lastUser           # last editor
        self.bot                 = bot
        self.now                 = now
        self.revid               = revid
        self.examinedAt          = None               # time of examineDiscussions() (aware, UTC)
        self.options             = {}                 # the parameters of the archive template (names in upper case)
        self.outcome             = None               # result of executeArchiving: 'archived', 'dryrun', 'skipped' (see summary.py)
        self.outcomeMessage      = None               # why it was skipped (in the language of the wiki)
        self.outcomeKey          = None               # ... as message key + arguments (messages.json)
        self.outcomeArgs         = None
        self.failedTarget        = None               # archive page whose save failed with an unexpected error

    def _skipped(self, key: str, **msgArgs):
        """Remembers why the page was not archived (for the run summary); key: see messages.json."""
        self.outcome = 'skipped'
        self.outcomeKey = key
        self.outcomeArgs = msgArgs
        self.outcomeMessage = formatMessage(self.bot.localBot.language, key, msgArgs)

    @classmethod
    def fromPage(cls, page, bot, now: datetime = None):
        return cls(page.get(), page.title(), page.latest_revision.timestamp,
                   page.latest_revision.user, bot, now, page.latest_revision.revid)

    def divideIntoSlices(self):
        """
            Divide the Original text by headlines ...
        """
        # Should match these variants
        # == 1.2. bla == 
        # ==A==
        # ==_==
        # == {{Q-|Q6501349|capitalization=ucfirst}} == <!-- Car parks -->
        # === sub header ===
        # Note, it is {1,%s} because it must match header levels less the defined level. Otherwise = Bla = will be archived with == Blub ==.
        # It must not match higher levels === like this ===.
        # Also, it must match not match just text starting with => bla.
        regex = "(?P<title>^(?P<hls>[=]{1,%s})(?P<title_clear>[^=\n\r].*)(?P=hls))(.*?)$" % self.headlineLevel
        p = re.compile(regex, re.IGNORECASE|re.M)
        # ... and iterate through it
        headlineIterator = p.finditer(self.originalText)
        # headlines inside comments, <nowiki>, <pre> etc. are no headlines
        hiddenSpans = [m.span() for m in HIDDEN_MARKUP.finditer(self.originalText)]

        counter = 0
        possibleDiscs = []
        for singleHeadline in headlineIterator:
            if any(start <= singleHeadline.start() < end for start, end in hiddenSpans):
                continue
            possibleDiscs.append(Discussion(self.originPageName))
            possibleDiscs[counter].setTitleOffsetStart(singleHeadline.span()[0])
            possibleDiscs[counter].setContentOffsetStart(singleHeadline.span()[1])
            possibleDiscs[counter].setTitle(singleHeadline.group('title'), singleHeadline.group('title_clear'))
            possibleDiscs[counter].setHeadlineLevel(singleHeadline.group('hls').count("="))

            if counter > 0:
                previousDisc = possibleDiscs[counter - 1]
                previousDisc.setContentOffsetEnd(self._endOfSection(previousDisc.getTitleOffsetStart(),
                                                                    possibleDiscs[counter].getTitleOffsetStart(), False))
                previousDisc.retrieveContent(self.originalText)
            counter += 1
        if (len(possibleDiscs) != 0):
            lastDisc = possibleDiscs[counter - 1]
            lastDisc.setContentOffsetEnd(self._endOfSection(lastDisc.getTitleOffsetStart(), len(self.originalText), True))
            lastDisc.retrieveContent(self.originalText)

        for i in possibleDiscs:
            if i.getHeadlineLevel() == self.headlineLevel:
                self.listDiscussions.append(i)
                self.numberDiscussions += 1

    def _endOfSection(self, start: int, end: int, isLast: bool) -> int:
        """
            A section ends where the next one starts, except for the archive template (with comments
            around it) on its own lines at the end: it belongs to the page and stays there, also when
            new sections were added below it. The last section also leaves categories, sort keys and
            magic words on its last lines on the page.
        """
        text = self.originalText
        footerStart = end
        while True:
            contentEnd = start + len(text[start:footerStart].rstrip())
            newFooterStart = None
            if isLast:
                footer = FOOTER_LINE.search(text, start, contentEnd)
                if footer is not None:
                    newFooterStart = footer.start()
            if newFooterStart is None:
                newFooterStart = self._archiveTemplateAtEnd(start, contentEnd)
            if newFooterStart is None:
                break
            footerStart = newFooterStart
        if footerStart == end:
            return end
        # keep the line break after the last line of the section
        contentEnd = start + len(text[start:footerStart].rstrip())
        return contentEnd + 1 if text[contentEnd:contentEnd + 1] == "\n" else contentEnd

    def _archiveTemplateAtEnd(self, start: int, end: int):
        """
            Where the line with the archive template starts, if only comments are around it up to 'end'
            and before it on its line; None otherwise.
        """
        text = self.originalText
        for template in reversed(list(re.finditer(self.bot.localBot.optionsRegEx, text[start:end], re.DOTALL))):
            templateStart, templateEnd = start + template.start(), start + template.end()
            if not COMMENTS_ONLY.fullmatch(text, templateEnd, end):
                return None
            lineStart = text.rfind("\n", start, templateStart) + 1
            if lineStart == 0 or not COMMENTS_ONLY.fullmatch(text, lineStart, templateStart):
                return None   # the template is not on a line of its own
            # comment lines right above it belong to it, e.g. <!-- please do not remove -->
            while lineStart - 1 > start:
                previousLineStart = text.rfind("\n", start, lineStart - 1) + 1
                previousLine = text[previousLineStart:lineStart - 1]
                if previousLineStart == 0 or "<!--" not in previousLine or not COMMENTS_ONLY.fullmatch(previousLine):
                    break
                lineStart = previousLineStart
            return lineStart
        return None

    def examineDiscussions(self):
        self.examinedAt = datetime.now(utc) if self.now is None else utc.localize(self.now)
        for singleDiscussion in self.listDiscussions:
            singleDiscussion.examine(self.bot, self.now)

    def nextDue(self):
        """
            When the first section gets due if nobody edits the page (aware datetime, UTC); None = never
        """
        days = [disc.daysUntilDue(self.thresholdAgeResolvedTemplate, self.thresholdAgeByTimeout)
                for disc in self.listDiscussions]
        days = [d for d in days if d is not None and math.isfinite(d)]
        if not days or min(days) > 36500:   # e.g. Alter=999999999: out of range for a date
            return None
        return self.examinedAt + timedelta(days=min(days))

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
            with open(localLogFilePath, 'a', encoding='utf-8') as fd:
                fd.write(self.reportText + "\n")
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
        # group 1: signature with timestamp, groups 2-6: parts of the timestamp, group 7: 2nd parameter (reason)
        lb = self.bot.localBot
        start = r"\{\{\s*" + TEMPLATE_PREFIX + lb.sectResolvedRegEx + r"\s*\|(?:1=)?"
        old = re.compile(start + r"([^}]*?" + lb.timeStampRegEx + r")\s*\|(?:2=)?([^}]*?)\s*\}\}", re.UNICODE | re.DOTALL)
        # an empty 2nd parameter is treated like a missing one
        withReason = lambda m: m.expand(lb.sectResolved2P if m.group(7).strip() else lb.sectResolved1P)
        originalText = textlib.replaceExcept(originalText, old, withReason, ["comment", "nowiki"])

        old = re.compile(start + r"([^}]*?[^}|*]?" + lb.timeStampRegEx + r")\s*\}\}", re.UNICODE | re.DOTALL)
        return textlib.replaceExcept(originalText, old, lb.sectResolved1P, ["comment", "nowiki"])

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
        if redirectTarget.site == self.bot.site and redirectTarget.title().startswith(self.originPageName + '/') \
                and not redirectTarget.isRedirectPage():
            pywikibot.output(f'[[{targetPageName}]] is a redirect, archiving into [[{redirectTarget.title()}]] instead')
            return redirectTarget
        pywikibot.output(f'<<lightpurple>>Skipping {self.originPageName} because archive [[{targetPageName}]] '
                         f'redirects to [[{redirectTarget.title()}]], which is not a subpage of the origin page.<<default>>')
        return None

    def _isArchiveOfItself(self, targetPageName: str) -> bool:
        """
            True if the origin page would archive into itself or looks like an archive page made
            by its own target pattern, e.g. X/Archiv/2024/01 archiving into X/Archiv/2024/01/Archiv/2024/01.
            This happens when the archive template got into an archive page.
        """
        origin = self.originPageName
        if targetPageName == origin:
            return True
        if not targetPageName.startswith(origin + '/'):
            return False
        # the part of the pattern after the page name variable, e.g. /Archiv/((Jahr))/((Monat:##))
        m = re.match(r"\s*\(\([^()]*\)\)(.+)", self.archivingTargetPattern)
        if m is None:
            return False
        if origin.endswith(targetPageName[len(origin):]):
            return True
        valuePatterns = self._variableValuePatterns()
        suffix = "".join(valuePatterns.get(part, re.escape(part))
                         for part in re.split(r"(\(\([^()]*\)\))", m.group(1)))
        return re.search(suffix + r"\Z", origin) is not None

    def _variableValuePatterns(self) -> dict:
        """
            A regex for every date ((variable)) that matches all values it can have, e.g.
            ((Jahr)) -> \\d+, ((Monat:Lang)) -> Januar|Februar|…, ((Quartal:I)) -> [IVXivx]+, 03 月 -> \\d+\\ 月.
        """
        pageToken = "\x00page\x00"   # variables that give the page name are left out
        values = {}
        for month in range(1, 13):
            stamp = localtime(mktime((2025, month, 15, 12, 0, 0, 0, 0, -1)))
            for monthNumber in ("%02d" % month, str(month)):
                for variable, value in self.bot.localBot.getReplacementDict(pageToken, stamp, "2025", monthNumber):
                    value = str(value)
                    if pageToken not in value:
                        values.setdefault(variable, set()).add(value)
        patterns = {}
        for variable, variableValues in values.items():
            alternatives = set()
            for value in variableValues:
                if re.fullmatch(r"[IVXivx]+", value):
                    alternatives.add(r"[IVXivx]+")
                else:
                    alternatives.add(re.sub(r"\d+", lambda _: r"\d+", re.escape(value)))
            patterns[variable] = "(?:" + "|".join(sorted(alternatives)) + ")"
        return patterns

    def _resolveTargets(self) -> bool:
        """
            Checks all archive pages before anything is saved and replaces redirects to a subpage
            of the origin page by their target, so the edit summaries name the page really written.
            Returns False if the origin page must be skipped.
        """
        textByTarget, sectionsByTarget, counterByTarget, firstTitleByTarget = {}, {}, {}, {}
        for targetPageName, discussionsAsText in self.archiveJobTextByTarget.items():
            if self._isArchiveOfItself(targetPageName):
                pywikibot.output(f'<<lightpurple>>Skipping {self.originPageName} because it would archive into '
                                 f'[[{targetPageName}]], it seems to be an archive page itself.<<default>>')
                self._skipped('skip.self_archive', target=targetPageName)
                return False
            try:
                targetPage = self._resolveTargetPage(targetPageName)
            except pywikibot.exceptions.InvalidTitleError as e:
                raise WrongOptions('opt.invalid_title', target=targetPageName)
            if targetPage is None:
                self._skipped('skip.redirect', target=targetPageName)
                return False
            # e.g. "en:User:X" is a page of another wiki; its title() without the prefix would be a local page
            if targetPage.site != self.bot.site:
                raise WrongOptions('opt.invalid_title', target=targetPageName)
            if targetPage.namespace() in FORBIDDEN_TARGET_NAMESPACES:
                pywikibot.output(f"Archiving into the namespace of [[{targetPageName}]] is not allowed")
                self._skipped('skip.namespace', target=targetPageName)
                return False
            if not targetPage.botMayEdit():
                pywikibot.output(f'<<lightpurple>>Skipping {targetPageName} because it is protected.<<default>>')
                self._skipped('skip.target_protected', target=targetPageName)
                return False
            if self.bot.localBot.mustNotArchiveToMainNamespace() and targetPage.namespace() == 0:
                pywikibot.output("Archiving into the (Main) namespace 0!")
                self._skipped('skip.main_namespace', target=targetPageName)
                return False
            title = targetPage.title()
            if title in textByTarget:
                textByTarget[title] += discussionsAsText
                sectionsByTarget[title] += self.archiveJobSectionsByTarget[targetPageName]
                counterByTarget[title] += self.archiveJobCounterByTarget[targetPageName]
            else:
                textByTarget[title] = discussionsAsText
                sectionsByTarget[title] = list(self.archiveJobSectionsByTarget[targetPageName])
                counterByTarget[title] = self.archiveJobCounterByTarget[targetPageName]
                firstTitleByTarget[title] = self.archiveJobFirstTitleByTarget[targetPageName]
        self.archiveJobTextByTarget = textByTarget
        self.archiveJobSectionsByTarget = sectionsByTarget
        self.archiveJobCounterByTarget = counterByTarget
        self.archiveJobFirstTitleByTarget = firstTitleByTarget
        return True

    def _originUnchanged(self, originPage) -> bool:
        """
            Whether the page (freshly loaded) still is at the revision the sections were taken from.
            modifiedText was made from that revision; saving it over a newer one would remove
            everything written in the meantime.
        """
        if not originPage.exists():
            return False
        return self.revid is None or originPage.latest_revision.revid == self.revid

    def executeArchiving(self):
        # first, check if we can edit all the pages
        originPage = pywikibot.Page(self.bot.site, self.originPageName)
        if not originPage.botMayEdit():
            pywikibot.output(f'<<lightpurple>>Skipping {self.originPageName} because it is protected.<<default>>')
            self._skipped('skip.protected')
            return
        if not self._originUnchanged(originPage):
            pywikibot.output(f'Skipping {self.originPageName} because it was changed since it was read')
            self._skipped('skip.origin_changed')
            return
        if not self._resolveTargets():
            return

        if not self.archiveJobTextByTarget:
            return
        # Build and check all archive pages before the first one is saved: if one of them cannot be
        # saved, the sections stay on the origin page and none of the other archives may get a copy.
        edits = []
        maxSize = self._maxPageSize()
        for targetPageName, sections in self.archiveJobSectionsByTarget.items():
            try:
                pywikibot.output(f"Opening page [[{targetPageName}]]")
                targetPage = pywikibot.Page(self.bot.site, targetPageName)  # redirects are resolved already
                newText, newSections = self._buildArchiveText(targetPage, sections)
            except Exception:
                self.failedTarget = targetPageName
                raise
            if newText is None:
                pywikibot.output(f"All sections are in [[{targetPageName}]] already (from an earlier run)")
                continue
            if maxSize is not None and len(newText.encode('utf-8')) > maxSize:
                pywikibot.output(f'<<lightpurple>>Skipping {self.originPageName} because [[{targetPageName}]] '
                                 f'would get too big.<<default>>')
                self._skipped('error.too_big', target=targetPageName)
                return
            edits.append((targetPageName, targetPage, newText, newSections))

        for targetPageName, targetPage, newText, newSections in edits:
            # stop at the first archive that was not saved; the ones saved before are not
            # written again by the next run (see _buildArchiveText)
            if not self._saveArchivePage(targetPageName, targetPage, newText, newSections):
                pywikibot.output(f'Skipping {self.originPageName} because [[{targetPageName}]] was not saved')
                return

        firstTarget = next(iter(self.archiveJobTextByTarget))
        self._performArchivingOnOriginPage(self._firstSectionLink(firstTarget))
        sleep(2)

    def _firstSectionLink(self, targetPageName: str) -> str:
        firstSection = self.archiveJobFirstTitleByTarget[targetPageName]
        return f'{targetPageName}#{firstSection}|{firstSection}'

    def _maxPageSize(self):
        """The maximum page size of the wiki in bytes, None if it is unknown."""
        try:
            return int(self.bot.site.siteinfo['maxarticlesize'])
        except Exception:
            return None

    def _buildArchiveText(self, targetPage, sections: list) -> tuple:
        """
            (new text of the archive page, number of sections added to it). Sections that are in the
            archive already are left out: they come from an earlier run that could not save the origin
            page or another archive. The text is None if nothing is left.
        """
        if not targetPage.exists():
            text = self.bot.localBot.headTemplate + "\n\n" + "".join(sections)
            return self.substSectionResolvedTempl(text), len(sections)
        oldText = targetPage.get()
        missing = [section for section in sections if not self._containsSection(oldText, section)]
        if not missing:
            return None, 0
        return self.substSectionResolvedTempl(oldText + "\n\n" + "".join(missing)), len(missing)

    def _containsSection(self, archiveText: str, section: str) -> bool:
        """Whether the section (as it is written to archives) is in the text as a whole, on lines of its own."""
        section = self.substSectionResolvedTempl(section).strip()
        # up to the next headline or the end: an archived section that goes on is another one
        return re.search(r"(?:\A|\n)" + re.escape(section) + r"\s*(?:\Z|\n=)", archiveText) is not None

    def _saveArchivePage(self, targetPageName: str, targetPage, newText: str, numberOfSections: int) -> bool:
        """Returns False if the archive page was not saved for an expected reason."""
        if numberOfSections == 1:
            targetEditComment = self.bot.localBot.archiveSumTargetS.format(sourcePage=self.originPageName)
        else:
            targetEditComment = self.bot.localBot.archiveSumTargetP.format(
                            numOfSections=numberOfSections, sourcePage=self.originPageName)
        if self.bot.localBot.firstNewSectionInArchiveSummary != '': # for projects without translation
            targetEditComment += self.bot.localBot.firstNewSectionInArchiveSummary.format(
                            firstNewSectionInArchiveLink=self._firstSectionLink(targetPageName))
        try:
            self._showDiffs(targetPageName, targetPage.text, newText)
            if self.bot.dryRun:
                pywikibot.output(f'Skipping {targetPageName} because of "dry run"')
            else:
                targetPage.text = newText
                targetPage.save(targetEditComment, minor=True, force=True)
            pywikibot.output(f'edit comment: {targetEditComment}')
        except pywikibot.exceptions.EditConflictError:
            pywikibot.output("<<lightpurple>>Edit conflict!<<default>>")
            self._skipped('skip.target_conflict', target=targetPageName)
            return False
        except pywikibot.exceptions.LockedPageError:
            pywikibot.output("<<lightpurple>>Page is locked!<<default>>")
            self._skipped('skip.target_locked', target=targetPageName)
            return False
        except Exception:
            # workaround for https://sourceforge.net/tracker/?func=detail&aid=3588463&group_id=93107&atid=603138
            pywikibot.output(f"\n<<lightpurple>>Error at {targetPageName}<<default>> skip page\n")
            pywikibot.output(f"Unexpected error: {str(traceback.format_exc())}")
            pywikibot.output(f"check if [[{targetPageName}]] was already saved")
            # The save may have succeeded server-side despite the error (e.g. timeout).
            # Only continue (and later remove the sections from the origin page) if the
            # archive page now really contains our new text; otherwise abort this page
            # so no discussions get lost.
            if self.bot.dryRun or not self._targetWasSaved(targetPageName, newText):
                pywikibot.output(f"<<lightpurple>>[[{targetPageName}]] was NOT saved, origin page stays untouched<<default>>")
                self.failedTarget = targetPageName
                raise
            pywikibot.output(f"[[{targetPageName}]] was saved after all")
        return True

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
        lastEditTime = self.lastEditTime + self.bot.localBot.getUtcDiff(self.lastEditTime)
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
            # .text loads the current revision, which then is the base revision for the edit conflict
            # detection of the API. So it has to be the revision that was examined.
            currentText = originPage.text
            if not self._originUnchanged(originPage):
                pywikibot.output(f'Skipping {self.originPageName} because it was changed since it was read')
                self._skipped('skip.origin_conflict')
                return
            self._showDiffs(self.originPageName, currentText, self.modifiedText)

            if self.bot.dryRun:
                pywikibot.output(f'Skipping {self.originPageName} because of "dry run"')
                pywikibot.output(f'edit comment: {archiveOverallSummary}')
            else:
                originPage.text = self.modifiedText
                # nocreate: never recreate a page that was deleted or moved in the meantime
                originPage.save(archiveOverallSummary, minor=True, nocreate=True)
                pywikibot.output(f'edit comment: {archiveOverallSummary}')
            self.outcome = 'dryrun' if self.bot.dryRun else 'archived'
        except (pywikibot.exceptions.EditConflictError, pywikibot.exceptions.NoCreateError):
            pywikibot.output(f'Skipping {self.originPageName} because of edit conflict')
            self._skipped('skip.origin_conflict')

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
            self.archiveJobSectionsByTarget[target].append(sliceText)
            self.archiveJobCounterByTarget[target] += 1
        else:
            self.archiveJobTextByTarget[target] = sliceText
            self.archiveJobSectionsByTarget[target] = [sliceText]
            self.archiveJobCounterByTarget[target] = 1
        
        if target not in self.archiveJobFirstTitleByTarget:
            # remove comments and HTML tags (keeping their content), like MediaWiki does for anchors
            headline = re.sub(r"(?s)<!--.*?-->", "", headline)
            headline = re.sub(r"</?[A-Za-z][^<>]*>", "", headline)
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
        """Removes comments, <nowiki>, <pre>, <code>, <syntaxhighlight> and <source> blocks."""
        return HIDDEN_MARKUP.sub("", originalText)

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
            self.options = optionsDict
            
            lb = self.bot.localBot

            def number(param, convert):
                value = optionsDict[param]
                try:
                    return convert(value)
                except ValueError:
                    raise WrongOptions('opt.not_a_number', param=param, value=value)

            if lb.paramAge not in optionsDict:
                raise NoOptions('opt.missing', param=lb.paramAge)
            if lb.paramArchive not in optionsDict:
                raise NoOptions('opt.missing', param=lb.paramArchive)

            self.thresholdAgeResolvedTemplate = number(lb.paramAge, float)
            if self.thresholdAgeResolvedTemplate < 0:
                raise WrongOptions('opt.negative', param=lb.paramAge)
            self.archivingTargetPattern = optionsDict[lb.paramArchive].replace("'", "") # remove '
            # {{FULLPAGENAME}} instead of ((FULLPAGENAME)) is a common mistake; it even looks right on the page
            self.archivingTargetPattern = re.sub(r"\{\{\s*(?:FULLPAGENAME|VOLLER_SEITENNAME)\s*\}\}", "((FULLPAGENAME))",
                                                 self.archivingTargetPattern, flags=re.IGNORECASE)
            if not self.archivingTargetPattern.strip():
                raise WrongOptions('opt.empty', param=lb.paramArchive)
            if INVALID_TITLE_CHARS.search(re.sub(r"\(\([^()]*\)\)", "", self.archivingTargetPattern)):
                raise WrongOptions('opt.invalid_target', param=lb.paramArchive, chars='[ ] { } < > # |',
                                   value=self.archivingTargetPattern)
            if optionsDict.get(lb.paramLevel, '') != '':
                self.headlineLevel = number(lb.paramLevel, int)
                if not 1 <= self.headlineLevel <= 6:
                    raise WrongOptions('opt.level_range', param=lb.paramLevel)
            else:
                self.headlineLevel = 2

            # Zeitvergleich=erledigt / timecompare=resolved: sort into the archive by the timestamp of the resolved template
            timeComparator = optionsDict.get(lb.paramTimeComparator, '')
            self.archivingUseTimeComparatorCleared = \
                timeComparator.lower() == lb.paramTimeComparatorCleared.lower()
            if optionsDict.get(lb.paramTimeout, '') != '':
                self.thresholdAgeByTimeout = number(lb.paramTimeout, float)
                if self.thresholdAgeByTimeout < 0:
                    raise WrongOptions('opt.negative', param=lb.paramTimeout)

        else:
            raise NoOptions('opt.no_template', template=self.bot.localBot.archiveTemplateName)
    
    def hasWorkToDo(self):
        """
        Whether there is something to archive or not
        """
        return self.numberOfDiscussionsToArchive > 0

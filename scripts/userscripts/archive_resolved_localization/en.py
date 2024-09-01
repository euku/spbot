#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.local_bot import LocalBot
from time import strftime
from datetime import datetime

class LocalBotEn(LocalBot):
    shortMonthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    longMonthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)

        self.timeStampRegEx = "(?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2}),\ (?P<dd>[0-9]{1,2})\.?\ (?P<MM>[a-zA-Zä]{3,10})\.?\ (?P<yyyy>[0-9]{4})\ \((?:CE[S]?T|UTC)\)"
        self.archiveTemplateName = "Template:Autoarchive resolved section"
        self.headTemplate   = "{{Talkarchive}}"

        self.excludeList = ( self.archiveTemplateName, 'Template:Autoarchive resolved section/doc' )
        self.errorCategory = "Category:{{ns:Project}}:Incorrect Autoarchive parameter/SpBot"
        self.errorText = "== Archiving could not be finished ==\n"
        self.errorText += f"The bot-run at ~~~~~ was not successful, because the template {self.archiveTemplateName} contains incorrect parameters. %s"
        self.errorText += f"Please have a look at the [[{self.archiveTemplateName}|documentation]] and fix the mistake. Regards --~~~~"
        self.errorText += f"\n\n[[{self.errorCategory}]]<!-- remove this line, if the problem was resolved -->"
        self.errorTextSummary = "reporting an error"
        # template parameters
        self.optionsRegEx = "\{\{\ *(?:[Tt]emplate\:)?\ *[Aa]utoarchive\ resolved\ section(?P<options>.*?)\}\}"
        self.templDoNotArchive = '\{\{\ *[Nn]icht\ *archivieren[|}]' # not used
        self.paramAge = 'AGE'
        self.paramArchive = 'ARCHIVE'
        self.paramLevel = 'LEVEL'
        self.paramTimeComparator = 'TIMECOMAPARE'
        self.paramTimeComparatorCleared = 'resolved'
        self.paramTimeComparator = 'TIMEOUT'
        # edit summaries
        self.archiveSumTargetS = "archiving 1 section from [[{sourcePage}]]"
        self.archiveSumTargetP = "archiving {numOfSections} sections from [[{sourcePage}]]"
        self.archiveSumOriginS = "1 section"
        self.archiveSumOriginP = "{numberOfSectionsRemovedFromOrigin} sections"
        self.archiveSumOriginMulti  = "{noOfDisuccionsToThisTarget} to [[{targetPageName}]]"
        self.firstNewSectionInArchiveSummary  = " (after section [[{firstNewSectionInArchiveLink}]])"
        self.archiveSumLastEdit= " - previous edit: [[:User:%s|%s]], %s"
        self.archiveOverallSummary = "archive {numberOfSectionsRemovedFromOriginStr}: {distributionComment}{firstNewSectionInArchiveSummary}{lastEditComment}"

        self.sectResolvedRegEx = "(?:[Ss]ection[\ _]resolved|[Rr]esolved[\ _]section)"
        self.sectResolved1P    = ":<small>This section was archived on a request by: \\1</small>"
        self.sectResolved2P    = ":<small>This section was archived on a request by \\1 \\7</small>"

    def convertMonthNameToNumber(self, month: str) -> int:
        """
            month: a month name or number fetched from the signature
        """
        if month in LocalBotEn.shortMonthNames:
            return int(LocalBotEn.shortMonthNames.index(month) + 1)
        return int(LocalBotEn.longMonthNames.index(month) + 1)
    
    def convertMonthNumberToShortName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return LocalBotEn.shortMonthNames[int(monthNumber) -1]
    
    def convertMonthNumberToLongName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return LocalBotEn.longMonthNames[int(monthNumber) -1]

    def _getAllWeekVariablesForTargetPath(self) -> list:
        return ["((week:##))", "((week))"]
    
    def getReplacementDict(self, fullpagename: str, timestampToUse: datetime, yearToUse: str, monthNumberToUse: str) -> dict:
        """
            Builds up a dictionary with all ((variables)) as keys and substituted to actual values as values of the dict.
            fullpagename: current page to work on
            timestampToUse: the timestamp to parse
            yearToUse: the preselected year to take. This can be different if we are are using calendar weeks an are in an exception week.
            monthNumberToUse: the preselected month to take. This can be different if we are are using calendar weeks an are in an exception week.
        """
        return [( "((year))"              , yearToUse),
                ( "((month:long))"        , self.convertMonthNumberToLongName(monthNumberToUse)),
                ( "((month:short))"       , self.convertMonthNumberToShortName(monthNumberToUse)),
                ( "((month:#))"           , int(monthNumberToUse)),
                ( "((month:##))"          , str(monthNumberToUse).zfill(2)),
                ( "((week:##))"           , strftime("%V", timestampToUse)),
                ( "((week))"              , int(strftime("%V", timestampToUse))),
                ( "((day:##))"            , strftime("%d", timestampToUse)),
                ( "((fullpagename))"      , fullpagename),
                ( "((Fullpagename))"      , fullpagename),
                ( "((FULLPAGENAME))"      , fullpagename),
                ( "((lemma))"             , fullpagename),
                ( "((quarter))"           , self.getQuarterName(timestampToUse, False, False) ),
                ( "((quarter:##))"        , self.getQuarterName(timestampToUse, False, True) ),
                ( "((quarter:i))"         , self.getQuarterName(timestampToUse, True, False) ),
                ( "((quarter:I))"         , self.getQuarterName(timestampToUse, True, False).upper() ),
                ( "((half-year))"         , self.getHalfyearName(timestampToUse, False, False) ),
                ( "((half-year:##))"      , self.getHalfyearName(timestampToUse, False, True) ),
                ( "((half-year:i))"       , self.getHalfyearName(timestampToUse, True, False) ),
                ( "((half-year:I))"       , self.getHalfyearName(timestampToUse, True, False).upper() )]
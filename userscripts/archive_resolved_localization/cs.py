#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.local_bot import LocalBot
from archive_resolved_localization.en import LocalBotEn
from time import strftime
from datetime import datetime

class LocalBotCs(LocalBot):
    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)
        
        self.timeStampRegEx = "(?P<dd>[0-9]{1,2})\.\ (?P<MM>\d{1,2})\.\ (?P<yyyy>[0-9]{4}),\ (?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2})\ \((?:CE[S]?T)\)"
        self.archiveTemplateName = "Šablona:Archivace vyřešených sekcí"
        self.headTemplate   = "{{Archiv diskuse}}"
        self.excludeList = ( self.archiveTemplateName )
        self.errorCategory = "Category:{{ns:Project}}:Incorrect Autoarchive parameter/SpBot"
        self.errorText = "== Archivaci nelze dokončit ==\n"
        self.errorText += f"Běh bota ~~~~~ nebyl úspěšný, protože šablona {self.archiveTemplateName} obsahuje nesprávné parametry. %s"
        self.errorText += f"Podívejte se, prosím, na [[{self.archiveTemplateName}|dokumentaci]] a opravte chybu. Zdraví --~~~~"
        self.errorText += f"\n\n[[{self.errorCategory}]]<!-- odstraňte tento řádek, pokud je problém vyřešen -->"
        self.errorTextSummary = "Archivaci nelze dokončit"
        # template parameters
        self.optionsRegEx = "\{\{\ *(?:[Šš]ablona|[Tt]emplate\:)?\ *[Aa]rchivace\ vyřešených\ sekcí(?P<options>.*?)\}\}"
        self.templDoNotArchive = '\{\{\ *[Nn]icht\ *archivieren[|}]' # not used
        self.paramAge = 'AGE'
        self.paramArchive = 'ARCHIVE'
        self.paramLevel = 'LEVEL'
        self.paramTimeComparator = 'TIMECOMAPARE'
        self.paramTimeComparatorCleared = 'resolved'
        self.paramTimeComparator = 'TIMEOUT'
        # edit summaries
        self.archiveSumTargetS = "archivuji 1 vlákno z [[{sourcePage}]]"
        self.archiveSumTargetP = "archivuji {numOfSections} vláken z [[{sourcePage}]]"
        self.archiveSumOriginS = "1 vlákno"
        self.archiveSumOriginP = "{numberOfSectionsRemovedFromOrigin} vláken"
        self.archiveSumOriginMulti = "%d do [[%s]]"
        self.archiveSumLastEdit= " - předchozí editace: [[User:%s|%s]], %s"
        self.archiveOverallSummary = "archivuji {numberOfSectionsRemovedFromOriginStr}: {distributionComment}{lastEditComment}"

        self.sectResolvedRegEx = "[Ss]ekce[_ ]vyřešena"
        self.sectResolved1P = ":<small>Tato sekce byla archivována na žádost uživatele: \\1</small>"
        self.sectResolved2P = ":<small>Tato sekce byla archivována na žádost uživatele: \\1 \\7</small>"
    
    def convertMonthNumberToShortName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        # CS wikipedia uses the English names
        return LocalBotEn.shortMonthNames[int(monthNumber) -1]
    
    def convertMonthNumberToLongName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        # CS wikipedia uses the English names
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
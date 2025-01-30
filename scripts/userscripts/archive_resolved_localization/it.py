#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.local_bot import LocalBot
from time import strftime
from datetime import datetime

class LocalBotIt(LocalBot):
    shortMonthNames = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
    longMonthNames = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']

    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)

        self.timeStampRegEx = "(?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2}),\ (?P<dd>[0-9]{1,2})\ (?P<MM>[a-zA-Zä]{3,10})\.?\ (?P<yyyy>[0-9]{4})\ \((?:CE[S]?T|UTC)\)"
        self.archiveTemplateName = "Template:Autoarchivio"
        self.headTemplate   = "{{Avviso archivio}}"

        self.excludeList = ( self.archiveTemplateName, 'Template:Autoarchivio/man' )
        self.errorCategory = "Categoria:{{ns:Project}}:Parametro Autoarchivio errato/SpBot"
        self.errorText = "== Non è stato possibile terminare l'archiviazione ==\n"
        self.errorText += f"La botolata delle ~~~~~ non ha avuto successo perché il template {self.archiveTemplateName} contiene parametri scorretti. %s"
        self.errorText += f"Dai un'occhiata alla [[{self.archiveTemplateName}|documentazione]] e correggi l'errore. Saluti --~~~~"
        self.errorText += f"\n\n[[{self.errorCategory}]]<!-- rimuovere questa riga, se il problema è stato risolto -->"
        self.errorTextSummary = "segnalazione di un errore"
        
        # template parameters
        self.optionsRegEx = "\{\{\ *(?:[Tt]emplate\:)?\ *[Aa]utoarchivio(?P<options>.*?)\}\}"
        self.templDoNotArchive = '\{\{\ *[Nn]icht\ *archivieren[|}]' # not used
        self.paramAge = 'GIORNI'
        self.paramArchive = 'ARCHIVIO'
        self.paramLevel = 'LIVELLO'
        self.paramTimeComparator = 'RIFERIMENTO'
        self.paramTimeComparatorCleared = 'resolved'
        self.paramTimeComparator = 'TIMEOUT'
        # edit summaries
        self.archiveSumTargetS = "archiviazione di 1 sezione da [[{sourcePage}]]"
        self.archiveSumTargetP = "archiviazione di {numOfSections} sezioni da [[{sourcePage}]]"
        self.archiveSumOriginS = "1 sezione"
        self.archiveSumOriginP = "{numberOfSectionsRemovedFromOrigin} sezioni"
        self.archiveSumOriginMulti = "{noOfDisuccionsToThisTarget} in [[{targetPageName}]]"
        self.firstNewSectionInArchiveSummary  = " (dopo la sezione [[{firstNewSectionInArchiveLink}]])"
        self.archiveSumLastEdit= " - modifica precedente: [[:User:%s|%s]], %s"
        self.archiveOverallSummary = "archiviate {numberOfSectionsRemovedFromOriginStr}: {distributionComment}{firstNewSectionInArchiveSummary}{lastEditComment}"

        self.sectResolvedRegEx = "(?:[Ss]ezione[\ _]risolta)"
        self.sectResolved1P = ":<small>Questa sezione è stata archiviata su richiesta di: \\1</small>"
        self.sectResolved2P = ":<small>Questa sezione è stata archiviata su richiesta di \\1 \\7</small>"

    def convertMonthNameToNumber(self, month: str) -> int:
        """
            month: a month name or number fetched from the signature
        """
        if month in LocalBotIt.shortMonthNames:
            return int(LocalBotIt.shortMonthNames.index(month) + 1)
        return int(LocalBotIt.longMonthNames.index(month) + 1)
    
    def convertMonthNumberToShortName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return LocalBotIt.shortMonthNames[int(monthNumber) -1].title() # Put first letter to upper case
    
    def convertMonthNumberToLongName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return LocalBotIt.longMonthNames[int(monthNumber) -1]

    def _getAllWeekVariablesForTargetPath(self) -> list:
        return ["((week:##))", "((week))"]
    
    def getReplacementDict(self, fullpagename: str, timestampToUse: datetime, yearToUse: str, monthNumberToUse: str) -> dict:
        """
            Builds up a dictionary with all ((variables)) as keys and substituted to actual values as values of the dict.
            fullpagename: current page to work on
            timestampToUse: the timestamp to parse
            yearToUse: the preselected year to take. This can be different if we are are using calendar weeks and are in an exception week.
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
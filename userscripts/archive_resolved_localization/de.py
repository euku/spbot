#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.local_bot import LocalBot
from time import strftime
from datetime import datetime

class LocalBotDe(LocalBot):
    shortMonthNames = ['Jan', 'Feb', 'Mrz', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
    longMonthNames = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']

    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)
        
        self.timeStampRegEx = "(?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2}),\ (?P<dd>[0-9]{1,2})\.?\ (?P<MM>[a-zA-Zä]{3,10})\.?\ (?P<yyyy>[0-9]{4})\ \((?:CE[S]?T|ME[S]?Z|UTC)\)"
        self.archiveTemplateName = "Vorlage:Autoarchiv-Erledigt"
        self.headTemplate   = "{{Archiv}}"      # Headtemplate to insert into new archivpages
        self.excludeList = (
                self.archiveTemplateName,
                "Vorlage:Erledigt",
                "Portal:Philosophie/Qualitätssicherung",
                "Wikipedia Diskussion:Hauptseite/Artikel des Tages/Chronologie der Artikel des Tages"
                )
        self.errorCategory = "Kategorie:{{ns:Project}}:Fehlerhafte Autoarchiv-Parameter/SpBot"
        self.errorText = "== Archivierung konnte nicht durchgeführt werden ==\n"
        self.errorText += "Beim Botlauf um ~~~~~ wurden fehlerhafte Optionen in der Vorlage 'Autoarchiv-Erledigt' festgestellt. %s"
        self.errorText += f"Beachte bitte die [[{self.archiveTemplateName}|Dokumentation der Vorlage]] und korrigiere den Fehler. Bei Unklarheiten kannst du [[:Benutzer:Euku|Euku]] fragen. Gruß --~~~~"
        self.errorText += f"\n\n[[{self.errorCategory}]]<!-- entferne diese Zeile, wenn das Problem behoben wurde -->"
        self.errorTextSummary = "Berichte Fehler"
        # template parameters
        self.optionsRegEx = "\{\{\ *(?:[Vv]orlage\:|[Tt]emplate\:)?\ *[Aa]utoarchiv-[Ee]rledigt(?P<options>.*?)\}\}"
        self.templDoNotArchive = r'\{\{\ *[Nn]icht\ *archivieren\s*[\|\}]'
        self.paramAge = 'ALTER'
        self.paramArchive = 'ZIEL'
        self.paramLevel = 'EBENE'
        self.paramTimeComparator = 'ZEITVERGLEICH'
        self.paramTimeComparatorCleared = 'erledigt'
        self.paramTimeComparator = 'ZEITBESCHRÄNKUNG'
        # edit summaries
        self.archiveSumTargetS = "Archiviere 1 Abschnitt von [[{sourcePage}]]"
        self.archiveSumTargetP = "Archiviere {numOfSections} Abschnitte von [[{sourcePage}]]"
        self.archiveSumOriginS = "1 Abschnitt"
        self.archiveSumOriginP = "{numberOfSectionsRemovedFromOrigin} Abschnitte"
        self.archiveSumOriginMulti  = "%d nach [[%s]]"
        self.archiveSumLastEdit= " - letzte Bearbeitung: [[:User:%s|%s]], %s"
        self.archiveOverallSummary = "Archiviere {numberOfSectionsRemovedFromOriginStr}: {distributionComment}{lastEditComment}"

        self.sectResolvedRegEx = "[Ee]rledigt"
        self.sectResolved1P    = ":<small>Archivierung dieses Abschnittes wurde gewünscht von: \\1</small>"
        self.sectResolved2P    = ":<small>Archivierung dieses Abschnittes wurde gewünscht von \\1, \\7</small>"
    
    def _getTimezone(self) -> str:
        return "Europe/Berlin"

    def convertMonthNameToNumber(self, month: str) -> int:
        """
            month: a month name or number fetched from the signature
        """
        # Exceptions not covered by the list above
        if month == 'Mär':
            return 3
        if month == 'Sept':
            return 9
        
        if month in LocalBotDe.shortMonthNames:
            return int(LocalBotDe.shortMonthNames.index(month) + 1)
        return int(LocalBotDe.longMonthNames.index(month) + 1)
    
    def convertMonthNumberToShortName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return LocalBotDe.shortMonthNames[int(monthNumber) -1]
    
    def convertMonthNumberToLongName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return LocalBotDe.longMonthNames[int(monthNumber) -1]
    
    def getReplacementDict(self, fullpagename: str, timestampToUse: datetime, yearToUse: str, monthNumberToUse: str) -> dict:
        """
            Builds up a dictionary with all ((variables)) as keys and substituted to actual values as values of the dict.
            fullpagename: current page to work on
            timestampToUse: the timestamp to parse
            yearToUse: the preselected year to take. This can be different if we are are using calendar weeks an are in an exception week.
            monthNumberToUse: the preselected month to take. This can be different if we are are using calendar weeks an are in an exception week.
        """
        return [( "((Jahr))"              , yearToUse),
                ( "((Monat:Lang))"        , self.convertMonthNumberToLongName(monthNumberToUse)),
                ( "((Monat:Kurz))"        , self.convertMonthNumberToShortName(monthNumberToUse)),
                # ( "((Monat:#))"           , int(monthNumberToUse)), # not used or wanted
                ( "((Monat:##))"          , str(monthNumberToUse).zfill(2)),
                ( "((Woche:##))"          , strftime("%V", timestampToUse)),
                ( "((Woche))"             , int(strftime("%V", timestampToUse))),
                ( "((Tag:##))"            , strftime("%d", timestampToUse)),
                ( "((FULLPAGENAME))"      , fullpagename),
                ( "((VOLLER_SEITENNAME))" , fullpagename),
                ( "((Lemma))"             , fullpagename),
                ( "((Quartal))"           , self.getQuarterName(timestampToUse, False, False) ),
                ( "((Quartal:##))"        , self.getQuarterName(timestampToUse, False, True) ),
                ( "((Quartal:i))"         , self.getQuarterName(timestampToUse, True, False) ),
                ( "((Quartal:I))"         , self.getQuarterName(timestampToUse, True, False).upper() ),
                ( "((Halbjahr))"          , self.getHalfyearName(timestampToUse, False, False) ),
                ( "((Halbjahr:##))"       , self.getHalfyearName(timestampToUse, False, True) ),
                ( "((Halbjahr:i))"        , self.getHalfyearName(timestampToUse, True, False) ),
                ( "((Halbjahr:I))"        , self.getHalfyearName(timestampToUse, True, False).upper() )]
    
    def _getAllWeekVariablesForTargetPath(self) -> list:
        return ["((Woche:##))", "((Woche))"]
    

    def applyLocalModifications(self, originalText: str) -> str:
        # diese Ersetzungen sind erst mal deaktiviert, weil sie zu haeufig Schaden anrichten
        if False:
            excludeTags = ["comment", "nowiki", "code"]
            # won't work for but also won't harm:
            # {{Autoarchiv-Erledigt|Alter=1|Ziel=((FULLPAGENAME))/Archiv|aktuelles Archiv={{FULLPAGENAME}}/Archiv|Zeigen=Ja}}
            rmParamRegEx = "(\{\{\s*?[Aa]utoarchiv\-[Ee]rledigt[^}]*)\|[^}]*%s\s*=\s*%s[\n\r\s]*([^}]*?\}\})"
            modifiedText = textlib.replaceExcept(originalText, rmParamRegEx % ("Mindestabschnitte", "\d+?"), "\\1\\2", excludeTags)
            modifiedText = textlib.replaceExcept(modifiedText, rmParamRegEx % ("Mindestbeiträge", "\d+?"), "\\1\\2", excludeTags)
            modifiedText = textlib.replaceExcept(modifiedText, rmParamRegEx % ("Frequenz","[a-zäöü\:]*"), "\\1\\2", excludeTags)
            modifiedText = textlib.replaceExcept(modifiedText, rmParamRegEx % ("Klein", "[JjAaNnEeIiNn]*"), "\\1\\2", excludeTags)
            modifiedText = textlib.replaceExcept(modifiedText, rmParamRegEx % ("Modus", "[Eerledigt]*"), "\\1\\2", excludeTags)
            modifiedText = textlib.replaceExcept(modifiedText, rmParamRegEx % ("Zeigen", "[JjAa]+"), "\\1\\2", excludeTags)
            
        return originalText
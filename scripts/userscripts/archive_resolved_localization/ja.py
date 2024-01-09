#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.local_bot import LocalBot
from time import strftime
from datetime import datetime

class LocalBotJa(LocalBot):
    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)

        self.timeStampRegEx = "(?P<yyyy>\d{4})年(?P<MM>\d{1,2})月(?P<dd>\d{1,2})日\ \(.\)\ (?P<hh>\d{2})\:(?P<mm>\d{2})\ \(UTC\)"
        self.archiveTemplateName = "Template:Autoarchive resolved section"
        self.headTemplate   = "{{Talkarchive}}"
        self.excludeList = ( self.archiveTemplateName )
        self.errorCategory = "Category:Autoarchive に誤った引数が渡されているページ/SpBot"
        self.errorText = "== 過去ログ化が正常終了しませんでした ==\n"
        self.errorText += f"~~~~~ のボット作業は失敗しました。原因はテンプレート {self.archiveTemplateName} に誤った引数が渡されていたためです： %s"
        self.errorText += f"[[{self.archiveTemplateName}|ドキュメント]]を確認して間違いを訂正してください。よろしくお願いします。 --~~~~"
        self.errorText += f"\n\n[[{self.errorCategory}]]<!-- 問題が解決したらこの行は除去してください -->"
        self.errorTextSummary = "エラーを報告"
        # template parameters
        self.optionsRegEx = "\{\{\ *(?:[Tt]emplate\:)?\ *[Aa]utoarchive\ resolved\ section(?P<options>.*?)\}\}"
        self.templDoNotArchive = '\{\{\ *[Nn]icht\ *archivieren[|}]'
        self.paramAge = 'AGE'
        self.paramArchive = 'ARCHIVE'
        self.paramLevel = 'LEVEL'
        self.paramTimeComparator = 'TIMECOMAPARE'
        self.paramTimeComparatorCleared = 'resolved'
        self.paramTimeComparator = 'TIMEOUT'
        # edit summaries
        self.archiveSumTargetS = "[[{sourcePage}]] から節 1 個を過去ログ化"
        self.archiveSumTargetP = "[[{sourcePage}]] から節 {numOfSections} 件を過去ログ化"
        self.archiveSumOriginS = "節 1 件"
        self.archiveSumOriginP = "節 {numberOfSectionsRemovedFromOrigin} 件"
        self.archiveSumOriginMulti = "%d件を%sに過去ログ化"
        self.archiveSumLastEdit= " - 前の編集: [[:User:%s|%s]], %s"
        self.archiveOverallSummary = "{numberOfSectionsRemovedFromOriginStr} を過去ログ化: {distributionComment}{lastEditComment}"

        self.sectResolvedRegEx = "(?:[Ss]ection[\ _]resolved|[Rr]esolved[\ _]section)"
        self.sectResolved1P    = ":<small>この節は次の利用者の依頼で過去ログ化されました： \\1</small>"
        self.sectResolved2P    = ":<small>この節は次の利用者の依頼で過去ログ化されました： \\1 \\7</small>"
    
    def convertMonthNumberToShortName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return f"{monthNumber} 月"
    
    def convertMonthNumberToLongName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return f"{monthNumber} 月"
    
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
                ( "((quarter))"           , self.getQuarterName(timestampToUse, False, False) ),
                ( "((quarter:##))"        , self.getQuarterName(timestampToUse, False, True) ),
                ( "((quarter:i))"         , self.getQuarterName(timestampToUse, True, False) ),
                ( "((quarter:I))"         , self.getQuarterName(timestampToUse, True, False).upper() ),
                ( "((half-year))"         , self.getHalfyearName(timestampToUse, False, False) ),
                ( "((half-year:##))"      , self.getHalfyearName(timestampToUse, False, True) ),
                ( "((half-year:i))"       , self.getHalfyearName(timestampToUse, True, False) ),
                ( "((half-year:I))"       , self.getHalfyearName(timestampToUse, True, False).upper() )]
#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.local_bot import LocalBot
from time import strftime
from datetime import datetime

class LocalBotKo(LocalBot):
    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)
        
        self.timeStampRegEx = "(?P<yyyy>\d{4})년\ (?P<MM>\d{1,2})월\ (?P<dd>\d{1,2})일\ \(.\)\ (?P<hh>\d{2})\:(?P<mm>\d{2})\ \(KST\)"
        self.archiveTemplateName = "틀:완료된 토론 자동 보존"
        self.headTemplate = "{{보존}}"
        self.excludeList = ( self.archiveTemplateName )
        self.errorCategory = "분류:잘못된 자동 보존 설정이 있는 문서"
        self.errorText = "== 보존을 처리하지 못했습니다 ==\n"
        self.errorText += f"봇이 ~~~~~ 에 토론을 보존하려 했으나, 성공적이지 못했습니다. 틀 {self.archiveTemplateName} 이 부정확한 변수를 포함했기 때문입니다. %s"
        self.errorText += f"[[{self.archiveTemplateName}|설명 문서]] 를 보고 문제를 고쳐 주세요. 감사합니다. --~~~~"
        self.errorText += f"\n\n[[{self.errorCategory}]]<!--문제가 해결되었다면 이 줄을 지우세요. -->"
        self.errorTextSummary = "문제 보고"
        # template parameters / 틀 변수
        self.optionsRegEx = "\{\{\ *(?:틀\:)?\ *완료된\ 토론\ 자동\ 보존(?P<options>.*?)\}\}"
        self.templDoNotArchive = '\{\{\ *보존i\ 중단\}\}'
        self.paramAge = '날짜'
        self.paramArchive = '보존'
        self.paramLevel = '단위'
        self.paramTimeComparator = '시간 비교'
        self.paramTimeComparatorCleared = '완료된 토론'
        self.paramTimeComparator = '타임아웃'
        #edit summaries/편집 요약
        self.archiveSumTargetS = "1개의 문단을 [[{sourcePage}]] 에서 가져옴"
        self.archiveSumTargetP = "{numOfSections}개의 문단을 [[{sourcePage}]] 에서 가져옴"
        self.archiveSumOriginS = "1개의 문단"
        self.archiveSumOriginP = "{numberOfSectionsRemovedFromOrigin}개의 문단"
        self.archiveSumOriginMulti  = "{noOfDisuccionsToThisTarget} 을(를) [[{targetPageName}]]"
        self.firstNewSectionInArchiveSummary  = ""
        self.archiveSumLastEdit = "-이전 편집: [[:User:%s|%s]],%s"
        self.archiveOverallSummary = "보존 {numberOfSectionsRemovedFromOriginStr}: {distributionComment}{firstNewSectionInArchiveSummary}{lastEditComment}"

        self.sectResolvedRegEx = "(?:완료된\ 토론)"
        self.sectResolved1P = ":<small>이 문단은 다음 사용자의 요청에 의해 보존되었습니다: \\1</small>"
        self.sectResolved2P = ":<small>이 문단은 다음 사용자의 요청에 의해 보존되었습니다: \\1 \\7</small>"
    
    def _getAllWeekVariablesForTargetPath(self) -> list:
        return ["((주:##))", "((주))"]
    
    def getReplacementDict(self, fullpagename: str, timestampToUse: datetime, yearToUse: str, monthNumberToUse: str) -> dict:
        """
            Builds up a dictionary with all ((variables)) as keys and substituted to actual values as values of the dict.
            fullpagename: current page to work on
            timestampToUse: the timestamp to parse
            yearToUse: the preselected year to take. This can be different if we are are using calendar weeks an are in an exception week.
            monthNumberToUse: the preselected month to take. This can be different if we are are using calendar weeks an are in an exception week.
        """
        return [( "((년))"                 , yearToUse), # year
                # there is no ((month:long)) or ((month:short)) in ko.wikipedia
                ( "((월))"                 , int(monthNumberToUse)), # month:#
                ( "((월:##))"              , str(monthNumberToUse).zfill(2)), # month:##
                ( "((주:##))"              , strftime("%V", timestampToUse)), # week:##
                ( "((주))"                 , int(strftime("%V", timestampToUse))), # week
                ( "((일:##))"              , strftime("%d", timestampToUse)), # day
                ( "((fullpagename))"      , fullpagename),
                ( "((Fullpagename))"      , fullpagename),
                ( "((FULLPAGENAME))"      , fullpagename),
                ( "((분기))"               , self.getQuarterName(timestampToUse, False, False) ),	# quarter
                ( "((분기:##))"            , self.getQuarterName(timestampToUse, False, True) ),	# quarter
                ( "((분기:i))"             , self.getQuarterName(timestampToUse, True, False) ),	# quarter
                ( "((분기:I))"             , self.getQuarterName(timestampToUse, True, False).upper() ),	# quarter
                ( "((반년))"               , self.getHalfyearName(timestampToUse, False, False) ),	#half-year
                ( "((반년:##))"            , self.getHalfyearName(timestampToUse, False, True) ),	#half-year
                ( "((반년:i))"             , self.getHalfyearName(timestampToUse, True, False) ),	#half-year
                ( "((반년:I))"             , self.getHalfyearName(timestampToUse, True, False).upper() )]	#half-year
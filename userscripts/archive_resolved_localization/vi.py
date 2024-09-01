#!/usr/bin/python
# -*- coding: utf-8 -*-
from archive_resolved_localization.local_bot import LocalBot
from time import strftime
from datetime import datetime

class LocalBotVi(LocalBot):
    longMonthNames = ["Một", "Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy", "Tám", "Chín", "Mười", "Mười Một", "Mười Hai"]

    def __init__(self, projectId: str) -> None:
        super().__init__(projectId)
        
        self.timeStampRegEx = "(?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2}),\ ngày\ (?P<dd>[0-9]{1,2})\ [Tt]háng\ (?P<MM>\d{1,2})\ năm\ (?P<yyyy>[0-9]{4})\ \(UTC\)"
        self.archiveTemplateName = "Bản mẫu:Autoarchive resolved section"
        self.headTemplate   = "{{Talkarchive}}"
        self.excludeList = ( self.archiveTemplateName, f"{{self.archiveTemplateName}}/doc" )
        self.errorCategory = "Thể loại:Bản mẫu lưu trữ thảo luận sử dụng tham số sai"
        self.errorText = "== Lưu trữ không thành công ==\n"
        self.errorText += f"Lưu trữ tại ~~~~~ không thành công vì bản mẫu {self.archiveTemplateName} chứa tham số sai. %s"
        self.errorText += f"Xin hãy xem lại [[{self.archiveTemplateName}|documentation]] và sửa các lỗi có trong bản mẫu. Trân trọng! --~~~~"
        self.errorText += f"\n\n[[{self.errorCategory}]]<!-- xin hãy xóa dòng này nếu vấn đề đã được giải quyết -->"
        self.errorTextSummary = "reporting an error"
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
        self.archiveSumTargetS = "Lưu trữ một đề mục từ [[{sourcePage}]]"
        self.archiveSumTargetP = "Lưu trữ {numOfSections} đề mục từ [[{sourcePage}]]"
        self.archiveSumOriginS = "1 đề mục"
        self.archiveSumOriginP = "{numberOfSectionsRemovedFromOrigin} đề mục"
        self.archiveSumOriginMulti  = "{noOfDisuccionsToThisTarget} tới [[{targetPageName}]]"
        self.firstNewSectionInArchiveSummary  = " (kể từ sau đề mục [[{firstNewSectionInArchiveLink}]])"
        self.archiveSumLastEdit= " - sửa đổi trước đó: [[User:%s|%s]], %s"
        self.archiveOverallSummary = "lưu trữ {numberOfSectionsRemovedFromOriginStr}: {distributionComment}{firstNewSectionInArchiveSummary}{lastEditComment}"

        self.sectResolvedRegEx = "(?:[Ss]ection[\ _]resolved|[Rr]esolved[\ _]section)"
        self.sectResolved1P    = ":<small>Đề mục này đã được lưu trữ theo yêu cầu của: \\1</small>"
        self.sectResolved2P    = ":<small>Đề mục này đã được lưu trữ theo yêu cầu của: \\1 \\7</small>"
    
    def convertMonthNumberToShortName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return f"Tháng {monthNumber}"
    
    def convertMonthNumberToLongName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        return "Tháng " + LocalBotVi.longMonthNames[int(monthNumber) -1]
    
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
        return [( "((year))"          , yearToUse),
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
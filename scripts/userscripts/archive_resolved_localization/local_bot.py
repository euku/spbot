#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
    This file extracts all the project and translation related stuff from the main bot code
"""
from datetime import datetime
import time
from pytz import timezone

class LocalBot():
    multi_lang_projects = ['meta', 'commons', 'wikidata', 'wikimania', 'wikifunctions', 'species']

    def __init__(self, projectId: str) -> None:
        """
            project_id: like dewikip, enwikisource or commons
        """
        self.projectId = projectId
        self.projectCode, self.projectFamily = LocalBot.splitInCodeAndFamily(projectId)
    
    def splitInCodeAndFamily(projectId: str) -> tuple:
        if projectId in LocalBot.multi_lang_projects:
            projectCode = projectId
            projectFamily = projectId
        else:
            projectCode = projectId[:2]
            projectFamily = projectId[2:]
        return projectCode, projectFamily

    def _getTimezone(self) -> str:
        return "UTC"

    def getUtcDiff(self) -> datetime:
        """
            Difference between the UTC and local timezone
        """
        tz = timezone(self._getTimezone())
        utc = timezone('UTC')
        now = datetime.now()
        utc.localize(now)
        return utc.localize(now) - tz.localize(now)
    
    def convertMonthNameToNumber(self, month: str) -> int:
        """
            month: a month name or number fetched from the signature
        """
        # default: just the number
        return int(month)
    
    def convertMonthNumberToShortName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        # default: just the number
        return str(monthNumber)
    
    def convertMonthNumberToLongName(self, monthNumber) -> str:
        """
            monthNumber: a month number as string or int
        """
        # default: just the number
        return str(monthNumber)

    def getHalfyearName(self, stamp, roman : bool, fill : bool):
        """
            roman: instead use I, II, III, IV
            fill: zero fill the number to 2 digits length
        """
        halfyearI = '1' if int(time.strftime("%m", stamp)) <= 6 else '2'
        halfyearI = ('0' if fill else '') + halfyearI
        if halfyearI == '1' or halfyearI == '01':
            return 'i' if roman else halfyearI
        return 'ii' if roman else halfyearI
    
    def getQuarterName(self, stamp, roman : bool, fill : bool):
        """
            roman: instead use I, II, III, IV
            fill: zero fill the number to 2 digits length
        """
        month = int(time.strftime("%m", stamp))
        quater = ('0' if fill else '') + str(int((month -1) / 3) +1)
        if quater == '1' or quater == '01':
            return 'i' if roman else quater
        elif quater == '2' or quater == '02':
            return 'ii' if roman else quater
        elif quater == '3' or quater == '03':
            return 'iii' if roman else quater
        elif quater == '4' or quater == '04':
            return 'iv' if roman else quater
        return None # error
    
    def getReplacementDict(self, fullpagename: str, timestampToUse: datetime, yearToUse: str, monthNumberToUse: str) -> dict:
        """
            Builds up a dictionary with all ((variables)) as keys and substituted to actual values as values of the dict.
            fullpagename: current page to work on
            timestampToUse: the timestamp to parse
            yearToUse: the preselected year to take. This can be different if we are are using calendar weeks an are in an exception week.
            monthNumberToUse: the preselected month to take. This can be different if we are are using calendar weeks an are in an exception week.
        """
        raise NotImplementedError("Please Implement this method")
    
    def _getAllWeekVariablesForTargetPath(self) -> list:
        """
            A list of all variables in the target parameter that reference the ((week))
        """
        raise NotImplementedError("Please Implement this method")
    
    def applyLocalModifications(self, originalText: str) -> str:
        """
        No changes by default
        """
        return originalText

    def mustNotArchiveToMainNamespace(self) -> bool:
        """
        Does not allow to create an archive in the (Main) namespace
        """
        return True
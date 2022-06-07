#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
These command line parameters can be used to specify how to work:

&params;

-donotsave        Pages and log files will not be saved on Wikipedia.
                  The bot just simulates the run and saves local log files under ./logs/

-nolocalelog      Logs will not be saved at all for this run.

-page             Works on a specified page. Otherwise it runs
                  over all pages that use 'archiveTemplateName' (Vorlage:Autoarchiv-Erledigt)

-project          'nothing': de.WP
                  commons: WM Commons
		  wikidata: wikidata
                  species: species
                  dewikisource, {de,en}wiktionary: the other projects...


authors:
	?- Nov. 2007:	Rhododendronbusch
	Nov. 2007- *:	Euku

"""
import sys              # To not have pywikibot and archivingext in one dir we'll import sys
sys.path.append(".")
assert sys.version_info >= (3,5)
import re               # Used for regular expressions
import os               # used for os.getcwd()
import pywikibot        # Wikipedia-pybot-framework
from pywikibot import config, pagegenerators, textlib
import locale			# for German
from time import localtime, strftime, mktime    # strftime-Function and related
from datetime import tzinfo, timedelta, datetime
from pytz import timezone

cosmetic_changes = False # NOT on talk pages!

#
# Local exceptions
#
class Error(Exception):
    """Archvierungsfehler"""

class NoOptions(Error):
    """Keine Optionen gefunden"""
    def __init__(self, msg=None):
        pywikibot.output("\t *** Keine Autoarchivvorlage gefunden oder falsches Format ***\n")
        self.msg = msg

    def getMsg(self):
        return self.msg

class WrongOptions(Error):
    """Optionen fehlerhaft"""
    def __init__(self):
        pywikibot.output("\t *** Falsches Format der Optionen ***\n")

def getUtcDiff(project):
    if (project[:2] == "de"):
       tzname = "Europe/Amsterdam"
    else:
       tzname = "UTC"
    tz = timezone(tzname)
    utc = timezone('UTC')
    now = datetime.now()
    utc.localize(now)
    delta =  utc.localize(now) - tz.localize(now)
    return delta


#
# *** DECLARATIONS ***
#
class Discussion:
    def __init__(self, pagename):
        """
        Initiate Object
        """
        self.titleOffsetStart    = 0       # offset, where title of disc starts
        self.hasDoNotArchiveTmpl = False   # is a temple used for this section, that denies archiving
        self.contentOffsetStart  = 0       # offset, where text starts
        self.contentOffsetEnd    = 0       # offset, where text ends
        self.content             = ""     # content of disc
        self.title               = ""     # Title of disc
        self.titleClear          = ""
        self.age                 = 0.0     # How old is the discussion? in days
        self.lastContributionAge = 0.0     # How old is the last timestamp? in days
        self.timestampClearedFlag= None    # The timestamp found in the clead template
        self.clearedAge          = 0       # How long this discussion has a cleared flag or not
        self.numContributions    = 0       # How many contributions were made to this discussion
        self.firstContribution   = None    # Date of the first contribution
        self.headlineLevel       = 0       # depth of headline-level
        self.pageOrigin          = pagename      # Name of the Page the discussion is from

    def __repr__(self):
        pass

    def setTitle(self, title, titleClear = ""):
        """
        Sets the Titletext of an discussion.
        """
        self.title = title
        self.titleClear = titleClear.strip()

    def getTitle(self, clear = False):
        if clear:
            return self.titleClear
        else:
            return self.title

    def getTitleLength(self):
        return len(self.title)

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

    def retrieveContent2(self, text):
        self.content = text[self.start:self.end]


    def setContent(self, content = ""):
        self.content = content

    def setStart(self, start):
        self.start = start

    def setEnd(self, end):
        self.end = end

    def setHeadlineLevel(self, headlineLevel):
        self.headlineLevel = headlineLevel

    def getHeadlineLevel(self):
        return self.headlineLevel

    def examine(self, bot):
        # Extract dates from content
        # 1 date = 1 contribution
        p1 = re.compile(bot.timeStampRegEx, re.I)
        matches1 = p1.finditer(self.content)
        agesList1 = []
        timestampList = []
        today = mktime((datetime.now() + getUtcDiff(bot.currentProject)).timetuple())
        for match1 in matches1:
            hh1 = match1.group('hh')
            mm1 = match1.group('mm')
            dd1 = match1.group('dd')
            MM1 = match1.group('MM')
            yy1 = match1.group('yyyy')

            try:
               dateToCheck = mktime((int(yy1), int(self.replaceToDate(MM1)), int(dd1), int(hh1), int(mm1), 0, 0, 0, 0))  # microsec. since 1970
               actualAge = (today - dateToCheck)/60/60/24
               agesList1.append(actualAge)
               timestampList.append(dateToCheck)
            except:
               actualAge = 0

        if agesList1 != [] and timestampList != []:
            self.firstContribution = timestampList[0]
            self.age = agesList1[0]
            self.lastContributionAge = min(agesList1)
            self.numContributions = len(agesList1)
            del agesList1
            del actualAge
            del timestampList
        del p1
        del matches1

        # Now examine if discussion has a "cleared" flag and
        # check how old it is
        p = re.compile("\{\{" + bot.sectResolvedRegEx + "[\s]{0,5}\|.*?" + bot.timeStampRegEx + "[^}]*?\}\}", re.I | re.S)
        doNotArchivePattern = re.compile(bot.templDoNotArchive, re.I)
        # remove comments and nowiki tags
        clearedContent = textlib.replaceExcept(self.content, r"(?s)<!\-\-.*?\-\->", "", [])
        clearedContent = textlib.replaceExcept(clearedContent, r"(?s)<nowiki>.*?</nowiki>", "", [])
        clearedContent = textlib.replaceExcept(clearedContent, r"(?s)<pre>.*?</pre>", "", [])
        matches = p.finditer(clearedContent)
        agesList = []
        for match in matches:
            hh = match.group('hh')
            mm = match.group('mm')
            dd = match.group('dd')
            MM = match.group('MM')
            yy = match.group('yyyy')
            try:
               dateToCheck = mktime((int(yy), int(self.replaceToDate(MM)), int(dd), int(hh), int(mm), 0, 0, 0, 0)) # microsec. since 1970
               actualAge = (today - dateToCheck)/60/60/24
               self.timestampClearedFlag = dateToCheck
               agesList.append(actualAge)
            except:
               actualAge = 0

        if agesList != []:
            self.clearedAge = min(agesList)
        del p
        del matches
        #pywikibot.output("Age: %3.2f\tCleared: %3.2f\tTitle: %s" % (self.age, self.clearedAge, self.titleClear))
        self.hasDoNotArchiveTmpl = doNotArchivePattern.search(clearedContent) != None

    def checkCleared(self, maxAgeCleared, notClearedTimeout):
        if self.clearedAge > maxAgeCleared or (not self.hasDoNotArchiveTmpl and notClearedTimeout > 0 and self.lastContributionAge >= notClearedTimeout):
            return True
        else:
            return False

    def getClearedAge(self):
        return self.clearedAge

    def replaceToDate(self, mm):
        if mm in ["Jan", "January"]:
            return 1
        if mm in ["Feb", "February"]:
            return 2
        if mm in ["Mär", "Mrz", "March"]:
            return 3
        if mm in ["Apr", "April"]:
            return 4
        if mm in ["Mai", "May"]:
            return 5
        if mm in ["Jun", "June"]:
            return 6
        if mm in ["Jul", "July"]:
            return 7
        if mm in ["Aug", "August"]:
            return 8
        if mm in ["Sep", "September"]:
            return 9
        if mm in ["Okt", "Oct", "October"]:
            return 10
        if mm in ["Nov", "November"]:
            return 11
        if mm in ["Dez", "Dec", "December"]:
            return 12
        return int(mm)

    def getAge(self):
        return self.age

    def getContributions(self):
        return self.numContributions

    def getArchivingTarget(self, target, useTimeComparatorCleared, bot):
        return self.parseArchivingTarget(target, useTimeComparatorCleared, bot)

    def parseArchivingTarget(self, parseString, useTimeComparatorCleared, bot):
        """
        * ((Tag)): Tag, z.B. 1, 24
        * ((Tag:##)): zweistelliger Tag, z.B. 01, 24
        * ((Tag:Kurz)): abgekürzter Tagesname, z.B. Mo, Fr
        * ((Tag:Lang)): Tagesname, z.B. Montag, Freitag
        * ((Monat)): Monat, z.B. 1, 10
        * ((Monat:##)): zweistelliger Monat, z.B. 01, 10
        * ((Monat:Kurz)): abgekürzter Monatsname, z.B. Jan, Okt
        * ((Monat:Lang)): Monatsname, z.B. Januar, Oktober
        * ((Quartal)): Quartal, z.B. 1, 3
        * ((Quartal:##)): zweistelliges Quartal, z.B. 01, 03
        * ((Quartal:i)): Quartal (kleine römische Ziffern), z.B. i, iv
        * ((Quartal:I)): Quartal (große römische Ziffern), z.B. I, IV
        * ((Halbjahr)): Halbjahr, z.B. 1, 2
        * ((Halbjahr:##)): zweistelliges Halbjahr, z.B. 01, 02
        * ((Halbjahr:i)): Halbjahr (kleine römische Ziffern), z.B. i, ii
        * ((Halbjahr:I)): Halbjahr (große römische Ziffern), z.B. I, II
        * ((Woche)): Woche, z.B. 1, 43
        * ((Woche:##)): zweistelliges Woche, z.B. 01, 43
        * ((Jahr)): Jahr, z.B. 2006, 2007
        """
        def getHalfyearName(stamp, roman = False, fill = False):
            month = strftime("%m", stamp)
            hj1 = "1"
            hj2 = "2"

            if fill:
                hj1 = "01"
                hj2 = "02"
                
            if roman:
                hj1 = "i"
                hj2 = "ii"
            
            if month in ("01","02","03","04","05","06"):
                return hj1
            else:
                return hj2
        
        def getQuarterName(stamp, roman = False, fill = False):
            month = strftime("%m", stamp)
            re1 = "1"
            re2 = "2"
            re3 = "3"
            re4 = "4"
            
            if fill:
                re1 = "01"
                re2 = "02"
                re3 = "03"
                re4 = "04"
            
            if roman:
                re1 = "i"
                re2 = "ii"
                re3 = "iii"
                re4 = "iv"
            
            if month in ("01","02","03"):
                return re1
            if month in ("04","05","06"):
                return re2
            if month in ("07","08","09"):
                return re3
            if month in ("10","11","12"):
                return re4
        
        def ClearTitle(title):
            p = re.compile("\[\[(?P<cl>.*)\]\]", re.I)
            m = p.match(title)
            if m:
                return m.group("cl")
            else:
                return title
        
        def ClearTitleNSD(title):
            p = re.compile("\[\[((?P<ns>.*):){0,1}(?P<cl>.*)\]\]", re.I)
            m = p.match(title)
            if m:
                return m.group("cl")
            else:
                return title

        def getGermMonthShort(enMonth):
            if enMonth == 'Mar':	return 'Mrz'
            if enMonth == 'May':	return 'Mai'
            if enMonth == 'Oct':	return 'Okt'
            if enMonth == 'Dec':	return 'Dez'
            return enMonth
        
        def getGermMonthLong(enMonth):
            if enMonth == "January":	return "Januar"
            if enMonth == "February":	return "Februar"
            if enMonth == "March":		return "März"
            if enMonth == "May":		return "Mai"
            if enMonth == 'June':		return 'Juni'
            if enMonth == 'July':		return 'Juli'
            if enMonth == "October":	return "Oktober"
            if enMonth == "December":	return "Dezember"
            return enMonth
                
        def getJaMonth(monthCount):
            return monthCount + "月"

        if (useTimeComparatorCleared):
             stamp = localtime(self.timestampClearedFlag)
        else:
             stamp = localtime(self.firstContribution)

        isExceptionDate = stamp[0]==2014 and stamp[1]==12 and stamp[2]>=29
        exceptionYear = "2014"
        exceptionMonth = "12"
        if bot.currentProject in ["dewikip", "dewiktionary", "dewikisource", 'dewikiversity']:
            # German
            replStrings = [( "((Jahr))"          , (strftime("%Y", stamp), exceptionYear)[isExceptionDate] ), # exception
                       ( "((Monat:Lang))"        , (getGermMonthLong(strftime("%B", stamp)), "Dezember")[isExceptionDate]),
                       ( "((Monat:Kurz))"        , (getGermMonthShort(strftime("%b", stamp)), "Dez")[isExceptionDate] ),
                       ( "((Monat:##))"          , (strftime("%m", stamp), "12")[isExceptionDate] ),
                       ( "((Woche:##))"          , ("%02d" % int(strftime("%V", stamp)), "01")[isExceptionDate] ),
                       ( "((Woche))"             , (strftime("%V", stamp), "1")[isExceptionDate] ),
                       ( "((Tag:##))"            , "%02d" % int(strftime("%d", stamp))),
                       ( "((fullpagename))"      , self.pageOrigin),
                       ( "((Fullpagename))"      , self.pageOrigin),
                       ( "((FULLPAGENAME))"      , self.pageOrigin),
                       ( "((VOLLER_SEITENNAME))" , self.pageOrigin),
                       ( "((VOLLER SEITENNAME))" , self.pageOrigin),
                       ( "((Lemma))"             , self.pageOrigin),
                       ( "((Überschrift))"       , ClearTitle(self.titleClear.strip() ) ),
                       ( "((Überschrift-NSD))"   , ClearTitleNSD(self.titleClear.strip() ) ),
                       ( "((Quartal))"           , getQuarterName(stamp, False, False) ),
                       ( "((Quartal:##))"        , getQuarterName(stamp, False, True) ),
                       ( "((Quartal:i))"         , getQuarterName(stamp, True, False) ),
                       ( "((Quartal:I))"         , getQuarterName(stamp, True, False).upper() ),
                       ( "((Halbjahr))"          , getHalfyearName(stamp, False, False) ),
                       ( "((Halbjahr:##))"       , getHalfyearName(stamp, False, True) ),
                       ( "((Halbjahr:i))"        , getHalfyearName(stamp, True, False) ),
                       ( "((Halbjahr:I))"        , getHalfyearName(stamp, True, False).upper() )]
        elif bot.currentProject in ['cswikip', 'jawikip']:
           replStrings = [( "((year))"          , (strftime("%Y", stamp), exceptionYear)[isExceptionDate] ), # exception
                       ( "((month:long))"       , (getJaMonth(strftime("%m", stamp)), "December")[isExceptionDate] ),
                       ( "((month:short))"      , (getJaMonth(strftime("%m", stamp)), "Dec")[isExceptionDate] ),
                       ( "((month:##))"         , (strftime("%m", stamp), "12")[isExceptionDate] ),
                       ( "((week:##))"          , ("%02d" % int(strftime("%V", stamp)), "01")[isExceptionDate] ),
                       ( "((week))"             , (strftime("%V", stamp), "1")[isExceptionDate] ),
                       ( "((day:##))"            , "%02d" % int(strftime("%d", stamp))),
                       ( "((fullpagename))"      , self.pageOrigin),
                       ( "((Fullpagename))"      , self.pageOrigin),
                       ( "((FULLPAGENAME))"      , self.pageOrigin),
                       ( "((quarter))"           , getQuarterName(stamp, False, False) ),
                       ( "((quarter:##))"        , getQuarterName(stamp, False, True) ),
                       ( "((quarter:i))"         , getQuarterName(stamp, True, False) ),
                       ( "((quarter:I))"         , getQuarterName(stamp, True, False).upper() ),
                       ( "((half-year))"         , getHalfyearName(stamp, False, False) ),
                       ( "((half-year:##))"      , getHalfyearName(stamp, False, True) ),
                       ( "((half-year:i))"       , getHalfyearName(stamp, True, False) ),
                       ( "((half-year:I))"       , getHalfyearName(stamp, True, False).upper() )]
        elif bot.currentProject == 'kowikip':
           replStrings = [( "((년))"            , (strftime("%Y", stamp), exceptionYear)[isExceptionDate] ), # exception # year
                       ( "((월))"               , (strftime("%m", stamp), "12")[isExceptionDate] ), # month
                       ( "((월:##))"            , ("%02d" % int(strftime("%m", stamp)), "12")[isExceptionDate] ), # month:##
                       ( "((주))"               , (strftime("%V", stamp), "1")[isExceptionDate] ), # week
                       ( "((주:##))"            , ("%02d" % int(strftime("%V", stamp)), "01")[isExceptionDate] ), # week:##
                       ( "((일:##))"            , "%02d" % int(strftime("%d", stamp))), # day
                       ( "((fullpagename))"     , self.pageOrigin),
                       ( "((Fullpagename))"     , self.pageOrigin),
                       ( "((FULLPAGENAME))"     , self.pageOrigin),
                       ( "((분기))"              , getQuarterName(stamp, False, False) ),	# quarter
                       ( "((분기:##))"           , getQuarterName(stamp, False, True) ),	# quarter
                       ( "((분기:i))"            , getQuarterName(stamp, True, False) ),	# quarter
                       ( "((분기:I))"            , getQuarterName(stamp, True, False).upper() ),	# quarter
                       ( "((반년))"              , getHalfyearName(stamp, False, False) ),	#half-year
                       ( "((반년:##))"           , getHalfyearName(stamp, False, True) ),	#half-year
                       ( "((반년:i))"            , getHalfyearName(stamp, True, False) ),	#half-year
                       ( "((반년:I))"            , getHalfyearName(stamp, True, False).upper() )]	#half-year
        else:
           # English
           replStrings = [( "((year))"          , (strftime("%Y", stamp), exceptionYear)[isExceptionDate] ), # exception
                       ( "((month:long))"       , (strftime("%B", stamp), "December")[isExceptionDate] ),
                       ( "((month:short))"      , (strftime("%b", stamp), "Dec")[isExceptionDate] ),
                       ( "((month:##))"         , (strftime("%m", stamp), "12")[isExceptionDate] ),
                       ( "((week:##))"          , ("%02d" % int(strftime("%V", stamp)), "01")[isExceptionDate] ),
                       ( "((week))"             , (strftime("%V", stamp), "1")[isExceptionDate] ),
                       ( "((day:##))"            , "%02d" % int(strftime("%d", stamp))),
                       ( "((fullpagename))"      , self.pageOrigin),
                       ( "((Fullpagename))"      , self.pageOrigin),
                       ( "((FULLPAGENAME))"      , self.pageOrigin),
                       ( "((lemma))"             , self.pageOrigin),
                       ( "((headline))"          , ClearTitle(self.titleClear.strip() ) ),
                       ( "((headline-NSD))"      , ClearTitleNSD(self.titleClear.strip() ) ),
                       ( "((quarter))"           , getQuarterName(stamp, False, False) ),
                       ( "((quarter:##))"        , getQuarterName(stamp, False, True) ),
                       ( "((quarter:i))"         , getQuarterName(stamp, True, False) ),
                       ( "((quarter:I))"         , getQuarterName(stamp, True, False).upper() ),
                       ( "((half-year))"         , getHalfyearName(stamp, False, False) ),
                       ( "((half-year:##))"      , getHalfyearName(stamp, False, True) ),
                       ( "((half-year:i))"       , getHalfyearName(stamp, True, False) ),
                       ( "((half-year:I))"       , getHalfyearName(stamp, True, False).upper() )]
        for old, new in replStrings:
            parseString = parseString.replace(old, new)
        return parseString


class WikiDocument:
    def __init__(self, page, archivingTarget):
        self.numberDiscussions   = 0                  # Number of Discussions on page
        self.originalText        = page.get()         # The original Text of the wikipage
        self.modifiedText        = self.originalText  # The text that should be saved back
        self.sliceOffset         = 0                  # When a slice gets extracted the offset changes
        self.listDiscussions     = []                 # A list containing the discussions
        self.reportText          = ""                 # Text to save into report file

        self.archivingAgeErledigt= 7.0                # Number of days, after a discussion will be archived with template {{section resolved}}
        self.archivingTarget     = archivingTarget    # Target String a discussion will be archived to
                                                      # Should be equal to [[Vorlage:Autoarchiv]] on de
        self.archivingUseTimeComparatorCleared = False# declares the timestamp that is used for the target, True: the one in the resolved template False: the oldest one
        self.archivingUseTimeout = 0                  # if this parameter x is bigger that 0, archiving will be triggered after x days
        self.headlineLevel       = 2                  # level of headline (no. of equal-signs)
        self.numArchived         = 0                  # Number of discussions that will be archived
        self.archiveContainer    = {}                 # Dict in which archive text will be stored in
        self.archiveContCounter  = {}                 # Number of archived discs per container

        self.name                = page.title()       # Own name of page
        self.minorEdit           = True               # Wheater to do minor Edits or not
        self.editTime            = page.editTime()    # last edit time
        self.userName            = page.userName()    # last editor

    def divideIntoSlices(self):
        # Divide the Original Text by Headlines ...
        #regex = "(?P<title>^=.*)[\s]+"
        regex = "(?P<title>^(?P<hls>[=]{1,%d})(?P<title_clear>[^=]{1}.*?)(?P=hls))([\s]{0,5})$" % self.headlineLevel
        p = re.compile(regex, re.I|re.M)
        # ... and iterate through it
        headlineIterator = p.finditer(self.originalText)
        
        counter = 0
        possibleDiscs = []
        for singleHeadline in headlineIterator:
            possibleDiscs.append(Discussion(self.name))
            possibleDiscs[counter].setTitleOffsetStart(singleHeadline.span()[0])
            possibleDiscs[counter].setContentOffsetStart(singleHeadline.span()[1])
            possibleDiscs[counter].setTitle(singleHeadline.group('title'), singleHeadline.group('title_clear'))
            headlineLevel = singleHeadline.group('hls').count("=")
            possibleDiscs[counter].setHeadlineLevel(headlineLevel)

            if counter > 0:
                possibleDiscs[counter - 1].setContentOffsetEnd(possibleDiscs[counter].getTitleOffsetStart())
                possibleDiscs[counter - 1].retrieveContent(self.originalText)
            counter = counter + 1
        if (len(possibleDiscs) != 0):
            possibleDiscs[counter - 1].setContentOffsetEnd(len(self.originalText))
            possibleDiscs[counter - 1].retrieveContent(self.originalText)

        for i in possibleDiscs:
            if i.getHeadlineLevel() == self.headlineLevel:

                self.listDiscussions.append(i)
                self.numberDiscussions = self.numberDiscussions + 1


    def examineDiscussions(self, bot):
        for singleDiscussion in self.listDiscussions:
            singleDiscussion.examine(bot)

    def generateErrorReport(self):
        logText = ("== [[%s]] ==\n" % self.name)
        logText += "Botlauf am " + strftime("%Y-%m-%d um %H:%M\n", localtime())
        logText += "Fehlende oder fehlerhafte Optionen!\n"
        pywikibot.output(logText)
        self.reportText = logText

    def generateReport(self, bot):
        """
        Should report the following:
          * Überschrift
          * Alter des letzen Beitrages
          * Anzahl Beiträge
          * Alter der Erledigt-Kennzeichnung
          * Ziel der Archivierung
          * Archivierung Ja/Nein
        """
        logText = ("== [[%s]] ==\n" % self.name)
        logText += "Bot run at " + strftime("%Y-%m-%d um %H:%M\n", localtime())
        logText = logText + "* Archiving starts after '''%03.1f days'''\n" % self.archivingAgeErledigt
        logText = logText + "* Target pattern: '''%s'''\n" % self.archivingTarget
        logText = logText + "* On headline level '''%d'''\n" % self.headlineLevel
        logText = logText + "* Number of sections: '''%d'''\n" % self.numberDiscussions
        logText = logText + "* Number of sections to archive: '''%d'''\n" % self.numArchived
        logText = logText + "{| class=\"wikitable\"\n|- class=\"hintergrundfarbe8\"\n! lfd. Nr. !! Headline !! Age of oldest signature !! Num. of signatures !! Age of 'resolved' !! Target"

        counter = 0              # lfd. Nr.
        headline = ""           # Überschrift
        agefirst = 0.0           # Age of first contribution
        numcontri = 0            # number of contributions
        agecleared = "-"        # age of cleared flag
        targettoarchiveto = ""  # where it would be archived to

        for discussion in self.listDiscussions:
            counter       = counter + 1
            headline      = discussion.getTitle(True)
            agefirst      = discussion.getAge()
            numcontri     = discussion.getContributions()
            targettoarchiveto = discussion.getArchivingTarget(self.archivingTarget, self.archivingUseTimeComparatorCleared, bot)

            if discussion.getClearedAge() == 0.0:
                agecleared = "-"
                headlineColor = ""
            else:
                agecleared = "%03.2f" % discussion.getClearedAge()
                if discussion.checkCleared(self.archivingAgeErledigt, self.archivingUseTimeout):
                    headlineColor = " style=\"background-color:#ffcbcb;\" "
                else:
                    headlineColor = " style=\"background-color:#b9ffc5;\" "

            logText = logText + "\n|-%s\n| %d || %s || %03.2f || %d || %s || [[%s|&rarr;]]" % (headlineColor, counter, headline, agefirst, numcontri, agecleared, targettoarchiveto)
            headline = ""           # Überschrift
            agefirst = 0.0           # Age of first contribution
            numcontri = 0            # number of contributions
            agecleared = "-"        # age of cleared flag
            targettoarchiveto = ""  # where it would be archived to

        logText = logText + "\n|}\n"
        pywikibot.output(logText)
        self.reportText = logText

    def saveReport(self, saveLogsLocale, localLogFile):
        if saveLogsLocale:
            pywikibot.output("Speichere Log lokal ... ")
            fd = open(localLogFile, 'a')
            writeMe = self.reportText + "\n" 
            writeMe = writeMe.encode('utf-8')
            fd.write(writeMe)
            fd.close()
            pywikibot.output("Done.\n")

    def prepareArchiving(self, bot):
        for discussion in self.listDiscussions:
            if discussion.checkCleared(self.archivingAgeErledigt, self.archivingUseTimeout):
                self.archiveSlice(discussion, bot)

    def substErledigt(self, originalText, bot):
        """
            Substitutes the templates
        """
        # subst erledigt
        old = re.compile("\{\{\ {0,5}" + bot.sectResolvedRegEx + "\ {0,5}\|(?:1=)?([^}]*?" + bot.timeStampRegEx + ")\ *?\|(?:2=.*?)?([^}]*?)\ *\}\}", re.UNICODE | re.S)
        originalText = textlib.replaceExcept(originalText, old, bot.sectResolved2P, ["comment", "nowiki"])
        
        old = re.compile("\{\{\ {0,5}" + bot.sectResolvedRegEx + "\ {0,5}\|(?:1=)?([^}]*?[^}|*]?" + bot.timeStampRegEx + ")\ *?\}\}", re.UNICODE | re.S)
#        print("\{\{\ {0,5}" + bot.sectResolvedRegEx + "\ {0,5}\|(?:1=)?([^}]*?[^}|*]?" + bot.timeStampRegEx + ")\ *?\}\}")
        return textlib.replaceExcept(originalText, old, bot.sectResolved1P, ["comment", "nowiki"])
    
    def executeArchiving(self, bot):
        # first, check if we can edit the origin page at all
        if bot.savePages:
            originPage = pywikibot.Page(bot.site, self.name)
            if not originPage.botMayEdit():
                pywikibot.output('Skipping %s because it is protected "edit:sysop"' % (self.name))
                return

        if len(self.archiveContainer) >= 1:
            # self.showDiffs()
            # Try to archive the slices
            doNotSave = False
            originEditComment = "" # Text for what bot did
            counter = 0
            for target, content in self.archiveContainer.items():
                pywikibot.showDiff("", content)
                print("---------------------------------------------------------------------")
                pywikibot.showDiff(content, self.substErledigt(content, bot))
                targetEditComment = ""
                if self.archiveContCounter[target] == 1:
                    targetEditComment = bot.archiveSumTargetS % (self.name)
                else:
                    if bot.currentProject == "jawikip": # FIXME this is crap
                       targetEditComment = bot.archiveSumTargetP % (self.name, self.archiveContCounter[target])
                    else:
                       targetEditComment = bot.archiveSumTargetP % (self.archiveContCounter[target], self.name)
                counter = counter + self.archiveContCounter[target]
                if originEditComment == "":
                    originEditComment = bot.archiveSumOriginMulti % (self.archiveContCounter[target], target)
                else:
                    originEditComment = originEditComment + ", " + bot.archiveSumOriginMulti % (self.archiveContCounter[target], target)
                if bot.savePages:
                    try:
                        pywikibot.output("opening [[%s]]" % target)
                        pageTo = pywikibot.Page(bot.site, target)
                        editTimeFirstTry = pageTo.editTime() if pageTo.exists() else 20301231235900
                        pageTo_origin = pageTo.get()
                        pageTo.put(self.substErledigt(pageTo_origin + "\n\n" + content, bot), targetEditComment, None, self.minorEdit, True)
                    except pywikibot.exceptions.NoPageError:
                        if bot.currentProject != 'meta' and pageTo.namespace() == 0:
                           pywikibot.output("Archivierung in den ANR!")
                           doNotSave = True 
                        else:
                           pageTo.put(self.substErledigt(bot.headTemplate + "\n\n" + content, bot), targetEditComment, None, self.minorEdit, True)
                           doNotSave = False
                    except pywikibot.exceptions.EditConflictError:
                        pywikibot.output("Bearbeitungskonflikt, Seite wird nicht gespeichert")
                        doNotSave = True
                    except pywikibot.exceptions.LockedPageError:
                        pywikibot.output("Seite evenutell blockiert!")
                        doNotSave = True
                    except pywikibot.exceptions.InvalidTitleError:
                        # don't care, some bug in the title
                        pywikibot.output("Page skipped because of pywikibot.exceptions.InvalidTitleError")
                        doNotSave = True
                    except:
                        # workaround for https://sourceforge.net/tracker/?func=detail&aid=3588463&group_id=93107&atid=603138
                        pywikibot.output("exception: %s" % sys.exc_info()[0])
                        pywikibot.output("check if [[%s]] was already saved" % target)
                        pageTo = pywikibot.Page(bot.site, target)
                        if (pageTo.exists() and pageTo.userName() == "SpBot" and (pageTo.editTime() - editTimeFirstTry).seconds < 60 * 2):
                            doNotSave = False # target was saved, go on
                        else:
                            raise

            # Try to save original page
            if counter == 1:
                partsText = bot.archiveSumOriginS
            else:
                partsText = bot.archiveSumOriginP % counter
            # add last contributor + time
            editTime = self.editTime + getUtcDiff(bot.currentProject)
            editTime = ("%s-%02d-%02d %02d:%02d" % (editTime.year, editTime.month, editTime.day, editTime.hour, editTime.minute))
            lastEditcomment = bot.archiveSumLastEdit % (self.userName, self.userName, editTime)
            originEditComment = bot.archiveSumArchive % (partsText, originEditComment) + lastEditcomment
            
            # diese Ersetzungen sind erst mal deaktiviert, weil sie zu haeufig Schaden anrichten
            if False and bot.currentProject == 'dewikip': 
                # http://de.pywikibot.org/w/index.php?oldid=55068954#Ersetzung_der_Vorlage:Keine_Auskunft
                self.modifiedText = textlib.replaceExcept(self.modifiedText, "\|\ *Kopfvorlage\ *=\ *(?:[Vv]orlage\ *\:\ *)?(?:[Aa]rchiv)?\ *[\n\r]*\|", "|", ["comment", "nowiki"])
                # http://de.pywikibot.org/w/index.php?title=Benutzer_Diskussion:Euku&curid=2487250&diff=61357082&oldid=61311496
                self.modifiedText = textlib.replaceExcept(self.modifiedText, "\{\{\ *(?:[Vv]orlage\ *\:\ *)?[Ll]AE\ *\}\}", "{{Löschantrag entfernt}}", ["comment", "nowiki"])
                rmParamRegEx = "(\{\{[Aa]utoarchiv\-[Ee]rledigt[\w\W]+?)\ *\|\ *%s\ *=\ *%s\ *[\n\r]*?([\w\W]*?\}\})"
                self.modifiedText = textlib.replaceExcept(self.modifiedText, rmParamRegEx % ("Mindestabschnitte", "\d+?"), "\\1\\2", ["comment", "nowiki"])
                self.modifiedText = textlib.replaceExcept(self.modifiedText, rmParamRegEx % ("Mindestbeitr.ge", "\d+?"), "\\1\\2", ["comment", "nowiki"])
                self.modifiedText = textlib.replaceExcept(self.modifiedText, rmParamRegEx % ("Frequenz","[a-zäöü\:]*"), "\\1\\2", ["comment", "nowiki"])
                self.modifiedText = textlib.replaceExcept(self.modifiedText, rmParamRegEx % ("Klein", "[JjAaNnEeIiNn]*"), "\\1\\2", ["comment", "nowiki"])
                self.modifiedText = textlib.replaceExcept(self.modifiedText, rmParamRegEx % ("Modus", "[Eerledigt]*"), "\\1\\2", ["comment", "nowiki"])
                self.modifiedText = textlib.replaceExcept(self.modifiedText, rmParamRegEx % ("Zeigen", "[JjAa]+"), "\\1\\2", ["comment", "nowiki"])
            
            if bot.savePages and not doNotSave:
                try:
                    pageTo = pywikibot.Page(bot.site, self.name)
                    pageTo_origin = pageTo.get()
                    pageTo.put(self.modifiedText, originEditComment, None, self.minorEdit)
                except pywikibot.exceptions.NoPageError:
                    pageTo.put(self.modifiedText, originEditComment, None, self.minorEdit)
                    pass
                except pywikibot.exceptions.EditConflictError:
                    pywikibot.output('Skipping %s because of edit conflict' % (self.name))


    def archiveSlice(self, disc, bot):
        SliceStart = disc.getTitleOffsetStart() - self.sliceOffset
        SliceStop  = disc.getContentOffsetEnd() - self.sliceOffset
        SliceText  = self.modifiedText[SliceStart:SliceStop]
        self.modifiedText  = self.modifiedText[:SliceStart] + self.modifiedText[SliceStop:]
        self.sliceOffset   = self.sliceOffset + len(SliceText)
        self.numArchived   = self.numArchived + 1

        target = disc.getArchivingTarget(self.archivingTarget, self.archivingUseTimeComparatorCleared, bot)

        if target in self.archiveContainer:
            self.archiveContainer[target] = self.archiveContainer[target] + SliceText
            self.archiveContCounter[target] = self.archiveContCounter[target] + 1
        else:
            self.archiveContainer[target]   = SliceText
            self.archiveContCounter[target] = 1
        
    def showDiffs(self):
        pywikibot.output("#"*80)
        pywikibot.output("Diff:")
        pywikibot.output("#"*80)
        pywikibot.showDiff(self.originalText, self.modifiedText)
        pywikibot.output("#"*80)
        pywikibot.output("#"*80)

    def findOptions(self, bot):
        """
        Looks for the template {{Autoarchiv-Erledigt}}
        """
        p = re.compile(bot.optionsRegEx, re.DOTALL)
        match = p.search(self.originalText)
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
                if bot.paramAge not in optionsDict:
                   raise NoOptions("'%s' is missing. " % bot.paramAge)
                if bot.paramArchive not in optionsDict:
                   raise NoOptions("'%s' is missing. " % bot.paramArchive)

                self.archivingAgeErledigt    = float(optionsDict[bot.paramAge])
                self.archivingTarget = optionsDict[bot.paramArchive].replace("'", "") # remove '
                if bot.paramLevel in optionsDict and optionsDict[bot.paramLevel] != '':
                    self.headlineLevel   = int(optionsDict[bot.paramLevel])
                else:
                    self.headlineLevel   = 2

                if bot.paramTimeComparator in optionsDict and optionsDict[bot.paramTimeComparator] != '':
                    self.archivingUseTimeComparatorCleared = (optionsDict[bot.paramTimeComparator] != None and optionsDict[bot.paramTimeComparator] == bot.paramTimeComparatorCleared)
                if bot.paramTimeout in optionsDict and optionsDict[bot.paramTimeout] != '':
                    self.archivingUseTimeout = float(optionsDict[bot.paramTimeout])
            except KeyError as ke:
                raise NoOptions()
            except ValueError:
                raise WrongOptions()

        else:
            raise NoOptions()
    
    def workToDo(self):
        """
        Whether there is something to archive or not
        """
        if self.numArchived > 0:
            return True
        else:
            return False

class ArchiveRobot:
    """
        A bot that can archive.
    """
    def __init__(self):
        """
            Initiate Object
        """
        self.savePages = True # Weather to save pages to wikipedia or not.... True means: yes, save it
        self.saveLogsLocale = False # Weather to save logs at all or not
        self.generator = None
        self.site = pywikibot.Site(code="de", fam="wikipedia")
        self.currentProject = "dewikip"

        # read arguments
        for arg in pywikibot.handle_args():
                if arg == '-donotsave':
                    self.savePages = False
                elif arg.startswith('-project'):
                    if len(arg) == 8:
                        self.currentProject = pywikibot.input('Welches Projekt soll es sein? [dewikip, dewiktionary, dewikiversity, enwikisource, dewikisource, commons, wikidata, wikimania, species]')
                    else:
                        self.currentProject = arg[9:]
                    # reload site
                    if self.currentProject == 'meta':
                        self.site = pywikibot.Site(code="meta", fam="meta")
                    elif self.currentProject == 'commons':
                        self.site = pywikibot.Site(code="commons", fam="commons")
                    elif self.currentProject == 'wikidata':
                        self.site = pywikibot.Site(code="wikidata", fam="wikidata")
                    elif self.currentProject == 'wikimania':
                        self.site = pywikibot.Site(code="wikimania", fam="wikimania")
                    elif self.currentProject == 'species':
                        self.site = pywikibot.Site(code="species", fam="species")
                    elif self.currentProject[2:] == 'wikip': # end with wikip
                        self.site = pywikibot.Site(code=self.currentProject[:2], fam="wikipedia")
                    elif self.currentProject[2:] == 'wikisource': # end with wikisource
                        self.site = pywikibot.Site(code=self.currentProject[:2], fam="wikisource")
                    elif self.currentProject == 'dewiktionary':
                        self.site = pywikibot.Site(code="de", fam="wiktionary")
                    elif self.currentProject == 'dewikiversity':
                        self.site = pywikibot.Site(code="de", fam="wikiversity")
                    else:
                        raise WrongOptions("Unknow wiki given")
                elif arg.startswith('-page'):
                    if len(arg) == 5:
                        self.generator = [pywikibot.Page(self.site, pywikibot.input('Welche Diskussionsseite soll archiviert werden?'))]
                    else:
                        self.generator = [pywikibot.Page(self.site, arg[6:])]
                elif arg == '-nolocallog':
                    self.saveLogsLocale = False
                else:
                    pywikibot.output(arg + " wurde ignoriert")
        
        if self.currentProject[:2] == "ja":
    	    self.timeStampRegEx = "(?P<yyyy>\d{4})年(?P<MM>\d{1,2})月(?P<dd>\d{1,2})日\ \(.\)\ (?P<hh>\d{2})\:(?P<mm>\d{2})\ \(UTC\)"
        elif self.currentProject[:2] == "ko":
            self.timeStampRegEx = "(?P<yyyy>\d{4})년\ (?P<MM>\d{1,2})월\ (?P<dd>\d{1,2})일\ \(.\)\ (?P<hh>\d{2})\:(?P<mm>\d{2})\ \(KST\)"
        elif self.currentProject[:2] == "cs":
            self.timeStampRegEx = "(?P<dd>[0-9]{1,2})\.\ (?P<MM>\d{1,2})\.\ (?P<yyyy>[0-9]{4}),\ (?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2})\ \((?:CE[S]?T)\)"
        else:
            self.timeStampRegEx = "(?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2}),\ (?P<dd>[0-9]{1,2})\.?\ (?P<MM>[a-zA-Zä]{3,10})\.?\ (?P<yyyy>[0-9]{4})\ \((?:CE[S]?T|ME[S]?Z|UTC)\)"
	    
        # localization
        self.localLogFile = os.getcwd() + strftime("/logs/archiv-" + self.currentProject + "-%Y-%m-%d.log",localtime())
        if self.currentProject in ["dewikip", "dewiktionary", "dewikisource", "dewikiversity"]:
                self.archiveTemplateName = "Vorlage:Autoarchiv-Erledigt"
                self.headTemplate   = "{{Archiv}}"      # Headtemplate to insert into new archivpages
                self.excludeList = (
                       "Vorlage:Erledigt",
                       "Benutzer:SpBot",
                       "Portal:Philosophie/Qualitätssicherung",
                       "Wikipedia Diskussion:Hauptseite/Artikel des Tages/Chronologie der Artikel des Tages"
                       )
                self.errorCategory = "Kategorie:{{ns:Project}}:Fehlerhafte Autoarchiv-Parameter/SpBot"
                self.errorText = "== Archivierung konnte nicht durchgeführt werden ==\n"
                self.errorText += "Beim Botlauf um ~~~~~ wurden fehlerhafte Optionen in der Vorlage 'Autoarchiv-Erledigt' festgestellt. %s"
                self.errorText += "Beachte bitte die [[" + self.archiveTemplateName + "|Dokumentation der Vorlage]] und korrigiere den Fehler. Bei Unklarheiten kannst du [[:Benutzer:Euku|Euku]] fragen. Gruß --~~~~"
                self.errorText += "\n\n[[" + self.errorCategory + "]]<!-- entferne diese Zeile, wenn das Problem behoben wurde -->"
                self.errorTextSummary = "Berichte Fehler"
                # template parameters
                self.optionsRegEx = "\{\{\ *(?:[Vv]orlage\:|[Tt]emplate\:)?\ *[Aa]utoarchiv-[Ee]rledigt(?P<options>.*?)\}\}"
                self.templDoNotArchive = r'\{\{\ *[Nn]icht\ *archivieren[\|\}]'
                self.paramAge = 'ALTER'
                self.paramArchive = 'ZIEL'
                self.paramLevel = 'EBENE'
                self.paramTimeComparator = 'ZEITVERGLEICH'
                self.paramTimeComparatorCleared = 'erledigt'
                self.paramTimeout = 'ZEITBESCHRÄNKUNG'
                # edit summaries
                self.archiveSumTargetS = "Archiviere 1 Abschnitt von [[%s]]"
                self.archiveSumTargetP = "Archiviere %d Abschnitte von [[%s]]"
                self.archiveSumOriginS = "1 Abschnitt"
                self.archiveSumOriginP = "%d Abschnitte"
                self.archiveSumOriginMulti  = "%d nach [[%s]]"
                self.archiveSumLastEdit= " - letzte Bearbeitung: [[:User:%s|%s]], %s"
                self.archiveSumArchive = "Archiviere %s: %s"
                self.sectResolvedRegEx = "[Ee]rledigt"
                self.sectResolved1P    = ":<small>Archivierung dieses Abschnittes wurde gewünscht von: \\1</small>"
                self.sectResolved2P    = ":<small>Archivierung dieses Abschnittes wurde gewünscht von \\1, \\7</small>"

        elif self.currentProject == 'cswikip':
                self.archiveTemplateName = "Šablona:Archivace vyřešených sekcí"
                self.headTemplate   = "{{Archiv diskuse}}"
                self.excludeList = ( self.archiveTemplateName )
                self.errorCategory = "Category:{{ns:Project}}:Incorrect Autoarchive parameter/SpBot"
                self.errorText = "== Archivaci nelze dokončit ==\n"
                self.errorText += "Běh bota ~~~~~ nebyl úspěšný, protože šablona" + self.archiveTemplateName + " obsahuje nesprávné parametry. %s"
                self.errorText += "Podívejte se, prosím, na [[" + self.archiveTemplateName + "|dokumentaci]] a opravte chybu. Zdraví --~~~~"
                self.errorText += "\n\n[[" + self.errorCategory + "]]<!-- odstraňte tento řádek, pokud je problém vyřešen -->"
                self.errorTextSummary = "Archivaci nelze dokončit"
                # template parameters
                self.optionsRegEx = "\{\{\ *(?:[Šš]ablona|[Tt]emplate\:)?\ *[Aa]rchivace\ vyřešených\ sekcí(?P<options>.*?)\}\}"
                self.templDoNotArchive = '\{\{\ *[Nn]icht\ *archivieren[|}]' # not used
                self.paramAge = 'AGE'
                self.paramArchive = 'ARCHIVE'
                self.paramLevel = 'LEVEL'
                self.paramTimeComparator = 'TIMECOMAPARE'
                self.paramTimeComparatorCleared = 'resolved'
                self.paramTimeout = 'TIMEOUT'
                # edit summaries
                self.archiveSumTargetS = "archivuji 1 vlákno z [[%s]]"
                self.archiveSumTargetP = "archivuji %d vláken z [[%s]]"
                self.archiveSumOriginS = "1 vlákno"
                self.archiveSumOriginP = "%d vláken"
                self.archiveSumOriginMulti = "%d do [[%s]]"
                self.archiveSumLastEdit= " - předchozí editace: [[User:%s|%s]], %s"
                self.archiveSumArchive = "archivuji %s: %s"
                self.sectResolvedRegEx = "[Ss]ekce[_ ]vyřešena"
                self.sectResolved1P = ":<small>Tato sekce byla archivována na žádost uživatele: \\1</small>"
                self.sectResolved2P = ":<small>Tato sekce byla archivována na žádost uživatele: \\1 \\7</small>"
                
        elif self.currentProject == 'jawikip':
                self.archiveTemplateName = "Template:Autoarchive resolved section"
                self.headTemplate   = "{{Talkarchive}}"
                self.excludeList = ( self.archiveTemplateName )
                self.errorCategory = "Category:Autoarchive に誤った引数が渡されているページ/SpBot"
                self.errorText = "== 過去ログ化が正常終了しませんでした ==\n"
                self.errorText += "~~~~~ のボット作業は失敗しました。原因はテンプレート " + self.archiveTemplateName + " に誤った引数が渡されていたためです： %s"
                self.errorText += "[[" + self.archiveTemplateName + "|ドキュメント]]を確認して間違いを訂正してください。よろしくお願いします。 --~~~~"
                self.errorText += "\n\n[[" + self.errorCategory + "]]<!-- 問題が解決したらこの行は除去してください -->"
                self.errorTextSummary = "エラーを報告"
                # template parameters
                self.optionsRegEx = "\{\{\ *(?:[Tt]emplate\:)?\ *[Aa]utoarchive\ resolved\ section(?P<options>.*?)\}\}"
                self.templDoNotArchive = '\{\{\ *[Nn]icht\ *archivieren[|}]'
                self.paramAge = 'AGE'
                self.paramArchive = 'ARCHIVE'
                self.paramLevel = 'LEVEL'
                self.paramTimeComparator = 'TIMECOMAPARE'
                self.paramTimeComparatorCleared = 'resolved'
                self.paramTimeout = 'TIMEOUT'
                # edit summaries
                self.archiveSumTargetS = "[[%s]] から節 1 個を過去ログ化"
                self.archiveSumTargetP = "[[%s]] から節 %d 件を過去ログ化"
                self.archiveSumOriginS = "節 1 件"
                self.archiveSumOriginP = "節 %d 件"
                self.archiveSumOriginMulti = "%d件を%sに過去ログ化"
                self.archiveSumLastEdit= " - 前の編集: [[:User:%s|%s]], %s"
                self.archiveSumArchive = "%s を過去ログ化: %s"
                self.sectResolvedRegEx = "(?:[Ss]ection[\ _]resolved|[Rr]esolved[\ _]section)"
                self.sectResolved1P    = ":<small>この節は次の利用者の依頼で過去ログ化されました： \\1</small>"
                self.sectResolved2P    = ":<small>この節は次の利用者の依頼で過去ログ化されました： \\1 \\7</small>"

        elif self.currentProject == 'kowikip':
                self.archiveTemplateName = "틀:완료된 토론 자동 보존"
                self.headTemplate = "{{보존}}"
                self.excludeList = ( self.archiveTemplateName )
                self.errorCategory = "분류:잘못된 자동 보존 설정이 있는 문서"
                self.errorText = "== 보존을 처리하지 못했습니다 ==\n"
                self.errorText += "봇이 ~~~~~ 에 토론을 보존하려 했으나, 성공적이지 못했습니다. 틀  " + self.archiveTemplateName + " 이 부정확한 변수를 포함했기 때문입니다. %s"
                self.errorText += "[[" + self.archiveTemplateName + "|설명 문서]] 를 보고 문제를 고쳐 주세요. 감사합니다. --~~~~"
                self.errorText += "\n\n[[" + self.errorCategory + "]]<!--문제가 해결되었다면 이 줄을 지우세요. -->"
                self.errorTextSummary = "문제 보고"
                # template parameters / 틀 변수
                self.optionsRegEx = "\{\{\ *(?:틀\:)?\ *완료된\ 토론\ 자동\ 보존(?P<options>.*?)\}\}"
                self.templDoNotArchive = '\{\{\ *보존i\ 중단\}\}'
                self.paramAge = '날짜'
                self.paramArchive = '보존'
                self.paramLevel = '단위'
                self.paramTimeComparator = '시간 비교'
                self.paramTimeComparatorCleared = '완료된 토론'
                self.paramTimeout = '타임아웃'
                #edit summaries/편집 요약
                self.archiveSumTargetS="1개의 문단을 [[%s]] 에서 가져옴"
                self.archiveSumTargetP="%d개의 문단을 [[%s]] 에서 가져옴"
                self.archiveSumOriginS="1개의 문단"
                self.archiveSumOriginP="%d개의 문단"
                self.archiveSumOriginMulti="%d 을(를) [[%s]]"
                self.archiveSumLastEdit="-이전 편집: [[:User:%s|%s]],%s"
                self.archiveSumArchive="보존 %s:%s"
                self.sectResolvedRegEx="(?:완료된\ 토론)"
                self.sectResolved1P=":<small>이 문단은 다음 사용자의 요청에 의해 보존되었습니다: \\1</small>"
                self.sectResolved2P=":<small>이 문단은 다음 사용자의 요청에 의해 보존되었습니다: \\1 \\7</small>"

        elif self.currentProject in ['commons', 'wikidata', 'species', 'meta', 'enwikisource', 'wikimania']:
            self.archiveTemplateName = "Template:Autoarchive resolved section"
            if self.currentProject == 'meta':
                self.headTemplate   = "{{Archive header}}"
            else:
                self.headTemplate   = "{{Talkarchive}}"
            
            self.excludeList = ( self.archiveTemplateName, 'Template:Autoarchive resolved section/doc' )
            self.errorCategory = "Category:{{ns:Project}}:Incorrect Autoarchive parameter/SpBot"
            self.errorText = "== Archiving could not be finished ==\n"
            self.errorText += "The bot-run at ~~~~~ was not successful, because the template " + self.archiveTemplateName + " contains incorrect parameters. %s"
            self.errorText += "Please have a look at the [[" + self.archiveTemplateName + "|documentation]] and fix the mistake. Regards --~~~~"
            self.errorText += "\n\n[[" + self.errorCategory + "]]<!-- remove this line, if the problem was resolved -->"
            self.errorTextSummary = "reporting an error"
            # template parameters
            self.optionsRegEx = "\{\{\ *(?:[Tt]emplate\:)?\ *[Aa]utoarchive\ resolved\ section(?P<options>.*?)\}\}"
            self.templDoNotArchive = '\{\{\ *[Nn]icht\ *archivieren[|}]' # not used
            self.paramAge = 'AGE'
            self.paramArchive = 'ARCHIVE'
            self.paramLevel = 'LEVEL'
            self.paramTimeComparator = 'TIMECOMAPARE'
            self.paramTimeComparatorCleared = 'resolved'
            self.paramTimeout = 'TIMEOUT'
            # edit summaries
            self.archiveSumTargetS = "archiving 1 section from [[%s]]"
            self.archiveSumTargetP = "archiving %d sections from [[%s]]"
            self.archiveSumOriginS = "1 section"
            self.archiveSumOriginP = "%d sections"
            self.archiveSumOriginMulti  = "%d to [[%s]]"
            self.archiveSumLastEdit= " - previous edit: [[:User:%s|%s]], %s"
            self.archiveSumArchive = "archive %s: %s"
            self.sectResolvedRegEx = "(?:[Ss]ection[\ _]resolved|[Rr]esolved[\ _]section)"
            self.sectResolved1P    = ":<small>This section was archived on a request by: \\1</small>"
            self.sectResolved2P    = ":<small>This section was archived on a request by \\1 \\7</small>"
        else:
            output("ungueltiger Parameter self.currentProject")
            exit() 
        
        if self.generator == None:
            startPage = pywikibot.Page(self.site, self.archiveTemplateName)
            self.generator = startPage.getReferences(False, True, True, False)

    def run(self):
        """
             Begin archiving
        """
        self.generator = pagegenerators.PreloadingGenerator(self.generator, groupsize = 1)
        for page in self.generator:
            try:
                try:
                    if page.title() in self.excludeList:
                       pywikibot.output("Skipping page: " + page.title())
                       continue
                    pywikibot.output("Check page: " + page.title())
                    wdoc = 0
                    wdoc = WikiDocument(page, self)
                    wdoc.findOptions(self)
                    wdoc.divideIntoSlices()
                    wdoc.examineDiscussions(self)
                    wdoc.prepareArchiving(self)
                    wdoc.generateReport(self)
                    wdoc.showDiffs()
                    wdoc.saveReport(self.saveLogsLocale, self.localLogFile)
                    if wdoc.workToDo():
                        wdoc.executeArchiving(self)
                except NoOptions as no:
                    # Write error report to the same page
                    if self.savePages:
                        pywikibot.output("\t\03{lightpurple}Berichte Fehler auf %s\03{default}\n" % page.title())
                        if no.getMsg() != None:
                            hintMsg = no.getMsg()
                        else:
                            hintMsg = "";
                            pywikibot.output("Grund war: " + hintMsg)
                            page = pywikibot.Page(self.site, page.title())
                            if (page.get().find(self.errorCategory) == -1):
                                # paste only, if there is no such message
                                page.put(page.get() + "\n\n" + (self.errorText % hintMsg), self.errorTextSummary, watchArticle=None, minorEdit=False, force=False)
                        wdoc.generateErrorReport()
                        wdoc.saveReport(self.saveLogsLocale, self.localLogFile)
                    continue
                except:
                    import traceback
                    pywikibot.output("\n\03{lightpurple}Fehler bei %s\03{default} überspringe Seite\n" % page.title())
                    pywikibot.output("Unexpected error: " + str(traceback.format_exc()))
                    wdoc.generateErrorReport()
                    wdoc.saveReport(self.saveLogsLocale, self.localLogFile)
                    continue
            except:
                # Catch everything and don't let the bot stop.
                # This can happen when an exception was raised inside the exception handling.
                pywikibot.output("\n\03{lightpurple}Fehlerreport konnte nicht gespeichert werden.\03{default}\n")
                pywikibot.output("Unexpected error: " + str(sys.exc_info()))
                continue
        
        # Everything is done, so stop it
        pywikibot.output("Alles getan.")

if __name__ == "__main__":
    try:
        bot = ArchiveRobot()
        bot.run()
    finally:
        pywikibot.stopme()

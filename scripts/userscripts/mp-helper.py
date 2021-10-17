#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	Wikipedia-pybot-framework is needed!
	
	These command line parameters can be used to specify how to work:

-force		Force to update the lists on Wikipedia

"""
import sys              # To not have wikipedia and this in one dir we'll import sys
import re               # Used for regular expressions
import os               # used for os.getcwd()
import pywikibot        # pywikibot framework
from pywikibot import config2, pagegenerators, Bot, textlib
import locale			# German

from time import localtime, strftime, mktime    # strftime-Function and related
import time
import datetime

sys.path.append('/data/project/mp/mp/pyapi') # TODO make this a relative path
import dewpmp
import mp_db_config

menteeTemplRegEx = "\|\ *Mentor\ *=\ *([^\r\n|}]+)"
mentorTemplRegEx = "\{\{[Bb]enutzer(?:in)?\ *\:\ *([^\r\n|}]+?)\/(?:Vorlage[ _\/])?Mentor\ *(?:\|.*?)?\}\}"

wpOptInList = "Wikipedia:Mentorenprogramm/Projektorganisation/Opt-in-Liste"
wpOptInListRegEx = "\[\[(?:[uU]ser|[bB]enutzer)(?:in)?\:(?P<username>[^\|\]]+)(?:\|[^\]]+)?\]\]"
mentorenProgrammMeldungen = "Benutzer_Diskussion:Euk" # "Wikipedia Diskussion:Mentorenprogramm"
mentorenProgrammMenteeliste = "Wikipedia:Mentorenprogramm/Projektorganisation/In Betreuung"
anzahlAllerBereutenMentees = "Wikipedia:Mentorenprogramm/Projektorganisation/Anzahl bisheriger Mentees"
anzahlAllerZurzeitBereuendenMentoren = "Wikipedia:Mentorenprogramm/Projektorganisation/Anzahl betreuender Mentoren"
mentorenProgrammMenteeArchiv = "Wikipedia:Mentorenprogramm/Projektorganisation/Archiv "
menteeStatusRotGrenze = 60 # Tage
menteeStatusOrangeGrenze = 365 # Tage

localLogFile = os.getcwd() + strftime("/logs/mp-help-bot-%Y-%m-%d.log",localtime())
forceWrite = False
from xml.parsers import expat

normalizedWpNameCache = dict()

class Parser:
    def __init__(self):
        self.data = []
        self.item = []
        self.depth = 1
        self.currTag = ''
        self._parser = expat.ParserCreate()
        self._parser.StartElementHandler = self.start
        self._parser.EndElementHandler = self.end
        self._parser.CharacterDataHandler = self.addData

    def feed(self, xmldata):
        self._parser.Parse(xmldata, 0)

    def start(self, tag, attrs):
        self.currTag = tag
        if (self.depth == 2):
            self.item = [] # renew
        self.depth += 1

    def end(self, tag):
        self.currTag = ''
        if (self.depth == 3):
            self.data.append(self.item)
        elif (self.depth == 1):
            self._parser.Parse("", 1) # end of data
            del self._parser # get rid of circular references
        self.depth -= 1

    def addData(self, data):
        if (self.depth == 4):
           if (self.currTag == 'name' and len(self.item) == 1):
               # work around
               self.item[0] = self.item[0] + data
           else:
               self.item.append(data)

    def getData(self):
        return self.data

##### general support methods
# mergesort for mentees (menteeName, menteeID, mentorID, menteeStatus, menteeEintrittDatumStr, menteeAustrittDatumStr = mentee)
def mergesort(seq):
    if len(seq) <= 1:
        return seq
    else:
        linkeListe = seq[:int(len(seq)/2)]
        rechteListe = seq[int(len(seq)/2):]
        return merge(mergesort(linkeListe), mergesort(rechteListe))

def merge(linkeListe, rechteListe):
    comperator1 = 'mm_stop' # sort the mentees by 'mm_stop' (Austrittsdatum)
    comperator2 = 'mentor_user_id' # sort the mentees by 'mentor_user_id' (UserId)
    newList = []
    while linkeListe != [] and rechteListe != []:
        if linkeListe[0][comperator1] == rechteListe[0][comperator1]:
            if linkeListe[0][comperator2] <= rechteListe[0][comperator2]:
                newList.append(linkeListe[0])
                del linkeListe[0]
            else:
                newList.append(rechteListe[0])
                del rechteListe[0]
        elif linkeListe[0][comperator1] <= rechteListe[0][comperator1]:
            newList.append(linkeListe[0])
            del linkeListe[0]
        else:
            newList.append(rechteListe[0])
            del rechteListe[0]

    while linkeListe != []:
        newList.append(linkeListe[0])
        del linkeListe[0]

    while rechteListe != []:
        newList.append(rechteListe[0])
        del rechteListe[0]

    return newList

def dateToList(date):
	return int(date[:4]), int(date[5:7]), int(date[8:10])

def isIn(text, regex):
	return re.search(regex, text, re.UNICODE)
	
def search(text, regex):
	m = re.search(regex, text, re.UNICODE)
	if m:
	  return m.groups()[0]
	else:
	  return ""
	
def output(text):
	#fd = open(localLogFile, 'a')
	#writeMe = text + "\n"
	#writeMe = writeMe.encode('utf-8')
	#fd.write(writeMe)
	#fd.close()
	pywikibot.output(text)

def menteeIstAktiv(db, user_id):
	return db.get_mw_user_contribsum(user_id=user_id, latest_days=menteeStatusRotGrenze) > 0


def checkForNewMentees(db, mentorenFromServer, menteesFromServer, userListWP):
	"""
	prüfe welche Benutzer in die DB neu eingetragen werden müssen
	"""
	logText = ""
	
	somethingChanged = False
	for userWP in userListWP:
		menteeNameWP = normalizeWpName(userWP['item'])
		for userServ in menteesFromServer: # from our database
			menteeNamedServ = normalizeWpName(userServ['mentee_user_name'])
			if menteeNamedServ == menteeNameWP:
				break # bereits eingetragen
		else:
			output("\nin DB nicht gefunden: " + menteeNameWP)
			
			# finde Mentor auf seiner Benutzerseite
			userPage = pywikibot.Page(pywikibot.Site(), "Benutzer:" + menteeNameWP)
			rawText = userPage.get()
			mentorName = search(rawText, menteeTemplRegEx)
			if (mentorName == ""):
				# versuche was anderes
				# finde Mentorenvorlage auf seiner Benutzerseite
				mentorName = search(rawText, mentorTemplRegEx)
			
			mentorName = normalizeWpName(mentorName)
			output("Mentor durch Mentorenvorlage gefunden: " + mentorName)

			## alles gefunden, trage neuen mentee ein oder reaktiviere ihn
			output("übertrage in DB: Mentor: " + mentorName + ", Mentee: " + menteeNameWP)
			db.add_mentee(mentorName, menteeNameWP)
			somethingChanged = True
			logText += "+[[:User:%s|%s]] ([[:User:%s|%s]]) " % (menteeNameWP, menteeNameWP, mentorName, mentorName)
	return (somethingChanged, logText)

def normalizeWpName(name):
	"""
		remove _ and small lower case chars as first letter
	"""
	name = str(name)
	if (name in normalizedWpNameCache):
		return normalizedWpNameCache[name]
	newName = name.replace("_", " ") # "_" is the same as " " for Wikipedia URls
	if (newName != ""):
		newName = newName[0].upper() + newName[1:] # first letter musst be Big
	newName = newName.strip() # trim
	normalizedWpNameCache[name] = newName
	return newName

def checkForMenteesToBeArchived(mentorenFromServer, menteesFromServer, userListWP):
	"""
	archiviere Benutzer, die nicht mehr in der Kat auftauchen
	"""
	logText = ""
	somethingChanged = False
	for userServ in menteesFromServer:
		menteeNamedServ = normalizeWpName(userServ['mentee_user_name'])
		for userWP in userListWP:
			menteeNameWP = normalizeWpName(userWP['item'])
			if (menteeNameWP == menteeNamedServ):
				break
		else:
			allMentors = db.get_all_mentors_for_mentee(menteeNamedServ)
			lastMentorName = allMentors[len(allMentors) -1]['mentor_user_name']
			output("\nmuss archiviert werden: " + menteeNamedServ + "\tMentor war " + lastMentorName)
			db.stop_all_current_mentoring(userServ['mentee_user_id'])
			somethingChanged = True
			logText += "-[[:User:%s|%s]] ([[:User:%s|%s]]) " % (menteeNamedServ, menteeNamedServ, lastMentorName, lastMentorName)
	return (somethingChanged, logText)

#############################################
#   Benutzerliste in die WP zurückschreiben
#############################################
def writeMenteeArchive(db, mentorenFromServer):
	# ist das True, werden sämtliche Archive neugeschrieben, sehr langsam aber einfach umzusetzen
	writeAllArchives = True

	# %% must be written for %
	monthTemplHead = "<noinclude><!--\n\
######################################################################################\n\
# ACHTUNG: Diese Liste wird von einem Bot aktualisiert.\n\
# Manuelle Änderungen werden überschrieben.\n\
######################################################################################\n\
-->\n\
{{Benutzer:SpBot/Nicht bearbeiten}}</noinclude>\n\
<div class=\"NavFrame\" style=\"margin:2px;margin-top:5px;margin-right:5px;border:1px solid #1A442B;padding:0 1em 1em 1em;background-color:#f8f8ff;align:right;font-size:95%%\">\n\
<div class=\"NavHead\" align=\"left\">\n\
<h5>%s %s: (<span style='color:red'>%s</span>)</h5></div>\n<div class=\"NavContent\" align=\"left\">\n\
'''Eintritt in das MP / Ausscheiden aus dem MP:'''<br />\n\
<ol start=\"%s\">\n"
	monthTemplBody = "<li>%02d.%02d.%s / %02d.%02d.%s: %s [[Spezial:Beiträge/%s|%s]] ([[Benutzer:%s|%s]])</li>\n"
	monthTemplFoot = "</ol></div></div>"
	monthDic = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]

	menteesForArchive = []
	menteesFromServer = db.get_all_mentees(mentor_user_name=None, only_active=False)
	# filter mentees
	for mentee in menteesFromServer:
		if (mentee['mm_stop'] != None):
			menteesForArchive.append(mentee)
	# sort them
	menteesForArchive = mergesort(menteesForArchive)
	heuteJahr, heuteMon, heuteTag = localtime()[0], localtime()[1], localtime()[2]

	# if all months must be written, just loop through them all
	firstMonth = 5
	firstYear = 2007
	if not writeAllArchives:
		firstMonth = heuteMon
		firstYear = heuteJahr
	
	for currYear in range(firstYear, heuteJahr+1):
		output("Prüfe Archiv für %s" % currYear)
		for currMon in range(1, 13):
			if (currYear == firstYear and currMon < firstMonth) or (currYear == heuteJahr and currMon > heuteMon):
				# current month is not in our range
				continue
			resultMiddleStr = ""
			archiveMenteeStartValueThisMonth = archiveMenteeTotalCounter = archiveMenteeThisMonthCounter = 0
			for mentee in menteesForArchive:
				menteeName = mentee['mentee_user_name']
				inDate = mentee['mm_start']
				outDate = mentee['mm_stop']
				archiveMenteeTotalCounter += 1
				# look for the current month only
				if (currYear == outDate.year and currMon == outDate.month):
					archiveMenteeThisMonthCounter += 1
					if (archiveMenteeStartValueThisMonth == 0):
						archiveMenteeStartValueThisMonth = archiveMenteeTotalCounter
		
					mentorName = mentee['mentor_user_name']
					if (mentee['mentee_type']==2):
						menteeTyp = "[W]"
					elif (mentee['mentee_type']==1):
						menteeTyp = "[N]"
					else:
						menteeTyp = ""
					resultMiddleStr += monthTemplBody % (inDate.day, inDate.month, inDate.year, outDate.day, outDate.month, outDate.year, menteeTyp, menteeName, menteeName, mentorName, mentorName)
			
			resultHeadStr = monthTemplHead % (monthDic[currMon-1], currYear, archiveMenteeThisMonthCounter, archiveMenteeStartValueThisMonth) # for current month only
			
			## write it to wikipedia
			page = pywikibot.Page(pywikibot.Site(), mentorenProgrammMenteeArchiv + str(currYear) + " " + monthDic[currMon-1])
			try:
				rawText = page.get()
				pywikibot.showDiff(rawText, resultHeadStr + resultMiddleStr + monthTemplFoot)
				
				if resultHeadStr + resultMiddleStr + monthTemplFoot != rawText:
					page.put(resultHeadStr + resultMiddleStr + monthTemplFoot, "Update", False, minor=True, force=True)
				else:
					output("keine Änderung im WP-Archiv nötig: " + str(currYear) + " " + monthDic[currMon-1])
			except pywikibot.NoPage:
				# create a new page
				page.put(resultHeadStr + resultMiddleStr + monthTemplFoot, "neues Archiv", False, minor=True, force=True)
	

##################################################
# aktive Benutzerliste in die WP zurückschreiben
##################################################
def writeActiveMenteeList(db, logText, menteesFromServer, mentorenFromServer):
	result = "{| class=\"wikitable sortable\"\n\
|- class=\"hintergrundfarbe5\"\n\
!Eintritt||Mentee||Mentor||Status||Typ"
	counterRed = 0
	counterOrange = 0
	for mentee in menteesFromServer:
		if (mentee['mm_stop'] != None):
			continue # im archiv, weiter
		
		menteeStatus = "grün"
		
		diffAge = (datetime.datetime.now() - mentee['mm_start']).days
		if (diffAge < 0):
			output("Alter von %s ist negativ" % mentee['mentee_user_name'])
			exit()
		if (diffAge >= menteeStatusOrangeGrenze): # ab 5*356/2 Tagen wirds orange
			menteeStatus = "orange"
		
		if (diffAge >= menteeStatusRotGrenze-1):	# WP nicht befragen, wenn Mentee noch gar nicht 'rot' werden kann, um Ressoucen zu sparen
			if (not menteeIstAktiv(db, mentee['mentee_user_id'])):	# wenn Mentee seit 60 Tagen inaktiv ist
				menteeStatus = "rot"

		if (mentee['mentee_type']==2):
			menteeTyp = "Wunschmentor"
		elif (mentee['mentee_type']==1):
			menteeTyp = "Zufall"
		else:
			menteeTyp = "nicht gesetzt"

		if (menteeStatus == "orange"):
			counterOrange += 1
		elif (menteeStatus == "rot"):
			counterRed += 1

		result += "\n|-\n{{MP-NB|Eintritt=%s-%s-%s|Mentee=%s|Mentor=%s|Status=%s|Typ=%s}}" % (mentee['mm_start'].year, mentee['mm_start'].month, mentee['mm_start'].day, mentee['mentee_user_name'], mentee['mentor_user_name'], menteeStatus, menteeTyp)

	result += "\n|}"
	countAll = len(menteesFromServer)
	result = ("{{Benutzer:Euku/SpBot-Status}}\nDerzeit sind '''%s''' Mentees in Betreuung. Davon haben %s (%s%%) den Status rot (letzter Edit > 60 Tage) und %s (%s%%) den Status orange (Betreuung > fünf Monate).\n"
		% (countAll, counterRed, round(100*counterRed/countAll), counterOrange, round(100*counterOrange/countAll))) + result
	
	## write it to wikipedia
	page = pywikibot.Page(pywikibot.Site(), mentorenProgrammMenteeliste)
	rawText = page.get()
	pywikibot.showDiff(rawText, result)
	if result != rawText:
		output("Logtext: " + logText)
		page.put(result, "Update " + logText, False, minor=True, force=True, botflag=True)
	#	output(result)
	else:
		output("keine Änderung in aktiver Menteeliste (WP)")


##################################################
# hat dieser Mentor "gelbe" oder "rote" Mentees?
##################################################
def writeInactiveMenteeListForMentor(menteesFromServer, mentorenFromServer, currMentorStr):
	output("Pruefe auf inaktive und alte Mentees")
	result = "\n==Erinnerung zur Betreuung am {{subst:CURRENTDAY}}. {{subst:LOCALMONTHABBREV}} {{subst:CURRENTYEAR}}==\nHallo %s! Du wirst benachrichtigt, weil du in [[%s|dieser Liste]] stehst. Bitte überprüfe, ob die Betreuung folgender Mentees noch erforderlich ist." % (currMentorStr, wpOptInList)
	menteeCounter = 0
	currMentorID = -1
	sumText = 'Erinnerung an: %s Mentee(s)'
	page = pywikibot.Page(pywikibot.Site(), "Benutzer_Diskussion:"+currMentorStr)
	rawText = ''

	for currMentor in mentorenFromServer:
		if (currMentor[0] == mentorStr):
			# Mentor gefunden
			currMentorID = currMentor[1]
			break
	if (currMentorID == -1):
		output("Mentor string nicht gefunden: %s" % mentorStr)
		currMentorID = 123
		## exit() DEBUG

	for mentee in menteesFromServer:
		if (len(mentee) == 4):
			menteeName, menteeID, menteeEintrittDatumStr, mentorID = mentee
			menteeAustrittDatumStr = ''
		elif (len(mentee) == 5):
			menteeName, menteeID, menteeEintrittDatumStr, menteeAustrittDatumStr, mentorID = mentee
		else:
			output(mentee + " konnte nicht entpackt werden")
			exit()

		if (currMentorID != mentorID or menteeAustrittDatumStr != ''):
			continue # falscher Mentor oder im Archiv, weiter
		menteeStatus = "grün"
		
		menteeEintrittJahr, menteeEintrittMon, menteeEintrittTag = dateToList(menteeEintrittDatumStr)
		diffAge = (date.today() - date(menteeEintrittJahr, menteeEintrittMon, menteeEintrittTag)).days
		if (diffAge < 0):
			output("Alter von MentorID %s ist negativ" % menteeID)
			exit()
		if (diffAge >= menteeStatusOrangeGrenze): # ab 5*356/2 Tagen wirds orange
			menteeStatus = "orange"
			menteeCounter += 1
		
		if (diffAge >= menteeStatusRotGrenze-1):	# WP nicht befragen, wenn Mentee noch gar nicht 'rot' werden kann, um Ressoucen zu sparen
			if (not menteeIstAktiv(menteeName)):	# wenn Mentee seit 60 Tagen inaktiv ist
				menteeStatus = "rot"
				menteeCounter += 1
		## create the messages if needed
		menteeEintrittJahr, menteeEintrittMon, menteeEintrittTag = dateToList(menteeEintrittDatumStr)
		if (menteeStatus == 'orange'):
			if (rawText == ''):
				rawText = page.get()
			if (not isIn(rawText, "\[\[Benutzer\:%s\|%s\]\]\:\ Eintritt\: 2" % (eukuhelp.UMLdecode(menteeName), eukuhelp.UMLdecode(menteeName)))):
				result += "\n*[[Benutzer:%s|]]: Eintritt: %s-%s-%s, wird seit mindestens %s Tagen betreut" % (eukuhelp.UMLdecode(menteeName), menteeEintrittJahr, menteeEintrittMon, menteeEintrittTag, menteeStatusOrangeGrenze)
		elif (menteeStatus == 'rot'):
			if (rawText == ''):
				rawText = page.get()
			if (not isIn(rawText, "\[\[Benutzer\:%s\|%s\]\]\:\ Eintritt\: 2" % (eukuhelp.UMLdecode(menteeName), eukuhelp.UMLdecode(menteeName)))):
				result += "\n*[[Benutzer:%s|]]: Eintritt: %s-%s-%s, seit %s Tagen inaktiv" % (eukuhelp.UMLdecode(menteeName), menteeEintrittJahr, menteeEintrittMon, menteeEintrittTag, menteeStatusRotGrenze)
		
	result += "\n--~~~~"
	
	## write it to wikipedia
	if menteeCounter > 0:
		pywikibot.showDiff(rawText, rawText + result)
		output("schreibe: " + result)
		page.put(result, sumText % menteeCounter, False, minor=True, force=True, botflag=False)

def writeOverallMenteeNumber(db):
	menteeNumber = db.get_overall_mentee_number()
	page = pywikibot.Page(pywikibot.Site(), anzahlAllerBereutenMentees)
	page.put(str(menteeNumber), "Anzahl bisheriger Mentees: %s" % menteeNumber, False, minor=True, force=True)

def writeActiveMentorNumber(db):
	mentorNumber = db.get_active_mentor_number()
	page = pywikibot.Page(pywikibot.Site(), anzahlAllerZurzeitBereuendenMentoren)
	page.put(str(mentorNumber), "Anzahl zurzeit betreuenden Mentoren: %s" % mentorNumber, False, minor=True, force=True)


"""
	read opt-in list
	XXX deprecated
"""
def optInUsersToCheck():
	optInPage = pywikibot.Page(pywikibot.Site(), wpOptInList)
	optInRawText = optInPage.get()

	p = re.compile(wpOptInListRegEx, re.UNICODE)
	userIterator = p.finditer(optInRawText)
	result = []
	for user in userIterator:
		# "_" is the same as " " for Wikipedia URls
		result.append(textlib.replaceExcept(user.group('username'), "_", " ", []))
	return result


"""
  MAIN
  gogogo
"""
# read program arguments
for arg in pywikibot.handle_args():
	if arg == '-force':
	    forceWrite = True
	else:
	    pywikibot.output(arg + " wurde ignoriert")

output(strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############",localtime()))
db = dewpmp.Database()
mentorenFromServer = db.get_all_mentors()
menteesFromServer = db.get_all_mentees()
userListWP = db.get_mw_cat_members("Benutzer:Mentee")
# check the lists
if (len(menteesFromServer) == 0 or len(mentorenFromServer) == 0):
	output("Userlist konnte nicht vom Server geladen werden")
	exit()
if (len(userListWP) == 0):
	output("Userlist konnte nicht aus WP geladen werden")
	exit()
somethingWasChanged = False
logText = ""

# müssen Mentoren benachricht werden?
# nur einmal täglich um 3:xx Uhr
# TODO
itIsThreeOClockPM = time.localtime()[3] in [3] and time.localtime()[4] in [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]
if (False and itIsThreeOClockPM):
	mentorenOptInList = optInUsersToCheck()
	for mentorStr in mentorenOptInList:
		writeInactiveMenteeListForMentor(menteesFromServer, mentorenFromServer, mentorStr)

somethingWasChanged, logText = checkForNewMentees(db, mentorenFromServer, menteesFromServer, userListWP)
result = checkForMenteesToBeArchived(mentorenFromServer, menteesFromServer, userListWP) # gibt zwei Argumente zurück (wasGeändert?, logText)
logText += result[1]
somethingWasChanged = somethingWasChanged or result[0]
if somethingWasChanged:
	output("etwas wurde verändert")

# write userlist 2 times per day or when changes were done
if (somethingWasChanged or forceWrite):
	mentorenFromServer = db.get_all_mentors()
	menteesFromServer = db.get_all_mentees()
	writeActiveMenteeList(db, logText, menteesFromServer, mentorenFromServer)
	writeMenteeArchive(db, mentorenFromServer)

if (forceWrite or itIsThreeOClockPM):
	writeOverallMenteeNumber(db)
	writeActiveMentorNumber(db)

#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	pywikibot framework is needed!

	Options:
	  -force      write the user lists even if there is nothing to do
	  --dry-run   only show what would be done, change neither the database nor Wikipedia
"""
import sys              # To not have wikipedia and this in one dir we'll import sys
import re               # Used for regular expressions
import pywikibot        # pywikibot framework
from pywikibot import textlib
from time import localtime, strftime    # strftime-Function and related
from datetime import datetime
import time
import pymysql
import traceback
sys.path.append('/data/project/pb/www/python/src')
from bot_api import BotDatabase

# templates and WP paths
tmplNewUser = "Wikipedia:Persönliche Bekanntschaften/neuer Benutzer"
newUserRegex = r"\{\{" + tmplNewUser + r"\|Name=(?P<user>[^|]+)(?:\|Kommentar=.*)?\|Zeit=(?P<timeh>(?:[01]\d|2[0-3]))\:(?P<timemin>[0-5]\d)\,\ (?P<timed>[123]?\d)\.\ (?P<timemon>Jan\.|Feb\.|Mär\.|Apr\.|Mai|Jun\.|Jul\.|Aug\.|Sep\.|Okt\.|Nov\.|Dez\.)\ (?P<timeyear>2\d\d\d)\ \(CES?T\)\}\}"
newUserReplRegex = r"\{\{" + tmplNewUser + r"\|Name=%s(?:\|Kommentar=.*?)?\|Zeit=.+?\ 2\d\d\d\ \(CES?T\)\}\}[\n\r]*"
tmplNewACK = "Wikipedia:Persönliche Bekanntschaften/neue Bestätigung"
newACKRegex = r"\{\{" + tmplNewACK + r"\|Bestätiger=(?P<certifier>[^|]+)\|Bestätigter=(?P<certified>[^|]+)\|Kommentar=(?P<comment>.*?)\|Zeit=(?P<timeh>(?:[01]\d|2[0-3]))\:(?P<timemin>[0-5]\d)\,\ (?P<timed>[123]?\d)\.\ (?P<timemon>Jan\.|Feb\.|Mär\.|Apr\.|Mai|Jun\.|Jul\.|Aug\.|Sep\.|Okt\.|Nov\.|Dez\.)\ (?P<timeyear>2\d\d\d)\ \(CES?T\)\}\}"
newACKReplRegex = r"\{\{" + tmplNewACK + r"\|Bestätiger=%s\|Bestätigter=%s\|Kommentar=.*?\|Zeit=.+?\ 2\d\d\d\ \(CES?T\)\}\}[\n\r]*"

workList = "Wikipedia:Persönliche Bekanntschaften/neue Einträge"
userRAWListPage = "Wikipedia:Persönliche Bekanntschaften/JS-alle Benutzer"
userListPage = "Wikipedia:Persönliche Bekanntschaften/Teilnehmerliste"
newUserListPage = "Wikipedia:Persönliche Bekanntschaften/Neu dazugekommen"

# check of the version history: a confirmation must be entered by the certifier himself/herself,
# a new user by the user himself/herself
reportPage = "Benutzer Diskussion:Euku"  # irregular entries are reported here
ackCheckExemptUsers = ["Euku"]  # these users may enter confirmations and new users for others
refuseIrregularEntries = True  # True => irregular entries are not stored; False => stored, but reported
maxRevisionsToCheck = 50  # how far back the version history is searched at most

# debugging
DONOTSAVEDB = False # if True => no changes will be made to the database
DONOTSAVE = False # if True => no changes will be made on Wikipedia

monthDic = {}
monthDic["Jan."] = 1
monthDic["Feb."] = 2
monthDic["Mär."] = 3
monthDic["Apr."] = 4
monthDic["Mai"]  = 5
monthDic["Jun."] = 6
monthDic["Jul."] = 7
monthDic["Aug."] = 8
monthDic["Sep."] = 9
monthDic["Okt."] = 10
monthDic["Nov."] = 11
monthDic["Dez."] = 12

# results of addConfirmation and addUser
ADDED = 'added'
ALREADY = 'already'
REFUSED = 'refused'

class ConfirmationNotStored(Exception):
	'''If the confirmation was not stored in the DB'''

def output(text):
	pywikibot.output(text)


def writeUserListToWikipedia(db, editSummary):
	if editSummary == '': editSummary = "Aktualisiere Benutzerliste"

	# load list
	userList = db.get_user_list_with_confirmations()
	#print (userList)

	#############################################
	# prepare the raw user list for JavaScripts #
	#############################################
	# convert it to a string
	newRawText = ""
	for u, confirmationCount, part_since_timestamp in userList:
		# former and bannen users are already left out
		newRawText += u + "\n"
	# save RAW-list
	page = pywikibot.Page(pywikibot.Site(), userRAWListPage)
	rawText = page.get()
	if newRawText != rawText + "\n":
		output("RAW-Benutzerliste:")
		pywikibot.showDiff(rawText, newRawText)
		if not DONOTSAVE:
			page.put(newRawText, summary=editSummary, watch='unwatch', minor=True, force=True)

	#####################################
	# prepare user list for main page   #
	#####################################
	toc: str = '{{WP:Persönliche Bekanntschaften/Infobox}}\n{{WP:Persönliche Bekanntschaften/Teilnehmerliste/Intro}}\n' \
		+ 'Angezeigt werden \'\'\'<span id="num-participants">' + str(len(userList)) + '</span>\'\'\' Teilnehmer und Teilnehmerinnen:\n'
	userTemplate = '{{DB-Link|%s|%s|%s|%s}}'
	safeUserTemplate = '{{DB-Link|1=%s|2=%s|3=%s|4=%s}}'
	classTemplate1 = '===%s===\n'
	classTemplate2 = '\n'

	currentLetter = "0–9"
	newRawText = toc + (classTemplate1 % currentLetter)
	for u, confirmationCount, part_since_timestamp in userList:
		# fill in sub headers
		if ((currentLetter == "0–9") and (u[0] == "A")):
			currentLetter = "A"
			newRawText += classTemplate2 + (classTemplate1 % currentLetter)
		elif (currentLetter != "0–9" and u[0] > currentLetter and u[0] <= "Z"):
			currentLetter = u[0]
			newRawText += classTemplate2 + (classTemplate1 % currentLetter)
		verfStatus = "u" if confirmationCount < 3 else ""
		inactiveStatus = "" # TODO
		homewiki = "" #TODO
		# names containing "=" would break positional template parameters
		if '=' in u:
			newRawText += safeUserTemplate % (u, verfStatus, inactiveStatus, homewiki)
		else:
			newRawText += userTemplate % (u, verfStatus, inactiveStatus, homewiki)
	newRawText += classTemplate2

	# save it
	page = pywikibot.Page(pywikibot.Site(), userListPage)
	rawText = page.get()
	if newRawText != rawText + "\n":
		output("Teilnehmerliste:")
		pywikibot.showDiff(rawText, newRawText)
		if not DONOTSAVE:
			page.put(newRawText, summary=editSummary, watch='unwatch', minor=True, force=True, bot=False)

	######################
	# write new users    #
	######################
	# prepare new-user list for main page
	newUserList = db.get_latest_user_list_with_confirmations()
	toc = '<noinclude>{{WP:Persönliche Bekanntschaften/Teilnehmerliste/Intro}}</noinclude>\n== Neu dazugekommen ==\n'
	# named parameters: names containing "=" would break positional template parameters
	userTemplate = '{{/Benutzer-Link|1=%s|2=%s|3=%s}} '

	newRawText = toc
	for u, confirmationCount, cfDate in newUserList:
		if confirmationCount < 3:
			userStatus = "unbestätigt"
		else:
			userStatus = ""
		date = "%s.%s" % (cfDate.day, cfDate.month) # convert to DD.MM.
		newRawText += userTemplate % (u, date, userStatus)

	# save it (MediaWiki strips trailing whitespace)
	page = pywikibot.Page(pywikibot.Site(), newUserListPage)
	rawText = page.get()
	if newRawText.rstrip() != rawText.rstrip():
		output("Neu dazugekommen:")
		pywikibot.showDiff(rawText, newRawText)
		if not DONOTSAVE:
			page.put(newRawText, summary=editSummary, watch='unwatch', minor=True, force=True, bot=False)


"""
   extrats from a text all information needed: new users and new acknoledgements
   and returns it back as a tuple
"""
def divideIntoTasks(pageText):
	# entries in comments and nowiki are not removed by replaceExcept, so they must not be processed either
	pageText = textlib.removeDisabledParts(pageText, ["comment", "nowiki"])

	### find new user requests
	p = re.compile(newUserRegex, re.UNICODE)
	taskIterator = p.finditer(pageText)
	newUsers = []
	for task in taskIterator:
		if task.group('timemon') in monthDic:
			newUsers.append((task.group('user'), int(task.group('timemin')), int(task.group('timeh')), int(task.group('timed')), monthDic[task.group('timemon')], int(task.group('timeyear'))))

	## find new acknowledgements
	p = re.compile(newACKRegex, re.UNICODE)
	taskIterator = p.finditer(pageText)
	newACKs = []
	for task in taskIterator:
		if task.group('timemon') in monthDic:
			newACKs.append((task.group('certifier'), task.group('certified'), task.group('comment'), int(task.group('timemin')), int(task.group('timeh')), int(task.group('timed')), monthDic[task.group('timemon')], int(task.group('timeyear'))))

	return newUsers, newACKs


"""
   returns 'YYYY-MM-DD hh:mm:00' or None if the date does not exist (e.g. 30. Feb.)
"""
def makeTimestamp(year, month, day, hours, minutes):
	try:
		return datetime(year, month, day, hours, minutes).strftime("%Y-%m-%d %H:%M:00")
	except ValueError:
		return None


"""
   sends information to the DB API skript
   returns (ADDED|ALREADY|REFUSED, reason); raises pymysql.DatabaseError or
   ConfirmationNotStored if it is unclear whether the confirmation was stored
"""
def addConfirmation(db, bestaetigerName, bestaetigterName, comment, timestamp):
	bestaetiger = db.get_user_by_name(bestaetigerName)
	bestaetigter = db.get_user_by_name(bestaetigterName)
	for user, name in ((bestaetiger, bestaetigerName), (bestaetigter, bestaetigterName)):
		if user is None:
			return REFUSED, "%s ist kein Teilnehmer" % name
		# hidden (former) and banned users: the edit summary is public, so do not tell the exact reason
		if user[3] or user[4]:
			output("%s ist %s" % (name, "gesperrt" if user[4] else "ausgetreten (versteckt)"))
			return REFUSED, "%s ist kein Teilnehmer" % name
	bestaetigerID = bestaetiger[1]
	bestaetigterID = bestaetigter[1]

	if db.get_cf_count_by_confirmed(bestaetigerID) < 3:
		output("Darf noch nicht bestätigen")
		return REFUSED, "%s hat noch keine 3 Bestätigungen" % bestaetigerName

	###### write to DB
	output("send it to DB API...")
	if not DONOTSAVEDB:
		try:
			if not db.add_confirmation(bestaetigerID, bestaetigterID, comment, timestamp):
				output("Validierung schlug fehl!")
				return REFUSED, "Validierung schlug fehl"
		except pymysql.IntegrityError:
			output("Bestätigung schon vorhanden")
			return ALREADY, ""
		output("bestaetigerID %s, bestaetigterID %s" % (bestaetigerID, bestaetigterID))
		if not db.has_confirmed(bestaetigerID, bestaetigterID):
			output("Bestätigung wurde nicht übertragen!")
			raise ConfirmationNotStored('Bestätigung %s -> %s zu %s wurde nicht übertragen!' % (bestaetigerName, bestaetigterName, timestamp))

	### check if 'bestaetigterName' is allowed to write ACKs now and leave a message on his/her talk page
	if db.get_cf_count_by_confirmed(bestaetigterID) == 3:
		# ok, write a message
		msgText = "\n==[[Wikipedia:Persönliche Bekanntschaften]] ==\nHallo " + bestaetigterName + ".\nDu wurdest vor ein paar Minuten von " + bestaetigerName + " bestätigt und hast damit insgesamt drei Bestätigungen. D.h. von nun an darfst du [[Wikipedia:Persönliche Bekanntschaften/neue Anfragen|selber Bestätigungen verteilen]] an Wikipedianer, die du persönlich kennengelernt hast. Bei Fragen wende dich [[Wikipedia Diskussion:Persönliche Bekanntschaften|hier]] hin. Gruß --~~~~"
		output("war unbestaetigt und darf nun selber bestaetigen")
		userTalkPage = pywikibot.Page(pywikibot.Site(), "Benutzer_Diskussion:" + bestaetigterName)
		if not DONOTSAVE:
			try:
				oldText = userTalkPage.get() if userTalkPage.exists() else ""
				userTalkPage.put(oldText + msgText, summary="du wurdest zum dritten Mal bestätigt", watch='unwatch', minor=False, force=True, bot=False)
			except pywikibot.exceptions.Error as e:
				pywikibot.error("Nachricht auf %s nicht gespeichert: %r" % (userTalkPage.title(), e))
	return ADDED, ""


"""
   returns (ADDED|ALREADY|REFUSED, reason); raises pymysql.DatabaseError
"""
def addUser(db, userName, timestamp):
	if DONOTSAVEDB:
		return ADDED, ""
	try:
		if not db.add_user(userName, timestamp):
			return REFUSED, "Benutzer existiert nicht"
	except pymysql.IntegrityError:
		output("user " + userName + " already in")
		return ALREADY, ""
	return ADDED, ""


def userLink(name):
	return "[[:User:%s|%s]]" % (name, name)


def normalizeUser(name):
	name = re.sub(r"[_\s]+", " ", name).strip()
	first = name[:1].upper()
	if len(first) != 1:
		# e.g. "ß".upper() == "SS", MediaWiki keeps it
		first = name[:1]
	return first + name[1:]


def userKey(name):
	return ('user', normalizeUser(name))


def ackKey(certifier, certified):
	return ('ack', normalizeUser(certifier), normalizeUser(certified))


def taskKeys(pageText):
	newUsers, newACKs = divideIntoTasks(pageText)
	return set(userKey(u[0]) for u in newUsers) | set(ackKey(a[0], a[1]) for a in newACKs)


"""
   searches the version history (newest first) for the revisions that entered
   the given entries (userKey/ackKey), i.e. back to the last run of the bot that
   removed the older entries; returns {key: (user, revid)}, user is None if hidden
   Only the key is compared, not the whole entry: whoever re-adds a removed entry
   (e.g. a revert) counts as its author, and changes to the comment or time of an
   entry by someone else are not noticed.
"""
def findAuthors(page, pending):
	pending = set(pending)
	candidates = {}
	authors = {}
	for rev in page.revisions(content=True, total=maxRevisionsToCheck):
		keys = taskKeys(rev.text or "")
		for key in list(pending):
			if key in keys:
				# still contained => this or an older revision entered it
				candidates[key] = (None if rev.userhidden else rev.user, rev.revid)
			else:
				# not contained => the newer revision entered it
				authors[key] = candidates.get(key, (None, None))
				pending.discard(key)
		if not pending:
			break
	for key in pending:
		# beyond maxRevisionsToCheck, take the oldest revision checked
		output("Ersteller von %s nicht sicher ermittelt" % " -> ".join(key[1:]))
		authors[key] = candidates.get(key, (None, None))
	return authors


"""
   rolls back the open transaction after a database error, so that a half
   written entry is not committed together with the next one
"""
def rollback(db):
	try:
		db.conn.rollback()
	except pymysql.Error as e:
		pywikibot.error("Rollback fehlgeschlagen: %r" % e)


"""
   reports irregular entries on reportPage
"""
def reportIrregularEntries(irregularEntries):
	lines = []
	for what, author, revid, status in irregularEntries:
		diff = " ([[Spezial:Diff/%s|Diff]])" % revid if revid else ""
		authorText = userLink(author) if author else "(versteckter Benutzer)"
		lines.append("* %s, eingetragen von %s%s – %s" % (what, authorText, diff, status))
	msgText = "\n== [[Wikipedia:Persönliche Bekanntschaften]]: irreguläre Einträge ==\nFolgende Einträge wurden nicht vom Bestätiger bzw. vom neuen Benutzer selbst eingetragen:\n" \
		+ "\n".join(lines) + "\nGruß --~~~~"
	output(msgText)
	if DONOTSAVE:
		return
	page = pywikibot.Page(pywikibot.Site(), reportPage)
	try:
		oldText = page.get() if page.exists() else ""
		page.put(oldText + msgText, summary="irreguläre Einträge bei [[WP:PB]]", watch='unwatch', minor=False, force=True, bot=False)
	except pywikibot.exceptions.Error as e:
		pywikibot.error("Meldung auf %s nicht gespeichert: %r" % (reportPage, e))


"""
  MAIN
"""
class PBBot:
	def __init__(self, isForceMode=False):
		self._site = pywikibot.Site()
		self.isForceMode = isForceMode

	def run(self):
		output(strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############",localtime()))
		if DONOTSAVE or DONOTSAVEDB:
			output("Dry run: nothing will be saved")
		self.db = BotDatabase()

		page = pywikibot.Page(self._site, workList)
		rawText = page.get()
		newRawText = rawText

		if not page.botMayEdit():
			output("Seite gesperrt")
			return

		# lists of short texts for the edit summary
		usersAdded = []
		usersAlreadyIn = []
		usersRefused = []
		acksAdded = []
		acksAlreadyIn = []
		acksRefused = []
		irregularSummary = []
		irregularEntries = [] # for reportPage
		errors = 0 # entries that stay on the page because of a database error

		newUsers, newACKs = divideIntoTasks(rawText)
		pendingKeys = taskKeys(rawText)
		authors = findAuthors(page, pendingKeys) if pendingKeys else {}
		exemptUsers = set(normalizeUser(u) for u in ackCheckExemptUsers)

		def irregularStatus(status, reason):
			return {ADDED: "übernommen", ALREADY: "war schon vorhanden"}.get(status, "abgelehnt: " + reason)

		seenUsers = []
		for rawName, minutes, hours, day, month, year in newUsers:
			# the raw name is needed to remove the entry, the normalized one for the DB
			if rawName in seenUsers:
				output("überspringe %s weil schon enthalten" % rawName)
				continue
			seenUsers.append(rawName)
			currentName = normalizeUser(rawName)

			output("füge %s hinzu.. "  % currentName)
			entry = newUserReplRegex % re.escape(rawName)
			timestamp = makeTimestamp(year, month, day, hours, minutes)
			author, revid = authors.get(userKey(currentName), (None, None))
			irregular = author is None or normalizeUser(author) not in exemptUsers | {currentName}
			if irregular:
				output("irregulär: %s eingetragen von %s" % (currentName, author))
			if irregular and refuseIrregularEntries:
				status, reason = REFUSED, "nicht vom Benutzer selbst eingetragen"
			elif timestamp is None:
				status, reason = REFUSED, "ungültiges Datum"
			else:
				try:
					status, reason = addUser(self.db, currentName, timestamp)
				except pymysql.DatabaseError:
					# the entry stays on the page and will be tried again next time
					pywikibot.error("Benutzer %s nicht übertragen:\n%s" % (currentName, traceback.format_exc()))
					rollback(self.db)
					errors += 1
					continue
			newRawText = textlib.replaceExcept(newRawText, entry, "", ["comment", "nowiki"])

			# build comments for edit summary
			if irregular:
				statusText = irregularStatus(status, reason)
				irregularEntries.append(("neuer Benutzer " + userLink(currentName), author, revid, statusText))
				irregularSummary.append("neuer Benutzer %s (eingetragen von %s, %s)" % (userLink(currentName), author or "verstecktem Benutzer", statusText))
			elif status == ADDED:
				usersAdded.append(userLink(currentName))
			elif status == ALREADY:
				usersAlreadyIn.append(userLink(currentName))
			else:
				output("abgelehnt: %s (%s)" % (currentName, reason))
				usersRefused.append("%s (%s)" % (userLink(currentName), reason))

		for currentACK in newACKs:
			rawCertifier, rawCertified, comment, minutes, hours, day, month, year = currentACK
			certifier, certified = normalizeUser(rawCertifier), normalizeUser(rawCertified)
			output("füge Bestätigung: %s >> %s (Kommentar: %s) am %s.%s.%s %s:%02d hinzu.." % (certifier, certified, comment, day, month, year, hours, minutes))
			entry = newACKReplRegex % (re.escape(rawCertifier), re.escape(rawCertified))
			timestamp = makeTimestamp(year, month, day, hours, minutes)
			author, revid = authors.get(ackKey(certifier, certified), (None, None))
			irregular = author is None or normalizeUser(author) not in exemptUsers | {certifier}
			if irregular:
				output("irregulär: %s -> %s eingetragen von %s" % (certifier, certified, author))
			if irregular and refuseIrregularEntries:
				status, reason = REFUSED, "nicht vom Bestätiger eingetragen"
			elif timestamp is None:
				status, reason = REFUSED, "ungültiges Datum"
			else:
				try:
					status, reason = addConfirmation(self.db, certifier, certified, comment, timestamp)
				except (pymysql.DatabaseError, ConfirmationNotStored):
					# we cannot be sure that the confirmation was stored: the entry stays
					# on the page and will be checked again next time
					pywikibot.error("Bestätigung %s -> %s nicht übertragen:\n%s" % (certifier, certified, traceback.format_exc()))
					rollback(self.db)
					errors += 1
					continue
			newRawText = textlib.replaceExcept(newRawText, entry, "", ["comment", "nowiki"])

			# build comments for edit summary
			ack = "%s → %s" % (userLink(certifier), userLink(certified))
			if irregular:
				statusText = irregularStatus(status, reason)
				irregularEntries.append(("Bestätigung " + ack, author, revid, statusText))
				irregularSummary.append("%s (eingetragen von %s, %s)" % (ack, author or "verstecktem Benutzer", statusText))
			elif status == ADDED:
				acksAdded.append(ack)
			elif status == ALREADY:
				acksAlreadyIn.append(ack)
			else:
				output("abgelehnt: %s -> %s (%s)" % (certifier, certified, reason))
				acksRefused.append("%s (%s)" % (ack, reason))

		if errors:
			output("%s Einträge wegen Datenbankfehlern nicht übertragen, sie bleiben auf der Seite" % errors)

		##### edit comments
		parts = [
			("Bestätigungen", acksAdded),
			("Bestätigungen schon vorhanden", acksAlreadyIn),
			("Bestätigungen abgelehnt", acksRefused),
			("neue(r) Benutzer", usersAdded),
			("Benutzer schon hinzugefügt", usersAlreadyIn),
			("Benutzer abgelehnt", usersRefused),
		]
		commentLong = "; ".join("%s: %s" % (pre, ", ".join(items)) for pre, items in parts if items)
		commentShort = "; ".join("%s: %s" % (pre, len(items)) for pre, items in parts if items)
		if (len(commentLong) > 200):
			editSummary = commentShort
		else:
			editSummary = commentLong
		# irregular entries are always named explicitly
		workListSummary = editSummary
		if irregularSummary:
			workListSummary = "; ".join(x for x in ["IRREGULÄRE Einträge: " + ", ".join(irregularSummary), editSummary] if x)

		## update wikipedia: delete requests
		if self.isForceMode or newRawText != rawText:
			if newRawText != rawText:
				output("Anfragen:")
				pywikibot.showDiff(rawText, newRawText)
				if not DONOTSAVE:
					page.put(newRawText, summary="In Datenbank übertragen: " + workListSummary, watch='unwatch', minor=False, bot=True)
			writeUserListToWikipedia(self.db, editSummary)
			if irregularEntries:
				reportIrregularEntries(irregularEntries)
			output("Zusammenfassung: " + workListSummary + "\n")
		else:
			output("nichts zu tun")
			# write userlist twice per day (03:00 and 15:00, the container runs in UTC)
			if time.localtime()[3] in [3,15] and time.localtime()[4] in [0,1,2,3,4,5,6,7,8,9]:
				writeUserListToWikipedia(self.db, editSummary)

	def shutdown(self):
		self.db.close_connections()

# start here
isForceMode = False
for arg in pywikibot.handle_args():
	if arg in ('-force', '--force'):
		isForceMode = True
	elif arg in ('--dry-run', '-dryrun'):
		DONOTSAVE = True
		DONOTSAVEDB = True
bot = PBBot(isForceMode)
bot.run()
bot.shutdown()

#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	pywikibot framework is needed!
"""
import sys              # To not have wikipedia and this in one dir we'll import sys
import re               # Used for regular expressions
import os               # used for os.getcwd()
import pywikibot        # pywikibot framework
from pywikibot import textlib
from time import localtime, strftime    # strftime-Function and related
from datetime import datetime, timedelta
sys.path.append('/data/project/pb/www/python/src')
from bot_api import BotDatabase

wpOptInList = "Wikipedia:Persönliche Bekanntschaften/Opt-in: Benachrichtigungen"
wpOptInListRegEx = "\[\[(?:[uU]ser|[bB]enutzer|[bB]enutzerin)\:(?P<username>[^\|\]]+)(?:\|[^\]]+)?\]\]"
localLogFile = os.getcwd() + strftime("/logs/pb-info-bot-%Y-%m.log",localtime())

# debugging
DONOTSAVE = False # if True => no changes will be made on Wikipedia
diffDays = 1 # to check e.g. yesterday set this to 1. Attention to the first day of a month! It doesn't work.

def output(text):
	pywikibot.output(text)

"""
	opt-in list
"""
def usersToCheck():
	optInPage = pywikibot.Page(pywikibot.Site(), wpOptInList)
	optInRawText = optInPage.get()

	p = re.compile(wpOptInListRegEx, re.UNICODE)
	userIterator = p.finditer(optInRawText)
	result = []
	for user in userIterator:
		# "_" is the same as " " for Wikipedia URls
		username = textlib.replaceExcept(user.group('username'), "_", " ", [])
		if len(username) == 1:
			username = username[0].capitalize()
		elif len(username) > 1:
			username = username[0].capitalize() + username[1:]
		result.append(username)
	return result


def isIn(text, regex):
	return re.search(regex, text, re.UNICODE)

def search(text, regex):
        m = re.search(regex, text, re.UNICODE)
        if m:
          return m.groups()[0]
        else:
          return ""

"""
  MAIN
"""
output(strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############",localtime()))
db = BotDatabase()

# request list of all users that are opt-in
usersToCheck = usersToCheck()
output("%s users found in opt-in list" % len(usersToCheck))

todaysVerifications = db.get_yesterdays_confirmations_sorted_by_confirmed(day=1,delta=diffDays) # yesterday only
output("today %s confirmations were commited at all:" % len(todaysVerifications))
#print todaysVerifications

# who are the people the bot must write a message?
usersWaitingForMsg = []
for (was_confirmed_name, has_confirmed_name, cf_time) in todaysVerifications:
	if (not (was_confirmed_name in usersWaitingForMsg)) and was_confirmed_name in usersToCheck:
		usersWaitingForMsg.append(was_confirmed_name)

# send them a message
for userWaitingForMsg in usersWaitingForMsg:
	usersVeriedThisUser = []
	for (was_confirmed_name, has_confirmed_name, cf_time) in todaysVerifications:
		if was_confirmed_name == userWaitingForMsg:
			usersVeriedThisUser.append(has_confirmed_name)

	# write a message
	userTalkPage = pywikibot.Page(pywikibot.Site(), "Benutzer_Diskussion:" + userWaitingForMsg)
	try:
		userTalkPageRaw = userTalkPage.get()
	except pywikibot.NoPage:
		userTalkPageRaw = ""
	usersVeriedThisUserText = ""
	# concat a string with 'user1, user2, ... and userN'
	if len(usersVeriedThisUser) == 1:
		u = usersVeriedThisUser[0]
		usersVeriedThisUserText = "{{noping|%s|%s}}" % (u, u)
	else:
		for u in usersVeriedThisUser[:len(usersVeriedThisUser)-1]:
			usersVeriedThisUserText += ", {{noping|%s|%s}}" % (u, u)
		lastU = usersVeriedThisUser[len(usersVeriedThisUser)-1]
		usersVeriedThisUserText += " und {{noping|%s|%s}}" % (lastU, lastU)
		# remove ', ' at the beginning
		usersVeriedThisUserText = usersVeriedThisUserText[2:]

	msgToUser = userTalkSummary = ""
	forThisDayText = ''
	if diffDays==0:
		forThisDayText = "heute"
	elif diffDays == 1:
		forThisDayText = "gestern"
	elif diffDays == 2:
		forThisDayText = "vorgestern"
	else:
		forThisDayText = "vor %s Tagen" % diffDays
	prevDate = datetime.now() - timedelta(diffDays)

	if len(usersVeriedThisUser) == 1:
		msgToUser = "\n== neue Bestätigung am %s.%s.%s ==\nHallo! Du hast %s eine neue Bestätigung von %s bei [[WP:Persönliche Bekanntschaften|]] erhalten. [[Wikipedia:Persönliche Bekanntschaften/neue Anfragen|Hier]] kannst du selber bestätigen. Du bekommst diese Nachricht, weil du in [[Wikipedia:Persönliche Bekanntschaften/Opt-in: Benachrichtigungen|dieser Liste]] stehst. Gruß --~~~~" % (prevDate.day, prevDate.month, prevDate.year, forThisDayText, usersVeriedThisUserText)
		userTalkSummary = "Neuer Abschnitt /* neue Bestätigung am %s.%s.%s */" % (prevDate.day, prevDate.month, prevDate.year)
	else:
		msgToUser = "\n== neue Bestätigungen am %s.%s.%s ==\nHallo! Du hast %s neue Bestätigungen von %s bei [[WP:Persönliche Bekanntschaften|]] erhalten. [[Wikipedia:Persönliche Bekanntschaften/neue Anfragen|Hier]] kannst du selber bestätigen. Du bekommst diese Nachricht, weil du in [[Wikipedia:Persönliche Bekanntschaften/Opt-in: Benachrichtigungen|dieser Liste]] stehst. Gruß --~~~~" % (prevDate.day, prevDate.month, prevDate.year, forThisDayText, usersVeriedThisUserText)
		userTalkSummary = "Neuer Abschnitt /* neue Bestätigungen am %s.%s.%s */" % (prevDate.day, prevDate.month, prevDate.year)

	output("Writing message to " + userWaitingForMsg + "...")
	output("message: " + msgToUser)
	archiveHelp = ""
	if (isIn(userTalkPageRaw, "\{\{\ *[Aa]utoarchiv")):
		archiveHelp = " <!{{subst:ns:0}}-- Hilfe für den Auto-Archiv-Bot: ~~~~~ -->"
	elif (isIn(userTalkPageRaw, "\{\{\ *[Aa]utoarchiv\-Erledigt")):
		archiveHelp = "\n{{Erledigt|1=~~~~}}"
	if not DONOTSAVE:
		try:
			userTalkPage.put(userTalkPageRaw + msgToUser + archiveHelp, userTalkSummary, False, minorEdit=False, force=True, botflag=True)
		except:
			output("Exception mache weiter...")

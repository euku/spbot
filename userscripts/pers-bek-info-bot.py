#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	pywikibot framework is needed!

	Options:
	  --dry-run   only show the messages, do not save anything
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
wpOptInListRegEx = r"\[\[(?:[uU]ser|[bB]enutzer|[bB]enutzerin)\:(?P<username>[^\|\]]+)(?:\|[^\]]+)?\]\]"
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
	the talk page to write to and its text; a redirect (e.g. after a rename) to another user talk page is followed
"""
def talkPage(userName):
	page = pywikibot.Page(pywikibot.Site(), "Benutzer_Diskussion:" + userName)
	try:
		return page, page.get()
	except pywikibot.exceptions.NoPageError:
		return page, ""
	except pywikibot.exceptions.IsRedirectPageError:
		target = page.getRedirectTarget()
		if target.site != page.site or target.namespace() != 3:
			raise ValueError("%s ist eine Weiterleitung auf %s" % (page.title(), target.title()))
		return target, target.get()

"""
	'user1, user2, ... und userN'
"""
def joinNames(names):
	links = ["{{noping|%s|%s}}" % (u, u) for u in names]
	if len(links) == 1:
		return links[0]
	return ", ".join(links[:-1]) + " und " + links[-1]

"""
	informs one user about the confirmations by the given users
"""
def informUser(userName, confirmers, prevDate):
	forThisDayText = {0: "heute", 1: "gestern", 2: "vorgestern"}.get(diffDays, "vor %s Tagen" % diffDays)
	date = "%s.%s.%s" % (prevDate.day, prevDate.month, prevDate.year)
	if len(confirmers) == 1:
		headline, what = "neue Bestätigung am " + date, "eine neue Bestätigung"
	else:
		headline, what = "neue Bestätigungen am " + date, "neue Bestätigungen"
	userTalkPage, userTalkPageRaw = talkPage(userName)
	if "== %s ==" % headline in userTalkPageRaw:
		output("%s wurde schon benachrichtigt" % userName)
		return

	msgToUser = "\n== %s ==\nHallo! Du hast %s %s von %s bei [[WP:Persönliche Bekanntschaften|]] erhalten. [[Wikipedia:Persönliche Bekanntschaften/neue Anfragen|Hier]] kannst du selber bestätigen. Du bekommst diese Nachricht, weil du in [[Wikipedia:Persönliche Bekanntschaften/Opt-in: Benachrichtigungen|dieser Liste]] stehst. Gruß --~~~~" % (headline, forThisDayText, what, joinNames(confirmers))
	userTalkSummary = "Neuer Abschnitt /* %s */" % headline

	output("Writing message to " + userName + "...")
	output("message: " + msgToUser)
	archiveHelp = ""
	if (isIn(userTalkPageRaw, r"\{\{\ *[Aa]utoarchiv\-Erledigt")):
		archiveHelp = "\n{{Erledigt|1=~~~~}}"
	elif (isIn(userTalkPageRaw, r"\{\{\ *[Aa]utoarchiv")):
		archiveHelp = " <!{{subst:ns:0}}-- Hilfe für den Auto-Archiv-Bot: ~~~~~ -->"
	if not DONOTSAVE:
		# appendtext: the server appends, so there are no edit conflicts and nothing written in the meantime is lost
		pywikibot.Site().editpage(userTalkPage, summary=userTalkSummary, minor=False, bot=True, watch='unwatch', appendtext=msgToUser + archiveHelp)
	else:
		output("Dry run: %s not saved (summary: %s, archiveHelp: %r)" % (userTalkPage.title(), userTalkSummary, archiveHelp))

"""
	informs all users on the opt-in list; returns the number of users that could not be informed
"""
def run(db):
	# request list of all users that are opt-in
	optInUsers = usersToCheck()
	output("%s users found in opt-in list" % len(optInUsers))

	todaysVerifications = db.get_yesterdays_confirmations_sorted_by_confirmed(day=1,delta=diffDays) # yesterday only
	output("today %s confirmations were commited at all:" % len(todaysVerifications))

	# who are the people the bot must write a message?
	confirmersByUser = {}
	for (was_confirmed_name, has_confirmed_name, cf_time) in todaysVerifications:
		if was_confirmed_name in optInUsers:
			confirmersByUser.setdefault(was_confirmed_name, []).append(has_confirmed_name)

	# send them a message
	prevDate = datetime.now() - timedelta(diffDays)
	failed = 0
	for userName, confirmers in confirmersByUser.items():
		try:
			informUser(userName, confirmers, prevDate)
		except Exception as e:
			# the others must get their message anyway, there is no second run for this day
			failed += 1
			pywikibot.error("%s nicht benachrichtigt: %r, mache weiter..." % (userName, e))
	return failed

"""
  MAIN
"""
def main():
	global DONOTSAVE
	for arg in pywikibot.handle_args():
		if arg in ('--dry-run', '-dryrun'):
			DONOTSAVE = True
	output(strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############",localtime()))
	if DONOTSAVE:
		output("Dry run: nothing will be saved")
	db = BotDatabase()
	try:
		return 1 if run(db) else 0 # 1 => Toolforge sends a mail
	finally:
		db.close_connections()

if __name__ == "__main__":
	sys.exit(main())

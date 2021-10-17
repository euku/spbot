#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	Wikipedia-pybot-framework is needed!
	
	These command line parameters can be used to specify how to work:
	...
	
	author: Euku
"""
import sys              # To not have pywikibot.and this in one dir we'll import sys
import re               # Used for regular expressions
import os               # used for os.getcwd()
import pywikibot        # Wikipedia-pybot-framework
import pywikibot.exceptions
from pywikibot.data import api
import urllib2
import locale			# German
from time import localtime, strftime, mktime    # strftime-Function and related
import time

# dbrepllag erhöhen
from pywikibot import config2
config2.maxlag = 5000 # bei dbrepllag unterhalb dieses Werts trotzdem editieren
config2.put_throttle = 0

#blockedUsersApiRegEx = "\<block\ user=\"(?P<blockedusername>.+?)\"\ by=\"(?P<byadmin>.*?)\"\ timestamp=\"(?P<timeY>20\d\d)\-(?P<timeMon>\d\d)\-(?P<timeD>\d\d)T(?P<timeH>\d\d)\:(?P<timeM>\d\d)\:(?P<timeS>\d\d).\"\ expiry=\"(?P<timeExp>.+?)\"\ reason=\"(?P<reason>.*?)\"\ \/\>"
expRegEx = "(?P<timeExpY>20\d\d)\-(?P<timeExpMon>\d\d)\-(?P<timeExpD>\d\d)T(?P<timeExpH>\d\d)\:(?P<timeExpM>\d\d)\:(?P<timeExpS>\d\d)."
vmHeadlineRegEx = u"(==\ *?\[*?(?:[Bb]enutzer\:|[Uu]ser\:|Spezial\:Beiträge\/|Special:Contributions\/)?%s(?:\|[^]]+)?\ *\]*?)\ *?==\ *"
vmHeadlineUserRegEx = u"(?:==\ *\[+(?:[Bb]enutzer\:|[Uu]ser\:|Spezial\:Beiträge\/|Special:Contributions\/)(?P<username>[^]\|=]+?)\ *\]+).*==\ *"
vmErlRegEx = u"(?:\(erl\.?\)|\(erledigt\)|\(gesperrt\))"

vmPageName = u"Wikipedia:Vandalismusmeldung"
#vmPageName = u"Benutzer:Euku/Spielwiese"

optOutListReceiverName = u"Benutzer:Euku/Opt-out: VM-Nachrichtenempfänger"
optOutListAccuserName = u"Benutzer:Euku/Opt-out: VM-Steller"
wpOptOutListRegEx = u"\[\[(?:[uU]ser|[bB]enutzer)\:(?P<username>[^\|\]]+)(?:\|[^\]]+)?\]\]"
#timeStampRegEx = u"(?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2}),\ (?P<dd>[0-9]{1,2})\.?\ (?P<MM>[a-zA-Zä]{3,10})\.?\ (?P<yyyy>[0-9]{4})\ \((?:CE[S]?T|ME[S]?Z|UTC)\)"

vmMessageTemplate = u"Benutzer:Euku/Botvorlage: Info zur VM-Meldung"

waittime = 15 # seconds!
optOutMaxAge = 60*60*6 # 6h

"""
	return the number of the days for a month
"""
def countDays(year, month):
	if month == 1 or month == 3 or month == 5 or month == 7 or month == 8 or month == 10 or month == 12:
		return 31
	elif (month == 4 or month == 6 or month == 9 or month == 11):
		return 30
	elif month == 2:
		if (year % 4 and not (year % 100) and not (year % 400)): # schalt jahr
			return 29
		else:
			return 28
	else:
		output(u"countDays(year, month) got: %s, %s" % (year, month))
		return u"ERROR"


def isIn(text, regex):
	return re.search(regex, text, re.UNICODE)
	
def search(text, regex):
	m = re.search(regex, text, re.UNICODE)
	if m:
	  return m.groups()[0]
	else:
	  return u""

def output(text):
#	localLogFile = os.getcwd() + strftime("/logs/vm-erl-bot-%Y-%m-%d.log",localtime())
#	fd = open(localLogFile, 'a')
#	writeMe = text + u"\n"
#	writeMe = writeMe.encode('utf-8')
#	fd.write(writeMe)
#	fd.close()
	pywikibot.output(text)

"""
	returns:
		[(blockedusername, byadmin, timestamp, blocklength, reason)], nexttimestamp
	http://de.wikipedia.org/w/api.php?action=query&list=blocks&bkusers=&format=xml&bkprop=user|by|timestamp|expiry|reason&bkend=2

"""
def loadBlockedUsers(nexttimestamp):
	newNexttimestamp = nexttimestamp
	results = []
	req = api.Request(site=mysite, action="query")
	req['list'] = 'blocks'
	req['bkusers'] = ''
	req['bkprop'] = 'user|by|timestamp|expiry|reason'
	req['bkend'] = nexttimestamp
	data = req.submit()
	newBlockedUsers = []
	for block in data['query']['blocks']:
		blockedusername = block['user']
		byadmin = block['by']
		timeY = int(search(block['timestamp'], r'(\d\d\d\d)\-.*'))
		timeMon = int(search(block['timestamp'], r'\d\d\d\d\-(\d\d).*'))
		timeD = int(search(block['timestamp'], r'\d\d\d\d\-\d\d\-(\d\d)T.*'))
		timeH = int(search(block['timestamp'], r'\d\d\d\d\-\d\d\-\d\dT(\d\d).*'))
		timeM = int(search(block['timestamp'], r'\d\d\d\d\-\d\d\-\d\dT\d\d\:(\d\d).*'))
		timeS = int(search(block['timestamp'], r'\d\d\d\d\-\d\d\-\d\dT\d\d\:\d\d\:(\d\d)Z'))
		timeExp = block['expiry']
		reason = block['reason']

		# check if it was infinity
		timeExpMon = timeExpD = timeExpH = timeExpM = timeExpS = ""
		if timeExp != "infinity":
			p = re.compile(expRegEx, re.UNICODE)
			expDateIterator = p.finditer(timeExp)
			for element in expDateIterator:
				timeExpY = int(element.group('timeExpY'))
				timeExpMon = int(element.group('timeExpMon'))
				timeExpD = int(element.group('timeExpD'))
				timeExpH = int(element.group('timeExpH'))
				timeExpM = int(element.group('timeExpM'))
				timeExpS = int(element.group('timeExpS'))
		
		# for how long was the user blocked?
		if timeExp == "infinity":
			blocklength = u"unbeschränkt"
		else:
			# offsets
			offsM = offsH = offsD = offsMon = offsY = 0
			# seconds
			diffS = timeExpS - timeS
			if diffS < 0:
				diffS = diffS + 60
				offsM = 1
			# minutes
			diffM = timeExpM - timeM - offsM
			if diffM < 0:
				diffM = diffM + 60
				offsH = 1
			# hours
			diffH = timeExpH - timeH - offsH
			if diffH < 0:
				diffH = diffH + 24
				offsD = offsD + 1
			# days
			diffD = timeExpD - timeD - offsD
			if diffD < 0:
				diffD = diffD + countDays(timeY, timeMon) ##- timeD + timeExpD ### remaining days in current month + fist days of the month of exipiration
				offsMon = offsMon + 1
			# months
			diffMon = timeExpMon - timeMon - offsMon
			if diffMon < 0:
				diffMon = diffMon + 12
				offsY = offsY + 1
			# years
			diffY = timeExpY - timeY - offsY
			if diffY < 0:
				diffY = "ERROR"

			# concat the human readable string
			blocklength = u""
			if diffY == 1:
				blocklength = blocklength + u"1 Jahr"
			elif diffY > 1:
				blocklength = blocklength + (u"%s Jahre" % diffY)
			if (diffY and (diffMon or diffD or diffH or diffM or diffS)): blocklength = blocklength + u", "
			if diffMon == 1:
				blocklength = blocklength + u"1 Monat"
			elif diffMon > 1:
				blocklength = blocklength + (u"%s Monate" % diffMon)
			if (diffY or diffMon and (diffD or diffH or diffM or diffS)): blocklength = blocklength + u", "
			if diffD == 1:
				blocklength = blocklength + u"1 Tag"
			elif diffD > 1:
				blocklength = blocklength + (u"%s Tage" % diffD)
			if ((diffY or diffMon or diffD) and (diffH or diffM or diffS)): blocklength = blocklength + u", "
			if diffH == 1:
				blocklength = blocklength + u"1 Stunde"
			elif diffH > 1:
				blocklength = blocklength + (u"%s Stunden" % diffH)
			if ((diffY or diffMon or diffD or diffH) and (diffM or diffS)): blocklength = blocklength + u", "
			if diffM == 1:
				blocklength = blocklength + u"1 Minute"
			elif diffM > 1:
				blocklength = blocklength + (u"%s Minuten" % diffM)
			if ((diffY or diffMon or diffD or diffH or diffM) and diffS): blocklength = blocklength + u", "
			if diffS == 1:
				blocklength = blocklength + u"1 Sekunde"
			elif diffS > 1:
				blocklength = blocklength + (u"%s Sekunden" % diffS)

		nextCandForTimestamp = u"%02d%02d%02d%02d%02d%02d" % (timeY, timeMon, timeD, timeH, timeM, timeS) # convert to string
		# use the latest block only
		if int(nextCandForTimestamp) > int(newNexttimestamp):
			newNexttimestamp  = nextCandForTimestamp
			
#			# subtract in very simple way some seconds, in order to mark some following block requests
#			# avoid times like 12:34:-5 - hh:mm:ss
#			if (int(nexttimestamp[10:]) - waittime + 1 > 0):
#				nexttimestamp = str(int(nexttimestamp) - waittime + 1)
#			else:
#				nexttimestamp = nexttimestamp[10:] + u"00"
		
		el = blockedusername, byadmin, u"%02d%02d%02d%02d%02d%02d" % (timeY, timeMon, timeD, timeH, timeM, timeS), blocklength, reason
		newBlockedUsers.append(el)
	
	# avoid times like 12:34:60 - hh:mm:ss
	#output( nexttimestamp)
	#output(nexttimestamp[12:], nexttimestamp[10:12])
	if nexttimestamp == newNexttimestamp:
		# there are no new blocks
		# increase nexttimestamp by 1 sec.
		if int(nexttimestamp[12:]) + 1 < 60: # e.g. 12:34 - mm:ss
			newNexttimestamp = str(int(nexttimestamp) + 1)
		elif int(nexttimestamp[12:]) + 1 >= 60:
			if (int(nexttimestamp[10:12]) + 1 < 60): # e.g. 12:59 - mm:ss
				newNexttimestamp = str(int(nexttimestamp) + 41) # e.g. 11:59 (mm:ss) + 1 sec. = 12:00 (mm:ss)
			# else: e.g. 59:59 - mm:ss
			# do nothing

	return newBlockedUsers, newNexttimestamp

"""
	analize the whole text to get the intro, the headlines and the corresponding bodies
"""
def divideIntoSlices(rawText):
	textLines = rawText.split("\n")
	
	# flow: intro -> head <-> body
	textPart = "intro"
	
	intro = u""
	vmHeads = []
	vmBodies = []
	for line in textLines:
		isHeadline = line.strip().startswith(u"==") and line.strip().endswith(u"==") 
		if isHeadline and textPart == "intro":
			textPart = "head"
			vmHeads.append(line + u"\n")
			vmBodies.append(u"")
		elif not isHeadline and textPart == "intro":
			intro += line + u"\n"
		elif isHeadline and textPart == "head":
			vmHeads.append(line + u"\n")
			vmBodies.append(u"")		# two headlines in sequence
		elif not isHeadline and textPart == "head":
			textPart = "body"
			vmBodies[len(vmHeads) - 1] += line + u"\n"
		elif isHeadline and textPart == "body":
			textPart = "head"
			vmHeads.append(line + u"\n")
			vmBodies.append(u"")
		elif not isHeadline and textPart == "body":
			vmBodies[len(vmHeads) - 1] += line + u"\n"
		else:
			output(u"ERROR! textPart: %s, line.startswith(u'=='): %s, line.endswith(u'=='): %s" % (textPart, line.startswith(u"=="), line.endswith(u"==")))

#	print intro, vmHeads, vmBodies
	return intro, vmHeads, vmBodies

"""
	write a message to WP:VM
		blockedUsers is an array of (blockedusername, byadmin, timestamp, blocklength, reason)
"""
def markBlockedusers(blockedUsers):
	if len(blockedUsers) > 0:
		userOnVMpageFound = False
		editSummary = u""
		oldRawVMText = u""
		try:
			vmPage = pywikibot.Page(pywikibot.getSite(), vmPageName)
			oldRawVMText = vmPage.get()
		except pywikibot.NoPage:
			output(u"could not open or write to WP:VM")
			return
		# read the VM page
		intro, vmHeads, vmBodies = divideIntoSlices(oldRawVMText)

		# add info messages
		for el in blockedUsers:
			blockedusername, byadmin, timestamp, blocklength, reason = el
			output("blocked user: %s blocked by %s, time:%s length:%s, reason:%s" % el)
			# escape chars in the username to make the regex working
			regExUserName = blockedusername
			for regEx in [u'\ ', u'\:', u'\-', u'\!', u'\(', u'\)', u'\?', u'\+', u'\.', u'\%', u'\^', u'\/']:
				regExUserName = pywikibot.replaceExcept(regExUserName, regEx, regEx, [])

			# check if user was reported on VM
			for i in range(0, len(vmHeads)):
#				print "suche: " + regExUserName, "habe: "
#				#output( vmHeads[i])
				#output(vmHeadlineRegEx % regExUserName)
				if isIn(vmHeads[i], vmHeadlineRegEx % regExUserName) and not isIn(vmHeads[i], vmErlRegEx):
					userOnVMpageFound = True
					if isIn(blockedusername, "\d+\.\d+\.\d+\.\d+"):
						editSummary += u", [[Spezial:Beiträge/" + blockedusername + u"|" + blockedusername + u"]]" # ip
					else:
						editSummary += u", [[User:" + blockedusername + u"|" + blockedusername + u"]]" # user
					reasonWithoutPipe = pywikibot.replaceExcept(reason, u"\|", u"{{subst:!}}", [])
					newLine = u"{{subst:Benutzer:Euku/Vorlage:VM-erl|Gemeldeter=%s|Admin=%s|Zeit=%s|Begründung=%s|subst=subst:}}" % (blockedusername, byadmin, blocklength, reasonWithoutPipe)
				

					# change headline and add a line at the end
					vmHeads[i] = pywikibot.replaceExcept(vmHeads[i], vmHeadlineRegEx % regExUserName, u"\\1 (erl.) ==", ['comment', 'nowiki', 'source']) # for the headline
					# add an anchor at the front
					# vmHeads[i] = pywikibot.replaceExcept(newHL, u"^==", u"=={{Anker|Benutzer:" + blockedusername + u"}}", ['comment', 'nowiki', 'source'])
					vmBodies[i] += newLine + u"\n"
		
		# was something changed?
		if userOnVMpageFound:			# new version of VM
			# we count how many sections are still not cleared
			headlinesWithOpenStatus = 0
			oldestHeadlineWithOpenStatus = u""
			for i in range(0, len(vmHeads)):
				# count any user
				if isIn(vmHeads[i], vmHeadlineRegEx % u".+") and not isIn(vmHeads[i], vmErlRegEx):
					headlinesWithOpenStatus += 1
					if oldestHeadlineWithOpenStatus == u"":
						oldestHeadlineWithOpenStatus =  pywikibot.replaceExcept(vmHeads[i], u"(?:==\ *|\ *==)", u"", ['comment', 'nowiki', 'source'])

			if oldestHeadlineWithOpenStatus != u"":
				oldestHeadlineWithOpenStatus = u", der älteste zu " + oldestHeadlineWithOpenStatus

			openSections = u""
			if (headlinesWithOpenStatus == 1):
				openSections = u"; 1 Abschnitt scheint noch offen zu sein"
			elif (headlinesWithOpenStatus > 1):
				openSections = (u"; %s Abschnitte scheinen noch offen zu sein" % headlinesWithOpenStatus)
			#print u"Offene Überschriften", headlinesWithOpenStatus, openSections, oldestHeadlineWithOpenStatus

			newRawText = intro
			for i in range(0, len(vmHeads)):
				newRawText += vmHeads[i] + vmBodies[i]

			# compare them
			pywikibot.showDiff(oldRawVMText, newRawText)
			editSummary = editSummary[2:] # remove ", " at the begining
			output(u"markiere: " + editSummary)
			vmPage.put(newRawText, u"Abschnitt(e) erledigt: " + editSummary + openSections + oldestHeadlineWithOpenStatus, False, minorEdit=True, force=True)
		else:
			output(u"auf VM ist nichts zu tun")

"""
	is this user experienced?
	user is experienced iff edits >= 50
"""
def userIsExperienced(username):
	# load user contribs from API
	req = api.Request(site=mysite, action="query")
	req['list'] = 'usercontribs'
	req['ucuser'] = username
	req['ucprop'] = '' # doesn't matter in detail, but the default setting are too much
	req['uclimit'] = 50
	data = req.submit()
        results = []
        try:
		#print data['query']['usercontribs']
        	return len(data['query']['usercontribs']) >= 50
        except:
        	return False

"""
	returns a username and a timestamp
"""
def getAccuser(rawText):
	sigRegEx =  u"\[\[(?:[Bb]enutzer(?:[ _]Diskussion)?\:|[Uu]ser(?:[ _]talk)?\:|Spezial\:Beiträge\/|Special:Contributions\/)(?P<username>[^|\]]+)\|.*?\]\].{1,30}"
	sigRegEx += u"(?P<hh>[0-9]{2})\:(?P<mm>[0-9]{2}),\ (?P<dd>[0-9]{1,2})\.?\ (?P<MM>[a-zA-Zä]{3,10})\.?\ (?P<yyyy>[0-9]{4})\ \((?:CE[S]?T|ME[S]?Z|UTC)\)"
	p1 = re.compile(sigRegEx, re.UNICODE)
	matches1 = p1.finditer(rawText)
	for match1 in matches1:
#		print "match", match1.group()
		username = match1.group('username')
		hh1 = match1.group('hh')
		mm1 = match1.group('mm')
		dd1 = match1.group('dd')
		MM1 = match1.group('MM')
		yy1 = match1.group('yyyy')
		return username, yy1 + u" " + MM1 + u" " + dd1 + u" " + hh1 + u":" + mm1 # we assume: the first timestamp was made by the accuser
	return u'', u''

"""
	read opt-in list
"""
def optOutUsersToCheck(pageName):
	result = []
	try:
		optOutPage = pywikibot.Page(pywikibot.getSite(), pageName)
		optOutRawText = optOutPage.get()

		p = re.compile(wpOptOutListRegEx, re.UNICODE)
		userIterator = p.finditer(optOutRawText)
		for user in userIterator:
			# "_" is the same as " " for Wikipedia URls
			result.append(pywikibot.replaceExcept(user.group('username'), u"_", u" ", []))
	except:
		output("Exception in optOutUsersToCheck()")
	return result

"""
	http://de.pywikibot.org/w/index.php?title=Benutzer_Diskussion:Euku&oldid=85204681#Kann_SpBot_die_auf_VM_gemeldeten_Benutzer_benachrichtigen.3F
	bootmode: mo messages are written on the first run, just 'alreadySeenReceiver' is filled with the current defendants. Otherwise the bot will always write a messge at startup
"""
def contactDefendants(alreadySeenReceiver, bootmode=False):
	try:
		vmPage = pywikibot.Page(pywikibot.getSite(), vmPageName)
		rawVMText = vmPage.get()
	except pywikibot.NoPage:
		output(u"could not open or write to WP:VM")
		return
	# read the VM page
	intro, vmHeads, vmBodies = divideIntoSlices(rawVMText)
	#print vmHeads
	for i in range(0, len(vmHeads)):
		# there are several thing to check...
		# is this a user account or a article?
		defendant = search(vmHeads[i], vmHeadlineUserRegEx)
		if (len(defendant) == 0):
			continue
		# convert the first letter to upper case
		defendant = defendant[0].upper() + defendant[1:]
		# is this one an IP address?
		if (isIn(vmHeads[i], r'(?:1?\d?\d|2[0-5]\d)\.(?:1?\d?\d|2[0-5]\d)\.(?:1?\d?\d|2[0-5]\d)\.(?:1?\d?\d|2[0-5]\d)')):
			continue
		# already cleared headline?
		if (isIn(vmHeads[i], vmErlRegEx)):
			continue
		# check if this user has opted out
		if defendant in optOutListReceiver:
			#print defendant, " ist in der Opt-out-Liste... nächster"
			continue

		# get timestamp and accuser
		accuser, timestamp = getAccuser(vmBodies[i])
		print u"\ndefendant:", defendant, u"accuser:", accuser, u"time:", timestamp
		if accuser == u"":
			output(u"Melder nicht gefunden bei %s, weiter..." % defendant)
			continue
		# TEST:
		#defendant = u"Euku"
		#accuser = u"Euku"
		#alreadySeenReceiver = [] # hack

		# is this an old section? maybe the user already got a message
		if (defendant, timestamp) in alreadySeenReceiver:
			#print u"schon gesehen"
			continue

		# check if the accuser has opted-out
		if accuser in optOutListAccuserName:
			output(u"%s will seber benachrichtigen (Opt-out), weiter..." % accuser)
			alreadySeenReceiver.append((defendant, timestamp))
			continue
		
		# check if the user has enough edits?
		if not userIsExperienced(defendant):
			#print defendant, " ist ein n00b... nächster"
			alreadySeenReceiver.append((defendant, timestamp))
			continue
		output(u"Gemeldeten zum Anschreiben gefunden: " + defendant)

		# write a message to the talk page
		if bootmode:
			output(u"überspringe das Anschreiben, weil es der erste Lauf ist")
			alreadySeenReceiver.append((defendant, timestamp))
			continue

		userTalk = pywikibot.Page(pywikibot.getSite(), "User talk:" + defendant)
		userTalkRawText = userTalk.get()
		sectionHeadClear = pywikibot.replaceExcept(vmHeads[i], u"==+\ *\[?\[?", u"", [])
		sectionHeadClear = pywikibot.replaceExcept(sectionHeadClear, u"\]\].*", u"", []).strip()

		# memo that this user has already been contacted
		alreadySeenReceiver.append((defendant, timestamp))
		if len(alreadySeenReceiver) > 50:
			# clean up the list
			alreadySeenReceiver = alreadySeenReceiver[49:]

		# is the accuser an IP?
		if (isIn(accuser, r'(?:1?\d?\d|2[0-5]\d)\.(?:1?\d?\d|2[0-5]\d)\.(?:1?\d?\d|2[0-5]\d)\.(?:1?\d?\d|2[0-5]\d)')):
			accuserLink = u"Spezial:Beiträge/" + accuser + u"{{subst:!}}" + accuser
		else:
			accuserLink = u"Benutzer:" + accuser + u"{{subst:!}}" + accuser
		# save WP talk page
		addText = u"\n{{subst:%s|Melder=%s|Abschnitt=%s}}" % (vmMessageTemplate, accuserLink, sectionHeadClear)
		newUserTalkRawText = userTalkRawText + addText
		output(u"schreibe: " + addText)
		pywikibot.showDiff(userTalkRawText, newUserTalkRawText)
		userTalk.put(newUserTalkRawText, u"Benachrichtigung zu [[WP:VM#" + sectionHeadClear + u"]]", False, minorEdit=False, force=False, botflag=True)


"""
  MAIN
"""
# read arguments
for arg in pywikibot.handleArgs():
	if arg == '-force':
	    forceWrite = True
	else:
	    output(arg + u" wurde ignoriert")

# start...
output(strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############",localtime()))
mysite = pywikibot.Site()  # ohne Parameter, falls de-wiki default-Einstellung ist
mysite.login()

nexttimestamp = "20130522123456"
optOutListReceiver = optOutUsersToCheck(optOutListReceiverName)
optOutListAccuser = optOutUsersToCheck(optOutListAccuserName)
optOutListAge = 0
alreadySeenReceiver = []
#print u"Opt-outs:", optOutListAccuser, optOutListReceiver
contactDefendants(alreadySeenReceiver, bootmode=True)

while True:
	# check logs
	output(strftime(">> %H:%M:%S: ", localtime()))
	try:
		blockedUsers, nexttimestamp = loadBlockedUsers(nexttimestamp)
#		blockedUsers, nexttimestamp = [(u"217.116.23.132", u"Blunt.", u"20091115124936", u"unbeschränkt", u"Nutzung eines [[Proxy (Rechnernetz)|offenen Proxys]]: Schreibrecht gemäß [[m:No open proxies/de|offizieller Richtlinie]] entzogen")], 2 ############## testing
#		#print u"next: " + nexttimestamp, u"blocked:", blockedUsers
		markBlockedusers(blockedUsers)
		#print alreadySeenReceiver
		contactDefendants(alreadySeenReceiver)
	except urllib2.HTTPError:
		output(u"urllib2.HTTPError")
	except pywikibot.exceptions.EditConflict:
		continue # try again and skip waittime
	except pywikibot.exceptions.PageNotSaved:
		continue # try again and skip waittime
	except: #AssertionError:
		output(u"something unexpeted happend, trace:")
		import traceback
		traceback.print_exc()

	time.sleep(waittime)
	optOutListAge += waittime
	if (optOutListAge > optOutMaxAge):
		output(u"Maximalalter der Opt-Out-Listen erreicht, hole neue")
		optOutListAge = 0
		optOutListReceiver = optOutUsersToCheck(optOutListReceiverName)
		optOutListAccuser = optOutUsersToCheck(optOutListAccuserName)
		#print u"Opt-outs:", optOutListAccuser, optOutListReceiver
		output(u"otpout-Liste hat optOutListReceiver: %s, optOutListAccuser: %s" % (optOutListReceiver, optOutListAccuser))
		if (len(optOutListReceiver) == 0):
			optOutListAge = 9999999


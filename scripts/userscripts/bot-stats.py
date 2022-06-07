#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys              # To not have wikipedia and this in one dir we'll import sys
import re               # Used for regular expressions
import pywikibot        # pywikibot framework
import operator
import pywikibot.exceptions
from pywikibot.data import api
from pywikibot import textlib
from datetime import datetime, date, timedelta
from time import localtime, strftime, mktime    # strftime-Function and related
import dateutil.parser
import time

botStatusInactiveThreshold = 3*356/12
mysite = pywikibot.Site()  # ohne Parameter, falls de-wiki default-Einstellung ist

formerBotNames = ["ArchivBot", "LinkFA-Bot", "RevoBot", "MerlBot", "KLBot2", "Luckas-bot", "Sebbot", "Beitragszahlen", "CopperBot", "ZéroBot", "TXiKiBoT", "Thijs!bot", "MerlIwBot"]

userDic = {}
userDic["AkaBot"] = "2004-11-30"
userDic["ApeBot"] = "2003-07-30"
userDic["BWBot"] = "2004-08-10"
userDic["Bota47"] = "2005-07-19"
userDic["Botteler"] = "2004-08-23"
userDic["Chlewbot"] = "2005-11-30"
userDic["Chobot"] = "2005-06-18"
userDic["ConBot"] = "2004-10-26"
userDic["FlaBot"] = "2004-11-21"
userDic["GeoBot"] = "2005-07-15"
userDic["Gpvosbot"] = "2005-06-11"
userDic["KocjoBot"] = "2005-10-08"
userDic["LeonardoRob0t"] = "2004-11-30"
userDic["MelancholieBot"] = "2005-09-22"
userDic["PortalBot"] = "2005-11-01"
userDic["PyBot"] = "2003-05-28"
userDic["RKBot"] = "2005-04-10"
userDic["RedBot"] = "2005-01-21"
userDic["Robbot"] = "2003-10-11"
userDic["RobotE"] = "2005-05-20"
userDic["RobotQuistnix"] = "2005-07-17"
userDic["Sk-Bot"] = "2004-10-20"
userDic["SpBot"] = "2005-10-06"
userDic["Tasca.bot"] = "2005-07-30"
userDic["Tsca.bot"] = "2005-07-30"
userDic["YurikBot"] = "2005-07-31"
userDic["Zwobot"] = "2003-12-02"

def queryLastEdit(username):
	# load user contribs from API
        req = api.Request(site=mysite, action="query")
        req['list'] = 'usercontribs'
        req['ucuser'] = username
        req['ucdir'] = 'older'
        req['uclimit'] = 1
        req['rawcontinue'] = ''
        data = req.submit()
        try:
            for x in data['query']['usercontribs']:
               return x['timestamp'] # last edit
        except:
            return None 

if __name__ == "__main__":
    formerBotList = []
    req1 = api.Request(site=mysite, action="query")
    req1['list'] = 'users'
    req1['ususers'] = "|".join(str(x) for x in formerBotNames)
    req1['usprop'] = 'editcount|registration'
    data1 = req1.submit()

    botList = []
    req2 = api.Request(site=mysite, action="query")
    req2['list'] = 'allusers'
    req2['augroup'] = 'bot'
    req2['aulimit'] = 'max'
    req2['auprop'] = 'editcount|registration'
    data2 = req2.submit()
    for x in data1['query']['users'] + data2['query']['allusers']:
        p1 = re.compile(r'(?P<date>\d\d\d\d\-\d\d\-\d\d).+', re.UNICODE)
        matches1 = p1.finditer(x['registration'])
        reg = "?"
        for match1 in matches1:
            reg = match1.group('date')
        if reg == "?" or reg == datetime.today().strftime("%Y-%m-%d"):
            if x['name'] in userDic:
               reg = userDic[x['name']] + "*"
            else:
               reg = "?"
        botList.append((textlib.replaceExcept(x['name'], "&amp;", "&", []), x['editcount'], reg))
    
    botList = reversed(sorted(botList, key=operator.itemgetter(1)))
    pageText = '{{Benutzer:Euku/B:Navigation}}\n\
<div style="margin:0; margin-bottom:10px; border:1px solid #dfdfdf; padding:0 1em 1em 1em; background-color:#F8F8FF; -moz-border-radius-bottomleft:1em; -moz-border-radius-bottomright:1em;">\
Aufgeführt sind alle Bots die einen Bot-Flag besitzen. Stand: ~~~~~<br />Ein Bot gilt als inaktiv, wenn er in den letzten drei Monaten keinen Beitrag geleistet hat.\n\n\
[//de.wikipedia.org/w/index.php?title=Benutzer:Euku/Botstatistik&diff=curr&oldid=prev&diffonly=1 &Auml;nderungen der letzten Woche]\n\
{|class="sortable wikitable"\n\
! #\n! Botname\n!Beiträge\n! Gesamtbearbeitungen\n! Letzte Bearbeitung\n! Anmeldedatum\n'
    counter = 0
    allEdits = 0
    now = datetime.now()
    for bot in botList:
        counter += 1
        botName, botEditCounter, botCreationDate = bot
        allEdits += botEditCounter
        remark = ""
        lastEditRes = queryLastEdit(botName)
        if (lastEditRes != None):
            lastEdit = dateutil.parser.parse(lastEditRes).replace(tzinfo=None)
            if botName in formerBotNames:
                remark = "(ehemalig)"
            elif (now - lastEdit).days > 3*30:
                remark = "(inaktiv)"
            pageText += "|-\n|%s||[[Benutzer:%s|%s]] %s||[[Spezial:Beiträge/%s|B]]||%s||%s||%s\n" % (counter, botName, botName, remark, botName, botEditCounter, lastEdit.strftime("%Y-%m-%d"), botCreationDate)
        else:
            if botName in formerBotNames:
                remark = "(ehemalig)"
            pageText += "|-\n|%s||[[Benutzer:%s|%s]] %s||[[Spezial:Beiträge/%s|B]]||%s||-||%s\n" % (counter, botName, botName, remark, botName, botEditCounter, botCreationDate)
    
    pageText += "|}\nGesamtbearbeitungen durch diese Bots: %s ([[Benutzer_Diskussion:Euku/Botstatistik#Bots_ohne_einen_Edit_mit_einem_letzten_Edit|eine Schätzung]])<br />\n<nowiki>*</nowiki> = Datum der ersten Bearbeitung<br/>\nehemalig = das Benutzterkonto besitzt kein Botflag mehr" % "{:,}".format(allEdits).replace(',', '.')
    
    # print pageText use pywikibot.out
    # save it
    pywikibot.output("Speichere...")
    pageOp = pywikibot.Page(pywikibot.Site(), "Benutzer:Euku/Botstatistik")
    pywikibot.output(pageText)
    pageOp.put(pageText, "Update")

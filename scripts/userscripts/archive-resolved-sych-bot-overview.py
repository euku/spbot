#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
This script will sychronize a commons page to all existing bot pages there the archiving bot is used.
"""
import sys
assert sys.version_info >= (3,5)
import pywikibot        # Wikipedia-pybot-framework
from time import sleep
from archive_resolved_localization.local_bot import LocalBot

basePageToCopy = ('commons', 'User:SpBot/Archivebot')
targetProjects = ['dewikipedia', 'cswikipedia', 'jawikipedia', 'kowikipedia', 'viwikipedia',
                  'dewiktionary',
                  'dewikisource',
                  'enwikisource',
                  'dewikiversity',
                  'meta', 'wikidata', 'wikimania', 'species', 'wikifunctions']

def getSourcePage():
    projectCode, projectFamily = LocalBot.splitInCodeAndFamily(basePageToCopy[0])
    site = pywikibot.Site(code=projectCode, fam=projectFamily)
    return pywikibot.Page(site, basePageToCopy[1]).text

def updatePageInLocalWiki(targetProjectId: str, newPageText: str):
    projectCode, projectFamily = LocalBot.splitInCodeAndFamily(targetProjectId)
    site = pywikibot.Site(code=projectCode, fam=projectFamily)
    pywikibot.output(f'Looking at {site}')

    pageName = basePageToCopy[1]
    page = pywikibot.Page(site, pageName)
    originalText = page.text
    page.text = newPageText

    pywikibot.output(f"Diff of {targetProjectId}:[[{pageName}]]:")
    pywikibot.output("#"*80)
    pywikibot.showDiff(originalText, newPageText)
    pywikibot.output("#"*80)

    if originalText != newPageText:
        page.save('Updating the page', minor=True, force=True)

if __name__ == "__main__":
    try:
        baseText = getSourcePage()
        # pywikibot.output(f'got base text:\n{baseText}')

        for targetProjectId in targetProjects:
            updatePageInLocalWiki(targetProjectId, baseText)
        
    finally:
        pywikibot.stopme()

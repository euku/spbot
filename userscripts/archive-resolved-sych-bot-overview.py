#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
This script will sychronize a commons page to all existing bot pages there the archiving bot is used.

-dryrun           Only show the differences, do not save anything
-simulate         (pywikibot) the same
"""
import sys
assert sys.version_info >= (3,12)
import traceback
import pywikibot        # Wikipedia-pybot-framework
from archive_resolved_localization.local_bot import LocalBot

basePageToCopy = ('commons', 'User:SpBot/Archivebot')
targetProjects = ['dewikipedia', 'cswikipedia', 'itwikipedia', 'jawikipedia', 'kowikipedia', 'viwikipedia',
                  'dewiktionary',
                  'dewikisource',
                  'enwikisource',
                  'dewikiversity',
                  'meta', 'wikidata', 'wikimania', 'species', 'wikifunctions', 'incubator']

def getSourcePage():
    projectCode, projectFamily = LocalBot.splitInCodeAndFamily(basePageToCopy[0])
    site = pywikibot.Site(code=projectCode, fam=projectFamily)
    # get() instead of .text: a missing page must not empty all copies
    return pywikibot.Page(site, basePageToCopy[1]).get()

def updatePageInLocalWiki(targetProjectId: str, newPageText: str, dryRun: bool):
    projectCode, projectFamily = LocalBot.splitInCodeAndFamily(targetProjectId)
    site = pywikibot.Site(code=projectCode, fam=projectFamily)
    pywikibot.output(f'Looking at {site}')

    pageName = basePageToCopy[1]
    page = pywikibot.Page(site, pageName)
    originalText = page.text
    if originalText == newPageText:
        return
    page.text = newPageText

    pywikibot.output(f"Diff of {targetProjectId}:[[{pageName}]]:")
    pywikibot.output("#"*80)
    pywikibot.showDiff(originalText, newPageText)
    pywikibot.output("#"*80)

    if dryRun:
        pywikibot.output('Dry run: not saved')
    else:
        page.save('Updating the page', minor=True, force=True)

def main() -> int:
    """Returns the exit code: 1 if a project failed, 2 for an unknown argument."""
    dryRun = False
    for arg in pywikibot.handle_args():
        if arg == '-dryrun':
            dryRun = True
        else:
            # may be a misspelled -dryrun
            pywikibot.error(f'unknown argument {arg}, nothing done')
            return 2
    failed = []
    try:
        baseText = getSourcePage()
        for targetProjectId in targetProjects:
            try:
                updatePageInLocalWiki(targetProjectId, baseText, dryRun)
            except Exception:
                failed.append(targetProjectId)
                pywikibot.error(f'{targetProjectId} failed, going on: {traceback.format_exc()}')
    finally:
        pywikibot.stopme()
    if failed:
        pywikibot.error('Failed: ' + ', '.join(failed))
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())

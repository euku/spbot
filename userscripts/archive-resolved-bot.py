#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
These command line parameters can be used to specify how to work:

&params;

-dryrun        Pages and log files will not be saved on Wikipedia.
                  The bot just simulates the run and saves local log files under ./logs/

-page             Works on a specified page. Otherwise it runs
                  over all pages that use 'archiveTemplateName' (Vorlage:Autoarchiv-Erledigt)

-nosummary        Do not write logs/archive-resolved-<project>.jsonl (the run summary
                  for the status web page; only written for runs without -page)

-project        'nothing': de.wikipedia
                commons, wikidata, species, dewikisource, {de,en}wiktionary: and other projects...

authors:
    until Nov. 2007: Rhododendronbusch
    after Nov. 2007: Euku
"""
import sys
assert sys.version_info >= (3,7)
# The code lives in the package archive_resolved (next to this file) so it can be tested.
from archive_resolved.bot import main

if __name__ == "__main__":
    main()

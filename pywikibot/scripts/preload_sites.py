#!/usr/bin/env python3
"""Script that preloads site and user info for all sites of given family.

The following parameters are supported:

-worker:<num>     The number of parallel tasks to be run. Default is the
                  number of processors on the machine

Usage::

    python pwb.py preload_sites [{<family>}] [-worker:{<num>}]

To force preloading, change the global expiry value to 0::

    python pwb.py -API_config_expiry:0 preload_sites [{<family>}]

.. versionchanged:: 7.4
   script was moved to the framework scripts folder.
"""
#
# (C) Pywikibot team, 2021-2023
#
# Distributed under the terms of the MIT license.
#
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
from typing import Optional, Union

import pywikibot
from pywikibot.backports import Dict, List, Set, removeprefix
from pywikibot.family import Family


try:  # Python 3.13
    from os import process_cpu_count  # type: ignore[attr-defined]
except ImportError:
    from os import cpu_count as process_cpu_count


#: supported families by this script
families_list = [
    'wikibooks',
    'wikinews',
    'wikipedia',
    'wikiquote',
    'wikisource',
    'wikiversity',
    'wikivoyage',
    'wiktionary',
]

# Ignore sites from preloading
# example: {'wikiversity': ['beta'], }
exceptions: Dict[str, List[str]] = {
}


def preload_family(family: str, executor: ThreadPoolExecutor) -> None:
    """Preload all sites of a single family file."""
    msg = 'Preloading sites of {} family{}'
    pywikibot.info(msg.format(family, '...'))

    codes = Family.load(family).languages_by_size
    for code in exceptions.get(family, []):
        if code in codes:
            codes.remove(code)
    obsolete = Family.load(family).obsolete

    futures = set()
    for code in codes:
        if code not in obsolete:
            site = pywikibot.Site(code, family)
            # page title does not care
            futures.add(executor.submit(pywikibot.Page, site, 'Main page'))
    wait(futures)
    pywikibot.info(msg.format(family, ' completed.'))


def preload_families(families: Union[List[str], Set[str]],
                     worker: Optional[int]) -> None:
    """Preload all sites of all given family files.

    .. versionchanged:: 7.3
       Default of worker is calculated like for Python 3.8 but preserves
       at least one worker for each element in families_list for better
       performance.
    """
    start = datetime.now()
    if worker is None:
        # Python 3.13 default
        worker = min(32, (process_cpu_count() or 1) + 4)
    # to allow adding futures in preload_family the workers must be one
    # more than families are handled
    worker = max(len(families) * 2, worker)
    pywikibot.info(
        f'Using {worker} workers to process {len(families)} families')
    with ThreadPoolExecutor(worker) as executor:
        futures = {executor.submit(preload_family, family, executor)
                   for family in families}
        wait(futures)
    pywikibot.info(f'Loading time used: {datetime.now() - start}')


if __name__ == '__main__':
    fam = set()
    worker = None
    for arg in pywikibot.handle_args():
        if arg in families_list:
            fam.add(arg)
        elif arg.startswith('-worker:'):
            worker = int(removeprefix(arg, '-worker:'))
    preload_families(fam or families_list, worker)

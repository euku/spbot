"""Family module for Wikimedia chapter, thematic organisation and WUG wikis."""
#
# (C) Pywikibot team, 2012-2023
#
# Distributed under the terms of the MIT license.
#
from pywikibot import family


class Family(family.SubdomainFamily, family.WikimediaFamily):

    """Family class for WCH, WTO and WUG wikis hosted on wikimedia.org."""

    name = 'wikimediachapter'
    code_aliases = {
        'et': 'ee'
    }

    closed_wikis = ['cn', 'nz', 'pa-us', ]

    codes = [
        'am', 'ar', 'az', 'bd', 'be', 'br', 'ca', 'co', 'dk', 'ec', 'ee', 'fi',
        'ge', 'gr', 'hi', 'id', 'id-internal', 'il', 'mai', 'mk', 'mx', 'ng',
        'nl', 'no', 'nyc', 'pl', 'pt', 'punjabi', 'romd', 'rs', 'ru', 'se',
        'tr', 'ua', 'uk', 've', 'wb',
    ]

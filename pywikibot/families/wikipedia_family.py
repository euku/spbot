"""Family module for Wikipedia."""
#
# (C) Pywikibot team, 2004-2023
#
# Distributed under the terms of the MIT license.
#
from pywikibot import family


# The Wikimedia family that is known as Wikipedia, the Free Encyclopedia
class Family(family.SubdomainFamily, family.WikimediaFamily):

    """Family module for Wikipedia."""

    name = 'wikipedia'

    closed_wikis = [
        # https://noc.wikimedia.org/conf/highlight.php?file=dblists/closed.dblist
        'aa', 'ak', 'cho', 'ho', 'hz', 'ii', 'kj', 'kr', 'lrc', 'mh', 'mus',
        'na', 'ng', 'ten',
    ]

    removed_wikis = [
        # https://noc.wikimedia.org/conf/highlight.php?file=dblists/deleted.dblist
        'dk', 'mo', 'ru-sib', 'tlh', 'tokipona', 'zh_cn', 'zh_tw',
    ]

    languages_by_size = [
        'en', 'ceb', 'de', 'sv', 'fr', 'nl', 'ru', 'es', 'it', 'arz', 'pl',
        'ja', 'zh', 'vi', 'uk', 'war', 'ar', 'pt', 'fa', 'ca', 'sr', 'id',
        'ko', 'no', 'ce', 'fi', 'cs', 'tr', 'hu', 'tt', 'sh', 'ro',
        'zh-min-nan', 'eu', 'ms', 'eo', 'he', 'hy', 'da', 'bg', 'cy', 'sk',
        'azb', 'uz', 'et', 'simple', 'kk', 'be', 'min', 'el', 'hr', 'lt', 'gl',
        'az', 'ur', 'sl', 'lld', 'ka', 'nn', 'hi', 'th', 'ta', 'bn', 'la',
        'mk', 'zh-yue', 'ast', 'lv', 'tg', 'af', 'my', 'mg', 'mr', 'sq', 'bs',
        'oc', 'te', 'nds', 'ml', 'be-tarask', 'br', 'ky', 'sw', 'jv', 'new',
        'lmo', 'pnb', 'vec', 'ht', 'pms', 'ba', 'lb', 'su', 'ku', 'ga', 'szl',
        'is', 'fy', 'cv', 'ckb', 'pa', 'tl', 'an', 'wuu', 'diq', 'io', 'sco',
        'vo', 'yo', 'ne', 'ia', 'gu', 'kn', 'als', 'ha', 'avk', 'bar', 'scn',
        'crh', 'bpy', 'qu', 'nv', 'mn', 'xmf', 'ban', 'si', 'tum', 'ps', 'frr',
        'os', 'bat-smg', 'or', 'sah', 'ig', 'mzn', 'cdo', 'gd', 'bug', 'yi',
        'sd', 'ilo', 'am', 'nap', 'li', 'bcl', 'fo', 'gor', 'hsb', 'map-bms',
        'mai', 'shn', 'eml', 'ace', 'zh-classical', 'sa', 'as', 'wa', 'ie',
        'lij', 'hyw', 'mhr', 'zu', 'sn', 'hif', 'mrj', 'bjn', 'mni', 'km',
        'hak', 'roa-tara', 'pam', 'rue', 'sat', 'nso', 'bh', 'so', 'se', 'mi',
        'myv', 'vls', 'nds-nl', 'sc', 'dag', 'kw', 'bo', 'vep', 'co', 'ary',
        'glk', 'tk', 'kab', 'gan', 'rw', 'fiu-vro', 'ab', 'gv', 'ug', 'nah',
        'zea', 'skr', 'frp', 'udm', 'pcd', 'kv', 'mt', 'csb', 'gn', 'smn',
        'ay', 'nrm', 'ks', 'lez', 'lfn', 'olo', 'mwl', 'stq', 'lo', 'ang',
        'fur', 'rm', 'mdf', 'lad', 'gom', 'ext', 'kaa', 'tyv', 'koi', 'av',
        'pap', 'dsb', 'ln', 'dty', 'tw', 'cbk-zam', 'dv', 'ksh', 'za', 'gag',
        'bxr', 'pfl', 'lg', 'szy', 'pag', 'blk', 'pi', 'tay', 'haw', 'awa',
        'inh', 'krc', 'xal', 'pdc', 'to', 'atj', 'tcy', 'arc', 'mnw', 'jam',
        'kbp', 'wo', 'kbd', 'anp', 'nia', 'nov', 'shi', 'ki', 'nqo', 'bi',
        'om', 'tpi', 'xh', 'tet', 'roa-rup', 'jbo', 'fj', 'lbe', 'kg', 'ff',
        'ty', 'guw', 'cu', 'trv', 'ami', 'srn', 'sm', 'mad', 'alt', 'gcr',
        'ltg', 'chr', 'tn', 'ny', 'st', 'pih', 'rmy', 'got', 'ee', 'pcm', 'bm',
        'ss', 'gpe', 've', 'ts', 'chy', 'kcg', 'rn', 'gur', 'ch', 'ik', 'ady',
        'fat', 'pnt', 'guc', 'iu', 'pwn', 'sg', 'din', 'ti', 'kl', 'dz', 'cr',
    ]

    # Sites we want to edit but not count as real languages
    test_codes = ['test', 'test2']

    # Templates that indicate a category redirect
    # Redirects to these templates are automatically included
    category_redirect_templates = {
        '_default': (),
        'ar': ('تحويل تصنيف',),
        'ary': ('Category redirect',),
        'arz': ('تحويل تصنيف',),
        'bn': ('বিষয়শ্রেণী পুনর্নির্দেশ',),
        'bs': ('Category redirect',),
        'cs': ('Zastaralá kategorie',),
        'da': ('Kategoriomdirigering',),
        'en': ('Category redirect',),
        'es': ('Categoría redirigida',),
        'eu': ('Kategoria birzuzendu',),
        'fa': ('رده بهتر',),
        'fr': ('Catégorie redirigée',),
        'gv': ('Aastiurey ronney',),
        'hi': ('श्रेणी अनुप्रेषित',),
        'hu': ('Kat-redir',),
        'id': ('Alih kategori',),
        'ja': ('Category redirect',),
        'ko': ('분류 넘겨주기',),
        'mk': ('Премести категорија',),
        'ml': ('Category redirect',),
        'ms': ('Pengalihan kategori',),
        'mt': ('Rindirizzament kategorija',),
        'ne': ('श्रेणी अनुप्रेषण',),
        'no': ('Kategoriomdirigering',),
        'pt': ('Redirecionamento de categoria',),
        'ro': ('Redirect categorie',),
        'ru': ('Переименованная категория',),
        'sco': ('Category redirect',),
        'sh': ('Prekat',),
        'simple': ('Category redirect',),
        'sl': ('Preusmeritev kategorije',),
        'sr': ('Category redirect',),
        'sq': ('Kategori e zhvendosur',),
        'sv': ('Kategoriomdirigering',),
        'tl': ('Category redirect',),
        'tr': ('Kategori yönlendirme',),
        'uk': ('Categoryredirect',),
        'ur': ('زمرہ رجوع مکرر',),
        'vi': ('Đổi hướng thể loại',),
        'yi': ('קאטעגאריע אריבערפירן',),
        'zh': ('分类重定向',),
        'zh-yue': ('分類彈去',),
    }

    # Global bot allowed languages on
    # https://meta.wikimedia.org/wiki/BPI#Current_implementation
    # & https://meta.wikimedia.org/wiki/Special:WikiSets/2
    cross_allowed = [
        'ab', 'ace', 'ady', 'af', 'als', 'am', 'an', 'ang', 'ar', 'arc', 'arz',
        'as', 'ast', 'atj', 'av', 'ay', 'az', 'ba', 'bar', 'bat-smg', 'bcl',
        'be', 'be-tarask', 'bg', 'bh', 'bi', 'bjn', 'bm', 'bo', 'bpy', 'bug',
        'bxr', 'ca', 'cbk-zam', 'cdo', 'ce', 'ceb', 'ch', 'chr', 'chy', 'ckb',
        'co', 'cr', 'crh', 'cs', 'csb', 'cu', 'cv', 'cy', 'da', 'diq', 'dsb',
        'dty', 'dz', 'ee', 'el', 'eml', 'en', 'eo', 'et', 'eu', 'ext', 'fa',
        'ff', 'fi', 'fj', 'fo', 'frp', 'frr', 'fur', 'ga', 'gag', 'gan', 'gd',
        'glk', 'gn', 'gom', 'gor', 'got', 'gu', 'gv', 'ha', 'hak', 'haw', 'he',
        'hi', 'hif', 'hr', 'hsb', 'ht', 'hu', 'hy', 'ia', 'ie', 'ig', 'ik',
        'ilo', 'inh', 'io', 'iu', 'ja', 'jam', 'jbo', 'jv', 'ka', 'kaa', 'kab',
        'kbd', 'kg', 'ki', 'kk', 'kl', 'km', 'kn', 'ko', 'koi', 'krc', 'ks',
        'ku', 'kv', 'kw', 'ky', 'la', 'lad', 'lb', 'lbe', 'lez', 'lfn', 'lg',
        'li', 'lij', 'lmo', 'ln', 'lo', 'lt', 'ltg', 'lv', 'map-bms', 'mdf',
        'meta', 'mg', 'mhr', 'mi', 'mk', 'ml', 'mn', 'mrj', 'ms', 'mwl', 'my',
        'myv', 'mzn', 'nah', 'nap', 'nds-nl', 'ne', 'new', 'nl', 'no', 'nov',
        'nrm', 'nso', 'nv', 'ny', 'oc', 'olo', 'om', 'or', 'os', 'pa', 'pag',
        'pam', 'pap', 'pdc', 'pfl', 'pi', 'pih', 'pms', 'pnb', 'pnt', 'ps',
        'qu', 'rm', 'rmy', 'rn', 'roa-rup', 'roa-tara', 'ru', 'rue', 'rw',
        'sa', 'sah', 'sc', 'scn', 'sco', 'sd', 'se', 'sg', 'sh', 'shn', 'si',
        'simple', 'sk', 'sm', 'sn', 'so', 'srn', 'ss', 'st', 'stq', 'su', 'sv',
        'sw', 'szl', 'ta', 'tcy', 'te', 'tet', 'tg', 'th', 'ti', 'tk', 'tl',
        'tn', 'to', 'tpi', 'tr', 'ts', 'tt', 'tum', 'tw', 'ty', 'tyv', 'udm',
        'ug', 'uz', 've', 'vec', 'vep', 'vls', 'vo', 'wa', 'war', 'wo', 'xal',
        'xh', 'xmf', 'yi', 'yo', 'za', 'zea', 'zh', 'zh-classical',
        'zh-min-nan', 'zh-yue', 'zu',
    ]

    # Languages that used to be coded in iso-8859-1
    latin1old = {
        'af', 'bs', 'co', 'cs', 'da', 'de', 'en', 'es', 'et', 'eu', 'fi', 'fr',
        'fy', 'ga', 'gl', 'ia', 'id', 'it', 'la', 'lt', 'lv', 'mi', 'mr', 'na',
        'nds', 'nl', 'no', 'pt', 'simple', 'sl', 'sv', 'sw', 'test', 'tt',
        'uk', 'vi', 'vo'
    }

    # Subpages for documentation.
    # TODO: List is incomplete, to be completed for missing languages.
    # TODO: Remove comments for appropriate pages
    doc_subpages = {
        '_default': (('/doc', ),
                     ['arz', 'bn', 'cs', 'da', 'en', 'es', 'hr', 'hu', 'id',
                      'ilo', 'ja', 'ms', 'pt', 'ro', 'ru', 'simple', 'sh',
                      'vi', 'zh']
                     ),
        'ar': ('/شرح', '/doc', ),
        'ary': ('/توثيق', '/شرح', '/doc', ),
        'bs': ('/dok', ),
        'ca': ('/ús', ),
        'de': ('Doku', '/Meta'),
        'dsb': ('/Dokumentacija', ),
        'eu': ('txantiloi dokumentazioa', '/dok'),
        'fa': ('/doc', '/توضیحات'),
        # fi: no idea how to handle this type of subpage at :Metasivu:
        'fi': ((), ),
        'fr': ('/Documentation',),
        'hsb': ('/Dokumentacija', ),
        'it': ('/Man', ),
        'ka': ('/ინფო', ),
        'ko': ('/설명문서', ),
        'no': ('/dok', ),
        'nn': ('/dok', ),
        'pl': ('/opis', ),
        'sk': ('/Dokumentácia', ),
        'sr': ('/док', ),
        'sv': ('/dok', ),
        'uk': ('/Документація', ),
        'ur': ('/doc', '/دستاویز'),
    }

    # Templates that indicate an edit should be avoided
    edit_restricted_templates = {
        'ar': ('تحرر',),
        'ary': ('كاتبدل دابا',),
        'arz': ('بتتطور',),
        'bs': ('Izmjena u toku',),
        'cs': ('Pracuje se',),
        'de': ('Inuse', 'In use', 'In bearbeitung', 'Inbearbeitung',),
        'en': ('Inuse', 'In use'),
        'fa': ('ویرایش',),
        'fr': ('En cours',),
        'he': ('בעבודה',),
        'hr': ('Radovi',),
        'hy': ('Խմբագրում եմ',),
        'ru': ('Редактирую',),
        'sr': ('Радови у току', 'Рут',),
        'test': ('In use',),
        'ur': ('زیر ترمیم',),
        'zh': ('Inuse',),
    }

    # Archive templates that indicate an edit of non-archive bots
    # should be avoided
    archived_page_templates = {
        'ar': ('أرشيف نقاش',),
        'arz': ('صفحة ارشيف',),
        'cs': ('Archiv', 'Archiv Wikipedie', 'Archiv diskuse',
               'Archivace start', 'Posloupnost archivů', 'Rfa-archiv-start',
               'Rfc-archiv-start',),
        'de': ('Archiv',),
    }

    @classmethod
    def __post_init__(cls):
        """Add 'yue' code alias due to :phab:`T341960`.

        .. versionadded:: 8.3
        """
        aliases = cls.code_aliases.copy()
        aliases['yue'] = 'zh-yue'
        cls.code_aliases = aliases

    def encodings(self, code):
        """Return a list of historical encodings for a specific site."""
        # Historic compatibility
        if code == 'pl':
            return 'utf-8', 'iso8859-2'
        if code == 'ru':
            return 'utf-8', 'iso8859-5'
        if code in self.latin1old:
            return 'utf-8', 'iso-8859-1'
        return super().encodings(code)

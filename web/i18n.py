"""
Translations of the status page: the languages of the wikis the archive bot runs on.

The language of a page is, in this order of precedence:
  1. the URL parameter ``uselang=<code>`` (only for this request, nothing is stored;
     ``forcedlang`` as on pb.toolforge.org works, too),
  2. the cookie ``spbot_lang``, set by a manual choice in the language menu,
  3. the browser's ``Accept-Language`` header,
  4. English.

The messages live in ``translations/<code>.json`` (key -> text). The texts are
trusted HTML with ``{name}`` placeholders; the values filled in are escaped
unless they are already ``Markup``. A key missing in a language falls back to English.

The bot's messages about a page (template errors, skipped pages, errors) come from
the bot's own ``userscripts/archive_resolved_localization/messages.json`` (one file for
the bot and this page) and are available here as ``msg.<key>``.
"""
import json
import os.path

import flask
from markupsafe import Markup, escape

# code -> (flag, name in the language itself)
LANGUAGES = {
    'cs': ('🇨🇿', 'Čeština'),
    'de': ('🇩🇪', 'Deutsch'),
    'en': ('🇬🇧', 'English'),
    'it': ('🇮🇹', 'Italiano'),
    'ja': ('🇯🇵', '日本語'),
    'ko': ('🇰🇷', '한국어'),
    'vi': ('🇻🇳', 'Tiếng Việt'),
}
DEFAULT_LANGUAGE = 'en'
PARAMS = ('uselang', 'forcedlang')
PARAM = PARAMS[0]
COOKIE_NAME = 'spbot_lang'
COOKIE_MAX_AGE = 365 * 24 * 3600
TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations')
# realpath: www/python/src is a symlink to bot/web
BOT_MESSAGES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                                 'userscripts', 'archive_resolved_localization', 'messages.json')


def _load_catalogs():
    catalogs = {}
    for code in LANGUAGES:
        with open(os.path.join(TRANSLATIONS_DIR, code + '.json'), encoding='utf-8') as f:
            catalogs[code] = json.load(f)
    with open(BOT_MESSAGES_FILE, encoding='utf-8') as f:
        bot_messages = json.load(f)
    for code in LANGUAGES:
        # plain text, not HTML: escape it, the placeholders stay
        catalogs[code].update({'msg.' + key: str(escape(text))
                               for key, text in bot_messages.get(code, {}).items()})
    return catalogs


CATALOGS = _load_catalogs()


def browser_language(request):
    """The supported language the browser prefers most (``de-AT`` counts as ``de``), else English."""
    best, best_quality = None, 0
    for value, quality in request.accept_languages:
        code = value.split('-')[0].split('_')[0].lower()
        if code in LANGUAGES and quality > best_quality:
            best, best_quality = code, quality
    return best or DEFAULT_LANGUAGE


def forced_language(request):
    """The language given in the URL, or None."""
    for param in PARAMS:
        if request.args.get(param) in LANGUAGES:
            return request.args[param]
    return None


def chosen_language(request):
    """The language of this request: URL parameter, then cookie, then browser."""
    forced = forced_language(request)
    if forced:
        return forced
    if request.cookies.get(COOKIE_NAME) in LANGUAGES:
        return request.cookies[COOKIE_NAME]
    return browser_language(request)


def current_language():
    if not flask.has_request_context():
        return DEFAULT_LANGUAGE
    if 'lang' not in flask.g:
        flask.g.lang = chosen_language(flask.request)
    return flask.g.lang


def gettext(key, **values):
    """The text for *key* in the current language, with the placeholders filled in."""
    text = CATALOGS[current_language()].get(key)
    if text is None:
        text = CATALOGS[DEFAULT_LANGUAGE].get(key, key)
    return Markup(text).format(**values) if values else Markup(text)


def has_key(key):
    return key in CATALOGS[DEFAULT_LANGUAGE]


def local_url(url):
    """*url* if it is a path on this site, otherwise ``/`` (no open redirects)."""
    if not url or not url.startswith('/') or url.startswith('//') or url.startswith('/\\'):
        return '/'
    return url

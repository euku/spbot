"""
Translations of the status page (like pb.toolforge.org).

The language of a page is, in this order of precedence:
  1. the URL parameter ``uselang=<code>``,
  2. the browser's ``Accept-Language`` header,
  3. English.

The messages live in ``translations/<code>.json`` (key -> text). The texts are
trusted HTML with ``{name}`` placeholders; the values filled in are escaped
unless they are already ``Markup``. A key missing in a language falls back to English.
"""
import json
import os.path

import flask
from markupsafe import Markup

LANGUAGES = {'de': 'Deutsch', 'en': 'English'}
DEFAULT_LANGUAGE = 'en'
PARAM = 'uselang'
TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations')


def _load_catalogs():
    catalogs = {}
    for code in LANGUAGES:
        with open(os.path.join(TRANSLATIONS_DIR, code + '.json'), encoding='utf-8') as f:
            catalogs[code] = json.load(f)
    return catalogs


CATALOGS = _load_catalogs()


def browser_language(request):
    best, best_quality = None, 0
    for value, quality in request.accept_languages:
        code = value.split('-')[0].split('_')[0].lower()
        if code in LANGUAGES and quality > best_quality:
            best, best_quality = code, quality
    return best or DEFAULT_LANGUAGE


def current_language():
    if not flask.has_request_context():
        return DEFAULT_LANGUAGE
    if 'lang' not in flask.g:
        chosen = flask.request.args.get(PARAM)
        flask.g.lang = chosen if chosen in LANGUAGES else browser_language(flask.request)
    return flask.g.lang


def gettext(key, **values):
    """The text for *key* in the current language, with the placeholders filled in."""
    text = CATALOGS[current_language()].get(key)
    if text is None:
        text = CATALOGS[DEFAULT_LANGUAGE].get(key, key)
    return Markup(text).format(**values) if values else Markup(text)

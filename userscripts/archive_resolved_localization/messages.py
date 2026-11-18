"""
Messages of the archive bot about a page, in the languages of the wikis (messages.json).

The bot raises/records a message as a key plus arguments. It formats it in the
language of the wiki for the talk page and the run summary; the summary also keeps
key and arguments, so the status page (web/) can show it in the language chosen there.
No imports besides the standard library: the web app loads the same file.
"""
import json
import os.path

MESSAGES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'messages.json')
DEFAULT_LANGUAGE = 'en'
# arguments that hold wikitext typed by users (e.g. a target with {{PAGENAME}}): <nowiki> on the wiki
RAW_ARGS = ('value', 'target')


def _load():
    with open(MESSAGES_FILE, encoding='utf-8') as f:
        return {code: texts for code, texts in json.load(f).items() if not code.startswith('_')}


MESSAGES = _load()


def languageFor(projectCode: str) -> str:
    """The message language of a wiki: its language code if there are messages for it, else English."""
    return projectCode if projectCode in MESSAGES else DEFAULT_LANGUAGE


def formatMessage(language: str, key: str, args: dict = None, wiki: bool = False) -> str:
    """The message *key* in *language* (fallback English); wiki=True: user wikitext in <nowiki>."""
    args = dict(args or {})
    if wiki:
        args = {k: f'<nowiki>{v}</nowiki>' if k in RAW_ARGS and v else v for k, v in args.items()}
    text = MESSAGES.get(language, {}).get(key) or MESSAGES[DEFAULT_LANGUAGE].get(key)
    if text is None:
        return f'{key} {args}' if args else key
    return text.format(**args)

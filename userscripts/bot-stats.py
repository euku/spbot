#!/usr/bin/python
"""Update bot statistic.

The following parameters are supported:

-always           The bot won't ask for confirmation when putting a page

-summary:         Set the action summary message for the edit.

-cache:<file>     Cache file with the known bot names
                  (default: data/bot-stats-cache.json in the repository)

-rebuild          Read the whole rights log again instead of only the
                  entries since the last run. Names that were only seen
                  in the bot group (e.g. expired flags) are kept.
"""
#
# (C) Euku, 2008-2026
# (C) xqt, 2024
#
from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import batched
from pathlib import Path

import pywikibot  # pywikibot framework
from pywikibot import Timestamp
from pywikibot.bot import CurrentPageBot, SingleSiteBot

PAGE_TITLE = 'Wikipedia:Liste der Bots nach Anzahl der Bearbeitungen'
DEFAULT_CACHE = (Path(__file__).resolve().parent.parent
                 / 'data' / 'bot-stats-cache.json')

# notable unflagged bots
unflagged_bots = ['Beitragszahlen']
# ignore users with (revoked) botflag
ignore_users = [
    'Geolina163 (WikiCon-Orga)',
    'Martin Urbanec (WMF)',
    'R. Hillgentleman',
]

# for colors see https://meta.wikimedia.org/wiki/Brand/colours
TEXT_COLOR = '202122'  # keeps the text dark in the dark mode of the skins
FORMER = ('ehemalig', 'E5C0C0', 'Konto besitzt kein Bot-Flag mehr')
NO_EDIT = ('inaktiv', 'C0E6FF', 'keine sichtbare Bearbeitung')
# (days since the last edit up to and including, remark, color, legend)
ACTIVITY = [
    (91, 'aktiv', 'DBF3EC', 'letzte Bearbeitung in den letzten drei Monaten'),
    (182, 'inaktiv', 'FDF6D8', 'letzte Bearbeitung vor 3–6 Monaten'),
    (365, 'inaktiv', 'FBEEBF', 'letzte Bearbeitung vor 6–12 Monaten'),
    (None, 'inaktiv', 'FBDFC5', 'letzte Bearbeitung vor über einem Jahr'),
]


@dataclass
class BotInfo:

    """Data of one bot account."""

    name: str
    editcount: int
    flagged: bool  # currently in the bot group
    registration: Timestamp | None = None
    first_edit: Timestamp | None = None
    last_edit: Timestamp | None = None
    unflagged_bot: bool = False  # notable bot without a bot flag

    @property
    def former(self) -> bool:
        """The account had a bot flag but has none now."""
        return not self.flagged and not self.unflagged_bot


def status(bot: BotInfo, now: Timestamp) -> tuple[str, str]:
    """Return remark and background color of a bot."""
    if bot.former:
        remark, color, _ = FORMER
    elif not bot.last_edit:
        remark, color, _ = NO_EDIT
    else:
        days = (now - bot.last_edit).days
        for limit, remark, color, _ in ACTIVITY:  # noqa: B007
            if limit is None or days <= limit:
                break
    if bot.unflagged_bot:
        remark += ' (ohne Flag)'
    return remark, color


def cell_style(color: str, extra: str = '') -> str:
    """Return the style attribute for a colored cell."""
    return f'style="background:#{color}; color:#{TEXT_COLOR}{extra}"'


def format_number(number: int) -> str:
    """Format a number with German thousands separators."""
    return f'{number:,}'.replace(',', '.')


def format_row(num: int, bot: BotInfo, now: Timestamp) -> str:
    """Return one table row."""
    if bot.last_edit:
        last_edit = str(bot.last_edit.date())
    else:
        last_edit = '?' if bot.editcount else '-'

    if bot.registration:
        registration = str(bot.registration.date())
    elif bot.first_edit:
        registration = f'{bot.first_edit.date()} *'
    else:
        registration = '?'

    remark, color = status(bot, now)
    return (
        f'|-\n|{num}|'
        f'|[[Benutzer:{bot.name}|{bot.name}]]|'
        f'| {cell_style(color)} |{remark}|'
        f'|[[Spezial:Beiträge/{bot.name}|B]]|'
        f'|{format_number(bot.editcount)}|'
        f'|{last_edit}|'
        f'|{registration}\n'
    )


TABLE_HEADER = """
{|class="sortable wikitable"
! #
! Botname
! Status
! Beiträge
! Gesamtbearbeitungen
! Letzte Bearbeitung
! Anmeldedatum

"""


def sort_bots(bots: Iterable[BotInfo]) -> list[BotInfo]:
    """Sort by edit count (descending), then by name."""
    return sorted(bots, key=lambda bot: (-bot.editcount, bot.name))


def format_table(bots: list[BotInfo], now: Timestamp) -> str:
    """Return a table with all given bots and their total edit count."""
    rows = ''.join(format_row(num, bot, now)
                   for num, bot in enumerate(bots, start=1))
    total = format_number(sum(bot.editcount for bot in bots))
    return (f'{TABLE_HEADER}{rows}|}}\n'
            f'Gesamtbearbeitungen durch diese Bots: {total}\n')


def legend_item(remark: str, color: str, text: str) -> str:
    """Return one legend line."""
    return (f'* <span {cell_style(color, "; padding:0 0.3em")}>'
            f'{remark}</span> = {text}\n')


def build_page(bots: Iterable[BotInfo], now: Timestamp) -> str:
    """Return the complete page text."""
    bots = sort_bots(bots)
    current = [bot for bot in bots if not bot.former]
    former = [bot for bot in bots if bot.former]
    total = format_number(sum(bot.editcount for bot in bots))

    header = (
        'Aufgeführt sind alle Bots, die das Bot-Flag besitzen, sowie '
        'bekannte Bots ohne Bot-Flag. Benutzerkonten, die das Bot-Flag '
        'früher besaßen, stehen im Abschnitt [[#Ehemalige Bots|Ehemalige Bots]]. '
        'Stand: ~~~~~<br />\n'
        'Ein Bot gilt als inaktiv, wenn er in den letzten drei Monaten '
        'keinen Beitrag geleistet hat.\n\n'
        '[//de.wikipedia.org/w/index.php?'
        f'title={PAGE_TITLE.replace(" ", "_")}'
        '&diff=curr&oldid=prev&diffonly=1 Änderungen der letzten Woche]\n'
    )

    legend = ''.join(legend_item(remark, color, text)
                     for _, remark, color, text in ACTIVITY)
    legend += legend_item(*NO_EDIT)
    legend += legend_item(*FORMER)

    footer = (
        '\n== Erläuterungen ==\n'
        f'Gesamtbearbeitungen aller aufgeführten Bots: {total}\n\n'
        "'''Status'''\n"
        f'{legend}'
        '\n'
        "'''Spalten'''\n"
        '* Gesamtbearbeitungen = Bearbeitungszähler der Software, nur '
        '[[Wikipedia_Diskussion:'
        'Liste der Bots nach Anzahl der Bearbeitungen'
        '#Bots_ohne_einen_Edit_mit_einem_letzten_Edit|eine Schätzung]]. '
        'Er kann von der Beitragsliste abweichen, deshalb hat manches Konto '
        '0 Bearbeitungen und trotzdem eine letzte Bearbeitung.\n'
        '* Letzte Bearbeitung: „-“ = keine Bearbeitung, '
        '„?“ = es gibt Bearbeitungen, aber keine sichtbaren '
        '(z.&nbsp;B. nur auf gelöschten Seiten)\n'
        '* Anmeldedatum: <nowiki>*</nowiki> = Anmeldedatum unbekannt, '
        'angegeben ist das Datum der ersten Bearbeitung\n\n'
        '[[Kategorie:Wikipedia:Bots]]'
    )

    return (header
            + '\n== Bots mit Bot-Flag ==\n' + format_table(current, now)
            + '\n== Ehemalige Bots ==\n' + format_table(former, now)
            + footer)


class BotCache:

    """Persistent list of known bot names (a JSON file in the repository).

    ``revoked``: accounts whose bot flag was removed according to the
    rights log; can be rebuilt with ``-rebuild``.
    ``flagged``: accounts that were seen in the bot group at least once.
    This is the only source for flags that simply expired (no log
    entry), so it can not be rebuilt.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.rights_log_until: str | None = None
        self.revoked: set[str] = set()
        self.flagged: set[str] = set()
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            self.rights_log_until = data.get('rights_log_until')
            self.revoked = set(data.get('revoked', []))
            self.flagged = set(data.get('flagged', []))

    def names(self) -> set[str]:
        """Return all known bot names."""
        return self.revoked | self.flagged

    def save(self) -> None:
        """Write the cache (sorted, one name per line for small diffs)."""
        data = {
            '_comment': 'Maintained by userscripts/bot-stats.py. '
                        '"revoked" can be rebuilt with -rebuild, '
                        '"flagged" can not (expired flags have no log entry).',
            'rights_log_until': self.rights_log_until,
            'revoked': sorted(self.revoked),
            'flagged': sorted(self.flagged),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + '.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n',
                       encoding='utf-8')
        os.replace(tmp, self.path)


def revoked_bot_names(events) -> tuple[set[str], str | None]:
    """Return the accounts whose bot flag was removed in the given events.

    :param events: rights log entries, newest first
    :return: names and the timestamp of the newest entry
    """
    names = set()
    newest = None
    cnt = 0
    pywikibot.info('read rights log...', newline=False)
    for cnt, event in enumerate(events, start=1):
        if cnt % 100 == 0:
            pywikibot.info('.', newline=False)
        if newest is None:
            newest = event.timestamp().isoformat()
        if event.action() != 'rights' or 'title' not in event.data:
            continue  # other action or hidden entry
        if 'bot' in event.oldgroups and 'bot' not in event.newgroups:
            names.add(event.page().title(with_ns=False))
    pywikibot.info(f' {cnt} entries')
    return names, newest


class BotStatsUpdater(SingleSiteBot, CurrentPageBot):

    """A bot which updates bot statistics."""

    update_options = {
        'summary': 'Bot: Aktualisiere Bot-Statistik',
        'cache': '',
        'rebuild': False,
    }

    @property
    def generator(self):
        """Yield the page to update."""
        yield pywikibot.Page(self.site, PAGE_TITLE)

    def update_cache(self, cache: BotCache) -> None:
        """Add new revoked flags and the current bot group to the cache."""
        rebuild = self.opt.rebuild or not cache.rights_log_until
        end = None if rebuild else Timestamp.fromISOformat(
            cache.rights_log_until)
        revoked, newest = revoked_bot_names(
            self.site.logevents('rights', end=end))
        if rebuild:
            cache.revoked = revoked
        else:
            cache.revoked |= revoked
        if newest:
            cache.rights_log_until = newest
        cache.flagged |= {user['name']
                          for user in self.site.allusers(group='bot')}

    def collect_data(self, names: Iterable[str]) -> list[BotInfo]:
        """Fetch the data of all bots (user info in batches of 50)."""
        ignore = set(ignore_users)
        names = sorted(set(names) - ignore)
        bots = []
        pywikibot.info('fetch user data...', newline=False)
        for chunk in batched(names, 50):
            pywikibot.info('.', newline=False)
            for user in self.site.users(chunk):
                if 'missing' in user or 'invalid' in user:
                    pywikibot.info(f'\nskip unknown user {user["name"]}')
                    continue
                reg = user.get('registration')
                bots.append(BotInfo(
                    name=user['name'],
                    editcount=user.get('editcount', 0),
                    flagged='bot' in user.get('groups', []),
                    registration=Timestamp.fromISOformat(reg) if reg else None,
                    unflagged_bot=user['name'] in unflagged_bots,
                ))

        pywikibot.info('\nfetch first and last edits...', newline=False)
        for num, bot in enumerate(bots, start=1):
            if num % 10 == 0:
                pywikibot.info('.', newline=False)
            bot.last_edit = self.edit_time(bot.name)
            if not bot.registration:
                bot.first_edit = self.edit_time(bot.name, reverse=True)
        pywikibot.info()
        return bots

    def edit_time(self, name: str, reverse: bool = False) -> Timestamp | None:
        """Return the time of the last (or first) visible edit."""
        for contrib in self.site.usercontribs(user=name, reverse=reverse,
                                              total=1):
            return Timestamp.fromISOformat(contrib['timestamp'])
        return None

    def build_text(self) -> str:
        """Update the cache and return the new page text."""
        cache = BotCache(Path(self.opt.cache) if self.opt.cache
                         else DEFAULT_CACHE)
        self.update_cache(cache)
        cache.save()
        names = cache.names() | set(unflagged_bots)
        return build_page(self.collect_data(names), Timestamp.now())

    def treat_page(self) -> None:
        """Process the bot statistic page."""
        self.put_current(
            self.build_text(),
            summary=self.opt.summary,
            show_diff=not self.opt.always
        )


def main(*args: str) -> None:
    """Process command line arguments and invoke bot.

    If args is an empty list, sys.argv is used.

    :param args: command line arguments
    """
    options = {}

    for arg in pywikibot.handle_args(args):
        opt, _, value = arg.partition(':')
        if not opt.startswith('-'):
            continue
        options[opt.removeprefix('-')] = value or True

    bot = BotStatsUpdater(**options)
    bot.run()


if __name__ == '__main__':
    main()

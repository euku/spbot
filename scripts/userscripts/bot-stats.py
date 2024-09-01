#!/usr/bin/python
"""Update bot statistic.

The following parameters are supported:

-always           The bot won't ask for confirmation when putting a page

-summary:         Set the action summary message for the edit.
"""
#
# (C) Euku, 2008-2024
# (C) xqt, 2024
#
from __future__ import annotations

from itertools import chain
from operator import methodcaller

import pywikibot  # pywikibot framework
from pywikibot import Timestamp
from pywikibot.backports import Generator, removeprefix
from pywikibot.bot import CurrentPageBot, SingleSiteBot
from pywikibot.tools.itertools import filter_unique

# notable unflagged bots
unflagged_bots = ['Beitragszahlen']
# ignore users with (revoked) botflag
ignore_users = [
    'Geolina163 (WikiCon-Orga)',
    'Martin Urbanec (WMF)',
    'R. Hillgentleman',
]


class BotStatsUpdater(SingleSiteBot, CurrentPageBot):

    """A bot which updates bot statistics."""

    update_options = {'summary': 'Bot: Aktualisiere Bot-Statistik'}

    def former_botnames(self) -> Generator[str, None, None]:
        """Collect former botnames.

        .. note:: This method yields account where bot flag was revoked.
           It does not check whether the flag was granted afterwards.
        """
        pywikibot.info('find former bot names...', newline=False)
        for cnt, event in enumerate(self.site.logevents('rights')):
            if event.action() != 'rights':
                continue
            if 'bot' in event.oldgroups and 'bot' not in event.newgroups:
                if cnt % 10 == 0:
                    pywikibot.info('.', newline=False)
                yield event.data['title']

    @property
    def generator(self) -> Generator[str, None, None]:
        """Yield the page to update."""
        yield pywikibot.Page(
            self.site,
            'Wikipedia:Liste der Bots nach Anzahl der Bearbeitungen'
        )

    def treat_page(self) -> None:
        """Process the bot statistic page."""
        page_header = (
            'Aufgeführt sind alle Bots die einen Bot-Flag besitzen. '
            'Stand: ~~~~~<br />'
            'Ein Bot gilt als inaktiv, wenn er in den letzten drei Monaten '
            'keinen Beitrag geleistet hat.\n\n'
            '[//de.wikipedia.org/w/index.php?'
            f'title={self.current_page.title(underscore=True)}'
            '&diff=curr&oldid=prev&diffonly=1 Änderungen der letzten Woche]'
        )

        page_footer = (
            '([[Wikipedia_Diskussion:'
            'Liste der Bots nach Anzahl der Bearbeitungen'
            '#Bots_ohne_einen_Edit_mit_einem_letzten_Edit|eine Schätzung]])'
            '<br />\n<nowiki>*</nowiki> = Datum der ersten Bearbeitung<br/>\n'
            'ehemalig = das Benutzterkonto besitzt kein Botflag mehr\n\n'
            '[[Kategorie:Wikipedia:Bots]]'
        )

        table_header = """
{|class="sortable wikitable"
! #
! Botname
! Status
! Beiträge
! Gesamtbearbeitungen
! Letzte Bearbeitung
! Anmeldedatum

"""

        text = page_header + table_header + self.create_table() + page_footer
        self.put_current(
            text,
            summary=self.opt.summary,
            show_diff=not self.opt.always
        )

    def collect_data(self) -> Generator[pywikibot.User, None, None]:
        """Collect flagged bots and bots with revoked flags."""
        allbots = (user['name'] for user in self.site.allusers(group='bot'))
        # Use bot users first in the chain.
        # The bot flag can have been granted for former botnames
        bots = (pywikibot.User(self.site, name)
                for name in chain(allbots,
                                  self.former_botnames(),
                                  unflagged_bots))
        container = {pywikibot.User(self.site, name)
                     for name in ignore_users}
        yield from filter_unique(bots, container=container)

    def create_table(self) -> str:
        """Create page content."""
        botlist = sorted(self.collect_data(),
                         key=methodcaller('editCount'),
                         reverse=True)

        pywikibot.info('\ncreating wiki table...', newline=False)
        pagetext = ''
        all_edits = 0
        now = Timestamp.now()

        for num, bot in enumerate(botlist, start=1):
            if num % 10 == 0:
                pywikibot.info('.', newline=False)

            all_edits += bot.editCount()

            last_edit = bot.last_edit[2] if bot.last_edit else None
            if not last_edit:
                last_edit_str = '-' if not bot.editCount() else '?'
            else:
                last_edit_str = str(last_edit.date())

            reg = bot.registration()
            if reg:
                registration = str(reg.date())
            else:
                reg = bot.first_edit[2]
                registration = f'{reg.date()} *' if reg else '?'

            # for colors see https://meta.wikimedia.org/wiki/Brand/colours
            remark = 'inaktiv'
            if 'bot' not in bot.groups():
                remark, color = 'ehemalig', 'E5C0C0'  # light red
            elif not last_edit:
                color = 'C0E6FF'  # light bright blue
            elif (now - last_edit).days > 365:
                color = 'FBDFC5'  # light orange
            elif (now - last_edit).days > 182:
                color = 'FBEEBF'  # light yellow
            elif (now - last_edit).days > 91:
                color = 'F9F9F0'  # light bright yellow
            else:
                remark, color = 'aktiv', 'DBF3EC'  # light bright green

            edits = f'{bot.editCount():,}'.replace(',', '.')
            pagetext += (
                f'|-\n|{num}|'
                f'|{bot.title(as_link=True, with_ns=False)}|'
                f'| style="background:#{color}" |{remark}|'
                f'|[[Spezial:Beiträge/{bot.title(with_ns=False)}|B]]|'
                f'|{edits}|'
                f'|{last_edit_str}|'
                f'|{registration}\n'
            )
            self.counter['collect'] = num

        pywikibot.info()
        edit_sum = f'{all_edits:,}'.replace(',', '.')
        pagetext += f'|}}\nGesamtbearbeitungen durch diese Bots: {edit_sum} '
        return pagetext


def main(*args: str) -> None:
    """Process command line arguments and invoke bot.

    If args is an empty list, sys.argv is used.

    :param args: command line arguments
    """
    options = {}

    for arg in pywikibot.handle_args():
        opt, _, value = arg.partition(':')
        if not opt.startswith('-'):
            continue
        options[removeprefix(opt, '-')] = value or True

    bot = BotStatsUpdater(**options)
    bot.run()


if __name__ == '__main__':
    main()

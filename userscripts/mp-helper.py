#!/usr/bin/env python3
"""
Schreibt die Listen des Mentorenprogramms (WP:MP) aus der Mentorendatenbank ins Wiki.

Die Daten kommen aus der read-only API des Tools mp (https://mp.toolforge.org/api/v1/).
Die Datenbank selbst (neue Mentees, beendete Betreuungen, Umbenennungen) pflegt der Job
``sync-mentees`` des Tools mp anhand von [[Kategorie:Benutzer:Mentee]]; der Bot hat
keinen Datenbankzugriff mehr.

Geschrieben werden:
  * Wikipedia:Mentorenprogramm/Projektorganisation/In Betreuung
  * Wikipedia:Mentorenprogramm/Projektorganisation/Archiv <Jahr> <Monat> (aktueller Monat,
    in den ersten Tagen eines Monats auch der Vormonat)
  * die beiden Seiten mit der Anzahl der Mentees/Mentoren (höchstens einmal am Tag)

Fehler (API nicht erreichbar, Seite nicht speicherbar) werden geloggt; der Exit-Code ist erst
nach mehreren Fehlschlägen hintereinander 1 (dann schickt Toolforge eine Mail), siehe
FAILURE_MAIL_AFTER/FAILURE_MAIL_EVERY.

Parameter:

-force          Anzahl-Seiten auch schreiben, wenn sie vor weniger als 23 Stunden geändert wurden
-api:URL        andere API-Basis (zum Testen), Standard: https://mp.toolforge.org/api/v1
-simulate       (pywikibot) nichts speichern, nur anzeigen
"""
import datetime
import os
import re
import sys
import time

import pywikibot
import requests
from pywikibot.exceptions import PageSaveRelatedError

API_BASE = "https://mp.toolforge.org/api/v1"
USER_AGENT = "SpBot mp-helper (https://de.wikipedia.org/wiki/Benutzer:SpBot)"
HTTP_TIMEOUT = {"mentees": 120}  # /mentees looks up the last edit of every mentee
HTTP_TIMEOUT_DEFAULT = 30
HTTP_RETRIES = (10, 30)  # seconds to wait before the 2nd and 3rd attempt
# the job runs every 20 minutes; give up before the next run starts
RUN_BUDGET = datetime.timedelta(minutes=15)

# the previous month's archive is only rewritten on the first days of a month (mentorings
# stopped shortly before midnight, or a late sync of the mp tool)
PREVIOUS_MONTH_DAYS = 3

# consecutive failed runs; a leading dot keeps the file out of daily-log-cleanup.sh
FAILURE_FILE = os.path.join("logs", ".mp-helper-failures")
FAILURE_MAIL_AFTER = 3   # exit code 1 (= mail) on the 3rd failed run in a row (after 1 hour) …
FAILURE_MAIL_EVERY = 72  # … and then once a day while the failure lasts

SUMMARY_MAX_LENGTH = 450  # MediaWiki cuts edit summaries at 500 characters

mentorenProgrammMenteeliste = "Wikipedia:Mentorenprogramm/Projektorganisation/In Betreuung"
anzahlAllerBetreutenMentees = "Wikipedia:Mentorenprogramm/Projektorganisation/Anzahl bisheriger Mentees"
anzahlAllerZurzeitBetreuendenMentoren = "Wikipedia:Mentorenprogramm/Projektorganisation/Anzahl betreuender Mentoren"
mentorenProgrammMenteeArchiv = "Wikipedia:Mentorenprogramm/Projektorganisation/Archiv "
COUNT_PAGE_MIN_AGE = datetime.timedelta(hours=23)

# archive edits are deliberately made without bot flag (since 2021), so that they show up in
# watchlists that hide bot edits; the list and count pages change often and use the bot flag
ARCHIVE_BOT_FLAG = False

STATUS = {"ok": "grün", "long": "orange", "critical": "rot"}
STATUS_UNKNOWN = "grün"  # Vorlage:MP-NB shows unknown values as green anyway
TYPE_LIST = {2: "Wunschmentor", 1: "Zufall"}
TYPE_ARCHIVE = {2: "[W]", 1: "[N]"}
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]

_LIST_ENTRY_RE = re.compile(r"\{\{MP-NB\|Eintritt=[^|}]*\|Mentee=([^|}]*)\|Mentor=([^|}]*)\|")


class ApiError(Exception):
    pass


def utcnow():
    return datetime.datetime.now(datetime.UTC)


# --- API ---

def api_get(session, base, path, deadline=None):
    """GET ``base/path`` as JSON; retries on network errors, 5xx answers and invalid JSON.

    No new attempt is started if it could not finish before ``deadline`` (aware datetime).
    """
    url = f"{base}/{path}"
    timeout = HTTP_TIMEOUT.get(path, HTTP_TIMEOUT_DEFAULT)
    error = None
    for wait in (0, *HTTP_RETRIES):
        if deadline is not None and utcnow() + datetime.timedelta(seconds=wait + timeout) > deadline:
            error = f"{url}: Zeitbudget des Laufs aufgebraucht" + (f" (zuletzt: {error})" if error else "")
            break
        if wait:
            pywikibot.info(f"Neuer Versuch in {wait} s …")
            time.sleep(wait)
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as exc:  # includes requests.JSONDecodeError
            error = f"{url}: {exc}"
        else:
            error = f"{url}: HTTP {response.status_code} {response.text[:200]}"
            if response.status_code < 500:
                break
        pywikibot.warning(error)
    raise ApiError(error)


# --- wikitext ---

def statusName(mentee):
    status = STATUS.get(mentee["status"])
    if status is None:
        pywikibot.warning(f"unbekannter Status {mentee['status']!r} bei {mentee['mentee']}")
        return STATUS_UNKNOWN
    return status


def renderActiveMenteeList(mentees):
    rows = []
    counterRed = counterOrange = 0
    for mentee in mentees:
        status = statusName(mentee)
        if status == "orange":
            counterOrange += 1
        elif status == "rot":
            counterRed += 1
        start = datetime.datetime.fromisoformat(mentee["start"])
        # Vorlage:MP-NB formats and sorts the date itself (#time), so no zero padding needed
        rows.append("{{MP-NB|Eintritt=%s-%s-%s|Mentee=%s|Mentor=%s|Status=%s|Typ=%s}}" % (
            start.year, start.month, start.day, mentee["mentee"], mentee["mentor"], status,
            TYPE_LIST.get(mentee["type"], "nicht gesetzt")))
    countAll = len(mentees)
    head = ("{{Benutzer:Euku/SpBot-Status}}\nDerzeit sind '''%s''' Mentees in Betreuung. Davon haben %s (%s%%) "
            "den Status rot (letzter Edit > 60 Tage) und %s (%s%%) den Status orange (Betreuung > fünf Monate).\n"
            % (countAll, counterRed, round(100 * counterRed / countAll), counterOrange,
               round(100 * counterOrange / countAll)))
    table = "{| class=\"wikitable sortable\"\n|- class=\"hintergrundfarbe5\"\n!Eintritt||Mentee||Mentor||Status||Typ"
    return head + table + "".join("\n|-\n" + row for row in rows) + "\n|}"


def changeSummary(oldText, mentees, maxLength=SUMMARY_MAX_LENGTH):
    """``+Mentee (Mentor)`` / ``-Mentee (Mentor)`` compared with the current wiki list.

    Entries that do not fit into ``maxLength`` are counted as ``… und N weitere``.
    """
    old = set(_LIST_ENTRY_RE.findall(oldText))
    new = {(m["mentee"], m["mentor"]) for m in mentees}
    items = ["%s[[:User:%s|%s]] ([[:User:%s|%s]])" % (sign, mentee, mentee, mentor, mentor)
             for entries, sign in ((new - old, "+"), (old - new, "-"))
             for mentee, mentor in sorted(entries)]
    summary = ""
    for i, item in enumerate(items):
        rest = len(items) - i - 1
        candidate = (summary + " " + item).strip()
        # keep room for the "… und N weitere" suffix unless this is the last item
        if len(candidate) + (len(" … und %d weitere" % rest) if rest else 0) > maxLength:
            return (summary + " … und %d weitere" % (len(items) - i)).strip()
        summary = candidate
    return summary


def renderArchiveMonth(archive):
    monthName = MONTHS[archive["month"] - 1]
    mentorings = archive["mentorings"]
    head = ("<noinclude><!--\n"
            "######################################################################################\n"
            "# ACHTUNG: Diese Liste wird von einem Bot aktualisiert.\n"
            "# Manuelle Änderungen werden überschrieben.\n"
            "######################################################################################\n"
            "-->\n"
            "{{Benutzer:SpBot/Nicht bearbeiten}}</noinclude>\n"
            "<div class=\"NavFrame\" style=\"margin:2px;margin-top:5px;margin-right:5px;border:1px solid #1A442B;"
            "padding:0 1em 1em 1em;background-color:#f8f8ff;align:right;font-size:95%%\">\n"
            "<div class=\"NavHead\" align=\"left\">\n"
            "<h5>%s %s: (<span style='color:red'>%s</span>)</h5></div>\n<div class=\"NavContent\" align=\"left\">\n"
            "'''Eintritt in das MP / Ausscheiden aus dem MP:'''<br />\n"
            "<ol start=\"%s\">\n") % (monthName, archive["year"], len(mentorings),
                                     archive["first_number"] if mentorings else 0)
    body = ""
    for m in mentorings:
        start = datetime.datetime.fromisoformat(m["start"])
        stop = datetime.datetime.fromisoformat(m["stop"])
        body += "<li>%02d.%02d.%s / %02d.%02d.%s: %s [[Spezial:Beiträge/%s|%s]] ([[Benutzer:%s|%s]])</li>\n" % (
            start.day, start.month, start.year, stop.day, stop.month, stop.year,
            TYPE_ARCHIVE.get(m["type"], ""), m["mentee"], m["mentee"], m["mentor"], m["mentor"])
    return head + body + "</ol></div></div>"


def archiveMonths(today):
    """(year, month) of the archive pages to update on ``today``."""
    months = []
    if today.day <= PREVIOUS_MONTH_DAYS:
        previous = today.replace(day=1) - datetime.timedelta(days=1)
        months.append((previous.year, previous.month))
    months.append((today.year, today.month))
    return months


# --- write to Wikipedia ---

def pageText(page):
    return page.get() if page.exists() else ""


def savePage(page, text, summary, **kwargs):
    """Saves the page; returns False (and logs) if the save is refused."""
    try:
        page.put(text, summary=summary, minor=True, force=True, **kwargs)
    except PageSaveRelatedError as exc:
        pywikibot.error(f"{page.title()} nicht gespeichert: {exc}")
        return False
    return True


def writeActiveMenteeList(site, mentees):
    if not mentees:
        pywikibot.error("Die API liefert keine Mentees in Betreuung, Liste wird nicht geschrieben")
        return False
    result = renderActiveMenteeList(mentees)
    page = pywikibot.Page(site, mentorenProgrammMenteeliste)
    rawText = pageText(page)
    if result == rawText:
        pywikibot.info("keine Änderung in aktiver Menteeliste (WP)")
        return True
    summary = changeSummary(rawText, mentees)
    pywikibot.showDiff(rawText, result)
    return savePage(page, result, "Update " + summary if summary else "Update (Status)", bot=True)


def writeMenteeArchive(site, session, base, today, deadline=None):
    ok = True
    for year, month in archiveMonths(today):
        archive = api_get(session, base, f"archive/{year}/{month}", deadline)
        text = renderArchiveMonth(archive)
        page = pywikibot.Page(site, f"{mentorenProgrammMenteeArchiv}{year} {MONTHS[month - 1]}")
        oldText = pageText(page)
        if oldText == text:
            pywikibot.info(f"keine Änderung im WP-Archiv nötig: {year} {MONTHS[month - 1]}")
            continue
        if page.exists():
            pywikibot.showDiff(oldText, text)
        ok &= savePage(page, text, "Update" if page.exists() else "neues Archiv", bot=ARCHIVE_BOT_FLAG)
    return ok


def writeCount(site, title, number, summary, force, now=None):
    page = pywikibot.Page(site, title)
    if number is None or pageText(page) == str(number):
        return True
    if page.exists() and not force:
        now = now or utcnow()
        age = now - page.latest_revision.timestamp.replace(tzinfo=datetime.UTC)
        if age < COUNT_PAGE_MIN_AGE:
            pywikibot.info(f"{title}: zuletzt vor {age} geändert, nächste Aktualisierung später")
            return True
    return savePage(page, str(number), summary % number)


# --- failure counter ---

def readFailures(path=FAILURE_FILE):
    try:
        with open(path) as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def recordRun(success, path=FAILURE_FILE):
    """Updates the counter of consecutive failed runs; returns the exit code of the job."""
    failures = 0 if success else readFailures(path) + 1
    try:
        if failures:
            with open(path, "w") as f:
                f.write(f"{failures}\n")
        elif os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        pywikibot.warning(f"Fehlerzähler {path} nicht aktualisiert: {exc}")
    if not failures:
        return 0
    pywikibot.warning(f"{failures}. fehlgeschlagener Lauf in Folge")
    if failures >= FAILURE_MAIL_AFTER and (failures - FAILURE_MAIL_AFTER) % FAILURE_MAIL_EVERY == 0:
        return 1
    return 0


# --- main ---

def run(site, session, base, force, now):
    """One run; returns True if everything was fetched and saved."""
    deadline = now + RUN_BUDGET
    try:
        mentees = api_get(session, base, "mentees", deadline)
        ok = writeActiveMenteeList(site, mentees)
        ok &= writeMenteeArchive(site, session, base, now.date(), deadline)
        counts = api_get(session, base, "counts", deadline)
    except ApiError as exc:
        pywikibot.error(f"Mentorendatenbank nicht erreichbar, nichts (weiter) geschrieben: {exc}")
        return False
    ok &= writeCount(site, anzahlAllerBetreutenMentees, counts["mentees_total"],
                     "Anzahl bisheriger Mentees: %s", force, now)
    ok &= writeCount(site, anzahlAllerZurzeitBetreuendenMentoren, counts["active_mentors"],
                     "Anzahl zurzeit betreuenden Mentoren: %s", force, now)
    return ok


def main():
    force = False
    base = API_BASE
    for arg in pywikibot.handle_args():
        if arg == "-force":
            force = True
        elif arg.startswith("-api:"):
            base = arg[len("-api:"):].rstrip("/")
        else:
            pywikibot.warning(arg + " wurde ignoriert")

    now = utcnow()
    pywikibot.info(now.strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############"))
    site = pywikibot.Site()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return recordRun(run(site, session, base, force, now))


if __name__ == "__main__":
    sys.exit(main())

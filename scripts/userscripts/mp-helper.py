#!/usr/bin/python
"""
Schreibt die Listen des Mentorenprogramms (WP:MP) aus der Mentorendatenbank ins Wiki.

Die Daten kommen aus der read-only API des Tools mp (https://mp.toolforge.org/api/v1/).
Die Datenbank selbst (neue Mentees, beendete Betreuungen, Umbenennungen) pflegt der Job
``sync-mentees`` des Tools mp anhand von [[Kategorie:Benutzer:Mentee]]; der Bot hat
keinen Datenbankzugriff mehr.

Geschrieben werden:
  * Wikipedia:Mentorenprogramm/Projektorganisation/In Betreuung
  * Wikipedia:Mentorenprogramm/Projektorganisation/Archiv <Jahr> <Monat> (aktueller und Vormonat)
  * die beiden Seiten mit der Anzahl der Mentees/Mentoren (höchstens einmal am Tag)

Parameter:

-force          Anzahl-Seiten auch schreiben, wenn sie vor weniger als 23 Stunden geändert wurden
-api:URL        andere API-Basis (zum Testen), Standard: https://mp.toolforge.org/api/v1
-simulate       (pywikibot) nichts speichern, nur anzeigen
"""
import datetime
import re
import sys
import time

import pywikibot
import requests

API_BASE = "https://mp.toolforge.org/api/v1"
USER_AGENT = "SpBot mp-helper (https://de.wikipedia.org/wiki/Benutzer:SpBot)"
HTTP_TIMEOUT = 120      # /mentees looks up the last edit of every mentee
HTTP_RETRIES = (10, 30)  # seconds to wait before the 2nd and 3rd attempt

mentorenProgrammMenteeliste = "Wikipedia:Mentorenprogramm/Projektorganisation/In Betreuung"
anzahlAllerBetreutenMentees = "Wikipedia:Mentorenprogramm/Projektorganisation/Anzahl bisheriger Mentees"
anzahlAllerZurzeitBetreuendenMentoren = "Wikipedia:Mentorenprogramm/Projektorganisation/Anzahl betreuender Mentoren"
mentorenProgrammMenteeArchiv = "Wikipedia:Mentorenprogramm/Projektorganisation/Archiv "
COUNT_PAGE_MIN_AGE = datetime.timedelta(hours=23)

STATUS = {"ok": "grün", "long": "orange", "critical": "rot"}
TYPE_LIST = {2: "Wunschmentor", 1: "Zufall"}
TYPE_ARCHIVE = {2: "[W]", 1: "[N]"}
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]

_LIST_ENTRY_RE = re.compile(r"\{\{MP-NB\|Eintritt=[^|}]*\|Mentee=([^|}]*)\|Mentor=([^|}]*)\|")


class ApiError(Exception):
    pass


##### API

def api_get(session, base, path):
    """GET ``base/path`` as JSON; retries on network errors and 5xx answers."""
    url = f"{base}/{path}"
    for attempt, wait in enumerate((0, *HTTP_RETRIES)):
        if wait:
            pywikibot.info(f"Neuer Versuch in {wait} s …")
            time.sleep(wait)
        try:
            response = session.get(url, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            error = f"{url}: {exc}"
        else:
            if response.status_code == 200:
                return response.json()
            error = f"{url}: HTTP {response.status_code} {response.text[:200]}"
            if response.status_code < 500:
                break
        pywikibot.warning(error)
    raise ApiError(error)


##### wikitext

def renderActiveMenteeList(mentees):
    rows = []
    counterRed = counterOrange = 0
    for mentee in mentees:
        status = STATUS[mentee["status"]]
        if status == "orange":
            counterOrange += 1
        elif status == "rot":
            counterRed += 1
        start = datetime.datetime.fromisoformat(mentee["start"])
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


def changeSummary(oldText, mentees):
    """``+Mentee (Mentor)`` / ``-Mentee (Mentor)`` compared with the current wiki list."""
    old = set(_LIST_ENTRY_RE.findall(oldText))
    new = {(m["mentee"], m["mentor"]) for m in mentees}

    def link(entries, sign):
        return "".join("%s[[:User:%s|%s]] ([[:User:%s|%s]]) " % (sign, mentee, mentee, mentor, mentor)
                       for mentee, mentor in sorted(entries))
    return (link(new - old, "+") + link(old - new, "-")).strip()


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


##### write to Wikipedia

def pageText(page):
    return page.get() if page.exists() else ""


def writeActiveMenteeList(site, mentees):
    if not mentees:
        pywikibot.error("Die API liefert keine Mentees in Betreuung, Liste wird nicht geschrieben")
        return
    result = renderActiveMenteeList(mentees)
    page = pywikibot.Page(site, mentorenProgrammMenteeliste)
    rawText = pageText(page)
    if result == rawText:
        pywikibot.info("keine Änderung in aktiver Menteeliste (WP)")
        return
    summary = changeSummary(rawText, mentees)
    pywikibot.showDiff(rawText, result)
    page.put(result, summary="Update " + summary if summary else "Update (Status)",
             minor=True, force=True, botflag=True)


def writeMenteeArchive(site, session, base, today):
    # the previous month as well, so mentorings stopped shortly before midnight are not lost
    previous = (today.replace(day=1) - datetime.timedelta(days=1))
    for year, month in ((previous.year, previous.month), (today.year, today.month)):
        archive = api_get(session, base, f"archive/{year}/{month}")
        text = renderArchiveMonth(archive)
        page = pywikibot.Page(site, f"{mentorenProgrammMenteeArchiv}{year} {MONTHS[month - 1]}")
        if not page.exists():
            page.put(text, summary="neues Archiv", minor=True, force=True, botflag=False)
        elif page.get() != text:
            pywikibot.showDiff(page.get(), text)
            page.put(text, summary="Update", minor=True, force=True, botflag=False)
        else:
            pywikibot.info(f"keine Änderung im WP-Archiv nötig: {year} {MONTHS[month - 1]}")


def writeCount(site, title, number, summary, force):
    page = pywikibot.Page(site, title)
    if number is None or pageText(page) == str(number):
        return
    if page.exists() and not force:
        age = datetime.datetime.utcnow() - page.latest_revision.timestamp.replace(tzinfo=None)
        if age < COUNT_PAGE_MIN_AGE:
            pywikibot.info(f"{title}: zuletzt vor {age} geändert, nächste Aktualisierung später")
            return
    page.put(str(number), summary=summary % number, minor=True, force=True)


"""
  MAIN
"""
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

    pywikibot.info(time.strftime("########## timestamp: %Y-%m-%d %H:%M:%S ############", time.gmtime()))
    site = pywikibot.Site()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    try:
        mentees = api_get(session, base, "mentees")
        writeActiveMenteeList(site, mentees)
        writeMenteeArchive(site, session, base, datetime.datetime.utcnow().date())
        counts = api_get(session, base, "counts")
    except ApiError as exc:
        pywikibot.error(f"Mentorendatenbank nicht erreichbar, nichts (weiter) geschrieben: {exc}")
        return 1
    writeCount(site, anzahlAllerBetreutenMentees, counts["mentees_total"],
               "Anzahl bisheriger Mentees: %s", force)
    writeCount(site, anzahlAllerZurzeitBetreuendenMentoren, counts["active_mentors"],
               "Anzahl zurzeit betreuenden Mentoren: %s", force)
    return 0


if __name__ == "__main__":
    sys.exit(main())

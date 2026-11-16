import json, re, sys, urllib.parse, urllib.request, time
OUT, FIX = sys.argv[1], sys.argv[2]
CASES = [
 ("dewikipedia","Wikipedia:Fragen zur Wikipedia","week variable, timeout, two targets"),
 ("dewikipedia","Benutzer Diskussion:Lars2019","ALTER=0, ((Quartal:##)), timeout 60"),
 ("dewikipedia","Benutzer Diskussion:ElBe","three targets, one archive is a redirect to another subpage"),
 ("dewikipedia","Wikipedia:Bibliotheksrecherche/Anfragen","((Quartal:I))"),
 ("dewikipedia","Wikipedia:Bots/Anfragen","((Halbjahr))"),
 ("dewikipedia","Benutzer Diskussion:NatiSythen","((Monat:Kurz)), timeout"),
 ("dewikipedia","Portal:Luftfahrt/Überarbeiten","EBENE=3"),
 ("commons","Commons:สภากาแฟ","((half-year:i)), non-latin title"),
 ("commons","User talk:Gamemaster669","relative target '/Archiv' -> main namespace, refused"),
 ("enwikisource","Wikisource:Copyright discussions","TIMECOMPARE=resolved"),
 ("incubator","Incubator:Requests for deletion","incubator localization"),
 ("itwikipedia","Discussioni progetto:Coordinamento/Connettività","it localization, Italian signatures"),
 ("jawikipedia","ノート:Kaya (歌手)","ja localization, target in main namespace"),
 ("jawikipedia","利用者‐会話:TSE 014","template missing -> NoOptions"),
 ("meta","Meta:Requests for deletion","LEVEL=3, meta localization"),
 ("meta","User talk:XXBlackburnXx","AGE=0, ((quarter:I))"),
 ("viwikipedia","Thảo luận Thành viên:Veritas Sapientiae","vi localization, ((quarter))"),
 ("wikidata","Wikidata:Project chat","many sections, ((month:##)), timeout"),
]
HOSTS = {"dewikipedia":"de.wikipedia.org","commons":"commons.wikimedia.org","enwikisource":"en.wikisource.org",
         "incubator":"incubator.wikimedia.org","itwikipedia":"it.wikipedia.org","jawikipedia":"ja.wikipedia.org",
         "meta":"meta.wikimedia.org","viwikipedia":"vi.wikipedia.org","wikidata":"www.wikidata.org"}
UA = "archive-bot-test-fixtures/1.0 (Toolforge tool spbot; https://spbot.toolforge.org)"

blocks, key = {}, None
for line in open(OUT, encoding="utf-8"):
    if line.startswith("@@@@ new|"):
        key = tuple(line[9:].rstrip("\n").split("|", 1)); blocks[key] = []; continue
    if line.startswith("@@@@ "): key = None; continue
    if key: blocks[key].append(line.rstrip("\n"))

def slug(s):
    s = re.sub(r"[^\w]+", "_", s, flags=re.U).strip("_")
    return s[:60]

cases = []
for proj, title, why in CASES:
    lines = blocks[(proj, title)]
    run = next(re.search(r"(\d{4}-\d\d-\d\d) um (\d\d:\d\d)", l).groups() for l in lines if l.startswith("Bot run at"))
    now = f"{run[0]}T{run[1]}:30"
    exp = {"rows": [], "editComments": [], "redirects": {}, "mainNamespaceRefused": False, "error": None}
    color = ""
    for l in lines:
        m = re.match(r"\* Number of sections: '''(\d+)'''", l)
        if m: exp["numberOfSections"] = int(m.group(1))
        m = re.match(r"\* Number of sections to archive: '''(\d+)'''", l)
        if m: exp["numberToArchive"] = int(m.group(1))
        if l.startswith("|-") and not l.startswith("|-\n!"):
            color = "archive" if "ffcbcb" in l else "resolved" if "b9ffc5" in l else ""
        m = re.match(r"\| (\d+) \|\| (.*) \|\| ([\d.]+) \|\| (\d+) \|\| ([\d.]+|-) \|\| \[\[(.*)\|&rarr;\]\]$", l)
        if m:
            exp["rows"].append({"headline": m.group(2), "firstAge": float(m.group(3)), "signatures": int(m.group(4)),
                                "resolvedAge": None if m.group(5) == "-" else float(m.group(5)),
                                "target": m.group(6), "mark": color})
        if l.startswith("edit comment: "): exp["editComments"].append(l[len("edit comment: "):])
        m = re.match(r"\[\[(.*)\]\] is a redirect, archiving into \[\[(.*)\]\] instead", l)
        if m: exp["redirects"][m.group(1)] = m.group(2)
        if "Archiving into the (Main) namespace" in l: exp["mainNamespaceRefused"] = True
        m = re.match(r"Reason was: (.*?) \*\*\*$|Reason was: (.*)$", l)
        if m: exp["error"] = (m.group(1) or m.group(2)).strip()
    # revision that was current at run time
    q = {"action":"query","prop":"revisions","titles":title,"rvprop":"ids|timestamp|user|content","rvslots":"main",
         "rvlimit":"1","rvdir":"older","rvstart":f"{run[0]}T{run[1]}:00Z","format":"json","formatversion":"2"}
    url = f"https://{HOSTS[proj]}/w/api.php?" + urllib.parse.urlencode(q)
    data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60))
    rev = data["query"]["pages"][0]["revisions"][0]
    fname = f"{proj}__{slug(title)}.wiki"
    open(f"{FIX}/{fname}", "w", encoding="utf-8").write(rev["slots"]["main"]["content"])
    cases.append({"project": proj, "title": title, "why": why, "file": fname, "now": now,
                  "revid": rev["revid"], "lastEditTime": rev["timestamp"], "lastUser": rev["user"],
                  "source": f"https://{HOSTS[proj]}/w/index.php?oldid={rev['revid']}", "expected": exp})
    print(f"{proj:13} {title[:45]:45} rev {rev['revid']} {rev['timestamp']} {len(rev['slots']['main']['content']):7d} B rows={len(exp['rows'])} comments={len(exp['editComments'])} err={exp['error']}")
    time.sleep(0.5)
json.dump(cases, open(f"{FIX}/cases.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

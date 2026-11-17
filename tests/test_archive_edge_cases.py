"""
Invented edge cases: comments, <nowiki>, <pre> & co., unusual headings, options and
{{Erledigt}} variants.

Tests marked xfail(strict=True) document known bugs: they fail today. When a bug is
fixed the test passes, pytest reports XPASS as failure, and the marker must be removed.
"""
import pytest

from archive_resolved import core
from conftest import makeBot, makeDoc

# NOW = 2026-11-16 12:00 (conftest); with Alter=1 everything resolved on 2 Nov is due
OPTIONS = "{{Autoarchiv-Erledigt|Alter=1|Ziel='((Lemma))/Archiv/((Jahr))'}}\n"
SIG = "--A 10:00, 1. Nov. 2026 (CET)"
RESOLVED = "{{Erledigt|1=--A 10:00, 2. Nov. 2026 (CET)}}"
TARGET = "Benutzer Diskussion:Test/Archiv/2026"


def prepared(body, options=OPTIONS, project="dewikipedia"):
    doc = makeDoc(options + body, bot=makeBot(project))
    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    doc.prepareArchiving()
    return doc


def sections(doc):
    return [d.getTitleClear() for d in doc.listDiscussions]


def isResolved(body):
    return prepared(body).listDiscussions[0].getAgeByResolvedTemplate() > 0


def assertNothingLost(doc):
    """modifiedText + all archived slices == original text (in some order)."""
    archived = "".join(doc.archiveJobTextByTarget.values())
    assert len(doc.modifiedText) + len(archived) == len(doc.originalText)
    rest = doc.originalText
    for text in doc.archiveJobTextByTarget.values():
        for chunk in text.split("\n== "):
            assert chunk.lstrip("= ") in rest
    return archived


def balanced(text):
    return all(text.count(a) == text.count(b) for a, b in
               [("<!--", "-->"), ("<nowiki>", "</nowiki>"), ("<pre>", "</pre>"),
                ("<syntaxhighlight", "</syntaxhighlight>")])


# ---------------------------------------------------------------- {{Erledigt}} hidden in markup

@pytest.mark.parametrize("hidden", [
    "<!-- %s -->",
    "<!--\n%s\n-->",
    "<nowiki>%s</nowiki>",
    "<code>%s</code>",
    "<pre>%s</pre>",
])
def test_resolved_template_in_markup_is_ignored(hidden):
    assert not isResolved("== A ==\nq %s\n%s\n" % (SIG, hidden % RESOLVED))


@pytest.mark.parametrize("hidden", [
    '<pre style="color:red">%s</pre>',
    '<syntaxhighlight lang="wikitext">%s</syntaxhighlight>',
    '<source lang="wikitext">%s</source>',
    "<NOWIKI>%s</NOWIKI>",
    "<nowiki >%s</nowiki >",
])
def test_resolved_template_in_other_markup_is_ignored(hidden):
    assert not isResolved("== A ==\nq %s\n%s\n" % (SIG, hidden % RESOLVED))


def test_unclosed_comment_hides_the_rest():
    """MediaWiki hides everything after an unclosed <!--"""
    doc = prepared("== A ==\nq %s\n<!-- %s\n== B ==\nx\n" % (SIG, RESOLVED))
    assert sections(doc) == ["A"]
    assert not doc.hasWorkToDo()


def test_self_closing_nowiki_hides_nothing():
    doc = prepared("== A ==\nq <nowiki/> %s\n%s\n<nowiki />\n== B ==\nb\n" % (SIG, RESOLVED))
    assert sections(doc) == ["A", "B"]
    assert doc.hasWorkToDo()


def test_resolved_template_broken_by_nowiki_tag_is_ignored():
    assert not isResolved("== A ==\nq %s\n{{Erledigt<nowiki/>|1=--A 10:00, 2. Nov. 2026 (CET)}}\n" % SIG)


def test_resolved_template_without_timestamp_is_ignored():
    assert not isResolved("== A ==\nq %s\n{{Erledigt}}\n" % SIG)


@pytest.mark.parametrize("template", [
    "{{erledigt|1=--A 10:00, 2. Nov. 2026 (CET)}}",
    "{{ Erledigt | 1=--A 10:00, 2. Nov. 2026 (CET) }}",
    "{{Erledigt|--A 10:00, 2. Nov. 2026 (CET)}}",
    "{{Erledigt|1=--[[Benutzer:A|A]] ([[BD:A|D]]) 10:00, 2. Nov. 2026 (CET)}}",
    "{{Erledigt|1=Grund: doppelt. --A 10:00, 2. Nov. 2026 (CET)}}",
    "{{Erledigt|1=--A 10:00, 2. Nov. 2026 (CET)|2=Antwort gefunden}}",
    "{{Erledigt\n|1=--A 10:00, 2. Nov. 2026 (CET)\n}}",
])
def test_resolved_template_variants(template):
    assert isResolved("== A ==\nq %s\n%s\n" % (SIG, template))


@pytest.mark.parametrize("prefix", ["Vorlage:", "vorlage :", "Template:"])
def test_resolved_template_with_namespace_prefix(prefix):
    template = "{{%sErledigt|1=--A 10:00, 2. Nov. 2026 (CET)}}" % prefix
    assert isResolved("== A ==\nq %s\n%s\n" % (SIG, template))
    assert subst(template) == (":<small>Archivierung dieses Abschnittes wurde gewünscht von: "
                               "--A 10:00, 2. Nov. 2026 (CET)</small>")


def test_resolved_in_subsection_counts_for_section():
    doc = prepared("== A ==\nq %s\n=== A1 ===\n%s\n== B ==\nb\n" % (SIG, RESOLVED))
    assert sections(doc) == ["A", "B"]
    assert doc.archiveJobTextByTarget[TARGET] == "== A ==\nq %s\n=== A1 ===\n%s\n" % (SIG, RESOLVED)


def test_newest_resolved_template_counts():
    doc = prepared("== A ==\nq %s\n%s\n:neu --B 10:00, 15. Nov. 2026 (CET)\n"
                   "{{Erledigt|1=--A 10:00, 16. Nov. 2026 (CET)}}\n" % (SIG, RESOLVED))
    assert not doc.hasWorkToDo()


def test_resolved_in_the_future_is_not_archived():
    doc = prepared("== A ==\nq %s\n{{Erledigt|1=--A 10:00, 2. Nov. 2027 (CET)}}\n" % SIG)
    assert not doc.hasWorkToDo()


# ---------------------------------------------------------------- {{Nicht archivieren}}

@pytest.mark.parametrize("keep", [
    "{{Nicht archivieren}}",
    "{{nicht archivieren|bis=2030}}",
    "{{Nicht archivieren }}",
    "{{Vorlage:Nicht archivieren}}",
    "{{ vorlage : Nicht archivieren|bis=2030}}",
    "{{Template:Nicht archivieren}}",
    # also inside a comment (needed for the <!-- [[User:DoNotArchiveUntil]] --> variant on other wikis)
    "<!-- {{Nicht archivieren}} -->",
])
def test_do_not_archive(keep):
    doc = prepared("== A ==\n%s\nq %s\n%s\n" % (keep, SIG, RESOLVED))
    assert not doc.hasWorkToDo()


def test_do_not_archive_only_for_its_section():
    doc = prepared("== A ==\n{{Nicht archivieren}}\nq %s\n%s\n== B ==\nq %s\n%s\n" % (SIG, RESOLVED, SIG, RESOLVED))
    assert doc.archiveJobCounterByTarget == {TARGET: 1}
    assert doc.archiveJobTextByTarget[TARGET].startswith("== B ==")


# ---------------------------------------------------------------- headings

@pytest.mark.parametrize("heading, title", [
    ("== A = B ==", "A = B"),
    ("== A ===", "A ="),                 # MediaWiki: level 2, title "A ="
    ("==AB==", "AB"),
    ("== A ==   ", "A"),
    ("== A == <!-- Kommentar -->", "A"),
    ("== Ü ✓ 漢字 ==", "Ü ✓ 漢字"),
])
def test_heading_variants(heading, title):
    doc = prepared("%s\nq %s\n%s\n" % (heading, SIG, RESOLVED))
    assert sections(doc) == [title]
    assert doc.hasWorkToDo()


@pytest.mark.parametrize("heading", ["==A==", "==1=="])
def test_one_character_heading(heading):
    doc = prepared("== X ==\nq %s\n%s\n%s\nb\n" % (SIG, RESOLVED, heading))
    assert len(doc.listDiscussions) == 2


@pytest.mark.parametrize("line", [" == A ==", "=> Antwort", "== A", ":== A =="])
def test_not_a_heading(line):
    doc = prepared("== X ==\nq %s\n%s\n%s\nmehr\n" % (SIG, RESOLVED, line))
    assert sections(doc) == ["X"]
    assert doc.archiveJobTextByTarget[TARGET].endswith(line + "\nmehr\n")


def test_level_1_heading_ends_section_but_is_not_archived():
    doc = prepared("== A ==\nq %s\n%s\n= Neu =\ntext\n" % (SIG, RESOLVED))
    assert doc.modifiedText == OPTIONS + "= Neu =\ntext\n"


def test_text_after_last_section_is_archived_with_it():
    """Known limitation: there is no end marker for the last section, so categories,
    navigation templates etc. below it go to the archive."""
    body = "== A ==\nq %s\n%s\n\n[[Kategorie:Foo]]\n" % (SIG, RESOLVED)
    doc = prepared(body)
    assert doc.archiveJobTextByTarget[TARGET] == body
    assert doc.modifiedText == OPTIONS


@pytest.mark.parametrize("open_, close", [("<!--", "-->"), ("<nowiki>", "</nowiki>"), ("<pre>", "</pre>"),
                                         ('<syntaxhighlight lang="wikitext">', "</syntaxhighlight>"),
                                         ("<!--\n== Muster ==\n", "-->")])
def test_heading_inside_markup_is_not_a_section(open_, close):
    body = "== A ==\nq %s\n%s\n== Vorlage ==\n%s\n%s\n== B ==\nb\n" % (SIG, open_, close, RESOLVED)
    doc = prepared(body)
    assert sections(doc) == ["A", "B"]
    archived = assertNothingLost(doc)
    assert balanced(archived) and balanced(doc.modifiedText)


# ---------------------------------------------------------------- signatures

@pytest.mark.parametrize("utc, local, month", [
    ("23:30, 31. Okt. 2026 (UTC)", "00:30, 1. Nov. 2026 (CET)", "11"),   # winter time: +1 h
    ("22:30, 31. Jul. 2026 (UTC)", "00:30, 1. Aug. 2026 (CEST)", "08"),  # summer time: +2 h
])
def test_utc_signature_is_converted_to_local_time(utc, local, month):
    """dewiki signatures with "(UTC)" (users with a UTC preference) are Berlin time + 1/2 h."""
    options = "{{Autoarchiv-Erledigt|Alter=1|Ziel='((Lemma))/Archiv/((Jahr))/((Monat:##))'}}\n"
    docs = [prepared("== A ==\nq --A %s\n%s\n" % (sig, RESOLVED), options) for sig in (utc, local)]
    discs = [doc.listDiscussions[0] for doc in docs]
    assert discs[0].getFirstContributionAge() == pytest.approx(discs[1].getFirstContributionAge())
    assert list(docs[0].archiveJobTextByTarget) == list(docs[1].archiveJobTextByTarget) == [TARGET + "/" + month]


def test_utc_resolved_template_is_converted_to_local_time():
    options = "{{Autoarchiv-Erledigt|Alter=1|Ziel='((Lemma))/Archiv/((Jahr))/((Monat:##))'|Zeitvergleich=erledigt}}\n"
    doc = prepared("== A ==\nq %s\n{{Erledigt|1=--A 23:30, 31. Okt. 2026 (UTC)}}\n" % SIG, options)
    assert list(doc.archiveJobTextByTarget) == [TARGET + "/11"]


def test_signature_with_unknown_month_is_ignored():
    doc = prepared("== A ==\nq --A 10:00, 1. Foo 2026 (CET)\n%s\n" % RESOLVED)
    assert doc.listDiscussions[0].getNumberOfContributions() == 1   # only the one in {{Erledigt}}


@pytest.mark.parametrize("signature", ["--A 10:00, 1. November 2026", "--A 10:00 1. Nov. 2026 (CET)", "--A 1. Nov. 2026"])
def test_incomplete_signature_is_ignored(signature):
    doc = prepared("== A ==\nq %s\n" % signature)
    assert doc.listDiscussions[0].getNumberOfContributions() == 0


def test_timeout_uses_newest_signature():
    options = "{{Autoarchiv-Erledigt|Alter=1|Ziel='((Lemma))/Archiv/((Jahr))'|Zeitbeschränkung=10}}\n"
    old = "== Alt ==\nq --A 10:00, 1. Okt. 2026 (CEST)\n"
    active = "== Aktiv ==\nq --A 10:00, 1. Okt. 2026 (CEST)\n:a --B 10:00, 15. Nov. 2026 (CET)\n"
    doc = prepared(old + active, options)
    assert doc.archiveJobTextByTarget == {TARGET: old}


# ---------------------------------------------------------------- options

@pytest.mark.parametrize("options", [
    "{{Autoarchiv-Erledigt\n|Alter=1\n|Ziel='((Lemma))/Archiv/((Jahr))'\n}}\n",
    "{{Autoarchiv-Erledigt\n|Alter = 1 <!-- Tage -->\n|Ziel = '((Lemma))/Archiv/((Jahr))' \n}}\n",
    "{{autoarchiv-erledigt|Alter=1|Ziel=((Lemma))/Archiv/((Jahr))}}\n",
    "{{Vorlage:Autoarchiv-Erledigt|Alter=1|Ziel='((Lemma))/Archiv/((Jahr))'|Übersicht=[[Spezial:Präfixindex/{{FULLPAGENAME}}/Archiv|Archiv]]}}\n",
    "{{Autoarchiv-Erledigt|Ziel='((Lemma))/Archiv/((Jahr))'|Alter=1|Zeigen=Nein|aktuelles Archiv=x}}\n",
])
def test_option_template_variants(options):
    doc = prepared("== A ==\nq %s\n%s\n" % (SIG, RESOLVED), options)
    assert doc.thresholdAgeResolvedTemplate == 1.0
    assert list(doc.archiveJobTextByTarget) == [TARGET]


def test_first_option_template_wins():
    doc = prepared("== A ==\nq %s\n%s\n" % (SIG, RESOLVED),
                   OPTIONS + "{{Autoarchiv-Erledigt|Alter=99|Ziel=Anderes/Ziel}}\n")
    assert doc.archivingTargetPattern == "((Lemma))/Archiv/((Jahr))"


def test_option_template_below_the_sections():
    doc = prepared("== A ==\nq %s\n%s\n%s" % (SIG, RESOLVED, OPTIONS), "")
    assert doc.thresholdAgeResolvedTemplate == 1.0


@pytest.mark.parametrize("value", ["1,5", "eins", "1 Tag"])
def test_wrong_age(value):
    with pytest.raises(core.WrongOptions):
        prepared("== A ==\n", "{{Autoarchiv-Erledigt|Alter=%s|Ziel=X/Y}}\n" % value)


def test_negative_age_is_rejected():
    with pytest.raises(core.WrongOptions):
        prepared("== A ==\nq %s\n" % SIG, "{{Autoarchiv-Erledigt|Alter=-1|Ziel=X/Y}}\n")


@pytest.mark.parametrize("level", ["0", "-1", "7"])
def test_invalid_level_is_rejected(level):
    with pytest.raises(core.WrongOptions):
        prepared("== A ==\n", "{{Autoarchiv-Erledigt|Alter=1|Ziel=X/Y|Ebene=%s}}\n" % level)


@pytest.mark.parametrize("options, message", [
    ("Alter=1,5|Ziel=X/Y", "'ALTER' must be a number, not '1,5'."),
    ("Alter=|Ziel=X/Y", "'ALTER' must be a number, not ''."),
    ("Alter=-1|Ziel=X/Y", "'ALTER' must not be negative."),
    ("Alter=1|Ziel=X/Y|Ebene=zwei", "'EBENE' must be a number, not 'zwei'."),
    ("Alter=1|Ziel=X/Y|Ebene=0", "'EBENE' must be between 1 and 6."),
    ("Alter=1|Ziel=X/Y|Zeitbeschränkung=30d", "'ZEITBESCHRÄNKUNG' must be a number, not '30d'."),
    ("Alter=1|Ziel=X/Y|Zeitbeschränkung=-3", "'ZEITBESCHRÄNKUNG' must not be negative."),
])
def test_wrong_options_message(options, message):
    with pytest.raises(core.WrongOptions) as e:
        prepared("== A ==\n", "{{Autoarchiv-Erledigt|%s}}\n" % options)
    assert e.value.getMsg() == message


@pytest.mark.parametrize("options", ["Ebene=1", "Ebene=6", "Zeitbeschränkung=0", "Ebene=", "Zeitbeschränkung="])
def test_valid_border_values(options):
    prepared("== A ==\n", "{{Autoarchiv-Erledigt|Alter=1|Ziel=X/Y|%s}}\n" % options)


def test_age_zero_archives_resolved_sections_only():
    doc = prepared("== A ==\nq %s\n%s\n== B ==\nq %s\n" % (SIG, RESOLVED, SIG),
                   "{{Autoarchiv-Erledigt|Alter=0|Ziel='((Lemma))/Archiv/((Jahr))'}}\n")
    assert doc.archiveJobCounterByTarget == {TARGET: 1}
    assert doc.archiveJobTextByTarget[TARGET].startswith("== A ==")


# ---------------------------------------------------------------- {{Erledigt}} substitution in the archive

def subst(text):
    return makeDoc("").substSectionResolvedTempl(text)


def test_subst_two_templates():
    assert subst(RESOLVED + "\n{{Erledigt|1=--B 11:00, 3. Nov. 2026 (CET)}}") == (
        ":<small>Archivierung dieses Abschnittes wurde gewünscht von: --A 10:00, 2. Nov. 2026 (CET)</small>\n"
        ":<small>Archivierung dieses Abschnittes wurde gewünscht von: --B 11:00, 3. Nov. 2026 (CET)</small>")


@pytest.mark.parametrize("text", ["<!-- %s -->" % RESOLVED, "<nowiki>%s</nowiki>" % RESOLVED, "{{Erledigt}}"])
def test_subst_leaves_alone(text):
    assert subst(text) == text


@pytest.mark.parametrize("template", ["{{Erledigt\n|1=--A 10:00, 2. Nov. 2026 (CET)\n}}",
                                      "{{Erledigt|1=--A 10:00, 2. Nov. 2026 (CET)\n|2=Grund\n}}"])
def test_subst_multiline_template(template):
    assert "{{" not in subst(template)


def test_subst_empty_second_parameter():
    assert subst("{{Erledigt|1=--A 10:00, 2. Nov. 2026 (CET)|2=}}") == (
        ":<small>Archivierung dieses Abschnittes wurde gewünscht von: --A 10:00, 2. Nov. 2026 (CET)</small>")


# ---------------------------------------------------------------- section anchors in the edit summary

@pytest.mark.parametrize("heading, anchor", [
    ("[[:Datei:A.jpg]] und [[B|C]]", ":Datei:A.jpg_und_C"),
    ("''kursiv'' und '''fett'''", "kursiv_und_fett"),
    ("<s>alt</s> neu", "alt_neu"),
    ("<nowiki>{{Erledigt}}</nowiki>?", "{{Erledigt}}?"),
])
def test_anchor(heading, anchor):
    doc = prepared("== %s ==\nq %s\n%s\n" % (heading, SIG, RESOLVED))
    assert doc.archiveJobFirstTitleByTarget[TARGET] == anchor


@pytest.mark.parametrize("heading, anchor", [
    ("A <!-- x -->", "A"),
    ('<span style="color:red">rot</span>', "rot"),
    ("A<br />B", "AB"),
    ("x<ref>Beleg</ref>", "xBeleg"),
])
def test_anchor_without_comments_and_tags(heading, anchor):
    doc = prepared("== %s ==\nq %s\n%s\n" % (heading, SIG, RESOLVED))
    assert doc.archiveJobFirstTitleByTarget[TARGET] == anchor


# ---------------------------------------------------------------- whole invented page

INVENTED = """{{Autoarchiv-Erledigt|Alter=2|Ziel='((Lemma))/Archiv/((Jahr))/((Monat:Kurz))'|Ebene=2}}
<!-- Bitte neue Abschnitte unten anfügen.
{{Erledigt|1=--Muster 10:00, 1. Jan. 2020 (CET)}}
-->
{{Nicht archivieren|Hinweis oben}}

== Erledigt im Oktober ==
Frage --A 10:00, 1. Okt. 2026 (CEST)
:Antwort --B 11:00, 2. Okt. 2026 (CEST)
{{Erledigt|1=--A 12:00, 3. Okt. 2026 (CEST)}}

== Beispiel-Code ==
So geht das: <code>{{Erledigt|1=--~~~~}}</code> und <nowiki>{{Erledigt|1=--X 10:00, 1. Nov. 2026 (CET)}}</nowiki>
--C 10:00, 5. Nov. 2026 (CET)

== Erledigt im November mit Unterabschnitt ==
Frage --A 10:00, 4. Nov. 2026 (CET)
=== Nachtrag ===
noch was --B 10:00, 5. Nov. 2026 (CET)
{{Erledigt|1=--A 10:00, 6. Nov. 2026 (CET)}}

== Frisch erledigt ==
Frage --A 10:00, 15. Nov. 2026 (CET)
{{Erledigt|1=--A 10:00, 15. Nov. 2026 (CET)}}

== Bleibt ==
{{Nicht archivieren}}
Frage --A 10:00, 1. Sep. 2026 (CEST)
{{Erledigt|1=--A 10:00, 2. Sep. 2026 (CEST)}}
"""


def test_invented_page_end_to_end():
    bot = makeBot()
    title = "Benutzer Diskussion:Test"
    page = bot.site.page(title, INVENTED)
    doc = makeDoc(INVENTED, bot=bot, title=title)
    doc.findOptions()
    doc.divideIntoSlices()
    doc.examineDiscussions()
    doc.prepareArchiving()
    doc.executeArchiving()

    assert sections(doc) == ["Erledigt im Oktober", "Beispiel-Code", "Erledigt im November mit Unterabschnitt",
                             "Frisch erledigt", "Bleibt"]
    okt, nov = title + "/Archiv/2026/Okt", title + "/Archiv/2026/Nov"
    assert [t for t, _ in bot.site.saveLog] == [okt, nov, title]
    assert bot.site.page(okt).text.startswith("{{Archiv}}\n\n== Erledigt im Oktober ==\n")
    assert ":<small>Archivierung dieses Abschnittes wurde gewünscht von: --A 12:00, 3. Okt. 2026 (CEST)</small>" \
        in bot.site.page(okt).text
    novText = bot.site.page(nov).text
    assert "=== Nachtrag ===\nnoch was" in novText
    # the head of the page (options, comment with an example, {{Nicht archivieren}}) is untouched
    assert page.text.startswith(INVENTED[:INVENTED.index("== Erledigt im Oktober ==")])
    for kept in ("== Beispiel-Code ==", "== Frisch erledigt ==", "== Bleibt =="):
        assert kept in page.text
    assert "== Erledigt im Oktober ==" not in page.text
    assertNothingLost(doc)
    assert balanced(page.text) and balanced(novText)

"""Tests for archive-resolved-sych-bot-overview.py (FakeSite from conftest.py, nothing is written to a wiki)."""
import importlib.util
import os

import pytest
import pywikibot
from conftest import FakeSite

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "userscripts", "archive-resolved-sych-bot-overview.py")
spec = importlib.util.spec_from_file_location("sych_bot_overview", SCRIPT)
sych = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sych)
TITLE = sych.basePageToCopy[1]


@pytest.fixture
def sites(monkeypatch):
    """One FakeSite per (code, family); commons has the new text, the others the old one."""
    sites = {}

    def site(code, fam):
        if (code, fam) not in sites:
            sites[code, fam] = FakeSite()
            sites[code, fam].page(TITLE, "new" if code == "commons" else "old")
        return sites[code, fam]
    monkeypatch.setattr(pywikibot, "Site", site)
    monkeypatch.setattr(pywikibot, "stopme", lambda: None)
    monkeypatch.setattr(pywikibot, "handle_args", lambda: [])
    return sites


def copies(sites):
    return [site.page(TITLE) for (code, fam), site in sites.items() if code != "commons"]


def test_all_copies_are_updated(sites):
    assert sych.main() == 0
    assert len(copies(sites)) == len(sych.targetProjects)
    assert all(page.text == "new" and len(page.saves) == 1 for page in copies(sites))


def test_unchanged_copies_are_not_saved(sites):
    pywikibot.Site(code="meta", fam="meta").page(TITLE).text = "new"
    sych.main()
    assert sites["meta", "meta"].page(TITLE).saves == []


def test_dry_run(sites, monkeypatch):
    monkeypatch.setattr(pywikibot, "handle_args", lambda: ["-dryrun"])
    assert sych.main() == 0
    assert all(page.saves == [] for page in copies(sites))


@pytest.mark.parametrize("arg", ["--dryrun", "-dry-run", "-x"])
def test_unknown_argument(sites, monkeypatch, arg):
    monkeypatch.setattr(pywikibot, "handle_args", lambda: [arg])
    assert sych.main() == 2
    assert sites == {}


def test_one_failure_does_not_stop_the_others(sites):
    pywikibot.Site(code="de", fam="wikipedia").page(TITLE).saveError = TimeoutError("x")
    assert sych.main() == 1
    assert sum(len(page.saves) for page in copies(sites)) == len(sych.targetProjects) - 1


def test_missing_source_page_empties_nothing(sites):
    pywikibot.Site(code="commons", fam="commons").page(TITLE)._exists = False
    with pytest.raises(pywikibot.exceptions.NoPageError):
        sych.main()
    assert all(page.saves == [] for page in copies(sites))

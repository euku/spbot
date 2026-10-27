#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
	Tests for pers-bek-to-db-bot.py (check of the version history for irregular confirmations).
	pywikibot, pymysql and the database are replaced by stubs: nothing is written to a wiki or a DB.

	Run: pyvenv/bin/python -m unittest discover -s src/userscripts -p 'test_pers_bek*'
"""
import os
import re
import sys
import types
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pers-bek-to-db-bot.py")
BOT = "SpBot"


class PywikibotError(Exception):
	pass


class FakeSite:
	pages = {}  # title -> FakePage

	def user(self):
		return BOT


class FakePage:
	def __init__(self, site, title):
		self.titleText = title.replace("_", " ")
		self.text = ""
		self.revs = []  # newest first
		self.puts = []  # (text, summary)
		FakeSite.pages.setdefault(self.titleText, self)
		self.__dict__ = FakeSite.pages[self.titleText].__dict__

	def title(self):
		return self.titleText

	def exists(self):
		return self.text != "" or bool(self.revs)

	def get(self):
		return self.text

	def botMayEdit(self):
		return True

	def put(self, text, summary="", **kwargs):
		self.puts.append((text, summary))
		self.text = text

	def revisions(self, content=False, total=None):
		return iter(self.revs[:total])


def makePywikibotStub():
	pwb = types.ModuleType("pywikibot")
	pwb.Site = lambda *a, **k: FakeSite()
	pwb.Page = FakePage
	pwb.output = lambda text: None
	pwb.error = lambda text: None
	pwb.showDiff = lambda a, b: None
	pwb.handle_args = lambda: []
	pwb.exceptions = types.SimpleNamespace(Error=PywikibotError)
	textlib = types.ModuleType("pywikibot.textlib")
	textlib.replaceExcept = lambda text, old, new, exceptions: re.sub(old, new, text)
	pwb.textlib = textlib
	return pwb, textlib


def loadScript():
	"""executes the script without its start code ('# start here') with stubbed modules"""
	pwb, textlib = makePywikibotStub()
	pymysql = types.ModuleType("pymysql")
	pymysql.DatabaseError = type("DatabaseError", (Exception,), {})
	pymysql.IntegrityError = type("IntegrityError", (pymysql.DatabaseError,), {})
	botApi = types.ModuleType("bot_api")
	botApi.BotDatabase = None
	saved = {n: sys.modules.get(n) for n in ("pywikibot", "pywikibot.textlib", "pymysql", "bot_api")}
	sys.modules.update({"pywikibot": pwb, "pywikibot.textlib": textlib, "pymysql": pymysql, "bot_api": botApi})
	try:
		with open(SCRIPT, encoding="utf-8") as f:
			source = f.read().split("\n# start here")[0]
		mod = types.ModuleType("pers_bek_to_db_bot")
		exec(compile(source, SCRIPT, "exec"), mod.__dict__)
	finally:
		for n, m in saved.items():
			if m is None:
				sys.modules.pop(n, None)
			else:
				sys.modules[n] = m
	return mod


class FakeDB:
	def __init__(self):
		self.confirmations = []

	def get_user_by_name(self, name):
		return (name, "id-" + name)

	def get_cf_count_by_confirmed(self, userID):
		return 5

	def add_confirmation(self, certifierID, certifiedID, comment, timestamp):
		self.confirmations.append((certifierID, certifiedID))
		return True

	def has_confirmed(self, certifierID, certifiedID):
		return (certifierID, certifiedID) in self.confirmations

	def get_user_list_with_confirmations(self):
		return []

	def get_latest_user_list_with_confirmations(self):
		return []

	def close_connections(self):
		pass


def ack(certifier, certified):
	return "{{Wikipedia:Persönliche Bekanntschaften/neue Bestätigung|Bestätiger=%s|Bestätigter=%s|Kommentar=kenne ich|Zeit=20:40, 26. Okt. 2026 (CET)}}\n" % (certifier, certified)


def rev(user, revid, text, userhidden=False):
	return types.SimpleNamespace(user=user, revid=revid, text=text, userhidden=userhidden)


class TestNormalizeUser(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.m = loadScript()

	def test_normalize(self):
		self.assertEqual(self.m.normalizeUser("amrei-Marie"), "Amrei-Marie")
		self.assertEqual(self.m.normalizeUser(" Hestia_Trismegista "), "Hestia Trismegista")
		self.assertEqual(self.m.normalizeUser("A  B"), "A B")


class TestFindACKAuthors(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.m = loadScript()

	def setUp(self):
		FakeSite.pages = {}
		self.page = FakePage(FakeSite(), "test")

	def authors(self, revs):
		self.page.revs = revs
		acks = self.m.divideIntoTasks(revs[0].text)[1]
		return self.m.findACKAuthors(self.page, acks)

	def test_own_entry(self):
		a = self.authors([rev("Amrei-Marie", 2, ack("Amrei-Marie", "Slashpub")), rev(BOT, 1, "")])
		self.assertEqual(a[("Amrei-Marie", "Slashpub")], ("Amrei-Marie", 2))

	def test_foreign_entry_among_own(self):
		a = self.authors([
			rev("Mallory", 4, ack("Amrei-Marie", "Slashpub") + ack("Amrei-Marie", "Fake")),
			rev("Amrei-Marie", 3, ack("Amrei-Marie", "Slashpub")),
			rev(BOT, 2, ""),
			rev("Old", 1, ack("Old", "Y")),
		])
		self.assertEqual(a[("Amrei-Marie", "Fake")], ("Mallory", 4))
		self.assertEqual(a[("Amrei-Marie", "Slashpub")], ("Amrei-Marie", 3))

	def test_certified_changed_by_other_user(self):
		a = self.authors([
			rev("Mallory", 3, ack("Amrei-Marie", "Mallory")),
			rev("Amrei-Marie", 2, ack("Amrei-Marie", "Slashpub")),
			rev(BOT, 1, ""),
		])
		self.assertEqual(a[("Amrei-Marie", "Mallory")], ("Mallory", 3))

	def test_comment_edit_keeps_original_author(self):
		edited = ack("Amrei-Marie", "Slashpub").replace("kenne ich", "geändert")
		a = self.authors([
			rev("Mallory", 3, edited),
			rev("Amrei-Marie", 2, ack("Amrei-Marie", "Slashpub")),
			rev(BOT, 1, ""),
		])
		self.assertEqual(a[("Amrei-Marie", "Slashpub")], ("Amrei-Marie", 2))

	def test_underscores_and_lowercase(self):
		a = self.authors([rev("Hestia Trismegista", 2, ack("hestia_Trismegista", "X")), rev(BOT, 1, "")])
		self.assertEqual(a[("Hestia Trismegista", "X")], ("Hestia Trismegista", 2))

	def test_hidden_user(self):
		a = self.authors([rev("", 2, ack("A", "B"), userhidden=True), rev(BOT, 1, "")])
		self.assertEqual(a[("A", "B")], (None, 2))

	def test_leftover_older_than_last_bot_run(self):
		a = self.authors([
			rev("C", 4, ack("A", "B") + ack("C", "D")),
			rev(BOT, 3, ack("A", "B")),
			rev("A", 2, ack("A", "B")),
			rev(BOT, 1, ""),
		])
		self.assertEqual(a[("A", "B")], ("A", 2))
		self.assertEqual(a[("C", "D")], ("C", 4))

	def test_beyond_limit_takes_oldest_checked(self):
		self.m.maxRevisionsToCheck = 2
		try:
			a = self.authors([rev("X", 3, ack("A", "B")), rev("A", 2, ack("A", "B")), rev(BOT, 1, "")])
		finally:
			self.m.maxRevisionsToCheck = 50
		self.assertEqual(a[("A", "B")], ("A", 2))


class TestRun(unittest.TestCase):
	def setUp(self):
		self.m = loadScript()
		self.db = FakeDB()
		self.m.BotDatabase = lambda: self.db
		FakeSite.pages = {}
		self.workPage = FakePage(FakeSite(), self.m.workList)
		self.reportPage = FakePage(FakeSite(), self.m.reportPage)
		self.reportPage.text = "alter Inhalt\n"

	def run_bot(self, revs):
		self.workPage.revs = revs
		self.workPage.text = revs[0].text
		self.m.PBBot().run()

	def test_regular_confirmation(self):
		self.run_bot([rev("Amrei-Marie", 2, ack("Amrei-Marie", "Slashpub")), rev(BOT, 1, "")])
		self.assertEqual(self.db.confirmations, [("id-Amrei-Marie", "id-Slashpub")])
		self.assertEqual(self.workPage.puts[0][0], "")
		self.assertNotIn("IRREGULÄRE", self.workPage.puts[0][1])
		self.assertEqual(self.reportPage.puts, [])

	def test_irregular_confirmation_refused_and_reported(self):
		self.run_bot([
			rev("Mallory", 3, ack("Amrei-Marie", "Slashpub") + ack("Amrei-Marie", "Fake")),
			rev("Amrei-Marie", 2, ack("Amrei-Marie", "Slashpub")),
			rev(BOT, 1, ""),
		])
		# only the regular one is stored
		self.assertEqual(self.db.confirmations, [("id-Amrei-Marie", "id-Slashpub")])
		# both entries are removed, the summary names the irregular one explicitly
		text, summary = self.workPage.puts[0]
		self.assertEqual(text, "")
		self.assertTrue(summary.startswith("In Datenbank übertragen: IRREGULÄRE Bestätigungen: "))
		self.assertIn("[[:User:Amrei-Marie|Amrei-Marie]] → [[:User:Fake|Fake]] (eingetragen von Mallory, abgelehnt", summary)
		# report on the talk page, appended to the old content
		self.assertEqual(len(self.reportPage.puts), 1)
		report = self.reportPage.puts[0][0]
		self.assertTrue(report.startswith("alter Inhalt\n"))
		self.assertIn("eingetragen von [[:User:Mallory|Mallory]] ([[Spezial:Diff/3|Diff]])", report)
		self.assertNotIn("Slashpub", report)

	def test_irregular_summary_survives_shortening(self):
		names = ["Benutzer mit langem Namen %d" % i for i in range(8)]
		text = "".join(ack("Amrei-Marie", n) for n in names) + ack("Amrei-Marie", "Fake")
		self.run_bot([
			rev("Mallory", 3, text),
			rev("Amrei-Marie", 2, "".join(ack("Amrei-Marie", n) for n in names)),
			rev(BOT, 1, ""),
		])
		summary = self.workPage.puts[0][1]
		self.assertIn("Bestätigungen: 8", summary)
		self.assertIn("[[:User:Fake|Fake]] (eingetragen von Mallory", summary)

	def test_exempt_user_may_confirm_for_others(self):
		self.run_bot([rev("Euku", 2, ack("Amrei-Marie", "Slashpub")), rev(BOT, 1, "")])
		self.assertEqual(self.db.confirmations, [("id-Amrei-Marie", "id-Slashpub")])
		self.assertEqual(self.reportPage.puts, [])

	def test_hidden_author_is_irregular(self):
		self.run_bot([rev("", 2, ack("A", "B"), userhidden=True), rev(BOT, 1, "")])
		self.assertEqual(self.db.confirmations, [])
		self.assertIn("(versteckter Benutzer)", self.reportPage.puts[0][0])

	def test_dry_run_saves_nothing(self):
		self.m.DONOTSAVE = True
		self.m.DONOTSAVEDB = True
		self.run_bot([rev("Mallory", 2, ack("A", "B")), rev(BOT, 1, "")])
		self.assertEqual(self.workPage.puts, [])
		self.assertEqual(self.reportPage.puts, [])
		self.assertEqual(self.db.confirmations, [])


if __name__ == "__main__":
	unittest.main()

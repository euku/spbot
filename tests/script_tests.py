#!/usr/bin/python3
"""Test that each script can be compiled and executed."""
#
# (C) Pywikibot team, 2014-2022
#
# Distributed under the terms of the MIT license.
#
import os
import sys
import unittest
from contextlib import suppress
from importlib import import_module

from pywikibot.tools import has_module
from tests import join_root_path, unittest_print
from tests.aspects import DefaultSiteTestCase, MetaTestCaseClass, PwbTestCase
from tests.utils import execute_pwb


ci_test_run = os.environ.get('PYWIKIBOT_TESTS_RUNNING', '0') == '1'
scripts_path = join_root_path('scripts')
framework_scripts = ['shell']

# These dependencies are not always the package name which is in setup.py.
# Here, the name given to the module which will be imported is required.
script_deps = {
    'commons_information': ['mwparserfromhell'],
    'patrol': ['mwparserfromhell'],
    'weblinkchecker': ['memento_client'],
}


def check_script_deps(script_name):
    """Detect whether all dependencies are installed."""
    if script_name in script_deps:
        for package_name in script_deps[script_name]:
            if not has_module(package_name):
                unittest_print(
                    "{} depends on {}, which isn't available"
                    .format(script_name, package_name))
                return False
    return True


failed_dep_script_set = {name for name in script_deps
                         if not check_script_deps(name)}

# scripts which cannot be tested
unrunnable_script_set = set()


def list_scripts(path, exclude=None):
    """Return list of scripts in given path."""
    scripts = [name[0:-3] for name in os.listdir(path)  # strip '.py'
               if name.endswith('.py')
               and not name.startswith('_')  # skip __init__.py and _*
               and name != exclude]
    return scripts


script_list = ['login'] + list_scripts(scripts_path,
                                       exclude='login.py') + framework_scripts

script_input = {
    'interwiki': 'Test page that should not exist\n',
    'misspelling': 'q\n',
    'pagefromfile': 'q\n',
    'replace': 'foo\nbar\n\n\n',  # match, replacement,
                                  # Enter to begin, Enter for default summary.
    'shell': '\n',  # exits on end of stdin
    'solve_disambiguation': 'Test page\nq\n',
    'upload':
        'https://upload.wikimedia.org/wikipedia/commons/'
        '8/80/Wikipedia-logo-v2.svg\n\n\n',
}

auto_run_script_list = [
    'blockpageschecker',
    'category_redirect',
    'checkimages',
    'clean_sandbox',
    'delinker',
    'login',
    'misspelling',
    'noreferences',
    'nowcommons',
    'parser_function_count',
    'patrol',
    'revertbot',
    'shell',
    'unusedfiles',
    'upload',
    'watchlist',
    'welcome',
]

# Expected result for no arguments
# Some of these are not pretty, but at least they are informative
# and not backtraces starting deep in the pywikibot package.
no_args_expected_results = {
    # TODO: until done here, remember to set editor = None in user-config.py
    'change_pagelang': 'No -setlang parameter given',
    'checkimages': 'Execution time: 0 seconds',
    'dataextend': 'No item page specified',
    'harvest_template': 'ERROR: Please specify',
    # script_input['interwiki'] above lists a title that should not exist
    'interwiki': 'does not exist. Skipping.',
    'login': 'Logged in on ',
    'pagefromfile': 'Please enter the file name',
    'parser_function_count': 'Hold on, this will need some time.',
    'replace': 'Press Enter to use this automatic message',
    'replicate_wiki':
        'error: the following arguments are required: destination',
    'shell': ('>>> ', 'Welcome to the'),
    'speedy_delete': "does not have 'delete' right for site",
    'transferbot': 'Target site not different from source site',
    'unusedfiles': ('Working on', None),
    'version': 'Pywikibot: [',
    'watchlist': 'Retrieving watchlist',

    # The following auto-run and typically can't be validated,
    # however these strings are very likely to exist within
    # the timeout of 5 seconds.
    'revertbot': 'Fetching new batch of contributions',
    'upload': 'ERROR: Upload error',
}

# skip test if result is unexpected in this way
skip_on_results = {
    'speedy_delete': 'No user is logged in on site'  # T301555
}


enable_autorun_tests = (
    os.environ.get('PYWIKIBOT_TEST_AUTORUN', '0') == '1')


def collector(loader=unittest.loader.defaultTestLoader):
    """Load the default tests."""
    # Note: Raising SkipTest during load_tests will
    # cause the loader to fallback to its own
    # discover() ordering of unit tests.

    if unrunnable_script_set:
        unittest_print('Skipping execution of unrunnable scripts:\n  {!r}'
                       .format(unrunnable_script_set))

    if not enable_autorun_tests:
        unittest_print('Skipping execution of auto-run scripts '
                       '(set PYWIKIBOT_TEST_AUTORUN=1 to enable):\n  {!r}'
                       .format(auto_run_script_list))

    tests = (['test__login']
             + ['test_' + name
                 for name in sorted(script_list)
                 if name != 'login'
                 and name not in unrunnable_script_set
                ])

    test_list = ['tests.script_tests.TestScriptHelp.' + name
                 for name in tests]

    tests = (['test__login']
             + ['test_' + name
                 for name in sorted(script_list)
                 if name != 'login'
                 and name not in failed_dep_script_set
                 and name not in unrunnable_script_set
                 and (enable_autorun_tests or name not in auto_run_script_list)
                ])

    test_list += ['tests.script_tests.TestScriptSimulate.' + name
                  for name in tests]

    tests = (['test__login']
             + ['test_' + name
                 for name in sorted(script_list)
                 if name != 'login'
                 and name not in failed_dep_script_set
                 and name not in unrunnable_script_set
                 and (enable_autorun_tests or name not in auto_run_script_list)
                ])

    test_list += ['tests.script_tests.TestScriptGenerator.' + name
                  for name in tests]

    tests = loader.loadTestsFromNames(test_list)
    suite = unittest.TestSuite()
    suite.addTests(tests)
    return suite


def load_tests(loader=unittest.loader.defaultTestLoader,
               tests=None, pattern=None):
    """Load the default modules."""
    return collector(loader)


def import_script(script_name: str):
    """Import script for coverage only (T305795)."""
    if not ci_test_run:
        return
    if script_name in framework_scripts:
        prefix = 'pywikibot.scripts.'
    else:
        prefix = 'scripts.'
    import_module(prefix + script_name)


class TestScriptMeta(MetaTestCaseClass):

    """Test meta class."""

    def __new__(cls, name, bases, dct):
        """Create the new class."""
        def test_execution(script_name, args=None):
            if args is None:
                args = []

            is_autorun = ('-help' not in args
                          and script_name in auto_run_script_list)

            def test_skip_script(self):
                raise unittest.SkipTest(
                    'Skipping execution of auto-run scripts (set '
                    'PYWIKIBOT_TEST_AUTORUN=1 to enable) "{}"'
                    .format(script_name))

            def test_script(self):
                global_args_msg = \
                    'For global options use -help:global or run pwb'
                global_args = ['-pwb_close_matches:1']

                cmd = global_args + [script_name] + args
                data_in = script_input.get(script_name)
                if isinstance(self._timeout, bool):
                    do_timeout = self._timeout
                else:
                    do_timeout = script_name in self._timeout
                timeout = 5 if do_timeout else None

                stdout, error = None, None
                if self._results:
                    if isinstance(self._results, dict):
                        error = self._results.get(script_name)
                    else:
                        error = self._results
                    if isinstance(error, tuple):
                        stdout, error = error

                test_overrides = {}
                if not hasattr(self, 'net') or not self.net:
                    test_overrides['pywikibot.Site'] = 'lambda *a, **k: None'

                # run the script
                result = execute_pwb(cmd, data_in, timeout=timeout,
                                     error=error, overrides=test_overrides)

                err_result = result['stderr']
                out_result = result['stdout']
                stderr_other = err_result.splitlines()

                if result['exit_code'] == -9:
                    unittest_print(' killed', end='  ')

                skip_result = self._skip_results.get(script_name)
                if skip_result and skip_result in err_result:
                    self.skipTest(skip_result)

                if error:
                    self.assertIn(error, err_result)
                    exit_codes = [0, 1, 2, -9]

                elif not is_autorun:
                    if not stderr_other:
                        self.assertIn(global_args_msg, out_result)
                    else:
                        self.assertIn('Use -help for further information.',
                                      stderr_other)
                        self.assertNotIn('-help', args)
                    exit_codes = [0]

                else:
                    # auto-run
                    # returncode is 1 if the process is killed
                    exit_codes = [0, 1, -9]
                    if not out_result and not err_result:
                        unittest_print(' auto-run script unresponsive after '
                                       '{} seconds'.format(timeout), end=' ')
                    elif 'SIMULATION: edit action blocked' in err_result:
                        unittest_print(' auto-run script simulated edit '
                                       'blocked', end=' ')
                    else:
                        unittest_print(
                            ' auto-run script stderr within {} seconds: {!r}'
                            .format(timeout, err_result), end='  ')
                    unittest_print(' exit code: {}'
                                   .format(result['exit_code']), end=' ')

                self.assertNotIn('Traceback (most recent call last)',
                                 err_result)
                self.assertNotIn('deprecated', err_result.lower())

                # If stdout doesn't include global help..
                if global_args_msg not in out_result:
                    # Specifically look for deprecated
                    self.assertNotIn('deprecated', out_result.lower())
                    # But also complain if there is any stdout
                    if stdout is not None and out_result:
                        self.assertIn(stdout, out_result)
                    else:
                        self.assertIsEmpty(out_result)

                self.assertIn(result['exit_code'], exit_codes)
                sys.stdout.flush()

            if not enable_autorun_tests and is_autorun:
                return test_skip_script
            return test_script

        arguments = dct['_arguments']

        for script_name in script_list:
            import_script(script_name)

            # force login to be the first, alphabetically, so the login
            # message does not unexpectedly occur during execution of
            # another script.
            # unrunnable script tests are disabled by default in load_tests()

            if script_name == 'login':
                test_name = 'test__login'
            else:
                test_name = 'test_' + script_name

            cls.add_method(dct, test_name,
                           test_execution(script_name, arguments.split()),
                           'Test running {} {}.'
                           .format(script_name, arguments))

            if script_name in dct['_expected_failures']:
                dct[test_name] = unittest.expectedFailure(dct[test_name])
            elif script_name in dct['_allowed_failures']:
                dct[test_name] = unittest.skip(
                    '{} is in _allowed_failures list'
                    .format(script_name))(dct[test_name])
            elif script_name in failed_dep_script_set \
                    and arguments == '-simulate':
                dct[test_name] = unittest.skip(
                    '{} has dependencies; skipping'
                    .format(script_name))(dct[test_name])

            # Disable test by default in pytest
            if script_name in unrunnable_script_set:
                # flag them as an expectedFailure due to py.test (T135594)
                dct[test_name] = unittest.expectedFailure(dct[test_name])
                dct[test_name].__test__ = False

        return super().__new__(cls, name, bases, dct)


class TestScriptHelp(PwbTestCase, metaclass=TestScriptMeta):

    """Test cases for running scripts with -help.

    All scripts should not create a Site for -help, so net = False.
    """

    net = False

    # Here come scripts requiring and missing dependencies, that haven't been
    # fixed to output -help in that case.
    _expected_failures = {'version'}
    _allowed_failures = []

    _arguments = '-help'
    _results = None
    _skip_results = {}
    _timeout = False


class TestScriptSimulate(DefaultSiteTestCase, PwbTestCase,
                         metaclass=TestScriptMeta):

    """Test cases for running scripts with -siumlate.

    This class sets the 'user' attribute on every test, thereby ensuring
    that the test runner has a username for the default site, and so that
    Site.login() is called in the test runner, which means that the scripts
    run in pwb can automatically login using the saved cookies.
    """

    login = True

    _expected_failures = {
        'catall',          # stdout user interaction
        'upload',          # raises custom ValueError
    }

    _allowed_failures = [
        'disambredir',
        'misspelling',   # T94681
        'watchlist',     # T77965
    ]

    _arguments = '-simulate'
    _results = no_args_expected_results
    _skip_results = skip_on_results
    _timeout = auto_run_script_list


class TestScriptGenerator(DefaultSiteTestCase, PwbTestCase,
                          metaclass=TestScriptMeta):

    """Test cases for running scripts with a generator."""

    login = True

    _expected_failures = {
        'add_text',
        'archivebot',
        'category',
        'change_pagelang',
        'claimit',
        'dataextend',
        'data_ingestion',
        'delete',
        'djvutext',
        'download_dump',
        'harvest_template',
        'interwiki',
        'listpages',
        'movepages',
        'pagefromfile',
        'protect',
        'redirect',
        'reflinks',
        'replicate_wiki',
        'speedy_delete',
        'template',
        'templatecount',
        'transferbot',
    }

    _allowed_failures = [
        'basic',
        'commonscat',
        'commons_information',
        'coordinate_import',
        'cosmetic_changes',
        'fixing_redirects',
        'illustrate_wikidata',
        'image',
        'imagetransfer',
        'interwikidata',
        'newitem',
        'replace',
        'solve_disambiguation',
        'touch',
        'weblinkchecker',
    ]

    _arguments = '-simulate -page:Foo -always'
    _results = ("Working on 'Foo", 'Script terminated successfully')
    _skip_results = {}
    _timeout = True


if __name__ == '__main__':  # pragma: no cover
    with suppress(SystemExit):
        unittest.main()

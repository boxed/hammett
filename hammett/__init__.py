import sys
import os
from collections import defaultdict
from os import listdir
from os.path import (
    abspath,
    isdir,
    join,
    split,
)

import hammett.mark as mark


__version__ = '0.7.1'

from hammett.colors import (
    YELLOW,
    RED,
    RESET_COLOR,
    GREEN,
)

MISSING = object()

_orig_print = print


class Globals:
    def __init__(self):
        self.source_location = None
        self.modules = None
        self.orig_cwd = os.getcwd()
        self.verbose = False
        self.durations = False
        self.terminal_width = None
        self.results = None
        self.settings = {}
        self.fail_fast = False
        self.quiet = False
        self.drop_into_debugger = False
        self.durations_results = []
        self.disable_assert_analyze = False
        self.output = []
        self.result_db = None
        self.should_stop = False
        
    def reset(self):
        self.__init__()

    def get_log_without_colors(self):
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', ''.join([
            str(args) + end
            for args, end, flush in self.output
        ]))


g = Globals()


def print(arg='', end='\n', flush=False):
    g.output.append((arg, end, flush))
    if g.quiet:
        return
    _orig_print(arg, end=end, flush=flush, file=sys.__stdout__)


def fixture(*args, **kwargs):
    args = list(args)

    def decorator(f):
        from hammett.impl import register_fixture
        register_fixture(f, *args, **kwargs)
        return f

    if len(args) == 1:
        if callable(args[0]):
            f = args[0]
            args[:] = args[1:]
            return decorator(f)
        else:
            return decorator
    else:
        assert not args
        return decorator


# This is a deprecated feature in pytest, but we'll keep it here for now. pytest-django uses it for example.
def yield_fixture(*args, **kwargs):
    return fixture(*args, **kwargs)


def raises(expected_exception, match=None):
    from hammett.impl import RaisesContext
    return RaisesContext(expected_exception, match=match)


def fail(message):
    raise RuntimeError(message)


class Option:
    def __init__(self):
        self.verbose = g.verbose


class Config:
    def __init__(self):
        self.option = Option()

    def getvalue(self, _):
        return None


class Request:
    current_fixture_setup = None

    def __init__(self, scope, parent, function=None):
        self.scope = scope
        self.function = function
        self.parent = parent
        self.additional_fixtures_wanted = set()
        self.keywords = {}
        self.fixturenames = set()
        self.finalizers = []
        self.fixture_results = {}
        self.funcargnames = []

        self.config = Config()

    def hammett_add_fixture_result(self, result):
        from hammett.impl import fixture_scope
        if fixture_scope.get(self.current_fixture_setup, 'function') != self.scope:
            self.parent.hammett_add_fixture_result(result)
        else:
            self.fixture_results[self.current_fixture_setup] = result

    def hammett_get_existing_result(self, name):
        try:
            return self.fixture_results[name]
        except KeyError:
            if self.parent:
                return self.parent.hammett_get_existing_result(name)
            return MISSING

    def teardown(self):
        for x in reversed(self.finalizers):
            x()

    @property
    def node(self):
        return self

    def addfinalizer(self, x):
        assert Request.current_fixture_setup is not None
        from hammett.impl import fixture_scope
        if fixture_scope.get(Request.current_fixture_setup, 'function') != self.scope:
            self.parent.addfinalizer(x)
        else:
            self.finalizers.append(x)

    def get_closest_marker(self, s):
        # TODO: fall back to the parent markers
        try:
            markers = self.function.hammett_markers
        except AttributeError:
            return None

        for marker in markers:
            if marker.name == s:
                return marker

        return None

    def getfixturevalue(self, s):
        return self.additional_fixtures_wanted.add(s)


def parse_markers(markers):
    if markers is None:
        return None

    def parse_one(s):
        if '[' not in s:
            return s, None

        assert s.endswith(']')
        base_name, _, name_plus_end_bracket = s.partition('[')
        return base_name, name_plus_end_bracket[:-1]

    # So far let's do something stupidly simple
    markers = markers.split(';')
    return dict(parse_one(m.strip()) for m in markers)


def guess_modules_and_source_path():
    this_dir = os.getcwd().split(os.sep)[-1]
    if isdir('lib'):
        return listdir('lib'), 'lib'
    elif isdir('src'):
        return listdir('src'), 'src'

    if isdir(this_dir):
        return [this_dir], '.'
    elif isdir(this_dir.replace('-', '_')):
        return [this_dir.replace('-', '_')], '.'
    elif isdir(this_dir.replace(' ', '_')):
        return [this_dir.replace(' ', '_')], '.'
    elif isdir(this_dir.replace('-', '')):
        return [this_dir.replace('-', '')], '.'
    elif isdir(this_dir.replace(' ', '')):
        return [this_dir.replace(' ', '')], '.'
    return [], '.'


def handle_dir(result, d):
    for root, dirs, files in os.walk(d):
        files = [
            f for f in files
            if f.endswith('__tests.py') or (f.startswith('test_') and f.endswith('.py'))
        ]
        result.extend(join(root, x) for x in files)


def collect_files(filenames):
    result = []
    if filenames is None:
        handle_dir(result, f'tests{os.sep}')
        handle_dir(result, f'test{os.sep}')
        for module_name in g.modules:
            handle_dir(result, join(g.source_location, module_name))
    else:
        for filename in filenames:
            if os.path.exists(filename):
                if os.path.isdir(filename):
                    handle_dir(result, filename)
                else:
                    result.append(filename)
            else:
                # This is a symbol, module or function/class? Try module first.
                symbol_path = join(g.source_location, filename.replace('.', os.sep))
                if os.path.exists(symbol_path + '.py'):
                    result.append(symbol_path + '__tests.py')

    return result


def collect_file_data(path):
    data = {}
    for root, dirs, files in os.walk(path):
        dirs[:] = [x for x in dirs if not x.startswith('.') and x not in ['venv', 'env', '__pycache__']]
        for filename in files:
            if not filename.endswith('.py'):
                continue
            full_path = join(root, filename)
            if full_path.startswith(f'.{os.sep}'):
                full_path = full_path[2:]
            data[full_path] = os.stat(full_path).st_mtime_ns
    return data


DB_VERSION = 1
DB_FILENAME = '.hammett-db'


def write_result_db(results):
    """
    The results database is a simple pickled dict with some keys:

    db_version: the version so we can change the format and throw away an old db if needed
    test_results: dict from filename -> (dict from test_name -> dict(stdout=str, stderr=str, status=str))
    file_data: dict filename -> nanosecond modification date
    """
    results['db_version'] = DB_VERSION
    from pickle import dump
    with open(DB_FILENAME, 'wb') as f:
        dump(results, f)


def new_result_db():
    return dict(
        db_version=DB_VERSION,
        test_results=defaultdict(dict),
        file_data=None,
    )


def read_result_db():
    from pickle import load
    try:
        with open(DB_FILENAME, 'rb') as f:
            results = load(f)
            if results['db_version'] != DB_VERSION:
                raise FileNotFoundError()
    except FileNotFoundError:
        return new_result_db()
    return results


def drop_cache_for_filename(result_db, filename):
    try:
        del result_db['test_results'][filename]
    except KeyError:
        pass


def update_result_db(result_db, new_file_data):
    if result_db['file_data'] is None:
        result_db['file_data'] = new_file_data
        assert not result_db['test_results']
        return result_db

    # Clear out test results when the test file or the tested module has changed
    old_file_data = result_db['file_data']
    clear_all_non_module_tests = False
    for filename, modification_time in old_file_data.items():
        if filename in new_file_data and modification_time != new_file_data[filename]:
            if filename.endswith('__tests.py') or filename.startswith('test_'):
                # The test has been changed
                drop_cache_for_filename(result_db, filename)
            else:
                # The module has been changed so translate the filename to the possible test files
                drop_cache_for_filename(result_db, filename[:-(len('.py'))] + '__tests.py')
                _, filename_only = split(filename)
                drop_cache_for_filename(result_db, f"tests{os.sep}{filename[:-(len('.py'))]}" + '__tests.py')
                clear_all_non_module_tests = True
                # TODO: this doesn't clear the db for module__function__tests.py

    if clear_all_non_module_tests:
        from pathlib import Path
        non_module_filenames = [x for x in result_db['test_results'].keys() if Path(x).stem.startswith('test_')]
        for x in non_module_filenames:
            del result_db['test_results'][x]

    result_db['file_data'] = new_file_data


def finish():
    for x in g.result_db['test_results'].values():
        for y in x.values():
            g.results[y['status']] += 1


def main(verbose=False, fail_fast=False, quiet=False, filenames=None, drop_into_debugger=False, match=None, durations=False, markers=None, disable_assert_analyze=False, module_unload=False, cwd=None):
    import sys
    if sys.version_info[:2] < (3, 6):
        print('hammett requires python 3.6 or later')
        exit(999)

    sys.modules['pytest'] = sys.modules['hammett']

    markers = parse_markers(markers)

    clean_up_sys_path = False

    if cwd is None:
        cwd = os.getcwd()
    cwd = abspath(cwd)
    g.orig_cwd = cwd
    os.chdir(cwd)

    if cwd not in sys.path:
        sys.path.insert(0, cwd)
        clean_up_sys_path = True

    from hammett.impl import should_stop
    g.reset()
    
    g.results = dict(success=0, failed=0, skipped=0, abort=0)
    g.verbose = verbose
    g.fail_fast = fail_fast
    g.quiet = quiet
    g.drop_into_debugger = drop_into_debugger
    g.durations = durations
    g.disable_assert_analyze = disable_assert_analyze

    from hammett.impl import read_settings, load_plugins
    read_settings()

    g.source_location = g.settings.get('source_location', '.')
    g.modules = g.settings.get('modules')
    if g.modules is None:
        m, s = guess_modules_and_source_path()
        g.source_location = g.source_location or s
        g.modules = m

    g.result_db = read_result_db()
    update_result_db(g.result_db, collect_file_data(g.source_location))
    write_result_db(g.result_db)

    filenames = collect_files(filenames)
    if not filenames:
        print('No tests found.')
        print('''You might need to add `modules` and `source_location` item under [hammett] in setup.cfg  like:

[hammett]
modules=
    foo
    bar
source_location=.
''')
        return 3

    plugins_loaded = False
    from os.path import split, sep

    session_request = Request(scope='session', parent=None)

    for test_filename in sorted(filenames):
        dirname, filename = split(test_filename)

        import importlib.util
        import sys
        if dirname.startswith(f'.{os.sep}'):
            dirname = dirname[2:]

        module_name = f'{dirname.replace(sep, ".")}.{filename.replace(".py", "")}'
        if module_name in sys.modules:
            del sys.modules[module_name]

        cache_filename = join(dirname, filename)
        if cache_filename in g.result_db['test_results']:
            continue

        # We do this here because if all test results are up to date, we want to avoid loading slow plugins!
        if not plugins_loaded:
            load_plugins()
            plugins_loaded = True

        spec = importlib.util.spec_from_file_location(module_name, test_filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            print(f'Failed to load module {module_name}:')
            import traceback
            print(traceback.format_exc())
            g.results['abort'] += 1
            break

        module_request = Request(scope='module', parent=session_request)

        module_markers = getattr(module, 'pytestmark', [])
        if not isinstance(module_markers, list):
            module_markers = [module_markers]

        from hammett.impl import execute_test_function
        for name, f in list(module.__dict__.items()):
            if g.results['abort']:
                break
            if name.startswith('test_') and callable(f):
                for m in module_markers:
                    f = m(f)

                if match is not None:
                    if match not in name:
                        continue

                if markers is not None:
                    keep = False
                    for f_marker in getattr(f, 'hammett_markers', []):
                        if f_marker.name in markers:
                            arg = markers[f_marker.name]
                            if arg is not None:
                                assert len(f_marker.args) == 1, 'hammett only supports filtering on single arguments to markers right now'
                                if str(f_marker.args[0]) == arg:
                                    keep = True
                                    break
                            else:
                                keep = True
                                break
                    if not keep:
                        continue

                execute_test_function(module_name + '.' + name, f, module_request)
            if should_stop():
                break

        module_request.teardown()

        if module_unload:
            del sys.modules[module_name]

        if should_stop():
            break

    session_request.teardown()

    if not g.verbose:
        print()

    finish()

    color = GREEN
    if g.results['skipped']:
        color = YELLOW
    if g.results['failed']:
        color = RED

    if clean_up_sys_path:
        del sys.path[0]

    if g.durations:
        limit = 10
        print()
        print(f'--- {limit} slowest tests ---')
        g.durations_results.sort(key=lambda x: x[1], reverse=True)
        for name, time, _ in g.durations_results[:10]:
            print(f'{time}   {name}')

        print()
        print(f'--- {limit} slowest startup times for tests ---')
        print('Note: startup times might be shared cost so might show up unfairly')
        g.durations_results.sort(key=lambda x: x[2], reverse=True)
        for name, _, startup_time in g.durations_results[:10]:
            print(f'{startup_time}   {name}')

        print()

    print(f'{color}{g.results["success"]} succeeded, {g.results["failed"]} failed, {g.results["skipped"]} skipped{RESET_COLOR}')
    os.chdir(g.orig_cwd)

    if g.results['abort']:
        write_result_db(g.result_db)
        return 2

    write_result_db(g.result_db)
    return 1 if g.results['failed'] else 0


def hookimpl(*_, **__):
    print("WARNING: hookimpl is not implemented in hammett")
    return lambda f: f


def main_cli(args=None):
    if args is None:
        args = sys.argv[1:]
    from argparse import ArgumentParser
    parser = ArgumentParser(prog='hammett')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False)
    parser.add_argument('-x', dest='fail_fast', action='store_true', default=False)
    parser.add_argument('-q', dest='quiet', action='store_true', default=False)
    parser.add_argument('-k', dest='match', default=None)
    parser.add_argument('-m', dest='markers', default=None)
    parser.add_argument('--durations', dest='durations', action='store_true', default=False)
    parser.add_argument('--no-assert-analyze', dest='disable_assert_analyze', action='store_true', default=False)
    parser.add_argument('--pdb', dest='drop_into_debugger', action='store_true', default=False)
    parser.add_argument(dest='filenames', nargs='*')
    args = parser.parse_args(args)

    return main(
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        quiet=args.quiet,
        filenames=args.filenames or None,
        drop_into_debugger=args.drop_into_debugger,
        match=args.match,
        durations=args.durations,
        markers=args.markers,
        disable_assert_analyze=args.disable_assert_analyze,
    )


if __name__ == '__main__':
    exit(main_cli())

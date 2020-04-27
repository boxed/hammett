import sys
import os

import hammett.mark as mark


__version__ = '0.5.0'


MISSING = object()

_orig_print = print
_orig_cwd = os.getcwd()

_verbose = False
_durations = False
_terminal_width = None
results = None
settings = {}
_fail_fast = False
_quiet = False
_drop_into_debugger = False
_durations_results = []
_disable_assert_analyze = False


def print(*args, **kwargs):
    if _quiet:
        return
    _orig_print(*args, **kwargs, file=sys.__stdout__)


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

        class Option:
            def __init__(self):
                self.verbose = _verbose

        class Config:
            def __init__(self):
                self.option = Option()

            def getvalue(self, _):
                return None

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


def main(verbose=False, fail_fast=False, quiet=False, filenames=None, drop_into_debugger=False, match=None, durations=False, markers=None, disable_assert_analyze=False, module_unload=False):
    import sys
    if sys.version_info[:2] < (3, 7):
        print('hammett requires python 3.7 or later')
        exit(999)

    sys.modules['pytest'] = sys.modules['hammett']

    markers = parse_markers(markers)

    clean_up_sys_path = False
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
        clean_up_sys_path = True

    from hammett.impl import should_stop

    global _fail_fast, _verbose, _quiet, results, _drop_into_debugger, _durations, _markers, _disable_assert_analyze

    results = dict(success=0, failed=0, skipped=0, abort=0)
    _verbose = verbose
    _fail_fast = fail_fast
    _quiet = quiet
    _drop_into_debugger = drop_into_debugger
    _durations = durations
    _disable_assert_analyze = disable_assert_analyze

    if filenames is None:
        from os.path import (
            exists,
            join,
        )
        if not exists('tests') and not exists('test'):
            print('No tests found')
            return 1

        filenames = []
        for root, dirs, files in os.walk('tests/'):
            filenames.extend(join(root, x) for x in files)
        for root, dirs, files in os.walk('test/'):
            filenames.extend(join(root, x) for x in files)

    from hammett.impl import read_settings
    read_settings()
    from os.path import split, sep

    session_request = Request(scope='session', parent=None)

    for test_filename in filenames:
        dirname, filename = split(test_filename)
        if not filename.startswith('test_') or not filename.endswith('.py'):
            continue

        import importlib.util
        import sys
        module_name = f'{dirname.replace(sep, ".")}.{filename.replace(".py", "")}'
        if module_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(module_name, test_filename)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
        else:
            module = sys.modules[module_name]
        try:
            spec.loader.exec_module(module)
        except Exception:
            print(f'Failed to load module {module_name}:')
            import traceback
            print(traceback.format_exc())
            results['abort'] += 1
            break

        module_request = Request(scope='module', parent=session_request)

        module_markers = getattr(module, 'pytestmark', [])
        if not isinstance(module_markers, list):
            module_markers = [module_markers]

        from hammett.impl import execute_test_function
        for name, f in list(module.__dict__.items()):
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

    if not _verbose:
        print()
    import colorama
    color = colorama.Fore.GREEN
    if results['skipped']:
        color = colorama.Fore.YELLOW
    if results['failed']:
        color = colorama.Fore.RED

    if clean_up_sys_path:
        del sys.path[0]

    if _durations:
        limit = 10
        print()
        print(f'--- {limit} slowest tests ---')
        _durations_results.sort(key=lambda x: x[1], reverse=True)
        for name, time, _ in _durations_results[:10]:
            print(f'{time}   {name}')

        print()
        print(f'--- {limit} slowest startup times for tests ---')
        print('Note: startup times might be shared cost so might show up unfairly')
        _durations_results.sort(key=lambda x: x[2], reverse=True)
        for name, _, startup_time in _durations_results[:10]:
            print(f'{startup_time}   {name}')

        print()

    print(f'{color}{results["success"]} succeeded, {results["failed"]} failed, {results["skipped"]} skipped{colorama.Style.RESET_ALL}')
    if results['abort']:
        return 2

    return 1 if results['failed'] else 0


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

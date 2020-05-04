import sys
import os
from os.path import (
    abspath,
    exists,
    join,
)

import hammett.mark as mark


__version__ = '0.6.0'


MISSING = object()

_orig_print = print


class Globals:
    def __init__(self):
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
                self.verbose = g.verbose

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


def main(verbose=False, fail_fast=False, quiet=False, filenames=None, drop_into_debugger=False, match=None, durations=False, markers=None, disable_assert_analyze=False, module_unload=False, cwd=None):
    import sys
    if sys.version_info[:2] < (3, 7):
        print('hammett requires python 3.7 or later')
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

    def handle_dir(result, d):
        for root, dirs, files in os.walk(d):
            files = [
                f for f in files
                if f.startswith('test_') and f.endswith('.py')
            ]
            result.extend(join(root, x) for x in files)

    if filenames is None:
        if not exists('tests') and not exists('test'):
            print('No tests found')
            return 1

        filenames = []

        handle_dir(filenames, 'tests/')
        handle_dir(filenames, 'test/')
    else:
        orig_filenames = filenames
        filenames = []

        for filename in orig_filenames:
            if os.path.isdir(filename):
                handle_dir(filenames, filename)
            else:
                filenames.append(filename)

    from hammett.impl import read_settings
    read_settings()
    from os.path import split, sep

    session_request = Request(scope='session', parent=None)

    for test_filename in sorted(filenames):
        dirname, filename = split(test_filename)

        import importlib.util
        import sys
        module_name = f'{dirname.replace(sep, ".")}.{filename.replace(".py", "")}'
        if module_name in sys.modules:
            del sys.modules[module_name]

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
    import colorama
    color = colorama.Fore.GREEN
    if g.results['skipped']:
        color = colorama.Fore.YELLOW
    if g.results['failed']:
        color = colorama.Fore.RED

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

    print(f'{color}{g.results["success"]} succeeded, {g.results["failed"]} failed, {g.results["skipped"]} skipped{colorama.Style.RESET_ALL}')
    os.chdir(g.orig_cwd)

    if g.results['abort']:
        return 2

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

import sys
import os

import hammett.mark as mark


__version__ = '0.3.0'

MISSING = object()

_orig_stdout = sys.stdout
_orig_stderr = sys.stderr
_orig_print = print
_orig_cwd = os.getcwd()

_verbose = False
results = None
settings = {}
_fail_fast = False
_quiet = False


def print(*args, **kwargs):
    if _quiet:
        return
    _orig_print(*args, **kwargs)


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


def should_stop():
    return _fail_fast and (results['failed'] or results['abort'])


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


def should_skip(_f):
    if not hasattr(_f, 'hammett_markers'):
        return False

    for marker in _f.hammett_markers:
        if marker.name == 'skip':
            return True

    return False


def analyze_assert(tb):
    # grab assert source line
    try:
        with open(tb.tb_frame.f_code.co_filename) as f:
            source = f.read().split('\n')
    except FileNotFoundError:
        try:
            with open(os.path.join(_orig_cwd, tb.tb_frame.f_code.co_filename)) as f:
                source = f.read().split('\n')
        except FileNotFoundError:
            print(f'Failed to analyze assert statement: file not found. Most likely there was a change of current directory.')
            return

    line_no = tb.tb_frame.f_lineno - 1
    relevant_source = source[line_no]

    # if it spans multiple lines grab them all
    while not relevant_source.strip().startswith('assert '):
        line_no -= 1
        relevant_source = source[line_no] + '\n' + relevant_source

    import ast
    try:
        assert_statement = ast.parse(relevant_source.strip()).body[0]
    except SyntaxError:
        print('Failed to analyze assert statement (SyntaxError)')
        return

    # We only analyze further if it's a comparison
    if assert_statement.test.__class__.__name__ != 'Compare':
        return

    # ...and if the left side is a function call
    if assert_statement.test.left.__class__.__name__ != 'Call':
        return

    print()
    print('--- Assert components ---')
    from astunparse import unparse
    left = eval(unparse(assert_statement.test.left), tb.tb_frame.f_globals, tb.tb_frame.f_locals)
    print('left:')
    print(f'   {left!r}')
    right = eval(unparse(assert_statement.test.comparators), tb.tb_frame.f_globals, tb.tb_frame.f_locals)
    print('right:')
    print(f'   {right!r}')


def run_test(_name, _f, _module_request, **kwargs):
    if should_skip(_f):
        results['skipped'] += 1
        return

    import colorama
    from io import StringIO
    from hammett.impl import register_fixture

    req = Request(scope='function', parent=_module_request, function=_f)

    def request():
        return req

    register_fixture(request, autouse=True)
    del request

    hijacked_stdout = StringIO()
    hijacked_stderr = StringIO()

    if _verbose:
        print(_name + '...', end='', flush=True)
    try:
        from hammett.impl import (
            dependency_injection,
            fixtures,
        )

        sys.stdout = hijacked_stdout
        sys.stderr = hijacked_stderr

        dependency_injection(_f, fixtures, kwargs, request=req)

        sys.stdout = _orig_stdout
        sys.stderr = _orig_stderr

        if _verbose:
            print(f' {colorama.Fore.GREEN}Success{colorama.Style.RESET_ALL}')
        else:
            print(f'{colorama.Fore.GREEN}.{colorama.Style.RESET_ALL}', end='', flush=True)
        results['success'] += 1
    except KeyboardInterrupt:
        sys.stdout = _orig_stdout
        sys.stderr = _orig_stderr

        print()
        print('ABORTED')
        global _fail_fast
        _fail_fast = True
        results['abort'] += 1
    except:
        sys.stdout = _orig_stdout
        sys.stderr = _orig_stderr

        print(colorama.Fore.RED)
        if not _verbose:
            print()
        print('Failed:', _name)
        print()

        import traceback
        print(traceback.format_exc())

        print()
        if hijacked_stdout.getvalue():
            print(colorama.Fore.YELLOW)
            print('--- stdout ---')
            print(hijacked_stdout.getvalue())

        if hijacked_stderr.getvalue():
            print(colorama.Fore.RED)
            print('--- stderr ---')
            print(hijacked_stderr.getvalue())

        print(colorama.Style.RESET_ALL)

        if not _quiet:
            import traceback
            type, value, tb = sys.exc_info()
            while tb.tb_next:
                tb = tb.tb_next

            print('--- Local variables ---')
            for k, v in tb.tb_frame.f_locals.items():
                print(f'{k}:')
                try:
                    print('   ', repr(v))
                except Exception as e:
                    print(f'   Error getting local variable repr: {e}')

            if type == AssertionError:
                analyze_assert(tb)

        results['failed'] += 1

    # Tests can change this which breaks everything. Reset!
    os.chdir(_orig_cwd)
    req.teardown()


def execute_parametrize(_name, _f, _stack, _module_request, **kwargs):
    if not _stack:
        param_names = [f'{k}={v}' for k, v in kwargs.items()]
        _name = f'{_name}[{", ".join(param_names)}]'
        return run_test(_name, _f, _module_request=_module_request, **kwargs)

    names, param_list = _stack[0]
    names = [x.strip() for x in names.split(',')]
    for params in param_list:
        if not isinstance(params, (list, tuple)):
            params = [params]
        execute_parametrize(_name, _f, _stack[1:], _module_request, **{**dict(zip(names, params)), **kwargs})
        if should_stop():
            break


def execute_test_function(_name, _f, module_request):
    if getattr(_f, 'hammett_parametrize_stack', None):
        return execute_parametrize(_name, _f, _f.hammett_parametrize_stack, module_request)
    else:
        return run_test(_name, _f, module_request)


def read_settings():
    from configparser import (
        ConfigParser,
        NoSectionError,
    )
    config_parser = ConfigParser()
    config_parser.read('setup.cfg')
    try:
        settings.update(dict(config_parser.items('hammett')))
    except NoSectionError:
        return

    # load plugins
    if 'plugins' not in settings:
        return

    class EarlyConfig:
        def addinivalue_line(self, name, doc):
            pass

        def getini(self, name):
            return None

    early_config = EarlyConfig()

    class Parser:
        def parse_known_args(self, *args):
            class Fake:
                pass
            s = Fake()
            s.itv = True
            s.ds = settings['django_settings_module']
            s.dc = None
            s.version = False
            s.help = False
            return s

    parser = Parser()

    import importlib
    for x in settings['plugins'].strip().split('\n'):
        plugin = importlib.import_module(x + '.plugin')
        try:
            plugin.pytest_load_initial_conftests(early_config=early_config, parser=parser, args=[])
            plugin.pytest_configure()
        except Exception:
            print(f'Loading plugin {x} failed: ')
            import traceback
            print(traceback.format_exc())
            results['abort'] += 1
            return
        importlib.import_module(x + '.fixtures')


def main(verbose=False, fail_fast=False, quiet=False, filenames=None):
    import sys
    sys.modules['pytest'] = sys.modules['hammett']

    global _fail_fast, _verbose, _quiet, results

    results = dict(success=0, failed=0, skipped=0, abort=0)
    _verbose = verbose
    _fail_fast = fail_fast
    _quiet = quiet

    if filenames is None:
        from os.path import (
            exists,
            join,
        )
        if not exists('tests'):
            print('No tests found')
            return 1

        filenames = []
        for root, dirs, files in os.walk('tests/'):
            filenames.extend(join(root, x) for x in files)

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
        spec = importlib.util.spec_from_file_location(module_name, test_filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
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

        for name, f in list(module.__dict__.items()):
            if name.startswith('test_') and callable(f):
                for m in module_markers:
                    f = m(f)

                execute_test_function(module_name + '.' + name, f, module_request)
            if should_stop():
                break

        module_request.teardown()

        del sys.modules[module_name]

        if should_stop():
            break

    session_request.teardown()

    if not _verbose:
        print()
    print(f'{results["success"]} succeeded, {results["failed"]} failed, {results["skipped"]} skipped')
    if results['abort']:
        return 2

    return 1 if results['failed'] else 0


def main_cli(args=None):
    if args is None:
        args = sys.argv[1:]
    from argparse import ArgumentParser
    parser = ArgumentParser(prog='hammett')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False)
    parser.add_argument('-x', dest='fail_fast', action='store_true', default=False)
    parser.add_argument('-q', dest='quiet', action='store_true', default=False)
    parser.add_argument(dest='filenames', nargs='*')
    args = parser.parse_args(args)

    return main(verbose=args.verbose, fail_fast=args.fail_fast, quiet=args.quiet, filenames=args.filenames or None)


if __name__ == '__main__':
    exit(main_cli())

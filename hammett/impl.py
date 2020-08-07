import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Optional
from unittest import SkipTest
from datetime import (
    datetime,
    timedelta,
)
from hammett import fixtures as built_in_fixtures

import hammett
from hammett.colors import (
    GREEN,
    RED,
    YELLOW,
    MAGENTA,
    RESET_COLOR,
)


class RaisesContext(object):
    def __init__(self, expected_exception, match):
        self.expected_exception = expected_exception
        self.excinfo = None
        self.match = match

    def __enter__(self):
        self.excinfo = ExceptionInfo()
        return self.excinfo

    def __exit__(self, *tp):
        __tracebackhide__ = True
        if tp[0] is None:
            assert False, f'Did not raise {self.expected_exception}'
        if self.match:
            import re
            assert re.match(self.match, str(tp[1]))
        self.excinfo.value = tp[1]
        self.excinfo.type = tp[0]
        suppress_exception = issubclass(self.excinfo.type, self.expected_exception)
        return suppress_exception


class ExceptionInfo:
    def __init__(self):
        self.type = None
        self.value = None

    def __str__(self):
        return f'<ExceptionInfo: type={self.type} value={self.value}'

    def __repr__(self):
        return str(self)


fixtures = {}
auto_use_fixtures = set()
fixture_scope = {}


def fixture_function_name(f):
    r = f.__name__
    if r == '<lambda>':
        import inspect
        r = inspect.getsource(f)
    return r


# TODO: store args
def register_fixture(fixture, *args, autouse=False, scope='function'):
    if scope == 'class':
        # hammett does not support class based tests
        return
    assert scope != 'package', 'Package scope is not supported at this time'

    name = fixture_function_name(fixture)
    # pytest uses shadowing.. I don't like it but I guess we have to follow that?
    # assert name not in fixtures, 'A fixture with this name is already registered'
    if hammett.g.verbose and name in fixtures and name != 'request':
        hammett.print(f'{fixture} shadows {fixtures[name]}')
    if autouse:
        auto_use_fixtures.add(name)
    assert scope in ('function', 'class', 'module', 'package', 'session')
    fixture_scope[name] = scope
    fixtures[name] = fixture


for fixture_name, fixture in built_in_fixtures.__dict__.items():
    if not fixture_name.startswith('_'):
        register_fixture(fixture)


def pick_keys(kwargs, params):
    return {
        k: v
        for k, v in kwargs.items()
        if k in params
    }


class FixturesUnresolvableException(Exception):
    pass


_params_of_cache = {}


def params_of(f):
    if f not in _params_of_cache:
        import inspect
        _params_of_cache[f] = set(
            x.name
            for x in inspect.signature(f).parameters.values()
            if x.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        )
    return _params_of_cache[f]


def _teardown_yield_fixture(fixturefunc, it):
    """Executes the teardown of a fixture function by advancing the iterator after the
    yield and ensure the iteration ends (if not it means there is more than one yield in the function)"""
    try:
        next(it)
    except StopIteration:
        pass
    else:
        hammett.print(f"yield_fixture {fixturefunc} function has more than one 'yield'")
        exit(1)


def call_fixture_func(fixturefunc, request, kwargs):
    # TODO: this fixture crashes for some reason, blacklist it for now
    if fixturefunc.__name__ == '_dj_autoclear_mailbox':
        return None
    existing_result = request.hammett_get_existing_result(fixture_function_name(fixturefunc))
    if existing_result is not hammett.MISSING:
        return existing_result

    import inspect
    import functools

    from hammett import Request
    Request.current_fixture_setup = fixture_function_name(fixturefunc)

    res = fixturefunc(**kwargs)

    request.hammett_add_fixture_result(res)

    yieldctx = inspect.isgenerator(res)
    if yieldctx:
        it = fixturefunc(**kwargs)
        res = next(it)
        finalizer = functools.partial(_teardown_yield_fixture, fixturefunc, it)
        request.addfinalizer(finalizer)

    Request.current_fixture_setup = None

    return res


def dependency_injection(f, fixtures, orig_kwargs, request):
    fixtures = fixtures.copy()
    f_params = params_of(f)
    params_by_name = {
        name: params_of(fixture)
        for name, fixture in fixtures.items()
        # prune the fixture list based on what f needs
        if name in f_params or name in auto_use_fixtures or name == 'request'
    }

    def add_fixture(kwargs, name, indent=0):
        if name in kwargs:
            return

        params = params_of(fixtures[name])
        for param in params:
            add_fixture(kwargs, param, indent+1)
        params_by_name[name] = params

    kwargs = {}
    while params_by_name:
        reduced = False
        for name, params in list(params_by_name.items()):
            # If we have a dependency that we have pruned, unprune it
            for param in params:
                if param not in kwargs:
                    if param in fixtures:
                        params_by_name[param] = params_of(fixtures[param])
                        reduced = True
                        break
            # If we can resolve this dependency fully
            if params.issubset(set(kwargs.keys())):
                assert name not in kwargs
                kwargs[name] = call_fixture_func(fixtures[name], request, pick_keys(kwargs, params))
                if request is not None:
                    request.fixturenames.add(name)
                    for x in request.additional_fixtures_wanted:
                        add_fixture(kwargs, x)
                reduced = True
                del params_by_name[name]
        if not reduced:
            raise FixturesUnresolvableException(f'Could not resolve fixtures for {f.__name__} any more.\nUnresolved:\n   {params_by_name}.\nAvailable dependencies:\n     {kwargs.keys()}\nFixtures:\n    {fixtures}')

    if request is not None:
        request.fixturenames = set(kwargs.keys())
    # prune again, to get rid of auto use fixtures that f doesn't take
    kwargs = {k: v for k, v in kwargs.items() if k in f_params}
    return f, {**kwargs, **orig_kwargs}


def dependency_injection_and_execute(f, fixtures, orig_kwargs, request):
    f, kwargs = dependency_injection(f, fixtures, orig_kwargs, request)
    return f(**kwargs)


def should_stop():
    return hammett.g.should_stop


def should_skip(_f):

    try:
        for marker in _f.hammett_markers:
            if marker.name == 'skip':
                return True
    except AttributeError:
        pass

    return False


def indent(s, levels=1):
    ind = '    ' * levels
    return '\n'.join(ind + x for x in s.split('\n'))


def pretty_format(x, _indent=0):
    indent = '    ' * _indent
    result = ''
    if isinstance(x, dict):
        if not x:
            return '{}'
        result += '{\n'
        for k, v in x.items():
            result += f'{indent}    {k!r}: {pretty_format(v, _indent + 1)},\n'
        result += f'{indent}}}'
        return result
    elif isinstance(x, list):
        if not x:
            return '[]'
        result += '[\n'
        for v in x:
            result += f'{indent}    {pretty_format(v, _indent + 1)},\n'
        result += f'{indent}]'
        return result
    elif isinstance(x, tuple):
        if not x:
            return '(,)'
        result += '(\n'
        for v in x:
            result += f'{indent}    {pretty_format(v, _indent + 1)},\n'
        result += f'{indent})'
        return result
    else:
        return repr(x)


def build_feedback_for_exception():
    type, value, tb = sys.exc_info()
    while tb.tb_next:
        tb = tb.tb_next

    result = []

    local_variables = tb.tb_frame.f_locals
    if local_variables:
        result.append('--- Local variables ---')
        for k, v in sorted(local_variables.items()):
            result.append(f'{k}:')
            try:
                result.append(indent(pretty_format(v)))
            except Exception as e:
                result.append(f'   Error getting local variable repr: {e}')

    if type == AssertionError:
        result.append(analyze_assert(tb))

    return '\n'.join(result)


DIFF_STRING_SIZE_CUTOFF = 100


def analyze_assert(tb):
    if hammett.g.disable_assert_analyze:
        return ''

    result = []

    # grab assert source line
    try:
        with open(tb.tb_frame.f_code.co_filename) as f:
            source = f.read().split('\n')
    except FileNotFoundError:
        try:
            with open(os.path.join(hammett.g.orig_cwd, tb.tb_frame.f_code.co_filename)) as f:
                source = f.read().split('\n')
        except FileNotFoundError:
            result.append('Failed to analyze assert statement: file not found. Most likely there was a change of current directory.')
            return '\n'.join(result)

    line_no = tb.tb_frame.f_lineno - 1
    relevant_source = source[line_no]

    # if it spans multiple lines grab them all
    while line_no and not relevant_source.strip().startswith('assert '):
        line_no -= 1
        relevant_source = source[line_no] + '\n' + relevant_source

    if not relevant_source.strip().startswith('assert '):
        result.append('Failed to analyze assert statement (Did not find the assert)')
        return '\n'.join(result)

    import ast
    try:
        assert_statement = ast.parse(relevant_source.strip()).body[0]
    except SyntaxError:
        try:
            # grab one more line after the the one where we got an exception, and try again
            relevant_source += '\n' + source[tb.tb_frame.f_lineno]
            assert_statement = ast.parse(relevant_source.strip()).body[0]
        except SyntaxError:
            result.append('Failed to analyze assert statement (SyntaxError)')
            return '\n'.join(result)

    # TODO: we should also analyze single values
    # We only analyze further if it's a comparison
    if assert_statement.test.__class__.__name__ != 'Compare':
        return '\n'.join(result)

    result.append('')
    result.append('--- Assert components ---')
    from astunparse import unparse
    try:
        left = eval(unparse(assert_statement.test.left), tb.tb_frame.f_globals, tb.tb_frame.f_locals)
        result.append('left:')
        result.append(indent(pretty_format(left)))
        right = eval(unparse(assert_statement.test.comparators), tb.tb_frame.f_globals, tb.tb_frame.f_locals)
    except Exception as e:
        result.append(f'Failed to analyze assert statement ({type(e)}: {e})')
        return '\n'.join(result)
    result.append('right:')
    result.append(indent(pretty_format(right)))
    if isinstance(left, str) and isinstance(right, str) and len(left) > DIFF_STRING_SIZE_CUTOFF and len(right) > DIFF_STRING_SIZE_CUTOFF and '\n' in left:
        result.append('')
        result.append('--- Diff of left and right assert components ---')
        left_lines = left.split('\n')
        right_lines = right.split('\n')
        from difflib import unified_diff
        for line in unified_diff(left_lines, right_lines, fromfile='expected', tofile='actual', lineterm=''):
            color = ''
            if line:
                color = {
                    '+': GREEN,
                    '-': RED,
                    '@': MAGENTA,
                }.get(line[0], '')
            result.append(f'{color}{line}{RESET_COLOR}')

    return '\n'.join(result)


SKIPPED = 'skipped'
SUCCESS = 'success'
FAILED = 'failed'


MESSAGES = {
    SKIPPED: dict(
        v=f' {YELLOW}Skipped{RESET_COLOR}',
        s=f'{YELLOW}s{RESET_COLOR}',
    ),
    SUCCESS: dict(
        v=f' {GREEN}Success{RESET_COLOR}',
        s=f'{GREEN}.{RESET_COLOR}',
    ),
    FAILED: dict(
        v=f' {RED}Failed{RESET_COLOR}',
        s=f'{RED}F{RESET_COLOR}',
    ),
}
MSG_SKIPPED_VERBOSE = f' {YELLOW}Skipped{RESET_COLOR}'
MSG_SKIPPED = f'{YELLOW}s{RESET_COLOR}'
MSG_SUCCESS_VERBOSE = f' {GREEN}Success{RESET_COLOR}'
MSG_SUCCESS = f'{GREEN}.{RESET_COLOR}'


@dataclass
class Result:
    status: str
    duration: Optional[timedelta] = 0
    stdout: str = ''
    stderr: str = ''
    stack_trace: str = ''
    feedback_for_exception: str = ''


def print_status(_name, result: Result):
    verbose = hammett.g.verbose
    message = MESSAGES[result.status]['v' if verbose else 's']
    if verbose:
        hammett.print(_name + ' ' + message + (str(result.duration) if result.duration else ''))
    else:
        hammett.print(message, end='', flush=True)

    if result.status == FAILED:
        hammett.print(RED)
        if not hammett.g.verbose:
            hammett.print()
        hammett.print('Failed: ', _name)
        hammett.print()

        hammett.print(result.stack_trace)

        hammett.print()
        if result.stdout:
            hammett.print(YELLOW)
            hammett.print('--- stdout ---')
            hammett.print(result.stdout)

        if result.stderr:
            hammett.print(RED)
            hammett.print('--- stderr ---')
            hammett.print(result.stderr)

        hammett.print(RESET_COLOR)

    if result.feedback_for_exception:
        hammett.print(result.feedback_for_exception)


def inc_test_result(_name, _f, result):
    print_status(_name, result)

    if hammett.g.fail_fast and result.status not in ('success', 'skipped'):
        hammett.g.should_stop = True

    filename = _f.__module__.replace('.', os.sep) + '.py'
    _name = _name[len(_f.__module__) + 1:]
    hammett.g.result_db['test_results'][filename][_name] = result


def run_test(_name, _f, _module_request, **kwargs):
    if should_skip(_f):
        inc_test_result(_name, _f, Result(status=SKIPPED))
        return

    from io import StringIO

    req = hammett.Request(scope='function', parent=_module_request, function=_f)

    def request():
        return req

    register_fixture(request, autouse=True)
    del request

    hammett.g.hijacked_stdout = StringIO()
    hammett.g.hijacked_stderr = StringIO()
    prev_stdout = sys.stdout
    prev_stderr = sys.stderr

    status = None
    duration = None
    start = None
    setup_time = None
    stack_trace = None
    feedback_for_exception = None

    if hammett.g.verbose:
        hammett.print(_name + '...', end='', flush=True)
    try:
        sys.stdout = hammett.g.hijacked_stdout
        sys.stderr = hammett.g.hijacked_stderr

        if hammett.g.durations:
            start = datetime.now()

        resolved_function, resolved_kwargs = dependency_injection(_f, fixtures, kwargs, request=req)

        if hammett.g.durations:
            setup_time = datetime.now() - start
            start = datetime.now()

        resolved_function(**resolved_kwargs)

        if hammett.g.durations:
            duration = datetime.now() - start
            hammett.g.durations_results.append((_name, duration, setup_time))

        sys.stdout = prev_stdout
        sys.stderr = prev_stderr
        status = SUCCESS
    except KeyboardInterrupt:
        sys.stdout = prev_stdout
        sys.stderr = prev_stderr

        hammett.print()
        hammett.print('ABORTED')
        hammett.g.results['abort'] += 1
        hammett.g.should_stop = True
    except SkipTest:
        sys.stdout = prev_stdout
        sys.stderr = prev_stderr

        status = SKIPPED
    except:
        sys.stdout = prev_stdout
        sys.stderr = prev_stderr

        import traceback
        stack_trace = traceback.format_exc()

        if not hammett.g.quiet:
            feedback_for_exception = build_feedback_for_exception()

        status = FAILED

    assert status is not None

    result = Result(
        status=status, duration=duration,
        stdout=hammett.g.hijacked_stdout.getvalue(),
        stderr=hammett.g.hijacked_stderr.getvalue(),
        stack_trace=stack_trace,
        feedback_for_exception=feedback_for_exception,
    )

    inc_test_result(_name, _f, result=result)

    if status == FAILED and hammett.g.drop_into_debugger:
        try:
            import ipdb as pdb
        except ImportError:
            import pdb
        pdb.set_trace()

    # Tests can change this which breaks everything. Reset!
    os.chdir(hammett.g.orig_cwd)
    req.teardown()


def execute_parametrize(_name, _f, _stack, _module_request, **kwargs):
    if not _stack:
        param_names = [f'{k}={v}' for k, v in kwargs.items()]
        _name = f'{_name}[{", ".join(param_names)}]'
        return run_test(_name, _f, _module_request=_module_request, **kwargs)

    names, param_list = _stack[0]
    if isinstance(names, str):
        names = [x.strip() for x in names.split(',')]
    # if you have just one argument, we allow to just pass a list instead of a list of lists, which is a pytest compatibility feature
    if len(names) == 1 and len(param_list) != 1 and not isinstance(param_list, Iterable):
        param_list = [param_list]
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


def execute_test_class(_name, _c, module_request):
    test_case = _c()
    try:
        test_case.setUp()
    except AttributeError:
        pass

    try:
        test_case.setup_class()
    except AttributeError:
        pass

    setup_method = getattr(test_case, 'setup_method', None)

    for member_name in dir(test_case):
        if member_name.startswith('test_'):
            test_func = getattr(test_case, member_name)
            if setup_method is not None:
                try:
                    setup_method(test_func)
                except Exception:
                    import traceback
                    print('Crash when running setup_method:')
                    traceback.print_exc()
                    continue
            execute_test_function(f'{_name}.{member_name}', test_func, module_request)

    try:
        test_case.tearDown()
    except AttributeError:
        pass

    # return run_test(_name, _f, module_request)


class FakePytestParser:
    def parse_known_args(self, *args):
        class Fake:
            pass
        s = Fake()
        s.itv = True
        s.ds = hammett.g.settings['django_settings_module']
        s.dc = None
        s.version = False
        s.help = False
        return s


class EarlyConfig:
    def __init__(self):
        self.inicfg = self
        self.config = self
        self.path = hammett.g.orig_cwd

    def addinivalue_line(self, name, doc):
        pass

    def getini(self, name):
        return None


early_config = EarlyConfig()


def load_plugin(module_name):
    import importlib
    try:
        plugin_module = importlib.import_module(module_name+'.plugin')
    except ImportError:
        plugin_module = importlib.import_module(module_name)

    parser = FakePytestParser()
    try:
        if hasattr(plugin_module, 'pytest_load_initial_conftests'):
            plugin_module.pytest_load_initial_conftests(early_config=early_config, parser=parser, args=[])

        if hasattr(plugin_module, 'pytest_configure'):
            import inspect
            if inspect.signature(plugin_module.pytest_configure).parameters:
                plugin_module.pytest_configure(early_config)
            else:
                plugin_module.pytest_configure()
    except Exception:
        hammett.print(f'Loading plugin {module_name} failed: ')
        import traceback
        hammett.print(traceback.format_exc())
        hammett.g.results['abort'] += 1
        hammett.g.should_stop = True
        return
    try:
        importlib.import_module(module_name + '.fixtures')
    except ImportError:
        pass
    return True


def read_settings():
    from configparser import (
        ConfigParser,
        NoSectionError,
    )
    config_parser = ConfigParser()
    config_parser.read('setup.cfg')
    try:
        hammett.g.settings.update(dict(config_parser.items('hammett')))
    except NoSectionError:
        return


def load_plugins():
    if 'plugins' not in hammett.g.settings:
        return

    import importlib
    for plugin in hammett.g.settings['plugins'].strip().split('\n'):
        load_plugin(plugin)
        if should_stop():
            return

    try:
        conftest = importlib.import_module('conftest')
    except ImportError:
        conftest = None

    if conftest is not None:
        plugins = getattr(conftest, 'pytest_plugins', [])
        for plugin in plugins:
            load_plugin(plugin)
            if should_stop():
                return

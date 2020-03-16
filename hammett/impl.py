from hammett import MISSING


class RaisesContext(object):
    def __init__(self, expected_exception):
        self.expected_exception = expected_exception
        self.excinfo = None

    def __enter__(self):
        self.excinfo = ExceptionInfo()
        return self.excinfo

    def __exit__(self, *tp):
        __tracebackhide__ = True
        if tp[0] is None:
            assert False, f'Did not raise {self.expected_exception}'
        self.excinfo.value = tp[1]
        self.excinfo.type = tp[0]
        suppress_exception = issubclass(self.excinfo.type, self.expected_exception)
        return suppress_exception


class ExceptionInfo:
    def __str__(self):
        return f'<ExceptionInfo: type={self.type} value={self.value}'


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
    if autouse:
        auto_use_fixtures.add(name)
    assert scope in ('function', 'class', 'module', 'package', 'session')
    fixture_scope[name] = scope
    fixtures[name] = fixture


def pick_keys(kwargs, params):
    return {
        k: v
        for k, v in kwargs.items()
        if k in params
    }


class FixturesUnresolvableException(Exception):
    pass


def params_of(f):
    import inspect
    return set(
        x.name
        for x in inspect.signature(f).parameters.values()
        if x.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    )


def _teardown_yield_fixture(fixturefunc, it):
    """Executes the teardown of a fixture function by advancing the iterator after the
    yield and ensure the iteration ends (if not it means there is more than one yield in the function)"""
    try:
        next(it)
    except StopIteration:
        pass
    else:
        print(f"yield_fixture {fixturefunc} function has more than one 'yield'")
        exit(1)


def call_fixture_func(fixturefunc, request, kwargs):
    existing_result = request.hammett_get_existing_result(fixture_function_name(fixturefunc))
    if existing_result is not MISSING:
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
            raise FixturesUnresolvableException(f'Could not resolve fixtures any more, have {params_by_name.keys()} left')

    if request is not None:
        request.fixturenames = set(kwargs.keys())
    # prune again, to get rid of auto use fixtures that f doesn't take
    kwargs = {k: v for k, v in kwargs.items() if k in f_params}
    return f(**{**kwargs, **orig_kwargs})

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
    pass


fixtures = {}


def register_fixture(fixture):
    assert fixture.__name__ not in fixtures, 'A fixture with this name is already registered'
    fixtures[fixture.__name__] = fixture


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


def dependency_injection(f, fixtures):
    f_params = params_of(f)
    params_by_name = {
        name: params_of(fixture)
        for name, fixture in fixtures.items()
        # prune the fixture list based on what f needs
        if name in f_params
    }
    kwargs = {}
    reduced = False
    while params_by_name:
        for name, params in list(params_by_name.items()):
            if params.issubset(set(kwargs.keys())):
                kwargs[name] = fixtures[name](**pick_keys(kwargs, params))
                reduced = True
                del params_by_name[name]
        if not reduced:
            raise FixturesUnresolvableException(f'Could not resolve fixtures any more, have {params_by_name.keys()} left')
    return f(**kwargs)

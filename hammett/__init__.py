import hammett.mark as mark


__version__ = '0.1.0'


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


# TODO: fix this
def yield_fixture(*args, **kwargs):
    pass
    return fixture(*args, **kwargs)


# TODO: implement optional message param
def raises(expected_exception):
    from hammett.impl import RaisesContext
    return RaisesContext(expected_exception)

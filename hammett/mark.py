def parametrize(argnames, argvalues, indirect=False, ids=None, scope=None):
    def parametrize_wrapper(f):
        if not hasattr(f, 'hammett_parametrize_stack'):
            f.hammett_parametrize_stack = []
        f.hammett_parametrize_stack.append((argnames, argvalues))
        return f

    return parametrize_wrapper


class Marker:
    def __init__(self, name, args, kwargs):
        self.args = args
        self.kwargs = kwargs
        self.name = name

    def __repr__(self):
        return f'hammett.{self.name}'


def __getattr__(name: str):
    if name in __package__:
        return __package__[name]

    else:
        def marker(*args, **kwargs):
            args = list(args)

            def decorate(f):
                if not hasattr(f, 'hammett_markers'):
                    f.hammett_markers = []
                f.hammett_markers.append(Marker(name, args, kwargs))
                return f

            if len(args) == 1:
                if callable(args[0]):
                    f = args[0]
                    args[:] = args[1:]
                    return decorate(f)
            return decorate

        return marker

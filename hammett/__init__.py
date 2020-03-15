import hammett.mark as mark


__version__ = '0.1.0'


class ExceptionInfo:
    pass


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


# TODO: implement optional message param
def raises(expected_exception):
    return RaisesContext(expected_exception)

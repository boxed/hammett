import hammett.mark as mark


__version__ = '0.1.0'


def fixture(f):
    from hammett.impl import register_fixture
    register_fixture(f)
    return f


# TODO: implement optional message param
def raises(expected_exception):
    from hammett.impl import RaisesContext
    return RaisesContext(expected_exception)

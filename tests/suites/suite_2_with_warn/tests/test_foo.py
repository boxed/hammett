import warnings

import pytest


def test_foo():
    with pytest.warns(UserWarning) as e:
        warnings.warn('foo', UserWarning)

    assert str(e[0].message) == 'foo'

    with pytest.warns(UserWarning, match='fo[oO]'):
        warnings.warn('foo', UserWarning)

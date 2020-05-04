import pytest


def test_foo():
    with pytest.raises(AssertionError, match='.*foo.*'):
        assert False, 'baz'

import pytest


def test_foo():
    with pytest.raises(AssertionError, match='.*foo.*') as e:
        assert False, 'bazfoobar'

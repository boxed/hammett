import pytest


def test_foo():
    with pytest.raises(AssertionError) as e:
        assert False, 'foo'

    assert str(e.value) == 'foo'

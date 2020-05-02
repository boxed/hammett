import pytest


@pytest.mark.parametrize('foo', range(5))
def test_foo(foo):
    assert True

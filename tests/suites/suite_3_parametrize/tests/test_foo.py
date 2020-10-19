import pytest


@pytest.fixture
def bar():
    pass


@pytest.mark.parametrize('foo', range(5))
def test_foo(foo, bar):
    assert True

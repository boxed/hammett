import pytest


@pytest.fixture
def bar():
    return 3


@pytest.fixture
def foo(bar):
    return 5 + bar


@pytest.fixture
def baz():
    yield 7


def test_foo(foo, baz):
    assert foo == 8
    assert baz == 7

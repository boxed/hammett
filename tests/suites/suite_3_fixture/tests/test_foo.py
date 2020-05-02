import pytest


@pytest.fixture
def bar():
    return 3


@pytest.fixture
def foo(bar):
    return 5 + bar


def test_foo(foo):
    assert foo == 8

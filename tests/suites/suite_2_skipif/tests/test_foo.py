import pytest


@pytest.mark.skipif(True)
def test_foo():
    assert False


@pytest.mark.skipif(False)
def test_bar():
    assert False

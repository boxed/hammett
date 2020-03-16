import unittest

from hammett import (
    fixture,
    Request,
)
from hammett.impl import (
    fixtures,
    dependency_injection,
)


class FixtureDecoratorTests(unittest.TestCase):
    def setUp(self) -> None:
        fixtures.clear()

    def test_simplest(self):
        assert 'foo' not in fixtures

        @fixture
        def foo():
            return 3

        assert foo() == 3
        assert 'foo' in fixtures

    def test_with_arg(self):
        assert 'foo' not in fixtures

        @fixture('bla')
        def foo():
            return 3

        assert foo() == 3

    def test_auto_use_is_called_but_not_passed(self):
        assert 'foo' not in fixtures

        @fixture(autouse=True)
        def foo():
            return 3

        request = Request(scope='function', parent=None)

        assert dependency_injection(lambda: 7, fixtures, {}, request=request) == 7

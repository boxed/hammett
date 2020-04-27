import unittest

from hammett import Request
from hammett.impl import dependency_injection_and_execute


class DITests(unittest.TestCase):

    def test_dependency_injection_simple(self):
        fixtures = dict(
            foo=lambda: 3,
        )

        request = Request(scope='function', parent=None)

        assert dependency_injection_and_execute(lambda foo: foo, fixtures, {}, request=request) == 3

    def test_di_graph(self):
        fixtures = dict(
            bar=lambda foo: 1 + foo,
            foo=lambda: 3,
            baz=lambda foo, bar: foo + bar,
        )

        request = Request(scope='function', parent=None)

        assert dependency_injection_and_execute(lambda foo, bar, baz: (foo, bar, baz), fixtures, {}, request=request) == (3, 4, 7)

    def test_di_does_not_call_unneeded_fixture(self):
        def crash():
            assert False

        fixtures = dict(
            crash=crash,
            foo=lambda: 3,
        )

        request = Request(scope='function', parent=None)

        assert dependency_injection_and_execute(lambda foo: foo, fixtures, {}, request=request) == 3

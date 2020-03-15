import unittest

from hammett.impl import dependency_injection


class Tests(unittest.TestCase):

    def test_dependency_injection_simple(self):
        fixtures = dict(
            foo=lambda: 3,
        )

        assert dependency_injection(lambda foo: foo, fixtures) == (3)

    def test_di_graph(self):
        fixtures = dict(
            bar=lambda foo: 1 + foo,
            foo=lambda: 3,
            baz=lambda foo, bar: foo + bar,
        )

        assert dependency_injection(lambda foo, bar, baz: (foo, bar, baz), fixtures) == (3, 4, 7)

    def test_di_does_not_call_unneeded_fixture(self):
        def crash():
            assert False

        fixtures = dict(
            crash=crash,
            foo=lambda: 3,
        )

        assert dependency_injection(lambda foo: foo, fixtures) == 3

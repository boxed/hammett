import unittest

from hammett import (
    fixture,
    parse_markers,
    Request,
)
from hammett.impl import (
    auto_use_fixtures,
    fixtures,
    dependency_injection_and_execute,
    indent,
    pretty_format,
)


class FixtureDecoratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orig_fixtures = fixtures.copy()
        fixtures.clear()

    def tearDown(self) -> None:
        fixtures.update(self.orig_fixtures)
        auto_use_fixtures.clear()

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

        assert dependency_injection_and_execute(lambda: 7, fixtures, {}, request=request) == 7


class MiscTests(unittest.TestCase):
    def test_indent(self):
        assert indent('foo') == '    foo'
        assert indent('foo', levels=2) == '        foo'
        assert indent('''foo
    bar
        baz''') == '''    foo
        bar
            baz'''

    def test_pretty_format(self):
        class Foo:
            def __repr__(self):
                return '<foo>'

        assert pretty_format(dict(
            foo=Foo(),
            bar=dict(
                foo=Foo(),
            ),
            baz=[1, 2, 3],
            quux=(4, 5, [6]),
            asd={},
            qwe=[],
            dfg=tuple(),
        )) == '''{
    'foo': <foo>,
    'bar': {
        'foo': <foo>,
    },
    'baz': [
        1,
        2,
        3,
    ],
    'quux': (
        4,
        5,
        [
            6,
        ],
    ),
    'asd': {},
    'qwe': [],
    'dfg': (,),
}'''

    def test_parse_markers(self):
        assert parse_markers('foo;bar[5]') == {'foo': None, 'bar': '5'}

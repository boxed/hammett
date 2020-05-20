import os
import unittest
from os.path import (
    abspath,
    join,
)

from hammett import main, g


class SuitesTests(unittest.TestCase):
    def test_suites(self):
        base = abspath('.')
        suites_base = abspath(join('tests', 'suites'))
        for d in os.listdir(suites_base):
            p = os.path.join(suites_base, d)
            if not os.path.isdir(p):
                continue

            with self.subTest(d):
                exit_code = main(cwd=p, quiet=True)
                with open(join(p, 'asserts.py')) as f:
                    asserts = f.read()

                try:
                    exec(asserts, {'g': g, 'exit_code': exit_code, 'base': base})
                except AssertionError:
                    print('g.results', g.results)
                    print('exit_code', exit_code)
                    print('base', base)
                    print('output', g.output)
                    assert False

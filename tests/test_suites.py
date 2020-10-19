import os
import unittest
from os.path import (
    abspath,
    dirname,
    join,
)

from hammett import main, g


class SuitesTests(unittest.TestCase):
    def test_suites(self):
        base = dirname(dirname(abspath(__file__)))
        suites_base = abspath(join(base, 'tests', 'suites'))
        for d in os.listdir(suites_base):
            p = os.path.join(suites_base, d)
            if not os.path.isdir(p):
                continue

            with self.subTest(d):
                exit_code = main(cwd=p, quiet=True, use_cache=False)
                with open(join(p, 'asserts.py')) as f:
                    asserts = f.read()

                try:
                    exec(asserts, {'g': g, 'exit_code': exit_code, 'base': base})
                except AssertionError:
                    print()
                    print('-------')
                    print('suite', d)
                    print('g.results', g.results)
                    print('asserts', asserts.strip())
                    print('exit_code', exit_code)
                    print('base', base)
                    print('output:')
                    print(''.join(a + b for a, b, _ in g.output))
                    print('output detailed:')
                    for x in g.output:
                        print(x)
                    print('-------')
                    print()
                    assert False

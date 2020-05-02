import os
import unittest
from os.path import (
    abspath,
    join,
)

from hammett import main, g


class SuitesTests(unittest.TestCase):
    def test_suites(self):
        base = abspath('tests/suites')
        for d in os.listdir(base):
            with self.subTest(d):
                main(cwd=os.path.join(base, d), quiet=True)
                with open(join(base, d, 'asserts.py')) as f:
                    asserts = f.read()

                exec(asserts, {'g': g})

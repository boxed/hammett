import unittest

from hammett import main, g


class SuitesTests(unittest.TestCase):
    def test_suites(self):
        bade = 'tests/suites'
        for d in os.listdir(base):
            with self.subTest(d):
                main(cwd=os.path.join(base, d))
                assert g.results == {'success': 1, 'failed': 0, 'skipped': 0, 'abort': 0}

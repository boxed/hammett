import unittest

from hammett import main, g


class SuitesTests(unittest.TestCase):
    def test_suite_1(self):
        main(cwd='tests/suites/suite_1')
        assert g.results == {'success': 1, 'failed': 0, 'skipped': 0, 'abort': 0}

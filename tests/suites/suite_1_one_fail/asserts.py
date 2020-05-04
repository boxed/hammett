assert g.results == {'success': 0, 'failed': 1, 'skipped': 0, 'abort': 0}
assert g.output == [
    (('\x1b[31m',), '\n', False),
    ((), '\n', False),
    (('Failed:', 'tests.test_foo.test_foo'), '\n', False),
    ((), '\n', False),
    (('Traceback (most recent call last):\n  File "{base}/hammett/impl.py", line 372, in run_test\n    resolved_function(**resolved_kwargs)\n  File "tests/test_foo.py", line 4, in test_foo\n    assert False\nAssertionError\n'.replace('{base}', base),), '\n', False),
    ((), '\n', False),
    (('\x1b[0m',), '\n', False),
    ((), '\n', False),
    (('\x1b[31m0 succeeded, 1 failed, 0 skipped\x1b[0m',), '\n', False),
]

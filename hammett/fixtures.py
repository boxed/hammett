def tmpdir():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix='hammet_') as d:
        yield d


# This is a bit over designed/weird because of pytest compatibility
def capsys():
    class CaptureFixture:
        def readouterr(self):
            import hammett
            return hammett.g.hijacked_stdout.getvalue(), hammett.g.hijacked_stderr.getvalue()

    return CaptureFixture()

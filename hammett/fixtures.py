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


def caplog(request):
    """Access and control log capturing.

    Captured logs are available through the following properties/methods::

    * caplog.messages        -> list of format-interpolated log messages
    * caplog.text            -> string containing formatted log output
    * caplog.records         -> list of logging.LogRecord instances
    * caplog.record_tuples   -> list of (logger_name, level, message) tuples
    * caplog.clear()         -> clear captured records and formatted log output string
    """
    from hammett.fixtures_support import LogCaptureFixture
    from hammett.fixtures_support import catching_logs
    from hammett.fixtures_support import LogCaptureHandler
    import logging
    with catching_logs(LogCaptureHandler(), level=logging.INFO) as handler:
        request.catch_log_handler = handler
        result = LogCaptureFixture(request.node)
        yield result
        result._finalize()

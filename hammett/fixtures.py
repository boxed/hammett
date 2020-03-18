def tmpdir():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix='hammet_') as d:
        yield d

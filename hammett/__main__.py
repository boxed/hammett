verbose = False
results = dict(success=0, failed=0, skipped=0)
settings = {}
fail_fast = False


def run_test(_name, _f, **kwargs):
    import colorama
    from hammett.impl import register_fixture

    class Request:
        def __init__(self):
            self.additional_fixtures_wanted = set()
            self.keywords = {}
            self.fixturenames = set()
            self.finalizers = []

            class Option:
                def __init__(self):
                    self.verbose = verbose

            class Config:
                def __init__(self):
                    self.option = Option()

                def getvalue(self, _):
                    return None

            self.config = Config()

        def teardown(self):
            for x in reversed(self.finalizers):
                x()

        @property
        def node(self):
            return self

        def addfinalizer(self, x):
            self.finalizers.append(x)

        def get_closest_marker(self, s):
            try:
                markers = _f.hammett_markers
            except AttributeError:
                return None

            for marker in markers:
                if marker.name == s:
                    return marker

            return None

        def getfixturevalue(self, s):
            return self.additional_fixtures_wanted.add(s)

    req = Request()

    def request():
        return req

    register_fixture(request, autouse=True)
    del request

    if verbose:
        print(_name, end='')
    try:
        from hammett.impl import (
            dependency_injection,
            fixtures,
        )
        dependency_injection(_f, fixtures, kwargs, request=req)
        if verbose:
            print(f'... {colorama.Fore.GREEN}Success{colorama.Style.RESET_ALL}')
        else:
            print(f'{colorama.Fore.GREEN}.{colorama.Style.RESET_ALL}', end='')
        results['success'] += 1

    except:
        global success
        success = False
        if verbose:
            print(f'... {colorama.Fore.RED}Fail{colorama.Style.RESET_ALL}')
        else:
            print(f'{colorama.Fore.RED}F{colorama.Style.RESET_ALL}')
        import traceback
        traceback.print_exc()
        results['failed'] += 1
        if fail_fast:
            req.teardown()
            exit(1)

    req.teardown()


def execute_parametrize(_name, _f, _stack, **kwargs):
    if not _stack:
        param_names = [f'{k}={v}' for k, v in kwargs.items()]
        _name = f'{_name}[{", ".join(param_names)}]'
        run_test(_name, _f, **kwargs)
        return

    names, param_list = _stack[0]
    names = [x.strip() for x in names.split(',')]
    for params in param_list:
        if not isinstance(params, (list, tuple)):
            params = [params]
        execute_parametrize(_name, _f, _stack[1:], **{**dict(zip(names, params)), **kwargs})


def execute_test_function(_name, _f):
    if getattr(_f, 'hammett_parametrize_stack', None):
        execute_parametrize(_name, _f, _f.hammett_parametrize_stack)
    else:
        run_test(_name, _f)


def read_settings():
    from configparser import (
        ConfigParser,
    )
    config_parser = ConfigParser()
    config_parser.read('setup.cfg')
    settings.update(dict(config_parser.items('hammett')))

    # load plugins
    if 'plugins' not in settings:
        return

    class EarlyConfig:
        def addinivalue_line(self, name, doc):
            pass

        def getini(self, name):
            return None

    early_config = EarlyConfig()

    class Parser:
        def parse_known_args(self, *args):
            class Fake:
                pass
            s = Fake()
            s.itv = True
            s.ds = settings['django_settings_module']
            s.dc = None
            return s

    parser = Parser()

    import importlib
    for x in settings['plugins'].strip().split('\n'):
        plugin = importlib.import_module(x + '.plugin')
        plugin.pytest_load_initial_conftests(early_config=early_config, parser=parser, args=[])
        plugin.pytest_configure()
        importlib.import_module(x + '.fixtures')


def main():
    global verbose, fail_fast
    from argparse import ArgumentParser
    parser = ArgumentParser(prog='hammett')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False)
    parser.add_argument('-x', dest='fail_fast', action='store_true', default=False)
    parser.add_argument(dest='filenames', nargs='+')
    args = parser.parse_args()

    verbose = args.verbose
    fail_fast = args.fail_fast

    if args.filenames:
        filenames = args.filenames
    else:
        from os import listdir
        try:
            filenames = ['tests/' + x for x in listdir('tests')]
        except FileNotFoundError:
            print('No tests found')
            return 1

    read_settings()
    from os.path import split, sep

    for test_filename in filenames:
        dirname, filename = split(test_filename)
        if not filename.startswith('test_') or not filename.endswith('.py'):
            continue

        import importlib.util
        import sys
        module_name = f'{dirname.replace(sep, ".")}.{filename.replace(".py", "")}'
        spec = importlib.util.spec_from_file_location(module_name, test_filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        for name, f in module.__dict__.items():
            if name.startswith('test_'):
                execute_test_function(module_name + '.' + name, f)

        del sys.modules[module_name]

    if not verbose:
        print()
    print(f'{results["success"]} succeeded, {results["failed"]} failed, {results["skipped"]} skipped')
    return 1 if results['failed'] else 0


if __name__ == '__main__':
    exit(main())

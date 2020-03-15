verbose = False
success = True


def run_test(name, f, **kwargs):
    if verbose:
        print(name, end='')
    try:
        f(**kwargs)
        if verbose:
            print('... Success')
        else:
            print('.', end='')
        return True
    except:
        global success
        success = False
        if verbose:
            print('... Fail')
            import traceback
            traceback.print_exc()
        else:
            print('F', end='')
        return False


def execute_parametrize(name, f, stack, **kwargs):
    if not stack:
        param_names = [f'{k}={v}' for k, v in kwargs.items()]
        name = f'{name}[{", ".join(param_names)}]'
        run_test(name, f, **kwargs)
        return

    names, param_list = stack[0]
    names = [x.strip() for x in names.split(',')]
    for params in param_list:
        if not isinstance(params, (list, tuple)):
            params = [params]
        execute_parametrize(name, f, stack[1:], **{**dict(zip(names, params)), **kwargs})


def execute_test_function(name, f):
    if getattr(f, 'hammett_parametrize_stack', None):
        execute_parametrize(name, f, f.hammett_parametrize_stack)
    else:
        run_test(name, f)


def main():
    from os import listdir
    for test_filename in listdir('tests'):
        if not test_filename.startswith('test_') or not test_filename.endswith('.py'):
            continue

        import importlib.util
        spec = importlib.util.spec_from_file_location(f'tests.{test_filename.replace(".py", "")}', f'tests/{test_filename}')
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)

        for name, f in foo.__dict__.items():
            if name.startswith('test_'):
                execute_test_function(name, f)

    if not verbose:
        print()
    exit(0 if success else 1)


if __name__ == '__main__':
    main()

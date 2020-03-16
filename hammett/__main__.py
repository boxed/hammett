import colorama

verbose = False
results = dict(success=0, failed=0, skipped=0)


def run_test(name, f, **kwargs):
    if verbose:
        print(name, end='')
    try:
        f(**kwargs)
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
            import traceback
            traceback.print_exc()
        else:
            print(f'{colorama.Fore.RED}F{colorama.Style.RESET_ALL}', end='')
        results['failed'] += 1


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
    try:
        filenames = listdir('tests')
    except FileNotFoundError:
        print('No tests found')
        exit(1)

    for test_filename in filenames:
        if not test_filename.startswith('test_') or not test_filename.endswith('.py'):
            continue

        import importlib.util
        spec = importlib.util.spec_from_file_location(f'{test_filename.replace(".py", "")}', f'tests/{test_filename}')
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)

        for name, f in foo.__dict__.items():
            if name.startswith('test_'):
                execute_test_function(name, f)

    if not verbose:
        print()
    print(f'{results["success"]} succeeded, {results["failed"]} failed, {results["skipped"]} skipped')
    exit(1 if results['failed'] else 0)


if __name__ == '__main__':
    main()

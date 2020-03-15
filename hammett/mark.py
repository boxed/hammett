def parametrize(argnames, argvalues, indirect=False, ids=None, scope=None):
    def parametrize_wrapper(f):
        if not hasattr(f, 'hammett_parametrize_stack'):
            f.hammett_parametrize_stack = []
        f.hammett_parametrize_stack.append((argnames, argvalues))
        return f

    return parametrize_wrapper

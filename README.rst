hammett
=======

Hammett is a fast python test runner that aims to be compatible with the parts
of pytest most people use (unless that conflicts with the goal of being fast).
It also adds some features that can dramatically improve your testing experience
if you adapt more fully to hammett.


How much faster is hammett?
---------------------------

This will depend on how fast your test suite is.
Hammett isn't magic, it's just a runner made by someone who cares about
performance a lot. It aims to have minimal startup overhead and minimal
overhead for each test. I have written some benchmarks for measuring this
overhead which you can find at https://github.com/boxed/test-benchmarks (TL;DR
if your test suite is < 1s in pytest you will see VAST improvements, if it's
minutes or hours, not so much).

A real world example is running the test suite of tri.declarative:

- pytest: ~860 ms
- hammett: ~160 ms

Or iommi:

- pytest: ~10 s
- hammett: ~8 s


But even if your test suite is big and slow you can still get some big
improvements out of hammett if you often run just one file or one test:

In iommi, running `-k test_render_attrs_none`

- pytest: ~1.3 s
- hammett: ~0.6 s

All of this is from a full and clean run. Hammett has features to avoid that!


Tests locked to a module
------------------------

In hammett you can optionally name your test files `module__tests.py` (that's
two `_`). This tells hammett that if you change `module` only the tests in
`module__tests.py` needs to be run. You can place those files either in the
tests directory or right next to the module you're testing.


Run just relevant tests
------------------------

Hammett keeps track of what modules and what tests have changed and runs only
the tests it needs to. Assuming you lock your tests to a module like above.

If hammett gets confused you can delete the `.hammett-db` file and it will
start from scratch.


Pytest features that work in hammett
------------------------------------

- `pytest.mark`
- parametrized tests
- fixtures
- `with pytest.raises`


Some plugins work, but you have to specify to load them in setup.cfg:

.. code:: ini

    [hammett]
    plugins=
        pytest_django


Notable missing features
------------------------

* no support for class based tests


Usage
------

First install: :code:`pip install hammett`

Then run hammett: :code:`python -m hammett`

Hopefully it will run your entire test suite!

Hammett works with some pytest plugins, most notably pytest-django, at least
for some projects. You need to specify what plugins hammett loads manually
in setup.cfg though.


Keeping pytest compatibility
----------------------------

If you want to use the hammett specific feature of `module__tests.py`-style
test files, you can still keep compatibility with pytest by specifying the
module of your project and the tests file pattern, like this:

.. code::

    testpaths=
        tests
        my_project
    python_files=
        *__tests.py

Also keep importing pytest instead of hammett obviously.


License
-------

BSD

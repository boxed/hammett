hammett
=======

Hammett is a fast python test runner that aims to be compatible with pytest (unless that conflicts with the goal of being fast).


How much faster is hammett? This will depend on how fast your test suite is.
Hammett isn't magic, it's just a runner made by someone who cares about
performance a lot. It aims to have minimal startup overhead and minimal
overhead for each test. I have written some bench marks for measuring this
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

In iommi, running "-k test_render_attrs_none"

- pytest: ~1.3 s
- hammett: ~0.6 s


Stuff that works
----------------

- pytest.mark
- parametrized tests
- fixtures
- with pytest.raises


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

hammett works with some pytest plugins, most notably pytest-django, at least for some projects.


License
-------

BSD

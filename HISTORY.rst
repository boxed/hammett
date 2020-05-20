Changelog
---------

0.7.0 (2020-05-20)
~~~~~~~~~~~~~~~~~~

* Added hammett specific tests files system. This means if you have a file `my_project/foo.py` hammett will look for `my_project/foo__tests.py` and `testt/foo__tests.py` for tests specific for that module.

* If you have module specific tests (see previous point), you can now run tests for a module with `hammett my_project.foo`

* Implemented a results cache. This means that if you haven't changed your source or tests hammett knows not to rerun the tests. If you have module specific tests it will run only the relevant tests for that module when you change the module.

* Added `hammett` command line. Beware of using this after doing `setup.py develop` as setuptools then adds a huge overhead.

* Support python 3.6

* Optimizations


0.6.0 (2020-05-04)
~~~~~~~~~~~~~~~~~~

* Added --durations feature

* Improvements to skipping tests

* Run tests in lexiographic order

* Better assertion analysis

* You can now pass hammett a directory on the command line and it'll do the right thing

* Support names parameter of mark.parametrize() being a list/tuple


0.5.0 (2020-03-30)
~~~~~~~~~~~~~~~~~~

* Implemented support for filtering tests based on markers. Also supports the marker[argument] syntax that goes beyond what pytest can do

* Nicer output on failed tests


0.4.0 (2020-03-25)
~~~~~~~~~~~~~~~~~~

* Implemented module level markers

* Added --pdb command line arguement. This will try ipdb first, then pdb.

* Added noop @pytest.hookimpl support

* Improved feedback on assertion error

* Added -k flag (it's a bit more naive then in pytest, but it's fine for now)

* Implemented --durations

* Added support for test/ folder

* Corrected display for skipped


0.3.0 (2020-03-18)
~~~~~~~~~~~~~~~~~~

* New flag: -q for quiet. In this mode there is no output. This is useful for CI/mutation testing.

* Fixes to make hammett usable as an API

* Fixes to be able to call hammett over and over in a single process even when the code on disk changes

* Improved support for pytest.raises

* Support for pytests `tmpdir` fixture

* Misc fixes


0.2.0 (2020-03-18)
~~~~~~~~~~~~~~~~~~

* Nicer output for failed tests: local variables and some analysis of asserts if applicable


0.1.0 (2020-03-17)
~~~~~~~~~~~~~~~~~~

* Initial release

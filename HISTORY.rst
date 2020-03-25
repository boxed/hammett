Changelog
---------

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

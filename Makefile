.PHONY: clean-pyc clean-build docs clean lint test coverage docs dist tag release-check

help:
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests"
	@echo "coverage - check code coverage quickly with the default Python"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "dist - package"
	@echo "tag - set a tag with the current version number"
	@echo "release-check - check release tag"

clean: clean-build clean-pyc
	rm -rf htmlcov/

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr lib/*.egg-info

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name "__pycache__" -type d -delete

clean-cache:
	find . -name '.hammett-db' -exec rm -f {} +

clean-docs:
	rm -f docs/tri*.rst

lint:
	tox -e lint

test: clean-cache
	python -m unittest tests/test_*.py -v

coverage:
	coverage run --source=hammett -m unittest tests/test_*.py

docs:
	tox -e docs

dist: clean
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

tag:
	python setup.py tag

release-check:
	python setup.py release_check

venv:
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt

run-examples: venv
	python examples/manage.py migrate
	python examples/manage.py runserver

Contributing
============

CNaaS-NMS is open source and everything including source code, documentation etc is available
to the public on Github. Please send pull requests using Github for any contributions.

Coding style
------------

CNaaS-NMS is developed for python 3.7 and uses type hinting and dataclasses.

PEP8 is used for style guidelines and black for formatting, we try to follow it as long as it
makes things more readable, and we use a locally defined maximum line length of 120 characters.

Pre-commit hooks for black, isort and flake8 are used. Run ``pip install -r requirements-dev.txt`` and run
"pre-commit install" to get the hooks installed.

PEP440 is used for versioning using the style 0.1.0dev1, 0.1.0b1, 0.1.0rc1, 0.1.0 etc.

Unit tests should be written for all parts that can be tested individually, but since the
project heavily relies on physical lab equipment some tests has to be performed only as
integration tests instead. The suite of unit tests should ideally complete within 5 minutes
and be run on all check-ins to any branch. Integration tests should run nightly on the master
branch. The combined code coverage for unit tests plus integration tests should be around 80%.

Core components of CNaaS-NMS should use type-hinting to help prevent bugs and increase
maintainability of the code. MyPy should pass without errors on the main code base (everything
except possibly tests?).

Alembic is used to handle SQL schema updates/versioning.

.. santanico documentation master file.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to santanico's documentation!
=================================================

|build-status| |code-quality| |ruff| |coverage|

|python-versions| |pypi-version|

Strip document metadata at scary speeds, with Python and Rust.

Features
========

* Streaming filter: O(1) memory, feed arbitrary byte chunks of any size
* Strips metadata/structural destination groups (``\info``, ``\fonttbl``,
  ``\generator``, ...) and everything inside them
* Preserves all document content and formatting groups (``\b``, ``\par``, ...)
* Pure-Python fallback when the native Rust extension is unavailable

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   api



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. |build-status| image:: https://github.com/maykinmedia/santanico/workflows/Run%20CI/badge.svg
    :alt: Build status
    :target: https://github.com/maykinmedia/santanico/actions?query=workflow%3A%22Run+CI%22

.. |code-quality| image:: https://github.com/maykinmedia/santanico/workflows/Code%20quality%20checks/badge.svg
     :alt: Code quality checks
     :target: https://github.com/maykinmedia/santanico/actions?query=workflow%3A%22Code+quality+checks%22

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Ruff

.. |coverage| image:: https://codecov.io/gh/maykinmedia/santanico/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/maykinmedia/santanico
    :alt: Coverage status

.. |python-versions| image:: https://img.shields.io/pypi/pyversions/santanico.svg

.. |pypi-version| image:: https://img.shields.io/pypi/v/santanico.svg
    :target: https://pypi.org/project/santanico/

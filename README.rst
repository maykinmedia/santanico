Welcome to santanico's documentation!
=====================================

:Version: 0.1.1
:Source: https://github.com/maykinmedia/santanico
:Keywords: ``rtf``, ``metadata``, ``sanitizer``, ``privacy``, ``streaming``, ``rust``, ``pyo3``
:PythonVersion: 3.11

|build-status| |code-quality| |ruff| |coverage|

|python-versions| |pypi-version|

Strip document metadata at scary speeds, with Python and Rust.

.. contents::

.. section-numbering::

Features
========

* Streaming filter: O(1) memory, feed arbitrary byte chunks of any size
* Strips metadata/structural destination groups (``\info``, ``\fonttbl``,
  ``\generator``, ...) and everything inside them
* Preserves all document content and formatting groups (``\b``, ``\par``, ...)
* Pure-Python fallback when the native Rust extension is unavailable

Installation
============

Requirements
------------

* Python 3.11 or above

Install
-------

.. code-block:: bash

    pip install santanico

A native Rust extension is used when a wheel for your platform is available
or a Rust toolchain is present to build the sdist; otherwise santanico falls
back to a pure-Python implementation (with a ``RuntimeWarning``).

Usage
=====

.. code-block:: python

    from santanico import RtfStreamFilter

    chunk_size = 64 * 1024
    filter_ = RtfStreamFilter()

    with open("input.rtf", "rb") as inf, open("output.rtf", "wb") as outf:
        while chunk := inf.read(chunk_size):
            outf.write(filter_.process_chunk(chunk))

The filter is stateful and single-use per document; call
``filter_.reset()`` to reuse the instance for another document. It is not
thread-safe: create one instance per stream (e.g. one per thread).

Local development
=================

Install the development dependencies, then build the native extension
in-place for an editable install::

    uv sync --all-groups
    uv run maturin develop

Re-run ``maturin develop`` after changing the Rust code. Run the tests
directly with pytest; the memory-limit tests only run with ``--memray``::

    uv run pytest --benchmark-skip
    uv run pytest -m limit_memory --memray

Run the code-quality checks and the full test matrix with tox (``tox p``
runs the environments in parallel)::

    tox -e lint,typecheck,rust,docs,build
    tox p

The tox test environments skip the benchmarks; run them explicitly::

    tox -e benchmark

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

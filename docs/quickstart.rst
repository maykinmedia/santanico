==========
Quickstart
==========

Installation
============

Install from PyPI with pip:

.. code-block:: bash

    pip install santanico

A native Rust extension is used when available; otherwise santanico falls
back to a pure-Python implementation (with a ``RuntimeWarning``).

Usage
=====

The entry point is :data:`santanico.RtfStreamFilter`, a streaming filter that
conforms to the :class:`santanico.StreamingFilter` interface. See the
:doc:`API reference <api>` for the full method reference.

Example: streaming a file in chunks
===================================

The filter is stateful and single-use per document. Stream the document in
arbitrary chunks (splits mid-escape, mid-keyword or mid-brace are fine) and
write the results as they come in:

.. code-block:: python

    from santanico import RtfStreamFilter

    chunk_size = 64 * 1024
    filter_ = RtfStreamFilter()

    with open("input.rtf", "rb") as inf, open("output.rtf", "wb") as outf:
        while chunk := inf.read(chunk_size):
            outf.write(filter_.process_chunk(chunk))

Call :meth:`santanico.RtfStreamFilter.reset` to reuse the same instance for
another document.

Thread safety
=============

Filters are stateful and **not thread-safe**: do not share a single instance
across threads, as their streaming state would interleave and corrupt the
output. Create one filter per stream (e.g. one per thread) and feed each
only its own chunks, sequentially.

API Reference
=============

santanico.StreamingFilter
-------------------------

.. autoclass:: santanico.StreamingFilter
   :members:
   :member-order: bysource

   The shared streaming interface. Both the native Rust implementation and
   the pure-Python :class:`~santanico.PyRtfStreamFilter` conform to this
   protocol. :data:`santanico.RtfStreamFilter` is statically typed as
   ``type[StreamingFilter]`` and can be used wherever the interface is
   expected.

santanico.RtfStreamFilter
-------------------------

The default RTF filter exported by :mod:`santanico`. At import time it is bound
to the native Rust implementation when the compiled extension is available,
and otherwise falls back to the pure-Python
:class:`~santanico.PyRtfStreamFilter` (with a :exc:`RuntimeWarning`).

Because it is declared as ``type[santanico.StreamingFilter]``, any code
written against the :class:`~santanico.StreamingFilter` interface works
unchanged with either backend. See the interface above for the method
reference.

santanico.PyRtfStreamFilter
---------------------------

.. autoclass:: santanico.PyRtfStreamFilter
   :members:
   :member-order: bysource

   The pure-Python fallback implementation, used automatically when the
   native Rust extension is unavailable.

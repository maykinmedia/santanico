from ._reference_rtf_filter import PyRtfStreamFilter
from .protocol import StreamingFilter

# Both implementations implement this interface
RtfStreamFilter: type[StreamingFilter]

try:
    # Native compiled Rust implementation
    from .santanico import RtfStreamFilter
except ImportError:
    import warnings

    warnings.warn(
        "Native Rust extension 'santanico' not available. "
        "Falling back to pure-Python implementation (PyRtfStreamFilter).",
        RuntimeWarning,
        stacklevel=2,
    )
    # Fall back transparently
    RtfStreamFilter = PyRtfStreamFilter


__all__ = [
    "PyRtfStreamFilter",  # Explicit pure-Python implementation
    "RtfStreamFilter",  # Default (Rust if compiled, Python as fallback)
    "StreamingFilter",  # Shared streaming interface
]

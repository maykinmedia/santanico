from ._reference_rtf_filter import PyRtfStreamFilter

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
    RtfStreamFilter = PyRtfStreamFilter  # type: ignore

__all__ = [
    "PyRtfStreamFilter",  # Explicit pure-Python implementation
    "RtfStreamFilter",  # Default (Rust if compiled, Python as fallback)
]

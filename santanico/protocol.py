"""Structural interface implemented by every santanico streaming filter.

This module defines :class:`StreamingFilter`, the shared contract between the
native Rust implementation and the pure-Python fallback.
"""

from typing import Protocol


class StreamingFilter(Protocol):
    """A stateful, single-use-per-document metadata stream filter.

    Feed the source document in arbitrary chunks with :meth:`process_chunk`
    and collect the returned bytes in order. To reuse the same instance for
    another document, call :meth:`reset` first.

    Instances are **not thread-safe**: sharing one across threads interleaves
    their streaming state and corrupts the output. Create one filter per
    stream (e.g. one per thread) and feed each only its own chunks,
    sequentially.
    """

    def reset(self) -> None:
        """Reset all internal state to that of a freshly created filter.

        After this call the filter behaves byte-for-byte identically to a
        newly constructed filter, discarding any partially consumed or
        in-progress input.
        """
        ...

    def process_chunk(self, chunk: bytes, /) -> bytes:
        """Feed a chunk of bytes into the stream and return the filtered output.

        :param chunk: Any slice of the source document. May be empty, and may
            split a control word, escape sequence, or brace group at any point.
        :returns: The metadata-stripped bytes corresponding to this chunk, in
            order. Concatenating the results of successive calls yields the
            fully stripped document.
        """
        ...

"""High-performance streaming filter that strips RTF metadata in O(1) space.

This module exposes a zero-allocation, stateful byte-stream filter. It removes
metadata/structural destination groups (e.g. ``\\info``, ``\\fonttbl``,
``\\generator``) and everything inside them while preserving all document
content and formatting groups (e.g. ``\\b``, ``\\par``).

The filter is a streaming finite state machine: it keeps only O(1) state and
can be fed an arbitrary sequence of byte chunks of any size, including splits
mid-escape, mid-keyword, or mid-brace. The concatenation of each chunk's
output equals the output of processing the whole stream at once.
"""

class RtfStreamFilter:
    """Streaming state machine for stripping RTF metadata.

    Instances are stateful and single-use per document. Feed the document's
    bytes via :meth:`process_chunk` (possibly across many calls) and collect
    the returned bytes. Call :meth:`reset` to return the filter to a fresh
    state so it can be reused for another document.

    Instances are not thread-safe: sharing one instance across threads
    interleaves their streaming state and corrupts the output. Create one
    filter per stream (e.g. one per thread) and feed each only its own
    chunks, sequentially.
    """

    def __init__(self) -> None:
        """Create a new filter in its initial (fresh) state."""

    def reset(self) -> None:
        """Reset all internal state to that of a freshly created filter.

        After this call the filter behaves byte-for-byte identically to a
        newly constructed :class:`RtfStreamFilter`, discarding any
        partially consumed or in-progress input.
        """

    def process_chunk(self, chunk: bytes, /) -> bytes:
        """Feed a chunk of RTF bytes into the stream and return the filtered output.

        Args:
            chunk: Any slice of the source document. May be empty, and may
                split a control word, escape sequence, or brace group at any
                point.

        Returns:
            The metadata-stripped bytes corresponding to this chunk, in order.
            Concatenating the results of successive calls yields the fully
            stripped document.
        """

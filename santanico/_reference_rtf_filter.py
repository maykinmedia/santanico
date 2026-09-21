"""Pure-Python reference implementation of the RTF metadata stream filter.

A line-for-line port of the Rust `RtfStreamFilter` state machine in `src/lib.rs`.
It exists to:

1. Provide a baseline for throughput comparisons in `test_rtf_benchmark.py`.
2. Act as a fallback for platforms where the Rust binary isn't available.

The public API mirrors the Rust class: `process_chunk(chunk: bytes) -> bytes`
and `reset()`.

The destination set mirrors `is_destination_tag` in `src/lib.rs`: ONLY
privacy-sensitive destinations are stripped; presentation tables (fonts,
colors, styles, math) are left intact.
"""

from __future__ import annotations

_SLASH = 92
_OBRACE = 123
_CLOBRACE = 125
_STAR = 42

_STATE_NONE = 0
_STATE_EXPECT_SLASH = 1
_STATE_COLLECTING_WORD = 2
_STATE_COLLECTING_DEST = 3

# Control words that open a privacy-sensitive destination block.
# Keep in lockstep with `is_destination_tag` in src/lib.rs.
_DEST_TAGS = frozenset(
    [
        # Document Info & Core Properties
        b"info",
        b"doccomm",
        b"keywords",
        b"comment",
        b"author",
        b"title",
        b"subject",
        b"company",
        b"manager",
        b"category",
        b"operator",
        # Session Tracking & Revision History
        b"rsidtbl",
        b"trackedchanges",
        # Reviewer Annotations
        b"annotation",
        b"atnauthor",
        b"atndate",
        b"atnicn",
        # Generator Signatures, Custom Props, & Internal XML Schemas
        b"generator",
        b"userprops",
        b"xmltbl",
        b"customxml",
    ]
)

# Maximum length of any destination tag. Used to bound `_header_buf` so an
# adversarial unterminated control word cannot grow it to O(input size).
# Keep in lockstep with `MAX_DEST_LEN` in src/lib.rs.
_MAX_DEST_LEN = 32


def _is_ascii_alpha(b: int) -> bool:
    return (97 <= b <= 122) or (65 <= b <= 90)


def _is_destination_tag(tag: bytes) -> bool:
    return tag in _DEST_TAGS


class PyRtfStreamFilter:
    __slots__ = (
        "_brace_depth",
        "_escaped",
        "_header_buf",
        "_header_state",
        "_suppress_at_depth",
    )

    def __init__(self) -> None:
        self._brace_depth = 0
        self._suppress_at_depth = None
        self._escaped = False
        self._header_state = _STATE_NONE
        self._header_buf = bytearray()

    def reset(self) -> None:
        self._brace_depth = 0
        self._suppress_at_depth = None
        self._escaped = False
        self._header_state = _STATE_NONE
        self._header_buf.clear()

    def process_chunk(self, chunk: bytes) -> bytes:
        out = bytearray()
        buf = self._header_buf
        for b in chunk:
            # 1. Escaped byte handling (e.g. \{, \}, \\)
            if self._escaped:
                self._escaped = False
                if self._suppress_at_depth is None:
                    if self._header_state != _STATE_NONE:
                        self._flush_header(out)
                    out.append(b)
                continue

            # 2. While collecting a control word, a non-word byte completes it.
            if self._suppress_at_depth is None and (
                self._header_state == _STATE_COLLECTING_WORD
                or self._header_state == _STATE_COLLECTING_DEST
            ):
                collecting_dest = self._header_state == _STATE_COLLECTING_DEST
                word_empty = (len(buf) == 4) if collecting_dest else (len(buf) == 2)
                if collecting_dest:
                    is_word_char = _is_ascii_alpha(b)
                else:
                    is_word_char = _is_ascii_alpha(b) or (word_empty and b == _STAR)
                # Bound the word: once it exceeds MAX_DEST_LEN it cannot be a
                # destination, so stop collecting and let _decide_header flush
                # it verbatim. This keeps _header_buf O(1) even for an
                # adversarial unterminated control word.
                if collecting_dest:
                    within_bound = len(buf) < 4 + _MAX_DEST_LEN
                else:
                    within_bound = len(buf) < 2 + _MAX_DEST_LEN
                if is_word_char and within_bound:
                    buf.append(b)
                    continue
                self._decide_header(b, out)
                continue

            # 3. Unescaped backslash
            if b == _SLASH:
                if self._suppress_at_depth is None:
                    if self._header_state == _STATE_EXPECT_SLASH:
                        buf.append(_SLASH)
                        self._header_state = _STATE_COLLECTING_WORD
                    elif self._header_state == _STATE_NONE:
                        self._escaped = True
                        out.append(_SLASH)
                else:
                    self._escaped = True
                continue

            # 4. Unescaped opening brace '{'
            if b == _OBRACE:
                if self._suppress_at_depth is None:
                    if self._header_state != _STATE_NONE:
                        self._flush_header(out)
                    self._header_state = _STATE_EXPECT_SLASH
                    buf.clear()
                    buf.append(_OBRACE)
                self._brace_depth += 1
                continue

            # 5. Unescaped closing brace '}'
            if b == _CLOBRACE:
                if self._suppress_at_depth is not None:
                    if self._brace_depth == self._suppress_at_depth:
                        self._suppress_at_depth = None
                else:
                    if self._header_state != _STATE_NONE:
                        self._flush_header(out)
                    out.append(_CLOBRACE)
                self._brace_depth = (
                    self._brace_depth - 1 if self._brace_depth > 0 else 0
                )
                continue

            # 6. Normal byte (neither '\', '{', nor '}')
            if self._suppress_at_depth is None:
                if self._header_state == _STATE_EXPECT_SLASH:
                    buf.append(b)
                    self._flush_header(out)
                elif self._header_state == _STATE_NONE:
                    out.append(b)
        return bytes(out)

    def _current_word(self) -> bytearray:
        if self._header_state == _STATE_COLLECTING_WORD:
            return self._header_buf[2:]
        if self._header_state == _STATE_COLLECTING_DEST:
            return self._header_buf[4:]
        return bytearray()

    def _word_is_star(self) -> bool:
        return (
            self._header_state == _STATE_COLLECTING_WORD
            and len(self._header_buf) == 3
            and self._header_buf[2] == _STAR
        )

    def _is_current_word_destination(self) -> bool:
        w = self._current_word()
        return len(w) > 0 and _is_destination_tag(bytes(w))

    def _flush_header(self, out: bytearray) -> None:
        out.extend(self._header_buf)
        self._header_buf.clear()
        self._header_state = _STATE_NONE

    def _discard_header(self) -> None:
        self._header_buf.clear()
        self._header_state = _STATE_NONE

    def _begin_suppression(self) -> None:
        self._suppress_at_depth = self._brace_depth
        self._header_buf.clear()
        self._header_state = _STATE_NONE

    def _decide_header(self, b: int, out: bytearray) -> None:
        # '{\*\...' -> the destination marker '*' is followed by '\'.
        if self._word_is_star() and b == _SLASH:
            self._header_buf.append(_SLASH)
            self._header_state = _STATE_COLLECTING_DEST
            return

        if self._is_current_word_destination():
            if b == _CLOBRACE:
                # Empty destination group (e.g. '{\info}'); discard, emit nothing.
                self._discard_header()
                self._brace_depth = (
                    self._brace_depth - 1 if self._brace_depth > 0 else 0
                )
            else:
                # Destination group with a body; suppress until the matching '}'.
                self._begin_suppression()
                if b == _OBRACE:
                    # The delimiter is a nested group's '{'; count it for depth.
                    self._brace_depth += 1
                elif b == _SLASH:
                    # The delimiter is a backslash, i.e. the start of an escape
                    # in the group body. Mark it so the following byte is consumed
                    # as its partner, keeping brace counting in sync while we
                    # suppress (otherwise a real closing '}' could be eaten as an
                    # escaped byte, e.g. '{\info\\}').
                    self._escaped = True
            return

        # Not a destination: keep the group verbatim.
        if len(self._current_word()) == 0:
            # No control word; 'b' is a literal, not a group boundary.
            self._header_buf.append(b)
            self._flush_header(out)
        elif b == _OBRACE:
            # A control word followed by '{' opens a nested group.
            self._flush_header(out)
            self._brace_depth += 1
            self._header_state = _STATE_EXPECT_SLASH
            self._header_buf.clear()
            self._header_buf.append(_OBRACE)
        elif b == _CLOBRACE:
            # The control word's group closes here.
            self._flush_header(out)
            out.append(_CLOBRACE)
            self._brace_depth = self._brace_depth - 1 if self._brace_depth > 0 else 0
        else:
            # Delimiter or ordinary byte; keep it.
            self._header_buf.append(b)
            self._flush_header(out)
        # A backslash delimiter is the start of an escape in the (kept)
        # content; mark it so the following byte is consumed as its partner,
        # keeping the output verbatim (e.g. '{\b\\{...}}').
        if b == _SLASH:
            self._escaped = True

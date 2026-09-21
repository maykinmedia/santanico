from __future__ import annotations

from dataclasses import dataclass

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from santanico import PyRtfStreamFilter, RtfStreamFilter

# AST NODES
# =========


@dataclass(frozen=True)
class TextNode:
    content: bytes

    def render_raw(self) -> bytes:
        return self.content

    def render_clean(self) -> bytes:
        return self.content


def _sep(no_space: bool, raw_inner: bytes) -> bytes:
    r"""Delimiter between a group's control word and its content.

    A control word is a maximal run of letters, so ``{\info`` may only be
    immediately followed by a *non-letter* (``{``, ``\``, a digit, ...). If
    ``no_space`` is requested but the content starts with a letter, fall back
    to a space so the word and content don't merge into a different control
    word (which would not be valid RTF).
    """
    if no_space and (
        not raw_inner or not (65 <= raw_inner[0] <= 90 or 97 <= raw_inner[0] <= 122)
    ):
        return b""
    return b" "


@dataclass(frozen=True)
class FormattingGroupNode:
    kw: bytes
    no_space: bool
    children: list[ASTNode]

    def render_raw(self) -> bytes:
        inner = b"".join(c.render_raw() for c in self.children)
        return b"{" + self.kw + _sep(self.no_space, inner) + inner + b"}"

    def render_clean(self) -> bytes:
        # The separator is decided from the *raw* content (what the filter
        # sees) so raw and clean always agree on the delimiter.
        raw_inner = b"".join(c.render_raw() for c in self.children)
        inner = b"".join(c.render_clean() for c in self.children)
        return b"{" + self.kw + _sep(self.no_space, raw_inner) + inner + b"}"


@dataclass(frozen=True)
class MetadataGroupNode:
    kw: bytes
    no_space: bool
    children: list[ASTNode]

    def render_raw(self) -> bytes:
        inner = b"".join(c.render_raw() for c in self.children)
        return b"{" + self.kw + _sep(self.no_space, inner) + inner + b"}"

    def render_clean(self) -> bytes:
        return b""


ASTNode = TextNode | FormattingGroupNode | MetadataGroupNode


# HYPOTHESIS STRATEGIES FOR RTF GRAMMAR
# =====================================

rtf_plain_text: st.SearchStrategy[bytes] = st.text(
    alphabet=st.characters(
        min_codepoint=32, max_codepoint=126, blacklist_characters=r"\{}"
    ),
    min_size=1,
    max_size=20,
).map(lambda s: s.encode("ascii"))
"Generates safe RTF plain text (contains no braces or backslashes)"

rtf_escapes: st.SearchStrategy[bytes] = st.sampled_from([rb"\\", rb"\{", rb"\}"])
"Generates explicit RTF escapes"

rtf_leaves: st.SearchStrategy[TextNode] = st.one_of(rtf_plain_text, rtf_escapes).map(
    TextNode
)
"Generates leaf nodes (pure text or escaped tokens)"

destination_kws: st.SearchStrategy[bytes] = st.sampled_from(
    [
        # Document Info & Core Properties
        rb"\info",
        rb"\doccomm",
        rb"\keywords",
        rb"\comment",
        rb"\author",
        rb"\title",
        rb"\subject",
        rb"\company",
        rb"\manager",
        rb"\category",
        rb"\operator",
        # Session Tracking & Revision History
        rb"\rsidtbl",
        rb"\trackedchanges",
        # Reviewer Annotations
        rb"\annotation",
        rb"\atnauthor",
        rb"\atndate",
        rb"\atnicn",
        # Generator Signatures, Custom Props, & Internal XML Schemas
        rb"\*\generator",
        rb"\userprops",
        rb"\*\xmltbl",
        rb"\customxml",
    ]
)
"""
Generates known destination control words (must be stripped)

IMPORTANT: keep this in lockstep with `is_destination_tag` in src/lib.rs.
It lists ONLY privacy-sensitive destinations; presentation tables
(fonttbl, colortbl, stylesheet, pict, ...) are intentionally NOT stripped.
"""

formatting_kws: st.SearchStrategy[bytes] = st.sampled_from(
    [
        rb"\b",
        rb"\dbch",
        rb"\f0",
        rb"\f1",
        rb"\hich",
        rb"\i",
        rb"\lang1033",
        rb"\loch",
        rb"\par",
        rb"\qc",
    ]
)
"Generates formatting control words (which must be preserved)"


def rtf_ast_nodes() -> st.SearchStrategy[ASTNode]:
    """Return a strategy which generates RTF ASTNodes

    ``node.render_raw() -> bytes`` returns a raw, unstripped RTF snippet
    ``node.render_clean() -> bytes`` returns the stripped RTF snippet
    """
    return st.recursive(
        rtf_leaves,
        lambda children: st.one_of(
            # 1. Plain text leaves
            rtf_leaves,
            # 2. Formatting groups (e.g., {\loch ...}, {\b ...})
            st.builds(
                FormattingGroupNode,
                kw=formatting_kws,
                no_space=st.booleans(),
                children=st.lists(children, max_size=4),
            ),
            # 3. Metadata groups (e.g., {\info ...}, {\*\xmltbl ...})
            st.builds(
                MetadataGroupNode,
                kw=destination_kws,
                no_space=st.booleans(),
                children=st.lists(children, max_size=4),
            ),
        ),
        max_leaves=25,
    )


@st.composite
def rtf_documents(draw) -> bytes:
    "Generate RTF document pairs (raw_bytes, expected_stripped_bytes)"
    children = draw(st.lists(rtf_ast_nodes(), min_size=1, max_size=10))

    raw_doc = rb"{\rtf1 " + b"".join(c.render_raw() for c in children) + b"}"

    return raw_doc


@st.composite
def rtf_document_pairs(draw) -> tuple[bytes, bytes]:
    "Generate RTF document pairs (raw_bytes, expected_stripped_bytes)"
    children = draw(st.lists(rtf_ast_nodes(), min_size=1, max_size=10))

    raw_doc = rb"{\rtf1 " + b"".join(c.render_raw() for c in children) + b"}"
    expected_doc = rb"{\rtf1 " + b"".join(c.render_clean() for c in children) + b"}"

    return raw_doc, expected_doc


def strip_all(data: bytes) -> bytes:
    filter_engine = RtfStreamFilter()
    return filter_engine.process_chunk(data)


@given(rtf_documents())
def test_monotonicity(s: bytes):
    """
    Law of Contraction / Monotonicity: |φ(s)| <= |s|
    The filter must never invent or expand data.
    """
    assert len(strip_all(s)) <= len(s)


@given(rtf_documents())
def test_idempotence(s: bytes):
    """
    Law of Idempotence: φ(φ(s)) == φ(s)
    Processing a sanitized document a second time changes nothing.
    """
    stripped_once = strip_all(s)
    stripped_twice = strip_all(stripped_once)
    assert stripped_once == stripped_twice


@example(
    # a destination group immediately followed by a nested group (no delimiter space).
    (rb"{\rtf1 {\info{\title T}{\author A}} {\b keep} t}", rb"{\rtf1  {\b keep} t}")
)
@given(rtf_document_pairs())
def test_oracle_equivalence(doc_pair: tuple[bytes, bytes]):
    """
    Oracle Test: Asserts that filtering the raw RTF produces
    the EXACT byte sequence specified by the AST's ground-truth clean rendering.
    """
    raw_doc, expected_clean_doc = doc_pair
    assert strip_all(raw_doc) == expected_clean_doc


@pytest.mark.parametrize(
    "Filter",
    [RtfStreamFilter, PyRtfStreamFilter],
    ids=["rust", "python"],
)
@given(
    rtf_document_pairs(),
    st.lists(st.integers(min_value=1, max_value=20), min_size=1, max_size=10),
)
def test_monoid_homomorphism_across_grammar_chunks(
    Filter: type[RtfStreamFilter | PyRtfStreamFilter],
    doc_pair: tuple[bytes, bytes],
    chunk_sizes: list[int],
):
    """
    State Transition Homomorphism: δ(s1 · s2) == δ(s1) · δ(s2)

    Processing a document all at once must yield the exact same bytes
    as processing it in arbitrary chunks sequentially.

    Slices syntactically valid RTF at arbitrary points (including mid-keyword,
    mid-escape, and mid-brace) to ensure stream-state continuity.
    """
    raw_doc, expected_clean_doc = doc_pair

    # Slice raw_doc into arbitrary stream chunks
    chunks: list[bytes] = []
    idx = 0
    for size in chunk_sizes:
        if idx >= len(raw_doc):
            break
        chunks.append(raw_doc[idx : idx + size])
        idx += size
    if idx < len(raw_doc):
        chunks.append(raw_doc[idx:])

    # Process through streaming FSM
    filter_engine = Filter()
    chunked_output = b"".join(filter_engine.process_chunk(c) for c in chunks)

    assert chunked_output == expected_clean_doc


@pytest.mark.parametrize(
    "Filter",
    [RtfStreamFilter, PyRtfStreamFilter],
    ids=["rust", "python"],
)
@given(rtf_documents(), rtf_ast_nodes())
def test_reset(
    Filter: type[RtfStreamFilter | PyRtfStreamFilter], doc: bytes, garbage: ASTNode
):
    f = Filter()

    cleaned_doc = f.process_chunk(doc)

    # put filter in some state, halfway of some piece of rtf
    node_bytes = garbage.render_raw()
    f.process_chunk(node_bytes[: max(1, len(node_bytes) // 2)])

    f.reset()

    assert f.process_chunk(doc) == cleaned_doc

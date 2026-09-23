use pyo3::prelude::*;
use pyo3::types::PyBytes;

/// A zero-allocation, streaming state machine for stripping RTF metadata in O(1) space.
#[derive(Debug, Clone)]
pub struct RtfStreamFilter {
    brace_depth: usize,
    suppress_at_depth: Option<usize>,
    escaped: bool,
    header_state: HeaderState,
    header_buf: Vec<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum HeaderState {
    /// Normal byte streaming.
    None,
    /// Just encountered `{`, waiting for `\` or whitespace.
    ExpectSlash,
    /// Collecting the control word name right after `{\\`.
    CollectingWord,
    /// After `{\\*\\`, collecting the real destination name.
    CollectingDest,
}

impl Default for RtfStreamFilter {
    fn default() -> Self {
        Self::new()
    }
}

impl RtfStreamFilter {
    pub fn new() -> Self {
        Self {
            brace_depth: 0,
            suppress_at_depth: None,
            escaped: false,
            header_state: HeaderState::None,
            header_buf: Vec::with_capacity(32),
        }
    }

    pub fn reset(&mut self) {
        self.brace_depth = 0;
        self.suppress_at_depth = None;
        self.escaped = false;
        self.header_state = HeaderState::None;
        self.header_buf.clear();
    }

    pub fn process_chunk(&mut self, chunk: &[u8], output: &mut Vec<u8>) {
        output.reserve(chunk.len());

        for &b in chunk {
            // 1. Escaped byte handling (e.g. \{, \}, \\)
            if self.escaped {
                self.escaped = false;
                if self.suppress_at_depth.is_none() {
                    if self.header_state != HeaderState::None {
                        // An escaped char cannot continue a control word, so the
                        // group does not begin with a destination; keep it verbatim.
                        self.flush_header(output);
                    }
                    output.push(b);
                }
                continue;
            }

            // 2. While collecting a control word, a non-word byte completes it.
            //    Decide (suppress or keep) before '{' / '}' / '\' are reinterpreted.
            if self.suppress_at_depth.is_none()
                && (self.header_state == HeaderState::CollectingWord
                    || self.header_state == HeaderState::CollectingDest)
            {
                let collecting_dest = self.header_state == HeaderState::CollectingDest;
                let word_empty = if collecting_dest {
                    self.header_buf.len() == 4
                } else {
                    self.header_buf.len() == 2
                };
                let is_word_char = if collecting_dest {
                    b.is_ascii_alphabetic()
                } else {
                    // Letters always extend the word; '*' only as the first char
                    // (the destination marker in '{\*\dest').
                    b.is_ascii_alphabetic() || (word_empty && b == b'*')
                };
                if is_word_char {
                    self.header_buf.push(b);
                    continue;
                }
                self.decide_header(b, output);
                continue;
            }

            // 3. Unescaped backslash
            if b == b'\\' {
                if self.suppress_at_depth.is_none() {
                    match self.header_state {
                        HeaderState::ExpectSlash => {
                            // '{\' -> begin collecting the first control word.
                            self.header_buf.push(b'\\');
                            self.header_state = HeaderState::CollectingWord;
                        }
                        HeaderState::None => {
                            // Ordinary escaped backslash; pass it through verbatim.
                            self.escaped = true;
                            output.push(b'\\');
                        }
                        // CollectingWord / CollectingDest are handled in step 2.
                        _ => {}
                    }
                } else {
                    // Suppressing: swallow the next byte too.
                    self.escaped = true;
                }
                continue;
            }

            // 4. Unescaped opening brace '{'
            if b == b'{' {
                if self.suppress_at_depth.is_none() {
                    if self.header_state != HeaderState::None {
                        // A nested group starts before the outer header scan
                        // finished (e.g. `{{`); the outer group is not a destination.
                        self.flush_header(output);
                    }
                    self.header_state = HeaderState::ExpectSlash;
                    self.header_buf.clear();
                    self.header_buf.push(b'{');
                }
                self.brace_depth += 1;
                continue;
            }

            // 5. Unescaped closing brace '}'
            if b == b'}' {
                if let Some(depth) = self.suppress_at_depth {
                    if self.brace_depth == depth {
                        self.suppress_at_depth = None;
                    }
                } else {
                    if self.header_state != HeaderState::None {
                        // The group ended before a control word was recognised
                        // (e.g. `{}`); keep the header verbatim.
                        self.flush_header(output);
                    }
                    output.push(b'}');
                }
                self.brace_depth = self.brace_depth.saturating_sub(1);
                continue;
            }

            // 6. Normal byte (neither '\', '{', nor '}')
            if self.suppress_at_depth.is_none() {
                match self.header_state {
                    HeaderState::ExpectSlash => {
                        // The group does not begin with a control word; keep verbatim.
                        self.header_buf.push(b);
                        self.flush_header(output);
                    }
                    HeaderState::None => {
                        output.push(b);
                    }
                    // CollectingWord / CollectingDest are handled in step 2.
                    _ => {}
                }
            }
        }
    }

    /// The control word currently being collected (empty if none).
    fn current_word(&self) -> &[u8] {
        match self.header_state {
            HeaderState::CollectingWord => &self.header_buf[2..],
            HeaderState::CollectingDest => &self.header_buf[4..],
            _ => &[],
        }
    }

    /// True when the word being collected is exactly the destination marker `*`.
    fn word_is_star(&self) -> bool {
        self.header_state == HeaderState::CollectingWord
            && self.current_word().len() == 1
            && self.current_word()[0] == b'*'
    }

    /// True when the word being collected names a destination to strip.
    fn is_current_word_destination(&self) -> bool {
        let w = self.current_word();
        !w.is_empty() && is_destination_tag(w)
    }

    /// Emits the buffered group header verbatim and stops scanning.
    fn flush_header(&mut self, output: &mut Vec<u8>) {
        output.extend_from_slice(&self.header_buf);
        self.header_buf.clear();
        self.header_state = HeaderState::None;
    }

    /// Discards the buffered group header (an empty destination group).
    fn discard_header(&mut self) {
        self.header_buf.clear();
        self.header_state = HeaderState::None;
    }

    /// Marks the current group (at `brace_depth`) as suppressed and drops its header.
    fn begin_suppression(&mut self) {
        self.suppress_at_depth = Some(self.brace_depth);
        self.header_buf.clear();
        self.header_state = HeaderState::None;
    }

    /// The control word just completed on byte `b`; decide to suppress or keep.
    fn decide_header(&mut self, b: u8, output: &mut Vec<u8>) {
        // '{\*\...' -> the destination marker '*' is followed by '\'.
        if self.word_is_star() && b == b'\\' {
            self.header_buf.push(b'\\');
            self.header_state = HeaderState::CollectingDest;
            return;
        }

        if self.is_current_word_destination() {
            if b == b'}' {
                // Empty destination group (e.g. '{\info}'); discard, emit nothing.
                self.discard_header();
                self.brace_depth = self.brace_depth.saturating_sub(1);
            } else {
                // Destination group with a body; suppress until the matching '}'.
                self.begin_suppression();
                match b {
                    b'{' => {
                        // The delimiter is a nested group's '{'; count it for depth.
                        self.brace_depth += 1;
                    }
                    b'\\' => {
                        // The delimiter is a backslash, i.e. the start of an escape
                        // in the group body. Mark it so the following byte is consumed
                        // as its partner, keeping brace counting in sync while we
                        // suppress (otherwise a real closing '}' could be eaten as an
                        // escaped byte, e.g. '{\info\\}').
                        self.escaped = true;
                    }
                    _ => {}
                }
            }
            return;
        }

        // Not a destination: keep the group verbatim.
        if self.current_word().is_empty() {
            // No control word; 'b' is a literal, not a group boundary.
            self.header_buf.push(b);
            self.flush_header(output);
        } else {
            match b {
                b'{' => {
                    // A control word followed by '{' opens a nested group.
                    self.flush_header(output);
                    self.brace_depth += 1;
                    self.header_state = HeaderState::ExpectSlash;
                    self.header_buf.clear();
                    self.header_buf.push(b'{');
                }
                b'}' => {
                    // The control word's group closes here.
                    self.flush_header(output);
                    output.push(b'}');
                    self.brace_depth = self.brace_depth.saturating_sub(1);
                }
                _ => {
                    // Delimiter or ordinary byte; keep it.
                    self.header_buf.push(b);
                    self.flush_header(output);
                }
            }
        }
        // A backslash delimiter is the start of an escape in the (kept)
        // content; mark it so the following byte is consumed as its partner,
        // keeping the output verbatim (e.g. '{\b\\{...}}').
        if b == b'\\' {
            self.escaped = true;
        }
    }
}

/// Matches ONLY hidden privacy hazards, editing history, and tool metadata,
/// leaving presentation tables (fonts, colors, styles, math) completely intact.
#[inline]
fn is_destination_tag(tag: &[u8]) -> bool {
    matches!(
        tag,
        // Document Info & Core Properties
        b"info"
            | b"doccomm"
            | b"keywords"
            | b"comment"
            | b"author"
            | b"title"
            | b"subject"
            | b"company"
            | b"manager"
            | b"category"
            | b"operator"
        // Session Tracking & Revision History
            | b"rsidtbl"
            | b"trackedchanges"
        // Reviewer Annotations
            | b"annotation"
            | b"atnauthor"
            | b"atndate"
            | b"atnicn"
        // Generator Signatures, Custom Props, & Internal XML Schemas
            | b"generator"
            | b"userprops"
            | b"xmltbl"
            | b"customxml"
    )
}

#[pyclass(name = "RtfStreamFilter")]
pub struct PyRtfStreamFilter {
    inner: RtfStreamFilter,
}

#[pymethods]
impl PyRtfStreamFilter {
    #[new]
    fn new() -> Self {
        Self {
            inner: RtfStreamFilter::new(),
        }
    }

    fn reset(&mut self) {
        self.inner.reset();
    }

    fn process_chunk<'py>(
        &mut self,
        py: Python<'py>,
        chunk: &[u8],
    ) -> PyResult<Bound<'py, PyBytes>> {
        let output = py.detach(|| {
            let mut out = Vec::with_capacity(chunk.len());
            self.inner.process_chunk(chunk, &mut out);
            out
        });
        Ok(PyBytes::new(py, &output))
    }
}

#[pymodule]
fn santanico(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyRtfStreamFilter>()?;
    Ok(())
}

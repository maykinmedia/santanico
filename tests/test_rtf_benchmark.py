import pytest

from santanico import PyRtfStreamFilter, RtfStreamFilter


def generate_large_rtf(target_mb: float = 20.0) -> bytes:
    """Generates a synthetic RTF payload containing both body text and metadata blocks."""
    header = (
        b"{\\rtf1\\ansi"
        b"{\\fonttbl{\\f0 Arial;}}"
        b"{\\colortbl ;\\red0\\green0\\blue0;}"
        b"{\\info{\\author Benchmarker}{\\title Large Test Payload}}"
    )
    footer = b"}"

    # Repeated body block containing formatting controls and embedded metadata
    block = (
        b"{\\para \\loch\\f0\\fs24 This is a realistic document body paragraph with "
        b"\\b bold text\\b0 and \\i italic text\\i0. }"
        b"{\\info{\\comment Nested metadata comment that must be stripped.}}"
        b"{\\para More standard content to exercise plain text streaming logic. }\n"
    )

    target_bytes = int(target_mb * 1024 * 1024)
    repeats = max(1, (target_bytes - len(header) - len(footer)) // len(block))

    return header + (block * repeats) + footer


CHUNK_SIZES = [
    None,  # Single shot (entire 20 MB at once) / zero overhead
    64 * 1024,  # 64 KiB (L2/L3 cache friendly, standard socket buffer)
    8 * 1024,  # 8 KiB (Typical OS page / file read buffer)
]


@pytest.mark.parametrize("chunk_size", CHUNK_SIZES, ids=["full", "64k", "8k"])
@pytest.mark.parametrize(
    "Filter",
    [RtfStreamFilter, PyRtfStreamFilter],
    ids=["rust", "python"],
)
def test_filter_throughput_20mb(Filter, chunk_size, benchmark):
    # 1. Generate payload and pre-chunk if a chunk size is requested
    payload = generate_large_rtf(target_mb=20.0)
    payload_size_mb = len(payload) / (1024 * 1024)

    filter_engine = Filter()

    if chunk_size is None:
        # Single-shot path
        def run_filter() -> bytes:
            filter_engine.reset()
            return filter_engine.process_chunk(payload)
    else:
        # Pre-slice chunks outside the benchmark closure
        chunks = [
            payload[i : i + chunk_size] for i in range(0, len(payload), chunk_size)
        ]

        def run_filter() -> bytes:
            filter_engine.reset()
            return b"".join(map(filter_engine.process_chunk, chunks))

    # 2. Execute benchmark loop
    result = benchmark(run_filter)

    # 3. Compute throughput and attach extra info
    mean_time_seconds = benchmark.stats["mean"]
    throughput_mb_s = payload_size_mb / mean_time_seconds

    chunk_label = f"{chunk_size // 1024}k" if chunk_size else "full"
    benchmark.extra_info["payload_size_mb"] = round(payload_size_mb, 2)
    benchmark.extra_info["chunk_size"] = chunk_label
    benchmark.extra_info["throughput_mb_s"] = round(throughput_mb_s, 2)

    # 4. Correctness assertions (real correctness is established in PBT tests)
    assert len(result) < len(payload)
    assert b"Benchmarker" not in result
    assert b"bold text" in result

    print(
        f"\nThroughput ({chunk_label}): {throughput_mb_s:.2f} MB/s "
        f"({payload_size_mb:.2f} MB in {mean_time_seconds * 1000:.2f} ms)"
    )

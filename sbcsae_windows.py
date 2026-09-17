"""Phase 2: fixed-size word windows for long-document LLM segmentation.

800-word windows, 600-word stride: each window SCORES only its central
600 words (the "core"); the 100 words on either side are shown as context
only ("margin"), never scored. Cores are cut by word count alone,
independent of IU or turn boundaries, and tile the document exactly: the
first core starts at word 1 (no left margin exists yet), the last core
ends at the document's last word (no right margin exists there either).
Word indices throughout are GLOBAL (1-indexed over the whole document),
never renumbered per window -- see sbcsae_llm.py.
"""
from __future__ import annotations

from dataclasses import dataclass

CORE = 600
MARGIN = 100


@dataclass(frozen=True)
class ScoreRegion:
    score_start: int  # 1-indexed, inclusive
    score_end: int  # 1-indexed, inclusive
    window_start: int  # score_start - MARGIN, clamped to 1
    window_end: int  # score_end + MARGIN, clamped to n_tokens


def build_score_regions(n_tokens: int, core: int = CORE, margin: int = MARGIN) -> list[ScoreRegion]:
    """Partition [1, n_tokens] into contiguous, non-overlapping `core`-word
    score regions (the last one shorter if n_tokens is not a multiple of
    `core`), each paired with a `margin`-word context window on both
    sides, clamped at the document's edges.

    Raises ValueError if n_tokens <= 0.
    """
    if n_tokens <= 0:
        raise ValueError(f"n_tokens must be positive, got {n_tokens}")

    regions = []
    s = 1
    while s <= n_tokens:
        e = min(s + core - 1, n_tokens)
        regions.append(
            ScoreRegion(
                score_start=s,
                score_end=e,
                window_start=max(1, s - margin),
                window_end=min(n_tokens, e + margin),
            )
        )
        s = e + 1
    return regions


def assert_regions_tile(regions: list[ScoreRegion], n_tokens: int) -> None:
    """Raise AssertionError unless the regions' score ranges partition
    [1, n_tokens] exactly: no gap, no overlap, starting at 1 and ending at
    n_tokens.
    """
    if not regions:
        raise AssertionError(f"no regions for n_tokens={n_tokens}")
    if regions[0].score_start != 1:
        raise AssertionError(f"first region starts at {regions[0].score_start}, not 1")
    if regions[-1].score_end != n_tokens:
        raise AssertionError(f"last region ends at {regions[-1].score_end}, not n_tokens={n_tokens}")
    for prev, nxt in zip(regions, regions[1:]):
        if nxt.score_start != prev.score_end + 1:
            raise AssertionError(
                f"gap or overlap between regions: {prev.score_start}-{prev.score_end} "
                f"then {nxt.score_start}-{nxt.score_end}"
            )


def region_for_boundary(regions: list[ScoreRegion], boundary: int) -> ScoreRegion:
    """The region a boundary position belongs to: whichever region's score
    range contains the word immediately AFTER the boundary (boundary b
    falls between word b and word b+1; the region owning word b+1 is the
    region where the new segment begins). Raises ValueError if no region
    (or more than one) claims it -- should never happen when `regions`
    tiles [1, n_tokens] exactly (see assert_regions_tile).
    """
    owners = [r for r in regions if r.score_start <= boundary + 1 <= r.score_end]
    if len(owners) != 1:
        raise ValueError(f"boundary {boundary} claimed by {len(owners)} region(s), expected exactly 1")
    return owners[0]


def assert_boundaries_each_in_one_region(regions: list[ScoreRegion], boundaries: set[int], n_tokens: int) -> None:
    """Raise ValueError (via region_for_boundary) unless every boundary in
    `boundaries` belongs to exactly one region. `boundaries` must only
    contain valid positions (1 <= b < n_tokens).
    """
    for b in boundaries:
        if not (1 <= b < n_tokens):
            raise ValueError(f"boundary {b} out of range [1, {n_tokens - 1}]")
        region_for_boundary(regions, b)

"""Phase 2: two-way scoring for turn-structured segmentation.

Every speaker change is a reference IU boundary by construction (the
transcriber never merges two speakers into one IU), so the prompt gives
those boundaries away for free: it labels each turn on its own line and
asks the model only for boundaries INSIDE a turn (excluding that turn's
own first word, which is never a legitimate answer -- see
score_document's ValueError for a hypothesis that includes one anyway).
The turn boundaries are then added back in code, not predicted.

Two scores are computed from the same pair of masses:

  - "all_boundaries": ref vs. hyp exactly as constructed (turn boundaries
    included on both sides -- they always match, since both are added
    identically, so this score gives partial credit for something the
    model was never actually asked to do).
  - "within_turn": both turn-boundary sets are removed before scoring, so
    only the boundaries the model actually had to decide are counted.
    This is the headline number.

These two are NOT comparable to each other: removing the turn boundaries
merges segments across every turn change, so "within_turn" is computed
over longer effective segments than "all_boundaries" is (median 36% of
this corpus's reference boundaries are speaker changes -- see
reports/phase2_per_file_stats.csv -- so this is not a marginal effect).
Exactly the same caveat CLAUDE.md already states for WindowDiff's
mean-segment-length-derived window size across corpora/phases applies
here within a single document's two scoring modes.
"""
from __future__ import annotations

from masses import boundaries_to_masses, masses_to_boundaries
from metrics import boundary_f1, boundary_precision_recall, boundary_similarity, window_diff

NON_COMPARABILITY_NOTE = (
    "all_boundaries and within_turn are computed over different effective "
    "segment lengths (within_turn merges every turn-change position into "
    "its neighbouring segment) and must never be compared to each other, "
    "only tracked separately across runs."
)


def _compute_metrics(ref_masses: list[int], hyp_masses: list[int]) -> dict:
    precision, recall = boundary_precision_recall(ref_masses, hyp_masses)
    ref_b = masses_to_boundaries(ref_masses)
    hyp_b = masses_to_boundaries(hyp_masses)
    # Hypothesis/reference boundary-count ratio: >1 means the hypothesis
    # over-segments relative to the reference, <1 under-segments. Not one
    # of metrics.py's published metrics (nothing to keep "unchanged" here)
    # -- a plain count ratio, added directly. 1.0 when both sides are
    # empty (perfect agreement on "no boundaries"); undefined (None) if
    # the reference has none but the hypothesis does, since no finite
    # ratio describes that.
    if ref_b:
        boundary_count_ratio = len(hyp_b) / len(ref_b)
    else:
        boundary_count_ratio = 1.0 if not hyp_b else None
    return {
        "precision": precision,
        "recall": recall,
        "f1": boundary_f1(ref_masses, hyp_masses),
        "window_diff": window_diff(ref_masses, hyp_masses),
        "boundary_similarity": boundary_similarity(ref_masses, hyp_masses),
        "boundary_count_ratio": boundary_count_ratio,
        # Plain counts, already computed above for the ratio -- exposed
        # directly so a caller (e.g. a per-sample CSV row) doesn't have to
        # re-derive them from boundary_count_ratio, which can lose
        # precision on the round trip.
        "n_ref_boundaries": len(ref_b),
        "n_hyp_boundaries": len(hyp_b),
    }


def score_document(
    ref_masses: list[int],
    turn_boundaries: set[int],
    hyp_within_turn_start_indices: list[int],
) -> dict:
    """Score one document both ways.

    ref_masses: the full IU-level reference masses (turn boundaries
        included -- e.g. DocumentStructure.ref_masses from sbcsae_llm.py).
    turn_boundaries: the subset of masses_to_boundaries(ref_masses) that
        are speaker changes (e.g. DocumentStructure.turn_boundaries).
    hyp_within_turn_start_indices: 1-indexed global word positions the
        model returned as within-turn unit starts (same "start position"
        convention as llm_segmenter.indices_to_masses) -- must NOT include
        any turn-initial position; those are added automatically below,
        not predicted.

    Returns {"all_boundaries": {...}, "within_turn": {...}, "note": str}.
    Raises ValueError if a hypothesis index names a turn-initial position
    (the model was never asked for those) or falls outside the document.
    """
    n_tokens = sum(ref_masses)
    ref_boundaries = masses_to_boundaries(ref_masses)
    if not turn_boundaries <= ref_boundaries:
        raise ValueError(
            f"turn_boundaries must be a subset of the reference boundaries: "
            f"{sorted(turn_boundaries - ref_boundaries)} are not reference boundaries"
        )

    hyp_added = set()
    for i in hyp_within_turn_start_indices:
        b = i - 1
        if not (1 <= b < n_tokens):
            raise ValueError(f"hypothesis index {i} out of range [2,{n_tokens}]")
        if b in turn_boundaries:
            raise ValueError(
                f"hypothesis index {i} names a turn-initial position; the model is only "
                f"ever asked for within-turn boundaries, turn boundaries are added in code"
            )
        hyp_added.add(b)

    hyp_boundaries = turn_boundaries | hyp_added
    hyp_masses = boundaries_to_masses(hyp_boundaries, n_tokens)

    all_boundaries_scores = _compute_metrics(ref_masses, hyp_masses)

    ref_within = ref_boundaries - turn_boundaries
    hyp_within = hyp_boundaries - turn_boundaries  # == hyp_added, spelled out for clarity
    ref_masses_within = boundaries_to_masses(ref_within, n_tokens)
    hyp_masses_within = boundaries_to_masses(hyp_within, n_tokens)
    within_turn_scores = _compute_metrics(ref_masses_within, hyp_masses_within)

    return {
        "all_boundaries": all_boundaries_scores,
        "within_turn": within_turn_scores,
        "headline": "within_turn",
        "note": NON_COMPARABILITY_NOTE,
    }

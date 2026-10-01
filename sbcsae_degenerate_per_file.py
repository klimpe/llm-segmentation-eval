"""Phase 2, batch 1: per-file degeneracy, replacing the whole-corpus
MAX_LEGITIMATE_RUN=11/DEGENERATE_FLAG_THRESHOLD=22 pair
(sbcsae_degenerate_threshold.py) with a per-file rule (reports/
phase2_llm_design.md's per-file degeneracy section documents why: 11 was
calibrated on a single outlier file, SBC038, and the 10 batch-1 files'
own legitimate maxima range 3-6 -- nowhere near 11).

A run is degenerate under the NEW rule iff it is BOTH longer than that
file's own observed maximum legitimate run AND predicts more than 3x
the reference boundaries actually present in the same span
(sbcsae_degenerate_threshold.per_file_review_policy).

Built on sbcsae_pilot.analyse's "all_window_runs" (every successful
draw's own run+span, regardless of whether it clears the OLD, whole-
corpus thresholds) -- this module never recomputes runs from raw cache
itself, only reclassifies what analyse() already found.

Two things this module adds beyond a yes/no flag per draw:

  - collapse_rate: the share of a file+condition's own window-draws
    that contain a NEW-rule-degenerate run. CLAUDE.md's own "Degenerate
    output" section requires flagging and reporting degenerate draws
    separately BECAUSE whole-file F1 barely moves when one window out
    of several collapses (confirmed on batch 1's own data: SBC053
    condition A had 4 of 5 samples auto-flagged under the OLD rule, yet
    folding them back into the aggregate moved F1 by only 0.007) -- a
    metric that is actually sensitive to how OFTEN this happens, not
    diluted by the rest of a mostly-fine document, is needed alongside
    F1, not instead of it.
  - share_words_in_runs: of every word actually scored across all
    n_samples draws for this file+condition, what share sat inside a
    degenerate run -- a second, complementary view (some files might
    collapse rarely but for a very long stretch each time; others often
    but briefly).
"""
from __future__ import annotations

from masses import masses_to_boundaries
from sbcsae_degenerate_threshold import file_max_legitimate_run, per_file_review_policy, review_policy
from sbcsae_llm import build_document_structure


def ref_boundaries_in_span(ref_within_sorted: list[int], span_start: int, span_end: int) -> int:
    """How many real within-turn reference boundaries fall in
    [span_start, span_end] -- ref_within_sorted is small enough per
    document (hundreds to low thousands of boundaries) that a linear
    scan per run is fine; this runs once per window-draw's own single
    longest run, not per word.
    """
    return sum(1 for b in ref_within_sorted if span_start <= b <= span_end)


def classify_window_runs(
    doc_id: str, units, condition_analysis: dict, core: int | None = None, margin: int | None = None
) -> list[dict]:
    """One record per entry in condition_analysis["all_window_runs"],
    carrying both the OLD (whole-corpus) and NEW (per-file) rule's
    verdict side by side. Pass core/margin if condition_analysis came
    from a non-default window size (e.g. the 400/300-word SBC053 test)
    -- see file_max_legitimate_run's own docstring for why.
    """
    doc = build_document_structure(doc_id, units)
    ref_within_sorted = sorted(masses_to_boundaries(doc.ref_masses) - doc.turn_boundaries)
    file_max = file_max_legitimate_run(doc_id, units, core=core, margin=margin)

    records = []
    for r in condition_analysis["all_window_runs"]:
        ref_in_span = ref_boundaries_in_span(ref_within_sorted, r["span_start"], r["span_end"])
        old_verdict = review_policy(r["run_length"])
        new_verdict = per_file_review_policy(r["run_length"], ref_in_span, file_max)
        records.append(
            {
                "sample": r["sample"],
                "window": r["window"],
                "run_length": r["run_length"],
                "span_start": r["span_start"],
                "span_end": r["span_end"],
                "ref_boundaries_in_span": ref_in_span,
                "file_max_legitimate_run": file_max,
                "old_auto_flagged": old_verdict["flagged_degenerate"],
                "old_needs_manual_review": old_verdict["needs_manual_review"],
                "new_degenerate": new_verdict["degenerate"],
            }
        )
    return records


def collapse_metrics(records: list[dict], total_window_draws: int, n_samples: int, n_tokens: int) -> dict:
    """collapse_rate and share_words_in_runs under the NEW rule, from
    classify_window_runs's own output -- total_window_draws is the
    file+condition's total attempted window-draws (successes and
    failures both count in the denominator, matching how the parse-
    failure rate is already reported); n_samples * n_tokens is every
    word actually scored across all samples (each sample scores the
    whole document's core words exactly once, since the windows tile).
    """
    degenerate = [r for r in records if r["new_degenerate"]]
    scored_words = n_samples * n_tokens
    words_in_runs = sum(r["run_length"] for r in degenerate)
    return {
        "n_degenerate_draws": len(degenerate),
        "total_window_draws": total_window_draws,
        "collapse_rate": len(degenerate) / total_window_draws if total_window_draws else float("nan"),
        "words_in_runs": words_in_runs,
        "scored_words": scored_words,
        "share_words_in_runs": words_in_runs / scored_words if scored_words else float("nan"),
    }

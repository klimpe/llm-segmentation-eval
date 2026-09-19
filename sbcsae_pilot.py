"""Phase 2: the SBCSAE LLM segmentation pilot -- one document (SBC039),
8 windows x condition {A, B} x n_samples=5, zero-shot. Calls the model.

Same model and call settings as phase 1 (llm_segmenter.py, recorded in
reports/phase2_llm_design.md S7): model=claude-sonnet-5, max_tokens=8192,
thinking disabled, no temperature/top_p/top_k (unsupported by this SDK).

Per window, per sample: the model sees that window's rendered text (see
sbcsae_llm.render_window/build_prompt) and returns a JSON array of
1-indexed within-turn unit-start positions (turn-initial positions are
never asked for -- see sbcsae_scoring.py). Response handling:

  - Raw output persisted to disk before parsing, one file per (condition,
    window, sample) -- llm_output_sbcsae/ (gitignored: real transcript-
    derived content, per the licence's no-corpus-data-in-git rule).
  - Cached and reused; a cached response that fails to parse/validate is
    retried once with a fresh call (same policy as llm_segmenter.py).
  - A turn-initial index in the response is dropped, not treated as an
    error -- counted per sample (the model was told not to report these,
    so this is a compliance count, not a fatal problem).
  - An index outside the window shown to the model IS a parse failure
    (the model invented a position it was never shown).
  - A window's raw prediction is only degenerate-checked (and, if all
    windows in a sample succeeded, assembled into a file-level
    hypothesis) using its CORE range -- margin predictions are discarded,
    since the neighbouring window's own core covers that span.

Degenerate output: sbcsae_degenerate_threshold.review_policy applied to
each window's own within-turn-core run length (MAX_LEGITIMATE_RUN=11,
DEGENERATE_FLAG_THRESHOLD=22).

Scoring: sbcsae_scoring.score_document, unchanged, both at whole-file
scope (all 8 windows' core predictions assembled, only when every window
in that sample parsed) and at each window's own local scope (that
window's core only, reindexed -- lets scores be compared by window
position without needing the whole sample to be complete).
"""
from __future__ import annotations

import bisect
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from llm_segmenter import call_model, parse_boundary_indices
from masses import boundaries_to_masses, masses_to_boundaries
from sbcsae_degenerate_threshold import max_consecutive_run_with_span, review_policy
from sbcsae_llm import build_document_structure, build_prompt, render_window
from sbcsae_reader import CORPUS_DIR, read_trn_document
from sbcsae_scoring import score_document
from sbcsae_tokenizer import Condition
from sbcsae_windows import (
    CORE,
    MARGIN,
    ScoreRegion,
    assert_boundaries_each_in_one_region,
    assert_regions_tile,
    build_score_regions,
)

DOC_ID = "SBC039"
MODEL = "claude-sonnet-5"  # llm_segmenter.DEFAULT_MODEL, same as phase 1
N_SAMPLES = 5
OUTPUT_DIR = Path("llm_output_sbcsae")


@dataclass
class WindowDraw:
    status: str  # "ok" or "fail"
    kept: list[int] = field(default_factory=list)  # within-turn, in-range indices
    dropped_turn_initial: list[int] = field(default_factory=list)
    reason: str = ""
    used_cache: bool = False


def _cache_path(
    doc_id: str, condition: Condition, window_idx: int, sample_idx: int, output_dir: Path = OUTPUT_DIR
) -> Path:
    return output_dir / f"{doc_id}_{condition.value}_w{window_idx}_sample{sample_idx}.txt"


def _parse_window_response(raw_output: str, region: ScoreRegion, turn_boundaries: set[int]) -> tuple[list[int], list[int]]:
    """Returns (kept, dropped_turn_initial). Raises ValueError on
    malformed JSON/non-integers (ordinary parse failure) or on any index
    outside [window_start, window_end] (the model invented a position it
    was never shown -- also a parse failure, per the brief).
    """
    indices = parse_boundary_indices(raw_output)
    dropped = [i for i in indices if (i - 1) in turn_boundaries]
    kept = [i for i in indices if (i - 1) not in turn_boundaries]
    out_of_range = [i for i in kept if not (region.window_start <= i <= region.window_end)]
    if out_of_range:
        raise ValueError(f"indices outside window [{region.window_start},{region.window_end}]: {out_of_range}")
    return kept, dropped


MAX_FRESH_ATTEMPTS = 2  # CLAUDE.md "Sampling": retry on parse failure, don't just give up on attempt 1


def _draw_one_window(
    doc_id: str,
    condition: Condition,
    window_idx: int,
    sample_idx: int,
    prompt: str,
    region: ScoreRegion,
    turn_boundaries: set[int],
    output_dir: Path = OUTPUT_DIR,
) -> WindowDraw:
    path = _cache_path(doc_id, condition, window_idx, sample_idx, output_dir)
    if path.exists():
        cached = path.read_text(encoding="utf-8")
        try:
            kept, dropped = _parse_window_response(cached, region, turn_boundaries)
            return WindowDraw(status="ok", kept=kept, dropped_turn_initial=dropped, used_cache=True)
        except ValueError:
            pass  # unusable cache; fall through to a fresh call, same policy as llm_segmenter.segment_document

    # A fresh call that fails to parse is retried (fresh call again, same
    # cache path -- the new raw output overwrites the unusable one) up to
    # MAX_FRESH_ATTEMPTS times before this draw is given up on and
    # counted as failed. This is what CLAUDE.md's "Sampling" section
    # means by "retry on failure" -- occasional parse failures (~5% per
    # that section) should not disappear a draw on the first bad
    # response.
    reason = ""
    for _ in range(MAX_FRESH_ATTEMPTS):
        raw = call_model(prompt, model=MODEL)
        path.write_text(raw, encoding="utf-8")
        try:
            kept, dropped = _parse_window_response(raw, region, turn_boundaries)
            return WindowDraw(status="ok", kept=kept, dropped_turn_initial=dropped)
        except ValueError as e:
            reason = str(e)
    return WindowDraw(status="fail", reason=reason)


def _core_only(indices: list[int], region: ScoreRegion) -> list[int]:
    return [i for i in indices if region.score_start <= i <= region.score_end]


def _nearest_signed_offset(p: int, sorted_ref: list[int]) -> int | None:
    """Signed distance from hypothesis boundary p to the nearest reference
    boundary in sorted_ref (both in "after token p" space): positive means
    p sits after the nearest reference boundary, negative means before.
    None if sorted_ref is empty (no reference boundary to measure against
    -- cannot happen for a real window with any within-turn reference
    boundaries, but a degenerate/tiny synthetic case could hit it).
    """
    if not sorted_ref:
        return None
    idx = bisect.bisect_left(sorted_ref, p)
    candidates = []
    if idx < len(sorted_ref):
        candidates.append(sorted_ref[idx])
    if idx > 0:
        candidates.append(sorted_ref[idx - 1])
    nearest = min(candidates, key=lambda r: abs(p - r))
    return p - nearest


POSITION_BUCKET_SIZE = 200


def _position_bucket(local_p: int) -> int:
    """Which third of the window core local_p (a local, 1-indexed word
    position) falls in, in fixed 200-word chunks (0: 1-200, 1: 201-400,
    2: 401-600) -- literal word-count chunks, not window_size/3, so a
    shorter final window's words all land in bucket 0 rather than being
    rescaled.
    """
    return (local_p - 1) // POSITION_BUCKET_SIZE


def _local_region_inputs(doc, region: ScoreRegion):
    """Reindex the reference (masses + turn boundaries) to the window's
    own local position space [1, local_n], local_n = the core's own word
    count -- lets score_document be reused unchanged at window scope,
    exactly as at whole-document scope (see sbcsae_scoring.py).

    Only STRICTLY INTERIOR boundaries (global position in [lo, hi-1])
    are representable locally: a global boundary at lo-1 sits between the
    word just before this window and this window's own first word --
    there is no "word before local word 1" in a local space that only
    covers [lo, hi], so it is excluded here, not reindexed to 0 (which
    boundaries_to_masses correctly rejects as out of range). This is
    deliberately narrower than sbcsae_windows.region_for_boundary's own
    OWNERSHIP convention ([lo-1, hi-1], used for corpus-wide attribution
    in sbcsae_degenerate_threshold.py) -- ownership and local
    representability are different questions.
    """
    lo, hi = region.score_start, region.score_end
    local_n = hi - lo + 1
    ref_boundaries = masses_to_boundaries(doc.ref_masses)
    local_ref_boundaries = {p - (lo - 1) for p in ref_boundaries if lo <= p <= hi - 1}
    local_ref_masses = boundaries_to_masses(local_ref_boundaries, local_n)
    local_turn_boundaries = {p - (lo - 1) for p in doc.turn_boundaries if lo <= p <= hi - 1}
    return local_ref_masses, local_turn_boundaries, lo


def run_pilot(
    doc_id: str = DOC_ID,
    n_samples: int = N_SAMPLES,
    conditions: tuple[Condition, ...] = (Condition.A, Condition.B),
    output_dir: Path = OUTPUT_DIR,
    core: int = CORE,
    margin: int = MARGIN,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = CORPUS_DIR / f"{doc_id}.trn"
    real_doc_id, units, *_ = read_trn_document(path)
    doc = build_document_structure(real_doc_id, units)

    regions = build_score_regions(doc.n_tokens, core=core, margin=margin)
    assert_regions_tile(regions, doc.n_tokens)
    assert_boundaries_each_in_one_region(regions, masses_to_boundaries(doc.ref_masses), doc.n_tokens)

    # draws[condition][sample_idx][window_idx] = WindowDraw
    draws: dict = {c: [[None] * len(regions) for _ in range(n_samples)] for c in conditions}

    for condition in conditions:
        for window_idx, region in enumerate(regions):
            window_text = render_window(doc, region.window_start, region.window_end, condition)
            prompt = build_prompt(window_text, condition)
            for sample_idx in range(n_samples):
                draws[condition][sample_idx][window_idx] = _draw_one_window(
                    doc_id, condition, window_idx, sample_idx, prompt, region, doc.turn_boundaries, output_dir
                )

    return {"doc": doc, "regions": regions, "draws": draws, "n_samples": n_samples, "units": units}


def _reference_segments_with_raw(units) -> list[tuple[int, int, str, str]]:
    """Parallel to sbcsae_llm.build_document_structure's zero-word-drop
    loop, but also keeps each kept segment's raw (pre-tokenisation) IU
    text and global word-start position -- needed for a covariate
    (overlap-bracket density) that only exists in text the tokeniser has
    already stripped by the time DocumentStructure is built. Returns
    (word_start, n_words, speaker, raw_text) per non-zero-word IU, in the
    same order/positions build_document_structure would assign.
    """
    from sbcsae_tokenizer import tokenize, words_only

    segments = []
    running_index = 0
    for u in units:
        words = words_only(tokenize(u.text))
        if not words:
            continue
        segments.append((running_index + 1, len(words), u.speaker, u.text))
        running_index += len(words)
    return segments


def compute_window_reference_stats(doc, units, regions: list[ScoreRegion]) -> list[dict]:
    """Per-window (score-core) reference covariates, condition-independent
    (computed once from the reference alone, not from any draw): the
    within-turn mean segment length (segments merged across a turn
    boundary, i.e. the same "effective segment length" the within_turn
    scoring mode itself operates over -- see sbcsae_scoring's
    NON_COMPARABILITY_NOTE), the number of speaker changes, and the
    overlap-bracket density per 100 words (raw '[' count, same convention
    as sbcsae_per_file_stats.py, attributed to whichever window a segment
    STARTS in).
    """
    segments = _reference_segments_with_raw(units)
    stats = []
    for region in regions:
        local_ref_masses, local_turn_boundaries, lo = _local_region_inputs(doc, region)
        local_n = sum(local_ref_masses)
        local_ref_boundaries = masses_to_boundaries(local_ref_masses)
        within_turn_boundaries_local = local_ref_boundaries - local_turn_boundaries
        merged_masses = boundaries_to_masses(within_turn_boundaries_local, local_n) if local_n else []
        mean_len = mean(merged_masses) if merged_masses else float("nan")

        in_region = [
            (start, n_words, raw)
            for start, n_words, speaker, raw in segments
            if region.score_start <= start <= region.score_end
        ]
        n_brackets = sum(raw.count("[") for _, _, raw in in_region)
        n_words_in_region = region.score_end - region.score_start + 1

        stats.append(
            {
                "mean_within_turn_segment_length": mean_len,
                "n_speaker_changes": len(local_turn_boundaries),
                "overlap_bracket_density_per_100_words": (
                    n_brackets / n_words_in_region * 100 if n_words_in_region else 0.0
                ),
            }
        )
    return stats


def analyse(pilot: dict) -> dict:
    doc = pilot["doc"]
    regions = pilot["regions"]
    draws = pilot["draws"]
    n_samples = pilot["n_samples"]

    result = {
        "doc_id": doc.doc_id,
        "n_tokens": doc.n_tokens,
        "n_windows": len(regions),
        "n_samples": n_samples,
        "regions": [(r.score_start, r.score_end) for r in regions],
    }
    if "units" in pilot:
        result["window_reference_stats"] = compute_window_reference_stats(doc, pilot["units"], regions)

    for condition in draws:
        cond_key = condition.value
        cdraws = draws[condition]

        # -- failure rate (window-level, matches phase 1's "N of M attempted samples") --
        total_window_draws = n_samples * len(regions)
        failed = [
            (s, w, cdraws[s][w].reason)
            for s in range(n_samples)
            for w in range(len(regions))
            if cdraws[s][w].status == "fail"
        ]

        # -- turn-initial drops, per sample --
        dropped_per_sample = [
            sum(len(cdraws[s][w].dropped_turn_initial) for w in range(len(regions)))
            for s in range(n_samples)
        ]

        # -- degenerate output, per window draw that succeeded --
        degenerate_flags = []  # (sample, window, run_length, flagged, needs_review)
        # Every successful draw's own run+span, regardless of whether it
        # clears review_policy's whole-corpus-calibrated thresholds --
        # additive only: degenerate_flags/auto_flagged_* below are
        # unchanged in shape or content for any existing caller. This
        # lets a caller with file-specific reference data (e.g.
        # sbcsae_degenerate_threshold.per_file_review_policy, reports/
        # phase2_llm_design.md's per-file degeneracy rule) re-derive its
        # own flags from real per-window span data without recomputing
        # runs from raw cache itself.
        all_window_runs = []  # (sample, window, run_length, span_start, span_end)
        for s in range(n_samples):
            for w, region in enumerate(regions):
                d = cdraws[s][w]
                if d.status != "ok":
                    continue
                core = sorted(i - 1 for i in _core_only(d.kept, region))
                run, span = max_consecutive_run_with_span(core)
                if run > 0:
                    span_start, span_end = span
                    all_window_runs.append(
                        {"sample": s, "window": w, "run_length": run, "span_start": span_start, "span_end": span_end}
                    )
                    policy = review_policy(run)
                    if policy["needs_manual_review"]:
                        degenerate_flags.append(
                            {"sample": s, "window": w, "run_length": run, **policy}
                        )

        # Auto-flagged (run > DEGENERATE_FLAG_THRESHOLD) draws are pulled
        # out of every aggregate below and reported in their own row
        # instead (CLAUDE.md, "Degenerate output": "Flag it automatically.
        # Report affected draws separately rather than folding them into
        # the aggregate."). needs_manual_review-only draws (11 < run <=
        # 22) stay in the aggregate -- that threshold exists to prompt a
        # human reading, not to change what gets averaged.
        auto_flagged_samples = sorted({f["sample"] for f in degenerate_flags if f["flagged_degenerate"]})
        auto_flagged_window_pairs = {
            (f["sample"], f["window"]) for f in degenerate_flags if f["flagged_degenerate"]
        }

        # -- whole-file hypothesis + score, per sample (only if every window in that sample parsed) --
        whole_file_scores = []  # list of score_document results, tagged with "sample"
        flagged_whole_file_scores = []  # same, for auto-flagged samples -- excluded from the above
        incomplete_samples = []
        for s in range(n_samples):
            if any(cdraws[s][w].status != "ok" for w in range(len(regions))):
                incomplete_samples.append(s)
                continue
            hyp_indices = []
            for w, region in enumerate(regions):
                hyp_indices.extend(_core_only(cdraws[s][w].kept, region))
            scores = score_document(doc.ref_masses, doc.turn_boundaries, hyp_indices)
            hyp_masses = boundaries_to_masses(
                doc.turn_boundaries | {i - 1 for i in hyp_indices}, doc.n_tokens
            )
            assert sum(hyp_masses) == sum(doc.ref_masses)
            scores["sample"] = s
            (flagged_whole_file_scores if s in auto_flagged_samples else whole_file_scores).append(scores)

        # -- per-window score, per sample (window-local scope; independent of other windows) --
        per_window_scores = defaultdict(list)  # window_idx -> list of score_document results, tagged with "sample"
        flagged_per_window_scores = defaultdict(list)  # same, for auto-flagged (sample, window) pairs
        # -- offset distribution, pooled across all non-flagged, successful draws --
        ref_within_sorted = sorted(masses_to_boundaries(doc.ref_masses) - doc.turn_boundaries)
        offset_counts = Counter()
        n_offset_boundaries = 0
        # -- within-turn F1 by position inside the window core, pooled (micro-averaged) --
        position_bucket_counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
        for s in range(n_samples):
            for w, region in enumerate(regions):
                d = cdraws[s][w]
                if d.status != "ok":
                    continue
                local_ref_masses, local_turn_boundaries, lo = _local_region_inputs(doc, region)
                # i == lo (the window's own first core word) is a real,
                # scoreable boundary at WHOLE-FILE scope (see the
                # whole-file assembly above), but not representable
                # locally -- there is no "word before local word 1" in a
                # space that only covers [lo, hi] (see
                # _local_region_inputs' own docstring). Excluded here,
                # not an error: this is a scope limitation of window-local
                # scoring, not a bad prediction.
                local_hyp = [i - (lo - 1) for i in _core_only(d.kept, region) if i > lo]
                scores = score_document(local_ref_masses, local_turn_boundaries, local_hyp)
                scores["sample"] = s
                flagged = (s, w) in auto_flagged_window_pairs
                (flagged_per_window_scores if flagged else per_window_scores)[w].append(scores)
                if flagged:
                    continue

                for i in _core_only(d.kept, region):
                    p = i - 1
                    offset = _nearest_signed_offset(p, ref_within_sorted)
                    if offset is not None:
                        offset_counts[offset] += 1
                        n_offset_boundaries += 1

                # local_hyp holds local 1-indexed START positions (i), like
                # score_document's own hyp_within_turn_start_indices param
                # -- convert to boundary ("after token p") space with i-1,
                # the same conversion score_document does internally,
                # before comparing against local_ref_within/local_turn_
                # boundaries (both already in p-space).
                local_ref_within = masses_to_boundaries(local_ref_masses) - local_turn_boundaries
                local_hyp_within = {i - 1 for i in local_hyp}
                local_n = sum(local_ref_masses)
                buckets_present = {_position_bucket(p) for p in range(1, local_n + 1)}
                for b in buckets_present:
                    lo_b, hi_b = b * POSITION_BUCKET_SIZE + 1, min((b + 1) * POSITION_BUCKET_SIZE, local_n)
                    ref_b = {p for p in local_ref_within if lo_b <= p <= hi_b}
                    hyp_b = {p for p in local_hyp_within if lo_b <= p <= hi_b}
                    counts = position_bucket_counts[b]
                    counts["tp"] += len(ref_b & hyp_b)
                    counts["fp"] += len(hyp_b - ref_b)
                    counts["fn"] += len(ref_b - hyp_b)

        offset_distribution = {
            "counts": {k: offset_counts.get(k, 0) for k in range(-3, 4)},
            "n_beyond_range": sum(v for k, v in offset_counts.items() if abs(k) > 3),
            "n_total": n_offset_boundaries,
        }

        position_f1 = {}
        for b in sorted(position_bucket_counts):
            counts = position_bucket_counts[b]
            tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
            precision = tp / (tp + fp) if (tp + fp) else (1.0 if not fn else 0.0)
            recall = tp / (tp + fn) if (tp + fn) else (1.0 if not fp else 0.0)
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
            position_f1[b] = {
                "word_range": f"{b * POSITION_BUCKET_SIZE + 1}-{(b + 1) * POSITION_BUCKET_SIZE}",
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }

        result[cond_key] = {
            "total_window_draws": total_window_draws,
            "n_failed": len(failed),
            "failed": failed,
            "dropped_turn_initial_per_sample": dropped_per_sample,
            "degenerate_flags": degenerate_flags,
            "all_window_runs": all_window_runs,
            "auto_flagged_samples": auto_flagged_samples,
            "auto_flagged_window_pairs": sorted(auto_flagged_window_pairs),
            "whole_file_scores": whole_file_scores,
            "flagged_whole_file_scores": flagged_whole_file_scores,
            "incomplete_samples": incomplete_samples,
            "per_window_scores": dict(per_window_scores),
            "flagged_per_window_scores": dict(flagged_per_window_scores),
            "offset_distribution": offset_distribution,
            "position_f1": position_f1,
        }

    return result


def _mean_range(values: list[float]) -> tuple[float, float, float]:
    return (mean(values), min(values), max(values)) if values else (float("nan"), float("nan"), float("nan"))


def write_report(result: dict, path: Path = Path("reports/phase2_pilot.md")) -> None:
    doc_id = result["doc_id"]
    lines = []
    lines.append("# Phase 2 pilot: SBC039")
    lines.append("")
    lines.append(
        "Counts and scores only -- no transcript text. **The target throughout is "
        "intonation-unit (prosodic) segmentation, not discourse-unit segmentation** "
        "(CLAUDE.md's phase 2 framing): SBCSAE has no discourse annotation, only IUs."
    )
    lines.append("")
    lines.append(
        f"One file ({doc_id}) x 8 windows x condition {{A, B}} x n_samples={result['n_samples']}, "
        f"zero-shot. Model and settings: see reports/phase2_llm_design.md S7 (same as phase 1)."
    )
    lines.append("")
    lines.append(
        "**This is a single-document pilot. One file supports no conclusion about A vs "
        "B, or about this model's segmentation ability in general** -- it validates the "
        "pipeline (rendering, scoring, windowing, degenerate detection) end to end on "
        "real model output before any scaling decision."
    )
    lines.append("")
    lines.append(f"n_tokens: {result['n_tokens']}, n_windows: {result['n_windows']}")
    lines.append("")

    for cond_key in ("A", "B"):
        c = result[cond_key]
        lines.append(f"## Condition {cond_key}")
        lines.append("")
        lines.append(
            f"- Window-level draws: {c['total_window_draws']}, failed to parse/align: "
            f"{c['n_failed']} ({c['n_failed'] / c['total_window_draws']:.1%})"
        )
        if c["failed"]:
            lines.append("  - Failures (sample, window, reason):")
            for s, w, reason in c["failed"]:
                lines.append(f"    - sample {s}, window {w}: {reason}")
        lines.append(f"- Turn-initial indices dropped, per sample: {c['dropped_turn_initial_per_sample']}")
        lines.append(
            f"- Samples with an incomplete whole-file hypothesis (>=1 window failed): "
            f"{len(c['incomplete_samples'])} of {result['n_samples']} "
            f"(samples {c['incomplete_samples']})"
            if c["incomplete_samples"]
            else "- All samples produced a complete whole-file hypothesis."
        )
        lines.append("")

        lines.append(
            "### Degenerate-output flags (runs of consecutive predicted intonation-unit, "
            "not discourse-unit, boundaries; run > 11; per "
            "sbcsae_degenerate_threshold.review_policy)"
        )
        lines.append("")
        if c["degenerate_flags"]:
            lines.append("| sample | window | run length | auto-flagged (>22) | needs manual reading |")
            lines.append("|---|---|---|---|---|")
            for f in c["degenerate_flags"]:
                lines.append(
                    f"| {f['sample']} | {f['window']} | {f['run_length']} | "
                    f"{f['flagged_degenerate']} | {f['needs_manual_review']} |"
                )
        else:
            lines.append("None.")
        lines.append("")

        lines.append(
            "### Whole-file scores per sample (intonation units, not discourse units; "
            "within-turn is the headline; precision/recall/boundary-count ratio/Boundary "
            "Similarity from the same unchanged metrics.py functions score_document "
            "already called)"
        )
        lines.append("")
        if c["whole_file_scores"]:
            lines.append(
                "| sample | scope | precision | recall | F1 | hyp/ref boundary ratio | "
                "Boundary Similarity | WindowDiff |"
            )
            lines.append("|---|---|---|---|---|---|---|---|")
            for sc in c["whole_file_scores"]:
                for scope, label in (("all_boundaries", "all_boundaries"), ("within_turn", "**within_turn**")):
                    m = sc[scope]
                    lines.append(
                        f"| {sc['sample']} | {label} | {m['precision']:.4f} | {m['recall']:.4f} | "
                        f"{m['f1']:.4f} | {m['boundary_count_ratio']:.4f} | "
                        f"{m['boundary_similarity']:.4f} | {m['window_diff']:.4f} |"
                    )
            lines.append("")
            for scope, label in (("all_boundaries", "all_boundaries"), ("within_turn", "within_turn (headline)")):
                for metric in ("precision", "recall", "f1", "boundary_count_ratio", "boundary_similarity"):
                    vals = [sc[scope][metric] for sc in c["whole_file_scores"]]
                    m_, lo_, hi_ = _mean_range(vals)
                    lines.append(f"- {label} {metric}: mean {m_:.4f}, range [{lo_:.4f}, {hi_:.4f}] (n={len(vals)})")
            lines.append(
                "- all_boundaries and within_turn are not comparable to each other "
                "(different effective segment lengths -- sbcsae_scoring.NON_COMPARABILITY_NOTE)."
            )
        else:
            lines.append("No sample produced a complete whole-file hypothesis (every sample had >=1 failed window).")
        lines.append("")

        lines.append(
            "### Auto-flagged draws (run > 22): excluded from every aggregate above, "
            "reported on their own (CLAUDE.md, \"Degenerate output\": report affected "
            "draws separately rather than folding them into the aggregate)"
        )
        lines.append("")
        if c["flagged_whole_file_scores"]:
            lines.append("| sample | scope | precision | recall | F1 | hyp/ref boundary ratio | Boundary Similarity |")
            lines.append("|---|---|---|---|---|---|---|")
            for sc in c["flagged_whole_file_scores"]:
                for scope, label in (("all_boundaries", "all_boundaries"), ("within_turn", "**within_turn**")):
                    m = sc[scope]
                    lines.append(
                        f"| {sc['sample']} | {label} | {m['precision']:.4f} | {m['recall']:.4f} | "
                        f"{m['f1']:.4f} | {m['boundary_count_ratio']:.4f} | {m['boundary_similarity']:.4f} |"
                    )
        else:
            lines.append("No sample had an auto-flagged (run > 22) window this condition.")
        lines.append("")

        lines.append(
            "### Offset distribution, within-turn boundaries (signed distance from each "
            "hypothesis boundary to the nearest reference boundary; pooled over all "
            "non-flagged, successful window draws; 0 = exact match)"
        )
        lines.append("")
        od = c["offset_distribution"]
        lines.append("| offset | -3 | -2 | -1 | 0 | +1 | +2 | +3 | beyond +-3 | total |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        counts = od["counts"]
        lines.append(
            "| n | " + " | ".join(str(counts[k]) for k in range(-3, 4))
            + f" | {od['n_beyond_range']} | {od['n_total']} |"
        )
        lines.append("")

        lines.append(
            "### Per-window scores by window position (intonation units, not discourse "
            "units; mean over samples where that window's own draw succeeded and was not "
            "auto-flagged -- window scope only, independent of whether other windows in "
            "the same sample failed). Reference covariates (mean within-turn segment "
            "length, speaker changes, overlap-bracket density) are condition-independent "
            "properties of this window's own reference, shown alongside the scores they "
            "plausibly explain -- not a claim that score changes by window position are a "
            "drift or trend over the document, since windows are scored independently and "
            "differ in reference difficulty, not in position per se."
        )
        lines.append("")
        lines.append(
            "| window | score range (words) | ref mean seg length | speaker changes | "
            "overlap-bracket density /100w | n samples | within_turn F1 mean [range] | "
            "all_boundaries F1 mean [range] |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for w, (score_start, score_end) in enumerate(result["regions"]):
            ref_stats = result["window_reference_stats"][w]
            window_scores = c["per_window_scores"].get(w, [])
            ref_cols = (
                f"{ref_stats['mean_within_turn_segment_length']:.2f} | "
                f"{ref_stats['n_speaker_changes']} | "
                f"{ref_stats['overlap_bracket_density_per_100_words']:.2f}"
            )
            if not window_scores:
                lines.append(f"| {w} | {score_start}-{score_end} | {ref_cols} | 0 | n/a | n/a |")
                continue
            wt_f1s = [sc["within_turn"]["f1"] for sc in window_scores]
            ab_f1s = [sc["all_boundaries"]["f1"] for sc in window_scores]
            wt_m, wt_lo, wt_hi = _mean_range(wt_f1s)
            ab_m, ab_lo, ab_hi = _mean_range(ab_f1s)
            lines.append(
                f"| {w} | {score_start}-{score_end} | {ref_cols} | {len(window_scores)} | "
                f"{wt_m:.4f} [{wt_lo:.4f}, {wt_hi:.4f}] | {ab_m:.4f} [{ab_lo:.4f}, {ab_hi:.4f}] |"
            )
        lines.append("")

        lines.append(
            "### Within-turn F1 by position inside the window core (pooled/micro-averaged "
            "tp/fp/fn over all non-flagged, successful window draws and all samples -- not "
            "a mean of per-window F1s)"
        )
        lines.append("")
        lines.append("| word range in core | precision | recall | F1 | tp | fp | fn |")
        lines.append("|---|---|---|---|---|---|---|")
        for b in sorted(c["position_f1"]):
            pf = c["position_f1"][b]
            lines.append(
                f"| {pf['word_range']} | {pf['precision']:.4f} | {pf['recall']:.4f} | "
                f"{pf['f1']:.4f} | {pf['tp']} | {pf['fp']} | {pf['fn']} |"
            )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    pilot = run_pilot()
    result = analyse(pilot)
    write_report(result)
    print(json.dumps({k: v for k, v in result.items() if k in ("doc_id", "n_tokens", "n_windows")}, indent=2))

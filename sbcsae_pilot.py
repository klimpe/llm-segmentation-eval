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

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from llm_segmenter import call_model, parse_boundary_indices
from masses import boundaries_to_masses, masses_to_boundaries
from sbcsae_degenerate_threshold import max_consecutive_run, review_policy
from sbcsae_llm import build_document_structure, build_prompt, render_window
from sbcsae_reader import CORPUS_DIR, read_trn_document
from sbcsae_scoring import score_document
from sbcsae_tokenizer import Condition
from sbcsae_windows import ScoreRegion, assert_boundaries_each_in_one_region, assert_regions_tile, build_score_regions

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


def _cache_path(doc_id: str, condition: Condition, window_idx: int, sample_idx: int) -> Path:
    return OUTPUT_DIR / f"{doc_id}_{condition.value}_w{window_idx}_sample{sample_idx}.txt"


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


def _draw_one_window(
    doc_id: str,
    condition: Condition,
    window_idx: int,
    sample_idx: int,
    prompt: str,
    region: ScoreRegion,
    turn_boundaries: set[int],
) -> WindowDraw:
    path = _cache_path(doc_id, condition, window_idx, sample_idx)
    if path.exists():
        cached = path.read_text(encoding="utf-8")
        try:
            kept, dropped = _parse_window_response(cached, region, turn_boundaries)
            return WindowDraw(status="ok", kept=kept, dropped_turn_initial=dropped, used_cache=True)
        except ValueError:
            pass  # unusable cache; fall through to a fresh call, same policy as llm_segmenter.segment_document

    raw = call_model(prompt, model=MODEL)
    path.write_text(raw, encoding="utf-8")
    try:
        kept, dropped = _parse_window_response(raw, region, turn_boundaries)
        return WindowDraw(status="ok", kept=kept, dropped_turn_initial=dropped)
    except ValueError as e:
        return WindowDraw(status="fail", reason=str(e))


def _core_only(indices: list[int], region: ScoreRegion) -> list[int]:
    return [i for i in indices if region.score_start <= i <= region.score_end]


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


def run_pilot(doc_id: str = DOC_ID, n_samples: int = N_SAMPLES) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = CORPUS_DIR / f"{doc_id}.trn"
    real_doc_id, units, *_ = read_trn_document(path)
    doc = build_document_structure(real_doc_id, units)

    regions = build_score_regions(doc.n_tokens)
    assert_regions_tile(regions, doc.n_tokens)
    assert_boundaries_each_in_one_region(regions, masses_to_boundaries(doc.ref_masses), doc.n_tokens)

    # draws[condition][sample_idx][window_idx] = WindowDraw
    draws: dict = {c: [[None] * len(regions) for _ in range(n_samples)] for c in (Condition.A, Condition.B)}

    for condition in (Condition.A, Condition.B):
        for window_idx, region in enumerate(regions):
            window_text = render_window(doc, region.window_start, region.window_end, condition)
            prompt = build_prompt(window_text, condition)
            for sample_idx in range(n_samples):
                draws[condition][sample_idx][window_idx] = _draw_one_window(
                    doc_id, condition, window_idx, sample_idx, prompt, region, doc.turn_boundaries
                )

    return {"doc": doc, "regions": regions, "draws": draws, "n_samples": n_samples}


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

    for condition in (Condition.A, Condition.B):
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
        for s in range(n_samples):
            for w, region in enumerate(regions):
                d = cdraws[s][w]
                if d.status != "ok":
                    continue
                core = sorted(i - 1 for i in _core_only(d.kept, region))
                run = max_consecutive_run(core)
                if run > 0:
                    policy = review_policy(run)
                    if policy["needs_manual_review"]:
                        degenerate_flags.append(
                            {"sample": s, "window": w, "run_length": run, **policy}
                        )

        # -- whole-file hypothesis + score, per sample (only if every window in that sample parsed) --
        whole_file_scores = []  # list of score_document results
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
            whole_file_scores.append(scores)

        # -- per-window score, per sample (window-local scope; independent of other windows) --
        per_window_scores = defaultdict(list)  # window_idx -> list of score_document results
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
                per_window_scores[w].append(score_document(local_ref_masses, local_turn_boundaries, local_hyp))

        result[cond_key] = {
            "total_window_draws": total_window_draws,
            "n_failed": len(failed),
            "failed": failed,
            "dropped_turn_initial_per_sample": dropped_per_sample,
            "degenerate_flags": degenerate_flags,
            "whole_file_scores": whole_file_scores,
            "incomplete_samples": incomplete_samples,
            "per_window_scores": dict(per_window_scores),
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
            "within-turn is the headline)"
        )
        lines.append("")
        if c["whole_file_scores"]:
            lines.append("| sample | all_boundaries F1 | all_boundaries WD | within_turn F1 (headline) | within_turn WD |")
            lines.append("|---|---|---|---|---|")
            for i, sc in enumerate(c["whole_file_scores"]):
                ab, wt = sc["all_boundaries"], sc["within_turn"]
                lines.append(
                    f"| {i} | {ab['f1']:.4f} | {ab['window_diff']:.4f} | "
                    f"**{wt['f1']:.4f}** | {wt['window_diff']:.4f} |"
                )
            ab_f1s = [sc["all_boundaries"]["f1"] for sc in c["whole_file_scores"]]
            wt_f1s = [sc["within_turn"]["f1"] for sc in c["whole_file_scores"]]
            ab_m, ab_lo, ab_hi = _mean_range(ab_f1s)
            wt_m, wt_lo, wt_hi = _mean_range(wt_f1s)
            lines.append("")
            lines.append(f"- all_boundaries F1: mean {ab_m:.4f}, range [{ab_lo:.4f}, {ab_hi:.4f}] (n={len(ab_f1s)})")
            lines.append(f"- within_turn F1 (headline): mean {wt_m:.4f}, range [{wt_lo:.4f}, {wt_hi:.4f}] (n={len(wt_f1s)})")
            lines.append(
                "- all_boundaries and within_turn are not comparable to each other "
                "(different effective segment lengths -- sbcsae_scoring.NON_COMPARABILITY_NOTE)."
            )
        else:
            lines.append("No sample produced a complete whole-file hypothesis (every sample had >=1 failed window).")
        lines.append("")

        lines.append(
            "### Per-window within_turn F1 and all_boundaries F1, by window position "
            "(intonation units, not discourse units; mean over samples where that "
            "window's own draw succeeded -- window scope only, independent of whether "
            "other windows in the same sample failed)"
        )
        lines.append("")
        lines.append(
            "| window | score range (words) | n samples | within_turn F1 mean [range] | "
            "all_boundaries F1 mean [range] |"
        )
        lines.append("|---|---|---|---|---|")
        for w, (score_start, score_end) in enumerate(result["regions"]):
            window_scores = c["per_window_scores"].get(w, [])
            if not window_scores:
                lines.append(f"| {w} | {score_start}-{score_end} | 0 | n/a | n/a |")
                continue
            wt_f1s = [sc["within_turn"]["f1"] for sc in window_scores]
            ab_f1s = [sc["all_boundaries"]["f1"] for sc in window_scores]
            wt_m, wt_lo, wt_hi = _mean_range(wt_f1s)
            ab_m, ab_lo, ab_hi = _mean_range(ab_f1s)
            lines.append(
                f"| {w} | {score_start}-{score_end} | {len(window_scores)} | "
                f"{wt_m:.4f} [{wt_lo:.4f}, {wt_hi:.4f}] | {ab_m:.4f} [{ab_lo:.4f}, {ab_hi:.4f}] |"
            )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    pilot = run_pilot()
    result = analyse(pilot)
    write_report(result)
    print(json.dumps({k: v for k, v in result.items() if k in ("doc_id", "n_tokens", "n_windows")}, indent=2))

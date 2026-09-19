"""Phase 2, batch 1: 10 files spanning the corpus's word-count deciles,
plus SBC039 (the pilot file -- run identically, reported separately,
since it already informed the prompt/threshold decisions the other 10
did not get a vote in).

Same model, settings, windows (800/600), conditions (A, B), n_samples=5
and clarified prompt as the pilot (reports/phase2_pilot.md,
reports/phase2_llm_design.md S7/S11). Target throughout is intonation-
unit (prosodic) segmentation, not discourse-unit segmentation.

Batch selection (`select_batch`) is a pure function of
reports/phase2_per_file_stats.csv's word counts -- no model output, no
score, no property of the pilot run enters it. It is computed and
reported (`format_selection_report`) BEFORE `run_batch` makes any model
call.

`run_batch` writes the four CSVs incrementally, one file's full set of
rows appended and flushed as soon as that file's run completes, not
buffered to the end. It stops immediately (no further model calls) if
any single file's own window-level parse/align failure rate (pooled
across both conditions, failed attempts counted in the denominator --
CLAUDE.md's "Sampling" section) exceeds MAX_PARSE_FAILURE_RATE.

`write_report` reads the four CSVs back from disk and computes every
number in reports/phase2_batch1.md from them -- nothing in the markdown
comes from an in-memory structure the CSVs don't also contain, so the
two cannot diverge.
"""
from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from sbcsae_baselines import RANDOM_SEED, per_file_baselines
from sbcsae_cue_adjacency import BUCKET_KEYS, base_rate_for_doc, per_sample_offset_rows
from sbcsae_degenerate_per_file import classify_window_runs, collapse_metrics
from sbcsae_pilot import N_SAMPLES, analyse, run_pilot
from sbcsae_reader import CORPUS_DIR, read_trn_document
from sbcsae_tokenizer import Condition

PER_FILE_STATS_CSV = Path("reports/phase2_per_file_stats.csv")
EXCLUDE_FILES = {"SBC037"}
PILOT_DOC_ID = "SBC039"
OUTPUT_DIR = Path("llm_output_sbcsae_batch1")
DECILE_TARGET_PERCENTILES = [5, 15, 25, 35, 45, 55, 65, 75, 85, 95]
MAX_PARSE_FAILURE_RATE = 0.10

SCORES_CSV = Path("reports/phase2_batch1_scores.csv")
OFFSETS_CSV = Path("reports/phase2_batch1_offsets.csv")
DEGENERATE_CSV = Path("reports/phase2_batch1_degenerate.csv")
BASELINES_CSV = Path("reports/phase2_batch1_baselines.csv")

SCOPES = ("within_turn", "all_boundaries")
METRICS = ("precision", "recall", "f1", "window_diff", "boundary_similarity")


# ---------------------------------------------------------------------
# 1. Batch selection -- pure function of word counts, no model call
# ---------------------------------------------------------------------


def _percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile (numpy's default 'linear' method),
    reimplemented directly to avoid adding numpy as a dependency for one
    function.
    """
    n = len(sorted_values)
    h = (p / 100) * (n - 1)
    lo = int(h)
    frac = h - lo
    if lo + 1 < n:
        return sorted_values[lo] + frac * (sorted_values[lo + 1] - sorted_values[lo])
    return sorted_values[lo]


def select_batch(stats_csv: Path = PER_FILE_STATS_CSV) -> list[dict]:
    """10 files, one per decile of the 59-file (SBC037 excluded) word-count
    distribution: for each of the 10 decile-bin MIDPOINTS (5th, 15th, ...,
    95th percentile of word count, linear interpolation), the actual file
    whose word count is nearest that target -- ties broken by doc_id,
    a collision (the same nearest file for two targets) resolved by
    falling through to the next-nearest not-yet-chosen file. Nothing
    about a file other than its word count enters the selection.

    SBC039 (the pilot file) is appended as an 11th, marked `is_pilot`,
    UNLESS it was already selected by the decile rule on its own merits,
    in which case the existing entry is marked `is_pilot` in place
    rather than adding a duplicate.

    Returns one dict per selected file, sorted by word count, each
    carrying the stats needed to report the selection before any model
    call: words, reference_segments, share_boundaries_at_speaker_change,
    overlap_bracket_density_per_100_words.
    """
    with open(stats_csv, newline="", encoding="utf-8") as f:
        all_rows = {r["file"]: r for r in csv.DictReader(f)}
    eligible = {doc_id: r for doc_id, r in all_rows.items() if doc_id not in EXCLUDE_FILES}
    sorted_pairs = sorted((int(r["words"]), doc_id) for doc_id, r in eligible.items())
    words_sorted = [w for w, _ in sorted_pairs]

    chosen_set: set[str] = set()
    selection_log = []
    for p in DECILE_TARGET_PERCENTILES:
        target = _percentile(words_sorted, p)
        for w, doc_id in sorted(sorted_pairs, key=lambda wf: (abs(wf[0] - target), wf[1])):
            if doc_id not in chosen_set:
                chosen_set.add(doc_id)
                selection_log.append({"decile_target_pct": p, "target_words": target, "doc_id": doc_id})
                break

    def _entry(doc_id: str, decile_target_pct, target_words, is_pilot: bool) -> dict:
        r = all_rows[doc_id]
        return {
            "doc_id": doc_id,
            "decile_target_pct": decile_target_pct,
            "target_words": target_words,
            "words": int(r["words"]),
            "reference_segments": int(r["reference_segments"]),
            "share_boundaries_at_speaker_change": float(r["share_boundaries_at_speaker_change"]),
            "overlap_bracket_density_per_100_words": float(r["overlap_bracket_density_per_100_words"]),
            "is_pilot": is_pilot,
        }

    batch = [
        _entry(e["doc_id"], e["decile_target_pct"], e["target_words"], e["doc_id"] == PILOT_DOC_ID)
        for e in selection_log
    ]
    batch.sort(key=lambda b: b["words"])

    if PILOT_DOC_ID not in chosen_set:
        batch.append(_entry(PILOT_DOC_ID, None, None, True))

    return batch


def format_selection_report(batch: list[dict]) -> str:
    lines = [
        "Batch 1 selection: one file per word-count decile of the 59-file "
        "corpus (SBC037 excluded), decile targets at the 5th/15th/.../95th "
        "percentile, nearest file by word count -- no score, pilot result, "
        "or any other property entered this choice.",
        "",
        f"{'doc_id':>8} {'decile%':>8} {'target_words':>13} {'words':>7} "
        f"{'ref_segments':>13} {'speaker_chg_share':>18} {'overlap/100w':>13} {'pilot':>6}",
    ]
    for b in batch:
        decile = f"{b['decile_target_pct']}" if b["decile_target_pct"] is not None else "n/a"
        target = f"{b['target_words']:.0f}" if b["target_words"] is not None else "n/a"
        lines.append(
            f"{b['doc_id']:>8} {decile:>8} {target:>13} {b['words']:>7} "
            f"{b['reference_segments']:>13} {b['share_boundaries_at_speaker_change']:>18.4f} "
            f"{b['overlap_bracket_density_per_100_words']:>13.2f} {str(b['is_pilot']):>6}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------
# 2. Running the batch -- the only part that calls the model
# ---------------------------------------------------------------------


@dataclass
class StopSignal:
    doc_id: str
    condition: str
    failure_rate: float
    n_failed: int
    total_window_draws: int


def _write_scores_rows(writer, doc_id: str, analysis: dict, collapse_stats: dict) -> None:
    for cond_key in ("A", "B"):
        c = analysis[cond_key]
        cs = collapse_stats[cond_key]
        for scores, flagged in [(s, False) for s in c["whole_file_scores"]] + [
            (s, True) for s in c["flagged_whole_file_scores"]
        ]:
            for scope in SCOPES:
                m = scores[scope]
                writer.writerow(
                    [
                        doc_id, cond_key, scores["sample"], scope,
                        f"{m['precision']:.4f}", f"{m['recall']:.4f}", f"{m['f1']:.4f}",
                        f"{m['window_diff']:.4f}", f"{m['boundary_similarity']:.4f}",
                        "" if m["boundary_count_ratio"] is None else f"{m['boundary_count_ratio']:.4f}",
                        m["n_ref_boundaries"], m["n_hyp_boundaries"], flagged,
                        # Per-file-rule collapse metrics (sbcsae_degenerate_per_file.py,
                        # reports/phase2_llm_design.md S14) -- a file+condition-level
                        # constant repeated on every one of that pair's rows, next to
                        # F1, since F1 alone barely moves when a collapse happens.
                        # total_window_draws is repeated the same way -- it lets the
                        # report's single aggregate old-vs-new-rule note (write_report)
                        # be computed from the CSVs alone, with no other source.
                        f"{cs['collapse_rate']:.4f}", f"{cs['share_words_in_runs']:.4f}",
                        cs["total_window_draws"],
                    ]
                )


def _write_offset_rows(writer, doc_id: str, n_samples: int, output_dir: Path) -> None:
    for condition in (Condition.A, Condition.B):
        for row in per_sample_offset_rows(doc_id, condition, n_samples, output_dir):
            writer.writerow(
                [row["doc_id"], row["condition"], row["sample"], row["offset"], row["count"], row["cue_after_named_word_count"]]
            )


def _write_degenerate_rows(writer, doc_id: str, units, analysis: dict) -> None:
    """One row per successful window-draw whose run is flagged by EITHER
    rule -- old needs-manual-review (run > 11) or auto-flagged (run > 22),
    or the new per-file rule (sbcsae_degenerate_per_file.py) -- carrying
    both verdicts side by side (reports/phase2_llm_design.md S14). A run
    only large enough to be uninteresting under both is not written; a
    trivial run of 1-3 on a file whose own legitimate max is 3-6 is not a
    finding, it is normal.
    """
    for cond_key in ("A", "B"):
        for r in classify_window_runs(doc_id, units, analysis[cond_key]):
            old_notable = r["run_length"] > 11  # sbcsae_degenerate_threshold.MAX_LEGITIMATE_RUN
            if not (old_notable or r["new_degenerate"]):
                continue
            writer.writerow(
                [
                    doc_id, cond_key, r["sample"], r["window"], r["run_length"],
                    r["ref_boundaries_in_span"], r["file_max_legitimate_run"],
                    r["old_auto_flagged"], r["new_degenerate"],
                ]
            )


def _write_baseline_rows(writer, doc_id: str, baselines: dict) -> None:
    cue = baselines["cue_rule"]
    for scope in SCOPES:
        m = cue[scope]
        writer.writerow(
            [doc_id, scope, "cue_rule", f"{m['precision']:.4f}", f"{m['recall']:.4f}", f"{m['f1']:.4f}",
             f"{m['window_diff']:.4f}", f"{m['boundary_similarity']:.4f}"]
        )
    rnd = baselines["random"]
    for scope in SCOPES:
        row = [doc_id, scope, "random"]
        for metric in METRICS:
            row.append(f"{rnd[scope][metric][0]:.4f}")  # mean of the (mean, lo, hi) tuple
        writer.writerow(row)


def run_batch(
    batch: list[dict],
    n_samples: int = N_SAMPLES,
    output_dir: Path = OUTPUT_DIR,
) -> StopSignal | None:
    """Runs every file in `batch` (conditions A and B, n_samples each),
    writing to the four CSVs as each file completes. Returns None if the
    whole batch ran to completion, or a StopSignal describing which file
    tripped the >10% parse-failure circuit breaker (in which case no
    further files are run).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(RANDOM_SEED)

    SCORES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORES_CSV, "w", newline="", encoding="utf-8") as f_scores, \
         open(OFFSETS_CSV, "w", newline="", encoding="utf-8") as f_offsets, \
         open(DEGENERATE_CSV, "w", newline="", encoding="utf-8") as f_degenerate, \
         open(BASELINES_CSV, "w", newline="", encoding="utf-8") as f_baselines:

        w_scores = csv.writer(f_scores)
        w_scores.writerow(
            ["doc_id", "condition", "sample", "scope", "precision", "recall", "f1", "window_diff",
             "boundary_similarity", "hyp_ref_ratio", "n_ref_boundaries", "n_hyp_boundaries", "flagged",
             "collapse_rate", "share_words_in_runs", "total_window_draws"]
        )
        w_offsets = csv.writer(f_offsets)
        w_offsets.writerow(["doc_id", "condition", "sample", "offset", "count", "cue_after_named_word_count"])
        w_degenerate = csv.writer(f_degenerate)
        w_degenerate.writerow(
            ["doc_id", "condition", "sample", "window", "run_length", "ref_boundaries_in_span",
             "file_max_legitimate_run", "old_auto_flagged", "new_degenerate"]
        )
        w_baselines = csv.writer(f_baselines)
        w_baselines.writerow(["doc_id", "scope", "baseline", "precision", "recall", "f1", "window_diff", "boundary_similarity"])
        for fh in (f_scores, f_offsets, f_degenerate, f_baselines):
            fh.flush()

        for entry in batch:
            doc_id = entry["doc_id"]
            label = "pilot" if entry["is_pilot"] else "batch"
            print(f"Running {doc_id} ({label}, {entry['words']} words)...")

            pilot = run_pilot(doc_id=doc_id, n_samples=n_samples, conditions=(Condition.A, Condition.B), output_dir=output_dir)
            analysis = analyse(pilot)

            total_window_draws = analysis["A"]["total_window_draws"] + analysis["B"]["total_window_draws"]
            n_failed = analysis["A"]["n_failed"] + analysis["B"]["n_failed"]
            failure_rate = n_failed / total_window_draws if total_window_draws else 0.0
            print(
                f"  window draws: {total_window_draws}, failed to parse/align "
                f"(after retry): {n_failed} ({failure_rate:.1%})"
            )
            if failure_rate > MAX_PARSE_FAILURE_RATE:
                print(
                    f"STOPPING: {doc_id} parse-failure rate {failure_rate:.1%} exceeds "
                    f"{MAX_PARSE_FAILURE_RATE:.0%} -- no further files will be run."
                )
                return StopSignal(doc_id, "A+B", failure_rate, n_failed, total_window_draws)

            path = CORPUS_DIR / f"{doc_id}.trn"
            _, units, *_ = read_trn_document(path)
            baselines = per_file_baselines(doc_id, units, rng)

            # Per-file-rule collapse metrics (sbcsae_degenerate_per_file.py,
            # reports/phase2_llm_design.md S14), one per condition.
            n_tokens = pilot["doc"].n_tokens
            collapse_stats = {
                cond_key: collapse_metrics(
                    classify_window_runs(doc_id, units, analysis[cond_key]),
                    analysis[cond_key]["total_window_draws"],
                    n_samples,
                    n_tokens,
                )
                for cond_key in ("A", "B")
            }

            _write_scores_rows(w_scores, doc_id, analysis, collapse_stats)
            _write_offset_rows(w_offsets, doc_id, n_samples, output_dir)
            _write_degenerate_rows(w_degenerate, doc_id, units, analysis)
            _write_baseline_rows(w_baselines, doc_id, baselines)
            for fh in (f_scores, f_offsets, f_degenerate, f_baselines):
                fh.flush()

    return None


# ---------------------------------------------------------------------
# 3. Reporting -- reads the four CSVs back from disk; nothing else
# ---------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _mean_range(values: list[float]) -> tuple[float, float, float]:
    return (mean(values), min(values), max(values)) if values else (float("nan"), float("nan"), float("nan"))


def write_report(batch: list[dict], path: Path = Path("reports/phase2_batch1.md")) -> None:
    scores = _read_csv(SCORES_CSV)
    offsets = _read_csv(OFFSETS_CSV)
    degenerate = _read_csv(DEGENERATE_CSV)
    baselines = _read_csv(BASELINES_CSV)

    doc_ids = [b["doc_id"] for b in batch]
    is_pilot = {b["doc_id"]: b["is_pilot"] for b in batch}

    lines = []
    lines.append("# Phase 2 batch 1: 10 files across the corpus's word-count deciles")
    lines.append("")
    lines.append(
        "Counts and scores only -- no transcript text. **The target throughout is "
        "intonation-unit (prosodic) segmentation, not discourse-unit segmentation** "
        "(CLAUDE.md's phase 2 framing): SBCSAE has no discourse annotation, only IUs."
    )
    lines.append("")
    lines.append(
        "10 files x 800/600 windows x condition {A, B} x n_samples=5, zero-shot, "
        "clarified prompt (reports/phase2_llm_design.md S11), same model and settings "
        "as the pilot. SBC039 is reported separately below: it already informed the "
        "prompt/threshold decisions the other 10 files did not, so it is not pooled "
        "into the batch's own aggregates."
    )
    lines.append("")
    lines.append(
        "Every figure below is read from reports/phase2_batch1_scores.csv, "
        "_offsets.csv, _degenerate.csv and _baselines.csv -- nothing here comes from "
        "an in-memory number those files don't also contain."
    )
    lines.append("")

    # -- Old-vs-new degeneracy rule, stated ONCE, in aggregate (reports/
    # phase2_llm_design.md S14 found the whole-corpus rule (run > 22)
    # undercounting collapse by roughly 6x on a partial batch; this is
    # the same comparison, recomputed over the completed 10-file batch).
    # Every per-file/per-condition section below still shows both rules'
    # verdict side by side on its own runs -- that is the underlying
    # data, not a repetition of this aggregate claim.
    batch_doc_ids_for_note = [b["doc_id"] for b in batch if not b["is_pilot"]]
    batch_scores_for_note = [r for r in scores if r["doc_id"] in batch_doc_ids_for_note]
    seen_file_cond = set()
    total_draws_note = 0
    for r in batch_scores_for_note:
        key = (r["doc_id"], r["condition"])
        if key not in seen_file_cond:
            seen_file_cond.add(key)
            total_draws_note += int(r["total_window_draws"])
    n_old_flagged = sum(
        1 for r in degenerate if r["doc_id"] in batch_doc_ids_for_note and r["old_auto_flagged"] == "True"
    )
    n_new_flagged = sum(
        1 for r in degenerate if r["doc_id"] in batch_doc_ids_for_note and r["new_degenerate"] == "True"
    )
    ratio = n_new_flagged / n_old_flagged if n_old_flagged else float("inf")
    lines.append(
        f"**Old rule (whole-corpus, run > 22) vs new rule (per-file, "
        f"reports/phase2_llm_design.md S14), over the full 10-file batch's "
        f"{total_draws_note} window-draws: {n_old_flagged} flagged by the old rule vs "
        f"{n_new_flagged} by the new one -- the old rule undercounts collapse by "
        f"roughly {ratio:.0f}x. Stated once, here; every table below reports "
        f"collapse_rate/share_words_in_runs under the new rule only, and cites the old "
        f"rule's own verdict per-draw only where relevant.**"
    )
    lines.append("")

    lines.append("## Batch selection")
    lines.append("")
    lines.append(
        "One file per decile of the 59-file (SBC037 excluded) word-count "
        "distribution -- decile targets at the 5th/15th/.../95th percentile "
        "(linear interpolation), nearest file by word count. No score, pilot "
        "result, or any other property entered this choice."
    )
    lines.append("")
    lines.append(
        "| doc_id | decile target | words | reference segments | speaker-change share | overlap/100w | pilot |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for b in batch:
        decile = f"{b['decile_target_pct']}%" if b["decile_target_pct"] is not None else "n/a (pilot)"
        lines.append(
            f"| {b['doc_id']} | {decile} | {b['words']} | {b['reference_segments']} | "
            f"{b['share_boundaries_at_speaker_change']:.4f} | {b['overlap_bracket_density_per_100_words']:.2f} | "
            f"{b['is_pilot']} |"
        )
    lines.append("")

    batch_doc_ids = [d for d in doc_ids if not is_pilot[d]]
    pilot_doc_ids = [d for d in doc_ids if is_pilot[d]]

    def _scores_for(doc_id, cond_key, scope, flagged_value="False"):
        return [
            r for r in scores
            if r["doc_id"] == doc_id and r["condition"] == cond_key and r["scope"] == scope and r["flagged"] == flagged_value
        ]

    def _per_file_metric_table(doc_id_list, section_title):
        lines.append(f"## {section_title}")
        lines.append("")
        for doc_id in doc_id_list:
            lines.append(f"### {doc_id}")
            lines.append("")
            for cond_key in ("A", "B"):
                lines.append(f"**Condition {cond_key}**")
                lines.append("")
                lines.append("| scope | metric | mean | range | n samples |")
                lines.append("|---|---|---|---|---|")
                for scope in SCOPES:
                    rows = _scores_for(doc_id, cond_key, scope)
                    for metric in METRICS:
                        vals = [float(r[metric]) for r in rows if r[metric] != ""]
                        m, lo, hi = _mean_range(vals)
                        label = "**within_turn**" if scope == "within_turn" else scope
                        lines.append(f"| {label} | {metric} | {m:.4f} | [{lo:.4f}, {hi:.4f}] | {len(vals)} |")
                    ratio_vals = [float(r["hyp_ref_ratio"]) for r in rows if r["hyp_ref_ratio"] != ""]
                    if ratio_vals:
                        m, lo, hi = _mean_range(ratio_vals)
                        label = "**within_turn**" if scope == "within_turn" else scope
                        lines.append(f"| {label} | hyp_ref_ratio | {m:.4f} | [{lo:.4f}, {hi:.4f}] | {len(ratio_vals)} |")
                lines.append("")
                # collapse_rate/share_words_in_runs (reports/phase2_llm_design.md
                # S14): a file+condition-level constant, repeated on every scores.csv
                # row for that pair -- pulled from any one of them here, next to F1.
                any_rows = [r for r in scores if r["doc_id"] == doc_id and r["condition"] == cond_key]
                if any_rows:
                    cr = float(any_rows[0]["collapse_rate"])
                    swr = float(any_rows[0]["share_words_in_runs"])
                    lines.append(
                        f"Collapse rate (share of window-draws with a per-file-rule degenerate "
                        f"run, reports/phase2_llm_design.md S14): {cr:.1%}. Share of scored words "
                        f"inside such runs: {swr:.2%}."
                    )
                    lines.append("")
                flagged_rows = [
                    r for r in scores
                    if r["doc_id"] == doc_id and r["condition"] == cond_key and r["flagged"] == "True"
                ]
                flagged_samples = sorted({r["sample"] for r in flagged_rows})
                if flagged_samples:
                    lines.append(
                        f"Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded "
                        f"from the aggregate above, reported on their own; the collapse rate "
                        f"just above uses the NEW per-file rule instead, S14, and is not what "
                        f"drives this exclusion): {flagged_samples}"
                    )
                    lines.append("")
                    lines.append("| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |")
                    lines.append("|---|---|---|---|---|---|---|")
                    for scope in SCOPES:
                        rows = _scores_for(doc_id, cond_key, scope, flagged_value="True")
                        for r in rows:
                            label = "**within_turn**" if scope == "within_turn" else scope
                            lines.append(
                                f"| {label} | {r['precision']} | {r['recall']} | {r['f1']} | "
                                f"{r['window_diff']} | {r['boundary_similarity']} | {r['hyp_ref_ratio']} |"
                            )
                    lines.append("")
                else:
                    lines.append("No auto-flagged (run > 22) draw this condition.")
                    lines.append("")

                deg_rows = [
                    r for r in degenerate
                    if r["doc_id"] == doc_id and r["condition"] == cond_key
                    and (r["old_auto_flagged"] == "True" or r["new_degenerate"] == "True")
                ]
                if deg_rows:
                    lines.append(
                        "Runs flagged by the old (whole-corpus, run > 22) or new "
                        "(per-file, reports/phase2_llm_design.md S14) rule, side by side "
                        "(rows where neither rule flagged the run are omitted):"
                    )
                    lines.append("")
                    lines.append(
                        "| sample | window | run length | ref boundaries in span | "
                        "file max legit. run | old rule (>22) | new per-file rule |"
                    )
                    lines.append("|---|---|---|---|---|---|---|")
                    for r in deg_rows:
                        lines.append(
                            f"| {r['sample']} | {r['window']} | {r['run_length']} | "
                            f"{r['ref_boundaries_in_span']} | {r['file_max_legitimate_run']} | "
                            f"{r['old_auto_flagged']} | {r['new_degenerate']} |"
                        )
                    lines.append("")

                offset_rows = [r for r in offsets if r["doc_id"] == doc_id and r["condition"] == cond_key]
                pooled = defaultdict(lambda: {"count": 0, "cue_after": 0})
                for r in offset_rows:
                    pooled[r["offset"]]["count"] += int(r["count"])
                    pooled[r["offset"]]["cue_after"] += int(r["cue_after_named_word_count"])
                lines.append(
                    "Offset distribution, within-turn boundaries (signed distance to nearest "
                    "reference boundary; 0 = exact match), and the share of each bucket's named "
                    "word immediately followed by a cue:"
                )
                lines.append("")
                if cond_key == "B":
                    hits, n, base_rate = base_rate_for_doc(doc_id)
                    lines.append(f"Base rate (cue immediately after a within-turn-eligible word): {hits}/{n} = {base_rate:.1%}")
                    lines.append("")
                header = "| offset | " + " | ".join(str(k) for k in BUCKET_KEYS) + " |"
                lines.append(header)
                lines.append("|---" * (len(BUCKET_KEYS) + 1) + "|")
                counts_row = [str(pooled[k]["count"]) for k in BUCKET_KEYS]
                lines.append("| n | " + " | ".join(counts_row) + " |")
                if cond_key == "B":
                    share_row = []
                    for k in BUCKET_KEYS:
                        c = pooled[k]["count"]
                        share_row.append(f"{pooled[k]['cue_after']/c:.1%}" if c else "n/a")
                    lines.append("| cue-after share | " + " | ".join(share_row) + " |")
                lines.append("")

            lines.append("")

    _per_file_metric_table(batch_doc_ids, "Per-file results (10-file batch)")
    _per_file_metric_table(pilot_doc_ids, "SBC039 (pilot file, reported separately)")

    lines.append("## A vs. B: per-file comparison, within-turn scope (batch files only, not the pilot)")
    lines.append("")
    lines.append(
        "Every metric below is a per-file mean over that file+condition's non-flagged "
        "samples (within-turn scope), plus collapse_rate under the new per-file rule "
        "(S14 above). This is a per-file table, not an aggregate: no cross-file mean, "
        "pooled score, or significance claim is made on 10 files -- CLAUDE.md's own "
        "standing caution applies. 'B beats A' on collapse_rate means B's rate is the "
        "LOWER of the two (fewer degenerate draws), the opposite direction from the "
        "other metrics where higher is better."
    )
    lines.append("")

    def _within_turn_mean(doc_id, cond_key, metric):
        vals = [float(r[metric]) for r in _scores_for(doc_id, cond_key, "within_turn") if r[metric] != ""]
        return mean(vals) if vals else float("nan")

    def _collapse_rate_for(doc_id, cond_key):
        any_rows = [r for r in scores if r["doc_id"] == doc_id and r["condition"] == cond_key]
        return float(any_rows[0]["collapse_rate"]) if any_rows else float("nan")

    comparison_metrics = ["precision", "recall", "f1", "window_diff", "boundary_similarity", "hyp_ref_ratio"]
    header_cells = ["doc_id"]
    for m in comparison_metrics:
        header_cells += [f"A {m}", f"B {m}"]
    header_cells += ["A collapse_rate", "B collapse_rate"]
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("|" + "---|" * len(header_cells))

    f1_diffs = []
    f1_b_wins = 0
    f1_comparable = 0
    f1_nan_files = []
    collapse_diffs = []
    collapse_b_wins = 0
    for doc_id in batch_doc_ids:
        row_cells = [doc_id]
        per_metric_vals = {}
        for m in comparison_metrics:
            a_v = _within_turn_mean(doc_id, "A", m)
            b_v = _within_turn_mean(doc_id, "B", m)
            per_metric_vals[m] = (a_v, b_v)
            row_cells += [f"{a_v:.4f}", f"{b_v:.4f}"]
        a_cr = _collapse_rate_for(doc_id, "A")
        b_cr = _collapse_rate_for(doc_id, "B")
        row_cells += [f"{a_cr:.4f}", f"{b_cr:.4f}"]
        lines.append("| " + " | ".join(row_cells) + " |")

        a_f1, b_f1 = per_metric_vals["f1"]
        if a_f1 != a_f1:  # nan check: this file+condition had 0 non-flagged samples
            f1_nan_files.append(doc_id)
        else:
            f1_comparable += 1
            f1_diff = b_f1 - a_f1
            f1_diffs.append((doc_id, f1_diff))
            if f1_diff > 0:
                f1_b_wins += 1
        collapse_diff = b_cr - a_cr  # negative means B collapses less -- a B win
        collapse_diffs.append((doc_id, collapse_diff))
        if collapse_diff < 0:
            collapse_b_wins += 1
    lines.append("")
    lines.append(
        f"B beats A on within_turn F1 on {f1_b_wins} of {f1_comparable} files with a valid A "
        f"score ({', '.join(d for d, diff in f1_diffs if diff > 0) or 'none'})."
        + (
            f" {', '.join(f1_nan_files)} excluded: condition A had 0 non-flagged samples there "
            f"(all auto-flagged degenerate -- see its own section above), so no A score exists "
            f"to compare."
            if f1_nan_files
            else ""
        )
    )
    lines.append(
        f"B beats A on collapse_rate (lower = fewer degenerate draws) on {collapse_b_wins} of "
        f"{len(batch_doc_ids)} files ({', '.join(d for d, diff in collapse_diffs if diff < 0) or 'none'})."
    )
    lines.append(
        "These are per-file counts, not a significance test or a pooled claim -- 10 files "
        "do not support one."
    )
    lines.append("")

    lines.append("## Baselines (cue rule and density-matched random), within-turn scope, same 10 batch files")
    lines.append("")
    lines.append(
        "Same per-file table structure as the A vs. B comparison above, for the cue rule "
        "(deterministic: boundary wherever a prosodic cue was rendered) and the density-"
        "matched random baseline, on the same 10 batch files (pilot excluded, matching the "
        "A vs. B section). Baselines are deterministic/resampled from text alone, not "
        "per-sample model draws, so there is no collapse_rate column here."
    )
    lines.append("")

    def _baseline_metric(doc_id, baseline_name, metric):
        rows = [r for r in baselines if r["doc_id"] == doc_id and r["scope"] == "within_turn" and r["baseline"] == baseline_name]
        return float(rows[0][metric]) if rows else float("nan")

    baseline_metrics = ["precision", "recall", "f1", "window_diff", "boundary_similarity"]
    bl_header = ["doc_id"]
    for m in baseline_metrics:
        bl_header += [f"cue_rule {m}", f"random {m}"]
    lines.append("| " + " | ".join(bl_header) + " |")
    lines.append("|" + "---|" * len(bl_header))
    for doc_id in batch_doc_ids:
        row_cells = [doc_id]
        for m in baseline_metrics:
            row_cells += [f"{_baseline_metric(doc_id, 'cue_rule', m):.4f}", f"{_baseline_metric(doc_id, 'random', m):.4f}"]
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append("")

    lines.append("### Where the model stands against the cue rule, file by file (within-turn F1)")
    lines.append("")
    lines.append(
        "The cue rule is not a naive baseline: it has direct access to the same prosodic "
        "cues condition B renders, applied deterministically (boundary after every cue), so "
        "it is a natural ceiling-ish comparison for B specifically, not just a floor. "
        "Condition A never sees cues at all, so its comparison to the cue rule tests "
        "something different (can text alone recover what the cue rule gets from prosodic "
        "markup) and is reported alongside, not instead."
    )
    lines.append("")
    lines.append("| doc_id | cue_rule F1 | A F1 | A vs. cue_rule | B F1 | B vs. cue_rule |")
    lines.append("|---|---|---|---|---|---|")

    def _verdict_cell(model_f1, cue_f1):
        # A file+condition with zero non-flagged samples (every sample
        # auto-flagged degenerate, e.g. SBC044 condition A below) has no
        # valid F1 to compare -- nan, not a loss: reported as its own
        # category, not folded silently into "loses to".
        if model_f1 != model_f1:  # nan check, no math import needed
            return "n/a (all samples auto-flagged)", None
        verdict = "beats" if model_f1 > cue_f1 else "loses to"
        return f"{verdict} ({model_f1 - cue_f1:+.4f})", model_f1 > cue_f1

    a_beats_cue = 0
    a_comparable = 0
    b_beats_cue = 0
    b_comparable = 0
    for doc_id in batch_doc_ids:
        cue_f1 = _baseline_metric(doc_id, "cue_rule", "f1")
        a_f1 = _within_turn_mean(doc_id, "A", "f1")
        b_f1 = _within_turn_mean(doc_id, "B", "f1")
        a_cell, a_win = _verdict_cell(a_f1, cue_f1)
        b_cell, b_win = _verdict_cell(b_f1, cue_f1)
        if a_win is not None:
            a_comparable += 1
            a_beats_cue += int(a_win)
        if b_win is not None:
            b_comparable += 1
            b_beats_cue += int(b_win)
        a_f1_cell = "nan" if a_f1 != a_f1 else f"{a_f1:.4f}"
        lines.append(f"| {doc_id} | {cue_f1:.4f} | {a_f1_cell} | {a_cell} | {b_f1:.4f} | {b_cell} |")
    lines.append("")
    lines.append(
        f"Condition A beats the cue rule on within_turn F1 on {a_beats_cue} of {a_comparable} "
        f"files with a valid (non-degenerate-only) score. Condition B beats the cue rule on "
        f"{b_beats_cue} of {b_comparable}. Per-file counts only -- no aggregate or significance "
        f"claim on 10 files."
    )
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


A_VS_B_CSV = Path("reports/phase2_batch1_a_vs_b.csv")
BASELINES_WIDE_CSV = Path("reports/phase2_batch1_baselines_wide.csv")
VS_CUE_RULE_CSV = Path("reports/phase2_batch1_vs_cue_rule.csv")


def write_comparison_csvs(batch: list[dict]) -> None:
    """One CSV per display table in write_report's "A vs. B", "Baselines"
    and "Where the model stands against the cue rule" sections -- same
    10 batch files (pilot excluded), same source data (reports/
    phase2_batch1_scores.csv and _baselines.csv), so these can never
    diverge from what the report shows. Missing/undefined values (e.g.
    SBC044 condition A, whose 5 samples are all auto-flagged degenerate)
    are written as "" (this codebase's existing convention for a missing
    numeric field, e.g. hyp_ref_ratio in scores.csv), not the string
    "nan" the markdown report uses for readability.
    """
    scores = _read_csv(SCORES_CSV)
    baselines = _read_csv(BASELINES_CSV)
    batch_doc_ids = [b["doc_id"] for b in batch if not b["is_pilot"]]

    def _scores_for(doc_id, cond_key, scope, flagged_value="False"):
        return [
            r for r in scores
            if r["doc_id"] == doc_id and r["condition"] == cond_key and r["scope"] == scope and r["flagged"] == flagged_value
        ]

    def _within_turn_mean(doc_id, cond_key, metric):
        vals = [float(r[metric]) for r in _scores_for(doc_id, cond_key, "within_turn") if r[metric] != ""]
        return mean(vals) if vals else float("nan")

    def _collapse_rate_for(doc_id, cond_key):
        any_rows = [r for r in scores if r["doc_id"] == doc_id and r["condition"] == cond_key]
        return float(any_rows[0]["collapse_rate"]) if any_rows else float("nan")

    def _baseline_metric(doc_id, baseline_name, metric):
        rows = [r for r in baselines if r["doc_id"] == doc_id and r["scope"] == "within_turn" and r["baseline"] == baseline_name]
        return float(rows[0][metric]) if rows else float("nan")

    def _fmt(v):
        return "" if v != v else f"{v:.4f}"  # v != v is the nan check

    comparison_metrics = ["precision", "recall", "f1", "window_diff", "boundary_similarity", "hyp_ref_ratio"]
    baseline_metrics = ["precision", "recall", "f1", "window_diff", "boundary_similarity"]

    A_VS_B_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(A_VS_B_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = ["doc_id"]
        for m in comparison_metrics:
            header += [f"a_{m}", f"b_{m}"]
        header += ["a_collapse_rate", "b_collapse_rate"]
        w.writerow(header)
        for doc_id in batch_doc_ids:
            row = [doc_id]
            for m in comparison_metrics:
                row += [_fmt(_within_turn_mean(doc_id, "A", m)), _fmt(_within_turn_mean(doc_id, "B", m))]
            row += [_fmt(_collapse_rate_for(doc_id, "A")), _fmt(_collapse_rate_for(doc_id, "B"))]
            w.writerow(row)

    with open(BASELINES_WIDE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = ["doc_id"]
        for m in baseline_metrics:
            header += [f"cue_rule_{m}", f"random_{m}"]
        w.writerow(header)
        for doc_id in batch_doc_ids:
            row = [doc_id]
            for m in baseline_metrics:
                row += [_fmt(_baseline_metric(doc_id, "cue_rule", m)), _fmt(_baseline_metric(doc_id, "random", m))]
            w.writerow(row)

    with open(VS_CUE_RULE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "cue_rule_f1", "a_f1", "a_vs_cue_rule", "a_diff", "b_f1", "b_vs_cue_rule", "b_diff"])
        for doc_id in batch_doc_ids:
            cue_f1 = _baseline_metric(doc_id, "cue_rule", "f1")
            a_f1 = _within_turn_mean(doc_id, "A", "f1")
            b_f1 = _within_turn_mean(doc_id, "B", "f1")
            if a_f1 != a_f1:
                a_verdict, a_diff = "n/a (all samples auto-flagged)", ""
            else:
                a_verdict, a_diff = ("beats" if a_f1 > cue_f1 else "loses to"), _fmt(a_f1 - cue_f1)
            if b_f1 != b_f1:
                b_verdict, b_diff = "n/a (all samples auto-flagged)", ""
            else:
                b_verdict, b_diff = ("beats" if b_f1 > cue_f1 else "loses to"), _fmt(b_f1 - cue_f1)
            w.writerow([doc_id, _fmt(cue_f1), _fmt(a_f1), a_verdict, a_diff, _fmt(b_f1), b_verdict, b_diff])


if __name__ == "__main__":
    batch = select_batch()
    print(format_selection_report(batch))
    print()
    stop = run_batch(batch)
    if stop is not None:
        print(f"\nBatch stopped early at {stop.doc_id}: "
              f"{stop.n_failed}/{stop.total_window_draws} window draws failed "
              f"({stop.failure_rate:.1%}) > {MAX_PARSE_FAILURE_RATE:.0%}.")
    write_report(batch)
    write_comparison_csvs(batch)
    print("\nWrote reports/phase2_batch1.md, the four batch1 CSVs, and the three comparison-table CSVs.")

"""Phase 2: set the degenerate-output flag threshold for windowed runs.

Phase 1's degenerate-output detector (CLAUDE.md, "Degenerate output")
flags a long run of consecutive predicted boundaries -- but on SBCSAE,
one-word IUs are common (median words-per-segment is 3, per
reports/phase2_per_file_stats.csv, and plenty of segments are shorter), so
a short run of consecutive boundaries is legitimate, unlike phase 1's
prose-derived EDUs. A fixed, guessed threshold risks flagging real,
correctly-segmented rapid speech as a model failure.

Instead: find the longest run of consecutive WITHIN-TURN reference
boundaries that actually occurs, per 600-word scored window, anywhere in
the whole corpus (59 files, SBC037 excluded) -- i.e. the most extreme
legitimate case the reference itself contains -- and set the flag
threshold one above it. Turn (speaker-change) boundaries are excluded
from this count: they are given to the model for free (see
sbcsae_scoring.py), never part of what a within-turn hypothesis predicts,
so a run of them is not a comparable phenomenon.

Whole-corpus run, terminal output only plus one small committed CSV (two
numbers, no transcript text).
"""
import csv
from pathlib import Path

from masses import masses_to_boundaries
from sbcsae_llm import build_document_structure
from sbcsae_reader import iter_trn_documents
from sbcsae_windows import build_score_regions

EXCLUDE_FILES = {"SBC037"}


def max_consecutive_run(sorted_positions: list[int]) -> int:
    best = 0
    current = 0
    prev = None
    for p in sorted_positions:
        current = current + 1 if prev is not None and p == prev + 1 else 1
        best = max(best, current)
        prev = p
    return best


def longest_within_turn_run_per_window():
    overall_max = 0
    overall_loc = None  # (file, score_start, score_end)
    per_file_max = {}

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id in EXCLUDE_FILES:
            continue
        doc = build_document_structure(doc_id, units)
        ref_boundaries = masses_to_boundaries(doc.ref_masses)
        within_turn = ref_boundaries - doc.turn_boundaries
        regions = build_score_regions(doc.n_tokens)

        file_max = 0
        for region in regions:
            # A boundary p belongs to this region iff p+1 is in
            # [score_start, score_end] (sbcsae_windows.region_for_boundary's
            # own rule), i.e. p in [score_start-1, score_end-1].
            owned = sorted(
                p for p in within_turn if region.score_start - 1 <= p <= region.score_end - 1
            )
            run = max_consecutive_run(owned)
            if run > file_max:
                file_max = run
            if run > overall_max:
                overall_max = run
                overall_loc = (doc_id, region.score_start, region.score_end)

        per_file_max[doc_id] = file_max

    return overall_max, overall_loc, per_file_max


def main():
    overall_max, overall_loc, per_file_max = longest_within_turn_run_per_window()
    threshold = overall_max + 1

    print(f"Longest run of consecutive within-turn reference boundaries, per 600-word "
          f"scored window, across all 59 files: {overall_max}")
    print(f"  (found in {overall_loc[0]}, window scoring words {overall_loc[1]}-{overall_loc[2]})")
    print(f"Degenerate-output flag threshold: {threshold} "
          f"(one more than the longest legitimate run observed)")

    reports_dir = Path("reports")
    with open(reports_dir / "phase2_degenerate_threshold.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["longest_observed_within_turn_run", overall_max])
        w.writerow(["longest_observed_file", overall_loc[0]])
        w.writerow(["longest_observed_window_score_start", overall_loc[1]])
        w.writerow(["longest_observed_window_score_end", overall_loc[2]])
        w.writerow(["degenerate_flag_threshold", threshold])

    print("\nPer-file max run (top 10):")
    for doc_id, m in sorted(per_file_max.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {doc_id}: {m}")

    print("\nWrote reports/phase2_degenerate_threshold.csv")


if __name__ == "__main__":
    main()

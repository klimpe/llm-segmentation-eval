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
legitimate case the reference itself contains. Turn (speaker-change)
boundaries are excluded from this count: they are given to the model for
free (see sbcsae_scoring.py), never part of what a within-turn hypothesis
predicts, so a run of them is not a comparable phenomenon.

That longest legitimate run is **11** (SBC038, words 2401-3000).

**Auto-flag threshold: 22 (twice 11), not 12 (one more than 11).** One
more than the observed maximum treats the single most extreme legitimate
case the corpus happens to contain as the ceiling -- but that maximum
was found over a finite sample (59 files); a threshold sitting right at
its edge would auto-flag the next real run that is merely as extreme,
which is not evidence of a model failure, just of the corpus containing
more than one case near its own extreme. Doubling leaves headroom
proportional to the phenomenon's own observed scale, per
reports/phase2_llm_design.md S3.

**This does not mean everything under 22 is ignored.** Per the pilot
review policy: every draw containing a run STRICTLY LONGER than 11 (the
actual longest legitimate run, not the doubled threshold) is listed for
manual reading, whether or not it crosses 22 and gets auto-flagged. A
run of, say, 15 is unprecedented in the reference and worth a human
look even though it stays under the auto-flag line; MANUAL_REVIEW_RUN
and DEGENERATE_FLAG_THRESHOLD are deliberately two different numbers
for two different jobs -- one triggers an automatic label, the other
triggers a human reading a specific draw.

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

# Set from the corpus-observed maximum (see longest_within_turn_run_per_window,
# run once, result hand-recorded here rather than recomputed live -- the
# corpus does not change between runs of a real pilot).
MAX_LEGITIMATE_RUN = 11
DEGENERATE_FLAG_THRESHOLD = 2 * MAX_LEGITIMATE_RUN  # 22


def review_policy(run_length: int) -> dict:
    """What to do with one observed run of consecutive predicted
    within-turn boundaries, in a real pilot run: whether it gets the
    automatic "degenerate" label, and whether it goes on the manual
    reading list regardless of that label -- the two thresholds are
    deliberately different (see module docstring).
    """
    return {
        "run_length": run_length,
        "flagged_degenerate": run_length > DEGENERATE_FLAG_THRESHOLD,
        "needs_manual_review": run_length > MAX_LEGITIMATE_RUN,
    }


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
    if overall_max != MAX_LEGITIMATE_RUN:
        print(
            f"NOTE: recomputed longest legitimate run is {overall_max}, but "
            f"MAX_LEGITIMATE_RUN is hand-set to {MAX_LEGITIMATE_RUN} -- update the "
            f"constant (and DEGENERATE_FLAG_THRESHOLD) if the corpus or its "
            f"reader/tokeniser have changed since that figure was recorded."
        )

    print(f"Longest run of consecutive within-turn reference boundaries, per 600-word "
          f"scored window, across all 59 files: {overall_max}")
    print(f"  (found in {overall_loc[0]}, window scoring words {overall_loc[1]}-{overall_loc[2]})")
    print(f"Degenerate-output flag threshold: {DEGENERATE_FLAG_THRESHOLD} "
          f"(2x the longest legitimate run, {MAX_LEGITIMATE_RUN})")
    print(f"Manual-review threshold: any run > {MAX_LEGITIMATE_RUN} "
          f"(independent of the auto-flag threshold -- see review_policy)")

    reports_dir = Path("reports")
    with open(reports_dir / "phase2_degenerate_threshold.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["longest_observed_within_turn_run", overall_max])
        w.writerow(["longest_observed_file", overall_loc[0]])
        w.writerow(["longest_observed_window_score_start", overall_loc[1]])
        w.writerow(["longest_observed_window_score_end", overall_loc[2]])
        w.writerow(["max_legitimate_run", MAX_LEGITIMATE_RUN])
        w.writerow(["degenerate_flag_threshold", DEGENERATE_FLAG_THRESHOLD])
        w.writerow(["manual_review_threshold", MAX_LEGITIMATE_RUN])

    print("\nPer-file max run (top 10):")
    for doc_id, m in sorted(per_file_max.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {doc_id}: {m}")

    print("\nWrote reports/phase2_degenerate_threshold.csv")


if __name__ == "__main__":
    main()

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


def max_consecutive_run_with_span(sorted_positions: list[int]) -> tuple[int, tuple[int, int] | None]:
    """Like max_consecutive_run, but also returns the (start, end) of the
    longest run (the first one found, if there is a tie) -- needed by
    per_file_review_policy, which must know WHERE the run sits to count
    how many real reference boundaries fall in the same span. Returns
    (0, None) for an empty input.
    """
    best = 0
    best_span = None
    current = 0
    current_start = None
    prev = None
    for p in sorted_positions:
        if prev is not None and p == prev + 1:
            current += 1
        else:
            current = 1
            current_start = p
        if current > best:
            best = current
            best_span = (current_start, p)
        prev = p
    return best, best_span


def file_max_legitimate_run(doc_id: str, units, core: int | None = None, margin: int | None = None) -> int:
    """This one file's own observed maximum run of consecutive within-turn
    reference boundaries, per scored window -- the file-local analogue of
    the whole-corpus MAX_LEGITIMATE_RUN (11, from SBC038 alone). Used by
    per_file_review_policy instead of applying one outlier file's
    threshold to every file (reports/phase2_llm_design.md's per-file
    degeneracy section).

    core/margin default to sbcsae_windows' own defaults (600/100) if not
    given -- pass the same core/margin a non-default window-size run used
    (e.g. the 400/300-word SBC053 test) so the "legitimate maximum" is
    measured over the SAME window boundaries the runs being judged were
    scored in; a run's ceiling is a property of how it was windowed, not
    just of the document.
    """
    doc = build_document_structure(doc_id, units)
    ref_boundaries = masses_to_boundaries(doc.ref_masses)
    within_turn = ref_boundaries - doc.turn_boundaries
    kwargs = {}
    if core is not None:
        kwargs["core"] = core
    if margin is not None:
        kwargs["margin"] = margin
    regions = build_score_regions(doc.n_tokens, **kwargs)

    file_max = 0
    for region in regions:
        # A boundary p belongs to this region iff p+1 is in
        # [score_start, score_end] (sbcsae_windows.region_for_boundary's
        # own rule), i.e. p in [score_start-1, score_end-1].
        owned = sorted(p for p in within_turn if region.score_start - 1 <= p <= region.score_end - 1)
        file_max = max(file_max, max_consecutive_run(owned))
    return file_max


def per_file_review_policy(run_length: int, ref_boundaries_in_span: int, file_max_legitimate_run: int) -> dict:
    """Per-file degeneracy rule, replacing the whole-corpus-calibrated
    review_policy/MAX_LEGITIMATE_RUN/DEGENERATE_FLAG_THRESHOLD constants
    above for callers that have file-specific reference data available
    (see reports/phase2_llm_design.md for why the global 11/22 pair,
    calibrated on a single outlier file (SBC038), does not transfer to
    other files whose own legitimate maximum can be much lower).

    A run is degenerate iff it is BOTH:
      - longer than THIS FILE's own observed maximum legitimate run
        (file_max_legitimate_run, from file_max_legitimate_run above),
        so a file with a naturally low ceiling doesn't need an
        implausibly long run before anything gets flagged; AND
      - predicting more than 3x as many boundaries as the reference
        actually has in that same span, so a run that is long but still
        broadly TRACKS a real, dense run of short reference units (fast
        speech, one-word IUs) is not flagged just for being long -- only
        one that is also badly over-segmenting relative to the truth in
        that specific span.
    Both conditions are needed: length alone conflates "unusual for this
    file" with "wrong"; the ratio alone would flag correctly-identified
    but genuinely dense passages the file's own reference already shows
    are legitimate.
    """
    exceeds_file_max = run_length > file_max_legitimate_run
    exceeds_ratio = run_length > 3 * ref_boundaries_in_span
    return {
        "run_length": run_length,
        "ref_boundaries_in_span": ref_boundaries_in_span,
        "file_max_legitimate_run": file_max_legitimate_run,
        "exceeds_file_max": exceeds_file_max,
        "exceeds_ratio": exceeds_ratio,
        "degenerate": exceeds_file_max and exceeds_ratio,
    }


def longest_within_turn_run_per_window():
    overall_max = 0
    overall_loc = None  # (file, score_start, score_end)
    per_file_max = {}

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id in EXCLUDE_FILES:
            continue
        per_file_max[doc_id] = file_max_legitimate_run(doc_id, units)
        if per_file_max[doc_id] > overall_max:
            # Recover the winning window's own range for the location
            # report below -- file_max_legitimate_run doesn't return it,
            # so it is recomputed here only for the single file that just
            # set a new overall maximum (cheap: this branch is taken at
            # most a handful of times across the whole corpus).
            doc = build_document_structure(doc_id, units)
            within_turn = masses_to_boundaries(doc.ref_masses) - doc.turn_boundaries
            for region in build_score_regions(doc.n_tokens):
                owned = sorted(p for p in within_turn if region.score_start - 1 <= p <= region.score_end - 1)
                if max_consecutive_run(owned) == per_file_max[doc_id]:
                    overall_max = per_file_max[doc_id]
                    overall_loc = (doc_id, region.score_start, region.score_end)
                    break

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

"""Phase 2: per-file corpus statistics for pilot-file selection.

Whole-corpus run (59 files, SBC037 excluded per CLAUDE.md's "Reading the
corpus" section: bilingual, not the same task as monolingual English).
No transcript text in the output -- counts only, per the licence's
no-derivative-transcript rule.

For each file:
  words                          -- total tokenised words (condition-
                                     independent: word identity/count never
                                     differs between A and B)
  reference_segments             -- non-zero-word IUs (sbcsae_tokenizer.
                                     reference_segments); this is what the
                                     masses contract will actually score
                                     against
  mean_words_per_segment
  median_words_per_segment
  speaker_changes                -- adjacent pairs of reference segments
                                     with a different speaker
  share_boundaries_at_speaker_change
                                  -- speaker_changes / (reference_segments - 1);
                                     both counted over the SAME reference-
                                     segment sequence, so this is exactly
                                     the fraction of scored boundaries that
                                     coincide with a turn change
  zero_word_ius_dropped_share    -- zero-word IUs / all merged IUs (reader
                                     output, before the tokeniser's own
                                     drop)
  overlap_bracket_density_per_100_words
                                  -- raw '[' count (every overlap-bracket
                                     span, numbered or not) per 100 words;
                                     counted on raw IU text, since the
                                     bracket itself is dropped by the
                                     tokeniser and leaves no token to count

Zero-word IUs are excluded from the speaker-change count (a dropped IU
contributes no scored boundary either side), consistent with
reference_segments() itself.
"""
import csv
import statistics
from pathlib import Path

from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import TokenizeError, tokenize, words_only

EXCLUDE = {"SBC037"}

COLUMNS = [
    "words",
    "reference_segments",
    "mean_words_per_segment",
    "median_words_per_segment",
    "speaker_changes",
    "share_boundaries_at_speaker_change",
    "zero_word_ius_dropped_share",
    "overlap_bracket_density_per_100_words",
]


def per_file_row(doc_id: str, units) -> dict:
    n_ius = len(units)
    kept = []  # (speaker, n_words, raw_text)
    n_zero_word = 0
    n_raised = 0
    total_open_brackets = 0

    for u in units:
        total_open_brackets += u.text.count("[")
        try:
            items = tokenize(u.text)
        except TokenizeError:
            n_raised += 1
            continue
        words = words_only(items)
        if not words:
            n_zero_word += 1
            continue
        kept.append((u.speaker, len(words)))

    if n_raised:
        raise RuntimeError(f"{doc_id}: {n_raised} IU(s) raised during tokenisation (expected 0)")

    n_words = sum(n for _, n in kept)
    n_segs = len(kept)
    per_seg_counts = [n for _, n in kept]

    speaker_changes = sum(
        1 for (s1, _), (s2, _) in zip(kept, kept[1:]) if s1 != s2
    )
    n_boundaries = n_segs - 1

    return {
        "file": doc_id,
        "words": n_words,
        "reference_segments": n_segs,
        "mean_words_per_segment": statistics.mean(per_seg_counts) if per_seg_counts else 0.0,
        "median_words_per_segment": statistics.median(per_seg_counts) if per_seg_counts else 0.0,
        "speaker_changes": speaker_changes,
        "share_boundaries_at_speaker_change": (speaker_changes / n_boundaries) if n_boundaries > 0 else 0.0,
        "zero_word_ius_dropped_share": (n_zero_word / n_ius) if n_ius > 0 else 0.0,
        "overlap_bracket_density_per_100_words": (total_open_brackets / n_words * 100) if n_words > 0 else 0.0,
    }


def quantiles_summary(rows: list[dict]) -> list[dict]:
    summary = []
    for stat_name, fn in [
        ("min", min),
        ("q1", lambda xs: statistics.quantiles(xs, n=4)[0]),
        ("median", statistics.median),
        ("q3", lambda xs: statistics.quantiles(xs, n=4)[2]),
        ("max", max),
    ]:
        row = {"stat": stat_name}
        for col in COLUMNS:
            values = [r[col] for r in rows]
            row[col] = fn(values)
        summary.append(row)
    return summary


def main():
    reports_dir = Path("reports")
    rows = []
    for doc_id, units, *_ in iter_trn_documents():
        if doc_id in EXCLUDE:
            continue
        rows.append(per_file_row(doc_id, units))

    rows.sort(key=lambda r: r["file"])
    print(f"{len(rows)} files (expected 59)")

    with open(reports_dir / "phase2_per_file_stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file"] + COLUMNS)
        w.writeheader()
        w.writerows(rows)

    summary = quantiles_summary(rows)
    with open(reports_dir / "phase2_per_file_stats_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stat"] + COLUMNS)
        w.writeheader()
        w.writerows(summary)

    print("\n=== Summary (min / Q1 / median / Q3 / max) ===")
    header = f"{'stat':8s} " + " ".join(f"{c:>36s}" for c in COLUMNS)
    print(header)
    for row in summary:
        print(f"{row['stat']:8s} " + " ".join(f"{row[c]:36.4f}" for c in COLUMNS))

    print(f"\nWrote reports/phase2_per_file_stats.csv ({len(rows)} rows) "
          f"and reports/phase2_per_file_stats_summary.csv")


if __name__ == "__main__":
    main()

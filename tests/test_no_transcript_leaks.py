"""Guards against the defect fixed twice this stage (sbcsae_reader.py's
NUL-byte CSVs, then sbcsae_marker_inventory.py's no-tier-examples CSV):
a script silently writing full transcript text into a CSV under reports/
or results/ (committed, public) instead of reports/private/ (gitignored).

Was a blocklist of text-like column names (text/context/content/raw/
iu_text). Strengthened this session to an allowlist of expected columns
per committed CSV (ALLOWED_COLUMNS below): any column a script writes that
isn't on that file's list fails the test, so adding one -- text-like or
not -- requires an explicit decision here rather than silently going out
in a rerun. The content check below (empty except the 14-row exception) is
unchanged and still the thing that actually catches a leak in a column
already on the allowlist, such as "content" in phase2_excluded_lines.csv.
"""
import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEXT_LIKE_COLUMNS = {"text", "context", "content", "raw", "iu_text"}
ALLOWED_EXCEPTION_FILE = "phase2_excluded_lines.csv"
ALLOWED_EXCEPTION_REASONS = {"dubois_dollar_note", "backslash_fused", "ambiguous_fields"}

# Keyed by "<reports|results>/<filename>.csv" -- every committed CSV this
# stage's scripts write, with its exact current column set. A script that
# starts writing a new column (or a whole new committed CSV, which shows
# up here as a "not on the allowlist" failure for the file itself) must
# update this table in the same commit as an explicit decision, not as a
# side effect of a rerun.
ALLOWED_COLUMNS = {
    "reports/phase2_baselines_per_file.csv": {
        "file", "n_tokens",
        "cue_rule_within_turn_f1", "cue_rule_all_boundaries_f1",
        "random_within_turn_f1_mean", "random_within_turn_f1_lo", "random_within_turn_f1_hi",
        "random_all_boundaries_f1_mean", "random_all_boundaries_f1_lo", "random_all_boundaries_f1_hi",
    },
    "reports/phase2_capitalization.csv": {"category", "label", "n_words", "n_capitalised", "share_capitalised"},
    "reports/phase2_capitalization_by_file.csv": {
        "file",
        "a_n", "b_n", "c_n", "d_n", "e_n", "f_n", "g_n",
        "a_capitalised", "b_capitalised", "c_capitalised", "d_capitalised",
        "e_capitalised", "f_capitalised", "g_capitalised",
    },
    "reports/phase2_degenerate_threshold.csv": {"metric", "value"},
    "reports/phase2_excluded_lines.csv": {"file", "line", "reason", "content"},
    "reports/phase2_marker_inventory.csv": {
        "class", "tier", "count", "files",
        "before_first_word", "between_words", "after_last_word", "iu_has_no_words",
    },
    "reports/phase2_marker_no_tier.csv": {"pattern", "count", "files"},
    "reports/phase2_marker_no_tier_examples.csv": {"pattern", "file", "line"},
    "reports/phase2_merge_counts.csv": {"file", "raw_lines", "merged_units", "merges"},
    "reports/phase2_nul_bytes.csv": {"file", "line", "byte"},
    "reports/phase2_per_file_stats.csv": {
        "file", "words", "reference_segments", "mean_words_per_segment",
        "median_words_per_segment", "speaker_changes",
        "share_boundaries_at_speaker_change", "zero_word_ius_dropped_share",
        "overlap_bracket_density_per_100_words",
    },
    "reports/phase2_per_file_stats_summary.csv": {
        "stat", "words", "reference_segments", "mean_words_per_segment",
        "median_words_per_segment", "speaker_changes",
        "share_boundaries_at_speaker_change", "zero_word_ius_dropped_share",
        "overlap_bracket_density_per_100_words",
    },
    "reports/phase2_reference_segments_by_file.csv": {
        "file", "segments_before", "segments_after", "dropped",
    },
    "reports/phase2_speaker_colon_fix.csv": {
        "file", "raw_line", "iu_index", "old_speaker", "new_speaker", "in_amp_chain", "cause",
    },
    "reports/phase2_tokenizer_crosscheck_summary.csv": {"diff", "category", "count"},
    "reports/phase2_tokenizer_invariants_summary.csv": {"check", "category", "count"},
    "reports/phase2_tokenizer_capitalised_tally.csv": {"value", "kept", "removed"},
    "reports/phase2_tokenizer_raises.csv": {"char", "codepoint", "count", "files", "reason"},
    "reports/phase2_tokenizer_summary.csv": {"metric", "value"},
    "reports/phase2_tokenizer_words_per_iu.csv": {"n_words", "n_ius"},
    "reports/phase2_tokenizer_zero_word_by_file.csv": {"file", "zero_word_ius"},
    "reports/phase2_tokenizer_zero_word_composition.csv": {"composition", "count"},
    "reports/phase2_truncation_position.csv": {
        "category", "n_truncated", "share_of_truncated", "n_all_words", "truncation_rate",
    },
    "reports/phase2_word_internal_marks.csv": {
        "symbol", "word_internal", "word_final", "standalone",
        "total_plain_rule_occurrences", "vanish_share_under_old_rendering",
        "raw_char_count_any_context", "compound_or_other_occurrences",
    },
    "results/eng.rst.gum_dev_excluded.csv": {"doc_id", "masked_fraction", "reason"},
    "results/eng.rst.gum_dev_failures.csv": {"doc_id", "reason"},
    "results/eng.rst.gum_dev_masking.csv": {"doc_id", "n_tokens", "masked_fraction"},
    "results/eng.rst.gum_dev_per_document.csv": {
        "doc_id", "genre", "n_tokens", "ref_segs", "hyp_segs",
        "precision", "recall", "f1", "window_diff", "boundary_similarity",
    },
    "results/eng.rst.gum_dev_per_genre.csv": {
        "genre", "n_docs", "mean_f1", "mean_window_diff", "mean_boundary_similarity",
        "micro_precision", "micro_recall", "micro_f1",
    },
    "results/eng.rst.gum_dev_resampling_failures.csv": {
        "group", "doc_id", "genre", "condition", "sample", "reason",
    },
    "results/eng.rst.gum_dev_resampling_per_sample.csv": {
        "group", "doc_id", "genre", "condition", "sample",
        "precision", "recall", "f1", "hyp_segs", "trailing_collapse_run",
    },
    "results/eng.rst.gum_dev_resampling_summary.csv": {
        "group", "doc_id", "genre", "condition", "n_samples",
        "precision_mean", "precision_min", "precision_max",
        "recall_mean", "recall_min", "recall_max",
        "f1_mean", "f1_min", "f1_max", "max_trailing_collapse_run",
    },
    "results/eng.rst.gum_dev_summary.csv": {"metric", "value"},
    "results/eng.rst.gum_dev_zero_vs_fewshot_per_document.csv": {
        "doc_id", "genre",
        "zeroshot_precision", "fewshot_precision",
        "zeroshot_recall", "fewshot_recall",
        "zeroshot_f1", "fewshot_f1",
        "zeroshot_window_diff", "fewshot_window_diff",
        "zeroshot_boundary_similarity", "fewshot_boundary_similarity",
    },
    "results/eng.rst.gum_dev_zero_vs_fewshot_per_genre.csv": {
        "genre", "n_docs",
        "zeroshot_micro_precision", "fewshot_micro_precision",
        "zeroshot_micro_recall", "fewshot_micro_recall",
        "zeroshot_micro_f1", "fewshot_micro_f1",
    },
    "results/eng.rst.gum_dev_zero_vs_fewshot_segment_ratios.csv": {
        "doc_id", "genre", "ref_segs",
        "zeroshot_hyp_segs", "fewshot_hyp_segs", "zeroshot_ratio", "fewshot_ratio",
    },
    "results/eng.rst.gum_dev_zero_vs_fewshot_summary.csv": {
        "metric", "zero_shot", "few_shot", "delta",
    },
}


def _report_and_result_csvs():
    csvs = []
    for base in ("reports", "results"):
        base_dir = REPO_ROOT / base
        if not base_dir.is_dir():
            continue
        for path in base_dir.rglob("*.csv"):
            if "private" in path.relative_to(REPO_ROOT).parts:
                continue
            csvs.append(path)
    return csvs


def test_every_committed_csv_column_is_on_the_allowlist():
    offenders = []
    for path in _report_and_result_csvs():
        key = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        with open(path, newline="", encoding="utf-8") as f:
            fieldnames = set(csv.DictReader(f).fieldnames or [])
        allowed = ALLOWED_COLUMNS.get(key)
        if allowed is None:
            offenders.append(f"{key}: not on ALLOWED_COLUMNS -- new committed CSV needs an explicit decision")
            continue
        extra = fieldnames - allowed
        if extra:
            offenders.append(f"{key}: unexpected column(s) {sorted(extra)} not on the allowlist")

    assert not offenders, "committed CSV column(s) outside the allowlist:\n" + "\n".join(offenders)


def test_no_committed_csv_has_a_populated_text_like_column():
    offenders = []
    for path in _report_and_result_csvs():
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            text_cols = [c for c in fieldnames if c.lower() in TEXT_LIKE_COLUMNS]
            if not text_cols:
                continue
            for row_no, row in enumerate(reader, start=2):  # header is line 1
                for col in text_cols:
                    value = (row.get(col) or "").strip()
                    if not value:
                        continue
                    if path.name == ALLOWED_EXCEPTION_FILE and row.get("reason") in ALLOWED_EXCEPTION_REASONS:
                        continue
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{row_no} column {col!r}: {value!r}")

    assert not offenders, "populated text-like column(s) in a committed CSV:\n" + "\n".join(offenders[:20])


def test_every_report_and_result_csv_was_actually_scanned():
    # A sanity check on the scanner itself, not the corpus: if reports/ or
    # results/ ever end up empty (e.g. a future refactor moves everything
    # under a new directory), the test above would pass vacuously and
    # silently stop guarding anything. Fail loudly instead.
    assert len(_report_and_result_csvs()) > 10

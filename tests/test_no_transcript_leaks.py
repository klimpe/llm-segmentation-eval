"""Guards against the defect fixed twice this stage (sbcsae_reader.py's
NUL-byte CSVs, then sbcsae_marker_inventory.py's no-tier-examples CSV):
a script silently writing full transcript text into a CSV under reports/
or results/ (committed, public) instead of reports/private/ (gitignored).

Scans every CSV actually on disk under reports/ and results/ (not
reports/private/) for a text-like column and asserts it is empty --
except phase2_excluded_lines.csv's 14 original rows ($ / backslash-fused /
ambiguous-field), which have always carried short content by design (Du
Bois researcher notes and transcription artifacts, not participant
speech) and are the one documented exception.
"""
import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEXT_LIKE_COLUMNS = {"text", "context", "content", "raw", "iu_text"}
ALLOWED_EXCEPTION_FILE = "phase2_excluded_lines.csv"
ALLOWED_EXCEPTION_REASONS = {"dubois_dollar_note", "backslash_fused", "ambiguous_fields"}


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

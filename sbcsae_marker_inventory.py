"""Phase 2 stage 4, step 1: marker inventory over the whole SBCSAE corpus.

Classifies every non-word symbol in the reader's parsed IU text (the
settled, unmodified sbcsae_reader) against the three tokenisation tiers in
CLAUDE.md, and separately surfaces anything that fits none of them. Read-only
with respect to the reader; produces no tokeniser output.

Run: python3 sbcsae_marker_inventory.py
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from sbcsae_reader import (
    AmbiguousFieldsError,
    CORPUS_DIR,
    decode_document,
    iter_trn_documents,
    split_line_fields,
)

NO_TIER = {"DOUBLE_ANGLE_OPEN", "DOUBLE_ANGLE_CLOSE"}

# --- marker classes, in priority order (first alternative that matches at
# a given position wins -- order encodes exactly the precedence rules
# CLAUDE.md calls out, e.g. (H)/(Hx) must be tried before the generic
# all-caps vocal-noise rule so the latter never swallows the former). -----
#
# The last two entries (INDECIPHERABLE_X, WORD) are tier-3 "kept always"
# atomic units, used only to say where a marker falls relative to the IU's
# words -- they are not reported as marker classes in the table.
_MARKER_PATTERNS = [
    # Tier 1 -- removed in both conditions
    ("RESEARCH_COMMENT", r"\(\([^()]*\)*"),
    ("BREATH_IN", r"\(H\)"),
    ("BREATH_OUT", r"\(Hx\)"),
    ("LATCHING", r"\(0\)"),
    ("VOCAL_NOISE_CAPS", r"\([A-Z][A-Z0-9_., ]*\)"),
    ("DOUBLE_ANGLE_OPEN", r"<<[A-Za-z]+"),       # not in any documented tier
    ("DOUBLE_ANGLE_CLOSE", r"[A-Za-z]+>>"),      # not in any documented tier
    ("ANGLE_OPEN", r"<[A-Za-z0-9@]+"),
    ("ANGLE_CLOSE", r"[A-Za-z0-9@]+>"),
    ("OVERLAP_NUM_OPEN", r"\[\d+"),
    ("OVERLAP_NUM_CLOSE", r"\d+\]"),
    ("OVERLAP_OPEN", r"\["),
    ("OVERLAP_CLOSE", r"\]"),
    ("AT_SIGN", r"@+"),
    # Tier 2 -- removed in A, kept in B (prosodic cues)
    ("PAUSE_TIMED", r"\.\.\.\(\d+(?:\.\d+)?\)"),
    ("PAUSE_LONG", r"\.\.\."),
    ("PAUSE_SHORT", r"\.\."),
    ("IU_TRUNCATION", r"--"),
    ("LENGTHENING", r"="),
    ("ACCENT_CARET", r"\^"),
    ("ACCENT_BACKTICK", r"`"),
    ("BOOSTER_BANG", r"!"),
    ("BOOSTER_SEMI", r";"),
    ("GLOTTAL", r"%"),
    ("PITCH_BACKSLASH", r"\\"),
    ("PITCH_SLASH", r"/"),
    ("PITCH_UNDERSCORE", r"_"),
    # Not in any tier -- transitional continuity punctuation
    ("PERIOD", r"\."),
    ("COMMA", r","),
    ("QMARK", r"\?"),
    # Tier 3 -- kept always (word-like spans, not reported as marker rows)
    ("INDECIPHERABLE_X", r"\bX+\b"),
    # Unicode letters (not just ASCII) so SBC037's Spanish words don't fall
    # through to OTHER; internal apostrophe for contractions (don't, I'm);
    # trailing apostrophe for plural possessives (kids'); trailing single
    # hyphen for word truncation (y-) -- but not when a second hyphen
    # follows, so a real "word--" (word directly abutting IU truncation,
    # no space) leaves "--" intact for IU_TRUNCATION instead of splitting it.
    ("WORD", r"[^\W\d_]+(?:['-][^\W\d_]+)*(?:-(?!-)|')?"),
    # Catch-all: single non-space character matching no rule above.
    ("OTHER", r"\S"),
]

TIER = {
    "RESEARCH_COMMENT": "1",
    "BREATH_IN": "2",
    "BREATH_OUT": "2",
    "LATCHING": "2",
    "VOCAL_NOISE_CAPS": "1",
    "DOUBLE_ANGLE_OPEN": "?",
    "DOUBLE_ANGLE_CLOSE": "?",
    "ANGLE_OPEN": "1",
    "ANGLE_CLOSE": "1",
    "OVERLAP_NUM_OPEN": "1",
    "OVERLAP_NUM_CLOSE": "1",
    "OVERLAP_OPEN": "1",
    "OVERLAP_CLOSE": "1",
    "AT_SIGN": "1",
    "PAUSE_TIMED": "2",
    "PAUSE_LONG": "2",
    "PAUSE_SHORT": "2",
    "IU_TRUNCATION": "2",
    "LENGTHENING": "2",
    "ACCENT_CARET": "2",
    "ACCENT_BACKTICK": "2",
    "BOOSTER_BANG": "2",
    "BOOSTER_SEMI": "2",
    "GLOTTAL": "2",
    "PITCH_BACKSLASH": "2",
    "PITCH_SLASH": "2",
    "PITCH_UNDERSCORE": "2",
    "PERIOD": "none (continuity)",
    "COMMA": "none (continuity)",
    "QMARK": "none (continuity)",
    "OTHER": "?",
}

_MASTER_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in _MARKER_PATTERNS))

WORD_LIKE = {"WORD", "INDECIPHERABLE_X"}


def scan_iu(text: str):
    """Yield (class_name, start, end, matched_text) for every marker and
    word-like span in an IU's text, left to right, non-overlapping."""
    for m in _MASTER_RE.finditer(text):
        name = m.lastgroup
        yield name, m.start(), m.end(), m.group()


def classify_position(word_spans, start, end):
    if not word_spans:
        return "iu_has_no_words"
    if end <= word_spans[0][0]:
        return "before_first_word"
    if start >= word_spans[-1][1]:
        return "after_last_word"
    return "between_words"


_decoded_cache: dict[str, str] = {}


def find_line_number(doc_id: str, iu_text: str) -> int | None:
    """Best-effort lookup of the raw-file line number containing iu_text's
    text field, by matching its first non-blank word run. Merged ('&')
    IUs won't appear verbatim on one raw line -- returns None then, and the
    caller falls back to reporting just the file.
    """
    if doc_id not in _decoded_cache:
        _decoded_cache[doc_id] = decode_document(CORPUS_DIR / f"{doc_id}.trn", [])
    needle = iu_text[:15]
    for line_no, line in enumerate(_decoded_cache[doc_id].split("\n"), start=1):
        if needle and needle in line:
            return line_no
    return None


def raw_line_examples(pattern: str, limit: int = 3) -> list[tuple[str, int, str]]:
    """Scan every .trn file's decoded text for `pattern` occurring in the
    TEXT field specifically (not the timestamp/speaker columns -- a naive
    whole-line search would match, e.g., every '1' or ':' in a timestamp or
    speaker label) and return up to `limit` (file, line_no, text) hits, for
    illustrating a no-tier pattern with a genuine file:line reference.

    Uses the reader's own split_line_fields to isolate the text field, but
    does not replicate its $-note/backslash/ambiguous exclusion or its '&'
    merge -- fine for illustration, since these are examples, not counts.
    """
    rx = re.compile(pattern)
    hits: list[tuple[str, int, str]] = []
    for path in sorted(CORPUS_DIR.glob("SBC*.trn")):
        doc_id = path.stem
        text = decode_document(path, [])
        for line_no, line in enumerate(text.split("\n"), start=1):
            if not line.strip() or "\\" in line:
                continue
            try:
                _, _, _, field_text = split_line_fields(line)
            except (ValueError, AmbiguousFieldsError):
                continue
            if rx.search(field_text):
                hits.append((doc_id, line_no, field_text))
                if len(hits) >= limit:
                    return hits
    return hits


def main():
    import csv

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    class_counts = Counter()
    class_files = defaultdict(set)
    class_positions = defaultdict(Counter)
    n_ius = 0
    n_ius_zero_words = 0
    unmatched_context = defaultdict(list)  # OTHER char -> [(file, iu_text)]
    other_char_counts = Counter()
    other_char_files = defaultdict(set)

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id == "SBC037":
            # Excluded from scoring for code-switching reasons
            # (reports/phase2_data.md S6); excluded from all figures here
            # too, per the stage-4 follow-up instruction.
            continue
        for u in units:
            n_ius += 1
            text = u.text
            spans = list(scan_iu(text))
            word_spans = [(s, e) for name, s, e, _ in spans if name in WORD_LIKE]
            if not word_spans:
                n_ius_zero_words += 1
            for name, s, e, matched in spans:
                if name in WORD_LIKE:
                    continue
                class_counts[name] += 1
                class_files[name].add(doc_id)
                pos = classify_position(word_spans, s, e)
                class_positions[name][pos] += 1
                if name == "OTHER":
                    other_char_counts[matched] += 1
                    other_char_files[matched].add(doc_id)
                    if len(unmatched_context[matched]) < 3:
                        unmatched_context[matched].append((doc_id, text))

    # --- main table: only classes that fit one of CLAUDE.md's three tiers,
    # or the explicitly-called-out continuity punctuation -------------
    print(f"=== Marker inventory over {n_ius} IUs (59 files, excl. SBC037) ===\n")
    header = f"{'class':20s} {'tier':18s} {'count':>8s} {'files':>6s} {'before':>8s} {'between':>8s} {'after':>8s} {'no_words':>9s}"
    print(header)
    rows_out = [header]
    main_table_rows = []
    for name, _ in _MARKER_PATTERNS:
        gname = name
        if gname == "OTHER" or gname in WORD_LIKE or gname in NO_TIER:
            continue
        count = class_counts.get(gname, 0)
        nfiles = len(class_files.get(gname, ()))
        pos = class_positions.get(gname, Counter())
        tier = TIER.get(gname, "?")
        line = (
            f"{gname:20s} {tier:18s} {count:8d} {nfiles:6d} "
            f"{pos.get('before_first_word', 0):8d} {pos.get('between_words', 0):8d} "
            f"{pos.get('after_last_word', 0):8d} {pos.get('iu_has_no_words', 0):9d}"
        )
        print(line)
        rows_out.append(line)
        main_table_rows.append(
            {
                "class": gname,
                "tier": tier,
                "count": count,
                "files": nfiles,
                "before_first_word": pos.get("before_first_word", 0),
                "between_words": pos.get("between_words", 0),
                "after_last_word": pos.get("after_last_word", 0),
                "iu_has_no_words": pos.get("iu_has_no_words", 0),
            }
        )

    with open(reports_dir / "phase2_marker_inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "class", "tier", "count", "files",
                "before_first_word", "between_words", "after_last_word", "iu_has_no_words",
            ],
        )
        w.writeheader()
        w.writerows(main_table_rows)

    # --- patterns that fit no documented tier ------------------------
    print("\n=== Patterns fitting no tier (not assigned a tier; for revision) ===\n")
    rows_out.append("\n=== Patterns fitting no tier ===")

    no_tier_report = []
    for gname in ("DOUBLE_ANGLE_OPEN", "DOUBLE_ANGLE_CLOSE"):
        count = class_counts.get(gname, 0)
        nfiles = len(class_files.get(gname, ()))
        no_tier_report.append((gname, count, nfiles, gname.replace("_", " ").lower()))

    for ch, c in other_char_counts.most_common():
        no_tier_report.append((f"OTHER {ch!r} (U+{ord(ch):04X})", c, len(other_char_files[ch]), None))

    no_tier_csv_rows = []
    for label, count, nfiles, _ in no_tier_report:
        row = f"  {label}: count={count}, {nfiles} files"
        print(row)
        rows_out.append(row)
        no_tier_csv_rows.append({"pattern": label, "count": count, "files": nfiles})

    with open(reports_dir / "phase2_marker_no_tier.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["pattern", "count", "files"])
        w.writeheader()
        w.writerows(no_tier_csv_rows)

    print("\n--- file:line examples for double-angle tags ---")
    example_rows = []
    for gname, pat in [("DOUBLE_ANGLE_OPEN", r"<<[A-Za-z]+"), ("DOUBLE_ANGLE_CLOSE", r"[A-Za-z]+>>")]:
        for doc_id, line_no, line in raw_line_examples(pat):
            print(f"  {gname}  {doc_id}:{line_no}  {line}")
            example_rows.append({"pattern": gname, "file": doc_id, "line": line_no, "text": line})

    print("\n--- examples for each OTHER character (from actual classified occurrences) ---")
    for ch, c in other_char_counts.most_common():
        label = f"OTHER {ch!r} (U+{ord(ch):04X})"
        print(f"  {ch!r} (U+{ord(ch):04X}), count={c}:")
        for doc_id, iu_text in unmatched_context[ch]:
            line_no = find_line_number(doc_id, iu_text)
            loc = f"{doc_id}:{line_no}" if line_no else f"{doc_id} (merged/not found verbatim)"
            print(f"      {loc}  {iu_text!r}")
            example_rows.append(
                {"pattern": label, "file": doc_id, "line": line_no or "", "text": iu_text}
            )

    # Short illustrative quotations only (<=3 per pattern, per the licence
    # note in reports/phase2_data.md -- same category of use as the
    # existing reports/phase2_excluded_lines.csv).
    with open(reports_dir / "phase2_marker_no_tier_examples.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["pattern", "file", "line", "text"])
        w.writeheader()
        w.writerows(example_rows)

    print(f"\nIUs with zero words after word/X extraction: {n_ius_zero_words} of {n_ius}")

    with open(reports_dir / "phase2_marker_inventory.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(rows_out) + "\n")


if __name__ == "__main__":
    main()

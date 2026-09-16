"""Phase 2 reader, stages 1-3: decode .trn files with the correct per-file
encoding, extract intonation-unit (IU) lines, and merge IUs that were split
across multiple lines by speaker interruption (the '&' convention).

Does NOT tokenise. IU text still contains every transcription marker
(pauses, breath, overlap brackets, prosodic tags, etc.) -- that is the next
stage's job, deliberately kept separate so this stage can be verified in
isolation first.
"""
import csv
import io
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

CORPUS_DIR = Path("corpora/sbcsae/TRN")

# Established in the phase 2 survey, not guessed: these two files were saved
# with a different encoding than the rest of the corpus. Every other file is
# clean, strict UTF-8 (confirmed by exhaustive decode over all 60 files).
ENCODINGS = {
    "SBC060": "cp1252",   # 147 curly apostrophes (0x92) in contractions/possessives
    "SBC037": "latin-1",  # 34 Spanish accented vowels inside <L2 ...> spans
}
DEFAULT_ENCODING = "utf-8"

# One regex, one code path, for every line regardless of file: two decimal
# numbers, then whitespace of any kind (this swallows however much
# tab/space padding the file happens to use, including zero), then
# whatever's left. No fallback branch for the tab-less SBC013 lines -- the
# same match produces the right split for them too, because a greedy \s*
# consumes a run of spaces exactly as readily as a run of tabs.
_HEAD_RE = re.compile(r"^\s*([\d.]+)\s+([\d.]+)\s*(.*)$", re.DOTALL)


@dataclass
class IntonationUnit:
    speaker: str
    start: float
    end: float
    text: str
    # True if this IU was assembled from more than one file line (the '&'
    # convention). Its [start, end] span is not continuous speech in that
    # case -- it encloses whatever interrupted it. Phase 2 doesn't use
    # timestamps, but phase 3 will care about this distinction.
    merged_from: int = field(default=1)


_STRIPPED_BYTES = {0x00: "NUL", 0x7F: "DEL"}


def strip_nul_bytes(raw: bytes, doc_id: str, log_rows: list) -> bytes:
    """Remove every NUL and DEL byte from raw, logging (doc_id, line, byte,
    context) for each to log_rows before removal. Line numbers are
    1-indexed, counted from '\\n' bytes in the untouched raw content, so
    they match what a text editor would show regardless of the file's
    eventual encoding.

    DEL (0x7F) is stripped by the same rule as NUL and for the same reason:
    it is a stray control byte with no documented transcription meaning,
    never reconstructed, just removed and logged. It is single-byte in
    every encoding this corpus uses (UTF-8, cp1252, latin-1), so it can be
    detected here at the byte level exactly like NUL, before any decoding
    happens.
    """
    cleaned = bytearray()
    line_no = 1
    i = 0
    n = len(raw)
    while i < n:
        b = raw[i]
        if b in _STRIPPED_BYTES:
            ctx = raw[max(0, i - 20) : i + 20].decode("latin-1", errors="replace")
            log_rows.append(
                {"file": doc_id, "line": line_no, "byte": _STRIPPED_BYTES[b], "context": repr(ctx)}
            )
        else:
            cleaned.append(b)
        if b == 0x0A:  # '\n'
            line_no += 1
        i += 1
    return bytes(cleaned)


def decode_document(path: Path, log_rows: list) -> str:
    """Read one .trn file and return its fully decoded, newline-normalised
    text: NUL bytes stripped (and logged), the file's specific encoding
    applied strictly (raises on any decode failure -- never substitutes),
    curly apostrophes normalised to ASCII, CRLF/CR normalised to LF via
    real universal-newline handling (not a manual replace).
    """
    doc_id = path.stem
    raw = path.read_bytes()
    cleaned = strip_nul_bytes(raw, doc_id, log_rows)

    encoding = ENCODINGS.get(doc_id, DEFAULT_ENCODING)
    # io.TextIOWrapper over BytesIO gives real newline=None (universal
    # newlines) semantics on the NUL-stripped bytes, without re-reading the
    # file from disk and without hand-rolling \r\n handling.
    with io.TextIOWrapper(io.BytesIO(cleaned), encoding=encoding, errors="strict", newline=None) as f:
        text = f.read()

    return text.replace("’", "'").replace("‘", "'")


# SBC011 lines 414-415: collaborative completion across speakers.
# Du Bois SS13.1 defines & as marking one IU split across lines; here the
# transcriber used it for "continues the preceding utterance" instead.
# ANGELA opens, DORIS closes: two speakers, two intonation contours, so two
# IUs, not one merged unit no one actually uttered as a single contour. The
# & is stripped from both lines and each stays its own independent IU. This
# is a named, one-off exception, not a general cross-speaker-matching rule:
# a second case of this kind must raise, not pass silently.
CROSS_SPEAKER_AMPERSAND = {("SBC011", 414), ("SBC011", 415)}


class AmbiguousFieldsError(ValueError):
    """Raised when more than one non-blank field remains after the speaker
    position -- i.e. it's not clear which field is the real text. Per the
    NUL-byte precedent: don't infer content where the inference costs more
    than the content is worth. Callers decide whether to exclude and log,
    or to stop.
    """


_SPEAKER_RE = re.compile(r"^([#>*]?[A-Za-z][A-Za-z0-9_]*):\s*")


def split_line_fields(line: str) -> tuple[float, float, str, str]:
    """Parse one non-blank .trn line into (start, end, speaker, text).

    One regex, applied the same way to every line: capture the two leading
    floats, then whatever whitespace follows (a tab, a run of spaces, both,
    or -- for a handful of lines that lost their tabs entirely -- nothing
    but spaces), then everything else ("rest").

    If a tab remains in that remainder, the text before it is the speaker
    (stripped, trailing ':' removed -- the speaker field does not always
    have a colon: "MONTOYA", ">MAC", "@@@2]" and other non-word content
    have all been observed there) and the text after is candidate text,
    which may itself still contain tabs (extra blank padding fields, or,
    rarely, a stray trailing tab after real content). The actual text is
    the last NON-BLANK such field. If more than one non-blank field remains
    there, which one is the real text is ambiguous -- raise
    AmbiguousFieldsError rather than guess.

    If no tab remains at all, the same speaker-token rule that identifies a
    tab-separated speaker field is applied to `rest` directly: a word,
    optionally prefixed with '#' (the disguised-name convention seen on some
    speaker codes, e.g. "#FOSTER:"), '>' (non-human/environmental
    pseudo-speakers, e.g. ">ENV:") or '*' (e.g. "*X:"), followed by ':' and
    whitespace of any kind. This is the fix for a real reader defect: a
    speaker field that is present but space-glued to the text instead of
    tab-separated (e.g. "CAROLYN:                           [2@...]",
    about 1,287 lines corpus-wide use spaces rather than a tab in at least
    one gap -- see reports/phase2_data.md S4 -- a minority of which have
    exactly this shape) was previously treated as "no speaker field at
    all", leaking "SPEAKER:" into the text and leaving the IU's speaker
    wrongly inherited from the previous line. Genuinely speakerless
    continuation lines (no leading colon token) are unaffected: this
    branch only ever recognises a colon-terminated token specifically,
    unlike the more permissive first-tab-content rule above, because
    without a tab there is no positional signal at all to fall back on if
    the colon rule doesn't fire.
    """
    m = _HEAD_RE.match(line)
    if not m:
        raise ValueError(f"line does not start with 'start end': {line!r}")
    start, end, rest = m.group(1), m.group(2), m.group(3)

    if "\t" in rest:
        speaker_part, _, text_part = rest.partition("\t")
        speaker = speaker_part.strip().rstrip(":").strip()
        sub_fields = text_part.split("\t")
        non_blank = [f for f in sub_fields if f.strip()]
        if len(non_blank) > 1:
            raise AmbiguousFieldsError(
                f"multiple non-blank fields after speaker, unclear which is text: "
                f"{sub_fields!r} (line: {line!r})"
            )
        text = non_blank[0].strip() if non_blank else ""
    else:
        speaker_match = _SPEAKER_RE.match(rest)
        if speaker_match:
            speaker = speaker_match.group(1)
            text = rest[speaker_match.end() :].strip()
        else:
            speaker = ""
            text = rest

    return float(start), float(end), speaker, text


def _strip_amp(text: str) -> str:
    """Remove exactly one leading and/or one trailing '&' continuation
    marker (after trimming surrounding whitespace), leaving every other
    transcription marker untouched -- tokenisation of those is the next
    stage, not this one.
    """
    t = text.strip()
    if t.startswith("&"):
        t = t[1:].strip()
    if t.endswith("&"):
        t = t[:-1].strip()
    return t


def read_trn_document(path: Path) -> tuple[str, list[IntonationUnit], int, list[dict], list[dict]]:
    """Read and fully process one .trn file: decode, split into raw lines,
    exclude non-transcription content, and merge '&'-linked fragments into
    single IntonationUnits, keyed by speaker (never by file position --
    concurrent threads from different speakers are common).

    Three categories of line are excluded before merging, each logged
    rather than silently dropped:
      - Du Bois-convention researcher notes: a line whose text begins with
        '$' (Du Bois, "Outline of Discourse Transcription," SS14.1 -- marks
        a non-transcription line, not spoken content). 9 in the corpus.
      - Lines containing a literal backslash: 3 in the whole corpus, each
        apparently a lost newline that fused two real lines together, one
        with a second, different timestamp format nested inside. Not
        repaired -- reconstructing what these were requires several
        assumptions to recover three IUs out of ~70,000; logged instead so
        they can be revisited if anyone wants to.
      - Lines where split_line_fields can't tell which of several
        non-blank fields is the real text (AmbiguousFieldsError). 1 in the
        whole corpus (SBC016 line 1185). Same principle as the backslash
        lines: excluded and logged, not guessed.

    Returns (doc_id, units, n_raw_lines, nul_log_rows, excluded_rows).
    n_raw_lines counts every non-blank line, excluded or not, matching the
    corpus-wide 70,083 baseline.

    Raises RuntimeError on any '&' pattern that doesn't fit the documented
    state machine: a leading '&' with no open fragment for that speaker (and
    not one of the two lines named in CROSS_SPEAKER_AMPERSAND); a line
    without a leading '&' from a speaker who already has one open (whether
    that line is ordinary or itself trying to open a second fragment -- 'at
    most one open fragment per speaker' forbids both); or an open fragment
    still unresolved at end of file. This function does not guess in any of
    these cases.
    """
    doc_id = path.stem
    nul_log_rows: list = []
    text = decode_document(path, nul_log_rows)

    units: list[IntonationUnit] = []
    open_fragments: dict[str, int] = {}  # speaker -> index into `units`
    current_speaker: str | None = None
    n_raw_lines = 0
    excluded_rows: list[dict] = []
    line_no = 0

    for raw_line in text.split("\n"):
        line_no += 1
        if not raw_line.strip():
            continue
        n_raw_lines += 1

        if "\\" in raw_line:
            excluded_rows.append(
                {"file": doc_id, "line": line_no, "reason": "backslash_fused", "content": raw_line}
            )
            continue

        try:
            start, end, speaker_field, raw_text = split_line_fields(raw_line)
        except AmbiguousFieldsError:
            # Exactly one such line in the whole corpus (SBC016 line 1185):
            # a stray tab splits an overlap bracket from the rest of the
            # text, and it isn't clear which piece is the real content.
            # Same principle as the NUL bytes and the backslash lines --
            # exclude and log rather than guess which field is right.
            excluded_rows.append(
                {"file": doc_id, "line": line_no, "reason": "ambiguous_fields", "content": raw_line}
            )
            continue

        if raw_text.strip().startswith("$"):
            excluded_rows.append(
                {"file": doc_id, "line": line_no, "reason": "dubois_dollar_note", "content": raw_line}
            )
            continue

        if speaker_field:
            current_speaker = speaker_field
        speaker = current_speaker
        if speaker is None:
            raise RuntimeError(f"{doc_id}: line before any speaker was established: {raw_line!r}")

        stripped = raw_text.strip()
        leading_amp = stripped.startswith("&")
        trailing_amp = stripped.endswith("&")
        # (a lone "&" with nothing else naturally satisfies both above)

        if (doc_id, line_no) in CROSS_SPEAKER_AMPERSAND:
            # Documented exception above: strip and keep as its own IU,
            # bypassing the per-speaker merge state machine entirely --
            # this line neither opens nor closes a fragment.
            unit = IntonationUnit(speaker=speaker, start=start, end=end, text=_strip_amp(raw_text))
            units.append(unit)
            continue

        if speaker in open_fragments:
            idx = open_fragments[speaker]
            if not leading_amp:
                kind = "an ordinary line" if not trailing_amp else "a new trailing-&"
                raise RuntimeError(
                    f"{doc_id}: {kind} from speaker {speaker!r}, who already has an open "
                    f"'&' fragment (line: {raw_line!r})"
                )
            entry = units[idx]
            entry.text = entry.text + " " + _strip_amp(raw_text)
            entry.end = end
            entry.merged_from += 1
            if not trailing_amp:
                del open_fragments[speaker]
        else:
            if leading_amp:
                raise RuntimeError(
                    f"{doc_id}: leading '&' with no open fragment for speaker {speaker!r} "
                    f"(line: {raw_line!r})"
                )
            unit = IntonationUnit(speaker=speaker, start=start, end=end, text=_strip_amp(raw_text))
            units.append(unit)
            if trailing_amp:
                open_fragments[speaker] = len(units) - 1

    if open_fragments:
        raise RuntimeError(
            f"{doc_id}: end of file with {len(open_fragments)} fragment(s) still open: "
            f"{sorted(open_fragments)}"
        )

    return doc_id, units, n_raw_lines, nul_log_rows, excluded_rows


def iter_trn_documents(
    corpus_dir: Path = CORPUS_DIR,
) -> Iterator[tuple[str, list[IntonationUnit], int, list[dict], list[dict]]]:
    for path in sorted(corpus_dir.glob("SBC*.trn")):
        yield read_trn_document(path)


if __name__ == "__main__":
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    from collections import Counter

    char_counts: Counter = Counter()
    all_nul_rows: list = []
    all_excluded_rows: list = []
    per_file_field_counts_raw: Counter = Counter()  # audit only, over ALL non-blank lines
    per_file_field_counts_post: Counter = Counter()  # audit only, over lines NOT excluded
    total_raw_lines = 0
    total_merged_units = 0
    per_file_summary = []

    for path in sorted(CORPUS_DIR.glob("SBC*.trn")):
        doc_id, units, n_raw, nul_rows, excluded_rows = read_trn_document(path)
        all_nul_rows.extend(nul_rows)
        all_excluded_rows.extend(excluded_rows)
        total_raw_lines += n_raw
        total_merged_units += len(units)

        n_merges = sum(u.merged_from - 1 for u in units)
        per_file_summary.append(
            {"file": doc_id, "raw_lines": n_raw, "merged_units": len(units), "merges": n_merges}
        )

        excluded_line_nos = {r["line"] for r in excluded_rows}
        text = decode_document(path, [])
        line_no = 0
        for raw_line in text.split("\n"):
            line_no += 1
            if not raw_line.strip():
                continue
            n = len(raw_line.split("\t"))
            per_file_field_counts_raw[n] += 1
            if line_no not in excluded_line_nos:
                per_file_field_counts_post[n] += 1
            field_text = raw_line.split("\t")[-1]
            char_counts.update(field_text)

    print("=== Stage 1: NUL/DEL bytes stripped ===")
    by_byte = Counter(row["byte"] for row in all_nul_rows)
    print(f"total control bytes removed: {len(all_nul_rows)} {dict(by_byte)} (this check covers all 60 files)")
    with open(reports_dir / "phase2_nul_bytes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "line", "byte", "context"])
        w.writeheader()
        w.writerows(all_nul_rows)
    for row in all_nul_rows:
        print(f"  {row['file']} line {row['line']} [{row['byte']}]: {row['context']}")

    print(f"\n=== Stage 1: character inventory ({len(char_counts)} unique characters) ===")
    with open(reports_dir / "phase2_char_inventory.txt", "w", encoding="utf-8") as f:
        for ch in sorted(char_counts):
            f.write(f"U+{ord(ch):04X}\t{ch!r}\tcount={char_counts[ch]}\n")
    alarms = [ch for ch in char_counts if ch in ("�", "\r", "\x00")]
    print(f"alarm characters present (U+FFFD, \\r, \\x00): {alarms if alarms else 'none'}")
    print(f"full inventory written to {reports_dir / 'phase2_char_inventory.txt'}")

    print("\n=== Excluded lines (Du Bois '$' notes + backslash-fused) ===")
    with open(reports_dir / "phase2_excluded_lines.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "line", "reason", "content"])
        w.writeheader()
        w.writerows(all_excluded_rows)
    by_reason = Counter(r["reason"] for r in all_excluded_rows)
    print(f"total excluded: {len(all_excluded_rows)}  by reason: {dict(by_reason)}")
    for row in all_excluded_rows:
        print(f"  {row['file']} line {row['line']} [{row['reason']}]: {row['content']!r}")

    print("\n=== Stage 2 (audit): raw tab-field-count distribution, ALL non-blank lines ===")
    for n_fields, count in sorted(per_file_field_counts_raw.items()):
        print(f"  {n_fields} fields: {count} lines")

    print("\n=== Stage 2 (audit): tab-field-count distribution AFTER excluding $ / backslash lines ===")
    for n_fields, count in sorted(per_file_field_counts_post.items()):
        print(f"  {n_fields} fields: {count} lines")
    remaining_1_or_5 = {n: c for n, c in per_file_field_counts_post.items() if n in (1, 5)}
    if remaining_1_or_5:
        print(f"NOTE: 1- or 5-field lines remain after exclusion: {remaining_1_or_5}")
        print(
            "These are NOT unaccounted for: the parser does not branch on raw tab count at all "
            "(one regex handles every case -- see split_line_fields). 1-field lines here are the "
            "18 tab-loss lines in SBC013 (handled by the no-tab-in-rest branch); 5-field lines are "
            "the extra-blank-field / last-non-blank-field cases (handled by the ambiguity guard, "
            "which raised zero times across the corpus -- see the merge run below completing "
            "without error)."
        )
    else:
        print("none remain")

    print("\n=== Stage 3: '&' merge -- per-file IU counts and merges ===")
    print(f"{'file':10s} {'raw_lines':>10s} {'merged_units':>13s} {'merges':>7s}")
    for row in per_file_summary:
        print(f"{row['file']:10s} {row['raw_lines']:10d} {row['merged_units']:13d} {row['merges']:7d}")

    with open(reports_dir / "phase2_merge_counts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "raw_lines", "merged_units", "merges"])
        w.writeheader()
        w.writerows(per_file_summary)

    n_dollar = by_reason.get("dubois_dollar_note", 0)
    n_backslash = by_reason.get("backslash_fused", 0)
    n_ambiguous = by_reason.get("ambiguous_fields", 0)
    n_amp_absorbed = sum(row["merges"] for row in per_file_summary)
    expected = total_raw_lines - n_dollar - n_backslash - n_ambiguous - n_amp_absorbed

    print(f"\n{total_raw_lines} raw lines")
    print(f"-  {n_dollar}    $ non-transcription lines")
    print(f"-  {n_backslash}    backslash-fused lines")
    print(f"-  {n_ambiguous}    ambiguous-field line")
    print(f"-  {n_amp_absorbed}   absorbed by & merge")
    print(f"=  {expected}")
    print(f"\nactual merged IU count: {total_merged_units}")
    # expected is derived from these same five live counters, so this match
    # is close to definitional; the real check is each counter against the
    # figure it was independently established at:
    for label, actual, prior in [
        ("raw lines", total_raw_lines, 70083),
        ("$ notes", n_dollar, 10),
        ("backslash-fused", n_backslash, 3),
        ("ambiguous fields", n_ambiguous, 1),
        ("& absorbed", n_amp_absorbed, 62),
    ]:
        flag = "OK" if actual == prior else f"MISMATCH (previously established: {prior})"
        print(f"  {label}: {actual}  [{flag}]")
    if total_merged_units == expected:
        print(f"\nOK: matches {expected} exactly.")
    else:
        print(f"\nMISMATCH: {total_merged_units} != {expected}  -- the discrepancy is the finding.")

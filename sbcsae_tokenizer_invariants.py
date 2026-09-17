"""Phase 2 stage 4, closing step 2 (word-level invariants).

The independent word-COUNT cross-check (sbcsae_tokenizer_crosscheck.py)
attributes any per-IU count mismatch to ANY delimiter present anywhere in
the IU -- so a genuine word-boundary error in an IU that also happens to
contain, say, an overlap bracket passes as "explained" even though the
bracket has nothing to do with the actual error. These three checks work
at the level of individual words and raw-text chunks instead, and share
no code with sbcsae_tokenizer.py (no imported regex, no reused helper --
an independent reimplementation, checked against the tokeniser's output,
not against its internals):

  a) No fusion across whitespace: every emitted word's letters must occur
     contiguously within a single whitespace-delimited raw chunk.
  b) No lost words: every raw chunk's lowercase letters, outside a
     ((...)) research comment or a /.../ phonetic gloss, must occur
     (contiguously) in some emitted word.
  c) Capitalised material: every distinct all-caps chunk, tallied
     corpus-wide as kept (appears as an emitted word) vs removed (does
     not) -- a spot check that real short words (I, OK, TV, ...) are
     never silently dropped and that only tag/vocal-noise/comment names
     are.

This is diagnostic only. Per the brief, it fixes nothing -- any violation
is reported, not corrected here. The category heuristics below (for b)
are for the terminal breakdown only, not used to decide anything.
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from sbcsae_marker_inventory import find_line_number
from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import TokenizeError, tokenize, words_only

_WORD_CHAR = re.compile(r"\S+")
# Not just a run of uppercase ASCII letters -- must not be glued to a
# lowercase letter on either side, or an ordinary mixed-case word's
# capitalised piece (sentence-initial "He", the "V" in "InterVarsity")
# would register as its own spurious "all-caps chunk."
_ALLCAPS_RUN = re.compile(r"(?<![a-z])[A-Z]+(?![a-z])")
_COMMENT_SPAN = re.compile(r"\(\([^()]*\)\)")
_GLOSS_SPAN = re.compile(r"/[^/]*/")


def _letters(s: str) -> str:
    return "".join(c for c in s if c.isalpha())


def whitespace_chunks(text: str) -> list[tuple[int, int, str]]:
    """(start, end, chunk_text) for every maximal non-whitespace run."""
    return [(m.start(), m.end(), m.group()) for m in _WORD_CHAR.finditer(text)]


def check_no_fusion_across_whitespace(text: str, tok_words: list[str]) -> list[str]:
    """(a). Every emitted word's letters must be a contiguous substring
    of SOME single whitespace-delimited chunk's own letters (deleting
    non-letters from that chunk first). Returns the offending word texts.
    """
    chunks = whitespace_chunks(text)
    chunk_letter_strs = [_letters(c) for _, _, c in chunks]
    violations = []
    for w in tok_words:
        wl = _letters(w)
        if not wl:
            continue
        if not any(wl in cl for cl in chunk_letter_strs):
            violations.append(w)
    return violations


def _excluded_mask(text: str) -> list[bool]:
    mask = [False] * len(text)
    for pat in (_COMMENT_SPAN, _GLOSS_SPAN):
        for m in pat.finditer(text):
            for i in range(m.start(), m.end()):
                mask[i] = True
    return mask


def check_no_lost_words(text: str, tok_words: list[str]) -> list[tuple[str, str]]:
    """(b). Every raw chunk's own lowercase letters (outside a ((...))
    or /.../ span) must be a contiguous substring of SOME single emitted
    word's letters. Returns (chunk_text, required_letters) for failures.
    """
    mask = _excluded_mask(text)
    word_letter_strs = [_letters(w) for w in tok_words]
    violations = []
    for start, _end, chunk in whitespace_chunks(text):
        required = "".join(
            ch for i, ch in enumerate(chunk, start=start)
            if ch.isalpha() and ch.islower() and not mask[i]
        )
        if not required:
            continue
        if not any(required in wl for wl in word_letter_strs):
            violations.append((chunk, required))
    return violations


def allcaps_chunks(text: str) -> list[str]:
    """(c) building block: every maximal run of uppercase ASCII letters,
    naturally stripped of surrounding delimiters (parens/brackets/angle
    tags/etc. are never part of an [A-Z]+ match).
    """
    return _ALLCAPS_RUN.findall(text)


# --- (b) categorisation, terminal reporting only, decides nothing -------
_HYPHEN_ONLY = re.compile(r"^-+$")
_DOUBLED_CUE = re.compile(r"[=^`!;%\\]{2,}")


def _is_doubled_cue_split(chunk: str) -> bool:
    """True only if a run of 2+ glued cue marks sits BETWEEN letters on
    both sides within the chunk (a trailing "==" after already-dropped/
    cue material with nothing left to fuse, e.g. "[@(Hx)]==", is not
    this -- there is no word on the far side for it to have split).
    """
    m = _DOUBLED_CUE.search(chunk)
    if not m:
        return False
    return any(c.isalpha() for c in chunk[: m.start()]) and any(c.isalpha() for c in chunk[m.end() :])
# Real words with an internal capital that a lowercase-only "required"
# extraction fragments at (McNuggets, Wal-Mart, InterVarsity, ...): the
# word is tokenised correctly, this check just can't see across the
# capital letter it deliberately ignores. Detected, not guessed: true
# only when the FULL chunk (case preserved, delimiters stripped) is a
# contiguous substring of some single emitted word.
def _is_internal_capital_false_positive(chunk: str, tok_words: list[str]) -> bool:
    chunk_letters = _letters(chunk)
    return any(chunk_letters and chunk_letters in w.replace("-", "").replace("'", "") for w in tok_words)


def _is_legitimate_multiword_split(chunk: str, required: str, tok_words: list[str]) -> bool:
    """True if the chunk's required letters are only missing from any
    SINGLE emitted word because the tokeniser correctly split the chunk
    into two or more separate words at a documented boundary -- a comma/
    period/qmark ("that,a" -> "that", "a"), or a displaced-truncation
    hyphen that always flushes ("Ya=-ha" -> "Ya-", "ha"). Checked by
    concatenating every emitted word's own letters, in emission order,
    and looking for `required` there -- not by assuming which specific
    rule caused the split.
    """
    all_words_letters = "".join(_letters(w) for w in tok_words)
    return required in all_words_letters


def _category(chunk: str, required: str, tok_words: list[str]) -> str:
    if _HYPHEN_ONLY.match(chunk):
        return "hyphen_only_chunk (Boundary, not lost)"
    if _is_doubled_cue_split(chunk):
        return "doubled_cue_fusion (silent mis-split, real bug, not attributable)"
    if "(" in chunk or ")" in chunk:
        return "parenthetical_marker (breath/vocal-noise name)"
    if "[" in chunk or "]" in chunk:
        return "overlap_bracket"
    if "<" in chunk or ">" in chunk:
        return "angle_tag"
    if "_" in chunk:
        return "underscore_truncation_or_gloss"
    if re.search(r"[~#*]", chunk):
        return "disguise_prefix"
    # Checked before the bare "+" check: the float artifact's own "+00"
    # contains a literal "+", which would otherwise mislabel these as
    # plus_fusion -- documented behaviour is to strip and never
    # reconstruct (CLAUDE.md), so the lost initial letter is expected,
    # not a bug.
    if re.search(r"0(?:\.000000(?:[eE]\+00)?)?[a-z-]", chunk):
        return "lost_initial_letter (documented: stripped, never reconstructed)"
    if "+" in chunk:
        return "plus_fusion"
    if "@" in chunk:
        return "at_sign_fusion"
    if _is_internal_capital_false_positive(chunk, tok_words):
        return "internal_capital_in_kept_word (McNuggets/Wal-Mart-shaped, not lost)"
    if _is_legitimate_multiword_split(chunk, required, tok_words):
        return "boundary_or_multiword_split (Boundary/displaced-truncation flush, not lost)"
    return "other"


def main():
    n_ius = 0
    a_violations = []  # (doc_id, line, text, word)
    b_violations = []  # (doc_id, line, text, chunk, required)
    b_by_category = Counter()
    caps_tally = defaultdict(lambda: {"kept": 0, "removed": 0})

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id == "SBC037":
            continue
        for u in units:
            n_ius += 1
            text = u.text
            try:
                items = tokenize(text)
            except TokenizeError:
                continue  # none currently raise
            tok_words = [w.text for w in words_only(items)]
            line = find_line_number(doc_id, text) or ""

            for w in check_no_fusion_across_whitespace(text, tok_words):
                a_violations.append((doc_id, line, text, w))

            for chunk, required in check_no_lost_words(text, tok_words):
                cat = _category(chunk, required, tok_words)
                b_violations.append((doc_id, line, text, chunk, required, cat))
                b_by_category[cat] += 1

            raw_caps = Counter(allcaps_chunks(text))
            for value, raw_n in raw_caps.items():
                # "Kept" means the chunk's letters actually survive into
                # some emitted word -- checked the same way as (a)/(b), by
                # substring containment, not by requiring the whole word
                # to be nothing but this value (which would wrongly count
                # "I" inside the emitted word "I'm" as "removed").
                kept_n = min(raw_n, sum(1 for w in tok_words if value in w))
                caps_tally[value]["kept"] += kept_n
                caps_tally[value]["removed"] += raw_n - kept_n

    print(f"=== Word-level invariants over {n_ius} IUs (59 files, excl. SBC037) ===\n")

    print(f"--- (a) No fusion across whitespace: {len(a_violations)} violations ---")
    for doc_id, line, text, w in a_violations[:10]:
        print(f"  {doc_id}:{line}  word={w!r}")
        print(f"    raw={text!r}")

    print(f"\n--- (b) No lost words: {len(b_violations)} violations ---")
    print("  by category:")
    for cat, c in b_by_category.most_common():
        print(f"    {cat}: {c}")
    print("\n  10 raw examples per category (terminal only):")
    shown = defaultdict(int)
    for doc_id, line, text, chunk, required, cat in b_violations:
        if shown[cat] >= 10:
            continue
        shown[cat] += 1
        print(f"    [{cat}] {doc_id}:{line}  chunk={chunk!r} required={required!r}")
        print(f"      raw={text!r}")

    print(f"\n--- (c) Capitalised material: {len(caps_tally)} distinct all-caps chunks ---")
    print("  sorted by total occurrences, descending:")
    for value, counts in sorted(caps_tally.items(), key=lambda kv: -(kv[1]["kept"] + kv[1]["removed"]))[:40]:
        total = counts["kept"] + counts["removed"]
        print(f"    {value!r}: kept={counts['kept']} removed={counts['removed']} (total {total})")

    spot_check = ["I", "OK", "TV"]
    print("\n  spot check (real words that must never be silently removed):")
    for value in spot_check:
        counts = caps_tally.get(value)
        if counts is None:
            print(f"    {value!r}: does not occur in the corpus")
        else:
            print(f"    {value!r}: kept={counts['kept']} removed={counts['removed']}")

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    with open(reports_dir / "phase2_tokenizer_invariants_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check", "category", "count"])
        w.writeheader()
        w.writerow({"check": "a_no_fusion_across_whitespace", "category": "violation", "count": len(a_violations)})
        for cat, c in b_by_category.most_common():
            w.writerow({"check": "b_no_lost_words", "category": cat, "count": c})

    with open(reports_dir / "phase2_tokenizer_capitalised_tally.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["value", "kept", "removed"])
        w.writeheader()
        for value, counts in sorted(caps_tally.items()):
            w.writerow({"value": value, "kept": counts["kept"], "removed": counts["removed"]})

    private_dir = Path("reports/private")
    private_dir.mkdir(parents=True, exist_ok=True)
    with open(private_dir / "phase2_tokenizer_invariants_a_full.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "line", "text", "word"])
        w.writeheader()
        for doc_id, line, text, word in a_violations:
            w.writerow({"file": doc_id, "line": line, "text": text, "word": word})
    with open(private_dir / "phase2_tokenizer_invariants_b_full.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "line", "text", "chunk", "required", "category"])
        w.writeheader()
        for doc_id, line, text, chunk, required, cat in b_violations:
            w.writerow(
                {
                    "file": doc_id,
                    "line": line,
                    "text": text,
                    "chunk": chunk,
                    "required": required,
                    "category": cat,
                }
            )


if __name__ == "__main__":
    main()

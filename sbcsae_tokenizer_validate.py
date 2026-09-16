"""Phase 2 stage 4: whole-corpus tokeniser validation.

Runs the tokeniser over every IU produced by the settled reader (SBC037
excluded throughout) and reports, without deciding what to do about any of
it:
  - number of raises, broken down by the offending character/pattern
  - number of IUs with zero words after tokenisation, broken down by an
    8-category composition breakdown and by file
  - segment counts per file before/after dropping zero-word IUs from the
    reference (reference_segments())
  - distribution of words per IU
  - result of the A/B word-identity assertion (trivially guaranteed by
    construction here -- there is one tokenize(), not separate A/B passes
    -- see the docstring note this prints)

This is now the single authoritative source for the zero-word-IU
composition breakdown, superseding two separate, disagreeing 4-category /
8-category classifiers from earlier in this stage (see reports/
phase2_tokeniser.md S4 for the reconciliation).
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import TokenizeError, tokenize, words_only

_LEADING_SYMBOL_RE = re.compile(r"unrecognised symbol U\+([0-9A-Fa-f]+)")

_LAUGHTER_ONLY = re.compile(r"^[\s@]+$")
_BREATH_ONLY = re.compile(r"^(?:\s*\(Hx?\)\s*)+$")
_PAUSE_ONLY = re.compile(r"^(?:\s*\.{2,3}(?:\(\d+(?:\.\d+)?\))?\s*)+$")
_VOCAL_NOISE_ONLY = re.compile(r"^(?:\s*\([A-Z][A-Z0-9_., ]*\)\s*)+$")
_COMMENT_ONLY = re.compile(r"^(?:\s*\(\([^()]*\)\)\s*)+$")


def _zero_word_category(text: str) -> str:
    stripped = text.strip()
    if stripped == "":
        return "raw_empty"
    if _LAUGHTER_ONLY.match(stripped):
        return "laughter_only"
    if _BREATH_ONLY.match(stripped):
        return "breath_only"
    if _PAUSE_ONLY.match(stripped):
        return "pause_only"
    if _VOCAL_NOISE_ONLY.match(stripped):
        return "vocal_noise_only"
    if _COMMENT_ONLY.match(stripped):
        return "comment_only"
    if "[" in stripped or "]" in stripped:
        return "nonwords_in_overlap_brackets"
    return "other"


def main():
    n_ius = 0
    n_raised = 0
    raise_by_char = Counter()
    raise_by_file = defaultdict(set)
    n_zero_word = 0
    zero_word_by_file = Counter()
    zero_word_composition = Counter()
    per_file_tokenised = Counter()  # segments "before" dropping zero-word IUs
    per_file_reference = Counter()  # segments "after" (reference_segments())
    words_per_iu = Counter()
    n_ab_mismatch = 0  # see note below: structurally impossible here

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id == "SBC037":
            continue
        for u in units:
            n_ius += 1
            try:
                items = tokenize(u.text)
            except TokenizeError as e:
                n_raised += 1
                m = _LEADING_SYMBOL_RE.search(str(e))
                key = chr(int(m.group(1), 16)) if m else "<unparsed>"
                raise_by_char[key] += 1
                raise_by_file[key].add(doc_id)
                continue

            words = words_only(items)
            n = len(words)
            words_per_iu[n] += 1
            per_file_tokenised[doc_id] += 1
            if n == 0:
                n_zero_word += 1
                zero_word_by_file[doc_id] += 1
                zero_word_composition[_zero_word_category(u.text)] += 1
            else:
                per_file_reference[doc_id] += 1

            # A/B word-identity check: tokenize() builds one Word/Cue
            # sequence; Condition only affects render()'s treatment of
            # cues, never which items are Words or their text/order. So A
            # and B words are the same list by construction here -- there
            # is no separate code path that could diverge. Recorded anyway,
            # per the task; see the printed note below.
            if [w.text for w in words] != [w.text for w in words_only(items)]:
                n_ab_mismatch += 1

    print(f"=== Tokeniser validation over {n_ius} IUs (59 files, excl. SBC037) ===\n")

    print(f"--- Raises: {n_raised} of {n_ius} ({100 * n_raised / n_ius:.2f}%) ---")
    for ch, c in raise_by_char.most_common():
        print(f"  {ch!r}: {c} IUs, {len(raise_by_file[ch])} files")

    print(f"\n--- Zero-word IUs (of the {n_ius - n_raised} that tokenised): "
          f"{n_zero_word} ---")
    print("  by composition:")
    for kind, c in zero_word_composition.most_common():
        print(f"    {kind}: {c} ({100*c/n_zero_word:.1f}% of zero-word)")
    print(f"  by file (top 15): {sorted(zero_word_by_file.items(), key=lambda kv: -kv[1])[:15]}")
    print(f"  files with at least one zero-word IU: {len(zero_word_by_file)}")

    print("\n--- Reference segments per file: before/after dropping zero-word IUs ---")
    print(f"  total before: {sum(per_file_tokenised.values())}  total after: {sum(per_file_reference.values())}")

    print(f"\n--- Words per IU distribution (of the {n_ius - n_raised} that tokenised) ---")
    for n in sorted(words_per_iu)[:15]:
        print(f"  {n} words: {words_per_iu[n]} IUs")
    if len(words_per_iu) > 15:
        remaining = sum(c for n, c in words_per_iu.items() if n >= 15)
        print(f"  15+ words: {remaining} IUs (max {max(words_per_iu)})")
    total_tokenised = n_ius - n_raised
    total_words = sum(n * c for n, c in words_per_iu.items())
    print(f"  mean words/IU: {total_words / total_tokenised:.2f}")

    print(f"\n--- A/B word-sequence identity mismatches: {n_ab_mismatch} "
          f"(structurally impossible given tokenize()'s single-pass design; "
          f"see module docstring) ---")

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    with open(reports_dir / "phase2_tokenizer_raises.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["char", "codepoint", "count", "files"])
        w.writeheader()
        for ch, c in raise_by_char.most_common():
            w.writerow(
                {
                    "char": ch,
                    "codepoint": f"U+{ord(ch):04X}" if ch != "<unparsed>" else "",
                    "count": c,
                    "files": len(raise_by_file[ch]),
                }
            )

    with open(
        reports_dir / "phase2_tokenizer_zero_word_composition.csv", "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(f, fieldnames=["composition", "count"])
        w.writeheader()
        for kind, c in zero_word_composition.most_common():
            w.writerow({"composition": kind, "count": c})

    with open(
        reports_dir / "phase2_tokenizer_zero_word_by_file.csv", "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(f, fieldnames=["file", "zero_word_ius"])
        w.writeheader()
        for doc_id, c in sorted(zero_word_by_file.items(), key=lambda kv: (-kv[1], kv[0])):
            w.writerow({"file": doc_id, "zero_word_ius": c})

    with open(
        reports_dir / "phase2_reference_segments_by_file.csv", "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(f, fieldnames=["file", "segments_before", "segments_after", "dropped"])
        w.writeheader()
        for doc_id in sorted(per_file_tokenised):
            before = per_file_tokenised[doc_id]
            after = per_file_reference[doc_id]
            w.writerow(
                {"file": doc_id, "segments_before": before, "segments_after": after, "dropped": before - after}
            )

    with open(reports_dir / "phase2_tokenizer_words_per_iu.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["n_words", "n_ius"])
        w.writeheader()
        for n in sorted(words_per_iu):
            w.writerow({"n_words": n, "n_ius": words_per_iu[n]})

    with open(reports_dir / "phase2_tokenizer_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["metric", "value"])
        w.writeheader()
        for metric, value in [
            ("n_ius", n_ius),
            ("n_raised", n_raised),
            ("raise_rate", round(n_raised / n_ius, 4)),
            ("n_tokenised", total_tokenised),
            ("n_zero_word_ius", n_zero_word),
            ("files_with_zero_word_ius", len(zero_word_by_file)),
            ("mean_words_per_iu", round(total_words / total_tokenised, 4)),
            ("max_words_per_iu", max(words_per_iu)),
            ("n_ab_mismatches", n_ab_mismatch),
        ]:
            w.writerow({"metric": metric, "value": value})


if __name__ == "__main__":
    main()

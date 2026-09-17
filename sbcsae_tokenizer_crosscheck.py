"""Phase 2 stage 4, closing step 2: an independent word-count cross-check.

The bracket-hyphen bug (reports/phase2_tokeniser.md S10.2b) produced wrong
word boundaries -- "third-graders" split into "third-" and "graders" -- with
no raise at all. Raise-on-unknown-symbol only catches a symbol that fits no
rule; it says nothing about whether a rule that DID fire produced the right
split. This script checks that separately, over the whole corpus, with a
method that shares no code with sbcsae_tokenizer.py: per IU, strip every
character except letters, apostrophes, hyphens and whitespace, collapse
whitespace, and count the resulting runs. Compare that count against the
tokeniser's own word count for the same IU.

This is a diagnostic only. Per the task, it fixes nothing -- any mismatch is
reported, not corrected here.
"""
import csv
import re
from collections import Counter
from pathlib import Path

from sbcsae_marker_inventory import find_line_number
from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import tokenize, words_only

# Deliberately not reusing any regex or helper from sbcsae_tokenizer.py --
# this is meant to be a second, independent opinion, not the same logic
# run twice. "Letter" is decided character-by-character via str.isalpha()
# (Unicode-aware, so it doesn't need its own separate class), not by
# importing the tokeniser's own word pattern.
_KEEP = "'-"


def independent_word_runs(text: str) -> list[str]:
    kept = []
    for ch in text:
        if ch.isalpha() or ch in _KEEP or ch.isspace():
            kept.append(ch)
        else:
            kept.append(" ")
    return "".join(kept).split()


_HYPHEN_ONLY_RUN = re.compile(r"^-+$")
_FUSABLE_MARK_MIDWORD = re.compile(r"[A-Za-z'][=^`!;%\\][A-Za-z']")


def _category(text: str, tok_words: list[str], indep_runs: list[str]) -> str:
    """Best-effort attribution to a documented rule, for the terminal
    breakdown only -- not used to decide anything. Ordered so the most
    specific, most mechanical explanation for the *naive* method's own
    blind spots is tried first (a fusable cue mark splits a run the naive
    method can't rejoin; a hyphen-only run is a boundary annotation the
    naive method counts as a word; parenthesised letters -- a breath or
    vocal-noise name -- are real letters the naive method has no way to
    know are dropped) before falling back to the coarser bracket/tag
    checks and finally "other" for anything none of these explain.
    """
    if any(_HYPHEN_ONLY_RUN.match(r) for r in indep_runs):
        return "hyphen_only_run (-- / --- / isolated -, a Boundary, not a Word)"
    if _FUSABLE_MARK_MIDWORD.search(text):
        return "cue_fusion (=^`!;%\\ mid-word, tokeniser fuses, naive method splits)"
    if "(" in text or ")" in text:
        return "parenthetical_marker (breath/vocal-noise/research-comment letters)"
    if "_" in text:
        return "underscore_truncation_or_gloss"
    if re.search(r"/[^/]*/", text):
        return "phonetic_gloss"
    if re.search(r"0(?:\.000000(?:[eE]\+00)?)?[a-z-]", text):
        return "lost_initial_letter"
    if re.search(r"\[\d+|\d+\]", text):
        return "numbered_overlap_bracket"
    if "[" in text or "]" in text:
        return "overlap_bracket"
    if "<" in text or ">" in text:
        return "angle_tag"
    if re.search(r"[~#*]", text):
        return "disguise_prefix"
    if "+" in text:
        return "plus_fusion (tier-1 drop mark mid-word, S8.1c)"
    if "@" in text:
        return "at_sign_fusion (tier-1 drop mark mid-word or standalone laughter)"
    return "other"


def main():
    n_ius = 0
    n_match = 0
    diff_counts = Counter()  # tok_count - indep_count -> n IUs
    category_counts = Counter()
    examples = {}  # category -> list of (file, line, text, tok, indep)
    mismatch_log = []

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id == "SBC037":
            continue
        for u in units:
            n_ius += 1
            text = u.text
            try:
                items = tokenize(text)
            except Exception:
                continue  # none currently raise; skip defensively
            tok_words = [w.text for w in words_only(items)]
            indep_runs = independent_word_runs(text)

            tok_n = len(tok_words)
            indep_n = len(indep_runs)
            diff = tok_n - indep_n

            if diff == 0:
                n_match += 1
                continue

            diff_counts[diff] += 1
            cat = _category(text, tok_words, indep_runs)
            category_counts[cat] += 1
            line = find_line_number(doc_id, text) or ""
            mismatch_log.append(
                {
                    "file": doc_id,
                    "line": line,
                    "diff": diff,
                    "tok_n": tok_n,
                    "indep_n": indep_n,
                    "category": cat,
                    "text": text,
                    "tok_words": tok_words,
                    "indep_runs": indep_runs,
                }
            )
            examples.setdefault(cat, []).append(
                (doc_id, line, text, tok_words, indep_runs)
            )

    print(f"=== Independent word-count cross-check over {n_ius} IUs (59 files, excl. SBC037) ===\n")
    print(f"Exact match: {n_match} of {n_ius} ({100 * n_match / n_ius:.2f}%)")
    print(f"Mismatch: {n_ius - n_match} of {n_ius} ({100 * (n_ius - n_match) / n_ius:.2f}%)\n")

    print("--- Distribution of (tokeniser count - independent count) ---")
    for diff, c in sorted(diff_counts.items()):
        print(f"  {diff:+d}: {c} IUs")

    print("\n--- By best-effort category ---")
    for cat, c in category_counts.most_common():
        print(f"  {cat}: {c} IUs")

    print("\n--- 10 raw examples per category (terminal only) ---")
    for cat, rows in examples.items():
        print(f"\n[{cat}]")
        for doc_id, line, text, tok_words, indep_runs in rows[:10]:
            print(f"  {doc_id}:{line}  tok={tok_words}  indep={indep_runs}")
            print(f"    raw={text!r}")

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    with open(reports_dir / "phase2_tokenizer_crosscheck_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["diff", "category", "count"])
        w.writeheader()
        by_diff_cat = Counter()
        for row in mismatch_log:
            by_diff_cat[(row["diff"], row["category"])] += 1
        for (diff, cat), c in sorted(by_diff_cat.items()):
            w.writerow({"diff": diff, "category": cat, "count": c})

    private_dir = Path("reports/private")
    private_dir.mkdir(parents=True, exist_ok=True)
    with open(private_dir / "phase2_tokenizer_crosscheck_full.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["file", "line", "diff", "tok_n", "indep_n", "category", "text", "tok_words", "indep_runs"]
        )
        w.writeheader()
        w.writerows(mismatch_log)


if __name__ == "__main__":
    main()

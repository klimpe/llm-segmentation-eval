"""Phase 2: where do truncated words (`y-`) fall within their IU?

Truncated words are kept always, in both conditions, as actually uttered
(CLAUDE.md's "Tokenisation" section) -- this is information only, no new
rule: it records a text-level cue that survives in both A and B, for
reports/phase2_llm_design.md, alongside the capitalisation finding that
prompted lowercasing. Nothing about how truncated words are tokenised or
rendered changes here.

A truncated word is identified the same way the tokeniser produces one:
Word.text ending in a single trailing "-" (the word rule's own trailing-
hyphen truncation case, or the displaced-truncation / SBC012-SBC013
underscore-truncation paths, which both normalise onto a trailing "-" --
see sbcsae_tokenizer.py's rule table and _handle_displaced_trunc). No
other Word in this tokeniser can end in "-": an internal hyphen
("third-graders") never lands at the end of .text.

Position is relative to the word's own reference segment (the IU it
belongs to, zero-word IUs already excluded, same convention as
sbcsae_llm.build_document_structure): IU-initial (first word), IU-final
(last word), IU-internal (neither). A single-word IU's lone truncated
word is both at once -- reported as its own category rather than forced
into either bucket.

Whole-corpus (59 files, SBC037 excluded). Terminal output plus one
committed CSV (counts only, no transcript text).
"""
import csv
from collections import Counter
from pathlib import Path

from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import tokenize, words_only

EXCLUDE_FILES = {"SBC037"}


def classify(word_idx: int, n_words: int) -> str:
    if n_words == 1:
        return "iu_initial_and_final"
    if word_idx == 0:
        return "iu_initial"
    if word_idx == n_words - 1:
        return "iu_final"
    return "iu_internal"


def collect_counts():
    total_words = 0
    total_truncated = Counter()  # category -> count of truncated words
    total_by_category = Counter()  # category -> count of ALL words (context)

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id in EXCLUDE_FILES:
            continue
        for u in units:
            words = words_only(tokenize(u.text))
            n = len(words)
            if n == 0:
                continue
            total_words += n
            for i, w in enumerate(words):
                cat = classify(i, n)
                total_by_category[cat] += 1
                if w.text.endswith("-"):
                    total_truncated[cat] += 1

    return total_words, total_truncated, total_by_category


def main():
    total_words, truncated, by_category = collect_counts()
    categories = ["iu_initial", "iu_internal", "iu_final", "iu_initial_and_final"]
    n_truncated = sum(truncated.values())

    print(f"Total words scored: {total_words}")
    print(f"Total truncated words (text ending in '-'): {n_truncated}")
    print(f"\n{'category':22s} {'n_truncated':>12s} {'share_of_truncated':>20s} {'n_all_words':>12s} {'truncation_rate':>16s}")
    rows = []
    for cat in categories:
        n_trunc = truncated[cat]
        n_all = by_category[cat]
        share_of_truncated = n_trunc / n_truncated if n_truncated else 0.0
        rate = n_trunc / n_all if n_all else 0.0
        print(f"{cat:22s} {n_trunc:12d} {share_of_truncated:20.4f} {n_all:12d} {rate:16.4f}")
        rows.append(
            {
                "category": cat,
                "n_truncated": n_trunc,
                "share_of_truncated": share_of_truncated,
                "n_all_words": n_all,
                "truncation_rate": rate,
            }
        )

    reports_dir = Path("reports")
    with open(reports_dir / "phase2_truncation_position.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["category", "n_truncated", "share_of_truncated", "n_all_words", "truncation_rate"])
        w.writeheader()
        w.writerows(rows)

    print("\nWrote reports/phase2_truncation_position.csv")


if __name__ == "__main__":
    main()

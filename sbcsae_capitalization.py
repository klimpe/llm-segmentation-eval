"""Phase 2: does capitalisation encode the IU boundary CLAUDE.md already
says `.`, `,`, `?` and `--` encode (transitional continuity punctuation,
removed in both conditions per sbcsae_tokenizer.py's Boundary class)?

Whole-corpus (59 files, SBC037 excluded), reference segments only (zero-
word IUs dropped, same convention as sbcsae_per_file_stats.py). For every
word except the literal token "I" (always capitalised regardless of
position, would swamp the signal), classify it into exactly one of:

  (a) IU-initial, same speaker as the previous reference segment (not
      turn-initial), whose LAST Boundary item was "period"
  (b) ... "comma"
  (c) ... "qmark"
  (d) ... "iu_truncation" or "underscore_iu_truncation" (SBC012/SBC013's
      "--" equivalent, CLAUDE.md's "Tokenisation" section) -- i.e. "--"
  (e) turn-initial: first word of the first reference segment of a new
      turn (speaker differs from the previous reference segment, or this
      is the file's first reference segment)
  (g) IU-initial, same speaker, but the previous reference segment's last
      item was not one of the four boundary kinds above (no marker, or
      the unrelated "isolated_hyphen" stray-dash Boundary) -- not asked
      for by name, reported anyway so (a)-(e) don't silently omit a slice
      of IU-initial words
  (f) IU-internal: every word that is not the first word of its IU,
      regardless of turn or boundary kind

A word is "capitalised" if its normalised text's first character is
uppercase (Word.text -- condition-independent, unaffected by A/B).

Terminal output and one committed CSV (counts only, no transcript text).
"""
import csv
from collections import Counter
from pathlib import Path

from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import Boundary, tokenize, words_only

EXCLUDE_FILES = {"SBC037"}
EXCLUDE_WORD = "I"

_BOUNDARY_TO_CATEGORY = {
    "period": "a",
    "comma": "b",
    "qmark": "c",
    "iu_truncation": "d",
    "underscore_iu_truncation": "d",
}


def _last_boundary_kind(items) -> str | None:
    for it in reversed(items):
        if isinstance(it, Boundary):
            return it.kind
    return None


def classify_corpus():
    counts = Counter()  # category -> total words (excl. "I")
    capitalised = Counter()  # category -> capitalised words (excl. "I")
    per_file = {}

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id in EXCLUDE_FILES:
            continue

        file_counts = Counter()
        file_capitalised = Counter()

        prev_speaker = None
        prev_items = None
        for u in units:
            items = tokenize(u.text)
            words = words_only(items)
            if not words:
                continue  # zero-word IU: dropped from the reference, as elsewhere

            turn_initial = prev_speaker is None or u.speaker != prev_speaker

            for wi, w in enumerate(words):
                if w.text == EXCLUDE_WORD:
                    continue
                if wi > 0:
                    cat = "f"
                elif turn_initial:
                    cat = "e"
                else:
                    kind = _last_boundary_kind(prev_items)
                    cat = _BOUNDARY_TO_CATEGORY.get(kind, "g")
                file_counts[cat] += 1
                if w.text[:1].isupper():
                    file_capitalised[cat] += 1

            prev_speaker = u.speaker
            prev_items = items

        per_file[doc_id] = (file_counts, file_capitalised)
        counts.update(file_counts)
        capitalised.update(file_capitalised)

    return counts, capitalised, per_file


def main():
    counts, capitalised, per_file = classify_corpus()
    cats = ["a", "b", "c", "d", "e", "f", "g"]
    labels = {
        "a": "IU-initial after '.'",
        "b": "IU-initial after ','",
        "c": "IU-initial after '?'",
        "d": "IU-initial after '--'",
        "e": "turn-initial",
        "f": "IU-internal",
        "g": "IU-initial, no marker (residual)",
    }

    print(f"Total words scored (excl. literal 'I'): {sum(counts.values())}")
    print(f"\n{'cat':4s} {'label':35s} {'n_words':>10s} {'n_capitalised':>14s} {'share':>8s}")
    for cat in cats:
        n = counts[cat]
        c = capitalised[cat]
        share = c / n if n else float("nan")
        print(f"{cat:4s} {labels[cat]:35s} {n:10d} {c:14d} {share:8.4f}")

    reports_dir = Path("reports")
    with open(reports_dir / "phase2_capitalization.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "label", "n_words", "n_capitalised", "share_capitalised"])
        for cat in cats:
            n = counts[cat]
            c = capitalised[cat]
            share = c / n if n else ""
            w.writerow([cat, labels[cat], n, c, share])

    with open(reports_dir / "phase2_capitalization_by_file.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file"] + [f"{c}_n" for c in cats] + [f"{c}_capitalised" for c in cats])
        for doc_id in sorted(per_file):
            file_counts, file_capitalised = per_file[doc_id]
            w.writerow(
                [doc_id]
                + [file_counts[c] for c in cats]
                + [file_capitalised[c] for c in cats]
            )

    print("\nWrote reports/phase2_capitalization.csv and reports/phase2_capitalization_by_file.csv")


if __name__ == "__main__":
    main()

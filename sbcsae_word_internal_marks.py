"""Phase 2: where do =, % and ! (lengthening, glottal stop, booster) fall
relative to word boundaries, and which of those currently vanish from
condition B's rendering?

The tokeniser fuses a cue that is glued on BOTH sides to real word
content ("s=o") into that Word's own `.raw` field (sbcsae_tokenizer.py's
`_sandwiched` mechanism) rather than emitting it as a separate Cue item.
Before this session's rendering fix, sbcsae_llm.py's B rendering used
Word.text (the bare, mark-stripped form) for every Word, so a sandwiched
mark was never emitted anywhere -- it does not become a Cue item (so the
old "cues only in B" logic never sees it) AND it is not in .text (so the
old word-rendering never sees it either). A cue glued on only one side
(word-final "so=", or leading with nothing open, "!Ron") is NOT
sandwiched -- it is flushed as its own Cue item and already renders
correctly, with or without this fix.

Classification, using the tokeniser's own internals directly (`_sandwiched`,
`_is_glued`, `_raw_matches`, `_KIND_OF` -- diagnostic-only imports, same
precedent as sbcsae_tokenizer_invariants.py and sbcsae_tokenizer_validate.py),
so this reports exactly what the real tokeniser does, not an approximation:
  - word_internal: `_sandwiched()` is True -- fused into Word.raw, invisible
    under the old .text-based rendering.
  - word_final: not sandwiched, but glued to the immediately preceding
    match (i>0 and no whitespace before it) -- already its own Cue item,
    rendered correctly.
  - standalone: neither of the above -- covers both a truly free-floating
    mark and one glued only to the FOLLOWING word ("!Ron"-style leading
    marks; documented in sbcsae_tokenizer.py as a separate, pre-existing
    display wrinkle, not something this session changes) -- both already
    render as their own Cue item.

Only the three PLAIN cue rules (lengthening "=", glottal "%",
booster_bang "!") are counted -- not the four "compound" rules that also
contain a "%" or "=" character inside a larger parenthetical match
(glottal_breath "(%Hx)", breath_bracket_lengthening "(H[=])",
breath_paren_lengthening "(H=)", and the single sbc015 named exception).
Every compound decomposes into its own separate Cue item unconditionally
(see tokenize()'s "compound" handling) -- never sandwiched, never
vanishing -- so they are not part of what this session's bug or fix
concerns. Their combined count is verified below via a whole-corpus
character-count cross-check, not asserted.

Whole-corpus (59 files, SBC037 excluded). Terminal output plus one
committed CSV (counts only, no transcript text).
"""
import csv
from collections import Counter
from pathlib import Path

from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import _KIND_OF, _is_glued, _raw_matches, _sandwiched

EXCLUDE_FILES = {"SBC037"}

_MARK_RULE_NAMES = {"lengthening": "=", "glottal": "%", "booster_bang": "!"}


def classify_occurrence(matches, i: int, text: str) -> str:
    if _sandwiched(matches, i, text):
        return "word_internal"
    if i > 0 and _is_glued(text, matches[i - 1].end(), matches[i].start()):
        return "word_final"
    return "standalone"


def collect_counts():
    # counts[symbol][category] = n
    counts = {sym: Counter() for sym in _MARK_RULE_NAMES.values()}
    raw_char_totals = Counter()  # sanity cross-check: every literal occurrence, any context

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id in EXCLUDE_FILES:
            continue
        for u in units:
            text = u.text
            raw_char_totals["="] += text.count("=")
            raw_char_totals["%"] += text.count("%")
            raw_char_totals["!"] += text.count("!")

            matches = _raw_matches(text)
            for i, m in enumerate(matches):
                name = m.lastgroup
                if _KIND_OF.get(name) != "cue" or name not in _MARK_RULE_NAMES:
                    continue
                symbol = _MARK_RULE_NAMES[name]
                category = classify_occurrence(matches, i, text)
                counts[symbol][category] += 1

    return counts, raw_char_totals


def main():
    counts, raw_char_totals = collect_counts()
    categories = ["word_internal", "word_final", "standalone"]

    print(f"{'symbol':8s} {'word_internal':>14s} {'word_final':>12s} {'standalone':>12s} {'total_plain':>12s} "
          f"{'vanish_share':>14s} {'raw_char_count':>15s} {'compound/other':>15s}")
    rows = []
    for name, symbol in _MARK_RULE_NAMES.items():
        c = counts[symbol]
        total_plain = sum(c[cat] for cat in categories)
        vanish_share = c["word_internal"] / total_plain if total_plain else 0.0
        raw_total = raw_char_totals[symbol]
        other = raw_total - total_plain  # compound-rule occurrences, or (for "!" ) none expected
        print(
            f"{symbol:8s} {c['word_internal']:14d} {c['word_final']:12d} {c['standalone']:12d} "
            f"{total_plain:12d} {vanish_share:14.4f} {raw_total:15d} {other:15d}"
        )
        rows.append(
            {
                "symbol": symbol,
                "word_internal": c["word_internal"],
                "word_final": c["word_final"],
                "standalone": c["standalone"],
                "total_plain_rule_occurrences": total_plain,
                "vanish_share_under_old_rendering": vanish_share,
                "raw_char_count_any_context": raw_total,
                "compound_or_other_occurrences": other,
            }
        )

    reports_dir = Path("reports")
    with open(reports_dir / "phase2_word_internal_marks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "symbol", "word_internal", "word_final", "standalone",
                "total_plain_rule_occurrences", "vanish_share_under_old_rendering",
                "raw_char_count_any_context", "compound_or_other_occurrences",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print("\nWrote reports/phase2_word_internal_marks.csv")


if __name__ == "__main__":
    main()

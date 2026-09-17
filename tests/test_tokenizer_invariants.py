"""Phase 2 stage 4, closing step 2: word-level invariants, run every time.

Promoted from the one-off sbcsae_tokenizer_invariants.py analysis (see
reports/phase2_tokeniser.md S14) into permanent regression tests, per the
brief. Runs the whole corpus once (SBC037 excluded, same as every other
stage-4 check) and checks:

  a) No fusion across whitespace -- must be exactly 0, always. A single
     word's letters spanning two whitespace-delimited raw chunks is never
     legitimate; if this test fails, it is a real silent mis-split.
  b) No lost words -- every violation must fall into an already-attributed
     category (a documented tier-1/tier-2 rule, a named exception, or one
     of this check's own known false-positive shapes: an internal capital
     inside a correctly-kept compound word, or a legitimate multi-word
     split at a Boundary/displaced-truncation flush). "other" must be
     empty. `doubled_cue_fusion` is a real, known, NOT-YET-FIXED bug
     (reports/phase2_tokeniser.md S14.3) -- its count is pinned to the
     current baseline rather than asserted zero, so a regression (the
     count growing) still fails loudly, without re-blocking this suite on
     something already reported and deliberately left open.
  c) Capitalised material -- spot check that real short words are never
     silently dropped (the flip side of (b) for uppercase content, which
     (b) does not examine).

Slow (~15-20s: three passes over 68,815 IUs) -- computed once per module
via a fixture, not once per test.
"""
from collections import Counter

import pytest

from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import TokenizeError, tokenize, words_only
from sbcsae_tokenizer_invariants import (
    _category,
    allcaps_chunks,
    check_no_fusion_across_whitespace,
    check_no_lost_words,
)

# Every category check_no_lost_words' violations are currently allowed to
# fall into. A new category appearing here (i.e. "other" becoming
# non-empty) means something new is either a real bug or needs its own
# attribution added to sbcsae_tokenizer_invariants.py's _category -- not a
# reason to just widen this set.
_KNOWN_B_CATEGORIES = {
    "parenthetical_marker (breath/vocal-noise name)",
    "overlap_bracket",
    "angle_tag",
    "underscore_truncation_or_gloss",
    "disguise_prefix",
    "plus_fusion",
    "at_sign_fusion",
    "lost_initial_letter (documented: stripped, never reconstructed)",
    "hyphen_only_chunk (Boundary, not lost)",
    "internal_capital_in_kept_word (McNuggets/Wal-Mart-shaped, not lost)",
    "boundary_or_multiword_split (Boundary/displaced-truncation flush, not lost)",
    "doubled_cue_fusion (silent mis-split, real bug, not attributable)",
}

# Known, reported, NOT fixed (reports/phase2_tokeniser.md S14.3):
# _sandwiched() only looks one match ahead/behind, so a run of 2+ glued
# cue marks between two word fragments ("b==itch" -> "b", "itch" instead
# of "bitch") breaks fusion the same way the already-fixed bracket-hyphen
# and pending-word bugs did. Pinned, not asserted zero, so this suite
# keeps passing while the bug stays open, but still fails if it changes.
_KNOWN_DOUBLED_CUE_FUSION_COUNT = 7


@pytest.fixture(scope="module")
def corpus_invariants():
    a_violations = []
    b_by_category = Counter()
    caps_tally = {}

    for doc_id, units, *_ in iter_trn_documents():
        if doc_id == "SBC037":
            continue
        for u in units:
            text = u.text
            try:
                items = tokenize(text)
            except TokenizeError:
                continue  # none currently raise (reports/phase2_tokeniser.md S11)
            tok_words = [w.text for w in words_only(items)]

            a_violations.extend(check_no_fusion_across_whitespace(text, tok_words))

            for chunk, required in check_no_lost_words(text, tok_words):
                b_by_category[_category(chunk, required, tok_words)] += 1

            raw_caps = Counter(allcaps_chunks(text))
            for value, raw_n in raw_caps.items():
                kept_n = min(raw_n, sum(1 for w in tok_words if value in w))
                counts = caps_tally.setdefault(value, {"kept": 0, "removed": 0})
                counts["kept"] += kept_n
                counts["removed"] += raw_n - kept_n

    return {"a_violations": a_violations, "b_by_category": b_by_category, "caps_tally": caps_tally}


def test_a_no_fusion_across_whitespace(corpus_invariants):
    violations = corpus_invariants["a_violations"]
    assert violations == [], f"{len(violations)} word(s) whose letters span two whitespace chunks: {violations[:10]}"


def test_b_no_lost_words_all_attributable(corpus_invariants):
    by_category = corpus_invariants["b_by_category"]
    unknown = set(by_category) - _KNOWN_B_CATEGORIES
    assert not unknown, f"unattributed lost-word categories: {unknown}"
    assert by_category.get("other", 0) == 0


def test_b_doubled_cue_fusion_is_pinned_open_bug(corpus_invariants):
    count = corpus_invariants["b_by_category"].get("doubled_cue_fusion (silent mis-split, real bug, not attributable)", 0)
    assert count == _KNOWN_DOUBLED_CUE_FUSION_COUNT, (
        f"doubled_cue_fusion count changed from the pinned baseline "
        f"({_KNOWN_DOUBLED_CUE_FUSION_COUNT}) to {count} -- re-investigate "
        f"before repinning: either the known bug grew, or something fixed "
        f"part of it."
    )


def test_c_real_short_words_never_silently_removed(corpus_invariants):
    caps_tally = corpus_invariants["caps_tally"]
    for value in ("I", "TV"):
        counts = caps_tally.get(value)
        assert counts is not None, f"{value!r} no longer occurs in the corpus -- check the reader/corpus, not the rule"
        assert counts["removed"] == 0, f"{value!r} was silently removed {counts['removed']} time(s)"

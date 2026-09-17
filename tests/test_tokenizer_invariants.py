"""Phase 2 stage 4, closing step 2/3: word-level invariants, run every time.

Promoted from the one-off sbcsae_tokenizer_invariants.py analysis (see
reports/phase2_tokeniser.md S14-S16) into permanent regression tests, per
the brief. Runs the whole corpus once (SBC037 excluded, same as every
other stage-4 check) and checks:

  a) No fusion across whitespace -- must be exactly 0, always. A single
     word's letters spanning two whitespace-delimited raw chunks is never
     legitimate; if this test fails, it is a real silent mis-split.
  b) No lost words -- every violation must fall into an already-attributed
     category (a documented tier-1/tier-2 rule, a named exception, or one
     of this check's own known false-positive shapes: an internal capital
     inside a correctly-kept compound word, or a legitimate multi-word
     split at a Boundary/displaced-truncation flush). "other" must be
     empty, and so must any category not on the known list -- a new
     category appearing is either a real bug or needs its own
     attribution added to sbcsae_tokenizer_invariants.py's _category.
  c) Capitalised material -- spot check that real short words are never
     silently dropped (the flip side of (b) for uppercase content, which
     (b) does not examine).
  d) No wrongful splits -- (a) and (b) both pass on a chunk whose letters
     all survive, in order, but end up as two or more separate words
     instead of one ("b==itch" -> "b", "itch": every letter is present,
     so (a)/(b) are silent). Every chunk assigned 2+ words must be
     explained by a documented rule (a Boundary inside the chunk, a
     displaced-truncation flush, or the SBC012/SBC013 bare-underscore
     truncation convention) -- "other" must be empty.

Also pins one open, NOT-yet-fixed bug found by the step-3 verification
(reports/phase2_tokeniser.md S16): the single-angle open/close/wrap
regex's greedy character class can swallow real spoken content glued
directly to the delimiter with no space ("<@Mm@>", "<@in San...")
because it can't distinguish that from a genuine short tag code -- every
confirmed genuine tag code in this corpus is all-caps, so a lowercase
letter in the matched name is a strong signal of swallowed content.
Pinned rather than asserted zero, so a regression (the count growing)
still fails loudly without re-blocking this suite on something already
reported and deliberately left open.

Slow (~10s: passes over 68,815 IUs) -- computed once per module via a
fixture, not once per test.
"""
from collections import Counter

import pytest

from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import TokenizeError, tokenize, words_only
from sbcsae_tokenizer_invariants import (
    _category,
    _split_category,
    allcaps_chunks,
    angle_tag_names_with_lowercase,
    check_no_fusion_across_whitespace,
    check_no_lost_words,
    check_no_wrongful_splits,
)

# Every category check_no_lost_words' violations are currently allowed to
# fall into. A new category appearing here (i.e. "other" becoming
# non-empty, or an unlisted category showing up) means something new is
# either a real bug or needs its own attribution added to
# sbcsae_tokenizer_invariants.py's _category -- not a reason to just
# widen this set. `doubled_cue_fusion` is deliberately NOT here any more
# -- it was a real, pinned, open bug (S14.3) and is now fixed (S15); if
# it reappears, it will show as an unknown category and fail loudly.
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
}

# (d)'s three documented splitting rules -- see _split_category.
_KNOWN_D_CATEGORIES = {
    "boundary_inside_chunk (documented: . , ? -- always end a word)",
    "displaced_truncation_flush (documented: =- or %- always ends a word)",
    "underscore_truncation_ends_word (documented: bare _ always ends a word)",
}

# Known, reported, NOT fixed (reports/phase2_tokeniser.md S16): the
# single-angle tag regex swallows real content glued to it with no
# space. 19 instances corpus-wide have a lowercase letter in the matched
# "name" (see angle_tag_names_with_lowercase's own docstring); 17 are
# high-confidence genuine content loss on manual review, 2 (a repeated
# "Hi"/"HI" pair, a repeated "X"/"x" pair) are lower-confidence and could
# be a genuine, if case-inconsistent, tag -- pinned at the full 19 rather
# than the curated 17, since the pin should track what the objective
# check actually counts, not a subjective read of which ones are "real."
_KNOWN_ANGLE_TAG_SWALLOW_COUNT = 19


@pytest.fixture(scope="module")
def corpus_invariants():
    a_violations = []
    b_by_category = Counter()
    d_by_category = Counter()
    caps_tally = {}
    angle_tag_swallows = 0

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

            for chunk, words, gaps in check_no_wrongful_splits(text, tok_words):
                d_by_category[_split_category(chunk, words, gaps)] += 1

            angle_tag_swallows += len(angle_tag_names_with_lowercase(text))

            raw_caps = Counter(allcaps_chunks(text))
            for value, raw_n in raw_caps.items():
                kept_n = min(raw_n, sum(1 for w in tok_words if value in w))
                counts = caps_tally.setdefault(value, {"kept": 0, "removed": 0})
                counts["kept"] += kept_n
                counts["removed"] += raw_n - kept_n

    return {
        "a_violations": a_violations,
        "b_by_category": b_by_category,
        "d_by_category": d_by_category,
        "caps_tally": caps_tally,
        "angle_tag_swallows": angle_tag_swallows,
    }


def test_a_no_fusion_across_whitespace(corpus_invariants):
    violations = corpus_invariants["a_violations"]
    assert violations == [], f"{len(violations)} word(s) whose letters span two whitespace chunks: {violations[:10]}"


def test_b_no_lost_words_all_attributable(corpus_invariants):
    by_category = corpus_invariants["b_by_category"]
    unknown = set(by_category) - _KNOWN_B_CATEGORIES
    assert not unknown, f"unattributed lost-word categories: {unknown}"
    assert by_category.get("other", 0) == 0


def test_c_real_short_words_never_silently_removed(corpus_invariants):
    caps_tally = corpus_invariants["caps_tally"]
    for value in ("I", "TV"):
        counts = caps_tally.get(value)
        assert counts is not None, f"{value!r} no longer occurs in the corpus -- check the reader/corpus, not the rule"
        assert counts["removed"] == 0, f"{value!r} was silently removed {counts['removed']} time(s)"


def test_d_no_wrongful_splits_all_attributable(corpus_invariants):
    by_category = corpus_invariants["d_by_category"]
    unknown = set(by_category) - _KNOWN_D_CATEGORIES
    assert not unknown, f"unattributed wrongful-split categories: {unknown}"
    assert by_category.get("other", 0) == 0


def test_angle_tag_content_swallowing_is_pinned_open_bug(corpus_invariants):
    count = corpus_invariants["angle_tag_swallows"]
    assert count == _KNOWN_ANGLE_TAG_SWALLOW_COUNT, (
        f"angle-tag content-swallowing count changed from the pinned "
        f"baseline ({_KNOWN_ANGLE_TAG_SWALLOW_COUNT}) to {count} -- "
        f"re-investigate before repinning: either the known bug grew, or "
        f"something fixed part of it."
    )

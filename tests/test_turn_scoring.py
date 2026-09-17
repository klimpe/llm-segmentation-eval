"""Synthetic-masses tests for sbcsae_scoring.score_document. No corpus
data involved -- a hand-built reference plus turn-boundary subset stands
in for a real document's IU/turn structure.
"""
import pytest

from masses import masses_to_boundaries
from sbcsae_scoring import score_document

# 36 tokens, 10 IU-level segments, boundaries at {3,7,10,15,17,23,24,28,31}
# (same fixture scale as test_metrics_sanity.py, big enough for
# window_diff's default k). Two of those nine boundaries, {10, 23}, are
# speaker changes; the other seven are within-turn IU boundaries.
REF_MASSES = [3, 4, 3, 5, 2, 6, 1, 4, 3, 5]
REF_BOUNDARIES = masses_to_boundaries(REF_MASSES)  # {3,7,10,15,17,23,24,28,31}
TURN_BOUNDARIES = {10, 23}
WITHIN_TURN_BOUNDARIES = REF_BOUNDARIES - TURN_BOUNDARIES  # {3,7,15,17,24,28,31}


def perfect_hyp_indices():
    return sorted(b + 1 for b in WITHIN_TURN_BOUNDARIES)


def test_perfect_hypothesis_scores_1_0_both_ways():
    result = score_document(REF_MASSES, TURN_BOUNDARIES, perfect_hyp_indices())
    for key in ("all_boundaries", "within_turn"):
        assert result[key]["precision"] == 1.0
        assert result[key]["recall"] == 1.0
        assert result[key]["f1"] == 1.0
        assert result[key]["boundary_similarity"] == 1.0
        assert result[key]["window_diff"] == 0.0


def test_result_carries_headline_and_non_comparability_note():
    result = score_document(REF_MASSES, TURN_BOUNDARIES, perfect_hyp_indices())
    assert result["headline"] == "within_turn"
    assert "different effective segment lengths" in result["note"]
    assert "must never be compared" in result["note"]


def test_missed_within_turn_boundary_hurts_within_turn_more_than_all_boundaries():
    # Drop boundary 7 (index 8) from the hypothesis: one within-turn false
    # negative. The two turn boundaries still match perfectly (added in
    # code, never predicted), so all_boundaries gets "free" credit that
    # within_turn does not -- within_turn must score strictly worse.
    indices = [i for i in perfect_hyp_indices() if i != 8]
    result = score_document(REF_MASSES, TURN_BOUNDARIES, indices)
    assert result["within_turn"]["recall"] < 1.0
    assert result["within_turn"]["f1"] < result["all_boundaries"]["f1"]
    # the turn boundaries themselves are untouched, so all_boundaries
    # still has 2 of its 9 boundaries matching purely from the code-added
    # positions even with a within-turn miss.
    assert result["all_boundaries"]["recall"] == pytest.approx(8 / 9)


def test_spurious_within_turn_boundary_hurts_precision_both_ways():
    indices = perfect_hyp_indices() + [2]  # index 2 -> boundary 1, not a real one
    result = score_document(REF_MASSES, TURN_BOUNDARIES, indices)
    assert result["within_turn"]["precision"] < 1.0
    assert result["all_boundaries"]["precision"] < 1.0


def test_rejects_hypothesis_naming_a_turn_initial_position():
    # index 11 -> boundary 10, a turn boundary -- never a legitimate answer.
    with pytest.raises(ValueError, match="turn-initial"):
        score_document(REF_MASSES, TURN_BOUNDARIES, perfect_hyp_indices() + [11])


def test_rejects_out_of_range_hypothesis_index():
    with pytest.raises(ValueError, match="out of range"):
        score_document(REF_MASSES, TURN_BOUNDARIES, [37])
    with pytest.raises(ValueError, match="out of range"):
        score_document(REF_MASSES, TURN_BOUNDARIES, [1])  # boundary 0 is not valid


def test_rejects_turn_boundaries_not_a_subset_of_reference():
    with pytest.raises(ValueError, match="subset"):
        score_document(REF_MASSES, {5}, perfect_hyp_indices())  # 5 is not a reference boundary


def test_empty_hypothesis_still_gets_turn_boundaries_for_free():
    result = score_document(REF_MASSES, TURN_BOUNDARIES, [])
    assert result["all_boundaries"]["recall"] == pytest.approx(2 / 9)
    assert result["within_turn"]["recall"] == 0.0

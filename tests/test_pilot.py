"""Synthetic tests for sbcsae_pilot.py's pure logic (parsing, window
core-filtering, local reindexing) -- no model call, no corpus. The
network-calling parts (run_pilot itself) are exercised by actually
running the pilot, not here.
"""
import pytest

from sbcsae_pilot import WindowDraw, _core_only, _local_region_inputs, _parse_window_response, analyse
from sbcsae_tokenizer import Condition
from sbcsae_windows import ScoreRegion


class _FakeDoc:
    def __init__(self, ref_masses, turn_boundaries):
        self.ref_masses = ref_masses
        self.turn_boundaries = turn_boundaries


def test_parse_window_response_drops_turn_initial_and_keeps_the_rest():
    region = ScoreRegion(score_start=1, score_end=10, window_start=1, window_end=10)
    turn_boundaries = {5}  # a boundary at position 5 -> index 6 is turn-initial
    kept, dropped = _parse_window_response("[3, 6, 8]", region, turn_boundaries)
    assert dropped == [6]
    assert kept == [3, 8]


def test_parse_window_response_raises_on_out_of_window_index():
    region = ScoreRegion(score_start=1, score_end=10, window_start=5, window_end=20)
    with pytest.raises(ValueError, match="outside window"):
        _parse_window_response("[3]", region, set())  # 3 < window_start=5


def test_parse_window_response_raises_on_malformed_json():
    region = ScoreRegion(score_start=1, score_end=10, window_start=1, window_end=10)
    with pytest.raises(ValueError):
        _parse_window_response("not json", region, set())


def test_parse_window_response_empty_array_is_valid():
    region = ScoreRegion(score_start=1, score_end=10, window_start=1, window_end=10)
    kept, dropped = _parse_window_response("[]", region, set())
    assert kept == [] and dropped == []


def test_core_only_filters_to_score_range_excluding_margin():
    region = ScoreRegion(score_start=101, score_end=200, window_start=1, window_end=300)
    indices = [50, 100, 101, 150, 200, 201, 300]
    assert _core_only(indices, region) == [101, 150, 200]


def test_local_region_inputs_reindexes_correctly():
    # 20-token doc, IU boundaries at 5, 10, 15; turn boundary at 10.
    ref_masses = [5, 5, 5, 5]  # boundaries at 5, 10, 15
    turn_boundaries = {10}
    doc = _FakeDoc(ref_masses, turn_boundaries)
    region = ScoreRegion(score_start=6, score_end=15, window_start=1, window_end=20)

    local_ref_masses, local_turn_boundaries, lo = _local_region_inputs(doc, region)
    assert lo == 6
    # Local space covers words 6-15 (10 words, local positions 1-10).
    # Interior boundaries are global p in [lo, hi-1] = [6, 14]: only 10
    # qualifies (5 is at lo-1, excluded -- see _local_region_inputs'
    # docstring; 15 is at hi, also excluded, it's the region's own last
    # position with nothing local after it). 10 reindexes to 10-(6-1)=5.
    assert sum(local_ref_masses) == 10
    assert local_ref_masses == [5, 5]  # one boundary at local position 5
    assert local_turn_boundaries == {5}


def test_local_region_inputs_matches_hand_derivation():
    ref_masses = [3, 4, 3]  # boundaries at 3, 7; 10 tokens total
    doc = _FakeDoc(ref_masses, set())
    region = ScoreRegion(score_start=1, score_end=10, window_start=1, window_end=10)
    local_ref_masses, local_turn_boundaries, lo = _local_region_inputs(doc, region)
    assert lo == 1
    assert local_ref_masses == [3, 4, 3]
    assert local_turn_boundaries == set()


# ---------------------------------------------------------------------
# analyse() end-to-end, with hand-built draws -- no network call
# ---------------------------------------------------------------------


class _FakeDocFull:
    """A minimal stand-in for sbcsae_llm.DocumentStructure: 20 tokens,
    two turns (speaker change at word 11, so turn_boundaries={10}), IU
    boundaries at 5, 10, 15 (10 is also the turn boundary).
    """

    def __init__(self):
        self.doc_id = "FAKE"
        self.ref_masses = [5, 5, 5, 5]
        self.turn_boundaries = {10}
        self.n_tokens = 20


def _two_window_regions():
    # Two 10-word regions, no margin needed for this synthetic case.
    return [
        ScoreRegion(score_start=1, score_end=10, window_start=1, window_end=10),
        ScoreRegion(score_start=11, score_end=20, window_start=11, window_end=20),
    ]


def test_analyse_perfect_predictions_score_1_0():
    doc = _FakeDocFull()
    regions = _two_window_regions()
    # Window 0 (words 1-10): reference boundary at 5 -> predict start-index 6.
    # Window 1 (words 11-20): reference boundary at 15 -> predict start-index 16;
    # word 11 is turn-initial, never asked for.
    ok_w0 = WindowDraw(status="ok", kept=[6], dropped_turn_initial=[])
    ok_w1 = WindowDraw(status="ok", kept=[16], dropped_turn_initial=[])
    draws = {
        Condition.A: [[ok_w0, ok_w1] for _ in range(3)],
        Condition.B: [[ok_w0, ok_w1] for _ in range(3)],
    }
    result = analyse({"doc": doc, "regions": regions, "draws": draws, "n_samples": 3})

    for cond in ("A", "B"):
        c = result[cond]
        assert c["n_failed"] == 0
        assert c["incomplete_samples"] == []
        assert len(c["whole_file_scores"]) == 3
        for sc in c["whole_file_scores"]:
            assert sc["within_turn"]["f1"] == 1.0
            assert sc["all_boundaries"]["f1"] == 1.0
        # window 1's own first core word (11) is turn-initial and
        # already excluded via dropped_turn_initial -- never reaches
        # _core_only/local scoring, so no i==lo edge case here. Confirm
        # per-window scoring didn't crash and is also perfect.
        for w in (0, 1):
            for sc in c["per_window_scores"][w]:
                assert sc["within_turn"]["f1"] == 1.0


def test_analyse_handles_prediction_at_windows_own_first_core_word():
    # Regression for the i == lo edge case: a real, valid within-turn
    # prediction landing exactly on window 1's own first core word (11)
    # -- legitimate at whole-file scope, but not locally representable
    # (see _local_region_inputs) -- must not raise, just be excluded
    # from that window's own local score.
    doc = _FakeDocFull()
    doc.turn_boundaries = set()  # no turn boundary this time, so word 11 CAN be predicted
    regions = _two_window_regions()
    ok_w0 = WindowDraw(status="ok", kept=[6], dropped_turn_initial=[])
    ok_w1 = WindowDraw(status="ok", kept=[11, 16], dropped_turn_initial=[])  # 11 == region 1's own lo
    draws = {Condition.A: [[ok_w0, ok_w1]], Condition.B: [[ok_w0, ok_w1]]}
    result = analyse({"doc": doc, "regions": regions, "draws": draws, "n_samples": 1})
    c = result["A"]
    assert len(c["whole_file_scores"]) == 1  # did not raise
    assert len(c["per_window_scores"][1]) == 1  # did not raise


def test_analyse_incomplete_sample_excluded_from_whole_file_scores():
    doc = _FakeDocFull()
    regions = _two_window_regions()
    ok_w0 = WindowDraw(status="ok", kept=[6], dropped_turn_initial=[])
    fail_w1 = WindowDraw(status="fail", reason="malformed JSON")
    draws = {Condition.A: [[ok_w0, fail_w1]], Condition.B: [[ok_w0, fail_w1]]}
    result = analyse({"doc": doc, "regions": regions, "draws": draws, "n_samples": 1})
    c = result["A"]
    assert c["n_failed"] == 1
    assert c["whole_file_scores"] == []
    assert c["incomplete_samples"] == [0]
    # window 0's own draw still succeeded, so it still contributes a
    # per-window score even though the sample overall is incomplete.
    assert len(c["per_window_scores"][0]) == 1
    assert 1 not in c["per_window_scores"]


def test_analyse_counts_dropped_turn_initial_per_sample():
    doc = _FakeDocFull()
    regions = _two_window_regions()
    ok_w0 = WindowDraw(status="ok", kept=[6], dropped_turn_initial=[])
    ok_w1 = WindowDraw(status="ok", kept=[16], dropped_turn_initial=[11])  # model guessed the turn start anyway
    draws = {Condition.A: [[ok_w0, ok_w1]], Condition.B: [[ok_w0, ok_w1]]}
    result = analyse({"doc": doc, "regions": regions, "draws": draws, "n_samples": 1})
    assert result["A"]["dropped_turn_initial_per_sample"] == [1]


def test_analyse_flags_a_long_run_as_degenerate():
    # A single 30-word region so a run of 13 consecutive one-word
    # predictions actually fits (MAX_LEGITIMATE_RUN is 11).
    class _BigDoc:
        doc_id = "FAKE"
        ref_masses = [30]
        turn_boundaries = set()
        n_tokens = 30

    doc = _BigDoc()
    region = ScoreRegion(score_start=1, score_end=30, window_start=1, window_end=30)
    # Predict a start index at every position 2..14 -> boundaries 1..13,
    # a run of 13 consecutive positions, > MAX_LEGITIMATE_RUN (11).
    ok = WindowDraw(status="ok", kept=list(range(2, 15)), dropped_turn_initial=[])
    draws = {Condition.A: [[ok]], Condition.B: [[ok]]}
    result = analyse({"doc": doc, "regions": [region], "draws": draws, "n_samples": 1})
    flags = result["A"]["degenerate_flags"]
    assert len(flags) == 1
    assert flags[0]["window"] == 0
    assert flags[0]["run_length"] == 13
    assert flags[0]["needs_manual_review"] is True
    assert flags[0]["flagged_degenerate"] is False  # 13 < DEGENERATE_FLAG_THRESHOLD (22)

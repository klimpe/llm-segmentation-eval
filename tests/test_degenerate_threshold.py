from sbcsae_degenerate_threshold import (
    DEGENERATE_FLAG_THRESHOLD,
    MAX_LEGITIMATE_RUN,
    max_consecutive_run,
    max_consecutive_run_with_span,
    per_file_review_policy,
    review_policy,
)


def test_empty():
    assert max_consecutive_run([]) == 0


def test_single():
    assert max_consecutive_run([5]) == 1


def test_all_consecutive():
    assert max_consecutive_run([3, 4, 5, 6]) == 4


def test_two_separate_runs_takes_the_longer():
    assert max_consecutive_run([1, 2, 3, 10, 11]) == 3


def test_no_consecutive_pairs():
    assert max_consecutive_run([1, 3, 5, 7]) == 1


def test_unsorted_input_is_not_handled_gracefully_by_design():
    # The function assumes sorted input (documented) and only compares
    # each element to its immediate predecessor IN THE GIVEN ORDER -- it
    # does not sort first. [5, 3, 4] "accidentally" finds a run (3, 4) at
    # the tail, purely because that adjacent pair happens to appear in
    # increasing order already; it never notices 5 belongs with them.
    # Documented here so a future caller doesn't assume this sorts for
    # them, or that its output means anything on unsorted input.
    assert max_consecutive_run([5, 3, 4]) == 2


def test_thresholds_are_11_and_22():
    assert MAX_LEGITIMATE_RUN == 11
    assert DEGENERATE_FLAG_THRESHOLD == 22


def test_run_at_or_below_max_legitimate_needs_no_review_and_is_not_flagged():
    result = review_policy(11)
    assert result == {"run_length": 11, "flagged_degenerate": False, "needs_manual_review": False}


def test_run_between_max_legitimate_and_flag_threshold_is_reviewed_but_not_flagged():
    # 15 is unprecedented in the reference (> 11) but stays under the
    # doubled auto-flag line (22) -- this is exactly the gap the two
    # separate thresholds exist to cover.
    result = review_policy(15)
    assert result["needs_manual_review"] is True
    assert result["flagged_degenerate"] is False


def test_run_above_flag_threshold_is_both_flagged_and_reviewed():
    result = review_policy(23)
    assert result["needs_manual_review"] is True
    assert result["flagged_degenerate"] is True


def test_run_exactly_at_flag_threshold_is_not_yet_flagged():
    result = review_policy(DEGENERATE_FLAG_THRESHOLD)
    assert result["flagged_degenerate"] is False  # strictly greater than, not >=
    assert result["needs_manual_review"] is True


def test_max_consecutive_run_with_span_matches_length_and_reports_first_tied_span():
    run, span = max_consecutive_run_with_span([3, 4, 5, 10, 11, 12])
    assert run == 3
    assert span == (3, 5)  # first of the two tied 3-runs


def test_max_consecutive_run_with_span_empty():
    assert max_consecutive_run_with_span([]) == (0, None)


def test_per_file_review_policy_needs_both_conditions():
    # Long enough to beat this file's own ceiling (3), but not
    # over-segmenting relative to a dense reference (4 real boundaries
    # in a run of 4 -- ratio 1x, well under 3x): not degenerate.
    result = per_file_review_policy(run_length=4, ref_boundaries_in_span=4, file_max_legitimate_run=3)
    assert result["exceeds_file_max"] is True
    assert result["exceeds_ratio"] is False
    assert result["degenerate"] is False


def test_per_file_review_policy_ratio_alone_is_not_enough():
    # Over-segmenting (ratio 4x) but still within this file's own
    # observed ceiling (5) -- a file where runs of 4 are already
    # legitimate should not flag a run of 4 just for a high ratio.
    result = per_file_review_policy(run_length=4, ref_boundaries_in_span=1, file_max_legitimate_run=5)
    assert result["exceeds_file_max"] is False
    assert result["exceeds_ratio"] is True
    assert result["degenerate"] is False


def test_per_file_review_policy_both_conditions_flags_degenerate():
    result = per_file_review_policy(run_length=12, ref_boundaries_in_span=3, file_max_legitimate_run=5)
    assert result["exceeds_file_max"] is True
    assert result["exceeds_ratio"] is True  # 12 > 3*3=9
    assert result["degenerate"] is True


def test_per_file_review_policy_zero_reference_boundaries_in_span():
    # Any real run vacuously exceeds "more than 3x zero" -- a run with
    # NO real boundaries anywhere in its span is exactly the enumeration
    # failure mode this rule exists to catch.
    result = per_file_review_policy(run_length=4, ref_boundaries_in_span=0, file_max_legitimate_run=3)
    assert result["exceeds_ratio"] is True
    assert result["degenerate"] is True

from sbcsae_degenerate_threshold import max_consecutive_run


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

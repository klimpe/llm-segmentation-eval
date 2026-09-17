import random

import pytest

from masses import assert_comparable, boundaries_to_masses, flags_to_masses, masses_to_boundaries


def test_docstring_example():
    # 10 tokens, boundaries after token 3 and token 7
    flags = [True, False, False, True, False, False, False, True, False, False]
    masses = flags_to_masses(flags)
    assert masses == [3, 4, 3]
    assert sum(masses) == len(flags)
    assert masses_to_boundaries(masses) == {3, 7}


def test_single_segment_no_boundaries():
    flags = [True, False, False, False]
    masses = flags_to_masses(flags)
    assert masses == [4]
    assert masses_to_boundaries(masses) == set()


def test_every_token_is_a_boundary():
    flags = [True, True, True, True]
    masses = flags_to_masses(flags)
    assert masses == [1, 1, 1, 1]
    assert masses_to_boundaries(masses) == {1, 2, 3}


def test_single_token():
    flags = [True]
    masses = flags_to_masses(flags)
    assert masses == [1]
    assert masses_to_boundaries(masses) == set()


def test_empty():
    assert flags_to_masses([]) == []
    assert masses_to_boundaries([]) == set()


def test_first_flag_must_be_true():
    with pytest.raises(ValueError):
        flags_to_masses([False, True, False])


def test_masses_sum_invariant():
    masses = [3, 4, 3]
    assert sum(masses) == 10


def test_assert_comparable_passes_when_sums_match():
    assert_comparable([3, 4, 3], [2, 5, 3])  # different segmentation, same 10 tokens


def test_assert_comparable_raises_on_mismatch():
    with pytest.raises(ValueError, match=r"ref=10 hyp=9"):
        assert_comparable([3, 4, 3], [3, 3, 3])  # hyp lost a token


def test_assert_comparable_reports_extra_tokens():
    with pytest.raises(ValueError, match=r"diff=2"):
        assert_comparable([3, 4, 3], [3, 4, 5])  # hyp invented tokens


@pytest.mark.parametrize("seed", range(50))
def test_round_trip_random(seed):
    rng = random.Random(seed)
    n_tokens = rng.randint(1, 30)

    # Build a random boundary set: positions 1..n_tokens-1 after which a
    # boundary may fall (position i is "after token i", 1-indexed).
    candidate_positions = range(1, n_tokens)
    boundaries = {p for p in candidate_positions if rng.random() < 0.4}

    flags = [i == 0 or (i in boundaries) for i in range(n_tokens)]
    masses = flags_to_masses(flags)

    assert sum(masses) == n_tokens
    assert len(masses) - 1 == len(boundaries)
    assert masses_to_boundaries(masses) == boundaries
    assert boundaries_to_masses(boundaries, n_tokens) == masses


def test_boundaries_to_masses_docstring_example():
    assert boundaries_to_masses({3, 7}, 10) == [3, 4, 3]


def test_boundaries_to_masses_empty():
    assert boundaries_to_masses(set(), 5) == [5]


def test_boundaries_to_masses_every_position():
    assert boundaries_to_masses({1, 2, 3}, 4) == [1, 1, 1, 1]


def test_boundaries_to_masses_rejects_zero_position():
    with pytest.raises(ValueError, match=r"out of range"):
        boundaries_to_masses({0, 3}, 10)


def test_boundaries_to_masses_rejects_position_at_or_past_n():
    with pytest.raises(ValueError, match=r"out of range"):
        boundaries_to_masses({3, 10}, 10)


def test_boundaries_to_masses_rejects_non_positive_n():
    with pytest.raises(ValueError, match=r"n must be positive"):
        boundaries_to_masses(set(), 0)


@pytest.mark.parametrize("seed", range(50))
def test_boundaries_to_masses_inverts_masses_to_boundaries_random(seed):
    rng = random.Random(1000 + seed)
    n_tokens = rng.randint(1, 30)
    candidate_positions = range(1, n_tokens)
    boundaries = {p for p in candidate_positions if rng.random() < 0.4}
    masses = boundaries_to_masses(boundaries, n_tokens)
    assert sum(masses) == n_tokens
    assert masses_to_boundaries(masses) == boundaries

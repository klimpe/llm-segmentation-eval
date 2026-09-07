"""Perturbation-based sanity checks for the metrics, mirroring the
damaged.py approach from Peshkov & Prevot (2014): take a reference, damage
it in known ways, and confirm each metric responds proportionally. If a
metric misbehaves here, the bug is in the metric, not in the model.
"""
import random

import pytest

from masses import masses_to_boundaries
from metrics import boundary_f1, boundary_precision_recall, boundary_similarity, window_diff

# 36 tokens, 10 segments, boundaries at {3,7,10,15,17,23,24,28,31}
REF = [3, 4, 3, 5, 2, 6, 1, 4, 3, 5]


def masses_from_boundaries(boundaries: set[int], n_tokens: int) -> list[int]:
    ordered = sorted(boundaries)
    masses = []
    prev = 0
    for b in ordered:
        masses.append(b - prev)
        prev = b
    masses.append(n_tokens - prev)
    return masses


def shift_one_boundary(ref_masses: list[int]) -> list[int]:
    """Move one boundary by exactly one position: a classic near-miss."""
    n = sum(ref_masses)
    boundaries = masses_to_boundaries(ref_masses)
    for b in sorted(boundaries):
        if b + 1 <= n - 1 and (b + 1) not in boundaries:
            shifted = (boundaries - {b}) | {b + 1}
            return masses_from_boundaries(shifted, n)
    raise ValueError("no boundary can be shifted by one without colliding")


def delete_a_boundary(ref_masses: list[int]) -> list[int]:
    """Merge two adjacent segments: one false negative, no near neighbour."""
    n = sum(ref_masses)
    boundaries = masses_to_boundaries(ref_masses)
    b = sorted(boundaries)[1]  # delete boundary 7, isolated from its neighbours
    return masses_from_boundaries(boundaries - {b}, n)


def add_a_spurious_boundary(ref_masses: list[int]) -> list[int]:
    """Split the first segment: one false positive, no near neighbour."""
    n = sum(ref_masses)
    boundaries = masses_to_boundaries(ref_masses)
    return masses_from_boundaries(boundaries | {1}, n)


def randomize(ref_masses: list[int], rng: random.Random) -> list[int]:
    n = sum(ref_masses)
    boundaries = {p for p in range(1, n) if rng.random() < 0.5}
    return masses_from_boundaries(boundaries, n)


SHIFTED = shift_one_boundary(REF)
DELETED = delete_a_boundary(REF)
ADDED = add_a_spurious_boundary(REF)
RANDOM = randomize(REF, random.Random(0))


def test_damage_functions_preserve_token_count():
    for hyp in (SHIFTED, DELETED, ADDED, RANDOM):
        assert sum(hyp) == sum(REF)


# --- boundary precision/recall/F1 -------------------------------------------


def test_prf_perfect_on_identical():
    assert boundary_precision_recall(REF, REF) == (1.0, 1.0)
    assert boundary_f1(REF, REF) == 1.0


def test_prf_delete_hurts_recall_only():
    precision, recall = boundary_precision_recall(REF, DELETED)
    assert precision == 1.0  # no spurious boundaries
    assert recall == pytest.approx(8 / 9)  # one of nine reference boundaries missing


def test_prf_add_hurts_precision_only():
    precision, recall = boundary_precision_recall(REF, ADDED)
    assert precision == pytest.approx(9 / 10)  # one of ten hyp boundaries is spurious
    assert recall == 1.0  # every reference boundary still present


def test_prf_shift_hurts_both():
    # exact-match P/R cannot tell a one-position shift from an unrelated
    # false positive + false negative: it is blind to "near"
    precision, recall = boundary_precision_recall(REF, SHIFTED)
    assert precision == pytest.approx(8 / 9)
    assert recall == pytest.approx(8 / 9)


def test_prf_randomize_is_worse_than_any_single_damage():
    assert boundary_f1(REF, RANDOM) < boundary_f1(REF, SHIFTED)
    assert boundary_f1(REF, RANDOM) < boundary_f1(REF, DELETED)
    assert boundary_f1(REF, RANDOM) < boundary_f1(REF, ADDED)


# --- WindowDiff --------------------------------------------------------------


def test_window_diff_zero_on_identical():
    assert window_diff(REF, REF) == 0.0


def test_window_diff_orders_damage_by_severity():
    wd_shift = window_diff(REF, SHIFTED)
    wd_delete = window_diff(REF, DELETED)
    wd_add = window_diff(REF, ADDED)
    wd_random = window_diff(REF, RANDOM)

    for wd in (wd_shift, wd_delete, wd_add):
        assert 0.0 < wd < wd_random


# --- Boundary Similarity ------------------------------------------------------


def test_boundary_similarity_one_on_identical():
    assert boundary_similarity(REF, REF) == 1.0


def test_boundary_similarity_gives_partial_credit_for_near_miss():
    # hand-derived (n_t=2, default): shifting boundary 3->4 is absorbed as one
    # transposition of span 1 (matches=8, additions=0, transpositions=1,
    # weighted cost = 1/n_t = 0.5): value = (9 - 0.5) / 9
    assert boundary_similarity(REF, SHIFTED) == pytest.approx(8.5 / 9)


def test_boundary_similarity_full_penalty_for_isolated_miss():
    # deleting boundary 7 has no adjacent mismatch to pair with: it is a
    # plain addition, full cost 1: value = (9 - 1) / 9
    assert boundary_similarity(REF, DELETED) == pytest.approx(8 / 9)
    # adding a spurious boundary at 1: value = (10 - 1) / 10
    assert boundary_similarity(REF, ADDED) == pytest.approx(9 / 10)


def test_boundary_similarity_prefers_near_miss_over_isolated_miss():
    # this is the whole point of Boundary Similarity over plain P/R: a
    # one-position shift is scored as a smaller error than an isolated
    # false positive/negative of the same edit-count size
    assert boundary_similarity(REF, SHIFTED) > boundary_similarity(REF, DELETED)
    assert boundary_similarity(REF, SHIFTED) > boundary_similarity(REF, ADDED)


def test_boundary_similarity_randomize_is_worst():
    assert boundary_similarity(REF, RANDOM) < boundary_similarity(REF, SHIFTED)
    assert boundary_similarity(REF, RANDOM) < boundary_similarity(REF, DELETED)
    assert boundary_similarity(REF, RANDOM) < boundary_similarity(REF, ADDED)


@pytest.mark.parametrize("seed", range(20))
def test_metrics_agree_random_is_worse_than_random_damage(seed):
    """Broader sweep: any single-boundary perturbation should score better
    than a fully randomized segmentation of the same document, across many
    random references and random seeds."""
    rng = random.Random(seed)
    n = rng.randint(15, 60)
    flags = [True] + [rng.random() < 0.3 for _ in range(n - 1)]
    from masses import flags_to_masses

    ref = flags_to_masses(flags)
    if len(ref) < 3:
        pytest.skip("too few segments to damage meaningfully")

    try:
        shifted = shift_one_boundary(ref)
    except ValueError:
        pytest.skip("no shiftable boundary in this random reference")
    rand_hyp = randomize(ref, rng)

    assert boundary_similarity(ref, rand_hyp) <= boundary_similarity(ref, shifted)
    assert window_diff(ref, rand_hyp) >= window_diff(ref, shifted)

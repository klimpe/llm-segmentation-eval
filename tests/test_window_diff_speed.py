"""Equivalence proof for metrics.window_diff's optimised (O(n)) sliding-
window implementation against the previous, unoptimised one (O(n_windows
* (|ref_b| + |hyp_b|)), effectively O(n^2) at this corpus's boundary
density) it replaced. CLAUDE.md forbids changing a metric's DEFINITION
("do not refactor or improve the metric definitions to be more elegant");
this only proves the implementation change preserves it exactly.

_window_diff_naive below is a verbatim copy of the implementation
metrics.window_diff had before the optimisation (see git history) --
kept here, not in metrics.py, since it exists only to be compared
against, not to be part of the shipped API.

Slow: 10,000 random (ref, hyp) mass pairs with n_tokens spanning this
corpus's own observed document-length range (reports/
phase2_per_file_stats.csv: 1,824-6,628 words), run against the O(n^2)
naive implementation, takes on the order of tens of minutes. Skipped by
default (no pytest config/markers added, per CLAUDE.md's "no ...
packaging" -- this project has none); run explicitly with
`RUN_SLOW_TESTS=1 pytest tests/test_window_diff_speed.py` after any
change to window_diff, the same "only needs to happen once per
corpus-affecting change" policy CLAUDE.md already applies to the
whole-corpus baseline run (reports/phase2_baselines.md).
"""
from __future__ import annotations

import os
import random
import time

import pytest

from masses import assert_comparable, flags_to_masses, masses_to_boundaries
from metrics import window_diff

# Verbatim copy of metrics.window_diff's implementation before the
# optimisation -- do not "clean up" to match the new one; the entire
# point is that this is the OLD code, unmodified.
def _window_diff_naive(ref_masses: list[int], hyp_masses: list[int], k: int | None = None) -> float:
    assert_comparable(ref_masses, hyp_masses)
    n = sum(ref_masses)
    ref_b = masses_to_boundaries(ref_masses)
    hyp_b = masses_to_boundaries(hyp_masses)

    if k is None:
        k = round(n / len(ref_masses) / 2)
        if k <= 1:
            k = 2

    n_windows = n - k
    if n_windows <= 0:
        raise ValueError(f"window size k={k} too large for document of {n} units")

    disagreements = 0
    for start in range(1, n_windows + 1):
        end = start + k  # window covers gap positions [start, end)
        ref_count = sum(1 for b in ref_b if start <= b < end)
        hyp_count = sum(1 for b in hyp_b if start <= b < end)
        disagreements += ref_count != hyp_count

    return disagreements / n_windows


CORPUS_MIN_WORDS = 1824  # reports/phase2_per_file_stats.csv
CORPUS_MAX_WORDS = 6628


def _random_masses(rng: random.Random, n_tokens: int, p: float) -> list[int]:
    flags = [True] + [rng.random() < p for _ in range(n_tokens - 1)]
    return flags_to_masses(flags)


def _random_pairs(n_pairs: int, seed: int):
    rng = random.Random(seed)
    for _ in range(n_pairs):
        n_tokens = rng.randint(CORPUS_MIN_WORDS, CORPUS_MAX_WORDS)
        # A range of boundary densities, not just this corpus's own mean
        # (~1/5, reports/phase2_per_file_stats.csv's median words/segment)
        # -- the proof should hold regardless of density, not just at the
        # one density this corpus happens to have.
        p_ref = rng.uniform(0.03, 0.4)
        p_hyp = rng.uniform(0.03, 0.4)
        yield _random_masses(rng, n_tokens, p_ref), _random_masses(rng, n_tokens, p_hyp)


@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="corpus-scale equivalence proof, ~tens of minutes; set RUN_SLOW_TESTS=1 to run",
)
def test_window_diff_optimized_matches_naive_corpus_scale():
    n_pairs = 10_000
    t_fast = 0.0
    t_naive = 0.0
    for ref, hyp in _random_pairs(n_pairs, seed=20260918):
        t0 = time.perf_counter()
        fast = window_diff(ref, hyp)
        t1 = time.perf_counter()
        naive = _window_diff_naive(ref, hyp)
        t2 = time.perf_counter()
        t_fast += t1 - t0
        t_naive += t2 - t1
        assert fast == naive, f"mismatch: fast={fast!r} naive={naive!r} n={sum(ref)}"
    speedup = t_naive / t_fast if t_fast else float("inf")
    print(
        f"\n{n_pairs} pairs, n in [{CORPUS_MIN_WORDS},{CORPUS_MAX_WORDS}]: "
        f"naive {t_naive:.1f}s, optimized {t_fast:.1f}s, speedup {speedup:.1f}x"
    )


@pytest.mark.parametrize("seed", range(20))
def test_window_diff_optimized_matches_naive_small(seed):
    """Fast, always-on sanity check at small n (not corpus-scale -- see
    the slow test above for that) so a regression here is caught on every
    run, not just when the slow test is explicitly invoked.
    """
    rng = random.Random(seed)
    n = rng.randint(2, 50)
    ref = _random_masses(rng, n, rng.uniform(0.05, 0.5))
    hyp = _random_masses(rng, n, rng.uniform(0.05, 0.5))
    try:
        fast = window_diff(ref, hyp)
    except ValueError:
        pytest.skip("k too large for this random document")
    naive = _window_diff_naive(ref, hyp)
    assert fast == naive

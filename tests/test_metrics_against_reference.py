"""Fuzz-test window_diff and boundary_similarity against the reference
`segeval` implementation (Fournier's own package, pip install segeval).
Not a hard dependency: skipped entirely if segeval isn't installed. Kept as
a regression guard since this is how the metrics were originally validated
during development.
"""
import random

import pytest

from masses import flags_to_masses
from metrics import boundary_similarity, window_diff

segeval = pytest.importorskip("segeval")


def random_masses(rng: random.Random, n_tokens: int) -> list[int]:
    flags = [True] + [rng.random() < 0.35 for _ in range(n_tokens - 1)]
    return flags_to_masses(flags)


@pytest.mark.parametrize("seed", range(100))
def test_window_diff_matches_segeval(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 25)
    ref = random_masses(rng, n)
    hyp = random_masses(rng, n)
    try:
        mine = window_diff(ref, hyp)
    except ValueError:
        pytest.skip("k too large for this random document")
    # segeval's positional args are (hypothesis, reference)
    theirs = float(segeval.window_diff(tuple(hyp), tuple(ref)))
    assert mine == pytest.approx(theirs)


@pytest.mark.parametrize("seed", range(100))
@pytest.mark.parametrize("n_t", [2, 3, 4])
def test_boundary_similarity_matches_segeval(seed, n_t):
    rng = random.Random(seed * 1000 + n_t)
    n = rng.randint(2, 25)
    ref = random_masses(rng, n)
    hyp = random_masses(rng, n)
    mine = boundary_similarity(ref, hyp, n_t=n_t)
    try:
        theirs = float(segeval.boundary_similarity(tuple(ref), tuple(hyp), n_t=n_t))
    except ValueError:
        pytest.skip("segeval chokes on documents with no boundaries on either side")
    assert mine == pytest.approx(theirs)

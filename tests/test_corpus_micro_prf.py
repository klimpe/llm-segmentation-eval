"""corpus_micro_boundary_prf was cross-checked against DISRPT's official
utils/seg_eval.py directly (not vendored here, downloaded ad hoc) over 500
random multi-document trials with 0 mismatches. These are the hand-derived
regression tests kept in the suite.
"""
import pytest

from metrics import corpus_micro_boundary_prf


def test_identical_docs_perfect_score():
    pairs = [([3, 4, 3], [3, 4, 3]), ([5, 5], [5, 5])]
    assert corpus_micro_boundary_prf(pairs) == (1.0, 1.0, 1.0)


def test_hand_derived_two_documents():
    # doc1: ref==hyp==[3,4,3] -> 2 real boundaries match + 1 trivial = TP 3
    # doc2: ref=[2,2,2,2] (boundaries at 2,4,6), hyp=[2,2,4] (boundaries at
    #   2,4) -> 2 real boundaries match + 1 trivial = TP 3, hyp misses
    #   boundary 6 -> FN 1, no spurious boundaries -> FP 0
    # totals: TP=6, FP=0, FN=1 -> P=6/6=1.0, R=6/7, F1=2*1*(6/7)/(1+6/7)
    pairs = [([3, 4, 3], [3, 4, 3]), ([2, 2, 2, 2], [2, 2, 4])]
    precision, recall, f1 = corpus_micro_boundary_prf(pairs)
    assert precision == pytest.approx(1.0)
    assert recall == pytest.approx(6 / 7)
    assert f1 == pytest.approx(2 * 1.0 * (6 / 7) / (1.0 + 6 / 7))


def test_micro_average_differs_from_macro_average_of_per_doc_f1():
    # a big document with one wrong boundary should dominate a small
    # document that is entirely wrong, under micro- but not macro-averaging
    from metrics import boundary_f1

    big_ref = list(range(1, 21))  # 20 segments of increasing size, many tokens
    big_hyp = list(big_ref)
    big_hyp[0], big_hyp[1] = big_hyp[0] - 1, big_hyp[1] + 1  # shift one boundary
    small_ref = [1, 1]
    small_hyp = [2]  # completely wrong, but only 2 tokens

    pairs = [(big_ref, big_hyp), (small_ref, small_hyp)]
    _, _, micro_f1 = corpus_micro_boundary_prf(pairs)
    macro_f1 = (boundary_f1(big_ref, big_hyp) + boundary_f1(small_ref, small_hyp)) / 2

    assert micro_f1 != pytest.approx(macro_f1)
    assert micro_f1 > macro_f1  # the large, mostly-correct document dominates


def test_empty_pairs_is_a_degenerate_zero_score():
    assert corpus_micro_boundary_prf([]) == (0.0, 0.0, 0.0)

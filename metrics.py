from masses import assert_comparable, masses_to_boundaries


def boundary_precision_recall(ref_masses: list[int], hyp_masses: list[int]) -> tuple[float, float]:
    """Exact-match boundary precision and recall.

    precision = |ref ∩ hyp| / |hyp|, recall = |ref ∩ hyp| / |ref|.
    An empty hyp/ref boundary set yields precision/recall 1.0 if the other
    side is also empty (perfect agreement on "no boundaries"), else 0.0.
    """
    assert_comparable(ref_masses, hyp_masses)
    ref_b = masses_to_boundaries(ref_masses)
    hyp_b = masses_to_boundaries(hyp_masses)
    tp = len(ref_b & hyp_b)

    if hyp_b:
        precision = tp / len(hyp_b)
    else:
        precision = 1.0 if not ref_b else 0.0

    if ref_b:
        recall = tp / len(ref_b)
    else:
        recall = 1.0 if not hyp_b else 0.0

    return precision, recall


def boundary_f1(ref_masses: list[int], hyp_masses: list[int]) -> float:
    precision, recall = boundary_precision_recall(ref_masses, hyp_masses)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def window_diff(ref_masses: list[int], hyp_masses: list[int], k: int | None = None) -> float:
    """WindowDiff (Pevzner & Hearst, 2002).

    Slides a window of k units across the document; penalizes windows where
    ref and hyp disagree on the number of boundaries they contain. Lower is
    better; 0 means no disagreement in any window.

    k defaults to round(mean reference segment length / 2), per the original
    paper, with a floor of 2 (matching the reference `segeval` implementation).
    """
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


def corpus_micro_boundary_prf(pairs: list[tuple[list[int], list[int]]]) -> tuple[float, float, float]:
    """Corpus-level micro-averaged boundary precision/recall/F1 over several
    documents, replicating DISRPT's official `seg_eval.py` exactly: pool
    true/false positives/negatives across every document's tokens (including
    each document's trivial first-token boundary) rather than averaging
    per-document scores. This is what published DISRPT system scores report,
    and it is not the same number as the mean of boundary_f1 over documents
    (that would be a macro average) -- use this specifically when comparing
    against them.

    `pairs` is a list of (ref_masses, hyp_masses) for each document.
    """
    tp = fp = fn = 0
    for ref_masses, hyp_masses in pairs:
        assert_comparable(ref_masses, hyp_masses)
        ref_b = masses_to_boundaries(ref_masses)
        hyp_b = masses_to_boundaries(hyp_masses)
        tp += len(ref_b & hyp_b) + 1  # +1: every document's first token is a trivial match
        fn += len(ref_b - hyp_b)
        fp += len(hyp_b - ref_b)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def boundary_similarity(ref_masses: list[int], hyp_masses: list[int], n_t: int = 2) -> float:
    """Boundary Similarity (Fournier & Inkpen, 2012; Fournier, 2013).

    Boundary edit distance restricted to a single (unlabeled) boundary type:
    each potential boundary position (PB) where ref and hyp disagree is
    either absorbed into a "transposition" with an adjacent disagreeing PB
    (a near-miss, i.e. a boundary shifted by up to n_t - 1 positions, credited
    at partial weight) or counted as a full addition/deletion (zero credit).
    PBs where both sides agree there is no boundary are ignored entirely.
    1.0 = identical segmentations, degrading towards 0.0. n_t=2 (segeval's
    default) means only a shift of exactly one position counts as a
    near-miss.
    """
    assert_comparable(ref_masses, hyp_masses)
    n = sum(ref_masses)
    num_pbs = n - 1
    if num_pbs <= 0:
        return 1.0

    ref_b = masses_to_boundaries(ref_masses)
    hyp_b = masses_to_boundaries(hyp_masses)

    matches = ref_b & hyp_b
    mismatched = ref_b ^ hyp_b

    transposition_spans: list[int] = []
    consumed: set[int] = set()
    for span in range(1, n_t):
        for i in range(1, num_pbs - span + 1):
            j = i + span
            if i in consumed or j in consumed:
                continue
            if i not in mismatched or j not in mismatched:
                continue
            ref_moved = (i in ref_b) != (j in ref_b)
            hyp_moved = (i in hyp_b) != (j in hyp_b)
            if ref_moved and hyp_moved:
                transposition_spans.append(span)
                consumed.add(i)
                consumed.add(j)

    num_transpositions = len(transposition_spans)
    additions = len(mismatched) - 2 * num_transpositions
    num_matches = len(matches)

    denominator = additions + num_transpositions + num_matches
    if denominator == 0:
        return 1.0

    weighted_transpositions = sum(transposition_spans) / n_t
    count_edits = additions + weighted_transpositions
    return (denominator - count_edits) / denominator

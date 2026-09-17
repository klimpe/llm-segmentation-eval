def flags_to_masses(flags: list[bool]) -> list[int]:
    """flags[i] is True if a new segment begins at token i."""
    if not flags:
        return []
    if not flags[0]:
        raise ValueError("flags[0] must be True: the first token always starts a segment")

    masses = []
    current = 0
    for flag in flags:
        if flag and current > 0:
            masses.append(current)
            current = 0
        current += 1
    masses.append(current)
    return masses


def masses_to_boundaries(masses: list[int]) -> set[int]:
    """Positions after which a boundary falls. len == len(masses) - 1."""
    boundaries = set()
    position = 0
    for mass in masses[:-1]:
        position += mass
        boundaries.add(position)
    return boundaries


def boundaries_to_masses(boundaries: set[int], n: int) -> list[int]:
    """Inverse of masses_to_boundaries: reconstruct masses from a boundary
    set and the total token count. Every element of `boundaries` must be a
    valid position (1 <= b < n); out-of-range positions raise rather than
    being silently clipped or ignored.

    Needed whenever a boundary set is edited directly (e.g. removing the
    turn-initial positions before within-turn scoring) and must be turned
    back into masses for the existing mass-based metrics to consume.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    bad = [b for b in boundaries if not (1 <= b < n)]
    if bad:
        raise ValueError(f"boundary positions out of range [1,{n - 1}]: {sorted(bad)}")

    masses = []
    prev = 0
    for b in sorted(boundaries):
        masses.append(b - prev)
        prev = b
    masses.append(n - prev)
    return masses


def assert_comparable(ref_masses: list[int], hyp_masses: list[int]) -> None:
    """Raise ValueError if ref and hyp do not cover the same number of tokens.

    Segmentation metrics assume both segmentations run over the same token
    sequence. If a model drops or invents tokens, that assumption is broken
    and any metric computed on the pair is meaningless — this must be checked
    before scoring, not after.
    """
    ref_total = sum(ref_masses)
    hyp_total = sum(hyp_masses)
    if ref_total != hyp_total:
        raise ValueError(
            f"ref and hyp cover different token counts: "
            f"ref={ref_total} hyp={hyp_total} (diff={hyp_total - ref_total})"
        )

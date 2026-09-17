import pytest

from sbcsae_windows import (
    CORE,
    MARGIN,
    assert_boundaries_each_in_one_region,
    assert_regions_tile,
    build_score_regions,
    region_for_boundary,
)


def test_exact_multiple_of_core():
    regions = build_score_regions(1200)
    assert [(r.score_start, r.score_end) for r in regions] == [(1, 600), (601, 1200)]
    assert regions[0].window_start == 1  # clamped: 1 - 100 < 1
    assert regions[0].window_end == 700  # 600 + 100
    assert regions[1].window_start == 501  # 601 - 100
    assert regions[1].window_end == 1200  # clamped: 1200 + 100 > n


def test_remainder_last_region_shorter():
    regions = build_score_regions(1250)
    assert [(r.score_start, r.score_end) for r in regions] == [(1, 600), (601, 1200), (1201, 1250)]
    assert regions[-1].window_start == 1101  # 1201 - 100
    assert regions[-1].window_end == 1250  # clamped: last region ends at n_tokens, no right margin


def test_single_region_shorter_than_core():
    regions = build_score_regions(300)
    assert [(r.score_start, r.score_end) for r in regions] == [(1, 300)]
    assert regions[0].window_start == 1
    assert regions[0].window_end == 300


def test_first_region_starts_at_word_one_last_ends_at_document_end():
    for n in (300, 600, 601, 1199, 1200, 1201, 6628):
        regions = build_score_regions(n)
        assert regions[0].score_start == 1
        assert regions[-1].score_end == n


@pytest.mark.parametrize("n", [1, 2, 599, 600, 601, 1199, 1200, 1201, 1824, 4347, 6628, 12345])
def test_regions_tile_exactly(n):
    regions = build_score_regions(n)
    assert_regions_tile(regions, n)  # must not raise


def test_rejects_non_positive_n():
    with pytest.raises(ValueError, match="must be positive"):
        build_score_regions(0)
    with pytest.raises(ValueError, match="must be positive"):
        build_score_regions(-5)


def test_assert_regions_tile_catches_a_gap():
    regions = build_score_regions(1200)
    tampered = [regions[0]] + [regions[1].__class__(700, 1200, 600, 1200)]
    with pytest.raises(AssertionError, match="gap or overlap"):
        assert_regions_tile(tampered, 1200)


def test_assert_regions_tile_catches_wrong_start():
    regions = build_score_regions(1200)
    tampered = [regions[0].__class__(2, 600, 1, 700), regions[1]]
    with pytest.raises(AssertionError, match="not 1"):
        assert_regions_tile(tampered, 1200)


def test_boundary_at_seam_belongs_to_the_later_region():
    regions = build_score_regions(1200)
    # boundary 600 is the gap between word 600 (region 1) and word 601
    # (region 2) -- it belongs to region 2, the region where the new
    # segment begins.
    assert region_for_boundary(regions, 600) is regions[1]
    assert region_for_boundary(regions, 599) is regions[0]


@pytest.mark.parametrize("n", [1, 2, 601, 1200, 1250, 4347, 6628])
def test_every_possible_boundary_belongs_to_exactly_one_region(n):
    regions = build_score_regions(n)
    all_boundaries = set(range(1, n))  # every valid boundary position
    assert_boundaries_each_in_one_region(regions, all_boundaries, n)  # must not raise


def test_boundary_out_of_range_rejected():
    regions = build_score_regions(1200)
    with pytest.raises(ValueError, match="out of range"):
        assert_boundaries_each_in_one_region(regions, {0}, 1200)
    with pytest.raises(ValueError, match="out of range"):
        assert_boundaries_each_in_one_region(regions, {1200}, 1200)


def test_core_and_margin_defaults():
    assert CORE == 600
    assert MARGIN == 100

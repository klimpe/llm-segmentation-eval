from run_eval import masked_token_fraction


def test_no_masked_tokens():
    assert masked_token_fraction(["The", "cat", "sat", "."]) == 0.0


def test_all_masked_tokens():
    assert masked_token_fraction(["___", "__", "____"]) == 1.0


def test_partial_masking():
    assert masked_token_fraction(["real", "___", "real", "____"]) == 0.5


def test_single_underscore_counts_as_masked():
    # DISRPT's own "no annotation" placeholder is a single "_"; a masked
    # token is indistinguishable from it by this regex, which is correct:
    # both mean "no real content here"
    assert masked_token_fraction(["_", "real"]) == 0.5


def test_underscore_inside_a_real_token_does_not_count():
    # e.g. a real token like "well_known" or a stray underscore as
    # punctuation must not be misdetected as a masked placeholder
    assert masked_token_fraction(["well_known", "real"]) == 0.0


def test_empty_document():
    assert masked_token_fraction([]) == 0.0

from sbcsae_truncation_position import classify


def test_single_word_iu_is_its_own_category():
    assert classify(0, 1) == "iu_initial_and_final"


def test_first_word_of_a_multi_word_iu():
    assert classify(0, 3) == "iu_initial"


def test_last_word_of_a_multi_word_iu():
    assert classify(2, 3) == "iu_final"


def test_middle_word():
    assert classify(1, 3) == "iu_internal"


def test_two_word_iu_has_no_internal_words():
    assert classify(0, 2) == "iu_initial"
    assert classify(1, 2) == "iu_final"

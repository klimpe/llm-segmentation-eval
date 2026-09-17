from sbcsae_tokenizer import _raw_matches
from sbcsae_word_internal_marks import classify_occurrence


def _classify_all(text: str, symbol: str) -> list[str]:
    matches = _raw_matches(text)
    out = []
    for i, m in enumerate(matches):
        if m.group() == symbol:
            out.append(classify_occurrence(matches, i, text))
    return out


def test_lengthening_sandwiched_mid_word_is_word_internal():
    assert _classify_all("s=o", "=") == ["word_internal"]


def test_lengthening_trailing_a_word_is_word_final():
    assert _classify_all("so= there", "=") == ["word_final"]


def test_lengthening_isolated_is_standalone():
    assert _classify_all("uh = huh", "=") == ["standalone"]


def test_lengthening_leading_a_word_is_standalone():
    # Documented tokeniser wrinkle: glued only on the trailing side (to
    # the word that follows), not sandwiched -- its own Cue item, same
    # "already renders fine" bucket as a truly isolated mark.
    assert _classify_all("uh =huh", "=") == ["standalone"]


def test_doubled_cue_run_both_marks_are_word_internal():
    assert _classify_all("b==itch", "=") == ["word_internal", "word_internal"]


def test_glottal_stop_word_internal():
    assert _classify_all("fa%st", "%") == ["word_internal"]


def test_booster_standalone_leading():
    assert _classify_all("!Ron said hi", "!") == ["standalone"]


def test_mixed_iu_classifies_each_occurrence_independently():
    # "ho=me" sandwiched, "so=" trailing, "uh" then isolated "="
    text = "ho=me and so= and uh = huh"
    assert _classify_all(text, "=") == ["word_internal", "word_final", "standalone"]

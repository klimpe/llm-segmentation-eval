"""Phase 2 stage 4, step 3a: hand-written tokeniser validation.

One case per marker class (tier 1, tier 2, tier 3, and the two documented
transcription patterns explicitly called out for careful handling), plus
the exact set of extra cases CLAUDE.md asks for. For each: raw text, the
words condition A and B must agree on, and a sanity check on the
condition-B rendering.

Several tier-2 marker classes never occur in the real corpus (accent caret/
backtick, latching, semicolon booster -- confirmed zero occurrences in the
phase 2 stage 4 step 1 marker inventory). Those are still exercised here,
hand-written, since the rule exists in CLAUDE.md regardless of whether the
corpus happens to use it.
"""
import pytest

from sbcsae_tokenizer import Boundary, Condition, Cue, TokenizeError, render, tokenize, words_only


def a_words(raw: str) -> list[str]:
    return [w.text for w in words_only(tokenize(raw))]


def assert_ab_identical(raw: str):
    """The word sequence (identity, count, order) must not depend on
    which cues get rendered -- there is only one tokenize(), so this is
    definitional here, but the assertion documents the contract."""
    items = tokenize(raw)
    a = [w.text for w in words_only(items)]
    b = [w.text for w in words_only(items)]  # same Word objects either way
    assert a == b
    return a


# --- exact cases requested in the task -----------------------------------

def test_crossing_nested_quality_spans():
    raw = "<@<HI well yeah @> HI>"
    words = assert_ab_identical(raw)
    assert words == ["well", "yeah"]
    assert render(tokenize(raw), Condition.A) == "well yeah"
    assert render(tokenize(raw), Condition.B) == "well yeah"


def test_numbered_overlap_bracket():
    raw = "[2 right 2]"
    words = assert_ab_identical(raw)
    assert words == ["right"]


def test_timed_pause():
    raw = "...(1.2)"
    items = tokenize(raw)
    assert words_only(items) == []
    assert render(items, Condition.A) == ""
    assert render(items, Condition.B) == "...(1.2)"


def test_breath_in_next_to_capitalised_vocal_noise():
    # The exact pitfall CLAUDE.md calls out: (H) must not be consumed by
    # the generic capitalised-vocal-noise (tier-1) rule.
    raw = "(H) next to (TSK)"
    words = assert_ab_identical(raw)
    assert words == ["next", "to"]
    assert render(tokenize(raw), Condition.B) == "(H) next to"


def test_laughter_run_alone():
    raw = "@@@"
    items = tokenize(raw)
    assert words_only(items) == []
    assert render(items, Condition.A) == ""
    assert render(items, Condition.B) == ""


def test_at_sign_inside_a_word():
    raw = "yeah@"
    words = assert_ab_identical(raw)
    assert words == ["yeah"]


def test_word_internal_lengthening():
    raw = "s=o"
    words = assert_ab_identical(raw)
    assert words == ["so"]
    assert render(tokenize(raw), Condition.B) == "s=o"


def test_word_truncation():
    raw = "y-"
    words = assert_ab_identical(raw)
    assert words == ["y-"]


def test_hyphenated_compound():
    raw = "twenty-two"
    words = assert_ab_identical(raw)
    assert words == ["twenty-two"]


def test_indecipherable_x_alone():
    raw = "X"
    words = assert_ab_identical(raw)
    assert words == ["X"]


def test_indecipherable_x_in_quality_span():
    raw = "<X right X>"
    words = assert_ab_identical(raw)
    assert words == ["right"]


def test_code_switch_span():
    raw = "<L2 si L2>"
    words = assert_ab_identical(raw)
    assert words == ["si"]


def test_iu_that_is_only_breath():
    raw = "(H)"
    items = tokenize(raw)
    assert words_only(items) == []
    assert render(items, Condition.B) == "(H)"


def test_iu_that_is_only_a_pause():
    raw = "..."
    items = tokenize(raw)
    assert words_only(items) == []
    assert render(items, Condition.B) == "..."


# --- one case per remaining marker class ---------------------------------

def test_plain_overlap_bracket():
    assert assert_ab_identical("[right there]") == ["right", "there"]


def test_research_comment_removed_with_content():
    assert assert_ab_identical("((DOG BARKS)) hello") == ["hello"]


def test_short_pause():
    items = tokenize("well .. yeah")
    assert [w.text for w in words_only(items)] == ["well", "yeah"]
    assert render(items, Condition.B) == "well .. yeah"


def test_long_pause():
    items = tokenize("well ... yeah")
    assert render(items, Condition.B) == "well ... yeah"


def test_breath_out():
    items = tokenize("(Hx) well")
    assert words_only(items)[0].text == "well"
    assert render(items, Condition.B) == "(Hx) well"


def test_latching_synthetic():
    # Zero occurrences in the corpus (step 1 inventory), hand-written per
    # the documented rule regardless.
    items = tokenize("well (0) yeah")
    assert [w.text for w in words_only(items)] == ["well", "yeah"]
    assert render(items, Condition.B) == "well (0) yeah"


def test_accent_caret_synthetic():
    items = tokenize("^word here")
    assert [w.text for w in words_only(items)] == ["word", "here"]


def test_accent_backtick_synthetic():
    items = tokenize("`word here")
    assert [w.text for w in words_only(items)] == ["word", "here"]


def test_booster_bang():
    items = tokenize("!word here")
    assert [w.text for w in words_only(items)] == ["word", "here"]


def test_booster_semicolon_synthetic():
    items = tokenize(";word here")
    assert [w.text for w in words_only(items)] == ["word", "here"]


def test_breath_lowercase_h():
    items = tokenize("(h) word")
    assert [w.text for w in words_only(items)] == ["word"]


def test_breath_lowercase_hx():
    items = tokenize("word (hx) here")
    assert [w.text for w in words_only(items)] == ["word", "here"]


def test_breath_out_mixed_case_hx():
    items = tokenize("word (HX) here")
    assert [w.text for w in words_only(items)] == ["word", "here"]


def test_lowercase_vocal_noise_dropped():
    items = tokenize("(throat) word")
    assert [w.text for w in words_only(items)] == ["word"]


def test_mixed_case_vocal_noise_dropped():
    items = tokenize("(COUGh) word")
    assert [w.text for w in words_only(items)] == ["word"]


def test_breath_paren_lengthening_uppercase():
    items = tokenize("(H=) word")
    assert [w.text for w in words_only(items)] == ["word"]
    assert [it.kind for it in items if isinstance(it, Cue)][:2] == ["breath_in", "lengthening"]


def test_breath_paren_lengthening_lowercase():
    items = tokenize("(h=) word")
    assert [it.kind for it in items if isinstance(it, Cue)][:2] == ["breath_in", "lengthening"]


def test_breath_paren_lengthening_hx():
    items = tokenize("(Hx=) word")
    assert [it.kind for it in items if isinstance(it, Cue)][:2] == ["breath_out", "lengthening"]


def test_empty_parens_dropped():
    items = tokenize("@() word")
    assert [w.text for w in words_only(items)] == ["word"]


def test_yawn_named_exception():
    items = tokenize("(YAWN0 Unhunh,")
    assert [w.text for w in words_only(items)] == ["Unhunh"]


def test_stray_close_paren_named_exception():
    items = tokenize("[Look okay)].")
    assert [w.text for w in words_only(items)] == ["Look", "okay"]


def test_stray_close_paren_elsewhere_still_raises():
    # Not the SBC024 case -- must not become a general orphan-) rule.
    with pytest.raises(TokenizeError):
        tokenize("[Look fine)].")


def test_overlap_leftover_digit_after_close():
    items = tokenize("[2I mean2, yeah")
    assert [w.text for w in words_only(items)] == ["I", "mean", "yeah"]


def test_overlap_leftover_digit_before_open():
    items = tokenize("2[cause I2] only")
    assert [w.text for w in words_only(items)] == ["cause", "I", "only"]


def test_overlap_leftover_digit_trailing_extra():
    items = tokenize("[2(H)2]1 .. life")
    assert [w.text for w in words_only(items)] == ["life"]


def test_overlap_leftover_digit_catches_non_glued_float_junk_too():
    # S1e's generic digit catch-all is reached only after every specific
    # rule above (including S1a's glued lost-initial-letter form) has had
    # first claim -- a NON-glued "0.000000e+00" (space before "word", so
    # S1a's lookahead doesn't apply) doesn't raise any more: the digit runs
    # are dropped as leftovers, and the "e" between them, not glued to
    # either digit run's absence, surfaces as its own one-letter word
    # (unlike S1a's glued form, nothing here identifies "e" as part of a
    # single artifact to consume whole).
    items = tokenize("0.000000e+00 word")
    assert [w.text for w in words_only(items)] == ["e", "word"]


def test_glottal_stop():
    items = tokenize("coming%, yeah")
    assert [w.text for w in words_only(items)] == ["coming", "yeah"]


def test_pitch_backslash_synthetic():
    items = tokenize(r"okay\ yeah")
    assert [w.text for w in words_only(items)] == ["okay", "yeah"]


def test_iu_truncation_after_word_no_space():
    # A word directly abutting IU truncation with no space must not have
    # one hyphen eaten as word-truncation, leaving the other orphaned.
    items = tokenize("and you're--")
    words = words_only(items)
    assert [w.text for w in words] == ["and", "you're"]
    boundaries = [it for it in items if isinstance(it, Boundary)]
    assert any(b.kind == "iu_truncation" for b in boundaries)
    # Never rendered, in either condition (a Boundary, not a Cue).
    assert render(items, Condition.B) == "and you're"


def test_continuity_punctuation_not_a_token():
    items = tokenize("okay, well. really?")
    assert [w.text for w in words_only(items)] == ["okay", "well", "really"]
    assert render(items, Condition.B) == "okay well really"


# --- patterns that must raise, per step 1 findings ------------------------

@pytest.mark.parametrize(
    "raw",
    [
        "~ Mae",  # disguise prefix NOT immediately followed by a letter (a
        # space intervenes) -- only the glued letter-prefix case is
        # authorised (see S2 tests below).
        "KENDRA: text",  # colon: not a documented marker (a settled reader bug used to
        # leak this into IU text; the reader is now fixed so this string
        # should never actually reach the tokeniser -- but the tokeniser
        # itself still has no rule for a bare colon and must still raise
        # if handed one directly).
        "Oh,\x7f",  # stray control byte
        "((RANDOM_COMMENT) word",  # a single-paren-closed researcher comment
        # that is NOT the one named exception (DOG_BARKING_BEGINS) -- still
        # raises rather than silently accepting any malformed comment.
    ],
)
def test_undocumented_patterns_raise(raw):
    with pytest.raises(TokenizeError):
        tokenize(raw)


# --- authorised: disguise prefixes, <%...%>, the float artifact ----------

def test_disguise_prefix_tilde():
    items = tokenize("~Mae was here")
    assert [w.text for w in words_only(items)] == ["Mae", "was", "here"]


def test_disguise_prefix_hash():
    items = tokenize("went to [#Deutsch]")
    assert [w.text for w in words_only(items)] == ["went", "to", "Deutsch"]


def test_disguise_prefix_star():
    items = tokenize("*Dorsen's")
    assert [w.text for w in words_only(items)] == ["Dorsen's"]


def test_percent_span_tag():
    items = tokenize("it takes <% like %>")
    assert [w.text for w in words_only(items)] == ["it", "takes", "like"]


def test_double_angle_zero_content_wrap():
    items = tokenize("<<THUMP>> like that")
    assert [w.text for w in words_only(items)] == ["like", "that"]


def test_double_angle_open_close_with_content():
    items = tokenize("<<SNAP just SNAP>> like that")
    assert [w.text for w in words_only(items)] == ["just", "like", "that"]


def test_double_angle_mismatched_names_not_paired():
    # No pairing: open and close are each stripped on their own; a
    # genuine name mismatch (S3b) must not raise or be treated specially.
    items = tokenize("<<VOMIT-SOUND real word VOMIT-NOISE>>")
    assert [w.text for w in words_only(items)] == ["real", "word"]


def test_double_angle_multiword_underscore_tag_name():
    items = tokenize("<<WATER_RUNNING_AND_DISH_NOISE>> quiet now")
    assert [w.text for w in words_only(items)] == ["quiet", "now"]


def test_word_gloss_suffix_no_parens():
    # good_/god/ -- the phonetic respelling is dropped with its "_", the
    # orthographic word before it is kept.
    before = tokenize("good_/god/ was said")
    assert [w.raw for w in words_only(before)] == ["good", "was", "said"]
    assert [w.text for w in words_only(before)] == ["good", "was", "said"]


def test_word_gloss_suffix_with_parens():
    items = tokenize("cello_(/cheller/) is nice")
    assert [w.text for w in words_only(items)] == ["cello", "is", "nice"]


def test_bare_phonetic_gloss_standalone():
    items = tokenize("The /pub/ Generation")
    assert [w.text for w in words_only(items)] == ["The", "Generation"]


def test_underscore_word_internal_kept_literally():
    items = tokenize("nineteen_ninety_three happened")
    assert [w.text for w in words_only(items)] == ["nineteen_ninety_three", "happened"]


def test_underscore_iu_truncation_run():
    # SBC012/SBC013's "__" == elsewhere's "--": confirmed this session
    # (same 100% IU-final position signature as "--").
    items = tokenize("well __")
    assert [w.text for w in words_only(items)] == ["well"]
    assert [it.kind for it in items if isinstance(it, Boundary)] == ["underscore_iu_truncation"]


def test_underscore_iu_truncation_run_no_words():
    items = tokenize("__")
    assert words_only(items) == []


def test_underscore_word_truncation():
    # SBC012/SBC013's "word_" == elsewhere's "word-".
    items = tokenize("some t_ thing")
    assert [w.text for w in words_only(items)] == ["some", "t-", "thing"]


def test_hyphen_compound_split_by_delimiter():
    # "third]-graders": the overlap-close bracket is incidental; the
    # hyphen is the compound's own and the word continues through it.
    items = tokenize("[third]-graders are here")
    assert [w.text for w in words_only(items)] == ["third-graders", "are", "here"]


def test_hyphen_compound_split_by_delimiter_word_final():
    # "[Degener]- --": the bracket displaces the word's own truncation
    # hyphen but nothing follows it -- completes the word right there,
    # same mechanism as the continuing case, just nothing to continue
    # into.
    items = tokenize("[Degener]- --")
    assert [w.text for w in words_only(items)] == ["Degener-"]


def test_hyphen_leading_word_after_pause():
    # "eighty .. -three": mirror of the trailing "y-" truncation form.
    items = tokenize("eighty .. -three")
    assert [w.text for w in words_only(items)] == ["eighty", "-three"]


def test_real_corpus_isolated_hyphen_between_truncation_and_iu_truncation():
    # ".. s- - --": a truncated word ("s-", the word pattern's own
    # trailing-hyphen support, not displaced_trunc at all), an isolated
    # hyphen (space on both sides), and IU truncation -- three distinct
    # authorised shapes in one real IU, previously a raise wholesale.
    items = tokenize(".. s- - --")
    assert [w.text for w in words_only(items)] == ["s-"]
    assert [it.kind for it in items if isinstance(it, Boundary)] == [
        "isolated_hyphen",
        "iu_truncation",
    ]


def test_isolated_hyphen_removed_both_conditions():
    items = tokenize("okay - well")
    words = words_only(items)
    assert [w.text for w in words] == ["okay", "well"]
    assert [it.kind for it in items if isinstance(it, Boundary)] == ["isolated_hyphen"]
    assert render(items, Condition.B) == "okay well"


def test_underscore_trunc_requires_open_word():
    # Not authorised: "_" glued to a mark, not a word (e.g. "%_you") --
    # the hypothesis covers word_, not mark_word.
    with pytest.raises(TokenizeError):
        tokenize("coming%_you know")


def test_plus_dropped_inside_tag_span():
    items = tokenize("<<POUND +money POUND>>")
    assert [w.text for w in words_only(items)] == ["money"]


def test_plus_fuses_mid_word():
    items = tokenize("ob+jecting to that")
    assert [w.text for w in words_only(items)] == ["objecting", "to", "that"]


def test_plus_standalone_dropped():
    items = tokenize("+money.")
    assert [w.text for w in words_only(items)] == ["money"]


def test_jason_hash_digit_named_exception():
    items = tokenize("[#5Jason #Dill5],")
    assert [w.text for w in words_only(items)] == ["Jason", "Dill"]


def test_stacked_disguise_prefix_named_exception():
    items = tokenize("*#Vodnoy,")
    assert [w.text for w in words_only(items)] == ["Vodnoy"]


def test_star_trailing_named_exception():
    items = tokenize("X[3X3]*")
    words = words_only(items)
    assert len(words) == 1
    assert words[0].text == "XX"


def test_single_angle_zero_content_wrap():
    items = tokenize("<HUMMING> word")
    assert [w.text for w in words_only(items)] == ["word"]


def test_single_angle_nested_zero_content():
    items = tokenize("<F<VOX> word VOX>,")
    assert [w.text for w in words_only(items)] == ["word"]


def test_angle_close_bare_missing_name():
    # "<VOX Ugh VOX >.": the transcriber didn't repeat the name before
    # ">", just a bare ">" after a space -- stripped, no pairing attempted
    # (so the un-glued repeated "VOX" is not specially recognised either,
    # same "no pairing" scope as double-angle).
    items = tokenize("<VOX Ugh VOX >.")
    assert [w.text for w in words_only(items)] == ["Ugh", "VOX"]


def test_double_angle_open_only_no_close_in_iu():
    # A tag opened here and closed in a later IU: no pairing required, no
    # raise just because this IU's close isn't visible.
    items = tokenize("<<SNAP like that")
    assert [w.text for w in words_only(items)] == ["like", "that"]


def test_float_artifact_glued_to_word():
    items = tokenize("0.000000e+00verything was great")
    # Stripped, not reconstructed: the remaining letters are kept as-is.
    assert [w.text for w in words_only(items)] == ["verything", "was", "great"]


def test_float_artifact_uppercase_e():
    items = tokenize("0.000000E+00specially of course")
    assert [w.text for w in words_only(items)] == ["specially", "of", "course"]


def test_float_artifact_no_exponent():
    # Same corruption, exponent tail itself lost: "0.000000or" -> "or".
    items = tokenize("0.000000or] .. Or")
    assert [w.text for w in words_only(items)] == ["or", "Or"]


def test_bare_zero_lost_letter():
    items = tokenize("0h, 0eople")
    assert [w.text for w in words_only(items)] == ["h", "eople"]


def test_bare_zero_mid_word():
    items = tokenize("r0h=,")
    assert [w.text for w in words_only(items)] == ["rh"]


def test_zero_before_hyphen_still_raises():
    # Not a lowercase letter next -- outside the authorised shape.
    with pytest.raises(TokenizeError):
        tokenize("0- le- --")


# --- authorised compounds of documented marks (stage 4 follow-up S4) -----

def test_truncation_displaced_by_lengthening_stays_with_word():
    # "b=-": the truncation hyphen is separated from the word by a
    # lengthening mark, but still belongs to the word, not a new tier.
    items = tokenize("is I kinda had a b=- general idea,")
    assert [w.text for w in words_only(items)] == [
        "is", "I", "kinda", "had", "a", "b-", "general", "idea",
    ]
    b_word = [w for w in words_only(items) if w.text == "b-"][0]
    assert b_word.raw == "b=-"


def test_truncation_displaced_by_glottal_stays_with_word():
    items = tokenize("that g%- word")
    assert [w.text for w in words_only(items)] == ["that", "g-", "word"]


def test_mark_only_truncation_counted_not_decided_as_word():
    # "%-" with no letters at all: not folded into any word, not silently
    # dropped either -- surfaces as its own Cue so it can be counted.
    items = tokenize("well %- yeah")
    assert [w.text for w in words_only(items)] == ["well", "yeah"]
    cues = [it for it in items if isinstance(it, Cue)]
    assert any(c.kind == "displaced_truncation" for c in cues)


def test_glottal_breath_compound():
    items = tokenize("(%Hx) word")
    cues = [it for it in items if isinstance(it, Cue)]
    assert [c.kind for c in cues] == ["glottal", "breath_out"]
    assert [w.text for w in words_only(items)] == ["word"]


def test_breath_bracket_lengthening_compound():
    items = tokenize("(Hx[=]) word")
    cues = [it for it in items if isinstance(it, Cue)]
    assert [c.kind for c in cues] == ["breath_out", "lengthening"]
    assert [w.text for w in words_only(items)] == ["word"]


def test_dog_barking_named_exception():
    # SBC029's one malformed researcher comment, missing its second ")".
    items = tokenize("((DOG_BARKING_BEGINS) word")
    assert [w.text for w in words_only(items)] == ["word"]


def test_research_comment_still_requires_double_close_normally():
    items = tokenize("((TSK TSK)) word")
    assert [w.text for w in words_only(items)] == ["word"]


# --- reference-segment dropping (S2e) -------------------------------------

def test_reference_segments_drops_zero_word_ius():
    from sbcsae_tokenizer import reference_segments

    doc = [tokenize("(H)"), tokenize("well yeah"), tokenize("...")]
    kept = reference_segments(doc)
    assert len(kept) == 1
    assert [w.text for w in words_only(kept[0])] == ["well", "yeah"]


def test_reference_segments_identical_under_a_and_b():
    from sbcsae_tokenizer import reference_segments

    doc = [tokenize("(H)"), tokenize("well yeah"), tokenize("...")]
    kept = reference_segments(doc)
    a_words = [w.text for items in kept for w in words_only(items)]
    b_words = [w.text for items in kept for w in words_only(items)]
    assert a_words == b_words == ["well", "yeah"]

"""Synthetic-IU tests for sbcsae_llm.py's document structure and
"candidate 2" rendering. No corpus files read here -- IntonationUnits are
built by hand, including a literal-text regression drawn from the actual
first-15-IU SBC001 rendering sketch already checked by hand in the prior
session, so a future change to tokenize()'s rule table or to this
module's grouping logic is caught here without needing the corpus.
"""
import re

from sbcsae_reader import IntonationUnit
from sbcsae_tokenizer import Condition, Cue
from sbcsae_llm import build_document_structure, render_document, render_turn_line, render_window


def iu(speaker, text):
    return IntonationUnit(speaker=speaker, start=0.0, end=0.0, text=text)


def test_turns_group_consecutive_same_speaker_ius():
    units = [
        iu("A", "one two"),
        iu("A", "three"),  # same speaker: merges into turn A's items, not a new turn
        iu("B", "four five six"),
        iu("A", "seven"),  # speaker returns: a NEW turn, not merged with the first
    ]
    doc = build_document_structure("TEST", units)
    assert [t.speaker for t in doc.turns] == ["A", "B", "A"]
    assert [t.n_words for t in doc.turns] == [3, 3, 1]
    assert [t.start_index for t in doc.turns] == [1, 4, 7]
    assert doc.words == ["one", "two", "three", "four", "five", "six", "seven"]
    assert doc.n_tokens == 7


def test_ref_masses_and_turn_boundaries():
    units = [
        iu("A", "one two"),
        iu("A", "three"),
        iu("B", "four five six"),
        iu("A", "seven"),
    ]
    doc = build_document_structure("TEST", units)
    # IU-level masses: "one two" (2), "three" (1), "four five six" (3), "seven" (1)
    assert doc.ref_masses == [2, 1, 3, 1]
    # boundaries at 2, 3, 6 (masses_to_boundaries convention); only 3 and 6
    # are turn (speaker) changes -- 2 is a within-turn IU boundary (A -> A).
    assert doc.turn_boundaries == {3, 6}


def test_zero_word_iu_is_dropped_and_does_not_start_a_turn():
    units = [
        iu("A", "(H)"),  # zero-word: a bare breath cue, no real speech
        iu("A", "hello"),
    ]
    doc = build_document_structure("TEST", units)
    assert len(doc.turns) == 1
    assert doc.turns[0].n_words == 1
    assert doc.words == ["hello"]
    assert doc.ref_masses == [1]


def test_first_reference_segment_never_a_turn_boundary():
    units = [iu("A", "hello there")]
    doc = build_document_structure("TEST", units)
    assert doc.turn_boundaries == set()  # nothing precedes the first turn


def test_condition_a_is_condition_b_with_cues_removed():
    units = [iu("LYNNE", "(H) Well, we're gonna go (Hx)")]
    doc = build_document_structure("TEST", units)
    turn = doc.turns[0]
    a = render_turn_line(turn, Condition.A)
    b = render_turn_line(turn, Condition.B)
    assert a != b  # the cues must actually appear in B for this to be a real check
    # Stripping every raw Cue string out of B's pieces reproduces A exactly --
    # same line, same indices, same label, only the cues differ.
    cue_raws = {it.raw for it in turn.items if isinstance(it, Cue)}
    b_without_cues = " ".join(p for p in b.split(" ") if p not in cue_raws)
    assert b_without_cues == a


def test_words_are_indexed_cues_are_not():
    units = [iu("X", "(H) hi there")]
    doc = build_document_structure("TEST", units)
    b = render_turn_line(doc.turns[0], Condition.B)
    assert b == "X: (H) 1:hi 2:there"  # already lowercase, so no change from the lowercasing rule


def test_indices_are_global_across_turns():
    units = [iu("A", "one two"), iu("B", "three four")]
    doc = build_document_structure("TEST", units)
    assert render_turn_line(doc.turns[0], Condition.A) == "A: 1:one 2:two"
    assert render_turn_line(doc.turns[1], Condition.A) == "B: 3:three 4:four"


def test_render_document_first_15_ius_of_sbc001_condition_a():
    # Literal IU texts from corpora/sbcsae/TRN/SBC001.trn lines 1-15
    # (as read by sbcsae_reader; hand-transcribed here so this test needs
    # no corpus file). Matches the rendering sketch already verified by
    # hand against the real file in the prior session.
    units = [
        iu("LENORE", "... So you don't need to go ... borrow equipment from anybody,"),
        iu("LENORE", "to --"),
        iu("LENORE", "... to do the feet?"),
        iu("LENORE", "... [Do the hooves]?"),
        iu("LYNNE", "[(H)=] <YWN Well,"),
        iu("LYNNE", "we're gonna have to find somewhere,"),
        iu("LYNNE", "to get,"),
        iu("LYNNE", "(Hx) ... something (Hx) YWN>."),
        iu("DORIS", ".. So,"),
        iu("DORIS", "[~Mae-] --"),
        iu("LYNNE", "[I'm gonna] (Hx) --"),
        iu("DORIS", "[2~Mae ~Lynne XX2]"),
        iu("LYNNE", "[2(H) We're not2] gonna do the feet today,"),
        iu("LYNNE", "I'm gonna wait till like,"),
        iu("LYNNE", "early in the morning=,"),
    ]
    doc = build_document_structure("SBC001", units)
    # LENORE's four IUs are one continuous turn: no visual break at the
    # IU boundaries within it -- that boundary is exactly what the model
    # must predict, so the format must not leak it.
    assert doc.turns[0].speaker == "LENORE"
    assert doc.turns[0].n_words == 18
    rendered = render_document(doc, Condition.A)
    lines = rendered.split("\n")
    # Speaker labels stay as transcribed (uppercase); rendered words are
    # lowercased uniformly, "So" -> "so" included (the lowercasing rule
    # from reports/phase2_llm_design.md).
    assert lines[0].startswith("LENORE: 1:so 2:you 3:don't 4:need 5:to 6:go 7:borrow")
    assert "16:do 17:the 18:hooves" in lines[0]
    assert lines[1].startswith("LYNNE: 19:well")
    assert lines[2].startswith("DORIS: 29:so 30:mae-")


def test_render_window_cuts_mid_turn_but_still_shows_speaker_label():
    units = [
        iu("A", "one two three four five six seven eight nine ten"),  # words 1-10
        iu("B", "eleven twelve thirteen fourteen fifteen"),  # words 11-15
    ]
    doc = build_document_structure("TEST", units)
    # Window [6, 12]: cuts turn A mid-turn (only words 6-10 shown) and
    # turn B partially (only 11-12 shown).
    rendered = render_window(doc, 6, 12, Condition.A)
    lines = rendered.split("\n")
    assert lines[0] == "A: 6:six 7:seven 8:eight 9:nine 10:ten"
    assert lines[1] == "B: 11:eleven 12:twelve"


def test_render_window_excludes_turns_entirely_outside_range():
    units = [iu("A", "one two"), iu("B", "three four"), iu("C", "five six")]
    doc = build_document_structure("TEST", units)
    rendered = render_window(doc, 3, 4, Condition.A)
    assert rendered == "B: 3:three 4:four"


def test_render_window_matches_render_document_over_the_full_range():
    units = [iu("A", "(H) one two"), iu("B", "three (Hx) four")]
    doc = build_document_structure("TEST", units)
    full_window = render_window(doc, 1, doc.n_tokens, Condition.B)
    assert full_window == render_document(doc, Condition.B)


def test_render_window_leading_cue_attaches_to_the_word_after_the_cut():
    # A leading cue with nothing yet placed in the window slice attaches
    # to the word that follows it, same as at the start of a whole turn.
    units = [iu("A", "one two three (Hx) four five")]
    doc = build_document_structure("TEST", units)
    rendered = render_window(doc, 4, 6, Condition.B)
    assert rendered == "A: (Hx) 4:four 5:five"


# ---------------------------------------------------------------------
# Lowercasing (reports/phase2_llm_design.md S1)
# ---------------------------------------------------------------------


def _rendered_words(line: str) -> list[str]:
    """Extract just the word text from each "idx:word" piece on a
    rendered line, skipping the speaker label and any cue symbols (which
    never match "digits colon text").
    """
    return [m.group(1) for m in re.finditer(r"\d+:(\S+)", line)]


def test_no_rendered_word_contains_an_uppercase_letter():
    units = [
        iu("KIRSTEN", "I went to Antarctica with Don and Lori"),
        iu("DON", "I wasn't THERE that weekend"),
        iu("LORI", "Really? I didn't know That"),
    ]
    doc = build_document_structure("TEST", units)
    for condition in (Condition.A, Condition.B):
        rendered = render_document(doc, condition)
        for line in rendered.split("\n"):
            for word in _rendered_words(line):
                assert word == word.lower(), f"uppercase leaked into rendered word: {word!r}"


def test_literal_i_is_lowercased_too():
    units = [iu("A", "I know I said I would")]
    doc = build_document_structure("TEST", units)
    rendered = render_turn_line(doc.turns[0], Condition.A)
    assert "1:i" in rendered
    assert ":I " not in rendered and not rendered.endswith(":I")


def test_speaker_label_and_cue_symbols_are_not_lowercased():
    units = [iu("KIRSTEN", "(H) Hello THERE")]
    doc = build_document_structure("TEST", units)
    rendered = render_turn_line(doc.turns[0], Condition.B)
    assert rendered.startswith("KIRSTEN: ")  # label untouched
    assert "(H)" in rendered  # cue symbol untouched
    assert "1:hello" in rendered and "2:there" in rendered  # words lowercased


def test_condition_a_and_b_of_a_window_differ_only_by_cues_after_lowercasing():
    units = [
        iu("KIRSTEN", "(H) I Went To Antarctica"),
        iu("DON", "Really (Hx) I Know That"),
    ]
    doc = build_document_structure("TEST", units)
    a = render_document(doc, Condition.A)
    b = render_document(doc, Condition.B)
    cue_raws = {it.raw for t in doc.turns for it in t.items if isinstance(it, Cue)}
    b_without_cues_lines = []
    for line in b.split("\n"):
        pieces = [p for p in line.split(" ") if p not in cue_raws]
        b_without_cues_lines.append(" ".join(pieces))
    assert "\n".join(b_without_cues_lines) == a
    for line in a.split("\n"):
        for word in _rendered_words(line):
            assert word == word.lower()

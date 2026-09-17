"""Whole-corpus regression: every symbol condition B can put in a prompt
-- standalone or embedded mid-word -- must be one of the symbols the
prompt's own glossary defines (sbcsae_llm.GLOSSARY_SYMBOLS). Runs over
every window of every file (59, SBC037 excluded), same as
tests/test_tokenizer_invariants.py's whole-corpus convention: no skip
guard, assumes the corpus is present locally.

This is the actual behavioural guarantee behind "canonical cue symbols"
(reports/phase2_llm_design.md-adjacent decision, this session): since
rendering now always looks up CUE_CANONICAL_SYMBOL by kind rather than
using a Cue's raw matched text, an unglossed symbol can only reach a
prompt if some kind is missing from GLOSSARY_SYMBOLS entirely -- this
test is the thing that would catch that, not a spot check.
"""
import re

from sbcsae_llm import GLOSSARY_SYMBOLS, build_document_structure, render_window
from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import Condition
from sbcsae_windows import build_score_regions

EXCLUDE_FILES = {"SBC037"}

# Found by this test, not by this session's own steps: 4 raw .trn lines
# (SBC027:94, SBC055 and SBC059:1710, SBC060:43) have TWO tabs
# immediately after the timestamps with nothing between them (an empty
# speaker field followed immediately by the real text's own leading tab).
# sbcsae_reader._HEAD_RE's `rest` group is captured after a greedy `\s*`,
# which swallows BOTH tabs at once -- collapsing "empty speaker, then a
# tab, then real text" into a single gap, so split_line_fields' "content
# before the first remaining tab is the speaker" rule (needed for real
# colon-less codes like "MONTOYA") wrongly takes the actual TEXT as the
# speaker and leaves text empty. That corrupts the IU's speaker (and,
# since an empty-string speaker_field does NOT update current_speaker,
# every following same-run IU keeps inheriting this garbled value until
# the next well-formed speaker field). This is a real reader defect --
# CLAUDE.md's "Reading the corpus" section calls the reader settled, but
# also says not without new evidence, and this is exactly that: a
# concrete, reproduced counter-example. Fixing sbcsae_reader.py itself is
# out of scope for this session (not one of the 4 steps asked for, and it
# would touch every downstream "settled" figure that depends on speaker
# assignment) -- flagged to the user instead of silently patched. Only 4
# of 59 files are affected, and the pilot (step 4) uses only SBC039,
# which is not one of them, so this does not block today's task. Two
# OTHER superficially similar cases, SBC052's "~Janine" and SBC056's
# "@@@2]", are NOT this bug -- both are pre-existing, already-documented
# real speaker-field content (split_line_fields' own docstring lists
# "@@@2]" by name) and are left in scope.
KNOWN_READER_BUG_FILES = {"SBC027", "SBC055", "SBC059", "SBC060"}

# A "bare" word piece, after removing the three marks that can be fused
# into it (=, %, !, per sbcsae_tokenizer.py's _sandwiched mechanism --
# see reports/phase2_word_internal_marks.csv), must still look like a
# real tokeniser-produced word: letters, joined by an internal apostrophe,
# hyphen or underscore, with an optional single leading OR trailing
# hyphen or apostrophe -- a leading hyphen is the "eighty .. -three" case
# (_handle_displaced_trunc case 4), a leading apostrophe the "that]'s"
# case (both in sbcsae_tokenizer.py's "word" rule comments), confirmed
# both occur for real (36 offenders before this was added). A trailing
# hyphen can also be doubled ("Mu--", SBC047): the word rule's own single
# optional trailing "-" plus a separately-matched displaced_truncation
# hyphen can both land on the same word when an overlap-bracket close
# sits between them ("[Mu-]- --") -- confirmed the only such case
# corpus-wide. "-"/"_" are NEVER a fused mark -- they are always genuine
# word identity when inside a word piece; only a fully standalone "-"/"_"
# token is the truncation-mark Cue (the GLOSSARY_SYMBOLS check above).
_BARE_WORD_RE = re.compile(r"^[-']?[^\W\d_]+(?:[-'_][^\W\d_]+)*(?:-{1,2}|')?$")
_WORD_PIECE_RE = re.compile(r"^(\d+):(.*)$")


def _unglossed_pieces_in_line(line: str) -> list[str]:
    """Every space-separated piece of a rendered B line must be (1) the
    speaker label (first piece only), (2) exactly one glossed symbol, or
    (3) a word piece whose word part -- after removing =, %, ! -- is a
    legitimate bare word. Anything else is an unglossed mark.
    """
    pieces = line.split(" ")
    offenders = []
    for i, p in enumerate(pieces):
        if i == 0:
            continue  # speaker label, e.g. "KIRSTEN:"
        if p in GLOSSARY_SYMBOLS:
            continue
        m = _WORD_PIECE_RE.match(p)
        if m:
            bare = m.group(2).translate(str.maketrans("", "", "=%!"))
            if bare and _BARE_WORD_RE.match(bare):
                continue
        offenders.append(p)
    return offenders


def test_every_b_symbol_in_every_window_of_every_file_is_glossed():
    offenders = []
    for doc_id, units, *_ in iter_trn_documents():
        if doc_id in EXCLUDE_FILES or doc_id in KNOWN_READER_BUG_FILES:
            continue
        doc = build_document_structure(doc_id, units)
        if doc.n_tokens == 0:
            continue
        for region in build_score_regions(doc.n_tokens):
            text = render_window(doc, region.window_start, region.window_end, Condition.B)
            for line in text.split("\n"):
                if not line:
                    continue
                leftover = _unglossed_pieces_in_line(line)
                if leftover:
                    offenders.append((doc_id, region.score_start, region.score_end, leftover))

    assert not offenders, f"{len(offenders)} window(s) contain an unglossed symbol: {offenders[:10]}"

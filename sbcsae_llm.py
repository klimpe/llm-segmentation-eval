"""Phase 2: LLM segmentation pipeline for SBCSAE (intonation-unit, not
discourse, segmentation -- see CLAUDE.md's phase 2 framing).

Builds one whole-document structure from the reader+tokeniser output
(turns, reference IU masses, turn/speaker-change boundary positions), and
renders it into a prompt under condition A (words only) or B (words +
tier-2 prosodic cues), following the "candidate 2" format from the
rendering-sketch session: one line per turn, "SPEAKER: 1:word 2:word",
cues inline and unindexed in B -- both standalone cues (between words)
and cues glued mid-word ("ho=me"), which the tokeniser fuses into that
Word's own .raw rather than emitting as a separate item (see
_word_piece). A is exactly B with every tier-2 mark removed, wherever it
sits: same line breaks, labels and indices either way, so any A/B
difference in what the model does cannot come from a format difference.
Every rendered cue is its KIND's canonical symbol (CUE_CANONICAL_SYMBOL),
never the raw matched text, which can vary by case or by which rule
produced it.

Word indices are global (1-indexed across the whole document, continuous
across turn and IU boundaries alike), matching the masses contract and
the existing DISRPT prompt convention (llm_segmenter.build_prompt).

Nothing here calls the model. Segmentation-run scaffolding (caching,
n_samples, retries) is deliberately not duplicated from llm_segmenter.py
in this module; see sbcsae_dry_run.py for what a real run needs before
that scaffolding is wired in.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sbcsae_tokenizer import Condition, Cue, TokenItem, Word, tokenize, words_only

# ---------------------------------------------------------------------
# Document structure
# ---------------------------------------------------------------------


@dataclass
class Turn:
    speaker: str
    items: list[TokenItem]  # this turn's IUs' token items, concatenated in order
    start_index: int  # global 1-indexed position of this turn's first word
    n_words: int


@dataclass
class DocumentStructure:
    doc_id: str
    turns: list[Turn]
    words: list[str] = field(repr=False)  # global word list, condition-independent
    ref_masses: list[int]  # IU-level (includes turn-initial boundaries)
    turn_boundaries: set[int]  # subset of masses_to_boundaries(ref_masses)
    n_tokens: int


def build_document_structure(doc_id: str, units) -> DocumentStructure:
    """Build a DocumentStructure from one file's reader output (`units`,
    the merged IntonationUnits from sbcsae_reader.read_trn_document /
    iter_trn_documents). Zero-word IUs are dropped, exactly as in
    sbcsae_tokenizer.reference_segments and sbcsae_per_file_stats.py, so
    ref_masses here is the same reference the corpus-wide per-file stats
    were built from.
    """
    turns: list[Turn] = []
    words: list[str] = []
    seg_word_counts: list[int] = []
    turn_boundaries: set[int] = set()

    prev_speaker = None
    running_index = 0  # number of words emitted so far (0-indexed count)

    for u in units:
        items = tokenize(u.text)
        seg_words = words_only(items)
        if not seg_words:
            continue  # zero-word IU: not part of the reference

        seg_word_counts.append(len(seg_words))
        words.extend(w.text for w in seg_words)

        turn_initial = prev_speaker is None or u.speaker != prev_speaker
        if turn_initial:
            if turns:  # not the very first reference segment in the document
                turn_boundaries.add(running_index)
            turns.append(Turn(speaker=u.speaker, items=list(items), start_index=running_index + 1, n_words=len(seg_words)))
        else:
            turns[-1].items.extend(items)
            turns[-1].n_words += len(seg_words)

        running_index += len(seg_words)
        prev_speaker = u.speaker

    ref_masses = seg_word_counts
    n_tokens = sum(ref_masses)

    return DocumentStructure(
        doc_id=doc_id,
        turns=turns,
        words=words,
        ref_masses=ref_masses,
        turn_boundaries=turn_boundaries,
        n_tokens=n_tokens,
    )


# ---------------------------------------------------------------------
# Rendering: candidate 2, "SPEAKER: 1:word 2:word", cues inline & unindexed
# ---------------------------------------------------------------------


def _word_piece(idx: int, word: Word, condition: Condition) -> str:
    """"i:word", lowercased for rendering only. Word.text itself (the
    masses/scoring identity) is untouched either way -- see the
    lowercasing section of reports/phase2_llm_design.md: capitalisation
    was found to leak the same boundary signal CLAUDE.md already strips
    via Boundary items (94% capitalised after '.', 86% turn-initial, vs.
    4% IU-internal), so every rendered word is lowercased uniformly
    (including "I"), never positionally -- a positional rule would just
    re-encode the same signal a different way.

    Condition A renders word.text (bare, marks stripped: "home").
    Condition B renders word.raw, which is the same string EXCEPT for a
    tier-2 mark glued on both sides ("ho=me") -- the tokeniser fuses such
    a mark into the word's own .raw rather than emitting a separate Cue
    item (sbcsae_tokenizer.py's `_sandwiched` mechanism), so a word-only
    render (word.text, the pre-fix behaviour) silently dropped it: it was
    neither in .text nor a standalone Cue. See
    reports/phase2_word_internal_marks.csv -- 44% of all lengthening ("=")
    occurrences are exactly this case. A mark glued on only one side
    (word-final "so=", or leading with nothing open, "!Ron") is NOT
    sandwiched -- it was already its own Cue item and is unaffected by
    this choice of word.text vs .raw.
    """
    text = word.raw if condition is Condition.B else word.text
    return f"{idx}:{text.lower()}"


# A Cue's own .raw is whatever substring actually matched -- for a plain
# rule that's always the same literal (lengthening's "=", glottal's "%"),
# but for breath_in/breath_out it varies by case ("(H)"/"(h)"/"(HX)") and,
# for a Cue produced by decomposing a "compound" rule match (see
# tokenize()'s "compound" handling), by which compound produced it: a
# whole-corpus check found breath_in raw as "(H)" (10,046x), but also
# "(H" (12x, breath_paren_lengthening), "(H[" (1x, breath_bracket_
# lengthening) and "(H]" (1x, the sbc015 named exception) -- none of
# those three are valid on their own. Rendering .raw directly would leak
# a malformed fragment into the prompt. Render the canonical symbol for
# the Cue's KIND instead, always -- every occurrence of one kind means
# the same thing regardless of which rule or case variant produced it.
CUE_CANONICAL_SYMBOL = {
    "pause_short": "..",
    "pause_long": "...",
    "breath_in": "(H)",
    "breath_out": "(Hx)",
    "lengthening": "=",
    "glottal": "%",
    "booster_bang": "!",
    # Both confirmed present corpus-wide (20 and 17 occurrences): a
    # truncation mark with nothing to attach to, so it surfaces as its
    # own standalone token rather than a word's trailing "-" -- see
    # sbcsae_tokenizer.py's _handle_displaced_trunc case 2 and the
    # underscore_trunc "%_you" case in CLAUDE.md's Tokenisation section.
    "displaced_truncation": "-",
    "underscore_truncation": "_",
    # Confirmed zero occurrences corpus-wide (CLAUDE.md's "Documented Du
    # Bois marks confirmed absent"), included so rendering never guesses
    # if one ever appears -- it renders the correct canonical symbol
    # immediately, the same way the tokeniser itself still carries a live
    # rule for each of these rather than deleting it.
    "latching": "(0)",
    "accent_caret": "^",
    "accent_backtick": "`",
    "booster_semi": ";",
    "pitch_backslash": "\\",
    # "pause_timed" ("...(N)") is deliberately NOT here: its matched text
    # is parametrised by N, so there is no single fixed canonical string.
    # Also confirmed zero occurrences -- if one ever appears, the lookup
    # below raises rather than rendering a guess.
}


def _cue_piece(cue: Cue) -> str:
    try:
        return CUE_CANONICAL_SYMBOL[cue.kind]
    except KeyError:
        raise KeyError(
            f"no canonical rendering symbol for cue kind {cue.kind!r} (raw={cue.raw!r}) -- "
            f"add one to CUE_CANONICAL_SYMBOL rather than falling back to .raw"
        ) from None


def render_turn_line(turn: Turn, condition: Condition, start_override: int | None = None) -> str:
    """Render one turn as "SPEAKER: i:word i:word ..." (condition A), or
    the same with tier-2 cues inserted -- both standalone (unindexed, at
    their original position) and embedded mid-word -- in condition B. A
    is exactly B with every tier-2 mark removed: every standalone Cue
    item dropped, AND every word rendered as its bare .text instead of
    its (possibly mark-carrying) .raw -- same line breaks, labels and
    indices either way, so an A/B difference in a real run cannot come
    from format. See _word_piece and _cue_piece for where each mark ends
    up; both render the CANONICAL symbol for a cue's kind, never the raw
    matched text, which can vary by case or by which compound rule
    produced it (see CUE_CANONICAL_SYMBOL).

    start_override lets a caller (the windowing code) renumber a turn
    that is only partially inside a window; by default the turn's own
    global start_index is used.
    """
    idx = start_override if start_override is not None else turn.start_index
    pieces = []
    for it in turn.items:
        if isinstance(it, Word):
            pieces.append(_word_piece(idx, it, condition))
            idx += 1
        elif isinstance(it, Cue) and condition is Condition.B:
            pieces.append(_cue_piece(it))
        # Cue dropped under condition A; Boundary items are never rendered
        # under either condition (sbcsae_tokenizer.Boundary docstring).
    return f"{turn.speaker}: " + " ".join(pieces)


def render_document(doc: DocumentStructure, condition: Condition) -> str:
    return "\n".join(render_turn_line(t, condition) for t in doc.turns)


# ---------------------------------------------------------------------
# Window rendering
# ---------------------------------------------------------------------


def _slice_turn_items(turn: Turn, lo: int, hi: int) -> list[TokenItem]:
    """The subsequence of turn.items whose words fall in [lo, hi] (global,
    1-indexed, inclusive), plus any Cue adjacent to an included word: a
    leading cue (before any word in this turn has been placed) attaches to
    the word that follows it; every other cue attaches to the word that
    precedes it. This is a display-only slicing decision (which margin a
    boundary-adjacent cue falls on does not affect scoring, since cues are
    never indexed or scored) -- see sbcsae_tokenizer's own note that a
    leading vs. trailing cue is already rendered asymmetrically.
    """
    out: list[TokenItem] = []
    next_word_idx = turn.start_index
    last_included_word_idx = None
    for it in turn.items:
        if isinstance(it, Word):
            current = next_word_idx
            next_word_idx += 1
            if lo <= current <= hi:
                out.append(it)
                last_included_word_idx = current
        elif isinstance(it, Cue):
            attach_idx = last_included_word_idx if last_included_word_idx is not None else next_word_idx
            if lo <= attach_idx <= hi:
                out.append(it)
        # Boundary items are never rendered regardless of window.
    return out


_IU_DEFINITION = """\
You will read a transcript of spontaneous spoken discourse. \
The transcript is given as a sequence of words, one speaker turn per line, \
in the format "SPEAKER: 1:word 2:word ...", where each number is a word's \
1-indexed position in the document.

Your task is to identify where a new intonation unit begins inside each \
turn. An intonation unit is a stretch of speech produced under a single, \
coherent intonation contour (Chafe, 1994; Du Bois, Schuetze-Coburn, \
Cumming & Paolino, 1993). It often corresponds to a clause, but not \
always: an intonation unit can be shorter than a clause, and is \
frequently as short as a single word.

Every turn's first word already begins a new intonation unit -- do not \
report it. Report only the positions of words, strictly inside a turn \
(never a turn's own first word), at which a new intonation unit begins.

A reported position is always the first word of the new intonation \
unit -- never the last word of the one before it. For example, in \
"SPEAKER: 12:we 13:went 14:down 15:to 16:the 17:store", if a new \
intonation unit begins at "down", report 14, not 13.

Respond with nothing but a JSON array of the 1-indexed positions where a \
new intonation unit begins inside a turn, e.g. [4, 9, 15]. No other \
text, no markdown fences.
"""

# Every cue kind CUE_CANONICAL_SYMBOL can actually render on real corpus
# data is glossed here (verified whole-corpus, tests/
# test_cue_glossary_coverage.py): accent caret/backtick, the semicolon
# booster, latching "(0)", and the timed-pause form are documented rules
# but confirmed to occur zero times corpus-wide, so they are not glossed
# -- a symbol that never appears needs no glossary entry (if one ever did
# appear, the whole-corpus test would catch the gap immediately). No
# claim about what any of these mean FOR segmentation -- purely what each
# one denotes. A single structured list, not a hand-kept parallel text
# block, so the printed glossary and GLOSSARY_SYMBOLS (what the
# whole-corpus coverage test checks against) cannot drift apart.
_GLOSSARY_ENTRIES = [
    ("...", "a long pause"),
    ("..", "a short pause"),
    ("(H)", "an in-breath"),
    ("(Hx)", "an out-breath"),
    ("=", "lengthening of the preceding sound"),
    ("%", "a glottal stop"),
    ("!", 'emphatic stress ("booster")'),
    ("-", "a truncation mark with no word attached"),
    ("_", "a truncation mark with no word attached (alternate written form)"),
]

GLOSSARY_SYMBOLS = frozenset(symbol for symbol, _ in _GLOSSARY_ENTRIES)

_CUE_GLOSSARY = (
    "Some words are also marked with symbols showing how they were spoken, or "
    "appear as their own symbol with no word attached. These symbols are not "
    "words and are never a valid answer:\n"
    + "\n".join(f"  {symbol:<5s} {desc}" for symbol, desc in _GLOSSARY_ENTRIES)
    + "\n"
)


def build_prompt(window_text: str, condition: Condition) -> str:
    """The zero-shot task prompt for one rendered window (sbcsae_render_window
    or render_document output) under the given condition. Condition B's
    extra cue glossary is purely denotational (what each symbol IS), never
    relational (how it relates to where a boundary falls) -- the model is
    left to discover any such relationship itself, exactly as it would
    have to when actually run.
    """
    parts = [_IU_DEFINITION]
    if condition is Condition.B:
        parts.append(_CUE_GLOSSARY)
    parts.append(window_text)
    return "\n".join(parts)


def estimate_tokens(text: str) -> int:
    """A rough, offline estimate of prompt token count: ~4 characters per
    token, a commonly-cited approximation for English text under
    BPE-style tokenisers. NOT an authoritative count -- getting an exact
    figure means either calling the model or the API's separate
    count_tokens endpoint, both out of scope for a dry run that must not
    call the model. Use only for order-of-magnitude prompt-sizing, never
    for anything that needs to match a real API's token accounting.
    """
    return round(len(text) / 4)


def render_window(doc: DocumentStructure, window_start: int, window_end: int, condition: Condition) -> str:
    """Render the [window_start, window_end] global word range (a
    ScoreRegion's window_start/window_end from sbcsae_windows.py) as one
    line per turn that overlaps it, in the same "SPEAKER: i:word ..."
    format as render_document. A turn only partially inside the window
    (its speaker label falls in the unscored margin, per the brief) still
    gets its label rendered -- there is no separate "margin" formatting,
    only a shorter slice of that turn's items.
    """
    lines = []
    for t in doc.turns:
        t_lo, t_hi = t.start_index, t.start_index + t.n_words - 1
        if t_hi < window_start or t_lo > window_end:
            continue  # no overlap with the window at all
        lo, hi = max(t_lo, window_start), min(t_hi, window_end)
        sliced = _slice_turn_items(t, lo, hi)
        idx = lo
        pieces = []
        for it in sliced:
            if isinstance(it, Word):
                pieces.append(_word_piece(idx, it, condition))
                idx += 1
            elif isinstance(it, Cue) and condition is Condition.B:
                pieces.append(_cue_piece(it))
        lines.append(f"{t.speaker}: " + " ".join(pieces))
    return "\n".join(lines)

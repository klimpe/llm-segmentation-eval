"""Phase 2 stage 4: tokeniser.

Splits one intonation unit's raw text (as produced by the settled,
unmodified sbcsae_reader) into an ordered sequence of TokenItems -- a Word
(indexed, in reading order), a Cue (a prosodic marker, not indexed), or a
Boundary (transitional punctuation / IU truncation, not indexed, never
rendered in either condition -- see the Boundary docstring). Words are the
atomic unit in both conditions; condition A and B differ only in whether
cues survive into the rendered output, never in which words exist, their
normalised form, or their count.

Tier-1 material (CLAUDE.md: overlap brackets, ((researcher comments)),
capitalised vocal noises, <TAG ... TAG> delimiters including <%...%>,
standalone/attached @, a disguised-name prefix ~/#/* immediately followed by
a letter) is dropped entirely and produces no token, in either condition.

Tier-2 material (pauses, breath, lengthening, accents, boosters, glottal
stop, terminal pitch, latching) produces a Cue: kept in B, filtered out at
render time for A.

Tier-3 material (words, truncated words, the indecipherable X marker) is
kept always and produces a Word.

`.`, `,`, `?` and IU truncation `--` are IU-final in 99.4-100% of their
occurrences: the boundary annotation itself, not a prosodic quality of a
word, so they are neither tier-1 nor tier-2 -- they produce a Boundary item,
which is never rendered in either condition (see Boundary).

A tier-1 delimiter, or a tier-2 mark, occurring with no surrounding
whitespace between two letter runs (e.g. the numbered-overlap-bracket case
"li[2ke2]," or the lengthening case "s=o") fuses those runs into a single
Word, exactly as if the interrupting material were not there -- this is
required for word identity to survive markup that happens to land
mid-word, and is the same mechanism for both cases (a dropped delimiter
and a rendered cue).

Anything not covered by an explicit rule above raises TokenizeError. Per
CLAUDE.md's working method, this is deliberate: a symbol that doesn't fit
any documented tier must surface as a raise, not be silently guessed at.

Known B-rendering limitation: a cue glued to a word on its TRAILING/
embedded side (s=o, idea=) is fused into that word's raw form for display.
A cue glued on the LEADING side of a word with nothing yet open (!Ron)
is not retroactively fused and renders as a separate, space-separated
piece. This never affects word identity, count, or the masses contract
(only Word.text and word count matter there) -- it is a display-only
wrinkle in Condition B's illustrative rendering.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Condition(Enum):
    A = "A"  # words only
    B = "B"  # words + prosodic cues


class TokenizeError(ValueError):
    """A character or symbol run fits no documented tier."""


@dataclass(frozen=True)
class Word:
    index: int
    text: str  # normalised bare form -- identical under A and B
    raw: str  # original substring (marks included), for B rendering only
    n_fragments: int = 1  # >1 means this word was fused across a dropped
    # delimiter or an embedded mark with no intervening whitespace (e.g.
    # "li[2ke2]," or "s=o") -- diagnostic only, not part of the masses
    # contract, which only cares about the final word count and identity.


@dataclass(frozen=True)
class Cue:
    kind: str
    raw: str


@dataclass(frozen=True)
class Boundary:
    """Transitional continuity punctuation (. , ?) and IU truncation (--).

    Not a Word (no index, not counted or scored as a segment word) and not
    a Cue (never rendered, in EITHER condition -- unlike a Cue, which
    survives into Condition B). Corpus-wide, these sit at the end of their
    IU 99.4-100% of the time: they mark where the boundary annotation
    falls, not a prosodic quality of a word, so they are their own kind
    rather than a cue that happens to render as nothing.
    """

    kind: str
    raw: str


TokenItem = Word | Cue | Boundary

# --- rule table, in priority order --------------------------------------
# (kind, name, pattern). kind is one of:
#   "drop"     -- tier 1, consumed, no token, can still fuse a word cluster
#   "cue"      -- tier 2, becomes a Cue, can still fuse a word cluster
#   "boundary" -- . , ? and -- : never fuses, becomes a Boundary item, which
#                 is never rendered in EITHER condition (unlike a Cue). The
#                 IU-final boundary annotation, not a prosodic quality of a
#                 word -- CLAUDE.md placed these in no tier; they are now
#                 their own kind rather than silently producing nothing.
#   "frag"     -- tier 3, a maximal run of letters (a written word,
#                 contractions and hyphenated compounds included) -- the
#                 fusable unit
_RULES: list[tuple[str, str, str]] = [
    ("cue", "pause_timed", r"\.\.\.\(\d+(?:\.\d+)?\)"),
    ("cue", "pause_long", r"\.\.\."),
    ("cue", "pause_short", r"\.\."),
    # (H)/(Hx)/(0) must be tried before the generic capitalised-vocal-noise
    # rule below, or that tier-1 rule would consume them (they fit its
    # pattern too: one-or-more run of the character class).
    # Case folded on the H/X letters only (S1e): lowercase "(h)"/"(hx)" and
    # the mixed "(HX)" all occur in the corpus alongside the documented
    # "(H)"/"(Hx)" and mean the same thing -- same cue, not a separate one.
    ("cue", "breath_in", r"\([hH]\)"),
    ("cue", "breath_out", r"\([hH][xX]\)"),
    ("cue", "latching", r"\(0\)"),
    # Compounds of two documented marks, found by the whole-corpus marker
    # inventory and named/handled individually rather than generalised into
    # a new rule: a glottal stop co-occurring with a breath ("(%Hx)", 1
    # occurrence), and a breath interrupted by an overlap bracket enclosing
    # a lengthening mark ("(H[=])"/"(Hx[=])", 3 occurrences total). Each
    # decomposes into the constituent documented cues at tokenise time
    # (see the "compound_*" handling in tokenize()) rather than becoming
    # its own new tier or cue kind.
    ("compound", "glottal_breath", r"\(%(?P<gb_letter>Hx?)\)"),
    ("compound", "breath_bracket_lengthening", r"\((?P<bbl_letter>Hx?)\[=\]\)"),
    ("drop", "vocal_noise_caps", r"\([A-Z][A-Z0-9_., ]*\)"),
    # Empty parens, nothing inside (S1e, "@()", "...() (TSK)"): a
    # vocal-noise annotation the transcriber opened and closed with no
    # content -- dropped the same way a filled one would be.
    ("drop", "empty_parens", r"\(\)"),
    # SBC007's "(YAWN0 Unhunh,": the vocal-noise-caps closing ")" was
    # mistyped as "0" (the same lost/corrupted-character phenomenon as
    # S1a's lost-initial-letter family, landing on a delimiter rather than
    # a word letter this time). Named, logged, one-off exception, same
    # principle as DOG_BARKING_BEGINS below -- not a general rule for
    # every vocal-noise annotation missing its closing paren.
    ("drop", "yawn_named_exception", r"\(YAWN0"),
    # Exactly two closing parens, matching researcher-comment content on
    # every occurrence but one (SBC029's "((DOG_BARKING_BEGINS)", missing
    # its second ")") -- that one case is a named, logged exception below,
    # not a reason to make this rule more permissive for everyone else.
    ("drop", "research_comment", r"\(\([^()]*\)\)"),
    ("drop", "research_comment_named_exception", r"\(\(DOG_BARKING_BEGINS\)(?!\))"),
    # SBC024's "[Look okay)].": a single stray ")" with no opening paren
    # anywhere in the IU. Named, logged, one-off exception anchored tightly
    # to its own context (not a general "drop any orphan )" rule, which
    # would silently swallow a real coverage gap anywhere else it occurs).
    ("drop", "stray_close_paren_named_exception", r"(?<=okay)\)(?=\])"),
    ("drop", "overlap_num_open", r"\[\d+"),
    ("drop", "overlap_num_close", r"\d+\]"),
    ("drop", "overlap_open", r"\["),
    ("drop", "overlap_close", r"\]"),
    # <<TAG ... TAG>>: same wrapper-over-real-speech principle as the
    # single-angle spans below, tier 1, never paired (open and close are
    # each stripped independently, whether or not their names match, and
    # whether or not both appear in the same IU -- see the corpus-wide
    # check in reports/phase2_tokeniser.md S3b: names occasionally don't
    # match, e.g. VOMIT-SOUND/VOMIT-NOISE, and that is not this rule's
    # problem to solve). "_"/"-" are in the tag-name class so multi-word
    # names (WATER_RUNNING_AND_DISH_NOISE, BANG-GLASSES) don't get half-
    # eaten -- the marker-inventory script's undercount (S3b) came from a
    # narrower class, not from this rule.
    #
    # The zero-content case ("<<THUMP>>", open and close directly
    # adjacent, no words between) needs its own higher-priority rule: a
    # greedy open-pattern tried alone would consume the tag-name letters
    # the close-pattern then has nothing left to match, and ">>" would
    # raise as unrecognised -- this is exactly the mechanism behind the
    # marker inventory's 83-vs-93 undercount (S3b), reproduced here if not
    # guarded against. Matching the whole wrapped span first when there's
    # no space to consume avoids it structurally, not by re-ordering luck.
    ("drop", "double_angle_wrap", r"<<[A-Za-z][A-Za-z_\-]*>>"),
    ("drop", "double_angle_open", r"<<[A-Za-z][A-Za-z_\-]*"),
    ("drop", "double_angle_close", r"[A-Za-z][A-Za-z_\-]*>>"),
    # "%" included so <% ... %> (a span-tag pair like <@ ... @>, S3.3: pairs
    # within the same IU at the same ~70% rate as <@...@>) strips the same
    # way, not just the letter/digit/@-named tags.
    ("drop", "angle_open", r"<[A-Za-z0-9@%]+"),
    ("drop", "angle_close", r"[A-Za-z0-9@%]+>"),
    ("drop", "at_sign", r"@+"),
    # "+": event-timing marker inside <<...>> quality spans (S3c, corrected
    # this session by cross-IU-aware scanning: of 177 occurrences, 165 sit
    # inside <<...>>, 7 in the lost-initial-letter float artifact -- already
    # consumed whole by that rule above, so this pattern never sees them --
    # and the remaining 5 are inside other already-dropped span constructs).
    # Tier 1, not a prosodic cue: removed in both conditions. Mid-word (e.g.
    # "ob+jecting") fuses like any other tier-1 mark via the ordinary "drop"
    # fusion logic, not a special case.
    ("drop", "plus_event_timing", r"\+"),
    # A disguised-name prefix (~Mae, #Deutsch, *Dorsen's) immediately
    # followed by a letter: strip the prefix, the word fuses in normally
    # right after via the ordinary "frag" rule. Zero-width lookahead so
    # the letter itself isn't consumed here. Any OTHER occurrence -- not
    # followed by a letter (X[3X3]*, #5Jason) -- still raises: this is not
    # a general rule for these three characters, only the letter-prefix
    # case is authorised.
    ("drop", "disguise_prefix", r"[~#*](?=[^\W\d_])"),
    # Lost-initial-letter corruption: one phenomenon, three surface shapes,
    # unified with the reader's NUL/DEL-byte handling (sbcsae_reader.py) --
    # same principle throughout: strip the corruption marker, keep
    # whatever letters survive, never reconstruct the lost content.
    #   - a bare "0" glued directly before a lowercase letter, standing in
    #     for exactly one lost character ("0h," from "uh,"/"oh,");
    #   - "0.000000" with no exponent, glued before a lowercase letter
    #     (found this session: "0.000000or", "0.000000irst" -- the same
    #     spreadsheet-mantissa artifact with the "e+00"/"E+00" tail itself
    #     lost or never applied);
    #   - the full "0.000000e+00"/"0.000000E+00" artifact (verified,
    #     reports/phase2_tokeniser.md), a capital-letter-initial word
    #     turned into scientific notation, almost certainly by a
    #     spreadsheet auto-format artifact in the file's editing history.
    # The lowercase-letter lookahead is deliberate, not incidental: every
    # verified corpus instance of all three shapes is followed by a
    # lowercase remainder (the lost character was the word's initial
    # letter, upper or lower, and what's left starts lowercase either
    # way), so restricting to lowercase is the conservative choice -- an
    # uppercase-letter continuation would still raise rather than guess.
    ("drop", "lost_initial_letter", r"0(?:\.000000(?:[eE]\+00)?)?(?=[a-z])"),
    # Overlap-number leftovers (S1e): a whole-corpus digit census, outside
    # timestamps (stripped before the tokeniser ever sees text) and every
    # already-matched context above (overlap-num open/close, angle-tag
    # names, the float artifact), found 86 residual digit occurrences and
    # verified none are real numerals -- SBCSAE spells numbers as words
    # throughout. Every one is a numbered-overlap-bracket digit whose
    # partner bracket character is missing or misplaced by a transcription
    # typo ("[2I mean2," missing its "]", "2[cause I2]" with the "2"
    # misplaced before "[" instead of inside it, "[2(H)2]1" with a bare
    # extra digit tacked on after an already-complete pair). Reached only
    # after every specific higher-priority rule above has had first claim,
    # so this never touches a digit that belongs to a construct already
    # handled by name.
    ("drop", "overlap_leftover_digit", r"\d+"),
    ("boundary", "iu_truncation", r"--"),
    # A single hyphen, not part of "--", that survived the word-fragment
    # rule below because something else (lengthening or glottal) sat
    # between it and the last letter -- "b=-", "%-". Whether it fuses onto
    # a word or stands alone as a mark-only token is decided in
    # tokenize(); anything not immediately preceded by a glued lengthening
    # or glottal mark still raises (see _handle_displaced_trunc).
    ("displaced_trunc", "displaced_truncation", r"-(?!-)"),
    ("cue", "lengthening", r"="),
    ("cue", "accent_caret", r"\^"),
    ("cue", "accent_backtick", r"`"),
    ("cue", "booster_bang", r"!"),
    ("cue", "booster_semi", r";"),
    ("cue", "glottal", r"%"),
    ("cue", "pitch_backslash", r"\\"),
    # "_" and "/" were reclassified this session (S1d): neither is a
    # terminal-pitch cue. Corpus-wide breakdown of every occurrence found
    # no genuine pitch-marking use of either character left -- "/" is
    # exclusively the delimiter of a slash-bracketed phonetic respelling
    # ("/god/"), and "_" is exclusively (a) a word-internal compound
    # joiner (handled directly in the "word" pattern below, not here --
    # "part of the word" per the task, not a mark that fuses by omission),
    # (b) the leading character of a phonetic-gloss suffix attached to a
    # word ("good_/god/", "cello_(/cheller/)"), or (c) a self-interruption/
    # abandoned-utterance marker (trailing "word_", or standalone "__"),
    # overwhelmingly concentrated in SBC012/SBC013 and NOT authorised by
    # this rule -- still raises, reported separately, not guessed at here.
    #
    # A phonetic-gloss suffix is dropped whole -- the slash-delimited
    # respelling is not the orthographic word either, so it isn't kept:
    # only the word before the "_" survives, per the "kept always" tier-3
    # rule already covering that word on its own.
    ("drop", "word_gloss_suffix", r"_\(?/[^/]*/\)?"),
    # A bare (not "_"-attached) slash-delimited phonetic-gloss aside --
    # same annotation, just standing alone rather than suffixed to a word
    # (2 IUs, S1d). Dropped whole for the same reason as the suffixed form.
    ("drop", "bare_phonetic_gloss", r"/[^/]*/"),
    ("boundary", "period", r"\."),
    ("boundary", "comma", r","),
    ("boundary", "qmark", r"\?"),
    # A written word: Unicode letters (so SBC037's Spanish text tokenises,
    # not just ASCII), internal apostrophe/hyphen/underscore for
    # contractions, compounds, and underscore-joined expressions ("kids'",
    # "third-graders", "nineteen_ninety_three") -- underscore is kept
    # literally in the word text ("part of the word", S1d), not dropped
    # and fused by omission the way an embedded tier-1/tier-2 mark is; an
    # optional single trailing hyphen for word truncation (y-) -- guarded
    # so a real IU-truncation "--" right after a word (no space) isn't
    # half-eaten by this rule -- or trailing apostrophe for a plural
    # possessive (kids'). An optional LEADING apostrophe handles a
    # contraction split by a removed delimiter with no space, e.g.
    # "that]'s" (a numbered-overlap bracket closing mid-word): the
    # fragment "'s" only ever fuses onto an already-open word (tokenize()'s
    # fusion logic), never starts one on its own in real data.
    ("frag", "word", r"'?[^\W\d_]+(?:['_-][^\W\d_]+)*(?:-(?!-)|')?"),
]

_KIND_OF = {name: kind for kind, name, _ in _RULES}
_MASTER_RE = re.compile("|".join(f"(?P<{name}>{pat})" for _, name, pat in _RULES))


def _raw_matches(text: str) -> list[re.Match]:
    return list(_MASTER_RE.finditer(text))


def _raise_unrecognised(text: str, bad: str, idx: int) -> None:
    # U+XXXX comes first and is the only machine-parsed part of this
    # message (see sbcsae_tokenizer_validate.py) -- {bad!r} alone is not
    # safe to parse back out, since Python's repr switches quote style
    # when the character itself is an apostrophe.
    raise TokenizeError(
        f"unrecognised symbol U+{ord(bad):04X} ({bad!r}) at position {idx} "
        f"fits no documented tier: {text!r}"
    )


def _check_coverage(text: str, matches: list[re.Match]) -> None:
    """Raise if any non-whitespace character is not part of some match."""
    pos = 0
    for m in matches:
        gap = text[pos : m.start()]
        if gap.strip():
            bad = gap.strip()[0]
            _raise_unrecognised(text, bad, pos + gap.index(bad))
        pos = m.end()
    tail = text[pos:]
    if tail.strip():
        bad = tail.strip()[0]
        _raise_unrecognised(text, bad, pos + tail.index(bad))


def _is_glued(text: str, prev_end: int, start: int) -> bool:
    return not any(c.isspace() for c in text[prev_end:start])


def _sandwiched(matches: list[re.Match], i: int, text: str) -> bool:
    """True if the cue at matches[i] sits directly between two letter runs
    with no whitespace on either side (e.g. the "=" in "s=o"), so it should
    fuse into the surrounding word rather than end it. A cue glued only on
    one side (trailing, e.g. "you're--") is not sandwiched -- it still ends
    the word, just with no space before it in the raw text.

    A displaced-truncation hyphen counts as a continuation here too, not
    just an ordinary word fragment: "b=-" must keep "=" open rather than
    ending the word at "b", so the hyphen can still reach it one match
    later (see _handle_displaced_trunc).
    """
    if i == 0:
        return False
    if not _is_glued(text, matches[i - 1].end(), matches[i].start()):
        return False
    if i + 1 >= len(matches):
        return False
    nxt = matches[i + 1]
    if not _is_glued(text, matches[i].end(), nxt.start()):
        return False
    return _KIND_OF[nxt.lastgroup] in ("frag", "displaced_trunc")


def tokenize(text: str) -> list[TokenItem]:
    """Tokenise one IU's raw text into an ordered Word/Cue sequence.

    Raises TokenizeError if any symbol fits no documented tier.
    """
    matches = _raw_matches(text)
    _check_coverage(text, matches)

    items: list[TokenItem] = []
    pending_norm_pieces: list[str] = []
    pending_raw_pieces: list[str] = []
    prev_end = 0
    word_index = 0
    pending_active = False

    def flush_word():
        nonlocal pending_active, word_index
        if not pending_active:
            return
        norm = "".join(pending_norm_pieces)
        raw = "".join(pending_raw_pieces)
        items.append(Word(index=word_index, text=norm, raw=raw, n_fragments=len(pending_norm_pieces)))
        word_index += 1
        pending_norm_pieces.clear()
        pending_raw_pieces.clear()
        pending_active = False

    for i, m in enumerate(matches):
        glued = _is_glued(text, prev_end, m.start())
        prev_end = m.end()

        name = m.lastgroup
        kind = _KIND_OF[name]
        matched = m.group()

        if kind == "boundary":
            # Never fuses; closes out any pending word cluster; produces a
            # Boundary item, which -- unlike a Cue -- is never rendered in
            # either condition (see the Boundary docstring).
            flush_word()
            items.append(Boundary(kind=name, raw=matched))
            continue

        if kind == "frag":
            if glued and pending_active:
                pending_norm_pieces.append(matched)
                pending_raw_pieces.append(matched)
            else:
                flush_word()
                pending_norm_pieces.append(matched)
                pending_raw_pieces.append(matched)
                pending_active = True
            continue

        if kind == "cue":
            if glued and pending_active and _sandwiched(matches, i, text):
                # Embedded mid-word (e.g. the "=" in "s=o"): contributes to
                # the word's raw/B-rendering only, not a separate sequence
                # item -- CLAUDE.md asks for cues "rendered on the word",
                # not sub-word placement fidelity in the token sequence.
                pending_raw_pieces.append(matched)
            else:
                flush_word()
                items.append(Cue(kind=name, raw=matched))
            continue

        if kind == "drop":
            if glued and pending_active:
                # e.g. overlap-bracket delimiter splitting one word; content
                # on either side fuses, the delimiter itself contributes
                # nothing to either rendering.
                pass
            else:
                flush_word()
            continue

        if kind == "compound":
            # A named compound of two documented marks (see _RULES):
            # decomposed into its constituent cues, in order. Never
            # sandwiched into a word -- these compounds are always
            # self-contained parenthetical material, like a plain (H).
            flush_word()
            group = m.group("gb_letter" if name == "glottal_breath" else "bbl_letter")
            breath_kind = "breath_out" if group == "Hx" else "breath_in"
            if name == "glottal_breath":
                items.append(Cue(kind="glottal", raw="%"))
                items.append(Cue(kind=breath_kind, raw=f"({group})"))
            else:  # breath_bracket_lengthening
                items.append(Cue(kind=breath_kind, raw=f"({group}["))
                items.append(Cue(kind="lengthening", raw="=])"))
            continue

        if kind == "displaced_trunc":
            was_active = pending_active
            _handle_displaced_trunc(
                matches, i, text, glued, pending_active, pending_norm_pieces, pending_raw_pieces, items
            )
            if was_active:
                # The hyphen completed the pending word (attached case):
                # flush it now, since truncation always ends a word.
                flush_word()
            continue

    flush_word()
    return items


def _handle_displaced_trunc(
    matches: list[re.Match],
    i: int,
    text: str,
    glued: bool,
    pending_active: bool,
    pending_norm_pieces: list[str],
    pending_raw_pieces: list[str],
    items: list[TokenItem],
) -> None:
    """A single hyphen displaced from its word by an intervening lengthening
    or glottal mark ("b=-", "%-") -- authorised, named handling for exactly
    this compound, not a general rule for orphan hyphens.

    If a word is still open (the mark was embedded/sandwiched into it),
    the hyphen completes that word: "b=-" tokenises to the one word "b-",
    keeping the truncation hyphen with the word per the same "kept always"
    tier-3 treatment as a plain "y-". If no word is open (the mark stood
    alone, e.g. "%-"), the hyphen becomes its own Cue rather than a word --
    CLAUDE.md's tiers don't say whether a mark-only run like this is a
    word, and this function does not decide that either; it is left
    countable (as a "displaced_truncation" Cue with no preceding Word) and
    excluded from the word sequence. Anything else -- a hyphen not
    directly preceded by a glued lengthening/glottal mark -- still raises:
    this is not a general orphan-hyphen rule.
    """
    if not (glued and i > 0):
        _raise_unrecognised(text, "-", matches[i].start())
    prev = matches[i - 1]
    if prev.lastgroup not in ("lengthening", "glottal"):
        _raise_unrecognised(text, "-", matches[i].start())

    if pending_active:
        pending_norm_pieces.append("-")
        pending_raw_pieces.append("-")
    else:
        items.append(Cue(kind="displaced_truncation", raw="-"))


def words_only(items: list[TokenItem]) -> list[Word]:
    return [it for it in items if isinstance(it, Word)]


def render(items: list[TokenItem], condition: Condition) -> str:
    """Render a token sequence back to a display string. Diagnostic /
    illustrative only -- not part of the masses data contract.

    Boundary items (. , ? --) match neither branch below and so never
    appear in the output, in either condition -- that omission is
    deliberate, not an oversight (see the Boundary docstring).
    """
    pieces = []
    for it in items:
        if isinstance(it, Word):
            pieces.append(it.raw if condition is Condition.B else it.text)
        elif isinstance(it, Cue):
            if condition is Condition.B:
                pieces.append(it.raw)
    return " ".join(pieces)


def reference_segments(iu_items: list[list[TokenItem]]) -> list[list[TokenItem]]:
    """Zero-word IUs are dropped from the reference, identically under
    Condition A and B (word content never differs between conditions, so
    "has at least one word" doesn't either). Their cues are not deleted --
    a caller rendering the full document in Condition B still has them,
    via the IU's own (unfiltered) item list -- they just don't count as
    their own segment for scoring purposes.
    """
    return [items for items in iu_items if words_only(items)]

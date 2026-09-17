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
from typing import Callable


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

# Single-angle tag codes: a CLOSED inventory, not "any letters" (reports/
# phase2_tokeniser.md S19). Built from every code found in an unambiguous
# position corpus-wide -- an opening delimiter followed by whitespace, a
# closing one preceded by whitespace -- keeping only those confirmed as
# BOTH an opener and a closer somewhere (genuine paired usage, not a
# one-off scanning artifact). Sorted longest first: since every code is a
# distinct literal string, at most one can ever match at a given
# position (a shorter code's own match requires the character right
# after it to be non-alphanumeric, which a longer code sharing that
# prefix never satisfies) -- verified corpus-wide, not just reasoned
# through, so "if more than one code could match, raise" never actually
# arises for this inventory.
_ANGLE_TAG_CODES = (
    "NONSENSE", "DRINKING", "HUMMING", "SMOKING", "ACCENT", "SHOUT",
    "FOOD", "SING", "READ", "YELL", "SIGH", "SLUR", "VOX", "MRC", "PAR",
    "YWN", "CRK", "CRY", "ACC", "WH", "HI", "BR", "FF", "PP", "WI", "L2",
    "SM", "X", "P", "Q", "F", "L", "A", "W", "@", "%",
)
_ANGLE_TAG_ALTERNATION = "|".join(re.escape(c) for c in _ANGLE_TAG_CODES)
# Stops a "word" frag match from extending into a recognised close-code
# immediately ahead of it ("knowX>", "XXP>": without this, frag's own
# greedy letter class has no way to know "X>"/"P>" belongs to the
# delimiter, not the word, and swallows straight through it -- see the
# "word" rule below).
_ANGLE_TAG_CLOSE_GUARD = rf"(?!(?:{_ANGLE_TAG_ALTERNATION})>)"

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
    # "(H=)"/"(h=)" (confirmed this session): the same lengthening-inside-
    # breath-parens compound as breath_bracket_lengthening above, just
    # without the enclosing "[=]" brackets -- decomposes the same way.
    # Case-folded on both letters, matching breath_in/out above.
    ("compound", "breath_paren_lengthening", r"\((?P<bpl_letter>[hH][xX]?)=\)"),
    # SBC015 line 1805, "[2(H]=2]": one of the 5 named exceptions closing
    # out the tokeniser raises. Same breath+lengthening compound as
    # breath_paren_lengthening ("(H=)") above, but here a numbered overlap
    # bracket has landed where the compound's own closing ")" should be --
    # the ")" never appears anywhere in the IU. Anchored tightly to this
    # exact occurrence (lookbehind/lookahead on the surrounding "[2"/"2]",
    # not a general "]" -> ")" substitution rule, which would conflate the
    # overlap-bracket and vocal-noise-paren conventions on no evidence
    # beyond convenience -- see reports/phase2_tokeniser.md S10.2e).
    ("compound", "sbc015_breath_bracket_lengthening_named_exception", r"(?<=\[2)\(H\]=(?=2\])"),
    # Case-insensitive throughout (confirmed this session: lowercase names
    # like "(throat)"/"(sigh)"/"(sniff)" are the same convention as the
    # capitalised form, and this single class also resolves a mixed-case
    # typo, "(COUGh)", for the same reason -- one convention, not two).
    # "[", "]", "=" in the BODY class only, not the first-character class
    # (confirmed this session, S2e): a vocal-noise name occasionally has
    # an overlap bracket landing inside it ("(THR[OAT)]",
    # "(AMENS_[CHEERS]_APPLAUSE)=") or a lengthening mark with no
    # dedicated compound for it ("(SH=)" -- not H/Hx, so
    # breath_paren_lengthening's own, higher-priority, more specific
    # pattern doesn't claim it first). Dropped whole either way, same as
    # any other vocal-noise annotation -- not decomposed, since the name
    # itself isn't a documented breath cue. Deliberately NOT widening the
    # first-character class to "@" too: "(@Hx)" would then be silently
    # swallowed as generic dropped noise instead of surfacing as its own
    # decision about whether to preserve the "Hx" breath cue underneath
    # the "@" -- left raising on purpose (S2 report).
    ("drop", "vocal_noise_caps", r"\([A-Za-z][A-Za-z0-9_.,\[\]= ]*\)"),
    # Four more of the 5 closing-out named exceptions (reports/
    # phase2_tokeniser.md S10.2): each an orphaned "(NAME" vocal-noise
    # annotation whose closing ")" is entirely missing from the raw text
    # (replaced by nothing, a nested unclosed breath cue, or a bracket-
    # then-digit run -- vocal_noise_caps above correctly fails to match
    # any of these, since it requires a literal ")" that never appears).
    # Each pattern is anchored to its own exact surrounding context, not a
    # general "missing paren" rule -- widening vocal_noise_caps itself to
    # tolerate a missing close would silently swallow the question of
    # what's actually inside, corpus-wide, not just here.
    #
    # SBC002 line 466, "(TSK (H)3]": "(TSK" dropped whole; the nested
    # "(H)" that follows is an ordinary, already-matched breath_in cue,
    # and "3]" is an ordinary, already-matched overlap-num-close leftover
    # -- only the orphaned "(TSK" itself needed a new rule.
    ("drop", "sbc002_tsk_named_exception", r"\(TSK(?=\s\(H\)3\])"),
    # SBC019 line 116, "... (SNIFF .. (Hx) (Hx)=)": "(SNIFF" is dropped
    # the same way; its own close never appears -- the IU's final ")"
    # (otherwise unmatched, since it belongs to no other span) is the
    # orphaned close and needs its own anchored exception. Everything in
    # between (the pause, both "(Hx)" breath cues, the lengthening "=")
    # already tokenises correctly on its own.
    ("drop", "sbc019_sniff_open_named_exception", r"\(SNIFF(?=\s\.\.\s\(Hx\)\s\(Hx\)=\))"),
    ("drop", "sbc019_sniff_close_named_exception", r"(?<=SNIFF\s\.\.\s\(Hx\)\s\(Hx\)=)\)"),
    # SBC023 line 1469, "[(SNIFF)] [2(SNIFF2]": the first "[(SNIFF)]" is
    # already well-formed and tokenises correctly (a complete
    # vocal_noise_caps match inside a plain overlap bracket). Only the
    # second, "[2(SNIFF2]", is malformed -- the bracket-then-digit-run
    # shape, "2]" landing where "SNIFF"'s own ")" should be. Anchored to
    # the preceding "[2" so it cannot fire on the first, well-formed
    # occurrence in the same IU.
    ("drop", "sbc023_sniff_bracket_digit_named_exception", r"(?<=\[2)\(SNIFF(?=2\])"),
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
    # SBC001, "<@SM ... SM@>": "@" and "SM" stacked with no space between
    # them, at both open and close -- two quality markers combined into
    # one compound delimiter (a shorthand for the fully-nested
    # "<@<SM ... SM>@>" form), not "@" plus the real word "SM". Anchored
    # to this exact, single, consistent pairing. Tried BEFORE the general
    # code rules below: "@" alone is also a valid code, and being shorter
    # it would otherwise win first, stranding "SM" to leak through as a
    # bogus real word.
    ("drop", "at_sm_open_named_exception", r"<@SM(?=\s)"),
    ("drop", "at_sm_close_named_exception", r"(?<=\s)SM@(?=>)"),
    # Single-angle tag codes, closed-inventory version (reports/
    # phase2_tokeniser.md S19, replacing the old "any letters" pattern
    # that swallowed real content glued to the delimiter with no space --
    # 19 confirmed instances, "<@Mm@>", "<@in San...", "Go]=dX>." among
    # them). Tried in this order: the zero-content wrap ("<VOX>", same
    # "match the whole thing first" reasoning as double_angle_wrap, so a
    # greedy open doesn't strand the close with nothing left to match);
    # then open, open-with-a-stray-space, and close.
    ("drop", "angle_wrap_code", rf"<(?:{_ANGLE_TAG_ALTERNATION})>"),
    ("drop", "angle_open_code", rf"<(?:{_ANGLE_TAG_ALTERNATION})"),
    # A space between "<" and the code (confirmed a prior session, SBC043:
    # "< HI any nights HI>") -- same "no pairing" treatment: stripped on
    # sight, not verified against a close.
    ("drop", "angle_open_spaced_code", rf"<\s+(?:{_ANGLE_TAG_ALTERNATION})"),
    ("drop", "angle_close_code", rf"(?:{_ANGLE_TAG_ALTERNATION})>"),
    # SBC058, "VOXX>": the closing "VOX" (repeating the "<VOX" opener) is
    # immediately followed by a third indecipherable-syllable "X" with no
    # space, then ">". Without this, the guarded "word" rule below would
    # match "VOX" alone as a bogus real word (its own guard only stops it
    # before "X>", not before "VOX" itself). Dropping "VOX" here prevents
    # that regression; the trailing "X>" is then claimed by
    # angle_close_code as an ordinary close, same as the pre-fix
    # behaviour -- this one trailing indecipherable-syllable "X" is not
    # additionally recovered as content (two others, "XX" and "X",
    # already survive earlier in the same IU), an accepted limitation of
    # this single, anchored exception, not pursued further.
    ("drop", "voxx_named_exception", r"VOX(?=X>)"),
    # A stray "<" or ">" that doesn't open/close a recognised code: the
    # delimiter character itself is a transcription artifact here (like a
    # NUL byte or the lost-initial-letter "0"), stripped and never
    # reconstructed -- whatever real content sits next to it (SBC016
    # "<0r", SBC023 "<or", SBC025 "<ot", SBC033 "<Hi") survives untouched
    # via the ordinary word rule below. Reached only after every
    # code-anchored rule above has had first claim, so a genuine code is
    # never mistaken for a stray. Confirmed corpus-wide (S17.1/S19): "<"
    # and ">" are never real content in this corpus.
    ("drop", "angle_stray_open", r"<"),
    ("drop", "angle_stray_close", r">"),
    # SBC056 line 1169, "(@Hx)": the fifth and last of the 5 named
    # exceptions closing out the tokeniser raises. Laughter "@" landed
    # inside an otherwise-ordinary breath_out annotation, with no
    # documented compound for "@" co-occurring with a breath cue (unlike
    # "(%Hx)"'s glottal_breath above). Per the decision: the laughter is
    # dropped (not rendered as a cue, unlike glottal_breath's own "%"),
    # and "(Hx)" survives as an ordinary breath_out cue -- the same
    # decomposition shape as breath_paren_lengthening, just with the "@"
    # discarded rather than converted into a second cue. Anchored to the
    # literal, single corpus occurrence, not a general "(@...)" rule.
    ("compound", "sbc056_laughter_breath_named_exception", r"\(@Hx\)"),
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
    # followed by a letter -- still raises: this is not a general rule for
    # these three characters, only the letter-prefix case is authorised.
    # Three named, logged, one-off exceptions to that, all confirmed this
    # session:
    #   - "[#5Jason #Dill5]": "#" directly before a digit, not a letter --
    #     strip just the "#"; the digit that follows falls to
    #     overlap_leftover_digit above, and "Jason" then fuses normally.
    #   - "*#Vodnoy": a second, stacked disguise prefix -- strip the
    #     leading "*"; "#Vodnoy" is then the already-authorised letter-
    #     prefix case on its own.
    #   - "X[3X3]*": a trailing "*" with nothing after it at all -- strip
    #     it; there is no word for it to disguise the start of.
    ("drop", "jason_hash_digit_named_exception", r"#(?=5Jason)"),
    ("drop", "stacked_disguise_prefix_named_exception", r"\*(?=#[^\W\d_])"),
    ("drop", "star_trailing_named_exception", r"\*(?!\S)"),
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
    # A trailing "-" is allowed in the lookahead too (confirmed this
    # session: "0-", "0.000000e+00-" -- the same artifact immediately
    # followed by a truncation hyphen rather than a letter); stripping it
    # leaves a lone "-" for the standalone-hyphen rule to handle on its
    # own, not a reason to widen this rule's own scope any further.
    ("drop", "lost_initial_letter", r"0(?:\.000000(?:[eE]\+00)?)?(?=[a-z-])"),
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
    # "-{2,}" not just "--": a literal "---" (confirmed this session,
    # SBC010 "I want---") is the same IU-truncation annotation, just
    # emphatic/repeated -- one Boundary item with the full run as its
    # raw text, logged as such (not silently identical to a plain "--"),
    # not a separate leftover "-" for the standalone-hyphen rule to
    # raise on.
    ("boundary", "iu_truncation", r"-{2,}"),
    # A single hyphen, not part of "--", in one of five authorised shapes
    # -- see _handle_displaced_trunc for all five: displaced past a
    # lengthening/glottal mark ("b=-", "%-"); a compound split by a
    # dropped delimiter ("third]-graders", confirmed this session); a
    # leading hyphen starting a word ("eighty .. -three", confirmed this
    # session); or a standalone hyphen glued to nothing on either side
    # (confirmed this session, removed in both conditions). Anything else
    # still raises -- this is not a general orphan-hyphen rule.
    ("displaced_trunc", "displaced_truncation", r"-(?!-)"),
    ("cue", "lengthening", r"="),
    ("cue", "accent_caret", r"\^"),
    ("cue", "accent_backtick", r"`"),
    ("cue", "booster_bang", r"!"),
    ("cue", "booster_semi", r";"),
    ("cue", "glottal", r"%"),
    ("cue", "pitch_backslash", r"\\"),
    # "_" and "/" were reclassified out of tier 2 last session: neither is
    # a terminal-pitch cue. "/" is exclusively the delimiter of a
    # slash-bracketed phonetic respelling ("/god/"). "_" is (a) a
    # word-internal compound joiner (handled directly in the "word"
    # pattern below -- "part of the word", not a mark that fuses by
    # omission), (b) the leading character of a phonetic-gloss suffix
    # ("good_/god/"), or (c) -- confirmed this session, not guessed --
    # SBC012/SBC013's own file-local variant of the standard truncation
    # marks: standalone "__" (2+) is that file pair's "--", and a trailing
    # "word_" is that file pair's "word-". Evidence: "__" has the exact
    # same corpus-wide position signature as "--" (100% IU-final: 156
    # after-last-word + 2 no-words, zero before/between); both files rank
    # in the bottom 3-8 of 59 for ordinary "-"/"--" rate (SBC012 20/25 per
    # 1000 IUs vs a corpus median of 66/65; SBC013 25/19) -- exactly what
    # a local substitute convention predicts. See the boundary rule for
    # "__" and the underscore_trunc kind for "word_" below.
    #
    # A phonetic-gloss suffix is dropped whole -- the slash-delimited
    # respelling is not the orthographic word either, so it isn't kept:
    # only the word before the "_" survives, per the "kept always" tier-3
    # rule already covering that word on its own.
    ("drop", "word_gloss_suffix", r"_\(?/[^/]*/\)?"),
    # SBC012/SBC013's "--" equivalent: tried before the single-"_" rule
    # below so a run is never partially eaten by it.
    ("boundary", "underscore_iu_truncation", r"_{2,}"),
    # SBC012/SBC013's "word-" equivalent: a single "_" glued right after a
    # word, not part of a run and not a gloss suffix (both already claimed
    # above). Handled specially in tokenize() (_handle_underscore_trunc):
    # normalises to a literal "-" in the word text, exactly like "word-"
    # elsewhere in the corpus, and only when a word is actually open to
    # attach it to -- a "_" glued to something else (a mark, a bracket)
    # is not this pattern and still raises.
    ("underscore_trunc", "underscore_truncation", r"_(?!_)"),
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
    #
    # Each letter is guarded (_ANGLE_TAG_CLOSE_GUARD) against extending
    # into a recognised angle-tag close code immediately ahead ("knowX>",
    # "XXP>", S19): without it, this rule's own greedy letter class has no
    # way to know where real content ends and "X>"/"P>" begins, and
    # swallows straight through -- "knowX" as one bogus word instead of
    # "know" (kept) + the close code (dropped).
    ("frag", "word", rf"'?(?:{_ANGLE_TAG_CLOSE_GUARD}[^\W\d_])+(?:['_-](?:{_ANGLE_TAG_CLOSE_GUARD}[^\W\d_])+)*(?:-(?!-)|')?"),
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


def _glued_frag_follows(matches: list[re.Match], i: int, text: str) -> bool:
    """True if, walking forward from matches[i] with no whitespace anywhere
    along the way, a word-fragment match is eventually reached -- skipping
    over any number of intervening tier-1 "drop" delimiters, not just zero
    or one. Needed for a hyphen sandwiched between two delimiters on
    *both* sides ("third]-[2graders", confirmed this session): the match
    right after the hyphen is another dropped delimiter ("[2"), not the
    frag itself, but "graders" is still the hyphen's own continuation --
    the delimiters in between are exactly as incidental as a single one
    would be.
    """
    j = i + 1
    prev_end = matches[i].end()
    while j < len(matches):
        nxt = matches[j]
        if not _is_glued(text, prev_end, nxt.start()):
            return False
        kind = _KIND_OF[nxt.lastgroup]
        if kind == "frag":
            return True
        if kind != "drop":
            return False
        prev_end = nxt.end()
        j += 1
    return False


def _glued_frag_or_trunc_follows_through_cues(matches: list[re.Match], i: int, text: str) -> bool:
    """True if, walking forward from matches[i] with no whitespace anywhere
    along the way, a frag or displaced_trunc match is eventually reached --
    skipping over any number of intervening "cue"- or "drop"-kind matches,
    not just zero or one. Two distinct real-corpus shapes need this, both
    the same one-hop-lookahead root cause as the already-fixed
    _glued_frag_follows (hyphen case):

    - A RUN of 2+ glued cue marks between two word fragments ("b==itch",
      confirmed this session): the match right after the FIRST "=" is the
      SECOND "=" (kind "cue"), not the frag -- checking only one match
      ahead made every cue but the last in the run look unsandwiched,
      flushing the word prematurely ("b", "itch" instead of "bitch").
    - A single cue immediately followed by a glued "drop"-kind delimiter
      before the frag ("fa=]st?", "do=[ing,", "[2u=2]m,", confirmed this
      session): checking only one match ahead saw the overlap-bracket
      delimiter, not "st"/"ing"/"m", and again flushed early ("fa", "st"
      instead of "fast"). The delimiter is exactly as incidental here as
      it already is in the plain "drop" fusion case (li[2ke2], -> like);
      the cue in front of it doesn't change that.
    """
    j = i + 1
    prev_end = matches[i].end()
    while j < len(matches):
        nxt = matches[j]
        if not _is_glued(text, prev_end, nxt.start()):
            return False
        kind = _KIND_OF[nxt.lastgroup]
        if kind in ("frag", "displaced_trunc"):
            return True
        if kind not in ("cue", "drop"):
            return False
        prev_end = nxt.end()
        j += 1
    return False


def _sandwiched(matches: list[re.Match], i: int, text: str) -> bool:
    """True if the cue at matches[i] sits directly between two letter runs
    with no whitespace on either side (e.g. the "=" in "s=o"), so it should
    fuse into the surrounding word rather than end it. A cue glued only on
    one side (trailing, e.g. "you're--") is not sandwiched -- it still ends
    the word, just with no space before it in the raw text.

    A displaced-truncation hyphen counts as a continuation here too, not
    just an ordinary word fragment: "b=-" must keep "=" open rather than
    ending the word at "b", so the hyphen can still reach it one match
    later (see _handle_displaced_trunc). And a run of further glued cue
    marks before that frag/hyphen is itself not a reason to stop looking
    (see _glued_frag_or_trunc_follows_through_cues).
    """
    if i == 0:
        return False
    if not _is_glued(text, matches[i - 1].end(), matches[i].start()):
        return False
    return _glued_frag_or_trunc_follows_through_cues(matches, i, text)


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
            if name == "glottal_breath":
                group = m.group("gb_letter")
                breath_kind = "breath_out" if group.lower() == "hx" else "breath_in"
                items.append(Cue(kind="glottal", raw="%"))
                items.append(Cue(kind=breath_kind, raw=f"({group})"))
            elif name == "breath_bracket_lengthening":
                group = m.group("bbl_letter")
                breath_kind = "breath_out" if group.lower() == "hx" else "breath_in"
                items.append(Cue(kind=breath_kind, raw=f"({group}["))
                items.append(Cue(kind="lengthening", raw="=])"))
            elif name == "sbc015_breath_bracket_lengthening_named_exception":
                # "[2(H]=2]" -- the numbered overlap brackets tokenise on
                # their own before/after this match; only the compound
                # itself (breath_in + lengthening, "]" standing in for the
                # missing ")") is produced here.
                items.append(Cue(kind="breath_in", raw="(H]"))
                items.append(Cue(kind="lengthening", raw="="))
            elif name == "sbc056_laughter_breath_named_exception":
                # "(@Hx)" -- laughter dropped, breath_out survives alone.
                items.append(Cue(kind="breath_out", raw="(Hx)"))
            else:  # breath_paren_lengthening: "(H=)"/"(h=)", case-folded
                group = m.group("bpl_letter")
                breath_kind = "breath_out" if group.lower() == "hx" else "breath_in"
                items.append(Cue(kind=breath_kind, raw=f"({group}"))
                items.append(Cue(kind="lengthening", raw="=)"))
            continue

        if kind == "displaced_trunc":
            action = _handle_displaced_trunc(
                matches, i, text, glued, pending_active, pending_norm_pieces, pending_raw_pieces, items, flush_word
            )
            if action == "flush":
                # The hyphen completed the pending word (attached case):
                # flush it now, since truncation always ends a word.
                flush_word()
            elif action in ("keep_open", "start_new"):
                # The hyphen continues into more letters -- a compound
                # split by a delimiter ("third]-graders") or a leading
                # hyphen starting a word ("eighty .. -three") -- do not
                # flush; the next frag match appends onto what's pending.
                pending_active = True
            elif action == "isolated":
                flush_word()
                items.append(Boundary(kind="isolated_hyphen", raw="-"))
            # "cue_only": nothing further to do.
            continue

        if kind == "underscore_trunc":
            # SBC012/SBC013's "word_" == elsewhere's "word-" (confirmed,
            # not guessed -- see the rule table comment above): when a
            # word is open, the "_" completes it, normalised to "-".
            #
            # "%_you" (confirmed this session, S2 of the closing pass):
            # a mark, not a word, directly before "_", with nothing open
            # -- handled exactly as "-" already is in the same position
            # ("%-you" -> Cue(glottal), Cue(displaced_truncation), then
            # "you" starts fresh): the "_" becomes its own standalone,
            # non-word-forming token, not raised, regardless of what kind
            # of mark precedes it (glottal, lengthening, or a dropped
            # construct like "(TSK)" -- all confirmed present in the
            # corpus's actual 20 cases, not just the glottal one).
            if glued and pending_active:
                pending_norm_pieces.append("-")
                pending_raw_pieces.append("-")
                flush_word()
            elif glued and i > 0:
                items.append(Cue(kind="underscore_truncation", raw="_"))
            else:
                _raise_unrecognised(text, "_", m.start())
            continue

    flush_word()
    return items


def _handle_displaced_trunc(
    matches: list[re.Match],
    i: int,
    text: str,
    glued_before: bool,
    pending_active: bool,
    pending_norm_pieces: list[str],
    pending_raw_pieces: list[str],
    items: list[TokenItem],
    flush_word: Callable[[], None],
) -> str:
    """A single hyphen not part of "--", in one of four authorised shapes.
    Returns an action for the caller: "flush" (word is complete, flush
    it), "keep_open" or "start_new" (word continues -- caller must not
    flush and must ensure pending_active is True for the next frag match
    to attach to), or "cue_only" (nothing else to do). Raises for anything
    outside these four shapes -- this is not a general orphan-hyphen rule.

    Bug fixed this session (reports/phase2_tokeniser.md S12/S14): cases 4
    and 5 below used to assume "not glued_before" meant no word could
    possibly be pending -- true when the hyphen follows a cue/boundary
    (which always flushes first), but false when it follows an ordinary
    word ended only by whitespace, with nothing in between to trigger a
    flush ("uh -gerald": "uh" is still open when the "-" match arrives).
    The old code appended the hyphen onto that stale pending word instead
    of starting a new one -- "uh-gerald" as one wrong word, silently, no
    raise. Both branches below now flush any pending word themselves
    (via the caller's own flush_word, so the already-open word becomes
    its own correct, complete Word) before deciding what the hyphen
    itself does.

    1. **Displaced truncation** ("b=-", "%-"): a hyphen displaced from its
       word by an intervening lengthening/glottal mark. Word-final --
       "b=-" tokenises to the one word "b-", same "kept always" treatment
       as a plain "y-". "flush".
    2. **The same mark, with no word open** ("%-" alone): the hyphen
       becomes its own Cue, not a word -- CLAUDE.md's tiers don't say
       whether a mark-only run like this is a word, and this function
       does not decide that either. "cue_only".
    3. **A dropped delimiter incidental to the word's own hyphen**
       ("third]-graders", confirmed this session): the previous match is
       some other tier-1 "drop" delimiter (not lengthening/glottal).
       Continuation ("graders") may itself be past more than one such
       delimiter ("third]-[2graders", `_glued_frag_follows` walks past
       all of them, not just one). Two sub-cases if a word is open --
       delimiter incidental, hyphen is the word's own, not a reason to
       end it prematurely: more letters glued on the other side keeps
       the word open, "keep_open"; nothing there completes it right where
       it is, same as a plain "y-", "flush" ("[Degener]- --"). **No word
       open** (confirmed this session: "0-", "0.000000e+00-", both after
       `lost_initial_letter` strips the artifact and leaves a bare "-"
       glued to nothing real) -- same choice, decided the same way:
       "start_new" if letters follow glued, "isolated" otherwise.
    4. **A leading hyphen starting a word** ("eighty .. -three", confirmed
       this session): not glued to anything before (so no word is open --
       verified by construction, since every other kind flushes on a
       non-glued transition before this point is ever reached), but glued
       to letters after -- mirrors "y-"'s trailing form. "start_new".
    5. **A standalone hyphen, glued on neither side** (confirmed this
       session): removed in both conditions, logged rather than silently
       dropped -- the caller appends a Boundary. "isolated".
    """
    glued_after = _glued_frag_follows(matches, i, text)

    if glued_before and i > 0:
        prev_name = matches[i - 1].lastgroup
        if prev_name in ("lengthening", "glottal"):
            if pending_active:
                pending_norm_pieces.append("-")
                pending_raw_pieces.append("-")
                return "flush"
            items.append(Cue(kind="displaced_truncation", raw="-"))
            return "cue_only"
        if _KIND_OF[prev_name] == "drop":
            if pending_active:
                pending_norm_pieces.append("-")
                pending_raw_pieces.append("-")
                return "keep_open" if glued_after else "flush"
            # No word open, and the thing immediately before is itself
            # invisible in the output (a dropped delimiter or, confirmed
            # this session, the lost_initial_letter artifact stripped
            # from "0-"/"0.000000e+00-") -- nothing real is actually
            # attached on that side. Same "start a word" / "stand alone"
            # choice as the not-glued-before case just below, decided the
            # same way: more letters glued after -> start one; otherwise
            # isolated.
            if glued_after:
                pending_norm_pieces.append("-")
                pending_raw_pieces.append("-")
                return "start_new"
            return "isolated"
        _raise_unrecognised(text, "-", matches[i].start())

    if not glued_before and glued_after:
        if pending_active:
            # The word before this hyphen ended at whitespace, not glued
            # to it -- it is already complete (e.g. "alw-", itself
            # correctly truncated) and must not be extended. Flush it as
            # its own Word first, so the hyphen below genuinely starts a
            # new one instead of silently fusing onto the old.
            flush_word()
        pending_norm_pieces.append("-")
        pending_raw_pieces.append("-")
        return "start_new"

    if not glued_before and not glued_after:
        # 5. A standalone "-" with nothing glued on either side (confirmed
        # this session): not a truncation, not a compound -- a bare, free-
        # floating dash. Removed in both conditions, same as a Boundary,
        # but logged as its own kind rather than silently absent. Same
        # stale-pending-word fix as case 4 above: flush first if needed.
        if pending_active:
            flush_word()
        return "isolated"

    _raise_unrecognised(text, "-", matches[i].start())


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

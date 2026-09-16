# Phase 2, stage 4 — Tokeniser: marker inventory, implementation, reader fixes, and decisions

Working report. Not for circulation.

Formerly `reports/phase2.md`, renamed to distinguish it from the reader
report (`reports/phase2_data.md`). This revision supersedes the previous one
throughout: several figures below changed materially in this session, and
where they did the old number is named and corrected rather than silently
dropped.

---

## 1. What this stage did and why

Reader stages 1-3 (`reports/phase2_data.md`) turned the 60 `.trn` files into
70,007 intonation units (IUs) of raw text, markers and all. Stage 4 turns
that raw text into the atomic unit the pipeline scores on: the word. Before
writing a tokeniser, every non-word symbol across the whole corpus was
catalogued against CLAUDE.md's tiers, because guessing a rule from a handful
of examples had already produced wrong numbers once in this project
(`reports/phase2_data.md` §8). The tokeniser was then written to raise on
anything not covered by an explicit rule, rather than guess.

Three passes followed, each turning the tokeniser's own raise output into a
worklist: the first fixed two reader defects the raises had exposed and gave
named handling to four combinations of already-documented marks; this
session's pass makes five further decisions explicitly authorised by you
(§2), and runs six checks that were requested *without* authorising new
rules (§3) — several of those checks found that a figure reported last
session was wrong, or that two of this project's own scripts disagreed with
each other. SBC037 is excluded from every figure in this report throughout,
since it is out of scope for scoring (bilingual code-switching,
`reports/phase2_data.md` §6).

---

## 2. Decisions implemented this session

Each below: the rule, a hand-written test, and a whole-corpus count of IUs
affected (current run, 69,029 IUs, SBC037 excluded).

**Before anything else, from the code** (not from memory of a prior
session): `tokenize()` matched `.`, `,`, `?` against a rule that called
`flush_word()` and then emitted **nothing** — no `Word`, no `Cue`. They were
invisible in the returned sequence and never raised.

**a) `. , ? --` are a boundary annotation, not a cue — removed in both
conditions.** A new `TokenItem` type, `Boundary`, was added: like `Cue` it
never fuses a word cluster, but unlike `Cue` it is never rendered in either
condition (`render()` skips it always). `--` moves here from tier 2 (it
never actually embedded mid-word — confirmed unchanged). `.`, `,`, `?` move
from producing nothing to producing a named, inspectable `Boundary` item.
Justification, from the marker inventory: these four are IU-final in
99.4-100% of occurrences (period 99.82%, comma 99.92%, qmark 100%, IU
truncation 99.4%) — the boundary itself, not a prosodic quality of a word.
Test: `test_iu_truncation_after_word_no_space` (updated) and the existing
continuity-punctuation test. **62,899 of 68,689 tokenised IUs (91.6%)**
contain at least one `Boundary` item. CLAUDE.md's "Tokenisation" section was
updated this session to record this as a fourth category alongside the
three original tiers, rather than leaving `. , ?` as unlisted and `--` under
tier 2.

**b) `~ # *` immediately followed by a letter: strip the prefix, keep the
word, both conditions.** Any other occurrence (not followed by a letter —
end of string, a digit, another mark) still raises; this is not a general
rule for these three characters. Tests: `test_disguise_prefix_tilde/hash/star`,
plus three raise-cases (`~ Mae` with a space, `X[3X3]*` with nothing after,
`[#5Jason]` with a digit after). **1,149 IUs** contain at least one
occurrence matching the letter-prefix rule.

**c) `<%` and `%>`: span-tag delimiters, stripped like `<@` and `@>`.** The
angle-bracket character classes were extended to include `%`. Test:
`test_percent_span_tag`. **64 IUs** contain `<%` or `%>`.

**d) `0.000000e+00` / `0.000000E+00` glued to a word: strip the artifact,
keep the remaining letters, do not reconstruct.** Named, logged exception
(`float_artifact_named_exception`), same principle as the reader's NUL-byte
handling. Tests: `test_float_artifact_glued_to_word`,
`test_float_artifact_uppercase_e`, plus a raise-case for the non-glued form.
**5 occurrences, in 5 files** — not 3, correcting what was reported verbally
last session (see §4). One of the five (`SBC026`) still raises: the same IU
also contains an unrelated stray-`0`-for-letter typo elsewhere in it, in a
different word, that this rule does not and should not touch.

**e) Zero-word IUs are dropped from the reference, identically in A and B;
their cues remain available for B's rendering.** New function
`reference_segments(iu_items)`: filters a document's per-IU token lists down
to those with at least one word. Tests: `test_reference_segments_drops_zero_word_ius`,
`test_reference_segments_identical_under_a_and_b`. Segment counts per file,
before/after (`reports/phase2_reference_segments_by_file.csv`, full 59-file
table; totals only here):

| | before | after | dropped |
|---|---|---|---|
| **all 59 files** | 68,689 | 63,392 | 5,297 |

Largest single-file drops: `SBC013` 2,239→1,861 (−378), `SBC006` 1,757→1,494
(−263), `SBC036` 1,817→1,604 (−213), `SBC028` 1,521→1,318 (−203), `SBC031`
1,536→1,333 (−203).

46 of 46 old tests plus 8 new ones pass (54 total); full suite 577 passed,
11 skipped.

---

## 3. Checks (no new rules)

**a) `"...("` and `"(0"` as raw substrings.** `"...("`: **20 IUs**, every
single one `...(H)` — pause immediately glued to breath-in, never the
documented timed-pause form `...(N)` (which requires a *digit* inside the
parens and has zero real occurrences, confirmed again here independently of
any regex). `"(0"`: **0 occurrences.** Both confirm the earlier PAUSE_TIMED=0
and LATCHING=0 findings were not a pattern-matching gap.

10 examples each were pulled and reviewed in the terminal (not reproduced
here — raw examples stay terminal-only). Current raise set, down
substantially after §2's fixes (see §4):
- **Stray `0`** (65 IUs): unchanged in character from last session —
  isolated letter→`0` corruption (a digit substituting for a vowel or
  consonant at various positions in various words), concentrated in
  `SBC015`/`SBC016`, no single consistent substitution rule. Not latching,
  not a missed pause form.
- **Orphaned `(`** (44 IUs): a missing closing paren after a vocal-noise
  name; empty parens with nothing inside (`SBC016`, several instances); a
  stray-0 typo inside a vocal-noise name; an overlap bracket landing inside
  a vocal-noise word, splitting it; a lowercase breath-marker variant; an
  overlap bracket landing inside a breath marker. None fit an authorised
  rule.
- **Orphaned `)`** (1 IU): a single stray close-paren with no opening paren
  anywhere in the IU.
- **Stray digits** `1 2 3 6` (9 IUs total): unchanged — isolated numbered-
  overlap digits with no adjacent bracket character, a transcription typo,
  not a pattern gap.

**b) `<<TAG ... TAG>>`: §3.2 (marker inventory) counted 83 closes; §3.3 (the
follow-up script) counted 93. Explained.** `reports/phase2_marker_inventory.csv`
is undercounted by exactly 10 — not a corpus fact, a scanning artifact in
`sbcsae_marker_inventory.py`: its `DOUBLE_ANGLE_OPEN` pattern (`<<[A-Za-z]+`)
is tried in a priority-ordered, non-overlapping scan and greedily consumes
the tag name, so for the 10 IUs where open and close are *immediately
adjacent with no content between them* (tag names THUMP, STAPLE, PAPERS,
and POUND ×4, plus one instance each of two multi-word tags — see below),
the close pattern (`[A-Za-z]+>>`) has no letters left to match against —
they were already eaten by the open. **§3.3's 93 is the reliable count**; verified by
an independent re-implementation (open/close searched separately, not as
mutually-exclusive alternatives in one scan) — confirmed 94 opens / 93
closes exactly.

**§3.2's figure is marked provisional in the table below.**

**Every open/close name mismatch, explained — also an extraction artifact,
not a corpus fact.** All six close-only names (`NOISE` ×9, `GLASSES`,
`STOPS`, `BARKING` ×2, `SINK`, `RUNNING`) come from **underscore/hyphen-
joined multi-word tag names**: `WATER_RUNNING_AND_DISH_NOISE`,
`ERASER_NOISE`, `RUMBLING_NOISE`, `MIC_NOISE`, `MACHINE_STOPS`,
`DOG_BARKING`/`DOGS_BARKING`, `WATER_RUNNING_IN_SINK`, `WATER_RUNNING`,
`BANG-GLASSES`, `VOMIT-SOUND`/`VOMIT-NOISE`. Both counting scripts' tag-name
character class is `[A-Za-z]+` — it excludes `_` and `-`, so the open-side
regex captures only the *first* word-fragment of a multi-word name and the
close-side regex captures only the *last*. `WATER_RUNNING_AND_DISH_NOISE`
therefore shows up as open-tag `WATER` and close-tag `NOISE` — the same tag,
counted as if it were two, by an artifact of the extraction regex, not a
real naming inconsistency in the corpus. All 15 raw lines behind these six
mismatches were checked (§3.2 count of distinct names is descriptive
metadata, not fed into any score, so left as-is rather than marked
provisional).

**Do tags span multiple words?** Yes: 16 opens have ≥2 space-separated words
of real content before a same-IU close.

**"I is a capitalised word"** — checked directly: no `<<I` or `I>>`
adjacency exists anywhere in the corpus. The concern was valid (a tag-name
regex with no word-boundary requirement could mistake the pronoun "I" for a
one-letter tag name if content directly abutted a delimiter with no space,
the same mechanism that produces the `BANG`/`GLASSES` split above) but does
not manifest here. Separately, `<<B ... B>>` (`SBC008`) is a genuine,
symmetric one-letter tag name, not an artifact — it appears correctly on
both sides.

**c) `+`: §3.3 said it occurs only inside `<<...>>`; §4's float-artifact
finding shows `+` inside `0.000000e+00` in three files. Reconciled, and a
further correction beyond just those two contexts.** Checked every `+`
occurrence directly: of 76 IUs containing `+`, only 54 have it exclusively
inside `<<...>>` or the float artifact. **The other 22 do not** — `+` also
occurs inside single-angle tags (a single-word quality-tag case and a
`<%...%>` case), and, more consequentially, **standalone in ordinary
running text**: word-initial, word-internal, and word-final attachment
across roughly a dozen distinct words in several files, always glued
directly to a word with no space. This pattern — attaching to a word's edge
or interior, never appearing alone — is the same shape as the documented,
currently-zero-occurrence accent marks `^`/backtick. **§3.3's "occurs only
inside `<<...>>`" claim is wrong and is corrected here; no tier is assigned
to `+` by this correction.** 10 examples of `+` inside `<<...>>` confirmed
separately in the terminal (all consistent with the compound-quality-span
reading already in §2 of the prior report).

**d) Every distinct speaker token per file, with IU and word counts**
(`/tmp/speaker_roster.csv` this session, 356 distinct file/speaker pairs —
not committed, regenerable from `iter_trn_documents()` directly). 51 rows
flagged as not a participant name:
- **40** are `>ENV` / `>DOG` / `>CAT` / `>MAC` / `>BABY` / `>HORSE` /
  `>RADIO` — genuine non-human pseudo-speaker sources (Du Bois's convention
  for environmental/animal/machine sound), not errors.
- **3** are documented uncertain-attribution forms: `KEN/KEV` (dual-speaker
  label), `SUE?`, `NORA?` (uncertain attribution).
- **1** is `@@@2]` (`SBC056`) — genuine leftover garbage from the tab
  branch's "everything before the first tab is the speaker" rule, unrelated
  to this session's fixes.
- **4** are real spoken text mis-attributed as a speaker name — the tab
  branch's permissive rule has no way to tell a genuine colon-less speaker
  code (e.g. `MONTOYA`) from ordinary dialogue that happens to precede a tab
  with no real speaker field: one each in `SBC027` (3 IUs / 9 words
  wrongly attributed), `SBC055` (3 IUs / 15 words), `SBC059` (1 IU), and
  `SBC060` (2 IUs / 4 words) — each case a short fragment of ordinary
  speech, not a real speaker code, misread as one. Pre-existing, not
  touched this session (see §4/§6).

**Explaining 84 changed IUs vs. 60 colons.** Traced precisely: of the 84 IUs
the speaker-colon fix changed, **60 had their own leaked `SPEAKER:` prefix
directly** (exactly matching the marker inventory's pre-fix `':'` count of
60) and **24 are cascade corrections** — blank-speaker continuation lines
that never had a colon of their own, whose *effective* speaker value changed
only because they inherit `current_speaker`, which one of the 60 direct
fixes corrected upstream of them (the `SBC013` 481-559 run accounts for
most of these). 60 + 24 = 84 exactly.

**e) 10 examples each of `_` and `/` in non-final position** (via the
marker-inventory scan, not a raw substring search — the latter over-counts
`_`/`/` occurring inside `((...))`/`(CAPS)` spans, which are already
consumed by an earlier rule and never reach the pitch-mark classification;
examples reviewed in the terminal, not reproduced here). Genuinely found a
second, distinct function neither tier currently describes: `_` directly
followed by a `/phonetic/` span reads as a **mispronunciation-correction
marker**, not terminal pitch — a handful of instances across several files
where an ordinary word is immediately followed by an underscore and a
slash-delimited phonetic respelling of it. Other non-final `_` cases look
like restart/self-correction boundaries within a word. No rule is proposed
or implemented for this.

**f) All 5 four-fragment fusions** (reviewed in the terminal): one number
word interrupted three times by lengthening marks (`SBC009`); one proper
name split by two separate overlap brackets (`SBC013`); one word
interrupted twice by lengthening marks (`SBC056`); and two from one
`SBC058` singing span, each a run of repeated sung syllables joined by
underscores. **20 random three-fragment fusions** (of 183 total) also
reviewed in the terminal — mostly a word interrupted twice by overlap
brackets or lengthening marks.

**A side effect surfaced by (f), not by design:** the `SBC058` singing-span
fusions and a three-fragment fusion in `SBC012` (a spoken-out date,
underscore-joined) show that the *same* mid-word fusion mechanism used for
lengthening marks also fuses underscore-joined material that plausibly
should stay separated (a sung syllable sequence; a hyphenated/spaced date
expression) into one run-together word. This is a consequence of `_`'s
current tier-2, fusable-mark classification interacting with the (e)
finding above — reported, not fixed.

---

## 4. Problems found, including corrections to prior reporting

**A number given verbally in the prior session was wrong.** "3 files" for
the float artifact — actual count, verified against the raw distributed
bytes: **5 occurrences, 5 files** (`SBC015`, `SBC017`, `SBC020`, plus
`SBC025` and `SBC026`, missed in the earlier pass). Corrected in §2d.

**A claim in the prior §3.3 was wrong.** "`+` occurs only inside
`<<...>>`" — actually true for 54 of 76 IUs containing `+`; the other 22
include standalone word-attached occurrences that look like an
undocumented accent/stress marker. Corrected in §3c; the underlying raw
count (`+`: 177 occurrences, 24 files, unchanged from the original marker
inventory) was never wrong — only the earlier narrative characterisation of
where it occurs was incomplete.

**`reports/phase2_marker_inventory.csv`'s `DOUBLE_ANGLE_CLOSE` figure (83)
is undercounted by 10, root-caused in §3b**: a priority-ordered single-pass
scan cannot award the same tag-name letters to both an open pattern and a
close pattern when they are immediately adjacent with no content between
them. **Marked provisional below.** The tag-name lists in the same table
(and in the prior report) additionally undercount distinct names for any
tag using `_` or `-` internally, for the same character-class reason — the
counts of *occurrences* are unaffected, only the *distinct name* lists are
artifacts.

**Two zero-word classification scripts disagreed and are now one.**
`sbcsae_tokenizer_validate.py`'s persisted 4-category breakdown and
`sbcsae_followup_analysis.py`'s separate 8-category breakdown gave different
`breath_only` counts (236 vs. 242) because of different regex strictness.
Reconciled last session, and this session the duplicate classifier was
deleted from `sbcsae_followup_analysis.py` — `sbcsae_tokenizer_validate.py`
is now the single source, and its persisted CSV carries the 8-category
breakdown (§4 of the previous revision has the full arithmetic
reconciliation; not repeated here since the duplicate no longer exists to
disagree).

---

## 5. Status: what is final, what is provisional

**Final:**
- The reader (`reports/phase2_data.md`, plus this stage's speaker-colon and
  DEL-byte fixes: 84 and 40 IUs changed respectively, `reports/phase2_speaker_colon_fix.csv`
  and `reports/phase2_nul_bytes.csv`, 70,007 total unaffected in every term
  of its derivation).
- All five decisions in §2, each covered by a hand-written test and a
  whole-corpus count, confirmed against the current corpus.
- The corpus-wide raise count (**340 of 69,029, 0.49%** — down from last
  session's 1,551/2.25%, entirely because of §2b-2d) and the zero-word/
  reference-segment counts in §2e (`reports/phase2_tokenizer_summary.csv`,
  `reports/phase2_tokenizer_raises.csv`, `reports/phase2_tokenizer_zero_word_composition.csv`,
  `reports/phase2_reference_segments_by_file.csv`).
- Every finding in §3, all independently verified against the raw corpus
  this session (not carried over from memory of the prior one).

**Provisional, and why:**
- `reports/phase2_marker_inventory.csv`'s `DOUBLE_ANGLE_CLOSE` row (83) —
  known undercount by 10, root cause in §3b, not yet corrected in the CSV
  itself (fixing the scanning script was not authorised this session).
- The distinct-tag-NAME lists (as opposed to open/close occurrence counts)
  in the same table — undercount real multi-word tag names for the reason
  in §3b/§4.
- `~ # * +` and `<<TAG...TAG>>` beyond the specific letter-prefix and
  span-tag cases authorised this session: still raise, still undecided.
- `+`'s status specifically is now less settled than it looked last
  session, not more: it is evidently not confined to `<<...>>` spans, and
  plausibly functions as an accent/stress marker CLAUDE.md's `^`/backtick
  slots were meant for. No tier is assigned.
- The `_`/`/` finding in §3e (mispronunciation-correction marker,
  word-internal restart) and the fusion side-effect in §3f: both reported,
  neither decided.

---

## 6. Open items, in order

1. **[Decision]** What `+` marks — evidence now points at an accent/stress
   function rather than a construct confined to `<<...>>` spans (§3c).
2. **[Decision]** Whether `<<TAG ... TAG>>` gets the same treatment as the
   now-handled single-angle/`<%...%>` case, given the tag-name mismatches in
   §3b are confirmed extraction artifacts, not evidence the construct itself
   is irregular.
3. **[Decision]** What the `_`/`/` mispronunciation-correction pattern in
   §3e should do to word identity — currently it fuses like an ordinary
   embedded mark (§3f), which may not be the right outcome once its function
   is recognised as distinct from terminal pitch.
4. **[Decision]** What happens, for scoring, to the 340 IUs (0.49%) that
   still raise — excluded, or something else. (Zero-word IUs are now
   resolved: §2e drops them from the reference.)
5. Not a decision — fix `sbcsae_marker_inventory.py`'s `DOUBLE_ANGLE_OPEN`/
   `DOUBLE_ANGLE_CLOSE` and tag-name extraction to use independent,
   non-mutually-exclusive searches (matching how `sbcsae_followup_analysis.py`
   already does it) and include `_`/`-` in the tag-name character class, so
   `reports/phase2_marker_inventory.csv` stops being provisional.
6. Not a decision — the reader's tab-branch permissiveness occasionally
   attributes real dialogue to a bogus "speaker" (4 cases, §3d). Out of
   scope this session ("do not change the reader"); see the note below on
   whether the two branches can be unified.
7. **Blocked on 1-4.** Build the segmentation prompt and run the model,
   `n_samples=5` from the start, per the standing sampling policy.

**On unifying the reader's two parsing branches (asked, not implemented):**
No — they solve different problems and unifying them would break real data
either direction. The tab-present branch answers "given a tab, is the field
before it a speaker" and answers *permissively* (whatever precedes the first
tab, colon or not) because a tab is itself a structural signal that a field
boundary was intended — this is required for real colon-less speaker codes
(`MONTOYA`, `>MAC`, `>ENV`, `KEN/KEV`, `SUE?`) but is also exactly why it
occasionally accepts genuine dialogue as a "speaker" when a line has a tab
somewhere but no real speaker field (§3d, 4 cases). The no-tab branch
answers "with no structural signal at all, is there a recognisable speaker
token" and must be *conservative* (require an actual colon-terminated token)
— this is what this session's earlier fix (two sessions ago) established,
and loosening it back to "whatever's there" would reintroduce the leaked-
`SPEAKER:` bug this stage exists to have fixed. Making the no-tab branch as
permissive as the tab branch reintroduces a known bug; making the tab
branch as conservative as the no-tab branch breaks every colon-less speaker
code in the corpus. **Recommendation: CLAUDE.md should describe the
two-branch structure explicitly** (why they differ, not just that they
differ) rather than record an aspiration to unify them — the asymmetry is
load-bearing, not accidental. Not changed in CLAUDE.md this session, since
only the §2a tier change was authorised there.

---

## 7. Follow-up verification session

Every decision in §2, every check in §3, and the classifier merge in §4
were re-verified from a clean context against the current code and corpus
rather than taken on trust from this report's own prose — consistent with
the standing rule that a number not re-derived is provisional. Result: all
of it reproduced exactly. `pytest tests/test_sbcsae_tokenizer.py` — 54/54
pass; full suite 577 passed, 11 skipped. A fresh `sbcsae_tokenizer_validate.py`
run over the corpus reproduced §5's figures exactly: 340/69,029 raises
(0.49%), 5,297 zero-word IUs, 68,689→63,392 reference segments. No
regression, nothing to redo.

One real gap found while chasing the §4 "stale pointer" instruction:
`reports/phase2_data.md`'s NUL-byte section (§3 there) still said "six,"
stripped, from before the stage-4 reader fix (`a37c3ad`) that found DEL
(`0x7F`) stripped by the identical rule — 40 more bytes, 46 total (6 NUL +
40 DEL), matching the "40 IUs changed" already on record here in §5. The
section had simply never been revisited after that fix. Corrected in
`reports/phase2_data.md` and in CLAUDE.md's mirrored bullet, and the
pointer there now names the gitignored `reports/private/phase2_nul_bytes_full.csv`
for context, not the public locations-only CSV.

---

## 8. Decisions from the §3a-3f findings, and their implementation

Code changed this session (`sbcsae_tokenizer.py`, `sbcsae_tokenizer_validate.py`,
`tests/test_sbcsae_tokenizer.py`) — first time in this stage the tokeniser
itself, not just its reports, was modified. Every rule below has a
hand-written test and a whole-corpus count. 79 tokenizer tests pass (up
from 54); full suite 602 passed, 11 skipped (up from 577).

### 8.0 Before implementing

**a) Orphaned `-` (58 IUs, 28 files) — no rule.** Heterogeneous: mostly a
hyphenated compound split by an overlap bracket or other delimiter
(`third]-graders`, `eighty]-seven`, `half]-way`); some genuinely isolated
dashes (false starts, trailing "`-`" with nothing glued to its left); a few
combined with a pause (`eighty .. -three`). Not one phenomenon, so not
touched.

**b) Remaining `#`/`*` raises.** `#`: 1 IU (`SBC019`, `[#5Jason #Dill5]` —
`#` followed by a digit, not a letter). `*`: 2 IUs (`SBC001`, `X[3X3]*`,
trailing with nothing after; `SBC019`, `*#Vodnoy`, a second, stacked
disguise prefix). Both already documented as raise-cases; still raise.

**c) `.`, `..`, `...` verified independently.** `(H)`, `(Hx)`, `--`, `?`,
`..` matched an independent regex count exactly. `...`/`.` differed by 2
each from a naive dot-run simulation — traced to the exact 2 IUs
(`((J,_M,_P_LAUGHING_7.8_SEC))`, `((H,_J,_P_LAUGHING_8.0_SEC))`): a decimal
point inside a researcher-comment timestamp, correctly absorbed into the
dropped `((...))` span rather than double-counted as `PERIOD`. Not a bug —
the DOUBLE_ANGLE undercount mechanism (shared, competing greedy letter
runs) has no analogue here (fixed-length patterns, nothing to compete
over).

### 8.1 Implemented

**a) Lost-initial-letter corruption — one rule, `lost_initial_letter`.**
Unifies the bare-`0`-before-a-lowercase-letter case with the
`0.000000e+00`/`E+00` artifact, **and a third shape found this session**:
the same artifact missing its exponent tail (`0.000000or`, `0.000000irst`
— `SBC024`, `SBC028`). `0(?:\.000000(?:[eE]\+00)?)?(?=[a-z])`. Files: bare
zero in 15 files (62 occurrences); no-exponent in 2 (`SBC024`, `SBC028`,
2); full exponent in 5 (`SBC015`, `SBC017`, `SBC020`, `SBC025`, `SBC026`,
5) — the exponent-form file list is unchanged from §2d's prior count.

**b) `<<TAG` / `TAG>>` delimiters.** Three rules: `double_angle_wrap`
(`<<[A-Za-z][A-Za-z_\-]*>>`, tried first) for the zero-content case
(`<<THUMP>>`) that would otherwise reproduce the §3b undercount mechanism
inside the tokeniser itself; `double_angle_open`/`double_angle_close` for
the general case. `_`/`-` included in the tag-name class throughout, so
multi-word names don't get half-eaten. No pairing: open/close never
checked against each other, within or across IUs (verified with a
mismatched-name case, `VOMIT-SOUND`/`VOMIT-NOISE`, and an open-with-no-
close-in-IU case).

**c) `+`.** New `drop` rule, `plus_event_timing`. Fuses mid-word like any
other tier-1 mark via the existing fusion logic, no special case needed.

**d) `_`/`/` reclassified out of tier 2.** `word_gloss_suffix`
(`_\(?/[^/]*/\)?`) drops a phonetic-gloss suffix whole, keeping the word
before it (`good_/god/` → `good`, dropping `_/god/` entirely — verified
before/after: before this session `good`, `/`, `god`, `/` all separately
tokenised as tier-2 pitch cues with nothing dropped; after, one `Word`
"good", nothing else). `bare_phonetic_gloss` (`/[^/]*/`) drops the 2
IUs (`SBC006`, `SBC016`) where the same convention appears without a
leading word+`_`. The `word` pattern's internal-joiner class gained `_`
alongside `'`/`-`, so a word-internal underscore is a direct regex match,
kept literally (`nineteen_ninety_three` stays as one token with its
underscores, not smashed together) — this also resolves the previously-
reported `SBC058` singing-span fusion side-effect (§3f), since those
underscore-joined runs now match in one shot instead of going through the
fusion mechanism at all.

Full breakdown of all 609 `_` and all 10 `/` (whole-corpus, this session):
`/` is 100% accounted for (6 in a word-gloss suffix, 4 in a bare gloss) —
**zero left that could be terminal pitch.** `_`: 160 word-internal
(letters both sides), 3 in a gloss suffix, and **~230+ in a newly-found
third pattern this rule does not authorise** — a self-interruption/
abandoned-utterance marker (trailing `word_`, or a standalone `__`),
concentrated almost entirely in `SBC012`/`SBC013`. **Zero of the 609 are
terminal pitch either** — that finding fully justifies removing `_` from
tier 2, but the self-interruption pattern is a real, sizeable, undecided
phenomenon, not folded into this rule, and now the dominant raise category
(§8.4).

**e) Five fixes, one census.** `(h)`/`(hx)`/`(HX)` case-folded onto the
existing breath cues (both letters, not just the first). `empty_parens`
drops bare `()`. `yawn_named_exception` drops the one-off `(YAWN0` (a
vocal-noise closing `)` mistyped as `0` — the same lost-character
phenomenon as (a), landing on a delimiter). `stray_close_paren_named_
exception` drops the one stray `)` in `SBC024`'s `[Look okay)]`, anchored
tightly to that exact context (verified it does **not** fire on an
unrelated `)]`, e.g. `[Look fine)]`, so it isn't a general orphan-`)`
rule). **Digit census, corpus-wide, outside timestamps and every already-
matched context** (overlap brackets, angle-tag names, the float artifact,
research comments): 86 residual digits, **zero real numerals** — SBCSAE
spells numbers as words throughout, confirmed independently of the
earlier per-character raise counts. All 86 are numbered-overlap-bracket
leftovers with a missing or misplaced bracket character (`[2I mean2,`
missing its `]`; `2[cause I2]` with the leading `2` outside the bracket
instead of inside). New low-priority catch-all rule, `overlap_leftover_
digit` (`\d+`), reached only after every specific higher-priority rule has
had first claim, so it never touches a digit that belongs to a named
construct.

### 8.2 Speakers

**a) Every `>`-prefixed source, IU and (tokenised, not raw-regex) word
count per file** — totals: `>ENV` 174 IUs/396 raw-alpha, but **only 9 real
tokenised words**, all in `SBC008`/`SBC013`; `>MAC` 20 IUs/5 words
(`SBC024`); `>RADIO` 1 IU/2 words (`SBC053`); `>DOG`, `>CAT`, `>BABY`,
`>HORSE` all 0 tokenised words. **This corrects a raw-regex-based count
from earlier in this stage that showed far more "words"** — that count was
counting letters inside `((RESEARCH_COMMENT))` annotations as words; the
real, tokenised count is near-zero almost everywhere, confirming "genuine
non-human pseudo-speaker source" for the bulk of these rows. **The
exception is real and not yet explained**: `SBC008`/`SBC013`'s `>ENV` IUs
include actual sentences (`"... to= expose himself to a person,"`,
`"It's like sparkling= grape juice .. cocktail,"`) — not environmental
sound descriptions. Reported, not touched (§2c: labels not normalised
this session).

**b) 356 vs 350 (file, speaker) pairs, reconciled in one line:** 356
includes `SBC037`'s own 6 speakers; 350 excludes them, per the standing
SBC037-out-of-scope rule applied everywhere else in this stage. 350 + 6 =
356 exactly — not a counting error, a scope difference.

**c) Labels not normalised.** No change to speaker tokens this session.

### 8.3 Fragment-fusion reconciliation

**167 three-fragment / 3 four-fragment fusions now, not 183/5 (last
session's count) — and not 173, which does not appear anywhere in this
repository or in either session's recorded output; if that number has a
source, it isn't one I can find, and I'm not going to fabricate a
reconciliation for it.** What actually changed the 183/5 baseline: §8.1d's
underscore-in-word-pattern change turns underscore-joined compounds
(`nineteen_ninety_three`, and the `SBC058` singing-span runs) into single
regex matches (`n_fragments=1`), removing them from the multi-fragment
buckets entirely — this alone accounts for the four-fragment drop from 5
to 3 (both `SBC058` cases). §8.1c's new `+`-fusion rule pulls in the
opposite direction (some previously-raising `+`-interrupted words now
complete successfully as multi-fragment words), so the net 183→167 change
is not attributable to one rule in isolation; both were verified in
combination via a full corpus rerun, not derived arithmetically.

### 8.4 Raising IUs: logged, not skipped

Every raise is now individually logged — file, best-effort line number,
character, a descriptive reason, and (private only) the raw text — via
`sbcsae_tokenizer_validate.py`, to `reports/private/phase2_tokenizer_
raises_full.csv` (gitignored, has transcript text) and `reports/
phase2_tokenizer_raises.csv` (committed: counts and reasons, no text).
**311 of 69,029 (0.45%), down from 340/0.49% — not zero.** By character:
`_` 210 (18 files — the §8.1d self-interruption marker, found, not
authorised), `-` 66 (31 files — §8.0a's orphaned hyphens), `(` 26 (10
files — a lowercase vocal-noise name or a mark glued inside plain parens
with no brackets, e.g. `(H=)`, neither covered by §8.1e), `>` 5 + `<` 1 (6
files — the same zero-content open/close adjacency mechanism fixed for
`<<...>>` in §8.1b, not yet fixed for single-angle tags, plus a close
missing its repeated tag name before `>`), `*` 2, `#` 1 (§8.0b, unchanged).
**"Zero raises" was not reached.** Every one of these is a real, named,
described gap, not a silent drop — none is guessed at or fixed without
authorisation.

Rerun, whole-corpus, this session: reference segments 68,718 → 63,354 (was
68,689 → 63,392). The net +29 tokenised is not simply 29 IUs added to the
same set — verified directly against the pre-session tokeniser: **239 IUs
that used to raise now tokenise, and 210 that used to tokenise now raise**
(239 − 210 = 29 exactly), the latter almost entirely the §8.1d
self-interruption-marker IUs that a blanket tier-2 `_` cue used to swallow
without complaint. Zero IUs that tokenised under both versions changed
word count (checked directly, not assumed) — the zero-word total moved
because the swapped-in and swapped-out sets have different zero-word
compositions (many of the 239 newly-fixed are markers-only, e.g.
`<<THUMP>>` alone; most of the 210 newly-raising carry real words around
the `_`, e.g. "`%_you know,`"), not because any individual IU's word count
changed.

### 8.5 CLAUDE.md and this report

CLAUDE.md's Tokenisation section: `<<TAG...TAG>>` and `+` moved into tier
1; terminal pitch narrowed to backslash only (`/`/`_` removed, with the
word-internal-underscore and phonetic-gloss treatment described in their
place); the lost-initial-letter rule added next to NUL/DEL in "Reading the
corpus," parallel-structured with it since it's the same principle one
processing stage later. This report updated (this section). Committed and
pushed together.

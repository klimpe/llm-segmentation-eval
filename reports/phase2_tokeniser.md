# Phase 2, stage 4 — Tokeniser: marker inventory, implementation, reader fixes, and decisions

Working report. Not for circulation.

**Correction, this session:** this report's own opening line used to claim
it was "formerly `reports/phase2.md`, renamed to distinguish it from the
reader report" — checked against full git history (`git log --all`, not
shallow, first commit `1fffcc6`) while chasing an unrelated "173
three-fragment, §3.3" figure the user attributed to that file: **no file
named `reports/phase2.md` has ever existed in this repository.** The claim
was carried forward across at least two revisions of this report without
anyone checking it. Removed here rather than repeated a third time; see §9
for the full "173" investigation.

This revision supersedes the previous one throughout: several figures
below changed materially in this session, and where they did the old
number is named and corrected rather than silently dropped.

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

Rerun, whole-corpus, this session: zero-word IUs went 5,297 → 5,364 (+67);
final (reference) segments **fell** by 38, 63,392 → 63,354 (before-dropping
totals rose too, 68,689 → 68,718, +29). Both directions in one number each,
not "a 38-segment increase" — that phrasing in an earlier revision of this
section was simply wrong and is corrected here.

The net +29 tokenised is not simply 29 IUs added to the same set — verified
directly against the pre-session tokeniser: **239 IUs that used to raise
now tokenise, and 210 that used to tokenise now raise** (239 − 210 = 29
exactly), the latter almost entirely the §8.1d self-interruption-marker IUs
that a blanket tier-2 `_` cue used to swallow without complaint. Zero IUs
that tokenised under both versions changed word count (checked directly,
not assumed) — the zero-word total moved because the swapped-in and
swapped-out sets have different zero-word compositions (many of the 239
newly-fixed are markers-only, e.g. `<<THUMP>>` alone; most of the 210
newly-raising carry real words around the `_`, e.g. "`%_you know,`"), not
because any individual IU's word count changed.

### 8.5 CLAUDE.md and this report

CLAUDE.md's Tokenisation section: `<<TAG...TAG>>` and `+` moved into tier
1; terminal pitch narrowed to backslash only (`/`/`_` removed, with the
word-internal-underscore and phonetic-gloss treatment described in their
place); the lost-initial-letter rule added next to NUL/DEL in "Reading the
corpus," parallel-structured with it since it's the same principle one
processing stage later. This report updated (this section). Committed and
pushed together.

---

## 9. Closing the tokeniser: the SBC012/SBC013 truncation variant,
## remaining raises, the `>`-prefixed exclusion, and terminal pitch

### 9.1 §8.4 wording fix

Corrected in §8.4 directly: it said "38-segment increase in dropped
zero-word IUs" for a quantity that actually *fell* by 38 (63,392 →
63,354); zero-word IUs themselves rose by 67 (5,297 → 5,364). Both
directions now stated explicitly, with the already-verified 239-fixed/
210-newly-broken breakdown next to them.

### 9.2 `_` in SBC012/SBC013: file-local truncation variant, confirmed

Hypothesis (word_ ≈ word-, __ ≈ --) checked before implementing, per the
brief:

- **All 609 `_`, exact breakdown**: 314 (157 instances) in a standalone
  `__` run, 160 word-internal, 101 trailing `word_`, 23 `mark_word`
  (leading, e.g. `%_you` — not covered by the hypothesis), 4 in a
  4-underscore run, 4 other isolated, 3 gloss-suffix. Sums to 609.
- **Position of `__` (2+)**: 156 after-last-word, 2 no-words, **zero**
  before-first-word or between-words — the identical 100%-IU-final
  signature `--` has (IU_TRUNCATION: 0/0/4654/28 in the marker
  inventory).
- **Per-file rate, `-`/`--` vs. corpus median**: median 65.6/64.7 per
  1000 IUs; SBC012 20.1/24.9 (rank 2/8 of 59, lowest end); SBC013
  25.3/19.1 (rank 3/5). Both files unusually low on the ordinary marks —
  consistent with a local substitute, not coincidence.
- **15 raw examples** (terminal only): confirmed the pattern cleanly
  once compound-word false positives (`Chicano_Latino`, `AFL_CIO` —
  ordinary word-internal joins, already handled) were filtered out.

**Confirmed. Implemented**: `_{2,}` → `Boundary` (same treatment as
`--`, kind `underscore_iu_truncation`). A single `_` glued right after a
word, not part of a run and not a gloss suffix, normalises to a literal
`-` in the word text (new `underscore_trunc` rule kind,
`_handle_underscore_trunc`-equivalent dispatch in `tokenize()`) — `"n_"` →
`"n-"`. Requires an open word to attach to; `%_you`-shaped cases (mark,
not word, before the `_`) are not this pattern and still raise. Tests:
`test_underscore_iu_truncation_run(_no_words)`,
`test_underscore_word_truncation`, `test_underscore_trunc_requires_open_word`.

### 9.3 Remaining raises: 340 → 38 (0.06%)

Implemented, each with a test and a whole-corpus count:

- **(a) Compound split by a dropped delimiter** (`third]-graders`):
  `_handle_displaced_trunc` extended with a third case — previous match
  is any tier-1 `drop` (not lengthening/glottal), a word is open, more
  letters glued on the other side → the delimiter is incidental, word
  stays open. **Also covers the word-final sub-case found while
  implementing** (`[Degener]- --`, nothing follows): same mechanism,
  completes the word there instead (`"Degener-"`) — not a separate
  authorisation, the mechanism the task described applies either way.
- **(b) Leading hyphen after whitespace/pause** (`eighty .. -three`):
  fourth case in the same function — not glued before, glued to letters
  after → starts a new word, `"-three"`.
- **(c) Standalone `-`, glued on neither side**: fifth case → `Boundary`
  (`isolated_hyphen`), removed in both conditions, logged not silently
  dropped.
- **(d) Lowercase/mixed-case vocal-noise names**: `vocal_noise_caps`
  widened to `[A-Za-z][A-Za-z0-9_., ]*` (was `[A-Z][A-Z0-9_., ]*`) — one
  case-insensitive rule, not two, which also resolves a mixed-case typo
  (`(COUGh)`) for the same reason. `(H=)`/`(h=)`/`(Hx=)`/`(hx=)` decompose
  into breath + lengthening via a new compound rule,
  `breath_paren_lengthening`, the unbracketed sibling of the existing
  `breath_bracket_lengthening` (`(H[=])`).
- **(e) Single-angle zero-content/malformed-close**: `angle_wrap`
  (`<[A-Za-z0-9@%]+>`), the single-angle sibling of `double_angle_wrap`
  (§8.1b), fixes `<HUMMING>` and nested-adjacent cases (`<F<VOX>...`) by
  the identical mechanism. `angle_close_bare_missing_name`
  (`(?<=\s)>`) drops a bare `>` after whitespace when the transcriber
  didn't repeat the tag name (`<VOX Ugh VOX >.`) — no pairing attempted,
  so the un-glued repeated name itself (`VOX`) still surfaces as an
  ordinary word, same "no pairing" scope as double-angle.
- **(f) Three named exceptions**: `#` before `5Jason` (a stray digit
  where the numbered-overlap marker should have been); the leading `*`
  in `*#Vodnoy` (a second, stacked disguise prefix — `#Vodnoy` was
  already the authorised case on its own); the trailing `*` in
  `X[3X3]*` (nothing after it to disguise the start of).

**What still raises: 38 of 69,029 (0.06%)**, all newly-scoped-out territory,
none silently guessed at:

- `_` (20, 13 files): the `mark_word` shape (`%_you know`, `(Hx)_every
  day`) — not covered by the confirmed word_/__ hypothesis, which is
  about a word or run, not a mark, before the `_`.
- `-` (9, 8 files): a hyphen sandwiched between two delimiters with a
  bracket on *both* sides (`third]-[2graders...`, `Thirty2]-[3five`) —
  the (a) fix requires the letters-after side to be an ordinary frag
  match, and a bracket there isn't one; a literal `---` (three hyphens:
  `--` consumes two, the third has nothing before or after to attach
  to); `0-` (lost-initial-letter zero immediately before a hyphen, not
  a letter — outside `lost_initial_letter`'s own lookahead, by design,
  6 instances); `0.000000e+00-` (the float artifact immediately before
  a hyphen instead of a letter, 1 instance, same reason).
- `(` (8, 8 files): a vocal-noise name containing an embedded overlap
  bracket (`(THR[OAT)]`, `(AMENS_[CHEERS]_APPLAUSE)=` — the character
  class excludes `[`/`]`, so these don't reach `vocal_noise_caps` at
  all); a non-breath name with an embedded `=` (`(SH=)` — the new
  compound is `[hH][xX]?` specifically, not any name); an `@` inside
  breath parens (`(@Hx)`); multi-level nesting (`(SNIFF .. (Hx)
  (Hx)=)`).
- `<` (1, 1 file): `< HI` — a space *after* `<`, the mirror-image
  malformation of the "close missing its name" case fixed in (e), not
  the same shape.

None of these were silently absorbed into an existing rule to force the
count to zero; each is a genuinely new shape, reported here rather than
guessed at.

### 9.4 `>`-prefixed sources: excluded as non-participants

Implemented in the reader (`sbcsae_reader.py`), not the tokeniser: any
line whose speaker starts with `>` is excluded before the `&` merge state
machine ever sees it, logged the same way as a `$` line — `reason:
"non_participant_speaker"`. **235 lines excluded corpus-wide.** Per the
task: the 9 words in SBC008/SBC013 that do tokenise were not
investigated further — the source disqualifies the line regardless of
content, and that was already established in §8.2a.

**Derivation from 70,083, new term added**:
```
70,083 − 10 ($) − 3 (backslash) − 1 (ambiguous) − 235 (non-participant)
       − 62 (& absorbed) = 69,772
```
Reader's actual output: **69,772.** Matches. **This changes the
corpus-wide expected-IU-count baseline from 70,007 to 69,772** — not a
correction to the old arithmetic (which was right for what it covered),
a new exclusion category added this session. Updated in CLAUDE.md and
`reports/phase2_data.md` §7.

Content for this category goes to `reports/private/
phase2_excluded_non_participant_speaker_full.csv` (gitignored); the
committed `reports/phase2_excluded_lines.csv` keeps file/line/reason for
every row (exact locations and counts) with content redacted for this
category only — the $-note/backslash/ambiguous rows there are unchanged
(pre-existing content, not part of this session's ask).

**Found while regenerating this: a real bug, not part of the ask,
fixed anyway.** Rerunning `sbcsae_reader.py` to get the new derivation
also regenerates `reports/phase2_nul_bytes.csv` — and it turned out that
file was being written *with* full transcript context every time the
script ran, despite CLAUDE.md and `phase2_data.md` both documenting a
private/public split for exactly that file. The split was real in the
documentation and in a one-off private CSV from an earlier session, but
`sbcsae_reader.py`'s own `__main__` had never actually implemented it —
every rerun silently overwrote the committed file with real transcript
text. Fixed in the same commit as the exclusion work: the committed CSV
now has file/line/byte only; full context moved to `reports/private/
phase2_nul_bytes_full.csv`, written by the same script run.

### 9.5 Validation reruns and the digit catch-all

`sbcsae_tokenizer_validate.py` now prints `overlap_leftover_digit`
firings every run (**20**, current corpus) — a number to watch, not
just a rule to trust, per the task. Whole-corpus rerun after every
change in this session: raises 340 → 38 (0.06%); `_` and `-` are now
the dominant categories by a wide margin, both newly-scoped-out
territory (§9.3), not silent gaps.

### 9.6 "173 three-fragment": not found, and the report's own citation for it doesn't check out

`git log -S "173 three" --all`: **zero hits**, in the full, non-shallow
history of this repository (first commit `1fffcc6`, `git
rev-parse --is-shallow-repository` → `false`). Broader searches (`git
log -S "173" --all`, `git log -S "6,571" --all`) turn up nothing in any
phase-2-related commit either. **No file named `reports/phase2.md` has
ever existed in this repository's tracked history** — checked directly
(`git log --all --name-only` across every commit), not assumed. This
report's own §1 used to open by claiming it was "formerly
`reports/phase2.md`" — that claim does not check out and has been
removed (see §1). One line: **the "173 three-fragment, §3.3" citation
points at a file and section that, as far as this repository's history
shows, never existed — it isn't something I declined to reconcile, it's
something that doesn't appear to be there to reconcile.** The real,
current, twice-independently-verified figure remains **167
three-fragment / 3 four-fragment** (§8.3), now further changed by this
session's rule additions (§9.2's `_` fix removes underscore-joined
words from the fragment count the same way as before; the net effect
was not re-measured this session since no fragment-affecting rule
changed after §8.3's reconciliation — flagged here rather than restated
without rechecking).

**Resolved, next session: the 173 figure came from a local, never-
committed draft — not recoverable, not pursued further.** Consistent
with the above: it was never in this repository's history because it
was never in this repository at all.

### 9.7 CLAUDE.md: terminal pitch and absent Du Bois marks

Terminal pitch removed from tier 2 entirely, not narrowed to backslash —
`\\` itself is confirmed **zero** occurrences corpus-wide (whole-corpus
marker inventory, not inferred from `/`/`_`'s already-established
absence). A new paragraph lists every documented Du Bois mark confirmed
absent from this corpus by the same inventory: accent caret, accent
backtick, booster semicolon, terminal-pitch backslash, latching `(0)`,
and the timed-pause form `...(N)` — each still a live rule (raises
rather than silently accepting one if it ever appears), absent from the
data, not removed from the tiers.

---

## 10. A committed-transcript-text leak, audited and fixed; raises to 5

### 10.1 The leak, and the audit

`reports/phase2_marker_no_tier_examples.csv`, committed and pushed in
`ae9f48e` (public repo), had a populated `text` column — 47 rows of raw
IU content. `sbcsae_marker_inventory.py` wrote the full-text version
straight to the committed path; the last rerun (regenerating the marker
inventory for that session's CLAUDE.md work) overwrote what had
previously been a pointer-only file. The exact same defect as the
NUL-bytes CSV, fixed in the reader two sessions ago — not fixed here,
because this script was never touched by that fix.

**Audit of every script writing under `reports/` or `results/`**
(`sbcsae_reader.py`, `sbcsae_tokenizer_validate.py`,
`sbcsae_marker_inventory.py`, `temp_experiment.py`, `run_eval.py`,
`run_eval_fewshot.py` — every `csv.DictWriter`/`csv.writer` call site in
the codebase, not a sample): only `sbcsae_marker_inventory.py` had the
defect. `sbcsae_reader.py` already carries the private/public split
(fixed previously). The other four write only numeric/metric/id columns
(`doc_id`, `precision`, `f1`, `window_diff`, `reason` as a diagnostic
string, never verbatim corpus or model-output text) — checked field by
field, not assumed clean because they looked similar.

**Fixed**: `sbcsae_marker_inventory.py` now writes `pattern`/`file`/`line`
only to the committed CSV and the full row (with `text`) to
`reports/private/phase2_marker_no_tier_examples_full.csv`, same pattern
as the NUL-bytes fix.

**Guard added**: `tests/test_no_transcript_leaks.py` scans every CSV
actually on disk under `reports/` and `results/` (not `reports/private/`)
for a column named `text`/`context`/`content`/`raw`/`iu_text`
(case-insensitive) and asserts it's empty, with one documented exception
— `phase2_excluded_lines.csv`'s 14 original rows (`$`/backslash/ambiguous),
which have always carried short content by design. Would have failed on
the leaked file before the fix; passes now.

**Remediation**: `ae9f48e` was the tip and had not been built on, so the
fix was folded into it directly (`git commit --amend`) and force-pushed
(`git push --force-with-lease`) rather than added as a new commit on top
— the leak never needs to appear in the public history at all, not just
get corrected in a later commit. New commit: `8d4d09c`.

### 10.2 The 38 remaining raises: mapped to existing rules, to 5

Each with a test and a whole-corpus count, per the brief:

**a) A mark before `_` (`%_you`, 20 IUs).** First checked what `%-you`
already does: `Cue(glottal)`, `Cue(displaced_truncation)`, then `you`
starts fresh as its own word — the hyphen never fuses into the
following word when nothing is open to attach it to. `_` now matches
this exactly: `underscore_trunc`'s dispatch gained a second branch (glued
to something, no word open → standalone `Cue(underscore_truncation)`,
not a raise), and — checked against the actual data, not assumed from
the one `%_you` example — the "mark" before it is not always glottal;
`(TSK)`, `(MURMUR)`, `(Hx)`, `((MATCH_STRIKE))` all occur too, so the new
branch doesn't restrict by what kind of mark precedes, only that
something already-matched does. **0 remaining.**

**b) A hyphen between two brackets** (`third]-[2graders`,
`Thirty2]-[3five`). The existing "delimiter incidental to the word's own
hyphen" mechanism (§9.3a) only looked one match ahead; a bracket on
*both* sides meant the match right after the hyphen was another dropped
delimiter, not the frag itself, so `glued_after` came back false and the
word ended prematurely (`"third-"`, `"graders"` as two words, not
raising but wrong). New helper, `_glued_frag_follows`, walks past any
number of consecutive glued `drop`-kind matches to find the frag on the
other side, not just one. **0 remaining** (was silently producing wrong
word boundaries, not raising — found while implementing this item, not
part of the original 38).

**c) `---`** (`SBC010`, "I want---"). `iu_truncation`'s pattern widened
from `--` to `-{2,}` — one `Boundary` with the full run as `raw`, logged
distinctly from a plain `--`, not silently identical to it. **0
remaining.**

**d) `0-` / `0.000000e+00-`.** `lost_initial_letter`'s lookahead widened
from `[a-z]` to `[a-z-]`. The bare `-` left behind after stripping falls
to `_handle_displaced_trunc`'s existing "no word open" logic, extended
to also treat a `drop`-kind predecessor that produced no pending word
(not just "nothing there at all") as unattached: `isolated` if nothing
follows, `start_new` if a word does. **0 remaining.**

**e) Vocal-noise names with an embedded bracket or non-breath `=`**
(`(THR[OAT)]`, `(AMENS_[CHEERS]_APPLAUSE)=`, `(SH=)`). `vocal_noise_caps`'s
body character class gained `[`, `]`, `=` — not the first-character
class, deliberately: widening that too would let `(@Hx)` be silently
swallowed as generic dropped noise instead of surfacing its own
question (does the `Hx` breath cue underneath the `@` deserve to
survive into condition B?) — left raising on purpose. **3 of 8 in this
category remain** (see below), not the 0 the task's own framing implied
for every case in it.

**f) `<` followed by a space and a tag name** (`< HI any nights HI>`).
New rule, `angle_open_spaced` (`<\s+[A-Za-z0-9@%]+`), the mirror-image of
the already-fixed "close missing its name before `>`" malformation
(§9.3e). **0 remaining.**

**Target zero raises — not reached. 5 of 68,815 remain, listed raw here
per the task's own instruction to stop rather than guess further:**

```
SBC002  (TSK (H)3]
SBC015  [2(H]=2]
SBC019  ... (SNIFF .. (Hx) (Hx)=)
SBC023  [(SNIFF)] [2(SNIFF2]
SBC056  (@Hx)
```

Four of these share one shape not covered by (e)'s literal "embedded
bracket or non-breath `=`": the closing `)` is **entirely missing**
(replaced by nothing, by a nested unclosed `(H)`/`(Hx)`, or by a
bracket-then-digit run with no `)` anywhere in the IU), not merely
accompanied by an extra bracket/`=` alongside an otherwise-present `)`.
Widening `vocal_noise_caps` to accept `]` as an alternative closing
delimiter to `)` would fix these mechanically but conflates two
different transcription conventions (parens and brackets) on no
evidence beyond convenience, so it wasn't done. `(@Hx)` is the
deliberately-scoped-out case from (e) above. All five: reported, not
guessed at.

106 tokenizer tests pass (up from 97); full suite 634 passed, 11
skipped.

---

## 11. The last 5 raises: named exceptions, raises to 0

Per the brief: each of the five remaining IUs checked for word content
*before* any code changed, confirmed on the raw text (not the tokeniser's
own output, which couldn't run on them yet):

| file | line | raw text | contains a word? |
|---|---|---|---|
| SBC002 | 466 | `(TSK (H)3]` | no |
| SBC015 | 1805 | `[2(H]=2]` | no |
| SBC019 | 116 | `... (SNIFF .. (Hx) (Hx)=)` | no |
| SBC023 | 1469 | `[(SNIFF)] [2(SNIFF2]` | no |
| SBC056 | 1169 | `(@Hx)` | no |

All five are markers only — pauses, vocal-noise names, breath cues,
lengthening, overlap-bracket leftovers. None was guessed at from this
table alone; each fix below was implemented against the exact raw text
above and verified to still produce zero words afterward, matching this
table rather than contradicting it.

Each of the five, implemented as a named exception anchored to its own
context (lookbehind/lookahead on the literal surrounding text, the same
style as the existing `yawn_named_exception`/`stray_close_paren_named_
exception` — not a general rule for the shape it happens to share with
others):

- **SBC002** `(TSK (H)3]`: `(TSK` (the orphaned open-paren-plus-name, no
  closing `)` anywhere in the IU) dropped by `sbc002_tsk_named_exception`,
  anchored to being followed by ` (H)3]`. The nested `(H)` and the `3]`
  overlap leftover already tokenised correctly on their own — only the
  orphaned `(TSK` itself needed a rule.
- **SBC015** `[2(H]=2]`: the same breath+lengthening compound as the
  already-handled `(H=)` (`breath_paren_lengthening`), except a numbered
  overlap bracket sits where the compound's own closing `)` should be —
  it never appears anywhere in the IU. New compound rule
  `sbc015_breath_bracket_lengthening_named_exception`, anchored to the
  exact `[2...2]` context via lookbehind/lookahead, decomposes to
  `Cue(breath_in, "(H]")` + `Cue(lengthening, "=")`; `[2`/`2]` tokenise
  normally on either side, unaffected.
- **SBC019** `... (SNIFF .. (Hx) (Hx)=)`: `(SNIFF` dropped
  (`sbc019_sniff_open_named_exception`, anchored to the exact following
  context); the IU's final `)` — otherwise unmatched, since it's actually
  `(SNIFF`'s own missing close, not any other span's — dropped by a
  second, symmetric exception (`sbc019_sniff_close_named_exception`,
  anchored by lookbehind on the preceding literal text). The pause and
  both `(Hx)` breath cues in between already tokenised correctly.
- **SBC023** `[(SNIFF)] [2(SNIFF2]`: the first `[(SNIFF)]` was already
  well-formed and untouched by this change (verified: the new rule's
  lookbehind requires a preceding `[2`, which only the second occurrence
  has). The second, `[2(SNIFF2]`, is the bracket-then-digit-run shape —
  `2]` sits where `SNIFF`'s own `)` should be. New rule
  `sbc023_sniff_bracket_digit_named_exception`, anchored the same way as
  SBC015's.
- **SBC056** `(@Hx)`: laughter `@` had no documented compound for
  co-occurring with a breath cue (unlike `(%Hx)`'s `glottal_breath`). New
  compound `sbc056_laughter_breath_named_exception`, a literal anchor (the
  single corpus occurrence), decomposes to a bare `Cue(breath_out,
  "(Hx)")` — the `@` is dropped outright, not rendered as its own cue
  (unlike `glottal_breath`, where the `%` survives as a cue too) — per
  the brief's own framing, "laughter dropped ... `(Hx)` kept as a cue."

One pre-existing test, `test_at_sign_breath_still_raises`, asserted the
old raising behaviour for `(@Hx)` in general and had to be updated to
`test_at_sign_breath_named_exception` (now asserts the fix) plus a new
`test_at_sign_breath_variant_still_raises` (`(@H)`, a different letter,
confirms the exception is literal, not general). Six new tests total, one
per named exception plus the SBC015 anchoring negative-check
(`test_sbc015_named_exception_does_not_fire_without_bracket_2`) — 113
tokenizer tests pass (up from 106).

**Whole-corpus rerun: 0 of 68,815 raises (0.00%).** Target reached, this
time exactly, not "close to zero" — `reports/phase2_tokenizer_raises.csv`
is now an empty table (header only), kept rather than deleted since the
scripts that populate it stay live for the next corpus-affecting change.

---

## 12. Independent word-count cross-check: one real, unattributed bug found

Zero raises answers "does every symbol fit a documented tier," not "did
the rule that fired produce the right word boundaries" — the earlier
bracket-hyphen bug (§10.2b) produced wrong words with no raise at all,
and nothing above rules out another instance of that class. Per the
brief, a second check, sharing no code with `sbcsae_tokenizer.py`
(`sbcsae_tokenizer_crosscheck.py`, new this session): per IU, strip every
character except letters, apostrophes, hyphens and whitespace, collapse
whitespace, count the resulting runs, and compare that count against the
tokeniser's own word count for the same IU.

**64.56% exact match (44,429 of 68,815); the other 35.44% is a mismatch**,
overwhelmingly not a tokeniser defect but the naive method's own blind
spots — it has no concept of a delimiter, so any letters inside a
parenthetical, tag or bracket construct, or a run consisting only of
hyphens, count as "words" it has no way to know are markers. Distribution
of (tokeniser count − independent count), whole corpus:

| diff | IUs | diff | IUs |
|---|---|---|---|
| −1 | 18,440 | −6 | 10 |
| −2 | 4,672 | −7 | 3 |
| −3 | 951 | −8 | 2 |
| −4 | 241 | −9 | 1 |
| −5 | 65 | −10 | 1 |

Every mismatch is negative or zero (the tokeniser never reports *more*
words than the naive count) — expected, since the naive method only ever
over-counts (keeps more spurious runs), never under-counts relative to a
correctly fusing tokeniser.

By best-effort category (each attributed to a specific, already-documented
tokeniser rule, not decided here — the category assignment is diagnostic
only):

| category | IUs | cause |
|---|---|---|
| `parenthetical_marker` | 11,174 | breath/vocal-noise/research-comment letters inside `(...)`/`((...))`, dropped by the tokeniser, counted as words by the naive method |
| `hyphen_only_run` | 4,743 | `--`/`---`/isolated `-` is a `Boundary`, not a `Word` — the naive method has no such kind, so any hyphen-only run becomes a spurious "word" |
| `cue_fusion` | 3,421 | a tier-2 mark (`=^\`!;%\\`) sandwiched mid-word (`s=o`) fuses in the tokeniser, splits the naive method's letter-run in two |
| `overlap_bracket` | 1,757 | `[...]` content/delimiters |
| `numbered_overlap_bracket` | 1,649 | `[2...2]` content/delimiters |
| `angle_tag` | 1,537 | `<TAG ... TAG>`/`<<TAG ... TAG>>` content/delimiters |
| `underscore_truncation_or_gloss` | 87 | `_` as SBC012/SBC013 truncation, phonetic-gloss suffix, or word-internal joiner |
| `lost_initial_letter` | 9 | the `0`/`0.000000e+00` artifact family |
| `at_sign_fusion` | 4 | `@` (laughter/event marker) mid-word, tier-1 drop, fuses |
| `plus_fusion` | 2 | `+` (event-timing marker) mid-word, tier-1 drop, fuses |
| **`other`** | **3** | **not attributable — see below** |

**The 3 unattributed cases, in full (per the brief, raw text stays
terminal-only — not reproduced in this committed report):**

```
SBC023:1047  Fitz- uh -gerald,        tok=['Fitz-', 'uh-gerald']
SBC032:1371  Might alw- -so,          tok=['Might', 'alw--so']
SBC055:264   And we he rela- -turned, tok=['And', 'we', 'he', 'rela--turned']
```

**Root cause, confirmed, not guessed:** `_handle_displaced_trunc`'s case 4
("a leading hyphen starting a word," `eighty .. -three` → `start_new`) is
written for the situation where nothing is pending — true in that example
because the preceding cue (`..`) already flushed the previous word. It
does not check whether a word is *already* pending before appending the
hyphen; when the immediately preceding token was an ordinary word ended
only by whitespace (no intervening cue/boundary to flush it), that
pending word is still open, and the hyphen — meant to *start a new
word* — is silently appended onto it instead. `uh -gerald` (a complete
word, then a truncated fragment) becomes one wrong word, `uh-gerald`,
with **no raise**: exactly the "silent mis-split" class the brief warned
raise-on-unknown does not cover. Confirmed directly, not inferred from
the category alone: for each candidate IU, the fused `Word.raw` was
checked against the source text and found *not* to occur there as a
substring — proof the tokeniser produced text that doesn't correspond to
any contiguous span of the actual IU.

**Scope, checked against the corpus, not assumed**: a targeted scan for
the structural pattern (`\S\s+-[A-Za-z]`: some non-space character, then
whitespace, then a hyphen directly glued to a letter) found 14 candidate
IUs corpus-wide; of those, exactly these 3 tokenise into a word whose
`raw` doesn't appear verbatim in the source — the other 11 are cases
where the preceding token was already a cue/boundary (nothing pending),
so case 4 behaves as documented.

**Not fixed in this step, per the brief.** `reports/phase2_tokenizer_
crosscheck_summary.csv` (committed: diff/category/count only) and
`reports/private/phase2_tokenizer_crosscheck_full.csv` (gitignored: full
per-IU rows, has transcript text) are the persisted evidence;
`sbcsae_tokenizer_crosscheck.py` reproduces both from a clean run.

---

## 13. Final figures, and stage-4 status

Whole-corpus, current code, SBC037 excluded throughout (59 files):

- **68,815 IUs, 0 raises (0.00%).**
- **5,179 zero-word IUs** dropped from the reference (identically under A
  and B); **63,636 reference segments** remain (`reports/
  phase2_reference_segments_by_file.csv`, full 59-file table).
- 113 tokenizer tests pass (up from 106 at the start of this session);
  full suite **642 passed, 11 skipped** (up from 634).
- `tests/test_no_transcript_leaks.py` strengthened per the brief: a
  blocklist of text-like column names became an allowlist of expected
  columns per committed CSV (`ALLOWED_COLUMNS`, one entry per file under
  `reports/`/`results/`) — any column not on a file's list fails the
  test, whether or not it looks text-like, so a new column requires
  updating that table as an explicit decision. The pre-existing content
  check (populated text-like column, minus the 14-row
  `phase2_excluded_lines.csv` exception) is unchanged and still the thing
  that would catch a leak into a column already on the allowlist.
  Verified both directions: a synthetic extra column fails the new test;
  reverting it passes again.

**Stage 4 is not marked final.** Every raise-based check from earlier
sessions now reads zero, but §12's independent cross-check — a
fundamentally different check, immune to the "no raise" blind spot —
found one real, confirmed, unattributed silent mis-split
(`_handle_displaced_trunc`'s leading-hyphen case, 3 IUs). Per the brief's
own instruction, this is reported as open, not folded into "final" by
proximity to zero. Next open item: decide what to do about it (the fix is
straightforward — flush a pending word before case 4's `start_new`
appends the hyphen — but per this step's brief, deciding and implementing
that fix was explicitly out of scope here).

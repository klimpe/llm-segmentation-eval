# Project context

## Who I am

I'm a computational linguist. My doctoral work at the Laboratoire Parole et
Langage (Aix-Marseille University, 2012–2018) was on discourse unit
segmentation in spontaneous spoken French, and I published on segmentation
evaluation metrics:

  Peshkov, K. & Prévot, L. (2014). Segmentation evaluation metrics, a
  comparison grounded on prosodic and discourse units. LREC'14, Reykjavik,
  pp. 321–325.
  http://www.lrec-conf.org/proceedings/lrec2014/pdf/931_Paper.pdf

My old research code is published at https://github.com/klimpe/speech-units
(Python 2, unmaintained, reference only — see "Do not port" below).

I know these metrics well. Do not explain WindowDiff, Boundary Similarity,
kappa, or inter-annotator agreement to me. Do tell me when an implementation
detail is wrong.

## What I'm building

A pipeline that has an LLM segment transcripts, measures the gap against human
annotation with standard segmentation metrics, and — this is the point of the
project — relates that score to inter-annotator agreement. Most evaluations of
this kind publish a score with no human ceiling, which makes the number
uninterpretable: you cannot tell whether the model is far from human
performance or already at the ceiling.

Three phases, in order:

1. **DISRPT** — open, unified format across many corpora, published system
   scores from the 2019/2021/2023/2025 shared tasks. Text only, no audio. For
   building and validating the pipeline and getting a baseline against trained
   systems. **Completed** — see `reports/phase1.md`.

2. **Santa Barbara Corpus (SBCSAE)** — free, ~249k words of spontaneous
   conversational American English across 60 files, transcribed at the level of
   intonation units and time-aligned at IU level. **Current phase.**

   The corpus contains **no discourse segmentation** — intonation units are the
   only human segmentation available. Phase 2 therefore measures something
   different from phase 1, and the difference is substantive rather than
   presentational: it asks **how far prosodic structure is recoverable from
   text alone**. A human transcriber heard where an intonation contour ended;
   the model sees only words. Agreement means prosodic phrasing is largely
   predictable from lexis and syntax; disagreement means the signal carried
   information the transcript does not. Every table and claim involving phase 2
   figures must state that the target is prosodic, not discourse, units — not
   once in a methods section, but wherever the numbers appear.

3. **CID (Corpus of Interactional Data)** — spontaneous French conversation,
   access pending from the LPL. Adds French, audio, discourse-unit annotation,
   and inter-annotator agreement measures I computed myself during the
   doctorate. It is the only phase where both unit types and a human ceiling
   are available on the same data. Data will NOT be published; only code and
   aggregate results.

The hypothesis to test: the model fails specifically where prosodic
information is decisive and absent from the transcript.

## Core data contract

Everything in the pipeline speaks one intermediate representation: **segment
masses**, a list of segment lengths in atomic units.

```python
# 10 tokens, boundaries after token 3 and token 7
masses = [3, 4, 3]
assert sum(masses) == n_tokens
```

Two functions define the contract:

```python
def flags_to_masses(flags: list[bool]) -> list[int]:
    """flags[i] is True if a new segment begins at token i."""

def masses_to_boundaries(masses: list[int]) -> set[int]:
    """Positions after which a boundary falls. len == len(masses) - 1."""
```

Every reader (DISRPT, SBCSAE, CID, LLM output) produces masses. Everything
downstream consumes masses only.

### Atomic units are not assumed

The atomic unit is whatever the corpus's own annotation is defined over, and is
fixed when its reader is written — not decided in advance. Phase 1 used the
token, because DISRPT annotates per token. Phase 2 may not: if SBCSAE's only
human segmentation is at the level of intonation units, then that is the unit,
and what is being measured is prosodic rather than discourse segmentation. That
is a substantive difference, not a formatting one, and must be established
before the reader is written.

Scores computed over different atomic units are **not comparable**: WindowDiff's
window size derives from mean segment length in atomic units. Any table placing
figures from different phases side by side must state this.

## Phase 2 specifics (SBCSAE)

### Source and licence

Read `.trn`, not `.cha`: one line per intonation unit, tab-separated timestamp,
speaker, text. Same information as CHAT with none of the convention layer.
Download from UCSB directly (`SBCorpus.zip`, static files, no account) rather
than TalkBank, which requires a login.

Licence is CC Attribution-NoDerivatives 3.0 US — stricter than phase 1. Beyond
the standing no-corpus-data-in-git rule, published output must not contain a
re-tokenised or otherwise modified version of the transcript text. Scores,
tables and short illustrative quotations are fine; a processed transcript file
is not. Required citation: Du Bois, John W. (2000, 2003, 2005, 2005). Santa
Barbara Corpus of Spoken American English, Parts 1–4. Philadelphia: Linguistic
Data Consortium.

### Reading the corpus — settled, see reports/phase2_data.md

These were established by full-corpus inspection, not by sampling. Do not
revisit them without new evidence.

**Encodings.** Per-file, explicit, `errors="strict"`. `SBC060` is cp1252 (147
curly apostrophes inside contractions); `SBC037` is latin-1 (34 Spanish
accented vowels); everything else UTF-8. `newline=None` handles SBC037's CRLF.
A decode failure must raise, never substitute — `errors="replace"` turns a
problem into plausible data, which is the failure mode this project exists to
avoid.

**NUL and DEL bytes.** 46 total (6 NUL, 40 DEL — DEL found and fixed during
the stage-4 tokeniser pass, `reports/phase2_tokeniser.md`; both stripped by
the same rule, for the same reason). Strip the byte; do not reconstruct the
missing letter. Locations logged in `reports/phase2_nul_bytes.csv`; raw
context is in the gitignored `reports/private/phase2_nul_bytes_full.csv`,
not committed (licence forbids publishing transcript text).

**Lost-initial-letter corruption, in the tokeniser, not the reader.** Same
principle as NUL/DEL — strip the corruption marker, keep whatever letters
survive, never reconstruct — but this one lands past decoding, in the
already-decoded text `sbcsae_tokenizer.py` sees, not in the raw bytes: a
bare `0` glued before a lowercase letter (`0h,` for "uh,"/"oh,"), or the
`0.000000e+00`/`0.000000E+00` spreadsheet-mantissa artifact glued before a
word, with or without the exponent tail (`0.000000e+00verything`,
`0.000000or`). One rule (`lost_initial_letter` in the tokeniser's rule
table), one family, three surface shapes.

**Curly apostrophes** normalise to ASCII `'`, or `didn't` from SBC060 becomes a
different token from `didn't` everywhere else. Spanish accented characters are
left alone — they are part of words.

**Line parsing.** Field counts are not uniform (1 to 5 observed). Parse every
line with one regex — two decimal numbers, whitespace of any kind, optional
speaker, then text — not a main path plus a rescue path for odd files. The
rescue path is always the less tested one. Take the last non-blank field as
text; raise if another non-blank field remains to its left.

Within that one regex, the remainder after the two timestamps still splits
two ways depending on whether a tab survives in it, and the two ways are
deliberately asymmetric, not an inconsistency to fix. Tab present: answers
"is whatever precedes the first tab a speaker" *permissively* — required
for real colon-less speaker codes (`MONTOYA`, `>MAC`, `>ENV`, `KEN/KEV`,
`SUE?`), which have no other structural signal to be recognised by. No tab
present: answers *conservatively*, requiring an actual colon-terminated
token — loosening this back to "whatever's there" reintroduces the
leaked-`SPEAKER:` bug a prior stage-4 fix exists to have closed. Making
either branch match the other breaks the case the other one exists for.

**The `&` merge.** Du Bois §13.1 defines `&` as marking one IU split across
lines when another speaker interrupts. 61 chains in the corpus: 60 same-speaker,
merged by speaker identity (never by file position — two speakers can have
threads open simultaneously). One cross-speaker chain, SBC011 lines 414–415, is
collaborative completion: two speakers, two contours, therefore two IUs. It is
coded as a named exception and is not merged. A leading `&` with no open
fragment for that speaker raises unless it is that known case.

**Exclusions: 14 lines of 70,083, plus 235 non-participant-speaker lines
added in the stage-4 tokeniser follow-up.** Ten `$` non-transcription lines
(Du Bois §14.1), three backslash-fused lines, one ambiguous-field line, each
logged with full content and reason. `SBC037` is additionally excluded as
bilingual: code-switched Spanish is not the same task as monolingual
English, and one file cannot support a separate finding. **A `>`-prefixed
speaker (`>ENV`, `>DOG`, `>MAC`, `>CAT`, `>BABY`, `>HORSE`, `>RADIO`) is not
a participant** — Du Bois's convention for an environmental/animal/machine
sound source — and every such IU is excluded, the same way as a `$` line,
regardless of whether it happens to tokenise to real words (confirmed,
checked directly: 9 words total, `SBC008`/`SBC013`, excluded anyway since
the source disqualifies it, not the content). Content logged to the
gitignored `reports/private/`; locations and counts in the committed
`reports/phase2_excluded_lines.csv`.

**Expected IU count: 69,772**, not 70,007 — the `>`-prefixed exclusion is
new this session and changes the corpus-wide baseline. Derivation: 70,083
raw − 10 `$` − 3 fused − 1 ambiguous − 235 non-participant − 62 absorbed by
merge. Verify the reader against the derivation, not the total; a
discrepancy is a finding. (70,007 was correct for its own scope — before
this exclusion existed — not a stale or wrong number superseded by
undercounting, unlike the 70,056/9/69,981 draft this section once carried;
see `reports/phase2_data.md` §7 for that separate history. The reader's
actual output matches 69,772 exactly.)

### Tokenisation — decided and implemented (`sbcsae_tokenizer.py`)

The atomic unit is the token after markers are stripped. Four categories, not
three — see the boundary-annotation addition below, decided during the
stage-4 checks in `reports/phase2_tokeniser.md` §2a:

**Removed in both conditions** — not speech, or not a boundary cue:
overlap brackets (`[...]`, `[2...2]`), researcher comments `((...))` including
their content, vocal noises in single parentheses with capitals (`(TSK)`,
`(THROAT)`), standalone laughter `@`, the delimiters of all `<TAG ... TAG>`
quality spans (content kept), `$` lines. Moved here this session (stage-4
follow-up, `reports/phase2_tokeniser.md` §1-§4): `<<TAG ... TAG>>` spans
(same wrapper-over-real-speech treatment as single-angle, never paired,
`_`/`-` included in the tag-name class); `+`, an event-timing marker inside
`<<...>>` spans, not a prosodic cue (was previously undocumented/raising);
a phonetic-gloss suffix on a word (`good_/god/`, `cello_(/cheller/)`) or a
bare slash-delimited phonetic aside (`/pub/`) — the respelling is dropped
whole, the orthographic word before it (if any) is kept.

**Removed in condition A, kept in condition B** — prosodic cues, the things a
transcriber used to place the boundary: pauses (`...`, `..`), inhalation
`(H)` and exhalation `(Hx)` (case-folded on H/X this session — `(h)`,
`(hx)`, `(HX)` all mean the same thing, including case-folded lowercase
vocal-noise names generally, e.g. `(throat)`, and the `(H=)`/`(h=)` breath-
plus-lengthening compound), lengthening `=`, boosters `!`, glottal stop `%`.
**Terminal pitch is gone from this tier entirely, not narrowed** — `\\`,
`/`, and `_` were all removed this session (`\\` last: confirmed **zero**
occurrences anywhere in the corpus, via the whole-corpus marker inventory,
not assumed from `/`/`_`'s own removal). `_` between letters is literally
part of the word (`nineteen_ninety_three`, kept as one token, underscore
included — not dropped-and-fused the way an embedded tier-1/2 mark is);
every other non-word use of `_`/`/` is covered by the phonetic-gloss rule
above, is SBC012/SBC013's own file-local truncation-mark variant (below),
or is a still-undecided mark-before-underscore case (`%_you`, §8 in
`reports/phase2_tokeniser.md`).

**Documented Du Bois marks confirmed absent from this corpus** (whole-
corpus marker inventory, zero occurrences each, not inferred): accent
caret `^`, accent backtick, booster semicolon `;`, terminal-pitch
backslash `\\`, latching `(0)`, and the timed-pause form `...(N)`. Each is
still a real rule in the tokeniser (raise rather than silently accept if
one ever appears) — absent from the data, not removed from the tiers.

**The boundary annotation itself — removed in BOTH conditions, but not
tier 1**: transitional continuity punctuation `.` `,` `?` and IU truncation
`--`. These were found to be IU-final in 99.4-100% of their whole-corpus
occurrences (`reports/phase2_tokeniser.md` §3.2/§2a) — they mark where the
segmentation boundary falls, not a prosodic quality carried by a word, so
unlike the tier-2 cues above they are never rendered even in condition B.
`--` moved here from tier 2 (it was never actually embeddable mid-word, so
this changes its rendering, not its tokenisation behaviour). `.` `,` `?`
were previously undocumented territory ("not in any tier"); they are now a
named category (`Boundary` in the tokeniser), not silent no-ops.

**Kept always** — actually uttered: words, truncated words (`y-`), and the
standalone `X` indecipherable-syllable marker, which is real speech that was not
heard clearly. Removing it would lose material and shift token counts.

Angle brackets are wrappers over real speech: strip the delimiters, keep the
content, never attempt to pair them. Du Bois §9.4 permits crossing nesting
(`<@<HI ... @> HI>`), so pairing would be wrong as well as unnecessary.
`<L2 ... L2>` is the same — code-switch marking over real words. Inline
lengthening normalises (`s=o` → `so`) in condition A.

**Condition B is not "markers retained" in general** — only the prosodic tier
above. Keeping overlap brackets or laughter would add noise, not signal. The
difference between A and B measures what the prosodic cue is worth, and is
likely the most informative result of the phase. Report both; never merge them.

Write the tokeniser with the A/B switch from the start. Validate the rule on
its own — given one IU's raw text, show what comes out — before it is used
anywhere.

**Raises: 311 of 69,029 IUs (0.45%), down from 340 — still not zero, still
not decided.** Every raise is logged (file, line, character, reason) to
`reports/private/phase2_tokenizer_raises_full.csv`; counts and reasons only
(no transcript text) in the committed `reports/phase2_tokenizer_raises.csv`.
Dominant remaining categories, each its own open decision, none authorised:
`_` (210 IUs, mostly SBC012/SBC013) — a self-interruption/abandoned-
utterance marker (trailing `word_`, standalone `__`), a different
phenomenon from anything above, found but not decided; `-` (66) — orphaned
hyphens (a compound split by a bracket, or an isolated dash); `(` (26) — a
lowercase vocal-noise name (`(throat)`) or a mark glued inside plain
parens with no brackets (`(H=)`), neither covered by the case-folding
above; `>`/`<` (6) — single-angle tags hitting the same zero-content
open/close adjacency mechanism fixed for `<<...>>` above, not yet fixed for
single angle.

### No genre breakdown

SBCSAE has no genre or register field, only free-text per-file descriptions. Do
not hand-derive a category scheme from them: a judgment-based grouping invented
for this purpose would not support the per-subset reasoning it is meant to
enable. Break results down by document and by document length instead.

### Where phase 2 stands

Stages 1–3 complete: reading, line structure, `&` merge. Next is the tokeniser,
per the decisions above, then the LLM run with `n_samples=5` from the start.

## Sampling

Sampling parameters are not controllable through this SDK — `temperature` is not
accepted and has no effect. Variance is therefore addressed by repetition, not
by pinning:

- Run `n_samples=5` per document by default. Cache each sample separately.
- Report mean and range across samples. **Never report a single draw as a
  result.** Phase 1 produced several document-level findings that did not
  survive resampling.
- Roughly 5% of responses fail to parse (malformed JSON, a missing comma).
  Retry on failure, and report the failure rate rather than letting failed
  draws disappear from the denominator.

## Degenerate output

Check every parsed output for runs of consecutive predicted boundaries. The
model intermittently stops segmenting partway through a long document and
enumerates every remaining index, marking punctuation as unit starts. This:

- produces a plausible-looking score rather than an error;
- occurs in some draws and not others (2 of 5 on the one document where it was
  studied), so its absence in one run is not evidence of absence;
- is invisible to aggregate metrics and was found only by reading raw output.

Flag it automatically. Report affected draws separately rather than folding
them into the aggregate.

## Working method

Build and verify each step in isolation before starting the next. Stop after
each and show me the result. The phase 1 order was: representation → one
reader, one file → metrics validated on synthetic perturbations → LLM on one
document → scale. Later phases reuse the representation and metrics unchanged;
what is rebuilt is the reader and, where the reference unit differs, the
prompt.

Validate anything new against an external reference where one exists. In phase
1 this caught two real bugs in the metric implementations that would otherwise
have produced plausible wrong numbers throughout.

**Any check not run over the whole corpus is provisional, and should be
reported as such.** Three checks in phase 2 stage 1 were first run on a subset
and each correction was material: `grep` silently skipped three files it flagged
as binary (4 NUL bytes became 6); the format survey used one file, which turned
out not to have the corpus's majority field layout; and the `&` pairing rule was
generalised from a single example that a later case contradicted. None of these
produced an error. All produced a number.

## Constraints

**Python 3.** Do not port the old Python 2 code from speech-units. Reimplement
cleanly. The old repository is a reading reference for the approach, nothing
more.

**Alignment is mandatory.** The model must return boundaries as indices into
the given sequence, never as rewritten text with inserted markers. After
parsing any model output, assert `sum(hyp_masses) == sum(ref_masses)`. On
mismatch, set the document aside and report it — never compute a metric on
misaligned data. Track how many documents fail this check; it is a result in
itself.

**Persist raw model output to disk** before parsing, one file per sample. These
are needed to diagnose surprising numbers later, and to detect degenerate
output after the fact.

**Cache API calls.** Do not re-query for a document and sample index already
processed unless explicitly asked. A cached response must parse and align
before being treated as reusable.

**No corpus data in git.** Corpora go in a gitignored directory. CID data in
particular has its own distribution terms and must never be committed.

**Check the data before trusting a score.** Two phase 1 documents scored near
zero because their text had been replaced by underscores in the public
distribution — the annotation was intact, the text was not. Detect this from
content (proportion of masked or degenerate tokens per document) rather than by
name or genre, and report the proportion for every document so that partial
cases stay visible.

## What not to do

- Do not refactor or "improve" the metric definitions to be more elegant. They
  must match the published definitions exactly.
- Do not silently drop documents that fail alignment or parse checks. Report
  them with counts.
- Do not aggregate across genres, registers or corpora into a single headline
  number without also reporting the per-subset breakdown. Evaluating by data
  subset rather than in aggregate is a deliberate methodological choice here,
  and it is what surfaced every real problem in phase 1.
- Do not draw a conclusion from a subset selected on extreme values without
  saying so. Selection on extremes guarantees regression to the mean on
  resampling, independently of whether any effect exists.
- Do not add a web UI, a CLI framework, or packaging. This is research code
  that produces tables.

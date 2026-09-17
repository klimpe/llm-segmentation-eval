# Phase 2: LLM segmentation run — design decisions

Design decisions for the SBCSAE (intonation-unit) LLM segmentation run.
One short section per decision. No corpus text in this file — counts and
rates only, per the SBCSAE licence.

## 1. Lowercasing

**Finding.** Whole-corpus capitalisation audit (`sbcsae_capitalization.py`,
239,108 words scored, literal "I" excluded), by position:

| category | n words | n capitalised | share |
|---|---:|---:|---:|
| (a) IU-initial after `.` | 11,235 | 10,558 | **0.940** |
| (b) IU-initial after `,` | 22,584 | 1,783 | 0.079 |
| (c) IU-initial after `?` | 1,098 | 1,015 | **0.924** |
| (d) IU-initial after `--` | 2,759 | 1,534 | 0.556 |
| (e) turn-initial | 21,426 | 18,379 | **0.858** |
| (f) IU-internal (baseline) | 179,917 | 7,338 | 0.041 |
| (g) IU-initial, no marker (residual) | 89 | 73 | 0.820 |

(a), (c), (e) sit 20-23x the IU-internal baseline; (d) is 13x. Only (b) is
close to baseline (2x). Capitalisation tracks the same IU-boundary signal
CLAUDE.md already strips out via `.`/`,`/`?`/`--` Boundary items — it is a
second channel carrying the same information the pipeline otherwise takes
care to remove before rendering.

**Decision.** Lowercase every rendered word, uniformly, in both
conditions, "I" included. Implemented in `sbcsae_llm.py`'s rendering layer
only (`_word_piece`): `Word.text` — the tokeniser's own identity, used for
masses, scoring, and everything else — is untouched; only the string
placed in the prompt is lowercased. Speaker labels and cue symbols (`(H)`,
`...`, etc.) are not touched.

**Why uniform, not positional.** A rule like "lowercase every word except
a turn's first" would remove the leak in form only: the model could still
read "this word is capitalised" as "this word starts a unit," just via a
rule the pipeline itself imposed rather than one the transcriber's
convention imposed. That is re-encoding the same signal through a
different channel, not removing it. Uniform lowercasing removes the
channel entirely, regardless of position.

**What is lost.** Proper-noun and acronym distinctiveness (e.g. this
corpus's own confirmed capitalised acronyms, `reports/
phase2_tokenizer_capitalised_tally.csv`'s "TV", kept=23) and ordinary
text readability. Both are real costs, but orthogonal to the boundary
signal being removed — nothing here suggests losing them helps or hurts
segmentation specifically, only that keeping them would have re-opened
the position leak.

Tests: `tests/test_sbcsae_llm.py` — no rendered word contains an
uppercase letter (checked on synthetic IUs mixing capitals, "I", and a
turn-initial capital); condition A and B of the same window differ only
by the presence of cues, after lowercasing; speaker labels and cue
symbols are confirmed untouched.

## 2. Truncated words: where they fall in the IU

**Finding.** Truncated words (`y-`, kept always in both conditions per
CLAUDE.md's "Tokenisation" section, as actually uttered) are a text-level
cue already present regardless of condition — unlike the tier-2 cues that
condition A strips, a truncated word's trailing `-` is part of the word
itself and survives in A too. Whole-corpus position breakdown
(`sbcsae_truncation_position.py`, 246,974 words scored, 3,759 truncated
words = 1.5% of all words), relative to the word's own reference segment:

| position | n truncated | share of truncated | n all words in position | truncation rate |
|---|---:|---:|---:|---:|
| IU-initial | 707 | 0.188 | 47,877 | 0.0148 |
| IU-internal | 995 | 0.265 | 135,454 | 0.0073 |
| IU-final | 1,656 | **0.441** | 47,877 | **0.0346** |
| IU-initial-and-final (1-word IU) | 401 | 0.107 | 15,766 | 0.0254 |

Truncation concentrates at IU-final position (44% of all truncated words,
a rate 4-5x the IU-internal rate) and in single-word IUs (a truncated
word standing alone as its own IU, rate 2.5x the IU-internal rate) — both
consistent with a truncated word marking an abrupt stop, which frequently
is where the speaker's contour actually breaks off.

**Decision: none.** This is recorded as a known text-level cue present in
both A and B, not turned into a rule — unlike capitalisation, nothing
here is being introduced by the rendering step or the reader/tokeniser
that needs correcting. It is left as-is for the same reason condition B's
prosodic cues are left as-is: whatever predictive value a truncated
word's position carries is exactly the kind of signal this phase exists
to measure the model's use of, not something to strip before the run.

## 3. Degenerate-output threshold

**Finding.** The longest run of consecutive within-turn reference
boundaries in any single 600-word scored window, anywhere in the corpus
(`sbcsae_degenerate_threshold.py`, 59 files): **11**, in SBC038 (words
2401-3000). One-word IUs are common on this corpus (median 3 words/IU,
`reports/phase2_per_file_stats.csv`), so short runs of consecutive
boundaries are legitimate, unlike phase 1's prose-derived EDUs — a
threshold guessed instead of measured risks flagging correctly segmented
rapid speech as a model failure.

**Decision: flag threshold 22 (2x11), raised from the previously recorded
12 (11+1).** One more than the single most extreme legitimate case the
corpus happens to contain treats that one observed maximum as a hard
ceiling; but 59 files is a finite sample, and the next real run
containing another case merely as extreme as SBC038's is not evidence of
a model failure, just of more than one case existing near the corpus's
own extreme. Doubling leaves headroom proportional to the scale of the
phenomenon actually observed, rather than sitting exactly on its edge.

**This does not mean runs between 12 and 22 go unexamined.** Per the
pilot review policy (`sbcsae_degenerate_threshold.review_policy`): every
draw containing a run **strictly longer than 11** — the actual observed
legitimate maximum, not the doubled flag threshold — is listed for manual
reading, whether or not it is automatically flagged as degenerate at 22.
A run of, say, 15 has no precedent in the reference and is worth a human
look even though it will not be auto-flagged. The two thresholds do two
different jobs: 22 triggers an automatic label used in aggregate
reporting, 11 triggers a human reading one specific draw.

Tests: `tests/test_degenerate_threshold.py` covers both thresholds and
the boundary cases between them (11, 15, 22, 23).

## 4. Word-internal marks in condition B

**Finding.** A tier-2 mark glued on BOTH sides to real word content
(`s=o`) is fused by the tokeniser into that `Word`'s own `.raw` field
rather than emitted as a separate `Cue` item (`sbcsae_tokenizer.py`'s
`_sandwiched` mechanism) — but condition B's rendering used `Word.text`
(the bare, mark-stripped form) for every word, so a sandwiched mark was
never emitted anywhere: not in `.text`, and not as a `Cue` either. A mark
glued on only one side (word-final `so=`, or leading with nothing open,
`!Ron`) is NOT sandwiched and was already rendering correctly as its own
token.

Whole-corpus count (`sbcsae_word_internal_marks.py`, classification via
the tokeniser's own `_sandwiched`/`_is_glued`, not an approximation):

| symbol | word-internal (vanished) | word-final | standalone | total | vanish share |
|---|---:|---:|---:|---:|---:|
| `=` (lengthening) | 4,235 | 5,303 | 2 | 9,540 | **0.444** |
| `%` (glottal stop) | 77 | 177 | 1,306 | 1,560 | 0.049 |
| `!` (booster) | 45 | 0 | 333 | 378 | 0.119 |

**44% of every lengthening mark in the corpus — its single most common
tier-2 cue by far — was silently invisible in condition B.** A handful of
additional `%`/`=` occurrences (98 and 18 respectively) come from
compound rules (`(%Hx)`, `(H=)`, etc.) that always decompose into their
own separate `Cue` item regardless and were never affected.

**Decision.** `sbcsae_llm.py`'s `_word_piece` now renders `Word.raw` in
condition B (`12:ho=me`) and `Word.text` in condition A (`12:home`) —
word identity, count and the masses contract are untouched either way,
only which string reaches the prompt. Tests: a word-internal mark
appears in B and not A; a general "strip every tier-2 mark from a B line
reproduces the A line exactly" property test (`=`, `%`, `!` removed from
inside word pieces; whole standalone-cue tokens dropped; `-`/`_` inside a
word are never touched, since they are real word identity — a truncated
word's own trailing `-`, or an underscore-joined compound — never a
fused mark).

## 5. Canonical cue symbols

**Finding.** Rendering a `Cue` used `.raw`, the exact matched substring
— fine for a plain rule (`lengthening` is always `=`), but `breath_in`
and `breath_out` vary by case (`(h)`, `(HX)` alongside `(H)`, `(Hx)`) and,
for a `Cue` produced by decomposing a "compound" rule match, by which
compound produced it: whole-corpus count found `breath_in` raw as `(H)`
10,046 times but also `(H` (12, from the `breath_paren_lengthening`
compound), `(H[` (1) and `(H]` (1) — none valid symbols on their own, and
none in the glossary. Rendering `.raw` directly would have leaked a
malformed fragment into the prompt.

**Decision.** Render the canonical symbol for a cue's *kind*
(`CUE_CANONICAL_SYMBOL`), never `.raw`. Two kinds confirmed present that
were not previously glossed — `displaced_truncation` (`-`, 17
occurrences: a truncation mark with nothing to attach to) and
`underscore_truncation` (`_`, 20 occurrences: the same thing in
SBC012/SBC013's own written form) — were added to the glossary so the
symbol-canonicalisation and glossary-completeness properties both hold
together, not just in the common cases.

**Test:** `tests/test_cue_glossary_coverage.py` renders every 800-word
window of every file (59, `SBC037` excluded) under condition B and
checks every symbol — standalone or embedded — is one of
`GLOSSARY_SYMBOLS`. This is a whole-corpus regression, not a spot check.

**Found along the way, not asked for, not fixed here: a reader defect.**
4 of 59 files (`SBC027`, `SBC055`, `SBC059`, `SBC060`) have a raw `.trn`
line with two tabs immediately after the timestamps and nothing between
them. `sbcsae_reader._HEAD_RE`'s `rest` group is captured after a greedy
`\s*`, which swallows both tabs as one gap, so `split_line_fields`'s
"content before the first remaining tab is the speaker" rule (needed for
real colon-less codes like `MONTOYA`) wrongly takes the actual IU text as
the speaker and leaves the text field empty — corrupting that IU's
speaker, and, since an empty `speaker_field` does not update
`current_speaker`, every following same-run IU until the next
well-formed speaker field too. 9 IUs directly affected across the 4
files (some number more indirectly, not yet quantified). Excluded from
`test_cue_glossary_coverage.py` by name, with the investigation recorded
in the test's own comment, rather than silently skipped. Two
superficially similar cases — `SBC052`'s `~Janine` and `SBC056`'s
`@@@2]` — are NOT this bug: both are pre-existing, already-documented
real speaker-field content and were left untouched.

CLAUDE.md marks the reader "settled... do not revisit without new
evidence" — this is that evidence, but fixing `sbcsae_reader.py` is out
of scope for this session (not one of the steps asked for, and it would
touch every downstream figure that depends on speaker assignment, e.g.
the per-file speaker-change counts in
`reports/phase2_per_file_stats.csv`). The pilot (step 4, next) uses only
`SBC039`, which is not one of the 4 affected files, so this does not
block it. Flagged here for a decision before phase 2 scales past the
pilot, not silently patched or silently ignored.

## 6. Prompt wording: no claim untrue of any file

**Finding.** The task description called the source "multi-party spoken
conversation" — false for `SBC025`, which has 0 speaker changes
(`reports/phase2_per_file_stats.csv`): a monologue, not a conversation.

**Decision.** Replaced with "spontaneous spoken discourse", true
regardless of how many speakers a given file has. "One speaker turn per
line" is unaffected — still literally true even for a file that turns
out to be one turn from start to end.

## 7. Pilot run configuration

Same model and call settings as phase 1 (`llm_segmenter.py`,
`reports/phase1_report.md` §2): model `claude-sonnet-5`, `max_tokens=8192`,
extended thinking disabled (a phase 1 finding: left on its default, some
responses burned the whole `max_tokens` budget on thinking and returned
zero text), no `temperature`/`top_p`/`top_k` (unsupported by this SDK —
sampling variance is addressed by resampling, not pinning, per CLAUDE.md's
"Sampling" section). Zero-shot only, per phase 1's own standing
conclusion for phase 2 (`reports/phase1_report.md`: "Standing
configuration for phase 2: Zero-shot, not few-shot").

Pilot scope: `SBC039`, 8 windows (800-word window / 600-word scored
core / 100-word margin, `sbcsae_windows.py`) x condition {A, B} x
`n_samples=5`. Raw output persisted per (condition, window, sample) under
the gitignored `llm_output_sbcsae/` (real transcript-derived content, per
the licence). See `reports/phase2_pilot.md` for the run itself.

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

**Found along the way this session, fixed a later session: a reader
defect.** 4 of 59 files (`SBC027`, `SBC055`, `SBC059`, `SBC060`) have a
raw `.trn` line with two tabs immediately after the timestamps and
nothing between them. `sbcsae_reader._HEAD_RE`'s `rest` group is
captured after a greedy `\s*`, which swallows both tabs as one gap, so
`split_line_fields`'s "content before the first remaining tab is the
speaker" rule (needed for real colon-less codes like `MONTOYA`) wrongly
took the actual IU text as the speaker and left the text field empty (or,
for `SBC055`, truncated) — corrupting that IU's speaker, and, since an
empty `speaker_field` does not update `current_speaker`, every following
same-run IU until the next well-formed speaker field too. 9 IUs directly
affected across the 4 files. Two superficially identical cases —
`SBC052`'s `~Janine` and `SBC056`'s `@@@2]` — are NOT this bug: nothing
in the raw line's structure tells them apart from the real defect, only
content does (there the field before the surviving tab really is the
speaker code), so the fix could not be a general rule.

**Fixed.** `sbcsae_reader.py`'s `KNOWN_EMPTY_SPEAKER_STRAY_TAB` names the
exact 4 (file, line) pairs and reparses only those, joining every
non-blank field after the empty speaker with a single space (a no-op for
3 of the 4, which have exactly one real field; `SBC055`'s stray tab sits
mid-sentence, splitting what reads as one continuous utterance) — a
named, line-anchored exception in the same style as
`CROSS_SPEAKER_AMPERSAND` above, not a general regex change, since
`SBC052`/`SBC056` are structurally identical to the bug and must not be
touched. Confirmed against the whole corpus: exactly these 4 files'
output changes (9 IUs), the 70,083-to-69,772 derivation still holds term
by term, and every tokeniser/invariant check still passes. The
`test_cue_glossary_coverage.py` by-name exclusion for these 4 files has
been removed — the whole-corpus glossary-coverage check now covers them
like every other file and still passes.

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

## 8. Degenerate-run detection: basis check and aggregate exclusion

**Basis check.** `sbcsae_pilot.analyse`'s degenerate-run detector counts
runs over `d.kept` — within-turn hypothesis indices only, since
`_parse_window_response` already drops any turn-initial index the model
returned before `kept` is ever populated. Confirmed empirically against
the pilot's own two flagged draws (sample 0/window 1, run 15; sample
3/window 5, run 26): neither run's span contains a turn boundary, so the
run-length count already matches `sbcsae_degenerate_threshold.py`'s own
basis for `MAX_LEGITIMATE_RUN`/`DEGENERATE_FLAG_THRESHOLD` (within-turn
reference boundaries only, turn boundaries excluded by construction, not
by coincidence). No fix was needed.

Both flagged runs were read in full (indices, rendered text, reference
boundaries): each marks a new intonation unit at literally every word for
15–26 consecutive words, matching only 3–4 real reference boundaries over
that span — enumeration, not a plausible segmentation, in both cases.

**Aggregate exclusion.** CLAUDE.md's "Degenerate output" section requires
flagged draws to be reported separately, not folded into the aggregate —
previously recorded as a policy but not actually wired into
`sbcsae_pilot.py`'s scoring. Now: any sample with an auto-flagged
(run > 22) window is excluded from the whole-file score aggregate (mean/
range) and reported in its own "Auto-flagged draws" table instead; the
same exclusion applies per (sample, window) pair for the per-window score
aggregate. A `needs_manual_review`-only run (11 < run ≤ 22, not
auto-flagged) stays in the aggregate — that threshold exists to prompt a
human reading, not to change what gets averaged (`reports/
phase2_llm_design.md` §3's own two-threshold design). Every score dict is
now tagged with its sample index (`scores["sample"]`) so a report can
show which sample a row came from once exclusion means list position no
longer equals sample number.

## 9. Extended scoring: boundary-count ratio, offset distribution, position F1

`sbcsae_scoring._compute_metrics` already called `boundary_precision_
recall`, `boundary_f1`, `window_diff` and `boundary_similarity` from
`metrics.py` (unchanged) for both scopes; the pilot report just wasn't
showing precision/recall/boundary_similarity, only F1 and WindowDiff.
Now shown for both scopes, per sample. One genuinely new figure was
added, not present in `metrics.py`: `boundary_count_ratio` = |hyp
boundaries| / |ref boundaries| (1.0 if both empty; `None`, not a
division error, if the reference has none but the hypothesis does — no
finite ratio describes that). A ratio > 1 means over-segmentation, < 1
under-segmentation — cheap to read alongside F1, which alone does not
say which direction an error leans.

**Offset distribution.** For every within-turn hypothesis boundary
(pooled over all non-flagged, successful draws, per condition): the
signed distance, in tokens, to the nearest within-turn reference boundary
(`sbcsae_pilot._nearest_signed_offset`, a simple bisect nearest-neighbour
search over the document's sorted reference boundary set). Bucketed into
-3..+3 plus a beyond-range tail. This answers a question F1 cannot: when
the model is wrong, is it wrong by a little (near-miss, off by one or two
words) or by a lot (a different segmentation decision entirely)?

**Position-in-core F1.** Within-turn precision/recall/F1 pooled
(micro-averaged tp/fp/fn, not a mean of per-window F1s) by fixed 200-word
position inside each window's 600-word score core (1–200, 201–400,
401–600 — literal word-count chunks, so a shorter final window's words
all land in the first bucket rather than being rescaled to thirds). Bug
caught while implementing this: the first version compared local
1-indexed *start positions* directly against boundary ("after token p")
positions without the same `i − 1` conversion `score_document` applies
internally, which silently deflated every position-bucket F1 by roughly
half; fixed by converting to boundary space before comparing, and
verified by checking that summing the three buckets' pooled tp/fp/fn
reproduces the same overall F1 as the existing (unbucketed) per-window
scoring, sample by sample.

## 10. No-model baselines: cue rule and density-matched random

Per CLAUDE.md's own governing logic for the project (a score means little
without something to compare it to) and the standing instruction to
validate any new number against an external reference: two baselines,
scored with the exact same `score_document` and window regions as the
model, so they sit in the same tables (`sbcsae_baselines.py`,
`reports/phase2_baselines.md`).

**Cue rule (condition B only).** A boundary before every word
immediately preceded — through any run of stacked cues — by a pause
(`..`/`...`) or an in-breath (`(H)`): exactly the three cue kinds
condition B keeps and condition A strips. Deterministic, one hypothesis
per file, not resampled. On the pilot file this rule alone reaches a
within-turn F1 in the same range as the model's own mean — a useful
ceiling-side sanity check: some of what looks like the model "using"
prosodic cues may be reachable by the cue's mere presence, not real
integration of cue and lexical/syntactic content.

**Random (both condition labels — the draw itself never looks at cues,
so "A" and "B" differ only in which independent set of 100 draws was
taken).** Per window, per draw: as many within-turn boundary positions as
the reference has in that window, chosen uniformly at random without
replacement from the window's own valid candidate positions (turn
boundaries excluded — never a legitimate prediction). Density-matched
per window, not once for the whole document, so a high-IU-density window
draws proportionally more random boundaries than a low-density one, the
same way the reference itself varies. 100 draws, `n=100` mean and range,
per CLAUDE.md's "Sampling" section — never a single draw, even for a
baseline cheap enough to run many more times than that.

Both baselines run on `SBC039` and on all 59 files (`SBC037` excluded),
per file and overall — a full corpus-wide per-file table is allowed here,
unlike for a real model run, specifically because no model call is
involved (CLAUDE.md's per-subset-breakdown rule is about not hiding
per-subset problems behind an aggregate, not about table size). Overall
figures are a macro mean across files with the across-file range shown
alongside, not a single pooled number, for the same reason.

`window_diff` (from `metrics.py`, unchanged) is O(n²) in its naive
sliding-window implementation; scoring 100 random draws per file at
whole-document length made the corpus-wide run the slowest script in the
pipeline (on the order of a minute per file). Left as is: `metrics.py` is
explicitly out of scope for "improvement" (CLAUDE.md, "What not to do"),
and the run only needs to happen once per corpus-affecting change, not
per model call.

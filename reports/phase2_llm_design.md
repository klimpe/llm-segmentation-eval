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

`window_diff`'s original implementation was O(n²) in its naive
sliding-window scan; scoring 100 random draws per file at whole-document
length made the corpus-wide run the slowest script in the pipeline (on
the order of a minute per file). **Since optimised (§12)** — the
corpus-wide baseline run now completes in well under a minute total, not
per file — without changing the metric's published definition, only the
implementation.

## 11. Prompt indexing convention: first word of the new unit, never the last of the old one -- tested and rejected as the explanation for the -1 asymmetry

**Finding.** The pilot's offset-distribution table (reports/
phase2_pilot.md) shows condition B's within-turn errors skewed toward
offset -1 (1,112 boundaries) far more than +1 (699) -- condition A is
nearly symmetric. `sbcsae_cue_adjacency.py`, reading only the cached
pilot draws (no model calls), asks the direct, hypothesis-side question
for condition B (dropped for A: it renders no cues at all, so the answer
is 0% there by construction): for the word the model actually NAMED as a
new unit's start, is a cue rendered immediately after it? Reported
against the document's own background rate for this (12.7%, all
within-turn-eligible word positions with a cue immediately after them),
by offset bucket:

| offset | -3 | -2 | -1 | 0 | +1 | +2 | +3 | beyond |
|---|---|---|---|---|---|---|---|---|
| share, named word followed by a cue | 25.8% | 14.8% | **75.4%** | 20.7% | 18.6% | 19.8% | 31.0% | 19.0% |
| vs. base rate (12.7%) | 2.03x | 1.16x | **5.95x** | 1.63x | 1.47x | 1.56x | 2.44x | 1.50x |

Offset -1 sits at 5.95x the base rate, far clear of every other bucket
(next highest 2.44x) -- a strong, direct correlation between the -1 mass
and cue-following positions.

**Decision (tried).** This pattern read as an indexing ambiguity, not a
segmentation-ability gap: at a cue-marked boundary, "where do you report
the position" has two plausible readings -- the last word before the
interruption, or the first word after it -- and the prompt did not say
which. Added to `sbcsae_llm._IU_DEFINITION`: "A reported position is
always the first word of the new intonation unit -- never the last word
of the one before it," with a short invented example (not drawn from the
corpus). Nothing was added about how cues relate to boundaries -- that
relationship is exactly what condition B's cue-visibility manipulation
exists to let the model discover or fail to discover on its own (§9's
"purely denotational, never relational" principle for the cue glossary
applies here too).

**Outcome: tested and rejected.** Rerunning SBC039 condition B
(n_samples=5, clarified prompt, reports/phase2_pilot.md's rerun section)
did not reduce the -1 asymmetry -- the -1:+1 ratio grew, 1.59 -> 2.00,
the wrong direction for the theory. The small F1/exact-match upticks in
that rerun sit within the original run's own sample range and are
attributed to resampling noise, not to the fix (CLAUDE.md already
documents this exact failure mode from phase 1). **The correlation above
is real and unretracted; the specific causal story built on it -- that
the model already finds the right cue-marked boundary and merely reports
the wrong side of it -- is not.** The clarified wording is kept anyway
(unambiguous, free, a genuine prompt-quality improvement regardless of
this asymmetry), but it is not the explanation for the -1 mass. See
reports/phase2_pilot.md's "Remaining explanation" section: the model may
be deciding the boundary itself one word early near cues, not
misreporting a correctly-decided one -- a claim a (start, end)-pair
answer format could test directly, since it removes the labeling
ambiguity structurally rather than by instruction.

## 12. `window_diff` speed: implementation optimised, definition unchanged

Per CLAUDE.md ("do not refactor or improve the metric definitions to be
more elegant... Do tell me when an implementation detail is wrong") and
this session's own instruction to optimise the implementation only: the
O(n²) naive per-window rescan (iterating the full boundary set for every
sliding-window position) is replaced with an O(n) incremental scan that
updates each side's in-window boundary count by one set-membership check
per position entering/leaving the window, rather than rescanning the
whole boundary set each time.

**Equivalence, not just speed.** `tests/test_window_diff_speed.py` keeps
a verbatim copy of the previous implementation (`_window_diff_naive`,
never touched again after being copied out) and checks the new
`metrics.window_diff` returns bit-identical values against it: 10,000
random (ref, hyp) mass pairs with `n_tokens` spanning this corpus's own
observed document-length range (1,824-6,628 words, reports/
phase2_per_file_stats.csv) and boundary density varied across each pair
(uniform in [0.03, 0.4], not just this corpus's own ~1/5 mean), plus 20
small-n cases run on every test invocation as a fast regression guard.
The corpus-scale 10,000-pair proof takes on the order of tens of minutes
(naive) and is gated behind `RUN_SLOW_TESTS=1`, not run by default, per
the same "run once per corpus-affecting change" policy §10 already
applies to the baseline run itself.

**Result: exact match on all 10,000 corpus-scale pairs (PASSED).** Total
wall time for the 10,000-pair run: 2,911.9s (~48.5 min) for the naive
implementation vs. 10.8s for the optimised one -- **269.6x**. (A single
isolated call at n=6,628, this corpus's longest file: ~0.58s -> ~0.0017s,
~340x -- close to, not identical to, the aggregate 269.6x, since the
10,000-pair run spans the full corpus length range and a mix of boundary
densities, not one fixed size.) The corpus-wide baseline run
(`sbcsae_baselines.py`, §10), which scores window_diff twice per random
draw x 100 draws x 59 files, dropped from "slowest script in the
pipeline, on the order of a minute per file" (order of an hour total) to
42.7s total -- confirmed by rerunning it and diffing the output against
the previously committed
`reports/phase2_baselines_per_file.csv`/`reports/phase2_baselines.md`:
byte-identical.

## 13. Long jobs write progress as they go, not only at the end

**Decision.** `sbcsae_baselines.py`'s corpus-wide run now opens its
output CSV once, writes the header, and writes + flushes one row
immediately after each file's baselines are computed, instead of
accumulating all 59 rows in memory and writing them only after the last
file finishes. A run that is killed partway, or just being watched,
shows real, already-computed results on disk for every file processed so
far, not nothing until the very end. The markdown summary
(`write_report`) still needs the complete set and is written once at the
end, since it is a genuine final aggregate, not a per-file row -- the
per-row streaming applies to the CSV, not the summary that depends on
every row existing.

The same principle applies to the corpus-wide LLM segmentation runner
once it is written (reports/phase2_pilot.md's "Next" section) -- a
59-file run making real API calls is exactly the kind of long job this
matters most for, and should stream one file's row to disk as soon as
that file's samples are scored, not buffer the whole corpus in memory
until the run completes or fails.

## 14. Degeneracy threshold: per file, not global -- 11 was calibrated on one outlier

**Finding.** `MAX_LEGITIMATE_RUN=11`/`DEGENERATE_FLAG_THRESHOLD=22`
(§3, `sbcsae_degenerate_threshold.py`) are whole-corpus constants: 11 is
the single longest run of consecutive within-turn reference boundaries
found ANYWHERE in 59 files, and it comes from one file, SBC038. Checked
directly against the first 10 batch-1 files
(`sbcsae_degenerate_threshold.file_max_legitimate_run`, reference data
only, no model call): their own legitimate maxima are

| doc_id | SBC024 | SBC005 | SBC041 | SBC053 | SBC012 | SBC045 | SBC016 | SBC014 | SBC052 | SBC044 |
|---|---|---|---|---|---|---|---|---|---|---|
| own max legitimate run | 5 | 4 | 5 | 3 | 5 | 4 | 4 | 4 | 4 | 6 |

None reach 11. A threshold calibrated on the single most extreme file in
59 is not a meaningful ceiling for a typical file -- it is far too
lenient for every file except the one it was measured on. SBC053's own
ceiling is 3, yet under the global rule nothing shorter than 12 even
gets a manual-review flag; under the global rule's 22-run auto-flag
line, the whole-corpus figures (23 auto-flagged draws in the 675
window-draws attempted so far) undercount how often batch-1 files
actually collapse.

**Decision.** Replaced with a per-file rule
(`sbcsae_degenerate_threshold.per_file_review_policy`,
`sbcsae_degenerate_per_file.py`): a run is degenerate iff it is BOTH
longer than THIS FILE's own observed maximum legitimate run AND
predicts more than 3x as many boundaries as the reference actually has
in that same span. Both conditions are needed -- length alone conflates
"unusual for this file" with "wrong" (a file whose own reference
regularly contains longer runs of short IUs should not be flagged for
matching its own normal density); the ratio alone would flag a run that
is long but still broadly tracks a real, dense stretch of one-word IUs,
which the file's own reference already shows is legitimate, not a
collapse.

**Recomputed over every cached batch-1 window-draw (675 attempted, no
model call -- read from cache only), old rule vs new rule side by
side:**

| doc_id | cond | file max | attempted | old rule (run>22) | new per-file rule | collapse rate (new) | share of scored words in runs (new) |
|---|---|---|---|---|---|---|---|
| SBC024 | A | 5 | 25 | 1 | 4 | 16.0% | 0.44% (57/12,870) |
| SBC024 | B | 5 | 25 | 0 | 0 | 0.0% | 0.00% |
| SBC005 | A | 4 | 25 | 1 | 1 | 4.0% | 0.20% (29/14,265) |
| SBC005 | B | 4 | 25 | 0 | 0 | 0.0% | 0.00% |
| SBC041 | A | 5 | 30 | 0 | 2 | 6.7% | 0.09% (14/15,375) |
| SBC041 | B | 5 | 30 | 1 | 5 | 16.7% | 0.57% (88/15,375) |
| SBC053 | A | 3 | 35 | 4 | 13 | 37.1% | 1.79% (324/18,145) |
| SBC053 | B | 3 | 35 | 2 | 11 | 31.4% | 0.97% (176/18,145) |
| SBC012 | A | 5 | 35 | 0 | 1 | 2.9% | 0.05% (10/19,485) |
| SBC012 | B | 5 | 35 | 1 | 4 | 11.4% | 0.28% (54/19,485) |
| SBC045 | A | 4 | 40 | 1 | 10 | 25.0% | 0.78% (168/21,410) |
| SBC045 | B | 4 | 40 | 0 | 8 | 20.0% | 0.27% (58/21,410) |
| SBC016 | A | 4 | 40 | 1 | 11 | 27.5% | 0.53% (121/22,950) |
| SBC016 | B | 4 | 40 | 2 | 8 | 20.0% | 0.54% (124/22,950) |
| SBC014 | A | 4 | 45 | 1 | 7 | 15.6% | 0.52% (128/24,470) |
| SBC014 | B | 4 | 45 | 1 | 19 | 42.2% | 0.73% (179/24,470) |
| SBC052 | A | 4 | 50 | 3 | 13 | 26.0% | 0.69% (190/27,530) |
| SBC052 | B | 4 | 50 | 1 | 9 | 18.0% | 0.37% (101/27,530) |
| SBC044 | A | 6 | 25 (partial) | 3 | 14 | 56.0% | 0.80% (255/31,860) |
| SBC044 | B | 6 | 0 (not yet run) | -- | -- | n/a | -- |

**Total: 23 draws flagged under the old rule vs 140 under the new one,
out of the same 675 attempted window-draws.** The old, globally-lenient
rule was undercounting degenerate collapse by roughly 6x across this
batch. `sbcsae_batch1.py` is updated to compute and report both
`collapse_rate` and `share_words_in_runs` per file/condition alongside
F1 (columns added to `reports/phase2_batch1_scores.csv`) precisely
because F1 barely moves when a collapse happens (SBC053 condition A: 4
of 5 samples auto-flagged under the OLD rule, whole-file F1 moves by
only 0.007 when they are folded back in -- reports/phase2_pilot.md-style
degenerate exclusion is necessary but not sufficient; a rate that is
actually sensitive to how often and how much a document collapses is
needed alongside it, not instead of it).

The whole-corpus `MAX_LEGITIMATE_RUN`/`DEGENERATE_FLAG_THRESHOLD`
constants in `sbcsae_degenerate_threshold.py` are left in place (still
used by the original SBC039 pilot's own already-published analysis,
untouched by this change) -- the per-file rule is additive, not a
retroactive rewrite of already-reported figures.

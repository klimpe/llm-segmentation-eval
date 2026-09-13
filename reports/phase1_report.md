# Phase 1 — Zero-shot LLM discourse segmentation on written text

Working report. Not for circulation.

---

## 1. What this measures and why

An LLM is asked to segment a text into discourse units. Its output is compared
against human annotation using standard segmentation metrics. The question is
how far the model's segmentation is from the human one.

The reason this phase exists is not the number itself. Evaluations of this kind
routinely publish a score with no reference point, which leaves the number
uninterpretable: a WindowDiff of 0.27 tells you nothing unless you know what two
human annotators score against each other on the same data. Establishing that
ceiling requires a corpus with multiple independent annotations, which the data
used here does not have.

Phase 1 therefore has three limited goals:

1. Build and validate the pipeline on data where errors are detectable, because
   a reference scorer and published system results exist.
2. Obtain a baseline for written text, against which spoken data can later be
   contrasted.
3. Establish whether the gap between model and human is attributable to
   ignorance of the corpus's annotation conventions.

The wider question — how much of discourse structure survives the reduction of
speech to text — is addressed in phases 2 and 3, and no claim about it is made
here.

---

## 2. Data

**Corpus.** `eng.rst.gum` from the DISRPT shared task collection, development
split: 24 documents across 12 genres, 2 documents per genre.

**Format.** The `.tok` track, not `.conllu`. This is deliberate. The `.conllu`
track supplies gold sentence splits and morphosyntactic parses; since discourse
unit boundaries frequently coincide with sentence boundaries, providing sentence
segmentation would give the model a substantial part of the answer and make the
comparison uninformative.

**Exclusions.** Two documents were excluded: `GUM_reddit_pandas` and
'GUM_reddit_macroeconomics'. In the openly distributed version of GUM,
Reddit-sourced texts are masked — each token is replaced by a run of underscores
matching its character length, preserving the annotation while removing the
text, because Reddit's terms do not permit redistribution. Masking rates in
these two documents are 96.7% and 97.5%.

All 22 remaining documents contain 0% masked tokens; no partial masking exists
in this split. Exclusion is nonetheless implemented by measuring masked-token
proportion per document (threshold 50%) rather than by genre name, so that
partial masking in other corpora would be detected rather than silently
depressing a genre's scores.

**Model.** `claude-sonnet-5`, called with `max_tokens=8192` and extended
thinking explicitly disabled (`thinking={"type": "disabled"}`) — see §5 for why.

**Sampling.** Temperature, `top_p` and `top_k` were left unset for all runs
reported here. Because responses are cached to disk and reused, **each
document was sampled exactly once** in each condition for the main results in
§4.1-§4.4, and run-to-run variance was not measured there. Every corpus/genre
figure in those sections is therefore built from single draws. See §6 for what
this does and does not undermine.

An attempt was made to fix sampling at `temperature=0` for reproducibility.
This is not possible: the installed SDK (`anthropic` 1.4.0, matching the
Claude 5 model family) exposes no `temperature`, `top_p`, or `top_k` parameter
on `messages.create()` at all — confirmed by inspecting the method's actual
signature and grepping the installed package for any trace of the word.
Passing `temperature` raises `TypeError` immediately, which is how this was
caught (an earlier commit that added it went untested against a real,
non-cached call and shipped broken). Sampling control on this API has
apparently moved to `output_config` (currently just `effort` and `format`),
with nothing equivalent to a raw sampling-temperature knob. So there is no
"default temperature of 1.0" to report either — that would assume a specific
numeric value that cannot be confirmed or set through this client.

Since sampling cannot be pinned, variance is measured by repetition instead:
§4.6 resamples 8 of the 22 documents 5 times each, under whatever default
(uncontrolled) sampling the API applies, and reports the spread.

**Run date.** 08.09.2026.

---

## 3. Method

### 3.1 Representation

All segmentations — reference and hypothesis — are reduced to **segment
masses**: a list of segment lengths in atomic units. The atomic unit is the
token as tokenised by the corpus; no re-tokenisation is performed.

Two segmentations are comparable only if their masses sum to the same total. The
pipeline asserts this before computing any metric. Documents failing the check
are set aside and reported rather than scored.

### 3.2 Metrics

Three metrics are computed:

- Boundary precision, recall and F1
- WindowDiff (Pevzner & Hearst 2002)
- Boundary Similarity (Fournier & Inkpen 2012; Fournier 2013)

All three were reimplemented in Python 3 rather than ported from earlier
Python 2 research code.

### 3.3 Validation of the metric implementations

Because an incorrect metric returns a plausible number rather than an error,
the implementations were validated in three independent ways.

**Against the reference implementation.** WindowDiff and Boundary Similarity
were cross-checked against `segeval`, the implementation by the author of
Boundary Similarity, on randomly generated segmentation pairs: 2,874 trials for
WindowDiff and 2,899 for Boundary Similarity (n_t ∈ {2,3,4,5}), with zero
mismatches after two bugs were fixed. The bugs were a missing floor of 2 on
WindowDiff's window size, and a reversed hypothesis/reference argument order.

`segeval` is used only as a test-time reference and is not a project
dependency; the cross-check is skipped if it is not installed.

**Against the official scorer.** DISRPT's `utils/seg_eval.py` was obtained and
inspected. It computes a **micro-average**, pooling boundaries across all
documents rather than averaging per-document scores — a methodological detail
that materially affects the corpus-level figure. The pipeline's
`corpus_micro_boundary_prf` replicates it exactly and was cross-checked against
the actual script over 500 random trials with zero mismatches.

**By perturbation.** A fixed 36-token, 10-segment reference was damaged in four
known ways — boundary shifted by one, boundary deleted, spurious boundary added,
segmentation randomised — with expected metric values derived by hand. This
includes an explicit test that Boundary Similarity ranks a one-token shift above
an isolated deletion or insertion, which precision/recall cannot distinguish and
which is the metric's reason for existing.

### 3.4 Corpus statistics as a parser check

After correcting the reader to skip CoNLL-U multiword-token range rows (`1-2
What'd`), matching `seg_eval.py`'s own behaviour, the total segment count across
all 24 dev documents matches the published DISRPT statistic exactly: 2,790. The
remaining token-count difference (21,409 against a published 21,743) is fully
accounted for by 334 multiword range rows counted in the published table and
correctly not counted here.

---

## 4. Results

### 4.1 Corpus level, zero-shot

Micro-averaged over 22 documents, matching DISRPT's own methodology:

| | precision | recall | F1 |
|---|---|---|---|
| This pipeline (dev, zero-shot) | 0.544 | 0.711 | 0.616 |

WindowDiff and Boundary Similarity, corpus level. WindowDiff 0.3012, boundary similarity 0.5215.

Alignment failures: 0 of 22.

### 4.2 Against a fine-tuned system

| | precision | recall | F1 |
|---|---|---|---|
| DisCut, DISRPT 2023 (test, fine-tuned) | 94.95 | 93.98 | 94.46 |
| This pipeline (dev, zero-shot) | 54.4 | 71.1 | 61.6 |

**This is not a controlled comparison** and is given only for orientation. The
two figures differ in two respects simultaneously: split (test vs. dev) and
approach (fine-tuned on the corpus's training data vs. zero-shot prompting). No
inference about the size of either effect can be drawn from the difference.

A run on the test split is deferred until the prompt is frozen, so that the test
data is not consumed during development.

### 4.3 Error profile

Recall exceeds precision (0.711 vs. 0.544): the model proposes more boundaries
than the reference contains, and a substantial proportion of them are not
reference boundaries. The model over-segments relative to the RST-DT EDU
granularity used by GUM.

Per-genre, zero-shot (micro-averaged, 2 documents per genre):

| genre | precision | recall | F1 |
|---|---|---|---|
| voyage | 0.902 | 0.758 | 0.824 |
| conversation | 0.679 | 0.935 | 0.787 |
| whow | 0.663 | 0.859 | 0.748 |
| news | 0.557 | 0.765 | 0.645 |
| vlog | 0.520 | 0.810 | 0.633 |
| academic | 0.703 | 0.534 | 0.607 |
| textbook | 0.485 | 0.609 | 0.540 |
| fiction | 0.412 | 0.695 | 0.517 |
| interview | 0.445 | 0.559 | 0.495 |
| speech | 0.427 | 0.516 | 0.467 |
| bio | 0.337 | 0.500 | 0.403 |

Eleven genres rather than twelve: `reddit` was removed with its two masked
documents. The spread is wide — F1 ranges from 0.403 to 0.824 — and recall
exceeds precision in nine of eleven genres, consistent with the corpus-level
over-segmentation. The two exceptions, `academic` and `voyage`, are the two
most edited registers in the set.

### 4.4 Few-shot: negative result

**Hypothesis.** The gap is caused by the model not knowing the corpus's
annotation convention — where exactly a boundary falls at a relative clause, an
apposition, a list item. Worked examples should convey this faster than a verbal
description.

**Design.** Three reference-annotated excerpts from the **training** split were
added to the prompt as worked examples. Everything else was held constant: same
model, same parsing, same metrics, same 22 documents, separate cache.

**Result.** The hypothesis is not supported.

| | precision | recall | F1 |
|---|---|---|---|
| zero-shot | 0.544 | 0.711 | 0.616 |
| few-shot | 0.477 | 0.713 | 0.572 |
| delta | −0.067 | +0.003 | −0.044 |

Recall is flat; precision falls by 6.7 points. The examples shift the model
toward proposing more boundaries without those boundaries being correct.

**Sensitivity check.** One document, `GUM_conversation_grounded`, suffered a
generation collapse under the few-shot prompt (§4.5) that is unrelated to the
few-shot effect itself. Recomputed over the remaining 21 documents:

| | precision | recall | F1 |
|---|---|---|---|
| zero-shot | 0.532 | 0.690 | 0.601 |
| few-shot | 0.494 | 0.689 | 0.576 |
| delta | −0.038 | −0.000 | −0.025 |

The collapsed document accounts for roughly half the precision and F1 damage
(−0.067 → −0.038; −0.044 → −0.025). A drop persists across the other 21
documents, so the corpus figure is not an artefact of that single failure. Both
are reported; the 21-document delta is the better estimate of the few-shot
effect proper.

**Direction is not consistent across documents.** Of the 21 documents,
precision falls on 12 and rises on 9 — a sign test gives a two-sided p of 0.66,
which is indistinguishable from chance. The negative corpus-level delta comes
not from a general downward shift but from an asymmetry in magnitude: among
documents where precision falls, the mean drop is 0.149; among those where it
rises, the mean gain is 0.076. Micro-averaging, which weights documents by
boundary count rather than equally, compounds this.

| | precision delta |
|---|---|
| `GUM_interview_gaming` | −0.420 |
| `GUM_academic_exposure` | −0.259 |
| `GUM_voyage_coron` | −0.198 |
| `GUM_voyage_athens` | −0.167 |
| `GUM_conversation_risk` | −0.162 |
| … | |
| `GUM_bio_byron` | +0.097 |
| `GUM_whow_joke` | +0.142 |
| `GUM_fiction_beast` | +0.199 |

Median delta across the 21 documents is −0.035, mean −0.052.

So the accurate statement is narrower than the corpus figure suggests:
few-shot prompting harms a subset of documents substantially and helps another
subset moderately, and the aggregate is negative. What distinguishes the two
subsets is not established here. Since each document was sampled once under
default, uncontrolled sampling (§2), part of the spread may be sampling
variance rather than a property of the documents. **This is now partly
resolved — see §4.6:** the resampling test finds the "helped" subset
replicates in direction on all 4 documents tested, while the "harmed" subset
only partly replicates (2 of 4 tested documents keep a real decline; 2 show it
was mostly noise).

**Interpretation.** The gap is not primarily attributable to ignorance of the
annotation convention. Examples move the model's threshold for proposing a
boundary without improving its discrimination between boundary and non-boundary
positions.

**Mechanism.** The boundaries few-shot adds and zero-shot does not, examined on
the same documents and tokens across `GUM_bio_emperor`, `GUM_interview_gaming`,
`GUM_vlog_portland`, `GUM_voyage_athens` and `GUM_voyage_coron`, cluster
overwhelmingly on subject pronouns (*I*, *he*, *she*, *we*, *it*, *this*),
coordinators and subordinators (*and*, *but*, *that*, *in*), and commas.

This mirrors the three worked examples, which do split at a complementizer or
subordinator introducing a genuine new clause. Each individual split in the
examples is correct. A candidate account is that with only three short
(~50-token) examples, the model generalises the surface trigger — *and* /
*that* / subject pronoun → split — rather than the underlying rule of
full-clause coordination. Zero-shot, working from the prose instructions alone,
shows no such token-triggered pattern; its over-segmentation is milder and
untargeted.

This account is not established. If the mechanism operated uniformly, precision
should fall on most documents, and it does not (12 of 21). Either the mechanism
is conditional on properties of the text that have not been identified, or part
of the variation is sampling noise. The lexical clustering of the added
boundaries is real and was observed directly; the inference from it to a general
mechanism is not yet supported.

The predicted-to-reference boundary ratio rises corpus-wide from 1.31× to
1.50×, with the largest individual jumps on `GUM_conversation_grounded`
(1.41× → 2.46×), `GUM_bio_emperor` (1.33× → 2.09×), `GUM_interview_gaming`
(1.01× → 1.71×) and `GUM_vlog_portland` (1.34× → 1.89×).

An alternative explanation — that the examples simply demonstrated finer
segmentation — is not supported: their EDU density (11.40, 7.00 and 7.14
tokens per EDU) is not unusually fine against the dev-split average of 7.78.

**Non-uniformity across genres.** The effect is not in one direction, which
argues against any single clean account:

| genre | P zero | P few | R zero | R few | F1 zero | F1 few | ΔF1 |
|---|---|---|---|---|---|---|---|
| conversation | 0.679 | 0.448 | 0.935 | 0.954 | 0.787 | 0.610 | −0.177 |
| voyage | 0.902 | 0.723 | 0.758 | 0.732 | 0.824 | 0.728 | −0.096 |
| interview | 0.445 | 0.353 | 0.559 | 0.532 | 0.495 | 0.425 | −0.071 |
| bio | 0.337 | 0.285 | 0.500 | 0.466 | 0.403 | 0.353 | −0.049 |
| news | 0.557 | 0.486 | 0.765 | 0.784 | 0.645 | 0.600 | −0.044 |
| vlog | 0.520 | 0.448 | 0.810 | 0.878 | 0.633 | 0.593 | −0.040 |
| speech | 0.427 | 0.404 | 0.516 | 0.484 | 0.467 | 0.440 | −0.027 |
| academic | 0.703 | 0.603 | 0.534 | 0.574 | 0.607 | 0.588 | −0.019 |
| whow | 0.663 | 0.692 | 0.859 | 0.845 | 0.748 | 0.761 | +0.013 |
| textbook | 0.485 | 0.562 | 0.609 | 0.562 | 0.540 | 0.562 | +0.022 |
| fiction | 0.412 | 0.535 | 0.695 | 0.708 | 0.517 | 0.610 | +0.092 |

The columns matter as much as the deltas. Where few-shot harms a genre it does
so by lowering precision while recall holds or rises — `conversation`
(P 0.679 → 0.448, R 0.935 → 0.954) and `vlog` (P 0.520 → 0.448, R 0.810 →
0.878) are the clearest cases: the same boundaries are found, plus a good many
spurious ones. But `fiction`, the one genre that gains substantially, moves in
the opposite manner (P 0.412 → 0.535, R 0.695 → 0.708): there the examples
appear to suppress spurious boundaries rather than add them. A single mechanism
does not obviously produce both patterns.

`conversation` is the most affected genre and is also the only spoken genre in
this split, at two documents — one of which is the collapsed document of §4.5,
so this genre figure rests on very little. The mechanism above offers a
candidate account:
the density of *and*, pronouns and commas per clause is far higher in disfluent
speech, and a far larger share of those tokens are not clause boundaries there
— backchannels, restarts, coordinated NPs, false starts — than in the three
worked examples, all of which are edited or prepared registers (academic prose,
a scripted-sounding monologue, fiction narrative) rather than spontaneous
multi-party dialogue. This is recorded as an observation to be tested in phase
2, not as a finding.

Zero-shot is retained as the baseline configuration for subsequent phases.

### 4.5 Generation collapse on a long document

`GUM_conversation_grounded` (1,247 tokens) shows a failure mode distinct from
the few-shot effect. From token 1088 to the end of the document — the final 13%
— the model marks every token as a boundary, including bare punctuation (`.`,
`?`, `,`) as EDU starts, which is nonsensical under the stated guidelines. It
predicts 578 boundaries against 235 in the reference (2.46×), versus 1.41× for
zero-shot on the identical document, which shows no comparable run.

The likely interaction is prompt length with output length: the few-shot prompt
adds roughly 150 tokens of worked examples, and on a long document requiring a
long structured list as output, the model appears to stop tracking clause
boundaries partway through and default to enumerating every remaining index.

This is reported separately rather than folded into the few-shot result,
because it concerns generation quality rather than the effect under test. It
is, however, a practical finding in its own right: long prompt plus long
structured output raises the risk of this degradation, and any pipeline of this
shape should check for runs of consecutive predicted boundaries rather than
trusting the aggregate score.

**Resolved by resampling (§4.6): the collapse is real and recurring, not a
single unlucky draw, but it is stochastic rather than deterministic.** Drawing
5 independent few-shot samples of this document, 2 collapsed (trailing runs of
160 and 115 tokens marked as boundaries) and 3 did not; across 5 independent
zero-shot samples of the same document, none collapsed. So the few-shot prompt
specifically raises the risk of this failure mode on this document — roughly a
40% rate here, zero in the zero-shot condition — without making it certain.
One consequence: on the 3 few-shot samples that didn't collapse, precision
(0.52-0.73) was competitive with or better than zero-shot's mean (0.63) on
this same document. The large negative delta originally reported for
`GUM_conversation_grounded` was therefore driven almost entirely by the two
collapsed draws, not by a general degradation in segmentation judgment on this
text. Whether the same collapse occurs on other long documents, and whether
40% is representative or specific to this document's length/register, is
still untested.

### 4.6 Resampling test: is the harmed/helped split real, or noise?

Deferred sampling-temperature control (§2) forced a different design than
originally planned in an earlier draft of §7: instead of comparing
`temperature=0` against `temperature=1.0` on resampled documents, this draws 5
independent samples per document per condition under whatever default,
uncontrolled sampling the API applies — variance is measured by repetition,
not eliminated by pinning.

**Documents.** The 4 with the largest few-shot precision decline
(`GUM_interview_gaming`, `GUM_conversation_grounded`, `GUM_academic_exposure`,
`GUM_voyage_coron`) and the 4 with the largest gain (`GUM_fiction_beast`,
`GUM_whow_joke`, `GUM_bio_byron`, `GUM_textbook_governments`), from the §4.4
per-document table. Sample 0 in each condition reuses the single cached run
already analysed above; samples 1-4 are fresh, independent calls. 4 of the 80
attempted fresh-plus-cached samples failed to parse (malformed JSON, a missing
comma) and are excluded, not silently dropped — a real ~5% base failure rate
that a single draw per document could not surface. Full detail in
`results/eng.rst.gum_dev_resampling_per_sample.csv` and `..._summary.csv`;
failures in `..._resampling_failures.csv`.

Precision, mean across samples with [min-max] range:

| doc_id | genre | zero-shot | few-shot | original single-draw delta |
|---|---|---|---|---|
| GUM_interview_gaming | interview | 0.593 [0.458-0.941] | 0.463 [0.387-0.521] | −0.420 |
| GUM_conversation_grounded | conversation | 0.630 [0.573-0.657] | 0.532 [0.372-0.726] | −0.264 |
| GUM_academic_exposure | academic | 0.558 [0.395-0.808] | 0.535 [0.455-0.586] | −0.259 |
| GUM_voyage_coron | voyage | 0.746 [0.629-0.978] | 0.757 [0.690-0.870] | −0.198 |
| GUM_fiction_beast | fiction | 0.512 [0.366-0.619] | 0.573 [0.512-0.665] | +0.199 |
| GUM_whow_joke | whow | 0.650 [0.513-0.735] | 0.697 [0.636-0.748] | +0.142 |
| GUM_bio_byron | bio | 0.553 [0.480-0.622] | 0.665 [0.587-0.705] | +0.097 |
| GUM_textbook_governments | textbook | 0.607 [0.578-0.643] | 0.662 [0.603-0.696] | +0.087 |

**The gain side replicates; the decline side only half does.**

- All 4 "gain" documents keep the same sign under resampling, usually at a
  smaller magnitude than the single-draw delta (e.g. `GUM_bio_byron`'s mean
  gain is +0.112, close to the original +0.097, and its ranges barely
  overlap — the most robust effect of the eight). Few-shot helping these four
  written, non-dialogue genres looks like a real, if modest, effect rather
  than noise.
- 2 of 4 "decline" documents mostly evaporate: `GUM_academic_exposure`'s means
  converge (0.558 vs 0.535) inside heavily overlapping ranges, and
  `GUM_voyage_coron`'s reverses sign entirely (0.746 vs 0.757). Both original
  deltas were driven largely by an unusually high single zero-shot draw
  (0.808 and 0.978 respectively sit at the top of each range), not by
  few-shot doing something wrong.
- `GUM_interview_gaming` keeps a real, consistent decline (0.593 vs 0.463
  mean), though smaller than the original −0.420 — the single zero-shot draw
  of 0.941 was itself the high outlier in a wide [0.458-0.941] range.
- `GUM_conversation_grounded`'s decline is real on average but is explained
  by §4.5's collapse, not a general precision loss: see there.

**Reading for the corpus-level result (§4.4).** This does not overturn the
corpus-level few-shot precision drop, which pools far more boundary decisions
than 8 resampled documents can speak to. What it changes is the
document-level narrative: roughly half of the specific documents flagged as
"harmed" in the original single-draw table were not reliably harmed, while
the "helped" documents were reliably helped. The corpus aggregate's negative
sign is not in question here; which documents are responsible for it is
better supported for some than others.

---

## 5. Errors found, and what they imply

Three bugs produced plausible but meaningless numbers, and each was caught by a
different check. They are recorded because they bear on how much confidence any
single reported score deserves.

**Masked text scored as segmentation.** The two Reddit documents scored F1 0.074
in the first full run. The model had been asked to find semantic boundaries in
strings of underscores. Aggregated into the corpus figure, this depressed micro
F1 from 0.616 to 0.585 — a difference small enough to look like an ordinary
result. It was visible only in the per-genre breakdown and confirmed only by
opening the source file.

**Multiword-token rows counted as tokens.** CoNLL-U range rows inflated token
counts, shifting every mass computation. Detected by comparing corpus statistics
against the published figures.

**Extended thinking consuming the output budget.** On some calls the entire
token budget was spent on reasoning, returning no text (`stop_reason:
max_tokens`, zero text output), causing 18 of 24 documents to fail alignment on
the first full run. Detected by the alignment assertion, which is why that
assertion is unconditional. Cache validity was subsequently tightened so that a
cached response must parse and align before being reused.

**Generation collapse producing a plausible aggregate.** The few-shot precision
drop initially appeared to be a single uniform effect. Roughly half of it came
from one document undergoing the degenerate output described in §4.5. Detected
only by inspecting per-document ratios of predicted to reference boundaries.

**Aggregation over mismatched document sets.** During the few-shot comparison, a
period existed in which corpus aggregates compared 22 zero-shot documents
against 20 few-shot documents. Aggregates are now restricted to the intersection
of successfully scored documents, with an explicit note in the report when this
applies.

The general point: with the exception of the last, none of these produced an
error. All produced a number.

---

## 6. Limitations

- **Single sample per document under default, uncontrolled sampling, for 14 of
  22 documents.** The corpus-level and per-genre figures in §4.1-§4.4 pool
  thousands of boundary decisions across 22 documents and are correspondingly
  less sensitive to any individual draw. §4.6 resampled the 8 documents with
  the largest per-document deltas 5 times each and found roughly half of the
  flagged "harmed" documents (2 of 4) did not reliably replicate, while all 4
  "helped" documents did — so per-document readings for the other 14
  documents, never resampled, should still be treated as indicative rather
  than established.
- Sampling cannot be pinned at all through this API/SDK (§2) — there is no
  `temperature=0` available to make any of this reproducible byte-for-byte.
  Only repetition (§4.6) characterizes variance; it does not eliminate it.
- Evaluated on the development split; the test split is deliberately unused.
- A single model, single prompt formulation, single corpus.
- Written text only. No claim about spoken language is made or supported here.
- The comparison against DisCut is uncontrolled in two respects simultaneously.
- No human ceiling. GUM does not provide multiple independent annotations of the
  same documents, so it cannot be established whether the observed model–human
  gap is large or small relative to human–human disagreement. This is the
  central limitation of phase 1 and the reason phase 3 exists.

---

## 7. Next

**Phase 2 — Santa Barbara Corpus.** Spontaneous conversational American
English, transcribed at the level of intonation units and time-aligned to audio.
The same pipeline, different data. Two questions: does performance drop on
spoken transcripts relative to written text, and does the few-shot penalty
observed in the `conversation` genre reproduce on a larger spoken sample.

**Resampling test — done, see §4.6.** The 4 documents with the largest
few-shot precision decline and the 4 with the largest gain were each resampled
5 times under default (uncontrolled) sampling, since `temperature` cannot be
pinned through this API/SDK. Result: the "helped" side replicates in direction
on all 4 documents; the "harmed" side only partly does (2 of 4 hold up,
`GUM_interview_gaming` and, via the collapse mechanism, `GUM_conversation_grounded`;
2 of 4 — `GUM_academic_exposure`, `GUM_voyage_coron` — were mostly a single
lucky/unlucky draw). The remaining 14 documents were never resampled and this
should not be assumed to generalize to them.

Phase 2 cannot run at a pinned temperature either, for the same reason (§2).
Any comparison against phase 1 numbers should treat both as single- or
few-sample draws under uncontrolled sampling, not as reproducible baselines —
resampling, not pinning, is the available tool for characterizing variance in
either phase.

An open question deferred from phase 1: whether swapping one worked example for
a spontaneous-dialogue excerpt closes the conversation-genre precision gap. If
it does, the cause is register-representativeness of the examples rather than
few-shot prompting as such. This is not pursued here, since the negative result
is already informative and prompt optimisation is not the object of the study.

Note that atomic units differ between phases: token-based scores and
intonation-unit-based scores are not comparable, since WindowDiff's window size
derives from mean segment length in atomic units. This must be stated wherever
figures from different phases appear together.

**Phase 3 — CID.** French, audio, and inter-annotator agreement measures from
the original annotation campaign. Access pending. This is the only phase in
which a human ceiling can be established.

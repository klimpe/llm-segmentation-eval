# Phase 2 pilot: SBC039

Counts and scores only -- no transcript text. **The target throughout is intonation-unit (prosodic) segmentation, not discourse-unit segmentation** (CLAUDE.md's phase 2 framing): SBCSAE has no discourse annotation, only IUs.

One file (SBC039) x 8 windows x condition {A, B} x n_samples=5, zero-shot. Model and settings: see reports/phase2_llm_design.md S7 (same as phase 1).

**This is a single-document pilot. One file supports no conclusion about A vs B, or about this model's segmentation ability in general** -- it validates the pipeline (rendering, scoring, windowing, degenerate detection) end to end on real model output before any scaling decision.

n_tokens: 4347, n_windows: 8

## Condition A

- Window-level draws: 40, failed to parse/align: 0 (0.0%)
- Turn-initial indices dropped, per sample: [277, 359, 314, 275, 326]
- All samples produced a complete whole-file hypothesis.

### Degenerate-output flags (runs of consecutive predicted intonation-unit, not discourse-unit, boundaries; run > 11; per sbcsae_degenerate_threshold.review_policy)

None.

### Whole-file scores per sample (intonation units, not discourse units; within-turn is the headline; precision/recall/boundary-count ratio/Boundary Similarity from the same unchanged metrics.py functions score_document already called)

| sample | scope | precision | recall | F1 | hyp/ref boundary ratio | Boundary Similarity | WindowDiff |
|---|---|---|---|---|---|---|---|
| 0 | all_boundaries | 0.5414 | 0.8108 | 0.6492 | 1.4976 | 0.5646 | 0.3841 |
| 0 | **within_turn** | 0.3881 | 0.6971 | 0.4986 | 1.7963 | 0.4260 | 0.4857 |
| 1 | all_boundaries | 0.5401 | 0.8124 | 0.6489 | 1.5041 | 0.5650 | 0.3809 |
| 1 | **within_turn** | 0.3873 | 0.6997 | 0.4986 | 1.8068 | 0.4268 | 0.4850 |
| 2 | all_boundaries | 0.5449 | 0.8214 | 0.6552 | 1.5073 | 0.5628 | 0.3793 |
| 2 | **within_turn** | 0.3941 | 0.7141 | 0.5079 | 1.8120 | 0.4250 | 0.4864 |
| 3 | all_boundaries | 0.5665 | 0.8091 | 0.6664 | 1.4282 | 0.5797 | 0.3634 |
| 3 | **within_turn** | 0.4121 | 0.6945 | 0.5173 | 1.6854 | 0.4394 | 0.4560 |
| 4 | all_boundaries | 0.5886 | 0.7887 | 0.6741 | 1.3401 | 0.5960 | 0.3330 |
| 4 | **within_turn** | 0.4286 | 0.6619 | 0.5203 | 1.5444 | 0.4519 | 0.4358 |

- all_boundaries precision: mean 0.5563, range [0.5401, 0.5886] (n=5)
- all_boundaries recall: mean 0.8085, range [0.7887, 0.8214] (n=5)
- all_boundaries f1: mean 0.6588, range [0.6489, 0.6741] (n=5)
- all_boundaries boundary_count_ratio: mean 1.4555, range [1.3401, 1.5073] (n=5)
- all_boundaries boundary_similarity: mean 0.5736, range [0.5628, 0.5960] (n=5)
- within_turn (headline) precision: mean 0.4020, range [0.3873, 0.4286] (n=5)
- within_turn (headline) recall: mean 0.6935, range [0.6619, 0.7141] (n=5)
- within_turn (headline) f1: mean 0.5085, range [0.4986, 0.5203] (n=5)
- within_turn (headline) boundary_count_ratio: mean 1.7290, range [1.5444, 1.8120] (n=5)
- within_turn (headline) boundary_similarity: mean 0.4338, range [0.4250, 0.4519] (n=5)
- all_boundaries and within_turn are not comparable to each other (different effective segment lengths -- sbcsae_scoring.NON_COMPARABILITY_NOTE).

### Auto-flagged draws (run > 22): excluded from every aggregate above, reported on their own (CLAUDE.md, "Degenerate output": report affected draws separately rather than folding them into the aggregate)

No sample had an auto-flagged (run > 22) window this condition.

### Offset distribution, within-turn boundaries (signed distance from each hypothesis boundary to the nearest reference boundary; pooled over all non-flagged, successful window draws; 0 = exact match)

| offset | -3 | -2 | -1 | 0 | +1 | +2 | +3 | beyond +-3 | total |
|---|---|---|---|---|---|---|---|---|---|
| n | 340 | 436 | 647 | 2656 | 913 | 535 | 259 | 836 | 6622 |

### Per-window scores by window position (intonation units, not discourse units; mean over samples where that window's own draw succeeded and was not auto-flagged -- window scope only, independent of whether other windows in the same sample failed). Reference covariates (mean within-turn segment length, speaker changes, overlap-bracket density) are condition-independent properties of this window's own reference, shown alongside the scores they plausibly explain -- not a claim that score changes by window position are a drift or trend over the document, since windows are scored independently and differ in reference difficulty, not in position per se.

| window | score range (words) | ref mean seg length | speaker changes | overlap-bracket density /100w | n samples | within_turn F1 mean [range] | all_boundaries F1 mean [range] |
|---|---|---|---|---|---|---|---|
| 0 | 1-600 | 4.41 | 55 | 6.83 | 5 | 0.4112 [0.3577, 0.4639] | 0.5500 [0.5052, 0.6014] |
| 1 | 601-1200 | 5.50 | 64 | 8.83 | 5 | 0.5862 [0.5221, 0.6343] | 0.7205 [0.6750, 0.7525] |
| 2 | 1201-1800 | 5.56 | 51 | 6.67 | 5 | 0.5064 [0.4123, 0.5641] | 0.6335 [0.5527, 0.6827] |
| 3 | 1801-2400 | 5.94 | 39 | 6.50 | 5 | 0.6337 [0.5887, 0.6833] | 0.7168 [0.6778, 0.7610] |
| 4 | 2401-3000 | 5.31 | 66 | 11.00 | 5 | 0.6215 [0.6006, 0.6553] | 0.7340 [0.7165, 0.7624] |
| 5 | 3001-3600 | 7.59 | 97 | 18.00 | 5 | 0.4260 [0.3909, 0.4726] | 0.6914 [0.6713, 0.7100] |
| 6 | 3601-4200 | 5.31 | 61 | 8.83 | 5 | 0.4166 [0.3491, 0.4925] | 0.5812 [0.5217, 0.6513] |
| 7 | 4201-4347 | 11.31 | 27 | 23.81 | 5 | 0.4388 [0.3636, 0.5217] | 0.7223 [0.6500, 0.7826] |

### Within-turn F1 by position inside the window core (pooled/micro-averaged tp/fp/fn over all non-flagged, successful window draws and all samples -- not a mean of per-window F1s)

| word range in core | precision | recall | F1 | tp | fp | fn |
|---|---|---|---|---|---|---|
| 1-200 | 0.3927 | 0.6555 | 0.4912 | 780 | 1206 | 410 |
| 201-400 | 0.4105 | 0.7068 | 0.5193 | 887 | 1274 | 368 |
| 401-600 | 0.3989 | 0.7164 | 0.5125 | 985 | 1484 | 390 |

## Condition B

- Window-level draws: 40, failed to parse/align: 0 (0.0%)
- Turn-initial indices dropped, per sample: [278, 300, 268, 244, 213]
- All samples produced a complete whole-file hypothesis.

### Degenerate-output flags (runs of consecutive predicted intonation-unit, not discourse-unit, boundaries; run > 11; per sbcsae_degenerate_threshold.review_policy)

| sample | window | run length | auto-flagged (>22) | needs manual reading |
|---|---|---|---|---|
| 0 | 1 | 15 | False | True |
| 3 | 5 | 26 | True | True |

Both read in full (indices, rendered text, reference boundaries):
**enumeration, not a plausible segmentation, in both cases** -- a new
intonation unit marked at literally every word for 15 (sample 0/window
1) and 26 (sample 3/window 5) consecutive words, matching only 3-4 real
reference boundaries over each span (reports/phase2_llm_design.md S8).
Only the run-15 draw stays in the aggregates below (11 < 15 <= 22: flagged
for manual reading, not auto-flagged); the run-26 draw (>22) is excluded
and reported on its own, in the "Auto-flagged draws" table below.

### Whole-file scores per sample (intonation units, not discourse units; within-turn is the headline; precision/recall/boundary-count ratio/Boundary Similarity from the same unchanged metrics.py functions score_document already called)

| sample | scope | precision | recall | F1 | hyp/ref boundary ratio | Boundary Similarity | WindowDiff |
|---|---|---|---|---|---|---|---|
| 0 | all_boundaries | 0.5552 | 0.7920 | 0.6528 | 1.4266 | 0.5417 | 0.3754 |
| 0 | **within_turn** | 0.3964 | 0.6671 | 0.4973 | 1.6828 | 0.3947 | 0.4820 |
| 1 | all_boundaries | 0.5857 | 0.7724 | 0.6662 | 1.3189 | 0.5640 | 0.3413 |
| 1 | **within_turn** | 0.4209 | 0.6358 | 0.5065 | 1.5104 | 0.4122 | 0.4445 |
| 2 | all_boundaries | 0.6026 | 0.8051 | 0.6892 | 1.3361 | 0.5733 | 0.3360 |
| 2 | **within_turn** | 0.4474 | 0.6880 | 0.5422 | 1.5379 | 0.4262 | 0.4346 |
| 4 | all_boundaries | 0.6030 | 0.7333 | 0.6618 | 1.2162 | 0.5623 | 0.3360 |
| 4 | **within_turn** | 0.4258 | 0.5731 | 0.4886 | 1.3460 | 0.4002 | 0.4365 |

- all_boundaries precision: mean 0.5866, range [0.5552, 0.6030] (n=4)
- all_boundaries recall: mean 0.7757, range [0.7333, 0.8051] (n=4)
- all_boundaries f1: mean 0.6675, range [0.6528, 0.6892] (n=4)
- all_boundaries boundary_count_ratio: mean 1.3244, range [1.2162, 1.4266] (n=4)
- all_boundaries boundary_similarity: mean 0.5603, range [0.5417, 0.5733] (n=4)
- within_turn (headline) precision: mean 0.4226, range [0.3964, 0.4474] (n=4)
- within_turn (headline) recall: mean 0.6410, range [0.5731, 0.6880] (n=4)
- within_turn (headline) f1: mean 0.5086, range [0.4886, 0.5422] (n=4)
- within_turn (headline) boundary_count_ratio: mean 1.5193, range [1.3460, 1.6828] (n=4)
- within_turn (headline) boundary_similarity: mean 0.4083, range [0.3947, 0.4262] (n=4)
- all_boundaries and within_turn are not comparable to each other (different effective segment lengths -- sbcsae_scoring.NON_COMPARABILITY_NOTE).

### Auto-flagged draws (run > 22): excluded from every aggregate above, reported on their own (CLAUDE.md, "Degenerate output": report affected draws separately rather than folding them into the aggregate)

| sample | scope | precision | recall | F1 | hyp/ref boundary ratio | Boundary Similarity |
|---|---|---|---|---|---|---|
| 3 | all_boundaries | 0.5570 | 0.8091 | 0.6598 | 1.4527 | 0.5524 |
| 3 | **within_turn** | 0.4027 | 0.6945 | 0.5098 | 1.7245 | 0.4094 |

### Offset distribution, within-turn boundaries (signed distance from each hypothesis boundary to the nearest reference boundary; pooled over all non-flagged, successful window draws; 0 = exact match)

| offset | -3 | -2 | -1 | 0 | +1 | +2 | +3 | beyond +-3 | total |
|---|---|---|---|---|---|---|---|---|---|
| n | 194 | 298 | 1112 | 2442 | 699 | 273 | 171 | 595 | 5784 |

#### The -1 offset asymmetry (1,112 at -1 vs 699 at +1; condition A is nearly symmetric): does it sit next to cues?

`sbcsae_cue_adjacency.py`, reading only these cached draws (no model
calls), asks the direct, hypothesis-side question for condition B only
(dropped for A: it renders no cues at all, so the answer there is 0% by
construction, not a comparison worth a column): for the actual word the
model NAMED as a new unit's start, is a cue rendered immediately AFTER
that named word? If the model systematically names the word before a
cue instead of the word after it, the named word itself should be
followed by a cue far more often than the document's own background
rate -- the share of ALL within-turn-eligible word positions (every word
except each turn's own first word) with a cue immediately after them:
12.7% (493/3,886) on this file.

| offset | -3 | -2 | -1 | 0 | +1 | +2 | +3 | beyond |
|---|---|---|---|---|---|---|---|---|
| share, named word followed by a cue | 25.8% | 14.8% | **75.4%** | 20.7% | 18.6% | 19.8% | 31.0% | 19.0% |
| vs. base rate (12.7%) | 2.03x | 1.16x | **5.95x** | 1.63x | 1.47x | 1.56x | 2.44x | 1.50x |

**Yes, offset -1 sits next to cues, far above the background rate**:
75.4% of offset -1 hypotheses name a word immediately followed by a
cue -- 5.95x the base rate, well clear of every other bucket (next
highest 2.44x, at +3). This is the correlation the "the model names the
word before a cue instead of the word after it" theory predicts, and it
is stronger under this direct, hypothesis-side check than the earlier,
indirect reference-side version of this analysis. **But a strong
correlation is not the same as a confirmed mechanism** -- see the rerun
below, which tested the fix this correlation motivated and did not
confirm it.

### Per-window scores by window position (intonation units, not discourse units; mean over samples where that window's own draw succeeded and was not auto-flagged -- window scope only, independent of whether other windows in the same sample failed). Reference covariates (mean within-turn segment length, speaker changes, overlap-bracket density) are condition-independent properties of this window's own reference, shown alongside the scores they plausibly explain -- not a claim that score changes by window position are a drift or trend over the document, since windows are scored independently and differ in reference difficulty, not in position per se.

| window | score range (words) | ref mean seg length | speaker changes | overlap-bracket density /100w | n samples | within_turn F1 mean [range] | all_boundaries F1 mean [range] |
|---|---|---|---|---|---|---|---|
| 0 | 1-600 | 4.41 | 55 | 6.83 | 5 | 0.4990 [0.4064, 0.5879] | 0.6397 [0.5873, 0.6950] |
| 1 | 601-1200 | 5.50 | 64 | 8.83 | 5 | 0.5451 [0.4775, 0.6137] | 0.6700 [0.5989, 0.7358] |
| 2 | 1201-1800 | 5.56 | 51 | 6.67 | 5 | 0.5745 [0.5506, 0.5979] | 0.6887 [0.6603, 0.7050] |
| 3 | 1801-2400 | 5.94 | 39 | 6.50 | 5 | 0.5577 [0.5425, 0.5773] | 0.6546 [0.6354, 0.6667] |
| 4 | 2401-3000 | 5.31 | 66 | 11.00 | 5 | 0.5638 [0.5378, 0.5887] | 0.7140 [0.7021, 0.7254] |
| 5 | 3001-3600 | 7.59 | 97 | 18.00 | 4 | 0.4192 [0.3483, 0.4730] | 0.7010 [0.6833, 0.7246] |
| 6 | 3601-4200 | 5.31 | 61 | 8.83 | 5 | 0.3843 [0.3444, 0.4464] | 0.5773 [0.5330, 0.6366] |
| 7 | 4201-4347 | 11.31 | 27 | 23.81 | 5 | 0.4922 [0.3448, 0.6875] | 0.8177 [0.7711, 0.8837] |

### Within-turn F1 by position inside the window core (pooled/micro-averaged tp/fp/fn over all non-flagged, successful window draws and all samples -- not a mean of per-window F1s)

| word range in core | precision | recall | F1 | tp | fp | fn |
|---|---|---|---|---|---|---|
| 1-200 | 0.3788 | 0.5735 | 0.4562 | 667 | 1094 | 496 |
| 201-400 | 0.4152 | 0.6013 | 0.4912 | 739 | 1041 | 490 |
| 401-600 | 0.4614 | 0.7622 | 0.5749 | 1029 | 1201 | 321 |

## Model vs. the cue rule: within-turn F1

The model's condition-B within-turn F1 on this pilot (mean 0.5086, table
above) sits **below** the cue rule's (reports/phase2_baselines.md; the
deterministic "boundary before a word preceded by a pause/breath" rule
of reports/phase2_llm_design.md S10) -- **0.51 on this one file for the
model vs. 0.60 as the cue rule's own whole-corpus (59-file) macro-mean**
(0.5692 on SBC039 itself, 0.5998 macro-mean across the corpus). These two
numbers are NOT the same kind of figure: the model's is a 5-sample pilot
on one file; the cue rule's is deterministic and evaluated whole-corpus,
because it involves no model call (reports/phase2_llm_design.md S10).
Read together, though, they say something plain: **in condition B, the
model does not exploit the prosodic cues it is shown as effectively as a
one-line rule that only checks for a pause or an in-breath before a
word.** Whatever the model is doing with condition B's cues, it is not
simply "place a boundary after every cue" -- if it were, it would match
or exceed the cue rule's own F1, not trail it.

## SBC039 rerun, condition B only, clarified prompt (reports/phase2_llm_design.md S11)

n_samples=5, same file, same windows, into a separate cache
(`llm_output_sbcsae_rerun_b/`) -- the original B cache is untouched, so
both runs remain independently reproducible. **This is a second 5-sample
pilot on the same one file, not a corpus-scale result**; the same
"supports no conclusion about A vs B, or about this model's segmentation
ability in general" caveat from the top of this report applies to the
comparison below just as much as to the original run.

| | original B | rerun B (clarified prompt) |
|---|---|---|
| window draws failed to parse/align | 0 of 40 | 0 of 40 |
| samples with a run > 11 (needs manual reading) | 2 (1 auto-flagged, >22) | 0 |
| samples in aggregate (auto-flagged excluded) | 4 | 5 |
| within_turn precision, mean [range] | 0.4226 [0.3964, 0.4474] | 0.4600 [0.4387, 0.4824] |
| within_turn recall, mean [range] | 0.6410 [0.5731, 0.6880] | 0.6209 [0.5587, 0.6540] |
| within_turn F1, mean [range] | 0.5086 [0.4886, 0.5422] | 0.5278 [0.5062, 0.5446] |
| offset 0 (exact match), share of within-turn boundaries | 2442/5784 = 42.2% | 2378/5177 = 45.9% |
| offset -1, share | 1112/5784 = 19.2% | 1033/5177 = 20.0% |
| offset +1, share | 699/5784 = 12.1% | 516/5177 = 10.0% |
| -1 : +1 ratio | 1.59 | 2.00 |

**The indexing-ambiguity hypothesis is tested and rejected.** The
clarified wording did not reduce the -1 asymmetry it was written to
fix -- if anything, the -1:+1 ratio grew (1.59 -> 2.00), the wrong
direction for the theory. The within-turn F1 and exact-match-share
upticks are within sample noise, not evidence the fix worked: the
original run's own [0.4886, 0.5422] F1 range already brackets the
rerun's 0.5278 mean, the aggregate sample count changed too (n=4 -> n=5,
since no rerun draw crossed the degenerate-run threshold this time), and
CLAUDE.md already documents this exact failure mode from phase 1
("several document-level findings that did not survive resampling"). A
single 5-sample rerun on one file cannot distinguish "the fix helped a
little" from ordinary run-to-run variance, and the one number that
*would* have been unambiguous evidence for the theory -- the asymmetry
itself shrinking -- moved the wrong way.

This does not retract the correlation above (offset -1 genuinely sits
5.95x the base rate for a cue following the named word -- that finding
stands on its own, from cached draws, independent of this rerun). What
it rejects is the SPECIFIC causal story built on that correlation: that
the model already picks the right cue-marked boundary and merely reports
the wrong side of it, and that telling it which side to report would
fix the -1 mass. It does not. **The clarified wording is kept anyway**
-- it is unambiguous, costs nothing, and removes a real gap in the
prompt regardless of whether it explains this particular asymmetry --
but the asymmetry itself needs a different explanation. See below.

## Remaining explanation

A labeling ambiguity was rejected, not the correlation that motivated
it. What remains consistent with both the strong offset -1/cue
correlation and the failed causal test: **in condition B the model may
be placing its actual, intended boundary systematically one word earlier
than the reference specifically near cues** -- not misreporting which
side of a correctly-identified boundary to name, but genuinely deciding
the unit ends a word sooner than the transcriber did, converging on the
neighbourhood of the same cue-marked position from an earlier point in
the sequence. This differs from the rejected theory in a way that
predicts a different fix: a labeling confusion is fixed by clarifying
which word to report (tried, did not work); an early-decision tendency
is not, since the "wrong" word is genuinely the one the model decided
to mark, not a correct decision reported off-by-one. This would be
tested by a task variant where a labeling ambiguity is structurally
impossible -- e.g. asking the model to report each unit as a (start,
end) word-index pair rather than a single start position -- and checking
whether the reported END of the unit immediately before a cue-marked
boundary still lands one word early at a rate above baseline. If it
does, the boundary decision itself, not its reporting, is early; if the
asymmetry disappears under that representation, the current single-
position format is somehow reintroducing it some other way.


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


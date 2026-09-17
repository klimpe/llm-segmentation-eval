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

### Whole-file scores per sample (intonation units, not discourse units; within-turn is the headline)

| sample | all_boundaries F1 | all_boundaries WD | within_turn F1 (headline) | within_turn WD |
|---|---|---|---|---|
| 0 | 0.6492 | 0.3841 | **0.4986** | 0.4857 |
| 1 | 0.6489 | 0.3809 | **0.4986** | 0.4850 |
| 2 | 0.6552 | 0.3793 | **0.5079** | 0.4864 |
| 3 | 0.6664 | 0.3634 | **0.5173** | 0.4560 |
| 4 | 0.6741 | 0.3330 | **0.5203** | 0.4358 |

- all_boundaries F1: mean 0.6588, range [0.6489, 0.6741] (n=5)
- within_turn F1 (headline): mean 0.5085, range [0.4986, 0.5203] (n=5)
- all_boundaries and within_turn are not comparable to each other (different effective segment lengths -- sbcsae_scoring.NON_COMPARABILITY_NOTE).

### Per-window within_turn F1 and all_boundaries F1, by window position (intonation units, not discourse units; mean over samples where that window's own draw succeeded -- window scope only, independent of whether other windows in the same sample failed)

| window | score range (words) | n samples | within_turn F1 mean [range] | all_boundaries F1 mean [range] |
|---|---|---|---|---|
| 0 | 1-600 | 5 | 0.4112 [0.3577, 0.4639] | 0.5500 [0.5052, 0.6014] |
| 1 | 601-1200 | 5 | 0.5862 [0.5221, 0.6343] | 0.7205 [0.6750, 0.7525] |
| 2 | 1201-1800 | 5 | 0.5064 [0.4123, 0.5641] | 0.6335 [0.5527, 0.6827] |
| 3 | 1801-2400 | 5 | 0.6337 [0.5887, 0.6833] | 0.7168 [0.6778, 0.7610] |
| 4 | 2401-3000 | 5 | 0.6215 [0.6006, 0.6553] | 0.7340 [0.7165, 0.7624] |
| 5 | 3001-3600 | 5 | 0.4260 [0.3909, 0.4726] | 0.6914 [0.6713, 0.7100] |
| 6 | 3601-4200 | 5 | 0.4166 [0.3491, 0.4925] | 0.5812 [0.5217, 0.6513] |
| 7 | 4201-4347 | 5 | 0.4388 [0.3636, 0.5217] | 0.7223 [0.6500, 0.7826] |

## Condition B

- Window-level draws: 40, failed to parse/align: 0 (0.0%)
- Turn-initial indices dropped, per sample: [278, 300, 268, 244, 213]
- All samples produced a complete whole-file hypothesis.

### Degenerate-output flags (runs of consecutive predicted intonation-unit, not discourse-unit, boundaries; run > 11; per sbcsae_degenerate_threshold.review_policy)

| sample | window | run length | auto-flagged (>22) | needs manual reading |
|---|---|---|---|---|
| 0 | 1 | 15 | False | True |
| 3 | 5 | 26 | True | True |

### Whole-file scores per sample (intonation units, not discourse units; within-turn is the headline)

| sample | all_boundaries F1 | all_boundaries WD | within_turn F1 (headline) | within_turn WD |
|---|---|---|---|---|
| 0 | 0.6528 | 0.3754 | **0.4973** | 0.4820 |
| 1 | 0.6662 | 0.3413 | **0.5065** | 0.4445 |
| 2 | 0.6892 | 0.3360 | **0.5422** | 0.4346 |
| 3 | 0.6598 | 0.3652 | **0.5098** | 0.4616 |
| 4 | 0.6618 | 0.3360 | **0.4886** | 0.4365 |

- all_boundaries F1: mean 0.6660, range [0.6528, 0.6892] (n=5)
- within_turn F1 (headline): mean 0.5089, range [0.4886, 0.5422] (n=5)
- all_boundaries and within_turn are not comparable to each other (different effective segment lengths -- sbcsae_scoring.NON_COMPARABILITY_NOTE).

### Per-window within_turn F1 and all_boundaries F1, by window position (intonation units, not discourse units; mean over samples where that window's own draw succeeded -- window scope only, independent of whether other windows in the same sample failed)

| window | score range (words) | n samples | within_turn F1 mean [range] | all_boundaries F1 mean [range] |
|---|---|---|---|---|
| 0 | 1-600 | 5 | 0.4990 [0.4064, 0.5879] | 0.6397 [0.5873, 0.6950] |
| 1 | 601-1200 | 5 | 0.5451 [0.4775, 0.6137] | 0.6700 [0.5989, 0.7358] |
| 2 | 1201-1800 | 5 | 0.5745 [0.5506, 0.5979] | 0.6887 [0.6603, 0.7050] |
| 3 | 1801-2400 | 5 | 0.5577 [0.5425, 0.5773] | 0.6546 [0.6354, 0.6667] |
| 4 | 2401-3000 | 5 | 0.5638 [0.5378, 0.5887] | 0.7140 [0.7021, 0.7254] |
| 5 | 3001-3600 | 5 | 0.4142 [0.3483, 0.4730] | 0.6904 [0.6479, 0.7246] |
| 6 | 3601-4200 | 5 | 0.3843 [0.3444, 0.4464] | 0.5773 [0.5330, 0.6366] |
| 7 | 4201-4347 | 5 | 0.4922 [0.3448, 0.6875] | 0.8177 [0.7711, 0.8837] |


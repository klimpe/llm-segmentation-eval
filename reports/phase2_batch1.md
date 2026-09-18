# Phase 2 batch 1: 10 files across the corpus's word-count deciles

Counts and scores only -- no transcript text. **The target throughout is intonation-unit (prosodic) segmentation, not discourse-unit segmentation** (CLAUDE.md's phase 2 framing): SBCSAE has no discourse annotation, only IUs.

10 files x 800/600 windows x condition {A, B} x n_samples=5, zero-shot, clarified prompt (reports/phase2_llm_design.md S11), same model and settings as the pilot. SBC039 is reported separately below: it already informed the prompt/threshold decisions the other 10 files did not, so it is not pooled into the batch's own aggregates.

Every figure below is read from reports/phase2_batch1_scores.csv, _offsets.csv, _degenerate.csv and _baselines.csv -- nothing here comes from an in-memory number those files don't also contain.

**Old rule (whole-corpus, run > 22) vs new rule (per-file, reports/phase2_llm_design.md S14), over the full 10-file batch's 760 window-draws: 28 flagged by the old rule vs 159 by the new one -- the old rule undercounts collapse by roughly 6x. Stated once, here; every table below reports collapse_rate/share_words_in_runs under the new rule only, and cites the old rule's own verdict per-draw only where relevant.**

## Batch selection

One file per decile of the 59-file (SBC037 excluded) word-count distribution -- decile targets at the 5th/15th/.../95th percentile (linear interpolation), nearest file by word count. No score, pilot result, or any other property entered this choice.

| doc_id | decile target | words | reference segments | speaker-change share | overlap/100w | pilot |
|---|---|---|---|---|---|---|
| SBC024 | 5% | 2574 | 778 | 0.3732 | 7.58 | False |
| SBC005 | 15% | 2853 | 732 | 0.3324 | 6.52 | False |
| SBC041 | 25% | 3075 | 932 | 0.2922 | 9.98 | False |
| SBC053 | 35% | 3629 | 847 | 0.2884 | 4.96 | False |
| SBC012 | 45% | 3897 | 1031 | 0.1748 | 2.77 | False |
| SBC045 | 55% | 4282 | 1087 | 0.2634 | 3.69 | False |
| SBC016 | 65% | 4590 | 1447 | 0.5353 | 19.22 | False |
| SBC014 | 75% | 4894 | 1147 | 0.2478 | 5.66 | False |
| SBC052 | 85% | 5506 | 1517 | 0.3608 | 9.17 | False |
| SBC044 | 95% | 6372 | 1339 | 0.1712 | 3.80 | False |
| SBC039 | n/a (pilot) | 4347 | 1227 | 0.3752 | 11.59 | True |

## Per-file results (10-file batch)

### SBC024

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4253 | [0.3812, 0.4673] | 4 |
| **within_turn** | recall | 0.8517 | [0.8070, 0.8768] | 4 |
| **within_turn** | f1 | 0.5668 | [0.5178, 0.6031] | 4 |
| **within_turn** | window_diff | 0.5458 | [0.4839, 0.5862] | 4 |
| **within_turn** | boundary_similarity | 0.4288 | [0.3947, 0.4608] | 4 |
| **within_turn** | hyp_ref_ratio | 2.0103 | [1.8193, 2.1170] | 4 |
| all_boundaries | precision | 0.5565 | [0.5170, 0.5986] | 4 |
| all_boundaries | recall | 0.9070 | [0.8790, 0.9228] | 4 |
| all_boundaries | f1 | 0.6895 | [0.6511, 0.7209] | 4 |
| all_boundaries | window_diff | 0.4245 | [0.3670, 0.4712] | 4 |
| all_boundaries | boundary_similarity | 0.5558 | [0.5239, 0.5889] | 4 |
| all_boundaries | hyp_ref_ratio | 1.6332 | [1.5135, 1.7001] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 16.0%. Share of scored words inside such runs: 0.44%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['2']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.4330 | 0.8624 | 0.5765 | 0.4994 | 0.4274 | 1.9918 |
| all_boundaries | 0.5635 | 0.9138 | 0.6971 | 0.3931 | 0.5549 | 1.6216 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 1 | 10 | 2 | 5 | False | True |
| 2 | 2 | 31 | 6 | 5 | True | True |
| 3 | 2 | 8 | 2 | 5 | False | True |
| 3 | 3 | 8 | 2 | 5 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 581 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.5326 | [0.4477, 0.5701] | 5 |
| **within_turn** | recall | 0.7335 | [0.7125, 0.7721] | 5 |
| **within_turn** | f1 | 0.6160 | [0.5523, 0.6422] | 5 |
| **within_turn** | window_diff | 0.3827 | [0.3497, 0.4527] | 5 |
| **within_turn** | boundary_similarity | 0.5070 | [0.4575, 0.5262] | 5 |
| **within_turn** | hyp_ref_ratio | 1.3873 | [1.2587, 1.6099] | 5 |
| all_boundaries | precision | 0.6727 | [0.5968, 0.7059] | 5 |
| all_boundaries | recall | 0.8329 | [0.8198, 0.8571] | 5 |
| all_boundaries | f1 | 0.7436 | [0.6926, 0.7646] | 5 |
| all_boundaries | window_diff | 0.2925 | [0.2648, 0.3585] | 5 |
| all_boundaries | boundary_similarity | 0.6438 | [0.5959, 0.6643] | 5 |
| all_boundaries | hyp_ref_ratio | 1.2427 | [1.1622, 1.3822] | 5 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 0.0%. Share of scored words inside such runs: 0.00%.

No auto-flagged (run > 22) draw this condition.

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 235/2283 = 10.3%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 286 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 4.9% |


### SBC005

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.3658 | [0.3428, 0.3909] | 4 |
| **within_turn** | recall | 0.7208 | [0.6967, 0.7643] | 4 |
| **within_turn** | f1 | 0.4846 | [0.4629, 0.5075] | 4 |
| **within_turn** | window_diff | 0.5256 | [0.4863, 0.5874] | 4 |
| **within_turn** | boundary_similarity | 0.3923 | [0.3639, 0.4140] | 4 |
| **within_turn** | hyp_ref_ratio | 1.9790 | [1.8258, 2.2295] | 4 |
| all_boundaries | precision | 0.4935 | [0.4628, 0.5201] | 4 |
| all_boundaries | recall | 0.8136 | [0.7975, 0.8427] | 4 |
| all_boundaries | f1 | 0.6138 | [0.5964, 0.6351] | 4 |
| all_boundaries | window_diff | 0.4122 | [0.3774, 0.4658] | 4 |
| all_boundaries | boundary_similarity | 0.5100 | [0.4767, 0.5342] | 4 |
| all_boundaries | hyp_ref_ratio | 1.6536 | [1.5513, 1.8208] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 4.0%. Share of scored words inside such runs: 0.20%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['4']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.3715 | 0.7439 | 0.4956 | 0.4975 | 0.3874 | 2.0020 |
| all_boundaries | 0.4967 | 0.8290 | 0.6212 | 0.3957 | 0.5043 | 1.6689 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 4 | 4 | 29 | 8 | 4 | True | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 627 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4591 | [0.4488, 0.4657] | 5 |
| **within_turn** | recall | 0.7434 | [0.7234, 0.7766] | 5 |
| **within_turn** | f1 | 0.5675 | [0.5551, 0.5787] | 5 |
| **within_turn** | window_diff | 0.4250 | [0.4130, 0.4393] | 5 |
| **within_turn** | boundary_similarity | 0.4504 | [0.4391, 0.4674] | 5 |
| **within_turn** | hyp_ref_ratio | 1.6193 | [1.5717, 1.6844] | 5 |
| all_boundaries | precision | 0.5863 | [0.5783, 0.5901] | 5 |
| all_boundaries | recall | 0.8287 | [0.8153, 0.8509] | 5 |
| all_boundaries | f1 | 0.6867 | [0.6776, 0.6941] | 5 |
| all_boundaries | window_diff | 0.3200 | [0.3146, 0.3294] | 5 |
| all_boundaries | boundary_similarity | 0.5711 | [0.5615, 0.5848] | 5 |
| all_boundaries | hyp_ref_ratio | 1.4134 | [1.3817, 1.4569] | 5 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 0.0%. Share of scored words inside such runs: 0.00%.

No auto-flagged (run > 22) draw this condition.

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 298/2609 = 11.4%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 379 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 11.1% |


### SBC041

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4251 | [0.4029, 0.4436] | 5 |
| **within_turn** | recall | 0.6953 | [0.6540, 0.7360] | 5 |
| **within_turn** | f1 | 0.5273 | [0.5059, 0.5468] | 5 |
| **within_turn** | window_diff | 0.4291 | [0.4116, 0.4474] | 5 |
| **within_turn** | boundary_similarity | 0.4285 | [0.4162, 0.4350] | 5 |
| **within_turn** | hyp_ref_ratio | 1.6373 | [1.5250, 1.7223] | 5 |
| all_boundaries | precision | 0.5409 | [0.5202, 0.5600] | 5 |
| all_boundaries | recall | 0.7843 | [0.7551, 0.8131] | 5 |
| all_boundaries | f1 | 0.6400 | [0.6220, 0.6531] | 5 |
| all_boundaries | window_diff | 0.4291 | [0.4116, 0.4474] | 5 |
| all_boundaries | boundary_similarity | 0.5354 | [0.5233, 0.5434] | 5 |
| all_boundaries | hyp_ref_ratio | 1.4511 | [1.3716, 1.5113] | 5 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 6.7%. Share of scored words inside such runs: 0.09%.

No auto-flagged (run > 22) draw this condition.

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 3 | 6 | 1 | 5 | False | True |
| 4 | 3 | 8 | 2 | 5 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 515 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4387 | [0.4152, 0.4563] | 4 |
| **within_turn** | recall | 0.7701 | [0.7284, 0.8316] | 4 |
| **within_turn** | f1 | 0.5581 | [0.5463, 0.5713] | 4 |
| **within_turn** | window_diff | 0.4289 | [0.3954, 0.4771] | 4 |
| **within_turn** | boundary_similarity | 0.4282 | [0.4096, 0.4428] | 4 |
| **within_turn** | hyp_ref_ratio | 1.7606 | [1.5964, 2.0030] | 4 |
| all_boundaries | precision | 0.5456 | [0.5151, 0.5680] | 4 |
| all_boundaries | recall | 0.8373 | [0.8077, 0.8808] | 4 |
| all_boundaries | f1 | 0.6600 | [0.6500, 0.6715] | 4 |
| all_boundaries | window_diff | 0.4289 | [0.3954, 0.4771] | 4 |
| all_boundaries | boundary_similarity | 0.5302 | [0.5063, 0.5455] | 4 |
| all_boundaries | hyp_ref_ratio | 1.5384 | [1.4221, 1.7100] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 16.7%. Share of scored words inside such runs: 0.57%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['2']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.4044 | 0.7891 | 0.5347 | 0.4605 | 0.3951 | 1.9514 |
| all_boundaries | 0.5083 | 0.8507 | 0.6364 | 0.4605 | 0.4948 | 1.6735 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 0 | 7 | 1 | 5 | False | True |
| 0 | 2 | 8 | 2 | 5 | False | True |
| 0 | 3 | 7 | 1 | 5 | False | True |
| 2 | 1 | 56 | 15 | 5 | True | True |
| 3 | 0 | 10 | 3 | 5 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 417/2802 = 14.9%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 455 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 21.3% |


### SBC053

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.3021 | [0.3021, 0.3021] | 1 |
| **within_turn** | recall | 0.7176 | [0.7176, 0.7176] | 1 |
| **within_turn** | f1 | 0.4252 | [0.4252, 0.4252] | 1 |
| **within_turn** | window_diff | 0.6324 | [0.6324, 0.6324] | 1 |
| **within_turn** | boundary_similarity | 0.3473 | [0.3473, 0.3473] | 1 |
| **within_turn** | hyp_ref_ratio | 2.3754 | [2.3754, 2.3754] | 1 |
| all_boundaries | precision | 0.4038 | [0.4038, 0.4038] | 1 |
| all_boundaries | recall | 0.7991 | [0.7991, 0.7991] | 1 |
| all_boundaries | f1 | 0.5365 | [0.5365, 0.5365] | 1 |
| all_boundaries | window_diff | 0.5068 | [0.5068, 0.5068] | 1 |
| all_boundaries | boundary_similarity | 0.4411 | [0.4411, 0.4411] | 1 |
| all_boundaries | hyp_ref_ratio | 1.9787 | [1.9787, 1.9787] | 1 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 37.1%. Share of scored words inside such runs: 1.79%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['1', '2', '3', '4']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.2803 | 0.7259 | 0.4044 | 0.6434 | 0.3211 | 2.5897 |
| **within_turn** | 0.3168 | 0.7342 | 0.4427 | 0.5993 | 0.3534 | 2.3173 |
| **within_turn** | 0.2807 | 0.7243 | 0.4046 | 0.6555 | 0.3189 | 2.5797 |
| **within_turn** | 0.2830 | 0.7625 | 0.4128 | 0.6627 | 0.3111 | 2.6944 |
| all_boundaries | 0.3777 | 0.8050 | 0.5142 | 0.5302 | 0.4118 | 2.1312 |
| all_boundaries | 0.4185 | 0.8109 | 0.5521 | 0.4797 | 0.4477 | 1.9374 |
| all_boundaries | 0.3784 | 0.8038 | 0.5146 | 0.5454 | 0.4099 | 2.1241 |
| all_boundaries | 0.3767 | 0.8310 | 0.5184 | 0.5456 | 0.3996 | 2.2057 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 0 | 5 | 0 | 3 | False | True |
| 0 | 2 | 4 | 1 | 3 | False | True |
| 1 | 1 | 149 | 30 | 3 | True | True |
| 1 | 4 | 4 | 1 | 3 | False | True |
| 2 | 0 | 4 | 1 | 3 | False | True |
| 2 | 1 | 4 | 1 | 3 | False | True |
| 2 | 4 | 24 | 4 | 3 | True | True |
| 2 | 5 | 4 | 1 | 3 | False | True |
| 3 | 4 | 72 | 14 | 3 | True | True |
| 4 | 0 | 25 | 5 | 3 | True | True |
| 4 | 1 | 4 | 1 | 3 | False | True |
| 4 | 2 | 4 | 0 | 3 | False | True |
| 4 | 4 | 21 | 5 | 3 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 992 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4291 | [0.4090, 0.4558] | 3 |
| **within_turn** | recall | 0.7592 | [0.7542, 0.7691] | 3 |
| **within_turn** | f1 | 0.5480 | [0.5304, 0.5682] | 3 |
| **within_turn** | window_diff | 0.4493 | [0.4264, 0.4788] | 3 |
| **within_turn** | boundary_similarity | 0.4194 | [0.3943, 0.4491] | 3 |
| **within_turn** | hyp_ref_ratio | 1.7730 | [1.6545, 1.8439] | 3 |
| all_boundaries | precision | 0.5353 | [0.5155, 0.5629] | 3 |
| all_boundaries | recall | 0.8286 | [0.8251, 0.8357] | 3 |
| all_boundaries | f1 | 0.6502 | [0.6345, 0.6692] | 3 |
| all_boundaries | window_diff | 0.3478 | [0.3215, 0.3733] | 3 |
| all_boundaries | boundary_similarity | 0.5205 | [0.4959, 0.5506] | 3 |
| all_boundaries | hyp_ref_ratio | 1.5500 | [1.4657, 1.6005] | 3 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 31.4%. Share of scored words inside such runs: 0.97%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['1', '4']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.3755 | 0.7193 | 0.4934 | 0.4793 | 0.3689 | 1.9153 |
| **within_turn** | 0.3980 | 0.8007 | 0.5317 | 0.4854 | 0.3923 | 2.0116 |
| all_boundaries | 0.4846 | 0.8002 | 0.6037 | 0.3802 | 0.4714 | 1.6513 |
| all_boundaries | 0.4990 | 0.8582 | 0.6310 | 0.3772 | 0.4892 | 1.7199 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 1 | 16 | 2 | 3 | False | True |
| 0 | 2 | 9 | 2 | 3 | False | True |
| 1 | 1 | 71 | 14 | 3 | True | True |
| 1 | 2 | 6 | 1 | 3 | False | True |
| 2 | 0 | 4 | 1 | 3 | False | True |
| 2 | 1 | 21 | 3 | 3 | False | True |
| 2 | 2 | 6 | 1 | 3 | False | True |
| 2 | 5 | 4 | 1 | 3 | False | True |
| 3 | 1 | 5 | 1 | 3 | False | True |
| 4 | 0 | 25 | 5 | 3 | True | True |
| 4 | 2 | 9 | 2 | 3 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 403/3384 = 11.9%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 527 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 8.9% |


### SBC012

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4440 | [0.3994, 0.4865] | 5 |
| **within_turn** | recall | 0.7784 | [0.7624, 0.7953] | 5 |
| **within_turn** | f1 | 0.5647 | [0.5277, 0.5940] | 5 |
| **within_turn** | window_diff | 0.4226 | [0.3787, 0.4732] | 5 |
| **within_turn** | boundary_similarity | 0.4598 | [0.4263, 0.4833] | 5 |
| **within_turn** | hyp_ref_ratio | 1.7624 | [1.5671, 1.9471] | 5 |
| all_boundaries | precision | 0.5037 | [0.4583, 0.5476] | 5 |
| all_boundaries | recall | 0.8171 | [0.8039, 0.8311] | 5 |
| all_boundaries | f1 | 0.6225 | [0.5871, 0.6515] | 5 |
| all_boundaries | window_diff | 0.4226 | [0.3787, 0.4732] | 5 |
| all_boundaries | boundary_similarity | 0.5154 | [0.4809, 0.5408] | 5 |
| all_boundaries | hyp_ref_ratio | 1.6291 | [1.4680, 1.7816] | 5 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 2.9%. Share of scored words inside such runs: 0.05%.

No auto-flagged (run > 22) draw this condition.

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 4 | 6 | 10 | 1 | 5 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 584 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.5022 | [0.4897, 0.5087] | 4 |
| **within_turn** | recall | 0.8167 | [0.7906, 0.8376] | 4 |
| **within_turn** | f1 | 0.6219 | [0.6102, 0.6306] | 4 |
| **within_turn** | window_diff | 0.3525 | [0.3407, 0.3633] | 4 |
| **within_turn** | boundary_similarity | 0.5026 | [0.4983, 0.5068] | 4 |
| **within_turn** | hyp_ref_ratio | 1.6267 | [1.5541, 1.6565] | 4 |
| all_boundaries | precision | 0.5595 | [0.5476, 0.5676] | 4 |
| all_boundaries | recall | 0.8488 | [0.8272, 0.8660] | 4 |
| all_boundaries | f1 | 0.6744 | [0.6639, 0.6814] | 4 |
| all_boundaries | window_diff | 0.3525 | [0.3407, 0.3633] | 4 |
| all_boundaries | boundary_similarity | 0.5572 | [0.5529, 0.5604] | 4 |
| all_boundaries | hyp_ref_ratio | 1.5172 | [1.4573, 1.5417] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 11.4%. Share of scored words inside such runs: 0.28%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['2']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.4696 | 0.8541 | 0.6060 | 0.4039 | 0.4642 | 1.8188 |
| all_boundaries | 0.5249 | 0.8796 | 0.6575 | 0.4039 | 0.5178 | 1.6757 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 2 | 11 | 3 | 5 | False | True |
| 2 | 1 | 29 | 5 | 5 | True | True |
| 2 | 2 | 7 | 2 | 5 | False | True |
| 3 | 2 | 7 | 2 | 5 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 775/3716 = 20.9%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 344 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 38.1% |


### SBC045

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.3938 | [0.3757, 0.4010] | 4 |
| **within_turn** | recall | 0.8053 | [0.7600, 0.8387] | 4 |
| **within_turn** | f1 | 0.5285 | [0.5182, 0.5420] | 4 |
| **within_turn** | window_diff | 0.5466 | [0.5151, 0.5887] | 4 |
| **within_turn** | boundary_similarity | 0.4135 | [0.3947, 0.4235] | 4 |
| **within_turn** | hyp_ref_ratio | 2.0475 | [1.9087, 2.2225] | 4 |
| all_boundaries | precision | 0.4841 | [0.4622, 0.4933] | 4 |
| all_boundaries | recall | 0.8566 | [0.8232, 0.8812] | 4 |
| all_boundaries | f1 | 0.6182 | [0.6057, 0.6280] | 4 |
| all_boundaries | window_diff | 0.4308 | [0.4056, 0.4645] | 4 |
| all_boundaries | boundary_similarity | 0.4986 | [0.4771, 0.5115] | 4 |
| all_boundaries | hyp_ref_ratio | 1.7716 | [1.6694, 1.9006] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 25.0%. Share of scored words inside such runs: 0.78%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['4']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.3633 | 0.8625 | 0.5113 | 0.5980 | 0.3712 | 2.3737 |
| all_boundaries | 0.4467 | 0.8987 | 0.5968 | 0.4862 | 0.4518 | 2.0120 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 4 | 7 | 1 | 4 | False | True |
| 1 | 1 | 6 | 1 | 4 | False | True |
| 1 | 4 | 10 | 3 | 4 | False | True |
| 2 | 0 | 5 | 1 | 4 | False | True |
| 2 | 5 | 14 | 4 | 4 | False | True |
| 3 | 2 | 8 | 1 | 4 | False | True |
| 3 | 6 | 13 | 3 | 4 | False | True |
| 4 | 1 | 89 | 17 | 4 | True | True |
| 4 | 4 | 6 | 1 | 4 | False | True |
| 4 | 6 | 10 | 3 | 4 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 855 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4316 | [0.4103, 0.4511] | 5 |
| **within_turn** | recall | 0.8163 | [0.7950, 0.8313] | 5 |
| **within_turn** | f1 | 0.5645 | [0.5444, 0.5756] | 5 |
| **within_turn** | window_diff | 0.4992 | [0.4578, 0.5223] | 5 |
| **within_turn** | boundary_similarity | 0.4369 | [0.4158, 0.4608] | 5 |
| **within_turn** | hyp_ref_ratio | 1.8932 | [1.7625, 1.9712] | 5 |
| all_boundaries | precision | 0.5219 | [0.5008, 0.5436] | 5 |
| all_boundaries | recall | 0.8646 | [0.8490, 0.8757] | 5 |
| all_boundaries | f1 | 0.6508 | [0.6328, 0.6628] | 5 |
| all_boundaries | window_diff | 0.3873 | [0.3530, 0.4105] | 5 |
| all_boundaries | boundary_similarity | 0.5231 | [0.5021, 0.5481] | 5 |
| all_boundaries | hyp_ref_ratio | 1.6580 | [1.5617, 1.7155] | 5 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 20.0%. Share of scored words inside such runs: 0.27%.

No auto-flagged (run > 22) draw this condition.

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 1 | 4 | 5 | 1 | 4 | False | True |
| 1 | 5 | 7 | 1 | 4 | False | True |
| 2 | 0 | 11 | 2 | 4 | False | True |
| 2 | 4 | 5 | 1 | 4 | False | True |
| 2 | 5 | 9 | 2 | 4 | False | True |
| 3 | 5 | 6 | 1 | 4 | False | True |
| 4 | 2 | 8 | 2 | 4 | False | True |
| 4 | 5 | 7 | 1 | 4 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 537/3995 = 13.4%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 603 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 14.4% |


### SBC016

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.3005 | [0.2735, 0.3279] | 4 |
| **within_turn** | recall | 0.6473 | [0.6116, 0.7039] | 4 |
| **within_turn** | f1 | 0.4097 | [0.3779, 0.4386] | 4 |
| **within_turn** | window_diff | 0.5591 | [0.5077, 0.6187] | 4 |
| **within_turn** | boundary_similarity | 0.3070 | [0.2928, 0.3252] | 4 |
| **within_turn** | hyp_ref_ratio | 2.1652 | [1.9464, 2.4583] | 4 |
| all_boundaries | precision | 0.5439 | [0.5140, 0.5720] | 4 |
| all_boundaries | recall | 0.8361 | [0.8195, 0.8624] | 4 |
| all_boundaries | f1 | 0.6585 | [0.6366, 0.6816] | 4 |
| all_boundaries | window_diff | 0.4508 | [0.4030, 0.4991] | 4 |
| all_boundaries | boundary_similarity | 0.5343 | [0.5105, 0.5550] | 4 |
| all_boundaries | hyp_ref_ratio | 1.5415 | [1.4398, 1.6777] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 27.5%. Share of scored words inside such runs: 0.53%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['4']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.2766 | 0.6696 | 0.3915 | 0.6087 | 0.2909 | 2.4211 |
| all_boundaries | 0.5098 | 0.8465 | 0.6363 | 0.4939 | 0.5094 | 1.6604 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 1 | 6 | 0 | 4 | False | True |
| 0 | 5 | 5 | 0 | 4 | False | True |
| 0 | 6 | 9 | 2 | 4 | False | True |
| 1 | 3 | 8 | 2 | 4 | False | True |
| 2 | 1 | 5 | 1 | 4 | False | True |
| 2 | 3 | 17 | 2 | 4 | False | True |
| 3 | 0 | 9 | 2 | 4 | False | True |
| 3 | 3 | 16 | 2 | 4 | False | True |
| 3 | 4 | 6 | 1 | 4 | False | True |
| 4 | 3 | 7 | 1 | 4 | False | True |
| 4 | 5 | 33 | 7 | 4 | True | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1803 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.3886 | [0.3684, 0.4146] | 3 |
| **within_turn** | recall | 0.7004 | [0.6741, 0.7336] | 3 |
| **within_turn** | f1 | 0.4998 | [0.4812, 0.5298] | 3 |
| **within_turn** | window_diff | 0.4383 | [0.4221, 0.4532] | 3 |
| **within_turn** | boundary_similarity | 0.3822 | [0.3644, 0.4040] | 3 |
| **within_turn** | hyp_ref_ratio | 1.8040 | [1.7604, 1.8824] | 3 |
| all_boundaries | precision | 0.6268 | [0.6081, 0.6454] | 3 |
| all_boundaries | recall | 0.8607 | [0.8485, 0.8762] | 3 |
| all_boundaries | f1 | 0.7253 | [0.7116, 0.7433] | 3 |
| all_boundaries | window_diff | 0.3422 | [0.3235, 0.3566] | 3 |
| all_boundaries | boundary_similarity | 0.6089 | [0.5917, 0.6262] | 3 |
| all_boundaries | hyp_ref_ratio | 1.3737 | [1.3534, 1.4101] | 3 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 20.0%. Share of scored words inside such runs: 0.54%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['1', '3']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.3827 | 0.6920 | 0.4928 | 0.4238 | 0.3628 | 1.8080 |
| **within_turn** | 0.3633 | 0.7158 | 0.4820 | 0.4585 | 0.3559 | 1.9702 |
| all_boundaries | 0.6229 | 0.8568 | 0.7214 | 0.3298 | 0.5936 | 1.3755 |
| all_boundaries | 0.5982 | 0.8679 | 0.7082 | 0.3601 | 0.5804 | 1.4509 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 6 | 13 | 0 | 4 | False | True |
| 1 | 5 | 6 | 1 | 4 | False | True |
| 1 | 6 | 42 | 4 | 4 | True | True |
| 2 | 3 | 5 | 1 | 4 | False | True |
| 3 | 0 | 35 | 9 | 4 | True | True |
| 3 | 3 | 5 | 1 | 4 | False | True |
| 3 | 5 | 13 | 2 | 4 | False | True |
| 4 | 3 | 5 | 1 | 4 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 422/3815 = 11.1%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 984 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 7.2% |


### SBC014

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.3342 | [0.3086, 0.3549] | 4 |
| **within_turn** | recall | 0.6688 | [0.6172, 0.7227] | 4 |
| **within_turn** | f1 | 0.4448 | [0.4227, 0.4650] | 4 |
| **within_turn** | window_diff | 0.5804 | [0.5375, 0.6494] | 4 |
| **within_turn** | boundary_similarity | 0.3624 | [0.3344, 0.3891] | 4 |
| **within_turn** | hyp_ref_ratio | 2.0105 | [1.8805, 2.3422] | 4 |
| all_boundaries | precision | 0.4283 | [0.3938, 0.4503] | 4 |
| all_boundaries | recall | 0.7509 | [0.7120, 0.7914] | 4 |
| all_boundaries | f1 | 0.5447 | [0.5259, 0.5641] | 4 |
| all_boundaries | window_diff | 0.4631 | [0.4276, 0.5241] | 4 |
| all_boundaries | boundary_similarity | 0.4479 | [0.4240, 0.4752] | 4 |
| all_boundaries | hyp_ref_ratio | 1.7600 | [1.6623, 2.0096] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 15.6%. Share of scored words inside such runs: 0.52%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['3']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.3357 | 0.7239 | 0.4587 | 0.5758 | 0.3630 | 2.1566 |
| all_boundaries | 0.4237 | 0.7923 | 0.5521 | 0.4716 | 0.4444 | 1.8700 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 4 | 7 | 2 | 4 | False | True |
| 1 | 1 | 6 | 1 | 4 | False | True |
| 1 | 4 | 5 | 1 | 4 | False | True |
| 2 | 5 | 20 | 3 | 4 | False | True |
| 3 | 1 | 5 | 1 | 4 | False | True |
| 3 | 3 | 7 | 2 | 4 | False | True |
| 3 | 5 | 78 | 13 | 4 | True | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1001 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4147 | [0.4025, 0.4269] | 4 |
| **within_turn** | recall | 0.7810 | [0.7320, 0.8329] | 4 |
| **within_turn** | f1 | 0.5413 | [0.5278, 0.5531] | 4 |
| **within_turn** | window_diff | 0.4959 | [0.4782, 0.5291] | 4 |
| **within_turn** | boundary_similarity | 0.4149 | [0.3999, 0.4235] | 4 |
| **within_turn** | hyp_ref_ratio | 1.8851 | [1.7738, 2.0696] | 4 |
| all_boundaries | precision | 0.5019 | [0.4845, 0.5139] | 4 |
| all_boundaries | recall | 0.8353 | [0.7984, 0.8743] | 4 |
| all_boundaries | f1 | 0.6267 | [0.6185, 0.6373] | 4 |
| all_boundaries | window_diff | 0.3846 | [0.3718, 0.4135] | 4 |
| all_boundaries | boundary_similarity | 0.4976 | [0.4791, 0.5063] | 4 |
| all_boundaries | hyp_ref_ratio | 1.6658 | [1.5820, 1.8045] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 42.2%. Share of scored words inside such runs: 0.73%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['2']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.4011 | 0.8538 | 0.5458 | 0.5367 | 0.4006 | 2.1288 |
| all_boundaries | 0.4814 | 0.8901 | 0.6248 | 0.4184 | 0.4783 | 1.8490 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 0 | 9 | 2 | 4 | False | True |
| 0 | 2 | 7 | 2 | 4 | False | True |
| 0 | 5 | 7 | 2 | 4 | False | True |
| 0 | 6 | 9 | 2 | 4 | False | True |
| 0 | 8 | 7 | 2 | 4 | False | True |
| 1 | 2 | 7 | 2 | 4 | False | True |
| 1 | 4 | 7 | 2 | 4 | False | True |
| 1 | 8 | 7 | 1 | 4 | False | True |
| 2 | 0 | 9 | 2 | 4 | False | True |
| 2 | 1 | 27 | 5 | 4 | True | True |
| 2 | 2 | 8 | 2 | 4 | False | True |
| 2 | 8 | 6 | 1 | 4 | False | True |
| 3 | 0 | 9 | 2 | 4 | False | True |
| 3 | 4 | 13 | 3 | 4 | False | True |
| 3 | 5 | 7 | 2 | 4 | False | True |
| 3 | 7 | 14 | 4 | 4 | False | True |
| 3 | 8 | 9 | 2 | 4 | False | True |
| 4 | 2 | 7 | 2 | 4 | False | True |
| 4 | 4 | 10 | 2 | 4 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 728/4609 = 15.8%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 690 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 28.1% |


### SBC052

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.3633 | [0.3612, 0.3654] | 2 |
| **within_turn** | recall | 0.7616 | [0.7327, 0.7905] | 2 |
| **within_turn** | f1 | 0.4917 | [0.4876, 0.4958] | 2 |
| **within_turn** | window_diff | 0.5566 | [0.5333, 0.5799] | 2 |
| **within_turn** | boundary_similarity | 0.3837 | [0.3804, 0.3869] | 2 |
| **within_turn** | hyp_ref_ratio | 2.0970 | [2.0052, 2.1889] | 2 |
| all_boundaries | precision | 0.4985 | [0.4921, 0.5048] | 2 |
| all_boundaries | recall | 0.8477 | [0.8292, 0.8661] | 2 |
| all_boundaries | f1 | 0.6276 | [0.6276, 0.6276] | 2 |
| all_boundaries | window_diff | 0.4441 | [0.4281, 0.4600] | 2 |
| all_boundaries | boundary_similarity | 0.5103 | [0.5042, 0.5164] | 2 |
| all_boundaries | hyp_ref_ratio | 1.7012 | [1.6425, 1.7599] | 2 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 26.0%. Share of scored words inside such runs: 0.69%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['0', '1', '4']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.3566 | 0.7276 | 0.4786 | 0.5381 | 0.3815 | 2.0402 |
| **within_turn** | 0.3545 | 0.8122 | 0.4936 | 0.5928 | 0.3746 | 2.2910 |
| **within_turn** | 0.3677 | 0.7585 | 0.4953 | 0.5432 | 0.3863 | 2.0630 |
| all_boundaries | 0.4960 | 0.8259 | 0.6198 | 0.4319 | 0.5107 | 1.6649 |
| all_boundaries | 0.4821 | 0.8799 | 0.6229 | 0.4675 | 0.4959 | 1.8252 |
| all_boundaries | 0.5035 | 0.8456 | 0.6312 | 0.4324 | 0.5137 | 1.6794 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 0 | 26 | 6 | 4 | True | True |
| 0 | 1 | 9 | 2 | 4 | False | True |
| 0 | 4 | 11 | 3 | 4 | False | True |
| 1 | 0 | 6 | 1 | 4 | False | True |
| 1 | 1 | 29 | 7 | 4 | True | True |
| 1 | 4 | 13 | 2 | 4 | False | True |
| 1 | 6 | 5 | 1 | 4 | False | True |
| 2 | 1 | 9 | 2 | 4 | False | True |
| 2 | 4 | 13 | 3 | 4 | False | True |
| 3 | 0 | 9 | 2 | 4 | False | True |
| 3 | 4 | 8 | 2 | 4 | False | True |
| 4 | 0 | 5 | 1 | 4 | False | True |
| 4 | 4 | 47 | 10 | 4 | True | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1149 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4390 | [0.4243, 0.4591] | 4 |
| **within_turn** | recall | 0.6943 | [0.6502, 0.7152] | 4 |
| **within_turn** | f1 | 0.5376 | [0.5200, 0.5547] | 4 |
| **within_turn** | window_diff | 0.4432 | [0.4274, 0.4630] | 4 |
| **within_turn** | boundary_similarity | 0.4304 | [0.4219, 0.4396] | 4 |
| **within_turn** | hyp_ref_ratio | 1.5828 | [1.5005, 1.6760] | 4 |
| all_boundaries | precision | 0.5865 | [0.5693, 0.6051] | 4 |
| all_boundaries | recall | 0.8046 | [0.7764, 0.8179] | 4 |
| all_boundaries | f1 | 0.6783 | [0.6693, 0.6923] | 4 |
| all_boundaries | window_diff | 0.3428 | [0.3281, 0.3617] | 4 |
| all_boundaries | boundary_similarity | 0.5687 | [0.5578, 0.5782] | 4 |
| all_boundaries | hyp_ref_ratio | 1.3725 | [1.3199, 1.4321] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 18.0%. Share of scored words inside such runs: 0.37%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['1']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.4106 | 0.6873 | 0.5141 | 0.4325 | 0.4017 | 1.6739 |
| all_boundaries | 0.5592 | 0.8001 | 0.6583 | 0.3476 | 0.5408 | 1.4307 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 0 | 5 | 1 | 4 | False | True |
| 0 | 2 | 6 | 1 | 4 | False | True |
| 0 | 8 | 5 | 1 | 4 | False | True |
| 1 | 0 | 5 | 1 | 4 | False | True |
| 1 | 1 | 55 | 11 | 4 | True | True |
| 1 | 8 | 6 | 1 | 4 | False | True |
| 3 | 0 | 5 | 1 | 4 | False | True |
| 3 | 6 | 5 | 1 | 4 | False | True |
| 4 | 1 | 9 | 2 | 4 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 516/4958 = 10.4%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 713 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 10.8% |


### SBC044

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | nan | [nan, nan] | 0 |
| **within_turn** | recall | nan | [nan, nan] | 0 |
| **within_turn** | f1 | nan | [nan, nan] | 0 |
| **within_turn** | window_diff | nan | [nan, nan] | 0 |
| **within_turn** | boundary_similarity | nan | [nan, nan] | 0 |
| all_boundaries | precision | nan | [nan, nan] | 0 |
| all_boundaries | recall | nan | [nan, nan] | 0 |
| all_boundaries | f1 | nan | [nan, nan] | 0 |
| all_boundaries | window_diff | nan | [nan, nan] | 0 |
| all_boundaries | boundary_similarity | nan | [nan, nan] | 0 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 47.3%. Share of scored words inside such runs: 1.87%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['0', '1', '2', '3', '4']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.3174 | 0.8458 | 0.4616 | 0.6571 | 0.3317 | 2.6646 |
| **within_turn** | 0.3250 | 0.8305 | 0.4672 | 0.6481 | 0.3442 | 2.5555 |
| **within_turn** | 0.3516 | 0.8151 | 0.4913 | 0.6048 | 0.3688 | 2.3183 |
| **within_turn** | 0.2951 | 0.7944 | 0.4304 | 0.6941 | 0.3218 | 2.6916 |
| **within_turn** | 0.3195 | 0.7583 | 0.4496 | 0.6445 | 0.3280 | 2.3733 |
| all_boundaries | 0.3665 | 0.8722 | 0.5161 | 0.5341 | 0.3790 | 2.3797 |
| all_boundaries | 0.3754 | 0.8595 | 0.5226 | 0.5221 | 0.3924 | 2.2892 |
| all_boundaries | 0.4046 | 0.8468 | 0.5476 | 0.4758 | 0.4193 | 2.0927 |
| all_boundaries | 0.3454 | 0.8296 | 0.4877 | 0.5647 | 0.3695 | 2.4021 |
| all_boundaries | 0.3740 | 0.7997 | 0.5096 | 0.5163 | 0.3793 | 2.1383 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 2 | 12 | 3 | 6 | False | True |
| 0 | 3 | 18 | 3 | 6 | False | True |
| 0 | 5 | 156 | 33 | 6 | True | True |
| 0 | 7 | 16 | 4 | 6 | False | True |
| 0 | 10 | 38 | 10 | 6 | True | True |
| 1 | 1 | 7 | 1 | 6 | False | True |
| 1 | 2 | 7 | 1 | 6 | False | True |
| 1 | 3 | 86 | 18 | 6 | True | True |
| 1 | 5 | 12 | 3 | 6 | False | True |
| 1 | 7 | 10 | 2 | 6 | False | True |
| 1 | 8 | 7 | 1 | 6 | False | True |
| 2 | 2 | 12 | 3 | 6 | False | True |
| 2 | 3 | 23 | 4 | 6 | True | True |
| 2 | 6 | 12 | 3 | 6 | False | True |
| 3 | 1 | 13 | 3 | 6 | False | True |
| 3 | 2 | 14 | 4 | 6 | False | True |
| 3 | 3 | 12 | 3 | 6 | False | True |
| 3 | 4 | 8 | 1 | 6 | False | True |
| 3 | 5 | 30 | 6 | 6 | True | True |
| 3 | 6 | 25 | 6 | 6 | True | True |
| 3 | 10 | 10 | 2 | 6 | False | True |
| 4 | 1 | 10 | 2 | 6 | False | True |
| 4 | 3 | 23 | 4 | 6 | True | True |
| 4 | 4 | 10 | 3 | 6 | False | True |
| 4 | 5 | 14 | 3 | 6 | False | True |
| 4 | 9 | 10 | 2 | 6 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1363 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4140 | [0.4054, 0.4213] | 4 |
| **within_turn** | recall | 0.8181 | [0.7962, 0.8404] | 4 |
| **within_turn** | f1 | 0.5497 | [0.5469, 0.5510] | 4 |
| **within_turn** | window_diff | 0.5101 | [0.4855, 0.5389] | 4 |
| **within_turn** | boundary_similarity | 0.4220 | [0.4125, 0.4312] | 4 |
| **within_turn** | hyp_ref_ratio | 1.9768 | [1.8900, 2.0730] | 4 |
| all_boundaries | precision | 0.4695 | [0.4593, 0.4783] | 4 |
| all_boundaries | recall | 0.8492 | [0.8311, 0.8677] | 4 |
| all_boundaries | f1 | 0.6046 | [0.6006, 0.6072] | 4 |
| all_boundaries | window_diff | 0.3918 | [0.3747, 0.4133] | 4 |
| all_boundaries | boundary_similarity | 0.4747 | [0.4641, 0.4849] | 4 |
| all_boundaries | hyp_ref_ratio | 1.8096 | [1.7377, 1.8894] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 12.7%. Share of scored words inside such runs: 0.25%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['2']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.4099 | 0.8467 | 0.5524 | 0.5222 | 0.4089 | 2.0658 |
| all_boundaries | 0.4635 | 0.8729 | 0.6055 | 0.4038 | 0.4606 | 1.8834 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 10 | 7 | 2 | 6 | False | True |
| 1 | 8 | 7 | 2 | 6 | False | True |
| 1 | 10 | 8 | 2 | 6 | False | True |
| 2 | 0 | 32 | 3 | 6 | True | True |
| 2 | 5 | 7 | 2 | 6 | False | True |
| 3 | 3 | 8 | 1 | 6 | False | True |
| 4 | 10 | 11 | 2 | 6 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 680/6142 = 11.1%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 798 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 8.8% |


## SBC039 (pilot file, reported separately)

### SBC039

**Condition A**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.3855 | [0.3414, 0.4126] | 4 |
| **within_turn** | recall | 0.6987 | [0.6775, 0.7193] | 4 |
| **within_turn** | f1 | 0.4963 | [0.4546, 0.5150] | 4 |
| **within_turn** | window_diff | 0.5039 | [0.4574, 0.5601] | 4 |
| **within_turn** | boundary_similarity | 0.4161 | [0.3840, 0.4384] | 4 |
| **within_turn** | hyp_ref_ratio | 1.8212 | [1.6423, 1.9922] | 4 |
| all_boundaries | precision | 0.5379 | [0.4940, 0.5698] | 4 |
| all_boundaries | recall | 0.8118 | [0.7985, 0.8246] | 4 |
| all_boundaries | f1 | 0.6467 | [0.6108, 0.6651] | 4 |
| all_boundaries | window_diff | 0.3953 | [0.3535, 0.4458] | 4 |
| all_boundaries | boundary_similarity | 0.5550 | [0.5222, 0.5807] | 4 |
| all_boundaries | hyp_ref_ratio | 1.5131 | [1.4013, 1.6199] | 4 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 5.0%. Share of scored words inside such runs: 0.32%.

Auto-flagged samples (OLD whole-corpus rule, run > 22 -- excluded from the aggregate above, reported on their own; the collapse rate just above uses the NEW per-file rule instead, S14, and is not what drives this exclusion): ['1']

| scope | precision | recall | f1 | window_diff | boundary_similarity | hyp_ref_ratio |
|---|---|---|---|---|---|---|
| **within_turn** | 0.3660 | 0.7650 | 0.4951 | 0.5460 | 0.3825 | 2.0901 |
| all_boundaries | 0.5075 | 0.8532 | 0.6364 | 0.4359 | 0.5157 | 1.6811 |

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 1 | 1 | 7 | 2 | 6 | False | True |
| 1 | 6 | 62 | 14 | 6 | True | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 893 |

**Condition B**

| scope | metric | mean | range | n samples |
|---|---|---|---|---|
| **within_turn** | precision | 0.4447 | [0.4097, 0.4659] | 5 |
| **within_turn** | recall | 0.6480 | [0.6123, 0.7128] | 5 |
| **within_turn** | f1 | 0.5272 | [0.4959, 0.5635] | 5 |
| **within_turn** | window_diff | 0.4323 | [0.4222, 0.4505] | 5 |
| **within_turn** | boundary_similarity | 0.4262 | [0.4081, 0.4474] | 5 |
| **within_turn** | hyp_ref_ratio | 1.4582 | [1.3877, 1.5326] | 5 |
| all_boundaries | precision | 0.6068 | [0.5759, 0.6232] | 5 |
| all_boundaries | recall | 0.7801 | [0.7577, 0.8206] | 5 |
| all_boundaries | f1 | 0.6824 | [0.6580, 0.7040] | 5 |
| all_boundaries | window_diff | 0.3286 | [0.3211, 0.3445] | 5 |
| all_boundaries | boundary_similarity | 0.5775 | [0.5600, 0.5909] | 5 |
| all_boundaries | hyp_ref_ratio | 1.2863 | [1.2423, 1.3328] | 5 |

Collapse rate (share of window-draws with a per-file-rule degenerate run, reports/phase2_llm_design.md S14): 5.0%. Share of scored words inside such runs: 0.06%.

No auto-flagged (run > 22) draw this condition.

Runs flagged by the old (whole-corpus, run > 22) or new (per-file, reports/phase2_llm_design.md S14) rule, side by side (rows where neither rule flagged the run are omitted):

| sample | window | run length | ref boundaries in span | file max legit. run | old rule (>22) | new per-file rule |
|---|---|---|---|---|---|---|
| 0 | 3 | 7 | 2 | 6 | False | True |
| 1 | 2 | 7 | 1 | 6 | False | True |

Offset distribution, within-turn boundaries (signed distance to nearest reference boundary; 0 = exact match), and the share of each bucket's named word immediately followed by a cue:

Base rate (cue immediately after a within-turn-eligible word): 493/3886 = 12.7%

| offset | -3 | -2 | -1 | 0 | 1 | 2 | 3 | beyond |
|---|---|---|---|---|---|---|---|---|
| n | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 581 |
| cue-after share | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 20.1% |


## A vs. B: per-file comparison, within-turn scope (batch files only, not the pilot)

Every metric below is a per-file mean over that file+condition's non-flagged samples (within-turn scope), plus collapse_rate under the new per-file rule (S14 above). This is a per-file table, not an aggregate: no cross-file mean, pooled score, or significance claim is made on 10 files -- CLAUDE.md's own standing caution applies. 'B beats A' on collapse_rate means B's rate is the LOWER of the two (fewer degenerate draws), the opposite direction from the other metrics where higher is better.

| doc_id | A precision | B precision | A recall | B recall | A f1 | B f1 | A window_diff | B window_diff | A boundary_similarity | B boundary_similarity | A hyp_ref_ratio | B hyp_ref_ratio | A collapse_rate | B collapse_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SBC024 | 0.4253 | 0.5326 | 0.8517 | 0.7335 | 0.5668 | 0.6160 | 0.5458 | 0.3827 | 0.4288 | 0.5070 | 2.0103 | 1.3873 | 0.1600 | 0.0000 |
| SBC005 | 0.3658 | 0.4591 | 0.7208 | 0.7434 | 0.4846 | 0.5675 | 0.5256 | 0.4250 | 0.3923 | 0.4504 | 1.9790 | 1.6193 | 0.0400 | 0.0000 |
| SBC041 | 0.4251 | 0.4387 | 0.6953 | 0.7701 | 0.5273 | 0.5581 | 0.4291 | 0.4289 | 0.4285 | 0.4282 | 1.6373 | 1.7606 | 0.0667 | 0.1667 |
| SBC053 | 0.3021 | 0.4291 | 0.7176 | 0.7592 | 0.4252 | 0.5480 | 0.6324 | 0.4493 | 0.3473 | 0.4194 | 2.3754 | 1.7730 | 0.3714 | 0.3143 |
| SBC012 | 0.4440 | 0.5022 | 0.7784 | 0.8167 | 0.5647 | 0.6219 | 0.4226 | 0.3525 | 0.4598 | 0.5026 | 1.7624 | 1.6267 | 0.0286 | 0.1143 |
| SBC045 | 0.3938 | 0.4316 | 0.8053 | 0.8163 | 0.5285 | 0.5645 | 0.5466 | 0.4992 | 0.4135 | 0.4369 | 2.0475 | 1.8932 | 0.2500 | 0.2000 |
| SBC016 | 0.3005 | 0.3886 | 0.6473 | 0.7004 | 0.4097 | 0.4998 | 0.5591 | 0.4383 | 0.3070 | 0.3822 | 2.1652 | 1.8040 | 0.2750 | 0.2000 |
| SBC014 | 0.3342 | 0.4147 | 0.6688 | 0.7810 | 0.4448 | 0.5413 | 0.5804 | 0.4959 | 0.3624 | 0.4149 | 2.0105 | 1.8851 | 0.1556 | 0.4222 |
| SBC052 | 0.3633 | 0.4390 | 0.7616 | 0.6943 | 0.4917 | 0.5376 | 0.5566 | 0.4432 | 0.3837 | 0.4304 | 2.0970 | 1.5828 | 0.2600 | 0.1800 |
| SBC044 | nan | 0.4140 | nan | 0.8181 | nan | 0.5497 | nan | 0.5101 | nan | 0.4220 | nan | 1.9768 | 0.4727 | 0.1273 |

B beats A on within_turn F1 on 9 of 9 files with a valid A score (SBC024, SBC005, SBC041, SBC053, SBC012, SBC045, SBC016, SBC014, SBC052). SBC044 excluded: condition A had 0 non-flagged samples there (all auto-flagged degenerate -- see its own section above), so no A score exists to compare.
B beats A on collapse_rate (lower = fewer degenerate draws) on 7 of 10 files (SBC024, SBC005, SBC053, SBC045, SBC016, SBC052, SBC044).
These are per-file counts, not a significance test or a pooled claim -- 10 files do not support one.

## Baselines (cue rule and density-matched random), within-turn scope, same 10 batch files

Same per-file table structure as the A vs. B comparison above, for the cue rule (deterministic: boundary wherever a prosodic cue was rendered) and the density-matched random baseline, on the same 10 batch files (pilot excluded, matching the A vs. B section). Baselines are deterministic/resampled from text alone, not per-sample model draws, so there is no collapse_rate column here.

| doc_id | cue_rule precision | random precision | cue_rule recall | random recall | cue_rule f1 | random f1 | cue_rule window_diff | random window_diff | cue_rule boundary_similarity | random boundary_similarity |
|---|---|---|---|---|---|---|---|---|---|---|
| SBC024 | 0.9224 | 0.2142 | 0.4641 | 0.2138 | 0.6175 | 0.2140 | 0.2940 | 0.5576 | 0.4542 | 0.2004 |
| SBC005 | 0.8404 | 0.1887 | 0.4857 | 0.1887 | 0.6156 | 0.1887 | 0.2681 | 0.5326 | 0.4590 | 0.1859 |
| SBC041 | 0.7250 | 0.2394 | 0.4401 | 0.2394 | 0.5477 | 0.2394 | 0.2890 | 0.4917 | 0.3922 | 0.2256 |
| SBC053 | 0.7845 | 0.1822 | 0.5199 | 0.1816 | 0.6254 | 0.1819 | 0.2664 | 0.5249 | 0.4777 | 0.1827 |
| SBC012 | 0.8237 | 0.2312 | 0.7694 | 0.2312 | 0.7956 | 0.2312 | 0.1592 | 0.5000 | 0.6748 | 0.2314 |
| SBC045 | 0.7925 | 0.1980 | 0.5250 | 0.1975 | 0.6316 | 0.1977 | 0.3040 | 0.5555 | 0.4744 | 0.1979 |
| SBC016 | 0.8673 | 0.1768 | 0.5833 | 0.1768 | 0.6975 | 0.1768 | 0.1975 | 0.4975 | 0.5484 | 0.1558 |
| SBC014 | 0.7158 | 0.1865 | 0.6079 | 0.1865 | 0.6575 | 0.1865 | 0.2909 | 0.5426 | 0.5144 | 0.1863 |
| SBC052 | 0.8351 | 0.1971 | 0.3973 | 0.1965 | 0.5385 | 0.1968 | 0.3195 | 0.5375 | 0.3768 | 0.1928 |
| SBC044 | 0.8544 | 0.1812 | 0.5131 | 0.1811 | 0.6411 | 0.1811 | 0.2762 | 0.5429 | 0.4832 | 0.1869 |

### Where the model stands against the cue rule, file by file (within-turn F1)

The cue rule is not a naive baseline: it has direct access to the same prosodic cues condition B renders, applied deterministically (boundary after every cue), so it is a natural ceiling-ish comparison for B specifically, not just a floor. Condition A never sees cues at all, so its comparison to the cue rule tests something different (can text alone recover what the cue rule gets from prosodic markup) and is reported alongside, not instead.

| doc_id | cue_rule F1 | A F1 | A vs. cue_rule | B F1 | B vs. cue_rule |
|---|---|---|---|---|---|
| SBC024 | 0.6175 | 0.5668 | loses to (-0.0507) | 0.6160 | loses to (-0.0015) |
| SBC005 | 0.6156 | 0.4846 | loses to (-0.1310) | 0.5675 | loses to (-0.0481) |
| SBC041 | 0.5477 | 0.5273 | loses to (-0.0204) | 0.5581 | beats (+0.0104) |
| SBC053 | 0.6254 | 0.4252 | loses to (-0.2002) | 0.5480 | loses to (-0.0774) |
| SBC012 | 0.7956 | 0.5647 | loses to (-0.2309) | 0.6219 | loses to (-0.1737) |
| SBC045 | 0.6316 | 0.5285 | loses to (-0.1031) | 0.5645 | loses to (-0.0671) |
| SBC016 | 0.6975 | 0.4097 | loses to (-0.2878) | 0.4998 | loses to (-0.1977) |
| SBC014 | 0.6575 | 0.4448 | loses to (-0.2127) | 0.5413 | loses to (-0.1162) |
| SBC052 | 0.5385 | 0.4917 | loses to (-0.0468) | 0.5376 | loses to (-0.0009) |
| SBC044 | 0.6411 | nan | n/a (all samples auto-flagged) | 0.5497 | loses to (-0.0914) |

Condition A beats the cue rule on within_turn F1 on 0 of 9 files with a valid (non-degenerate-only) score. Condition B beats the cue rule on 1 of 10. Per-file counts only -- no aggregate or significance claim on 10 files.


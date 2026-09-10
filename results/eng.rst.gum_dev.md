# eng.rst.gum dev -- LLM discourse segmentation results

22 of 24 documents scored; 0 failed alignment; 2 excluded.

## Excluded documents (not sent to the model, not counted anywhere below)

Reason: more than 50% of tokens match ^_+$ -- text is masked in the open corpus distribution, not real. Detected from the data, not by genre name.

- GUM_reddit_macroeconomics: 97.5% masked
- GUM_reddit_pandas: 96.7% masked

## Masked-token audit (^_+$), all documents, before exclusion

- GUM_reddit_macroeconomics: 97.5% of 1141 tokens masked [EXCLUDED]
- GUM_reddit_pandas: 96.7% of 614 tokens masked [EXCLUDED]
(22 of 24 documents have 0% masked tokens; full per-document figures in eng.rst.gum_dev_masking.csv.)

## Per-document results

doc_id                         genre           n_tok  ref  hyp      P      R     F1     WD     BS
-------------------------------------------------------------------------------------------------
GUM_academic_exposure          academic          964  110   53  0.808  0.385  0.522  0.270  0.398
GUM_academic_librarians        academic          810   94  102  0.644  0.699  0.670  0.268  0.544
GUM_bio_byron                  bio               746   91  148  0.490  0.800  0.608  0.415  0.454
GUM_bio_emperor                bio               962   85  113  0.125  0.167  0.143  0.491  0.100
GUM_conversation_grounded      conversation     1247  235  331  0.648  0.915  0.759  0.278  0.634
GUM_conversation_risk          conversation      944  197  264  0.715  0.959  0.819  0.161  0.698
GUM_fiction_beast              fiction          1030  130  258  0.416  0.829  0.554  0.475  0.441
GUM_fiction_lunre              fiction           761   96  123  0.393  0.505  0.442  0.324  0.467
GUM_interview_cyclone          interview         866  103  150  0.154  0.225  0.183  0.514  0.146
GUM_interview_gaming           interview         719   85   86  0.941  0.952  0.947  0.050  0.899
GUM_news_homeopathic           news              649   79  112  0.532  0.756  0.624  0.330  0.508
GUM_news_iodine                news             1071  125  168  0.569  0.766  0.653  0.301  0.521
GUM_speech_impeachment         speech           1101  152  173  0.273  0.311  0.291  0.314  0.439
GUM_speech_inauguration        speech            885  104  136  0.615  0.806  0.697  0.278  0.563
GUM_textbook_governments       textbook          945  112  134  0.609  0.730  0.664  0.306  0.509
GUM_textbook_labor             textbook          643   80  107  0.321  0.430  0.368  0.413  0.288
GUM_vlog_portland              vlog             1097  146  196  0.595  0.800  0.682  0.331  0.546
GUM_vlog_radiology             vlog              943  133  239  0.454  0.818  0.584  0.463  0.464
GUM_voyage_athens              voyage           1021  101   86  0.859  0.730  0.789  0.118  0.740
GUM_voyage_coron               voyage            582   56   46  0.978  0.800  0.880  0.087  0.786
GUM_whow_joke                  whow             1021  135  189  0.606  0.851  0.708  0.291  0.590
GUM_whow_overalls              whow              647   78   87  0.779  0.870  0.822  0.148  0.737

## Per-genre breakdown (mean of per-document scores; macro average)

genre          n_docs  mean_F1  mean_WD  mean_BS  micro_P  micro_R  micro_F1
----------------------------------------------------------------------------
academic            2    0.596    0.269    0.471    0.703    0.534     0.607
bio                 2    0.375    0.453    0.277    0.337    0.500     0.403
conversation        2    0.789    0.220    0.666    0.679    0.935     0.787
fiction             2    0.498    0.399    0.454    0.412    0.695     0.517
interview           2    0.565    0.282    0.523    0.445    0.559     0.495
news                2    0.639    0.316    0.515    0.557    0.765     0.645
speech              2    0.494    0.296    0.501    0.427    0.516     0.467
textbook            2    0.516    0.360    0.399    0.485    0.609     0.540
vlog                2    0.633    0.397    0.505    0.520    0.810     0.633
voyage              2    0.835    0.102    0.763    0.902    0.758     0.824
whow                2    0.765    0.219    0.663    0.663    0.859     0.748

## Corpus-level aggregate (all documents pooled)

macro mean F1 (unweighted mean over 22 docs): 0.6095
macro mean WindowDiff: 0.3012
macro mean Boundary Similarity: 0.5215

micro-averaged boundary P/R/F1 (DISRPT's own scoring methodology, seg_eval.py):
  precision=0.5441  recall=0.7107  f1=0.6163

## Comparison against published DISRPT 2023 baseline (eng.rst.gum, Plain track, DisCut*)

Caveat: the published score is a fine-tuned system evaluated on the *test* partition; the numbers above are zero/few-shot prompting evaluated on the *dev* partition (the only split downloaded here). Not a controlled comparison -- reported for context only.

                      precision     recall         f1
DISRPT 2023 DisCut*       94.95      93.98      94.46
this pipeline (dev)       54.41      71.07      61.63

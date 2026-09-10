# eng.rst.gum dev -- zero-shot vs few-shot

Same 22 documents both runs (masked-text docs excluded, same as the zero-shot report).
Few-shot worked examples: GUM_academic_census, GUM_conversation_atoms, GUM_fiction_claus (TRAIN split).
zero-shot: 22 scored, 0 failed alignment.
few-shot:  22 scored, 0 failed alignment.

## Per-document: precision / recall (zero-shot -> few-shot)

doc_id                         genre            zs_P   fs_P    d_P     zs_R   fs_R    d_R    zs_F1  fs_F1   d_F1
----------------------------------------------------------------------------------------------------------------
GUM_academic_exposure          academic        0.808  0.548 -0.259    0.385  0.468 +0.083    0.522  0.505 -0.017
GUM_academic_librarians        academic        0.644  0.646 +0.003    0.699  0.688 -0.011    0.670  0.667 -0.003
GUM_bio_byron                  bio             0.490  0.587 +0.097    0.800  0.711 -0.089    0.608  0.643 +0.036
GUM_bio_emperor                bio             0.125  0.090 -0.035    0.167  0.190 +0.024    0.143  0.123 -0.020
GUM_conversation_grounded      conversation    0.648  0.385 -0.264    0.915  0.949 +0.034    0.759  0.547 -0.211
GUM_conversation_risk          conversation    0.715  0.553 -0.162    0.959  0.959 +0.000    0.819  0.701 -0.118
GUM_fiction_beast              fiction         0.416  0.616 +0.199    0.829  0.845 +0.016    0.554  0.712 +0.158
GUM_fiction_lunre              fiction         0.393  0.408 +0.015    0.505  0.516 +0.011    0.442  0.456 +0.013
GUM_interview_cyclone          interview       0.154  0.168 +0.014    0.225  0.225 +0.000    0.183  0.192 +0.009
GUM_interview_gaming           interview       0.941  0.521 -0.420    0.952  0.893 -0.060    0.947  0.658 -0.289
GUM_news_homeopathic           news            0.532  0.586 +0.054    0.756  0.833 +0.077    0.624  0.688 +0.063
GUM_news_iodine                news            0.569  0.431 -0.138    0.766  0.750 -0.016    0.653  0.547 -0.106
GUM_speech_impeachment         speech          0.273  0.234 -0.039    0.311  0.238 -0.073    0.291  0.236 -0.055
GUM_speech_inauguration        speech          0.615  0.570 -0.045    0.806  0.835 +0.029    0.697  0.677 -0.020
GUM_textbook_governments       textbook        0.609  0.696 +0.087    0.730  0.640 -0.090    0.664  0.667 +0.003
GUM_textbook_labor             textbook        0.321  0.398 +0.077    0.430  0.443 +0.013    0.368  0.419 +0.052
GUM_vlog_portland              vlog            0.595  0.469 -0.126    0.800  0.890 +0.090    0.682  0.614 -0.068
GUM_vlog_radiology             vlog            0.454  0.422 -0.032    0.818  0.864 +0.045    0.584  0.567 -0.017
GUM_voyage_athens              voyage          0.859  0.692 -0.167    0.730  0.740 +0.010    0.789  0.715 -0.074
GUM_voyage_coron               voyage          0.978  0.780 -0.198    0.800  0.709 -0.091    0.880  0.743 -0.137
GUM_whow_joke                  whow            0.606  0.748 +0.142    0.851  0.799 -0.052    0.708  0.773 +0.064
GUM_whow_overalls              whow            0.779  0.617 -0.162    0.870  0.922 +0.052    0.822  0.740 -0.083

## Per-genre: micro precision / recall / F1 (zero-shot -> few-shot)

genre            n     zs_P   fs_P    d_P     zs_R   fs_R    d_R    zs_F1  fs_F1   d_F1
---------------------------------------------------------------------------------------
academic         2    0.703  0.603 -0.100    0.534  0.574 +0.039    0.607  0.588 -0.019
bio              2    0.337  0.285 -0.052    0.500  0.466 -0.034    0.403  0.353 -0.049
conversation     2    0.679  0.448 -0.231    0.935  0.954 +0.019    0.787  0.610 -0.177
fiction          2    0.412  0.535 +0.123    0.695  0.708 +0.013    0.517  0.610 +0.092
interview        2    0.445  0.353 -0.092    0.559  0.532 -0.027    0.495  0.425 -0.071
news             2    0.557  0.486 -0.071    0.765  0.784 +0.020    0.645  0.600 -0.044
speech           2    0.427  0.404 -0.023    0.516  0.484 -0.031    0.467  0.440 -0.027
textbook         2    0.485  0.562 +0.077    0.609  0.562 -0.047    0.540  0.562 +0.022
vlog             2    0.520  0.448 -0.072    0.810  0.878 +0.068    0.633  0.593 -0.040
voyage           2    0.902  0.723 -0.178    0.758  0.732 -0.025    0.824  0.728 -0.096
whow             2    0.663  0.692 +0.029    0.859  0.845 -0.014    0.748  0.761 +0.013

## Corpus-level (micro-averaged, matching DISRPT's seg_eval.py methodology)

              precision     recall         f1
zero-shot        0.5441     0.7107     0.6163
few-shot         0.4774     0.7135     0.5720
delta           -0.0667    +0.0028    -0.0443


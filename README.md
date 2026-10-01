# llm-segmentation-eval

**A one-line deterministic rule outperforms a frontier LLM at finding
intonation-unit boundaries in spoken English: precision 0.72–0.92 vs
0.30–0.53.** The model sits well above a random baseline and well below
the rule — nobody had measured the trivial baseline.

This repository evaluates LLM segmentation of transcripts against human
annotation, and reads the result against inter-annotator agreement:
a score without a human ceiling is uninterpretable.

Three phases: written text (DISRPT, done), spoken English
(Santa Barbara, in progress), spoken French with audio and a measured
human ceiling (CID, next).

Author: MA in NLP (France), doctoral research on discourse unit
boundaries in spontaneous speech. Earlier peer-reviewed work on exactly
these metrics: Peshkov & Prévot, LREC 2014.

---

Most evaluations of this kind publish a score with no human ceiling,
which makes the number uninterpretable: a WindowDiff of 0.27 tells you
nothing unless you know how far two trained annotators are from each
other on the same data. This pipeline is built to answer the second
question alongside the first, and to keep every result broken down by
document instead of collapsed into one headline figure.

Research code. It produces tables; there is no CLI, no packaging, no
web UI.

## Phases

**1. DISRPT — complete.** Text only, many corpora, published shared-task
scores to compare against. Used to build and validate the pipeline.
Zero-shot on `eng.rst.gum` dev, micro-averaged over 22 documents:
precision 0.544, recall 0.711, F1 0.616; WindowDiff 0.3012; Boundary
Similarity 0.5215; 0 alignment failures. See `reports/phase1_report.md`.

**2. Santa Barbara Corpus — in progress.** 60 files of spontaneous
conversational American English, transcribed at the level of intonation
units. The corpus has no discourse segmentation, so this phase measures
something different: **how far prosodic phrasing is recoverable from
text alone.** A transcriber heard where a contour ended; the model sees
only words. Two conditions on identical word sequences: words alone (A),
and words plus the transcript's prosodic marks (B) — pauses, in- and
out-breaths, lengthening, glottal stop, boosters. Which marks count as
prosodic, and which are dropped in both conditions as noise, is set out
in CLAUDE.md ("Tokenisation"); the symbols actually shown to the model
are `_GLOSSARY_ENTRIES` in `sbcsae_llm.py`, and a whole-corpus test
checks that no other symbol ever reaches a prompt.

**3. CID — next.** Spontaneous French, audio, discourse-unit annotation,
and inter-annotator agreement measured during the author's doctorate.
The only data where both unit types and a human ceiling exist on the
same material. The same question applied to turn detection in
conversational agents: how much does a learned endpointing model gain
over waiting N milliseconds of silence, and at what latency cost? No
corpus data will be published.

## Results so far, phase 2

Preliminary, 10 of 59 files, zero-shot, 5 samples per document, per
file and never aggregated into one number:

- The model **over-segments** in both conditions: 1.6–2.4x the reference
  boundary count in A, 1.4–2.0x in B. Recall is high, precision low.
- **Prosodic marks help, through precision.** B beats A on mean
  within-turn F1 on all 9 comparable files, and on 7 without the sample
  ranges overlapping.
- **A one-line rule beats the model.** Placing a boundary after a pause
  or an in-breath gives precision 0.72–0.92 against the model's
  0.30–0.53. A random baseline at the reference boundary density gives
  F1 0.18–0.24, so the model is well above chance and below the rule.
- **Segmentation collapses locally** in about one draw in five: the
  model stops segmenting and enumerates every remaining position. It is
  invisible in whole-file scores, which move by less than 0.01 when the
  affected draws are excluded.

See `reports/phase2_batch1.md`.

## How it works

Every component speaks one representation: **segment masses**, a list of
segment lengths in atomic units.

```python
masses = [3, 4, 3]            # 10 tokens, boundaries after token 3 and 7
assert sum(masses) == n_tokens
```

Each reader (DISRPT, SBCSAE, model output) produces masses; everything
downstream consumes masses only. The atomic unit is whatever the
corpus's own annotation is defined over — tokens in phase 1, words in
phase 2 — so scores from different phases are not comparable, and the
reports say so wherever figures sit side by side.

Rules the pipeline holds itself to:

- The model returns boundaries as indices into the given sequence.
  `sum(hyp_masses) == sum(ref_masses)` is asserted before any metric is
  computed; a document that fails is set aside and reported.
- Raw model output is written to disk before parsing, one file per
  sample, and calls are cached.
- `n_samples=5` per document. Mean and range, never a single draw:
  several phase 1 document-level findings did not survive resampling.
- Degenerate output is detected per file, against that file's own
  longest legitimate run of consecutive boundaries, and reported
  separately rather than folded into the aggregate.
- Metrics match their published definitions and are validated against an
  external implementation. The fast WindowDiff is proved bit-identical
  to the naive one on 10,000 random pairs.

## Layout

- `masses.py`, `metrics.py` — the representation and the metrics.
- `disrpt_reader.py`, `run_eval.py`, `run_eval_fewshot.py` — phase 1.
- `sbcsae_reader.py`, `sbcsae_tokenizer.py` — reading and tokenising
  SBCSAE; the decisions behind every rule are in
  `reports/phase2_data.md` and `reports/phase2_tokeniser.md`.
- `sbcsae_llm.py`, `sbcsae_windows.py`, `sbcsae_scoring.py`,
  `sbcsae_baselines.py` — rendering, windowing, scoring, baselines.
- `reports/` — every stage report and the figures behind it.
- `tests/` — including whole-corpus invariants that run on every suite.

## Data

No corpus data is in this repository. SBCSAE is distributed by UCSB
under CC Attribution-NoDerivatives 3.0 US; processed transcript text is
not published here, only counts, scores and short illustrative
quotations. Required citation:

> Du Bois, John W. (2000, 2003, 2005, 2005). Santa Barbara Corpus of
> Spoken American English, Parts 1–4. Philadelphia: Linguistic Data
> Consortium.

CID has its own distribution terms and will not be published in any
form.

## Earlier work

Doctoral code on the same questions:
https://github.com/klimpe/speech-units

> Peshkov, K. & Prévot, L. (2014). Segmentation evaluation metrics, a
> comparison grounded on prosodic and discourse units. LREC'14,
> Reykjavik, pp. 321–325.

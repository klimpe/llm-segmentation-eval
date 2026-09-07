# Project context

## Who I am

I'm a computational linguist. My doctoral work at the Laboratoire Parole et
Langage (Aix-Marseille University, 2012–2018) was on discourse unit
segmentation in spontaneous spoken French, and I published on segmentation
evaluation metrics:

  Peshkov, K. & Prévot, L. (2014). Segmentation evaluation metrics, a
  comparison grounded on prosodic and discourse units. LREC'14, Reykjavik,
  pp. 321–325.
  http://www.lrec-conf.org/proceedings/lrec2014/pdf/931_Paper.pdf

My old research code is published at https://github.com/klimpe/speech-units
(Python 2, unmaintained, reference only — see "Do not port" below).

I know these metrics well. Do not explain WindowDiff, Boundary Similarity,
kappa, or inter-annotator agreement to me. Do tell me when an implementation
detail is wrong.

## What I'm building

A pipeline that has an LLM segment transcripts into discourse units, measures
the gap against human annotation with standard segmentation metrics, and —
this is the point of the project — relates that score to inter-annotator
agreement. Most evaluations of this kind publish a score with no human ceiling,
which makes the number uninterpretable: you cannot tell whether the model is
far from human performance or already at the ceiling.

Three phases, in order:

1. **DISRPT** (https://github.com/disrpt) — open, unified format across many
   corpora, published system scores from the 2019/2021/2023/2025 shared tasks.
   Text only, no audio. This phase is for building and validating the pipeline
   and getting a baseline comparison against trained systems.

2. **Santa Barbara Corpus (SBCSAE)** — free, ~20h of spontaneous conversational
   American English, transcribed at the level of intonation units and
   time-aligned to audio. This phase adds spoken data and makes prosodic
   questions possible.

3. **CID (Corpus of Interactional Data)** — spontaneous French conversation,
   access pending from the LPL. Adds French, audio, and inter-annotator
   agreement measures I computed myself during the doctorate. Data will NOT be
   published; only code and aggregate results.

The hypothesis to test: the model fails specifically where prosodic
information is decisive and absent from the transcript.

## Core data contract

Everything in the pipeline speaks one intermediate representation: **segment
masses**, a list of segment lengths in atomic units.

```python
# 10 tokens, boundaries after token 3 and token 7
masses = [3, 4, 3]
assert sum(masses) == n_tokens
```

The atomic unit is a token in phases 1–2. It was a time interval in my old
code; the metrics do not care, but scores are not comparable across different
atomic units — this must be stated in any results table.

Two functions define the contract:

```python
def flags_to_masses(flags: list[bool]) -> list[int]:
    """flags[i] is True if a new segment begins at token i."""

def masses_to_boundaries(masses: list[int]) -> set[int]:
    """Positions after which a boundary falls. len == len(masses) - 1."""
```

Every reader (DISRPT, SBCSAE, LLM output) produces masses. Everything
downstream consumes masses only.

## Build order

Build and verify each step in isolation before starting the next. Stop after
each and show me the result.

1. **Representation.** The two functions above, plus round-trip tests.
2. **One reader, one file.** Parse a single DISRPT document into masses.
   Verify `sum(masses) == n_tokens` and check the segment count by eye against
   the source file. Do not write a generic multi-corpus loader yet.
3. **Metrics on synthetic data.** Implement boundary precision/recall,
   WindowDiff, and Boundary Similarity. Validate them by perturbation: take a
   reference, damage it in known ways (shift boundaries by one, delete a
   boundary, add a spurious one, randomise entirely), and confirm each metric
   responds proportionally. This mirrors the `damaged.py` approach from the
   2014 paper. If a metric misbehaves here, the bug is in the metric, not in
   the model.
4. **LLM on one document.** Prompt, call, parse. See constraints below.
5. **Scale.** Full dataset, results table, comparison against published
   DISRPT system scores.

## Constraints

**Python 3.** Do not port the old Python 2 code from speech-units. Reimplement
the metrics cleanly. The old repository is a reading reference for the
approach, nothing more.

**Alignment is mandatory.** The model must return boundaries as token or line
indices, never as rewritten text with inserted markers. After parsing any model
output, assert `sum(hyp_masses) == sum(ref_masses)`. On mismatch, set the
document aside and report it — never compute a metric on misaligned data. Track
how many documents fail this check; it is a result in itself.

**Persist raw model output to disk** before parsing, one file per document.
These are needed to diagnose surprising numbers later.

**Cache API calls.** Do not re-query the model for a document already
processed unless explicitly asked.

**No corpus data in git.** Corpora go in a gitignored directory. CID data in
particular has its own distribution terms and must never be committed.

## What not to do

- Do not refactor or "improve" the metric definitions to be more elegant. They
  must match the published definitions exactly.
- Do not silently drop documents that fail alignment checks. Report them.
- Do not aggregate scores across genres or corpora into a single headline
  number without also reporting the per-subset breakdown. Evaluating by data
  subset rather than in aggregate is a deliberate methodological choice here.
- Do not add a web UI, a CLI framework, or packaging. This is research code
  that produces tables.

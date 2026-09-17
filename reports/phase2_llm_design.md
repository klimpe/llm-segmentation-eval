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

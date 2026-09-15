# Phase 2 — SBCSAE data survey (Step 1, read-only)

No code written yet. This inspects the actual corpus (one real file downloaded
and read directly, not just documentation) to answer the brief's key
question before a reader is built.

## Key question: what human segmentation does this corpus give us?

**Intonation units, and nothing finer.** Each transcript line is one
intonation unit (IU) with its own start/end timestamp. This is not a
document-internal choice we can work around — it is how the corpus was
transcribed: Du Bois's transcription system, which SBCSAE uses, defines the
IU as "delimited by carriage returns" (Du Bois, "Outline of Discourse
Transcription," in *Talking Data: Transcription and Coding in Discourse
Research*, ed. Edwards & Lampert, 1993). There is no EDU/RST-style discourse
segmentation anywhere in the corpus, gold or otherwise.

**This changes what phase 2 measures, exactly as flagged in the brief.**
Phase 1 scored the model against discourse-unit boundaries (RST-DT
convention: clause-level, coordinated clauses usually split, etc.). Phase 2
can only score the model against *prosodic* unit boundaries — a stretch of
speech under one intonation contour, cued by pitch reset and final-syllable
lengthening, not by syntactic/rhetorical structure. A boundary precision/
recall/F1 number from phase 2 answers "does the model's segmentation align
with where a human transcriber heard a pitch contour end," not "does it
align with where a human would place a discourse unit." These can
correlate — intonation units and clauses often coincide — but they are not
the same target, and the report must say so wherever phase 2 numbers appear,
not just once in a methods section.

## Transcript formats: two, use `.trn`

Every file ships as both `.trn` and `.cha`. Downloaded and diffed `SBC001` in
both formats directly.

**`.trn`** (tab-separated, LDC Callhome-style): each line is
`<start> <end>\t<speaker or 8 spaces>\t<text>`. One line = one IU. Speaker
code appears only on the first IU of a turn; continuation IUs from the same
speaker have a blank (8-space) speaker field. Confirmed real tabs (not
space-aligned) via `cat -A`. This mirrors DISRPT's `.tok`: flat, one
record per line, mechanically parseable, no annotation-tool-specific syntax.

**`.cha`** (CHAT/CLAN format): same IUs, but grouped under `*SPEAKER:`
turn headers with tab-indented continuation lines for subsequent IUs in the
same turn (so "which IU" requires tracking the last-seen speaker tag, not
just splitting on tabs), CHAT-specific notation (`⌈⌉`/`⌊⌋` for overlap
instead of `[ ]`, `+/.`/`+...` for cutoffs instead of `--`, `(..)`/`(.)` for
pauses instead of `...`, IPA characters for glottal stops), and a metadata
header block (`@Participants`, `@ID`, `@Comment` — the last carries the
per-file free-text description, e.g. `SBC001`: *"Actual Blacksmithing... a
conversation recorded in rural Hardin, Montana..."*). Timestamps are the
same IU spans, just in milliseconds appended inline (`9210_9520`) rather
than a leading tab-separated field in seconds.

**Recommendation: read `.trn`.** Same information, simpler grammar, no CHAT
convention layer to reimplement. `.cha`'s only advantage is the `@Comment`
free-text description per file, which can be read from a handful of files
directly if per-document description is wanted later.

## Time alignment: IU-level only, not word-level

Confirmed directly: every `.trn` line carries a `start end` pair in seconds
(`0.00 9.21`); nothing finer exists in either format. No per-word timestamps
anywhere in the distribution. Overlapping speech is real and visible in the
timestamps themselves — e.g. in `SBC001`, one speaker's IU spans `21.19–21.74`
while another's spans `21.26–22.24`, genuinely overlapping, not just marked
by bracket notation. The file's line order already linearizes this (the
convention interleaves overlapping IUs in transcription order), so a
single linear sequence per document is available the same way DISRPT's
token order was — but it's worth knowing the underlying timing isn't
strictly sequential before reasoning about it.

## Tokenization: not provided, must be decided in Step 2

DISRPT's `.tok` gave one gold token per line with an explicit
`BeginSeg=Yes` flag — masses fell out directly. SBCSAE gives free running
text per IU with no tokenization and no per-token markup at all. Per
`CLAUDE.md`, phases 1–2 both use the token as the atomic unit (not a time
interval, unlike the old Python 2 code), so Step 2 will need its own
tokenizer (whitespace-split is the obvious default) — and a decision about
what counts as a token, because the transcript text is not clean prose. From
the raw `SBC001.trn`, confirmed present: pause markers (`...`, `..`, `(H)`
breath, `(Hx)`), overlap brackets (`[...]`, numbered for multi-party overlap:
`[2...2]`), uncertain-transcription brackets (`<X ... X>`), prosodic contour
tags (`<YWN ... YWN>`), lengthening marked inline on the word itself
(`s=o`, `ti=red` — not a separate token), truncation (`y- --`), and a
retrace/reduction marker (`~Mae-`). Whitespace-splitting this naively would
count `...`, `(H)`, `--` etc. as "tokens" alongside real words, which is not
obviously correct or obviously wrong — it's a decision to make explicitly in
Step 2 and document, not silently default. `assert_comparable`'s
token-count check means whatever choice is made must be applied identically
to every IU or documents will fail alignment for a spurious reason.

## Genre-equivalent grouping: no controlled field, free text only

No genre/register/topic column exists anywhere in the corpus metadata.
`metadata{1-4}.csv` (in `metadata.zip`) is **speaker** demographic data
(gender, age, hometown, education, occupation, ethnicity) — one row per
speaker, not per document, and not a topic label. The only per-document
description is the free-text `@Comment` in each `.cha` file and the
"Contents and Summaries" listing on the UCSB page, e.g.: *"Face-to-face
conversation recorded in the living room of a private home in Boise,
Idaho... Topics center mostly on their work day."* The corpus is
overwhelmingly one interaction type — face-to-face conversation, with a
minority of phone calls and a handful of other settings (the UCSB page
separately mentions card games, food preparation, on-the-job talk,
classroom lectures, sermons, storytelling, town hall meetings, tour-guide
spiels, scattered across the 60 files, not evenly distributed the way GUM's
12 genres were 2-per-genre). There is no GUM-genre equivalent to break
per-genre scores out by in Step 4. Options, not decided here: skip the
per-genre breakdown and report corpus-level only; or hand-derive a coarse
category (face-to-face / phone / other) from the descriptions, which would
be a manual, judgment-based grouping rather than a corpus-provided one and
should be labeled as such if used.

## Licensing

`SBCSAE by John W. Du Bois is licensed under a Creative Commons
Attribution-No Derivative Works 3.0 United States License` — confirmed from
the UCSB page's own citation section. Free to use with attribution; **no
derivative works** — this is stricter than DISRPT's terms and reinforces
(does not just repeat) the existing "no corpus data in git" rule: it also
means published outputs shouldn't include a modified/re-annotated version of
the transcript text itself. Scores, tables, and short illustrative quotes
for methodology (the way phase 1's report quoted individual DISRPT tokens)
are the kind of use this is meant to allow; redistributing a cleaned or
re-tokenized transcript file would not be.

Required citation (from the same page): Du Bois, John W. (2000, 2003, 2005,
2005). *Santa Barbara Corpus of Spoken American English, Parts 1-4.*
Philadelphia: Linguistic Data Consortium.

## Download

Two distribution channels exist; they are not equivalent in access friction:

- **TalkBank/CABank** (`talkbank.org/ca/access/SBCSAE.html`): described as
  open access, but the bulk-download endpoint
  (`talkbank.org/data/ca/SBCSAE?f=zip`) returned a login modal when fetched
  directly — actual bulk download requires a free TalkBank account and
  agreement to their terms, not just the CC license. Only `.cha` is offered
  here.
- **UCSB's own distribution** (linked from
  `linguistics.ucsb.edu/research/santa-barbara-corpus-spoken-american-english`):
  plain static files, no login, no account. Confirmed working directly:
  `.../sitefiles/research/SBC/SBC001.trn` and `SBC001.cha` downloaded with a
  bare `curl`, no auth. Both a full corpus zip (`SBCorpus.zip`) and a
  transcripts-only CHAT zip (`SBCSAE_chat.zip`) exist at the same path, plus
  `metadata.zip`. Audio is separate, linked via `ucsb.box.com` share links,
  one per file (not needed yet — phase 2 doesn't use audio, per the
  brief's constraints).

**Recommendation: download from UCSB directly (`SBCorpus.zip`), not
TalkBank**, to avoid the account requirement for no benefit — the content is
the same corpus, same license, same citation obligation either way.

## Corpus size

60 files (`SBC001`–`SBC060`), ~249,000 words total across Parts I-IV (source:
UCSB page). One sample file (`SBC001`, "Actual Blacksmithing"): 1,312 IU
lines, ~9,041 whitespace-separated tokens including annotation symbols (so
the real word count is somewhat lower once those are excluded — exact figure
depends on the Step 2 tokenization decision above).

## Open decisions for Step 2 (not resolved here)

1. `.trn`, as recommended above.
2. Tokenization rule for IU text containing pause/breath/overlap/prosody
   markers — needs an explicit, documented convention before any reader is
   written, since it directly determines `sum(masses) == n_tokens`.
3. Whether to attempt a coarse interaction-type grouping for a Step 4
   genre-equivalent breakdown, or report corpus-level only.

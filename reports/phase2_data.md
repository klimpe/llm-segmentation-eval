# Phase 2 — SBCSAE data: format, encoding, and reader verification

Working report. Not for circulation.

---

## 1. Corpus and format

**Corpus.** Santa Barbara Corpus of Spoken American English (SBCSAE), Parts
1-4: 60 files (`SBC001`-`SBC060`), spontaneous conversational American
English, ~249,000 words, transcribed and time-aligned at the level of
intonation units (IUs).

**Format: `.trn`, not `.cha`.** Every file ships as both. `.trn` (LDC
Callhome-style) is one line per IU: `start end`, a tab, the speaker (or
blank, for a line continuing the previous speaker's turn), a tab, the text.
`.cha` (CHAT/CLAN) carries the same information under `*SPEAKER:` turn
headers with tab-indented continuation lines for subsequent IUs in the same
turn, plus CHAT-specific notation (`⌈⌉`/`⌊⌋` for overlap instead of `[ ]`,
`+/.`/`+...` for cutoffs instead of `--`, IPA characters for glottal stops).
Same content, one fewer convention layer to reimplement — `.trn` was chosen
for the same reason DISRPT's `.tok` was chosen over `.conllu` in phase 1.

**Download.** UCSB's own static distribution
(`linguistics.ucsb.edu/research/santa-barbara-corpus-spoken-american-english`),
not TalkBank/CABank. TalkBank's bulk-download endpoint requires a free
account despite being described as open access; UCSB serves the same files
(`SBCorpus.zip`) with a plain, unauthenticated `curl`. Downloaded into
`corpora/sbcsae/` (gitignored, per the standing no-corpus-data-in-git rule).

**Licence: CC BY-ND 3.0 US.** *"SBCSAE by John W. Du Bois is licensed under
a Creative Commons Attribution-No Derivative Works 3.0 United States
License"* (UCSB page's own citation section). Free to use with attribution;
**no derivative works**. Stricter than DISRPT and not just a repeat of the
no-corpus-data-in-git rule: it also means published output must not contain
a re-tokenised or otherwise modified version of the transcript text itself.
Scores, tables, and short illustrative quotations for methodology (as used
throughout this report) are the kind of use this is meant to allow;
redistributing a cleaned or re-tokenised transcript file would not be.

**Required citation.** Du Bois, John W. (2000, 2003, 2005, 2005). *Santa
Barbara Corpus of Spoken American English, Parts 1-4.* Philadelphia:
Linguistic Data Consortium.

---

## 2. What the corpus does and does not annotate

**Intonation units, and nothing finer.** Every `.trn` line is one IU with
its own timestamp. Du Bois's transcription system, which SBCSAE uses,
defines the IU as delimited by carriage returns (Du Bois, "Outline of
Discourse Transcription," in *Talking Data: Transcription and Coding in
Discourse Research*, ed. Edwards & Lampert, 1993). There is no EDU/RST-style
discourse segmentation anywhere in the corpus, gold or otherwise.

**This changes what phase 2 measures, not just the register of the text.**
Phase 1 scored the model against discourse-unit boundaries: clause-level,
coordinated clauses usually split, the RST-DT convention. Phase 2 can only
score the model against *prosodic* unit boundaries — a stretch of speech
under one intonation contour, cued by pitch reset and final-syllable
lengthening, not by syntactic or rhetorical structure. A boundary
precision/recall/F1 number from phase 2 answers "does the model's
segmentation align with where a human transcriber heard a pitch contour
end," not "does it align with where a human would place a discourse unit."
These can correlate — intonation units and clauses often coincide — but they
are not the same target. Every table and claim involving phase 2 figures
must state this, wherever the numbers appear, not once in a methods
section. **Figures from phase 1 and phase 2 are not comparable** for this
reason and also because the atomic unit differs (§4).

---

## 3. Encoding

Two files, and only two, were saved with a different encoding than the rest
of the corpus. Established by exhaustive decode over all 60 files (every
byte, not a sample), not by a `file`-command guess:

```python
ENCODINGS = {
    "SBC060": "cp1252",   # 147 curly apostrophes (0x92) in contractions/possessives
    "SBC037": "latin-1",  # 34 Spanish accented vowels inside <L2 ...> spans
}
```

**`SBC060`: 147× byte `0x92`.** Windows-1252's `’` (curly right single
quote), used as the apostrophe throughout — *"we’re talking," "I’ll tell
you," "o’clock," "didn’t," "It’s."* Confirmed by decoding the whole file as
cp1252 and checking that every instance lands exactly where an apostrophe
belongs.

**`SBC037`: 34× (í×10, ó×3, é×9, á×12).** Genuine Spanish accented
vowels — *Sí, cómo, Qué, más, está/están, periódico, Avelín* — confirmed by
decoding as Latin-1 and reading the result. These sit inside `<L2 ... L2>`
bracket spans: SBCSAE's language-switch marker. `<L2` appears in 14 of 60
files (118 occurrences total), `SBC037` alone accounting for 60 of those — a
substantially bilingual, code-switched English/Spanish conversation, not an
occasional foreign word (§6 covers what this means for phase 2's scope).

All other 58 files are confirmed strict, valid UTF-8, checked by direct
byte-level decode, not inferred from a clean-looking sample.

**NUL bytes: 6, stripped, not reconstructed.** Each sits where a single
letter c/C should be:

| file | line | context |
|---|---|---|
| SBC015 | 225 | `...\x00hurch things.\n176.9` |
| SBC016 | 675 | `...bought \x00ouple pieces here,\n` |
| SBC018 | 399 | `... \x00oming in yesterday,` |
| SBC020 | 270 | `...\x00ontrols our lives,\n` |
| SBC020 | 813 | `...we ... \x00annot find words to` |
| SBC028 | 1164 | `.. really .. \x00orrect,\n1127.400...` |

(`couple`, `coming`, `controls`, `cannot`, `correct` — the missing letter is
obvious in every case.) The byte is deleted; the letter is not
reconstructed. Same principle applied throughout this stage: don't infer
content where the inference costs more than the content is worth. Full
detail in `reports/phase2_nul_bytes.csv`.

**Character inventory: clean.** 93 unique characters across all text fields
in all 60 files, zero alarm characters (no U+FFFD, no bare `\r`, no
`\x00`) — confirming the per-file encoding choices and the NUL-stripping
are both complete and correct. Full inventory in
`reports/phase2_char_inventory.txt`.

---

## 4. Line structure

**Field count is not uniform**, and `SBC001` (used for the initial survey)
is not representative of the corpus's dominant format:

| tab-fields | lines | cause |
|---|---|---|
| 1 | 27 | 9 Du Bois `$` researcher notes (no tab at all) + 18 lines in `SBC013` that are ordinary dialogue but lost their tabs entirely (timestamp and text separated only by spaces) |
| 2 | 1,287 | the speaker field space-glued to the timestamp instead of tab-separated, in some files |
| 3 | 16,401 | the `SBC001`-style baseline: `start end`, speaker, text |
| 4 | 52,344 | the corpus's actual majority format — mostly an extra blank leading or middle field (harmless); 3 lines contain a literal backslash apparently substituting for a lost newline (§6) |
| 5 | 24 | mostly harmless extra blank fields; a handful genuinely put real content one field before an empty final field |

**Parsing rule adopted: one regex, one code path, for every line.**

```python
_HEAD_RE = re.compile(r"^\s*([\d.]+)\s+([\d.]+)\s*(.*)$", re.DOTALL)
```

Capture the two leading floats, then whatever whitespace follows — a tab, a
run of spaces, both, or (for the 18 `SBC013` lines) spaces only — then
whatever's left. If a tab remains in that remainder, the text before it is
the speaker and the text after is candidate text, which may itself still
contain tabs; the real text is the last **non-blank** such field (not
simply the last field — a stray trailing tab otherwise silently drops real
content one field earlier). If more than one non-blank field remains there,
which one is the real text is ambiguous, and the parser raises rather than
guessing (`AmbiguousFieldsError`) — this fired exactly once in the whole
corpus (§6). If no tab remains at all, there was never a separate speaker
field: the whole remainder is text, and the speaker is inherited from
context. No branch on raw tab count anywhere in the logic — the same
regex-and-partition handles every row in the table above.

---

## 5. The `&` analysis

Du Bois §13.1 defines `&` as marking one intonation unit split across
multiple transcript lines — typically because another speaker's turn
interrupts it, and the original speaker resumes later. A trailing `&`
opens; a leading `&` closes (or, with `&` at both ends, continues a chain of
three or more fragments). Pairing was done **by speaker identity, never by
file position** — concurrent interruption threads from different speakers
occur in the data (e.g. `SBC019`: JAN interrupted, then FRANK also
interrupted mid-gap, each resuming separately later).

**61 chains total: 60 same-speaker, 1 cross-speaker.** The one exception,
`SBC011` lines 414-415:

```
572.12  574.56  ANGELA:  (H) And do you know the postage came to more &
574.56  575.17  DORIS:   & ... Than the g- --
575.17  575.93           than the product.
575.93  577.16  ANGELA:  .. more than the product.
```

ANGELA opens; DORIS — a different speaker — closes, and ANGELA then confirms
by repeating "more than the product." This is collaborative sentence
completion, a genuine conversational phenomenon: two speakers, two
intonation contours, and therefore **two IUs, not one**. Merging them into a
single unit would create something nobody actually uttered as one contour —
exactly the error the reference annotation exists to avoid. The `&` is
stripped from both lines and each is kept independent, coded as a named,
one-off exception rather than a general cross-speaker rule:

```python
# SBC011 lines 414-415: collaborative completion across speakers.
# Du Bois §13.1 defines & as marking one IU split across lines; here the
# transcriber used it for "continues the preceding utterance" instead.
# Two speakers, two contours, two IUs.
CROSS_SPEAKER_AMPERSAND = {("SBC011", 414), ("SBC011", 415)}
```

A leading `&` with no open fragment for that speaker still raises unless the
line is in this set — a second instance of the same pattern must surface,
not pass silently.

**What this shows: the `&` symbol is used more broadly in this corpus than
Du Bois's own definition covers**, at least once. That is a fact about this
specific transcription, not an error in the standard, and it was found only
because the parser refused to guess when the "pair by speaker" rule
produced a `RuntimeError` instead of a silent (wrong) merge. A rule that
had instead matched by file position, or by any heuristic tolerant enough
to let this pass quietly, would have merged two speakers' separate
utterances into one fabricated IU without ever raising.

---

## 6. Exclusions

**14 lines excluded, not 13** — the number stated going into this stage was
wrong by one; the actual `$`-note count is 10 (§7 explains why the earlier
manual count found only 9). All 14, in full:

| file | line | category | content |
|---|---|---|---|
| SBC003 | 250 | `$` note | `000000000 000000000 $ COMMA OR PERIOD?` |
| SBC003 | 257 | `$` note | `000000000 000000000 $ CHECK CAPITALIZATION AFTER IU CONTOUR IS ADDED ABOVE` |
| SBC003 | 659 | `$` note | `000000000 000000000 $ COMMA OR PERIOD?` |
| SBC003 | 1023 | `$` note | `000000000 000000000 $ HE SAYS "LAUNDRY MAT"?` |
| SBC003 | 1050 | `$` note | `000000000 000000000 $ LAUNDRYMAT?` |
| SBC003 | 1523 | `$` note | `000000000 000000000 $ HOW TO SHOW THIS AS ONE IU BROKEN BYE PARENTHETICAL EXCLAMATION?` |
| SBC005 | 620 | `$` note | `000000000 000000000 $ COMMA OR PERIOD?` |
| SBC005 | 789 | `$` note | `000000000 000000000 $ COMMA OR PEROID?` |
| SBC011 | 957 | `$` note | `000000000 000000000 $ TEXT ENDS` |
| SBC013 | 1371 | `$` note | `0.00 0.00\t$ INDETERMINATE BETWEEN "TOO" AND "TWO"` |
| SBC004 | 809 | backslash-fused | `...surly,\00:11:47:96 00:11:49:46 708.11 708.71\tSHARON: \t   [I did that].` |
| SBC007 | 631 | backslash-fused | `...a lot anyway.\000000000 000000000 MARY: 1182.90 1186.92\t...he [adores] me.` |
| SBC014 | 1122 | backslash-fused | `...also --\000000000 000000000 1602.72 1604.72\t...requirements by uh,` |
| SBC016 | 1185 | ambiguous fields | `1105.975\t1106.375\tBRAD:\t[\t[(H)] [uh]-- w--` |

Full content (untruncated) in `reports/phase2_excluded_lines.csv`.

**`$` non-transcription lines (10).** Du Bois §14.1 defines `$` as marking a
researcher's note, not spoken content — a marginal comment to self, not an
IU. Excluded on that standard, not on a heuristic guess about what looks
like a note.

**Backslash-fused lines (3).** Each looks like a lost newline that fused
two real lines together — one (`SBC004`) has a second, different
`HH:MM:SS:FF` timecode format nested inside the fused text. Not repaired:
reconstructing what these were requires several assumptions (where exactly
the line break belongs, how to interpret the leftover junk before the real
timestamp, how to handle the nested timecode format) to recover three IUs
out of ~70,000. Excluded and logged instead, so they can be revisited if
anyone wants to.

**Ambiguous fields (1).** `SBC016` line 1185: a stray tab splits an overlap
bracket (`[`) from the rest of the text (`[(H)] [uh]-- w--`), and it isn't
clear which piece is the real content, or how they should be joined. Same
principle as the backslash lines.

**`SBC037` — excluded from phase 2's evaluation scope, separately from the
line-level exclusions above.** This file's IUs parse correctly and are
included in this stage's counts (§7) — the reader has to handle the file
regardless of what happens to it later. But `SBC037` is substantially
bilingual (§3: 60 of the corpus's 118 `<L2` occurrences are in this one
file), and code-switched English/Spanish segmentation is not the same task
as monolingual English segmentation. A single file cannot support a
separate finding about code-switching, and folding it into the monolingual
corpus-level number would silently mix two different tasks into one score.
Excluded from scoring; kept as data, in case a code-switching question is
worth pursuing on its own later.

---

## 7. Arithmetic

```
   70,083  raw lines
-      10  $ non-transcription lines
-       3  backslash-fused lines
-       1  ambiguous-field line
-      62  absorbed by & merge (61 chains, minus the 1 cross-speaker
           exception that stays as 2 IUs; 58 two-fragment chains + 2
           three-fragment chains = 58x1 + 2x2 = 62)
= 70,007
```

Reader's actual output: **70,007.** Matches.

**This is not the number stated going into this stage (69,981), and the
disagreement is real, not a rounding difference — two separate errors in
the earlier manual count:**

1. **70,056 vs. 70,083 raw lines.** The earlier total came from an ad hoc
   script that filtered lines by `len(parts) >= 2` (at least one tab)
   instead of checking non-blank content. That silently dropped all 27
   one-field lines (the `$` notes and the `SBC013` tab-loss lines) from the
   count. 70,083 − 27 = 70,056 exactly — confirmed by reproducing the old
   filter directly, not just by arithmetic coincidence.
2. **9 vs. 10 `$` notes.** The earlier manual search matched the literal
   prefix `"000000000 000000000"`, which is the placeholder timestamp on 9
   of the 10 notes. The 10th (`SBC013` line 1371) uses a different
   placeholder (`0.00 0.00`) and has a real tab before the `$`, so the
   prefix search missed it. The current code doesn't share this weakness:
   it checks the actual parsed `text` field for a leading `$`, after the
   same regex that handles every other line has already isolated it, so it
   found this one without a special case.

Both errors point the same direction (both undercounts), and both
independently explain exactly the gap between 69,981 and 70,007 once
combined with the corrected exclusion count: 70,083 − 10 − 3 − 1 − 62 =
70,007, not 69,981. The corrected arithmetic and the reader's independently
computed output agree exactly; 69,981 does not survive contact with the
full-corpus data.

---

## 8. What this cost

Three checks in this stage were run on a subset before being run on all 60
files, and every correction was material:

- **NUL bytes.** Plain `grep` silently skips files it flags as binary (a
  literal NUL byte trips this). The manual survey found 4 NUL bytes in 3
  files; the actual count is 6, in 5 files. `SBC015` and `SBC028` were
  invisible to the first check entirely.
- **Field structure.** The initial format survey read one file (`SBC001`)
  to establish "3 tab-fields, one line per IU." `SBC001`'s format is not
  the corpus's majority format (§4) — running the same assumption across
  all 60 files surfaced five distinct field-count categories, one of which
  (the `SBC013` tab-loss lines) has *zero* tabs, the opposite of what the
  survey generalised from.
- **Speaker-pairing for `&`.** The rule ("pair by speaker, never by file
  position") was derived from one clean example (`SBC019`'s interleaved
  JAN/FRANK case). It held for 60 of 61 chains corpus-wide but broke on the
  61st (`SBC011`'s collaborative completion) — a real counter-example, not
  a hypothetical one, found only by running the rule against every chain
  rather than trusting the one example it was built from.
- **This report's own arithmetic (§7).** A fourth instance of the same
  pattern, found while writing this section: the raw-line and `$`-note
  totals quoted going into this stage were themselves computed by earlier,
  narrower scripts (a stricter tab-count filter; a literal-prefix search)
  rather than the final unified reader. Both undercounted. Re-deriving the
  arithmetic from the actual CSVs, rather than carrying the previously
  stated numbers forward, is what caught it.

The pattern held four times running: every check confined to a subset of
the corpus — one file, three files, one example, one earlier script — was
wrong in a way that only running it against the full 60 files caught.
Treat any number in this report, or produced later in this project, that
has not been verified against all 60 files as provisional, and say so.

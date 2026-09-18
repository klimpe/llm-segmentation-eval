"""Phase 2 follow-up: does the pilot's condition-B offset asymmetry
(-1: 1112 vs +1: 699 -- reports/phase2_pilot.md's offset-distribution
table; condition A is nearly symmetric) coincide with prosodic cues in
the rendered text?

Hypothesis-side check (not reference-side -- an earlier version of this
script asked whether the TRUE reference boundary nearest a hypothesis
was itself cue-marked; that is a different, more indirect question and
is no longer computed here). The direct question, matching the failure
mode under test ("the model names the word before a cue instead of the
word after it"): for the actual word the model named as a new unit's
start, is a cue rendered immediately AFTER that named word? If the model
systematically names the word before a cue instead of the word after it,
the named word itself should be immediately followed by a cue far more
often than baseline -- and specifically so at offset -1, where the named
word is exactly the word that would be the cue-preceding word under that
error theory.

Reported against a base rate: the share of ALL within-turn-eligible word
positions in the document (every word except each turn's own first word
-- the same restriction the model is asked to obey) that have a cue
immediately after them. Offset -1 is only evidence for the "names the
word before the cue" theory if its share sits FAR above this base rate,
not merely above zero.

Condition A is not reported here: it renders no cues at all
(sbcsae_llm.render_turn_line drops every Cue item unless condition is
B), so "is a cue rendered after the named word" is 0% for every offset
bucket in A by construction -- a structural fact, not a comparison worth
a column.

Reads only the cached raw model output already on disk under
llm_output_sbcsae/ (written by sbcsae_pilot.run_pilot) -- makes NO model
calls, ever. Raises if an expected cache file is missing rather than
falling back to a fresh call.
"""
from __future__ import annotations

from collections import defaultdict

from masses import masses_to_boundaries
from sbcsae_degenerate_threshold import max_consecutive_run, review_policy
from sbcsae_llm import build_document_structure
from sbcsae_pilot import DOC_ID, N_SAMPLES, _cache_path, _core_only, _nearest_signed_offset, _parse_window_response
from sbcsae_reader import CORPUS_DIR, read_trn_document
from sbcsae_tokenizer import Condition, Cue, Word
from sbcsae_windows import assert_boundaries_each_in_one_region, assert_regions_tile, build_score_regions

BUCKET_KEYS = [-3, -2, -1, 0, 1, 2, 3, "beyond"]


def _read_cached_window(doc_id, condition, window_idx, sample_idx, region, turn_boundaries):
    """Parses a cache file that must already exist. Raises FileNotFoundError
    if it doesn't (this script must never call the model), or returns
    ("ok", kept) / ("fail", reason) exactly like sbcsae_pilot._draw_one_window
    would for that same cached content, without ever writing or calling.
    """
    path = _cache_path(doc_id, condition, window_idx, sample_idx)
    if not path.exists():
        raise FileNotFoundError(
            f"missing cached draw {path} -- this script must not call the model; "
            f"run sbcsae_pilot.run_pilot first to populate the cache"
        )
    raw = path.read_text(encoding="utf-8")
    try:
        kept, dropped = _parse_window_response(raw, region, turn_boundaries)
        return "ok", kept
    except ValueError as e:
        return "fail", str(e)


def _cue_after_word_flags(doc) -> dict[int, bool]:
    """after[w] = True iff a Cue item (any kind, in doc.turns' own item
    order -- condition B renders every one of them inline, none dropped)
    appears strictly between global word w and global word w+1. Boundary
    items (never rendered in either condition) are transparent: they
    neither set nor clear the pending-cue flag. Keyed by WORD index (not
    boundary/gap index), since the question here is about a named word,
    not a boundary position. A trailing cue after a turn's own last word
    is not recorded: no word follows it in that turn, so it cannot be
    "immediately after" a nameable word in the next position.
    """
    after: dict[int, bool] = {}
    for turn in doc.turns:
        idx = turn.start_index
        prev_word_idx = None
        pending = False
        for item in turn.items:
            if isinstance(item, Cue):
                pending = True
            elif isinstance(item, Word):
                if prev_word_idx is not None:
                    after[prev_word_idx] = pending
                pending = False
                prev_word_idx = idx
                idx += 1
    return after


def _within_turn_candidate_words(doc) -> list[int]:
    """Every word position a model answer could legitimately name: every
    word in the document except each turn's own first word (turn-initial
    positions are never a valid answer -- sbcsae_llm._IU_DEFINITION,
    sbcsae_scoring.score_document's ValueError for one anyway). This is
    the population the base rate is computed over.
    """
    candidates = []
    for turn in doc.turns:
        for offset in range(1, turn.n_words):  # skip offset 0: the turn's own first word
            candidates.append(turn.start_index + offset)
    return candidates


def analyse_cue_adjacency(doc_id: str = DOC_ID, n_samples: int = N_SAMPLES) -> dict:
    path = CORPUS_DIR / f"{doc_id}.trn"
    real_doc_id, units, *_ = read_trn_document(path)
    doc = build_document_structure(real_doc_id, units)

    regions = build_score_regions(doc.n_tokens)
    assert_regions_tile(regions, doc.n_tokens)
    assert_boundaries_each_in_one_region(regions, masses_to_boundaries(doc.ref_masses), doc.n_tokens)

    cue_after = _cue_after_word_flags(doc)
    ref_within_sorted = sorted(masses_to_boundaries(doc.ref_masses) - doc.turn_boundaries)

    # -- base rate: share of ALL within-turn-eligible word positions in
    # the document with a cue immediately after them -- condition- and
    # draw-independent, computed once over the whole document, not just
    # the positions any particular draw happened to name. --
    candidates = _within_turn_candidate_words(doc)
    base_rate_n = len(candidates)
    base_rate_hits = sum(1 for w in candidates if cue_after.get(w, False))
    base_rate = base_rate_hits / base_rate_n if base_rate_n else float("nan")

    condition = Condition.B  # condition A renders no cues at all -- see module docstring
    draws = {}
    for s in range(n_samples):
        for w, region in enumerate(regions):
            draws[(s, w)] = _read_cached_window(doc_id, condition, w, s, region, doc.turn_boundaries)

    # Reproduce sbcsae_pilot.analyse's auto-flagged (run > 22) exclusion
    # exactly, so this population matches the published offset table.
    auto_flagged_window_pairs = set()
    for (s, w), (status, kept) in draws.items():
        if status != "ok":
            continue
        region = regions[w]
        core = sorted(i - 1 for i in _core_only(kept, region))
        run = max_consecutive_run(core)
        if run > 0 and review_policy(run)["flagged_degenerate"]:
            auto_flagged_window_pairs.add((s, w))

    buckets = defaultdict(lambda: {"total": 0, "cue_after_named_word": 0})

    for (s, w), (status, kept) in draws.items():
        if status != "ok" or (s, w) in auto_flagged_window_pairs:
            continue
        region = regions[w]
        for i in _core_only(kept, region):  # i = the named word, 1-indexed global position
            p = i - 1  # boundary position, for offset bucketing only
            offset = _nearest_signed_offset(p, ref_within_sorted)
            if offset is None:
                continue
            bucket = offset if -3 <= offset <= 3 else "beyond"
            b = buckets[bucket]
            b["total"] += 1
            b["cue_after_named_word"] += int(cue_after.get(i, False))

    per_bucket = {k: dict(buckets[k]) for k in BUCKET_KEYS if k in buckets}
    for k in BUCKET_KEYS:
        per_bucket.setdefault(k, {"total": 0, "cue_after_named_word": 0})

    return {
        "base_rate": base_rate,
        "base_rate_n": base_rate_n,
        "base_rate_hits": base_rate_hits,
        "buckets": per_bucket,
    }


def format_report(result: dict) -> str:
    lines = []
    lines.append(
        "Condition B: share of within-turn hypothesis boundaries whose NAMED "
        "word is immediately followed by a cue, by signed offset from the "
        "nearest reference boundary (same population as the pilot's "
        "offset-distribution table)."
    )
    lines.append(
        f"\nBase rate (all within-turn-eligible word positions in the document "
        f"with a cue immediately after them): {result['base_rate_hits']}/{result['base_rate_n']} "
        f"= {result['base_rate']:.1%}"
    )
    lines.append(f"\n{'offset':>8} {'total':>7} {'cue after named word':>22} {'share':>8} {'vs base rate':>14}")
    for k in BUCKET_KEYS:
        b = result["buckets"][k]
        total = b["total"]
        share = b["cue_after_named_word"] / total if total else float("nan")
        ratio = share / result["base_rate"] if total and result["base_rate"] else float("nan")
        lines.append(
            f"{str(k):>8} {total:>7} {b['cue_after_named_word']:>22} {share:>7.1%} {ratio:>13.2f}x"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    result = analyse_cue_adjacency()
    print(format_report(result))

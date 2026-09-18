"""Phase 2 follow-up: does the pilot's condition-B offset asymmetry
(-1: 1112 vs +1: 699 -- reports/phase2_pilot.md's offset-distribution
table; condition A is nearly symmetric) coincide with prosodic cues in
the rendered text?

For every within-turn hypothesis boundary in the cached SBC039 pilot
draws -- the SAME population as sbcsae_pilot.analyse's
offset_distribution (non-flagged, successful window draws' core-kept
indices only) -- this reports, split by signed offset bucket (-3..+3,
plus 0 and beyond) and by condition, the share immediately FOLLOWED by a
cue in the rendered text (a cue sits between the boundary and the
reported start word, i.e. the cue leads into the new unit) and the share
immediately PRECEDED by one (a cue sits between the boundary and the
word that closes the previous unit).

Reads only the cached raw model output already on disk under
llm_output_sbcsae/ (written by sbcsae_pilot.run_pilot) -- makes NO model
calls, ever. Raises if an expected cache file is missing rather than
falling back to a fresh call.

Condition A renders no cues at all (sbcsae_llm.render_turn_line drops
every Cue item unless condition is B) -- so "in the rendered text", both
shares are 0.0 for every offset bucket in A, by construction. This is
reported as the structural control it is, not a finding: the adjacency
channel this script measures only exists for the model to see in B in
the first place, which is exactly why any offset-bucket skew relative to
cue position can only be a B phenomenon.
"""
from __future__ import annotations

import bisect
from collections import defaultdict

from masses import masses_to_boundaries
from sbcsae_degenerate_threshold import max_consecutive_run, review_policy
from sbcsae_llm import build_document_structure
from sbcsae_pilot import DOC_ID, N_SAMPLES, _cache_path, _core_only, _nearest_signed_offset, _parse_window_response
from sbcsae_reader import CORPUS_DIR, read_trn_document
from sbcsae_tokenizer import Condition, Cue, Word
from sbcsae_windows import assert_boundaries_each_in_one_region, assert_regions_tile, build_score_regions

BUCKET_KEYS = [-3, -2, -1, 0, 1, 2, 3, "beyond"]


def _nearest_ref(p: int, sorted_ref: list[int]) -> int:
    """The reference boundary _nearest_signed_offset(p, sorted_ref) measured
    against -- recomputed here (not returned by that function) so this
    module can also ask "was THAT reference boundary itself cue-marked",
    a question about the true position an erring hypothesis was closest
    to, distinct from cue-adjacency at the hypothesis's OWN (possibly
    wrong) position.
    """
    idx = bisect.bisect_left(sorted_ref, p)
    candidates = []
    if idx < len(sorted_ref):
        candidates.append(sorted_ref[idx])
    if idx > 0:
        candidates.append(sorted_ref[idx - 1])
    return min(candidates, key=lambda r: abs(p - r))


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


def _gap_cue_flags(doc) -> dict[int, bool]:
    """gap[p] = True iff a Cue item (any kind, in doc.turns' own item order
    -- condition-independent: every Cue rendered inline in condition B,
    none of them dropped there) appears strictly between global word p and
    global word p+1 (p=0: before the document's very first word). Boundary
    items (never rendered in either condition) are transparent: they
    neither set nor clear the pending-cue flag.
    """
    gap: dict[int, bool] = {}
    for turn in doc.turns:
        pos = turn.start_index - 1
        pending = False
        for item in turn.items:
            if isinstance(item, Cue):
                pending = True
            elif isinstance(item, Word):
                gap[pos] = pending
                pending = False
                pos += 1
        gap[pos] = pending  # trailing cue(s) after the turn's last word
    return gap


def analyse_cue_adjacency(doc_id: str = DOC_ID, n_samples: int = N_SAMPLES) -> dict:
    path = CORPUS_DIR / f"{doc_id}.trn"
    real_doc_id, units, *_ = read_trn_document(path)
    doc = build_document_structure(real_doc_id, units)

    regions = build_score_regions(doc.n_tokens)
    assert_regions_tile(regions, doc.n_tokens)
    assert_boundaries_each_in_one_region(regions, masses_to_boundaries(doc.ref_masses), doc.n_tokens)

    gap_flags = _gap_cue_flags(doc)
    ref_within_sorted = sorted(masses_to_boundaries(doc.ref_masses) - doc.turn_boundaries)

    result = {}
    for condition in (Condition.A, Condition.B):
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

        buckets = defaultdict(lambda: {"total": 0, "followed": 0, "preceded": 0, "true_boundary_cue_marked": 0})

        for (s, w), (status, kept) in draws.items():
            if status != "ok" or (s, w) in auto_flagged_window_pairs:
                continue
            region = regions[w]
            for i in _core_only(kept, region):
                p = i - 1
                offset = _nearest_signed_offset(p, ref_within_sorted)
                if offset is None:
                    continue
                bucket = offset if -3 <= offset <= 3 else "beyond"
                b = buckets[bucket]
                b["total"] += 1
                if condition is Condition.B:
                    # Only B ever renders a cue -- see module docstring.
                    b["followed"] += int(gap_flags.get(p, False))
                    b["preceded"] += int(gap_flags.get(p - 1, False))
                    # A THIRD, offset-symmetric question, distinct from the
                    # two above: was the TRUE (nearest) reference boundary
                    # this hypothesis is being scored against itself
                    # cue-marked (i.e. would the cue rule have predicted
                    # it)? "followed"/"preceded" above are local to the
                    # hypothesis's own (possibly wrong, for offset != 0)
                    # position; for offset -1 or +1 that is a DIFFERENT gap
                    # from the true boundary's own leading gap, so this is
                    # needed to directly answer "does the true position an
                    # off-by-one error is closest to sit next to a cue".
                    p_ref = _nearest_ref(p, ref_within_sorted)
                    b["true_boundary_cue_marked"] += int(gap_flags.get(p_ref, False))
                # Condition A: all three stay 0 -- its rendered text never
                # contains a cue symbol, by construction.

        result[condition.value] = {k: dict(buckets[k]) for k in BUCKET_KEYS if k in buckets}
        for k in BUCKET_KEYS:
            result[condition.value].setdefault(
                k, {"total": 0, "followed": 0, "preceded": 0, "true_boundary_cue_marked": 0}
            )

    return result


def format_report(result: dict) -> str:
    lines = []
    lines.append(
        "Cue adjacency of within-turn hypothesis boundaries, by signed offset "
        "from the nearest reference boundary (same population as the pilot's "
        "offset-distribution table; shares in parentheses)."
    )
    for cond_key in ("A", "B"):
        lines.append(f"\nCondition {cond_key}:")
        lines.append(f"{'offset':>8} {'total':>7} {'followed':>16} {'preceded':>16} {'true_bnd_cued':>16}")
        for k in BUCKET_KEYS:
            b = result[cond_key][k]
            total = b["total"]
            f_share = b["followed"] / total if total else float("nan")
            p_share = b["preceded"] / total if total else float("nan")
            t_share = b["true_boundary_cue_marked"] / total if total else float("nan")
            lines.append(
                f"{str(k):>8} {total:>7} {b['followed']:>7} ({f_share:6.1%}) {b['preceded']:>7} ({p_share:6.1%}) "
                f"{b['true_boundary_cue_marked']:>7} ({t_share:6.1%})"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    result = analyse_cue_adjacency()
    print(format_report(result))

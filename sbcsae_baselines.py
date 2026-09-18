"""Phase 2: two no-model baselines for the SBCSAE pilot's scores to sit
against -- CLAUDE.md's whole point ("relates that score to inter-annotator
agreement... uninterpretable" for phase 3, but the same logic applies here:
a segmentation score with nothing to compare it to besides another
segmentation score is hard to read) plus the standing instruction to check
any new number against something external before trusting it.

Same scoring as sbcsae_pilot.py -- sbcsae_scoring.score_document,
unchanged, both scopes (all_boundaries, within_turn) -- and the same
600-word-core/100-word-margin windows (sbcsae_windows.py), so these
numbers sit in the same table as the model's. Neither baseline is
context-limited the way the model is (a rule or a random draw doesn't
need to "see" a window to decide), so windowed and whole-document scoring
of the SAME hypothesis are mathematically identical; the windows are used
here only to let a per-window breakdown match the pilot's own tables, not
because either baseline actually needs windowing.

  a) Cue rule (condition B only): a boundary before every word
     immediately preceded (through a run of stacked cues) by a pause
     (".." or "...") or an in-breath ("(H)") -- the exact three cue kinds
     CLAUDE.md's Du Bois-derived tokeniser tiers keep in condition B and
     strip in condition A. Deterministic: one hypothesis per file, not
     resampled.

  b) Random (conditions A and B -- the draw itself does not use cue
     information, so "A" and "B" differ only in which independent set of
     100 random draws was taken, not in method): per window, draw
     within-turn boundary positions uniformly at random, WITHOUT
     replacement, at the same COUNT as that window's own reference
     within-turn boundaries (a density-matched random baseline -- same
     number of predicted boundaries as truth, placed randomly). 100
     draws per window; mean and range, per CLAUDE.md's "Sampling" section
     (never report a single draw as a result, even for a baseline that
     could technically be reproduced exactly by fixing a seed).

Run on SBC039 (the pilot file, for direct comparison) and on all 59
files (SBC037 excluded, per CLAUDE.md). Per-file AND overall tables are
both reported -- CLAUDE.md's per-subset-breakdown rule exists because a
single aggregate number hides where a real effect or a real problem is,
but a full corpus-wide per-file table is explicitly allowed here (unlike
for a real model run, which would be too expensive to run per-file at
this stage) since no model call is involved.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path
from statistics import mean

from masses import boundaries_to_masses, masses_to_boundaries
from sbcsae_llm import DocumentStructure, build_document_structure
from sbcsae_reader import CORPUS_DIR, iter_trn_documents, read_trn_document
from sbcsae_scoring import score_document
from sbcsae_tokenizer import Cue, Word
from sbcsae_windows import ScoreRegion, build_score_regions

EXCLUDE_FILES = {"SBC037"}
CUE_TRIGGER_KINDS = {"pause_short", "pause_long", "breath_in"}
N_RANDOM_DRAWS = 100
RANDOM_SEED = 20260918  # fixed for reproducibility across runs; not a tuning choice


def cue_rule_boundaries(doc: DocumentStructure) -> set[int]:
    """Global within-turn boundary positions (p, "after token p" space)
    predicted by the cue rule: a boundary immediately before a word iff
    that word was immediately preceded by a pause_short/pause_long/
    breath_in cue (any stacked run of cues counts if at least one member
    is a trigger kind -- e.g. ".. (H)" before a word fires on either
    cue). Never predicts a turn's own first word (not a legitimate
    within-turn answer, matching what the model itself is asked for and
    what score_document rejects).
    """
    boundaries: set[int] = set()
    for turn in doc.turns:
        pos = turn.start_index
        pending_trigger = False
        first_word_seen = False
        for item in turn.items:
            if isinstance(item, Cue):
                if item.kind in CUE_TRIGGER_KINDS:
                    pending_trigger = True
            elif isinstance(item, Word):
                if first_word_seen and pending_trigger:
                    boundaries.add(pos - 1)
                pending_trigger = False
                first_word_seen = True
                pos += 1
    return boundaries


def _local_within_turn_inputs(doc: DocumentStructure, region: ScoreRegion):
    """Same local reindexing as sbcsae_pilot._local_region_inputs (not
    imported from there to keep this module runnable standalone without
    pulling in the pilot's model-calling machinery): local_ref_masses,
    local_turn_boundaries, lo (global offset), for one window's score
    core.
    """
    lo, hi = region.score_start, region.score_end
    local_n = hi - lo + 1
    ref_boundaries = masses_to_boundaries(doc.ref_masses)
    local_ref_boundaries = {p - (lo - 1) for p in ref_boundaries if lo <= p <= hi - 1}
    local_ref_masses = boundaries_to_masses(local_ref_boundaries, local_n)
    local_turn_boundaries = {p - (lo - 1) for p in doc.turn_boundaries if lo <= p <= hi - 1}
    return local_ref_masses, local_turn_boundaries, lo


def cue_rule_score(doc: DocumentStructure) -> dict:
    """Whole-file score_document result for the cue rule's global
    hypothesis. Windowing this hypothesis first and reassembling would
    give the identical result (the rule has no window-context dependence
    at all), so this scores the whole document directly.
    """
    boundaries = cue_rule_boundaries(doc)
    hyp_indices = [p + 1 for p in boundaries]
    return score_document(doc.ref_masses, doc.turn_boundaries, hyp_indices)


def random_baseline_window_draws(
    doc: DocumentStructure, regions: list[ScoreRegion], n_draws: int, rng: random.Random
) -> list[dict]:
    """n_draws whole-file scores, each built by, independently per window,
    drawing as many within-turn boundary positions as the reference has
    in that window, uniformly at random from the window's own candidate
    positions (every local position except the window's own turn
    boundaries -- those are never a legitimate prediction). Density is
    matched PER WINDOW, not once for the whole document, so a
    high-density window (many short IUs) draws proportionally more random
    boundaries than a low-density one, mirroring how the reference itself
    varies across the document.
    """
    # Per-region candidate pool and draw count are the same on every draw
    # (only the random sample itself changes) -- computed once here, not
    # inside the n_draws loop, since masses_to_boundaries/list-building
    # cost the same 100x over otherwise for no reason.
    per_region = []
    for region, (local_ref_masses, local_turn_boundaries, lo) in zip(
        regions, (_local_within_turn_inputs(doc, r) for r in regions)
    ):
        local_n = sum(local_ref_masses)
        local_ref_within = masses_to_boundaries(local_ref_masses) - local_turn_boundaries
        candidates = [p for p in range(1, local_n) if p not in local_turn_boundaries]
        n_to_draw = min(len(local_ref_within), len(candidates))
        per_region.append((candidates, n_to_draw, lo))

    scores = []
    for _ in range(n_draws):
        hyp_indices: list[int] = []
        for candidates, n_to_draw, lo in per_region:
            drawn = rng.sample(candidates, n_to_draw) if n_to_draw else []
            hyp_indices.extend(p + lo for p in drawn)  # local p -> global i = p + lo (== global p+1, lo=score_start)
        scores.append(score_document(doc.ref_masses, doc.turn_boundaries, hyp_indices))
    return scores


def _mean_range(values: list[float]) -> tuple[float, float, float]:
    return (mean(values), min(values), max(values)) if values else (float("nan"), float("nan"), float("nan"))


def _summarise_draws(scores: list[dict], scope: str) -> dict:
    out = {}
    for metric in ("precision", "recall", "f1", "boundary_count_ratio", "boundary_similarity", "window_diff"):
        vals = [sc[scope][metric] for sc in scores if sc[scope][metric] is not None]
        out[metric] = _mean_range(vals)
    return out


def per_file_baselines(doc_id: str, units, rng: random.Random) -> dict:
    doc = build_document_structure(doc_id, units)
    regions = build_score_regions(doc.n_tokens)

    cue_score = cue_rule_score(doc)
    random_scores = random_baseline_window_draws(doc, regions, N_RANDOM_DRAWS, rng)

    return {
        "doc_id": doc_id,
        "n_tokens": doc.n_tokens,
        "cue_rule": cue_score,
        "random": {
            "within_turn": _summarise_draws(random_scores, "within_turn"),
            "all_boundaries": _summarise_draws(random_scores, "all_boundaries"),
        },
    }


def _fmt_mean_range(mr: tuple[float, float, float]) -> str:
    m, lo, hi = mr
    return f"{m:.4f} [{lo:.4f}, {hi:.4f}]"


def write_report(per_file: list[dict], path: Path) -> None:
    lines = []
    lines.append("# Phase 2 no-model baselines: cue rule and density-matched random")
    lines.append("")
    lines.append(
        "Counts and scores only -- no transcript text. Target is intonation-unit "
        "(prosodic), not discourse-unit, segmentation (CLAUDE.md's phase 2 framing). "
        "Same scoring (sbcsae_scoring.score_document, unchanged) and windows "
        "(sbcsae_windows.py) as the LLM pilot (reports/phase2_pilot.md) -- see this "
        "module's own docstring for why windowing does not change either baseline's "
        "score. Random baseline: 100 draws per file, density-matched per window; "
        f"fixed seed {RANDOM_SEED}."
    )
    lines.append("")
    lines.append(f"{len(per_file)} files (59 expected, SBC037 excluded).")
    lines.append("")

    lines.append("## Per file")
    lines.append("")
    lines.append(
        "| file | n_tokens | cue rule within_turn F1 | cue rule all_boundaries F1 | "
        "random within_turn F1 mean [range] | random all_boundaries F1 mean [range] |"
    )
    lines.append("|---|---|---|---|---|---|")
    for row in per_file:
        cue = row["cue_rule"]
        rnd = row["random"]
        lines.append(
            f"| {row['doc_id']} | {row['n_tokens']} | {cue['within_turn']['f1']:.4f} | "
            f"{cue['all_boundaries']['f1']:.4f} | "
            f"{_fmt_mean_range(rnd['within_turn']['f1'])} | "
            f"{_fmt_mean_range(rnd['all_boundaries']['f1'])} |"
        )
    lines.append("")

    lines.append("## Overall (macro mean across files, then range across files)")
    lines.append("")
    for label, key, scope in (
        ("Cue rule, within_turn", "cue_rule", "within_turn"),
        ("Cue rule, all_boundaries", "cue_rule", "all_boundaries"),
        ("Random, within_turn", "random", "within_turn"),
        ("Random, all_boundaries", "random", "all_boundaries"),
    ):
        for metric in ("precision", "recall", "f1", "boundary_count_ratio", "boundary_similarity"):
            if key == "cue_rule":
                vals = [row[key][scope][metric] for row in per_file if row[key][scope][metric] is not None]
            else:
                vals = [row[key][scope][metric][0] for row in per_file]  # mean-of-100-draws per file, then macro mean
            m, lo, hi = _mean_range(vals)
            lines.append(f"- {label} {metric}: mean {m:.4f}, range across files [{lo:.4f}, {hi:.4f}] (n={len(vals)})")
    lines.append("")
    lines.append(
        "- all_boundaries and within_turn are not comparable to each other "
        "(sbcsae_scoring.NON_COMPARABILITY_NOTE)."
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


CSV_HEADER = [
    "file", "n_tokens",
    "cue_rule_within_turn_f1", "cue_rule_all_boundaries_f1",
    "random_within_turn_f1_mean", "random_within_turn_f1_lo", "random_within_turn_f1_hi",
    "random_all_boundaries_f1_mean", "random_all_boundaries_f1_lo", "random_all_boundaries_f1_hi",
]


def _csv_row(row: dict) -> list[str]:
    cue = row["cue_rule"]
    rnd = row["random"]
    wt_m, wt_lo, wt_hi = rnd["within_turn"]["f1"]
    ab_m, ab_lo, ab_hi = rnd["all_boundaries"]["f1"]
    return [
        row["doc_id"], row["n_tokens"],
        f"{cue['within_turn']['f1']:.4f}", f"{cue['all_boundaries']['f1']:.4f}",
        f"{wt_m:.4f}", f"{wt_lo:.4f}", f"{wt_hi:.4f}",
        f"{ab_m:.4f}", f"{ab_lo:.4f}", f"{ab_hi:.4f}",
    ]


def main():
    rng = random.Random(RANDOM_SEED)

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    per_file = []

    # One row written and flushed to disk per file, as it is computed --
    # not accumulated and written only at the end. This is a ~59-file,
    # whole-corpus run with a 100-draw random baseline per file
    # (previously "the slowest script in the pipeline", reports/
    # phase2_baselines.md's own docstring); buffering every row until the
    # last file means a run killed partway (or just watched) shows
    # nothing on disk for files already computed. The markdown summary
    # (write_report) still needs the complete list and is written once at
    # the end, since it is a genuine final aggregate, not a per-file row.
    with open(reports_dir / "phase2_baselines_per_file.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        f.flush()

        # SBC039 first (the pilot file), then the rest of the corpus in file order.
        sbc039_path = CORPUS_DIR / "SBC039.trn"
        _, sbc039_units, *_ = read_trn_document(sbc039_path)
        docs = [("SBC039", sbc039_units)]
        docs.extend(
            (doc_id, units)
            for doc_id, units, *_ in iter_trn_documents()
            if doc_id not in EXCLUDE_FILES and doc_id != "SBC039"
        )

        for doc_id, units in docs:
            row = per_file_baselines(doc_id, units, rng)
            per_file.append(row)
            w.writerow(_csv_row(row))
            f.flush()
            print(f"  {doc_id}: cue rule within_turn F1 {row['cue_rule']['within_turn']['f1']:.4f}")

    write_report(per_file, reports_dir / "phase2_baselines.md")
    print(f"Wrote reports/phase2_baselines_per_file.csv and reports/phase2_baselines.md ({len(per_file)} files)")


if __name__ == "__main__":
    main()

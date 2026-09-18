"""Phase 2 follow-up, step 3: rerun SBC039 condition B only, n_samples=5,
with the clarified prompt (sbcsae_llm._IU_DEFINITION now states a
reported position is the first word of the new unit, never the last
word of the previous one -- see reports/phase2_llm_design.md and
sbcsae_cue_adjacency.py's finding that motivated it).

Writes into a SEPARATE cache (llm_output_sbcsae_rerun_b/, gitignored),
never touching the original pilot's llm_output_sbcsae/ cache, so both
runs stay independently reproducible and comparable. This is the ONLY
script in this follow-up session that calls the model -- everything else
reads cache already on disk.

Compares, against the original cached B draws (reports/phase2_pilot.md):
offset distribution, within-turn precision/recall/F1 (mean/range,
auto-flagged draws excluded from the aggregate exactly as
sbcsae_pilot.analyse already does), and degenerate-run classification.
"""
from __future__ import annotations

from pathlib import Path
from statistics import mean

from sbcsae_pilot import DOC_ID, N_SAMPLES, OUTPUT_DIR, analyse, run_pilot
from sbcsae_tokenizer import Condition

RERUN_OUTPUT_DIR = Path("llm_output_sbcsae_rerun_b")


def _mean_range(values: list[float]) -> tuple[float, float, float]:
    return (mean(values), min(values), max(values)) if values else (float("nan"), float("nan"), float("nan"))


def _within_turn_prf_summary(b: dict) -> dict:
    scores = b["whole_file_scores"]
    out = {}
    for metric in ("precision", "recall", "f1"):
        vals = [sc["within_turn"][metric] for sc in scores]
        out[metric] = _mean_range(vals)
    return out


def _degenerate_summary(b: dict) -> list[dict]:
    return [
        {"sample": f["sample"], "window": f["window"], "run_length": f["run_length"], "flagged": f["flagged_degenerate"]}
        for f in b["degenerate_flags"]
    ]


def main():
    print("Rerunning SBC039, condition B, n_samples=5, clarified prompt -> "
          f"{RERUN_OUTPUT_DIR}/ (fresh model calls for any cache miss)...")
    rerun_pilot = run_pilot(
        doc_id=DOC_ID, n_samples=N_SAMPLES, conditions=(Condition.B,), output_dir=RERUN_OUTPUT_DIR
    )
    rerun_result = analyse(rerun_pilot)

    print(f"Reading original cached B draws from {OUTPUT_DIR}/ (no fresh calls; cache already complete)...")
    original_pilot = run_pilot(
        doc_id=DOC_ID, n_samples=N_SAMPLES, conditions=(Condition.B,), output_dir=OUTPUT_DIR
    )
    original_result = analyse(original_pilot)

    print("\n" + "=" * 70)
    print("Offset distribution, within-turn boundaries (0 = exact match)")
    print("=" * 70)
    header = f"{'offset':>8} {'-3':>6} {'-2':>6} {'-1':>6} {'0':>6} {'+1':>6} {'+2':>6} {'+3':>6} {'beyond':>7} {'total':>7}"
    print(header)
    for label, result in (("original B", original_result), ("rerun B   ", rerun_result)):
        od = result["B"]["offset_distribution"]
        counts = od["counts"]
        row = " ".join(f"{counts[k]:>6}" for k in range(-3, 4))
        print(f"{label:>8} {row} {od['n_beyond_range']:>7} {od['n_total']:>7}")

    print("\n" + "=" * 70)
    print("Within-turn precision/recall/F1, mean [range] over non-flagged samples")
    print("=" * 70)
    for label, result in (("original B", original_result), ("rerun B   ", rerun_result)):
        b = result["B"]
        summary = _within_turn_prf_summary(b)
        n = len(b["whole_file_scores"])
        print(f"{label} (n={n} samples, {len(b['auto_flagged_samples'])} auto-flagged excluded):")
        for metric, (m, lo, hi) in summary.items():
            print(f"    {metric}: mean {m:.4f}, range [{lo:.4f}, {hi:.4f}]")

    print("\n" + "=" * 70)
    print("Degenerate-output flags (run > 11; * = auto-flagged, run > 22)")
    print("=" * 70)
    for label, result in (("original B", original_result), ("rerun B   ", rerun_result)):
        flags = _degenerate_summary(result["B"])
        print(f"{label}:")
        if not flags:
            print("    None.")
        for f in flags:
            star = "*" if f["flagged"] else ""
            print(f"    sample {f['sample']}, window {f['window']}: run length {f['run_length']}{star}")

    print("\n" + "=" * 70)
    print("Parse/alignment failures and turn-initial drops")
    print("=" * 70)
    for label, result in (("original B", original_result), ("rerun B   ", rerun_result)):
        b = result["B"]
        print(
            f"{label}: {b['n_failed']} of {b['total_window_draws']} window draws failed to parse/align; "
            f"turn-initial dropped per sample: {b['dropped_turn_initial_per_sample']}"
        )


if __name__ == "__main__":
    main()

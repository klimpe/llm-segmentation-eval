"""Phase 2, batch-1 follow-up: does a smaller window (400 words / 300
scored core) reduce SBC053's collapse rate, compared to the standard
800/600 windows already cached for it?

SBC053 was selected for this test because it is the worst-collapsing
batch-1 file (condition A: 37.1% collapse rate under the new per-file
rule, only 1 of 5 samples not auto-flagged under the old one --
reports/phase2_llm_design.md S14). **Selecting the single most extreme
file and then testing an intervention on IT SPECIFICALLY means any
apparent improvement is expected to regress toward the mean on its own,
by construction, independent of whether the intervention does anything
real.** This is directional evidence only, not a finding that would
generalise to other files, and is reported that way throughout.

Model calls: yes -- this is the one script in this session's work that
calls the model (n_samples=5, both conditions, 400-word windows, a
fresh and separate cache -- llm_output_sbcsae_sbc053_400w/, never
touching the existing 800/600 cache for SBC053 in
llm_output_sbcsae_batch1/, which is only read, not written, here).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean

from sbcsae_degenerate_per_file import classify_window_runs, collapse_metrics
from sbcsae_llm import build_document_structure
from sbcsae_pilot import analyse, run_pilot
from sbcsae_reader import CORPUS_DIR, read_trn_document
from sbcsae_tokenizer import Condition

DOC_ID = "SBC053"
N_SAMPLES = 5
OLD_OUTPUT_DIR = Path("llm_output_sbcsae_batch1")
NEW_OUTPUT_DIR = Path("llm_output_sbcsae_sbc053_400w")
OLD_CORE, OLD_MARGIN = 600, 100
NEW_CORE, NEW_MARGIN = 300, 50


def _position_bucket(local_start: int, core: int) -> int:
    """Which third of the CORE local_start (a local, 1-indexed word
    position within its score region) falls in -- proportional to core
    size, so a 300-word core's thirds (100 words each) are comparable to
    a 600-word core's (200 words each), not literally the same fixed
    200-word chunks.
    """
    third = core // 3
    return min((local_start - 1) // third, 2)


def summarise(doc_id: str, units, n_tokens: int, core: int, margin: int, output_dir: Path, n_samples: int = N_SAMPLES):
    pilot = run_pilot(
        doc_id=doc_id, n_samples=n_samples, conditions=(Condition.A, Condition.B),
        output_dir=output_dir, core=core, margin=margin,
    )
    analysis = analyse(pilot)
    region_by_window = dict(enumerate(pilot["regions"]))

    out = {}
    for cond_key in ("A", "B"):
        records = classify_window_runs(doc_id, units, analysis[cond_key], core=core, margin=margin)
        metrics = collapse_metrics(records, analysis[cond_key]["total_window_draws"], n_samples, n_tokens)

        buckets = Counter()
        for rec in records:
            if not rec["new_degenerate"]:
                continue
            region = region_by_window[rec["window"]]
            local_start = rec["span_start"] - (region.score_start - 1)
            buckets[_position_bucket(local_start, core)] += 1

        wt_f1 = [sc["within_turn"]["f1"] for sc in analysis[cond_key]["whole_file_scores"]]

        out[cond_key] = {
            "collapse_rate": metrics["collapse_rate"],
            "share_words_in_runs": metrics["share_words_in_runs"],
            "n_degenerate_draws": metrics["n_degenerate_draws"],
            "total_window_draws": metrics["total_window_draws"],
            "within_turn_f1_mean": mean(wt_f1) if wt_f1 else float("nan"),
            "within_turn_f1_range": (min(wt_f1), max(wt_f1)) if wt_f1 else (float("nan"), float("nan")),
            "n_samples_in_aggregate": len(wt_f1),
            "position_buckets": dict(buckets),
        }
    return out


def format_comparison(old: dict, new: dict) -> str:
    lines = [
        "SBC053 was selected as the single worst-collapsing batch-1 file -- any change",
        "below regresses toward the mean by construction and is directional only, not a",
        "finding that would generalise to the other 9 files.",
        "",
    ]
    for cond_key in ("A", "B"):
        o, n = old[cond_key], new[cond_key]
        lines.append(f"Condition {cond_key}:")
        lines.append(f"  {'':>26} {'800/600 (cached)':>18} {'400/300 (new)':>18}")
        lines.append(f"  {'collapse_rate':>26} {o['collapse_rate']:>17.1%} {n['collapse_rate']:>18.1%}")
        lines.append(f"  {'share_words_in_runs':>26} {o['share_words_in_runs']:>17.2%} {n['share_words_in_runs']:>18.2%}")
        old_frac = f"{o['n_degenerate_draws']}/{o['total_window_draws']}"
        new_frac = f"{n['n_degenerate_draws']}/{n['total_window_draws']}"
        lines.append(f"  {'degenerate/total draws':>26} {old_frac:>18} {new_frac:>18}")
        lines.append(f"  {'within_turn F1 mean':>26} {o['within_turn_f1_mean']:>17.4f} {n['within_turn_f1_mean']:>18.4f}")
        o_range = f"[{o['within_turn_f1_range'][0]:.4f}, {o['within_turn_f1_range'][1]:.4f}]"
        n_range = f"[{n['within_turn_f1_range'][0]:.4f}, {n['within_turn_f1_range'][1]:.4f}]"
        lines.append(f"  {'within_turn F1 range':>26} {o_range:>18} {n_range:>18}")
        lines.append(f"  {'n samples in aggregate':>26} {o['n_samples_in_aggregate']:>17} {n['n_samples_in_aggregate']:>18}")
        lines.append(f"  degenerate-run start, by third of core (new rule only): "
                      f"800/600={o['position_buckets']}  400/300={n['position_buckets']}")
        lines.append("")
    return "\n".join(lines)


def main():
    path = CORPUS_DIR / f"{DOC_ID}.trn"
    _, units, *_ = read_trn_document(path)
    n_tokens = build_document_structure(DOC_ID, units).n_tokens

    print(f"Reading cached 800/600 draws for {DOC_ID} (no model calls)...")
    old = summarise(DOC_ID, units, n_tokens, OLD_CORE, OLD_MARGIN, OLD_OUTPUT_DIR)

    print(f"Running {DOC_ID} with 400-word windows / 300-word cores "
          f"(separate cache, model calls for any miss)...")
    new = summarise(DOC_ID, units, n_tokens, NEW_CORE, NEW_MARGIN, NEW_OUTPUT_DIR)

    print()
    print(format_comparison(old, new))


if __name__ == "__main__":
    main()

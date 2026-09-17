"""Phase 2: dry run of the windowed LLM segmentation prompt on one file,
no model call. Prints window count and estimated prompt size under both
conditions, and the full prompt text of window 1 under each -- terminal
output only, nothing written to disk (the rendered prompt is real,
licensed transcript text and must not be committed).

Zero-shot only (phase 1's standing configuration, carried into phase 2 --
see reports/phase1_report.md's "Standing configuration for phase 2").
When this is actually run against the model: n_samples=5 per window, per
CLAUDE.md's sampling policy.
"""
import sys

from masses import masses_to_boundaries
from sbcsae_llm import build_document_structure, build_prompt, estimate_tokens, render_window
from sbcsae_reader import CORPUS_DIR, read_trn_document
from sbcsae_tokenizer import Condition
from sbcsae_windows import assert_boundaries_each_in_one_region, assert_regions_tile, build_score_regions

DOC_ID = "SBC039"  # candidate pilot file, chosen in the prior session
N_SAMPLES = 5  # standing sampling policy, applies once this is a real run


def main():
    path = CORPUS_DIR / f"{DOC_ID}.trn"
    if not path.exists():
        sys.exit(f"corpus file not found: {path} (SBCSAE is gitignored, local-only)")

    doc_id, units, *_ = read_trn_document(path)
    doc = build_document_structure(doc_id, units)

    regions = build_score_regions(doc.n_tokens)
    assert_regions_tile(regions, doc.n_tokens)
    ref_boundaries = masses_to_boundaries(doc.ref_masses)
    assert_boundaries_each_in_one_region(regions, ref_boundaries, doc.n_tokens)

    print(f"=== Dry run: {DOC_ID}, no model call, zero-shot, n_samples={N_SAMPLES} when actually run ===")
    print(f"n_tokens: {doc.n_tokens}")
    print(f"n_windows: {len(regions)}")
    print(f"{len(ref_boundaries)} reference boundaries, all tile into exactly one window each (asserted above)\n")

    print(f"{'window':>6s} {'score_range':>15s} {'window_range':>15s} "
          f"{'chars_A':>8s} {'est_tok_A':>10s} {'chars_B':>8s} {'est_tok_B':>10s}")
    for i, r in enumerate(regions, start=1):
        text_a = build_prompt(render_window(doc, r.window_start, r.window_end, Condition.A), Condition.A)
        text_b = build_prompt(render_window(doc, r.window_start, r.window_end, Condition.B), Condition.B)
        print(
            f"{i:6d} {f'{r.score_start}-{r.score_end}':>15s} {f'{r.window_start}-{r.window_end}':>15s} "
            f"{len(text_a):8d} {estimate_tokens(text_a):10d} {len(text_b):8d} {estimate_tokens(text_b):10d}"
        )

    first = regions[0]
    print("\n" + "=" * 70)
    print(f"WINDOW 1 -- CONDITION A (words only), score range {first.score_start}-{first.score_end}, "
          f"window range {first.window_start}-{first.window_end}")
    print("=" * 70)
    prompt_a = build_prompt(render_window(doc, first.window_start, first.window_end, Condition.A), Condition.A)
    print(prompt_a)
    print(f"\n[{len(prompt_a)} chars, ~{estimate_tokens(prompt_a)} estimated tokens]")

    print("\n" + "=" * 70)
    print(f"WINDOW 1 -- CONDITION B (words + prosodic cues), score range {first.score_start}-{first.score_end}, "
          f"window range {first.window_start}-{first.window_end}")
    print("=" * 70)
    prompt_b = build_prompt(render_window(doc, first.window_start, first.window_end, Condition.B), Condition.B)
    print(prompt_b)
    print(f"\n[{len(prompt_b)} chars, ~{estimate_tokens(prompt_b)} estimated tokens]")


if __name__ == "__main__":
    main()

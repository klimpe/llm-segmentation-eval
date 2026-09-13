"""One-off: is the section-4.5 generation collapse on GUM_conversation_grounded
a deterministic consequence of the few-shot prompt, or a sampling artifact of
the single temperature=1.0 draw the original report was based on?

5 fresh few-shot calls at temperature=0, 5 fresh few-shot calls at
temperature=1.0, on this one document only. Bypasses segment_document's
on-disk cache entirely (every call here is fresh) and writes each raw
response to its own file under llm_output_fewshot_temp_experiment/ for later
inspection, separate from the cached llm_output_fewshot/ used by the main
pipeline.

Run with: python3 temp_experiment.py
"""
import functools
from pathlib import Path

from disrpt_reader import iter_tok_documents
from llm_segmenter import build_fewshot_prompt, call_model, indices_to_masses, masses_to_indices, parse_boundary_indices
from masses import assert_comparable
from run_eval import CORPUS_PATH
from run_eval_fewshot import FEWSHOT_EXAMPLE_DOCS, TRAIN_CORPUS_PATH, truncate_to_segments

DOC_ID = "GUM_conversation_grounded"
OUTPUT_DIR = Path("llm_output_fewshot_temp_experiment")
N_RUNS = 5
TEMPERATURES = [0, 1.0]


def load_target_document():
    for doc_id, tokens, ref_masses in iter_tok_documents(CORPUS_PATH):
        if doc_id == DOC_ID:
            return tokens, ref_masses
    raise ValueError(f"{DOC_ID} not found in {CORPUS_PATH}")


def build_examples():
    train_docs = {doc_id: (tokens, masses) for doc_id, tokens, masses in iter_tok_documents(TRAIN_CORPUS_PATH)}
    examples = []
    for doc_id, target_len in FEWSHOT_EXAMPLE_DOCS:
        tokens, masses = train_docs[doc_id]
        ex_tokens, ex_masses = truncate_to_segments(tokens, masses, target_len)
        examples.append((ex_tokens, masses_to_indices(ex_masses)))
    return examples


def longest_trailing_all_boundary_run(indices: list[int], n_tokens: int) -> int:
    """Length of the suffix ending at n_tokens where every single position is
    a predicted boundary. This operationalizes the section-4.5 'collapse'
    (model marks literally every remaining token as an EDU-start) without
    hardcoding the token-1088 onset the original single draw happened to
    show -- a collapse in a different run could start at a different point.
    """
    idx_set = set(indices)
    run = 0
    pos = n_tokens
    while pos >= 1 and pos in idx_set:
        run += 1
        pos -= 1
    return run


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    tokens, ref_masses = load_target_document()
    n_tokens = len(tokens)
    n_ref_boundaries = len(masses_to_indices(ref_masses))
    print(f"{DOC_ID}: {n_tokens} tokens, {n_ref_boundaries} reference boundaries\n")

    examples = build_examples()
    prompt = build_fewshot_prompt(tokens, examples=examples)

    results = []
    for temperature in TEMPERATURES:
        for run in range(1, N_RUNS + 1):
            label = f"temp{temperature}_run{run}"
            raw_path = OUTPUT_DIR / f"{label}.txt"
            print(f"[{label}] calling model...", flush=True)
            raw_output = call_model(prompt, temperature=temperature)
            raw_path.write_text(raw_output, encoding="utf-8")

            row = {"temperature": temperature, "run": run, "label": label}
            try:
                indices = parse_boundary_indices(raw_output)
                hyp_masses = indices_to_masses(indices, n_tokens)
                assert_comparable(ref_masses, hyp_masses)
                run_len = longest_trailing_all_boundary_run(indices, n_tokens)
                row.update(
                    {
                        "ok": True,
                        "n_predicted": len(indices),
                        "ratio_to_ref": len(indices) / n_ref_boundaries,
                        "trailing_collapse_run": run_len,
                        "collapse": run_len >= 20,  # arbitrary but generous vs normal tail density (~1 boundary/7-8 tokens)
                    }
                )
            except ValueError as e:
                row.update({"ok": False, "error": str(e)})

            results.append(row)
            print(f"  -> {row}\n", flush=True)

    print("\n=== Summary ===")
    print(f"{'label':16s} {'ok':>4s} {'n_pred':>7s} {'ratio':>6s} {'tail_run':>9s} {'collapse':>9s}")
    for r in results:
        if r["ok"]:
            print(
                f"{r['label']:16s} {'yes':>4s} {r['n_predicted']:7d} {r['ratio_to_ref']:6.2f} "
                f"{r['trailing_collapse_run']:9d} {str(r['collapse']):>9s}"
            )
        else:
            print(f"{r['label']:16s} {'FAIL':>4s} {r['error']}")

    for temperature in TEMPERATURES:
        sub = [r for r in results if r["temperature"] == temperature and r["ok"]]
        n_collapsed = sum(1 for r in sub if r["collapse"])
        print(f"\ntemperature={temperature}: {n_collapsed}/{len(sub)} runs collapsed")


if __name__ == "__main__":
    main()

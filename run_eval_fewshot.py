"""Few-shot variant of the segmentation prompt, compared against the
existing zero-shot results, on the same 22 (masking-excluded) dev documents.

Worked examples are short excerpts from the TRAIN split (never dev, never
test), cut at a segment boundary near a target length so no example ends
mid-EDU. Everything else -- model, parsing, metrics, documents, cache
directory -- differs only in the prompt; see FEWSHOT_OUTPUT_DIR vs
run_eval.LLM_OUTPUT_DIR.

Run with: python3 run_eval_fewshot.py
"""
import csv
import functools
from pathlib import Path

from disrpt_reader import iter_tok_documents
from llm_segmenter import build_fewshot_prompt, masses_to_indices
from metrics import corpus_micro_boundary_prf
from run_eval import CORPUS_PATH, LLM_OUTPUT_DIR, evaluate_documents, genre_of, load_eligible_documents

TRAIN_CORPUS_PATH = "corpora/disrpt/eng.rst.gum/eng.rst.gum_train.tok"
FEWSHOT_OUTPUT_DIR = Path("llm_output_fewshot")

# (train doc_id, target excerpt length in tokens). Cut at the first segment
# boundary at or past the target, so every example ends on a whole EDU.
# Picked for topical/register diversity (formal prose, spontaneous speech,
# narrative fiction) and because their openings are real body text, not a
# title/author metadata block.
FEWSHOT_EXAMPLE_DOCS = [
    ("GUM_academic_census", 45),
    ("GUM_conversation_atoms", 45),
    ("GUM_fiction_claus", 45),
]


def truncate_to_segments(tokens: list[str], masses: list[int], target_tokens: int):
    cum = 0
    kept_masses = []
    for m in masses:
        if cum >= target_tokens:
            break
        kept_masses.append(m)
        cum += m
    return tokens[:cum], kept_masses


def build_examples():
    train_docs = {doc_id: (tokens, masses) for doc_id, tokens, masses in iter_tok_documents(TRAIN_CORPUS_PATH)}
    examples = []
    for doc_id, target_len in FEWSHOT_EXAMPLE_DOCS:
        tokens, masses = train_docs[doc_id]
        ex_tokens, ex_masses = truncate_to_segments(tokens, masses, target_len)
        examples.append((ex_tokens, masses_to_indices(ex_masses)))
    return examples


def aggregate_corpus(rows):
    macro_f1 = sum(r["f1"] for r in rows) / len(rows)
    macro_wd = sum(r["window_diff"] for r in rows) / len(rows)
    macro_bs = sum(r["boundary_similarity"] for r in rows) / len(rows)
    micro_p, micro_r, micro_f1 = corpus_micro_boundary_prf([(r["ref_masses"], r["hyp_masses"]) for r in rows])
    return {
        "macro_f1": macro_f1,
        "macro_window_diff": macro_wd,
        "macro_boundary_similarity": macro_bs,
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f1,
    }


def aggregate_by_genre(rows):
    out = {}
    for genre in sorted({r["genre"] for r in rows}):
        genre_rows = [r for r in rows if r["genre"] == genre]
        agg = aggregate_corpus(genre_rows)
        agg["n_docs"] = len(genre_rows)
        out[genre] = agg
    return out


def main():
    _, docs, _, _ = load_eligible_documents(CORPUS_PATH)  # same 22 documents as the zero-shot run

    examples = build_examples()
    print("Few-shot worked examples (from TRAIN, not dev/test):")
    for (doc_id, target_len), (ex_tokens, ex_indices) in zip(FEWSHOT_EXAMPLE_DOCS, examples):
        print(f"  {doc_id}: {len(ex_tokens)} tokens, {len(ex_indices)} EDUs")
    print()

    fewshot_builder = functools.partial(build_fewshot_prompt, examples=examples)

    print("Scoring zero-shot (cached from the earlier run)...")
    zero_rows, zero_failures = evaluate_documents(docs, LLM_OUTPUT_DIR)
    print(f"  {len(zero_rows)} scored, {len(zero_failures)} failed\n")

    print("Scoring few-shot...")
    few_rows, few_failures = evaluate_documents(docs, FEWSHOT_OUTPUT_DIR, prompt_builder=fewshot_builder)
    print(f"  {len(few_rows)} scored, {len(few_failures)} failed\n")

    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit("# eng.rst.gum dev -- zero-shot vs few-shot")
    emit()
    emit(f"Same {len(docs)} documents both runs (masked-text docs excluded, same as the zero-shot report).")
    emit(f"Few-shot worked examples: {', '.join(doc_id for doc_id, _ in FEWSHOT_EXAMPLE_DOCS)} (TRAIN split).")
    emit(f"zero-shot: {len(zero_rows)} scored, {len(zero_failures)} failed alignment.")
    emit(f"few-shot:  {len(few_rows)} scored, {len(few_failures)} failed alignment.")
    emit()

    for label, failures in (("zero-shot", zero_failures), ("few-shot", few_failures)):
        if failures:
            emit(f"## {label} alignment failures")
            emit()
            for doc_id, reason in failures:
                emit(f"- {doc_id}: {reason}")
            emit()

    zero_by_doc = {r["doc_id"]: r for r in zero_rows}
    few_by_doc = {r["doc_id"]: r for r in few_rows}
    common_ids = [doc_id for doc_id, _, _ in docs if doc_id in zero_by_doc and doc_id in few_by_doc]
    common_ids_set = set(common_ids)
    # Every aggregate below (genre and corpus level) is restricted to
    # common_ids: if either run failed alignment on a document, comparing
    # aggregates computed over different document sets would not be the
    # controlled comparison this was supposed to be.
    zero_rows_common = [r for r in zero_rows if r["doc_id"] in common_ids_set]
    few_rows_common = [r for r in few_rows if r["doc_id"] in common_ids_set]
    if len(common_ids) < len(docs):
        emit(
            f"## Note: aggregates below use only the {len(common_ids)} documents where BOTH runs "
            f"aligned successfully (out of {len(docs)} attempted), for a controlled comparison."
        )
        emit()

    emit("## Per-document: precision / recall (zero-shot -> few-shot)")
    emit()
    header = (
        f"{'doc_id':30s} {'genre':14s} "
        f"{'zs_P':>6s} {'fs_P':>6s} {'d_P':>6s}   "
        f"{'zs_R':>6s} {'fs_R':>6s} {'d_R':>6s}   "
        f"{'zs_F1':>6s} {'fs_F1':>6s} {'d_F1':>6s}"
    )
    emit(header)
    emit("-" * len(header))
    doc_comparison_rows = []
    for doc_id in common_ids:
        z, f = zero_by_doc[doc_id], few_by_doc[doc_id]
        d_p, d_r, d_f1 = f["precision"] - z["precision"], f["recall"] - z["recall"], f["f1"] - z["f1"]
        emit(
            f"{doc_id:30s} {z['genre']:14s} "
            f"{z['precision']:6.3f} {f['precision']:6.3f} {d_p:+6.3f}   "
            f"{z['recall']:6.3f} {f['recall']:6.3f} {d_r:+6.3f}   "
            f"{z['f1']:6.3f} {f['f1']:6.3f} {d_f1:+6.3f}"
        )
        doc_comparison_rows.append(
            {
                "doc_id": doc_id,
                "genre": z["genre"],
                "zeroshot_precision": z["precision"],
                "fewshot_precision": f["precision"],
                "zeroshot_recall": z["recall"],
                "fewshot_recall": f["recall"],
                "zeroshot_f1": z["f1"],
                "fewshot_f1": f["f1"],
                "zeroshot_window_diff": z["window_diff"],
                "fewshot_window_diff": f["window_diff"],
                "zeroshot_boundary_similarity": z["boundary_similarity"],
                "fewshot_boundary_similarity": f["boundary_similarity"],
            }
        )
    emit()

    zero_genre = aggregate_by_genre(zero_rows_common)
    few_genre = aggregate_by_genre(few_rows_common)

    emit("## Per-genre: micro precision / recall / F1 (zero-shot -> few-shot)")
    emit()
    header2 = (
        f"{'genre':14s} {'n':>3s}   "
        f"{'zs_P':>6s} {'fs_P':>6s} {'d_P':>6s}   "
        f"{'zs_R':>6s} {'fs_R':>6s} {'d_R':>6s}   "
        f"{'zs_F1':>6s} {'fs_F1':>6s} {'d_F1':>6s}"
    )
    emit(header2)
    emit("-" * len(header2))
    genre_comparison_rows = []
    for genre in sorted(zero_genre):
        z, f = zero_genre[genre], few_genre[genre]
        d_p = f["micro_precision"] - z["micro_precision"]
        d_r = f["micro_recall"] - z["micro_recall"]
        d_f1 = f["micro_f1"] - z["micro_f1"]
        emit(
            f"{genre:14s} {z['n_docs']:3d}   "
            f"{z['micro_precision']:6.3f} {f['micro_precision']:6.3f} {d_p:+6.3f}   "
            f"{z['micro_recall']:6.3f} {f['micro_recall']:6.3f} {d_r:+6.3f}   "
            f"{z['micro_f1']:6.3f} {f['micro_f1']:6.3f} {d_f1:+6.3f}"
        )
        genre_comparison_rows.append(
            {
                "genre": genre,
                "n_docs": z["n_docs"],
                "zeroshot_micro_precision": z["micro_precision"],
                "fewshot_micro_precision": f["micro_precision"],
                "zeroshot_micro_recall": z["micro_recall"],
                "fewshot_micro_recall": f["micro_recall"],
                "zeroshot_micro_f1": z["micro_f1"],
                "fewshot_micro_f1": f["micro_f1"],
            }
        )
    emit()

    zero_corpus = aggregate_corpus(zero_rows_common)
    few_corpus = aggregate_corpus(few_rows_common)

    emit("## Corpus-level (micro-averaged, matching DISRPT's seg_eval.py methodology)")
    emit()
    emit(f"{'':12s} {'precision':>10s} {'recall':>10s} {'f1':>10s}")
    emit(
        f"{'zero-shot':12s} {zero_corpus['micro_precision']:10.4f} "
        f"{zero_corpus['micro_recall']:10.4f} {zero_corpus['micro_f1']:10.4f}"
    )
    emit(
        f"{'few-shot':12s} {few_corpus['micro_precision']:10.4f} "
        f"{few_corpus['micro_recall']:10.4f} {few_corpus['micro_f1']:10.4f}"
    )
    emit(
        f"{'delta':12s} {few_corpus['micro_precision'] - zero_corpus['micro_precision']:+10.4f} "
        f"{few_corpus['micro_recall'] - zero_corpus['micro_recall']:+10.4f} "
        f"{few_corpus['micro_f1'] - zero_corpus['micro_f1']:+10.4f}"
    )
    emit()

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    (results_dir / "eng.rst.gum_dev_zero_vs_fewshot.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with open(
        results_dir / "eng.rst.gum_dev_zero_vs_fewshot_per_document.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=list(doc_comparison_rows[0].keys()))
        writer.writeheader()
        writer.writerows(doc_comparison_rows)

    with open(
        results_dir / "eng.rst.gum_dev_zero_vs_fewshot_per_genre.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=list(genre_comparison_rows[0].keys()))
        writer.writeheader()
        writer.writerows(genre_comparison_rows)

    with open(results_dir / "eng.rst.gum_dev_zero_vs_fewshot_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "zero_shot", "few_shot", "delta"])
        for key in ("micro_precision", "micro_recall", "micro_f1", "macro_f1", "macro_window_diff", "macro_boundary_similarity"):
            writer.writerow([key, zero_corpus[key], few_corpus[key], few_corpus[key] - zero_corpus[key]])


if __name__ == "__main__":
    main()

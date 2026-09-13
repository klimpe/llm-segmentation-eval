"""Resampling test (report §7): is the split between few-shot-harmed and
few-shot-helped documents a property of the texts, or just sampling spread?

Temperature/top_p/top_k are not controllable through this SDK/model (see
llm_segmenter.call_model) -- an earlier version of this experiment tried to
compare temperature=0 against temperature=1.0 and failed immediately with
TypeError, since the parameter does not exist. Variance is measured instead
of pinned: this draws 5 independent samples (default, uncontrolled sampling)
per document per condition (zero-shot, few-shot) for the 4 documents with
the largest few-shot precision decline and the 4 with the largest gain
(picked from results/eng.rst.gum_dev_zero_vs_fewshot_per_document.csv), and
reports the mean and range of precision/recall/F1 across samples.

Sample 0 in each condition reuses the existing single-sample cache under
llm_output/ or llm_output_fewshot/ (no re-query); samples 1-4 are fresh
calls, cached separately under llm_output_temp_resample/ and
llm_output_fewshot_temp_resample/ so the main pipeline's caches are
untouched.

If the harmed/helped ranking is stable across samples, the split is a
property of the documents. If ranges overlap heavily between the two
groups, the aggregate few-shot result may be dominated by sampling noise
rather than a real effect.

Also tracks the generation-collapse signature from report §4.5 (every
remaining token marked as a boundary) on every sample of
GUM_conversation_grounded, to check whether that collapse recurs or was a
one-off draw.

Run with: python3 temp_experiment.py
"""
import csv
import functools
from pathlib import Path

from disrpt_reader import iter_tok_documents
from llm_segmenter import segment_document
from metrics import boundary_f1, boundary_precision_recall
from run_eval import CORPUS_PATH, LLM_OUTPUT_DIR, genre_of
from run_eval_fewshot import FEWSHOT_OUTPUT_DIR, build_examples, build_fewshot_prompt

N_SAMPLES = 5  # must stay >= 2: N_SAMPLES - 1 is passed as segment_document's
# n_samples for the resample-only calls below, which only returns a list (as
# opposed to a single hyp_masses) when its own n_samples argument is > 1.
ZERO_RESAMPLE_DIR = Path("llm_output_temp_resample")
FEWSHOT_RESAMPLE_DIR = Path("llm_output_fewshot_temp_resample")
PER_DOCUMENT_CSV = "results/eng.rst.gum_dev_zero_vs_fewshot_per_document.csv"

# The 4 largest few-shot precision declines and 4 largest gains, read off
# the existing comparison CSV (fewshot_precision - zeroshot_precision).
DECLINE_DOCS = [
    "GUM_interview_gaming",
    "GUM_conversation_grounded",
    "GUM_academic_exposure",
    "GUM_voyage_coron",
]
GAIN_DOCS = [
    "GUM_fiction_beast",
    "GUM_whow_joke",
    "GUM_bio_byron",
    "GUM_textbook_governments",
]


def load_target_documents(doc_ids: set[str]):
    return {doc_id: (tokens, ref_masses) for doc_id, tokens, ref_masses in iter_tok_documents(CORPUS_PATH) if doc_id in doc_ids}


def trailing_all_boundary_run(hyp_masses: list[int]) -> int:
    """Length of the trailing run of mass-1 segments -- the operationalized
    signature of the §4.5 collapse (every remaining token its own EDU),
    without hardcoding the specific token offset a single draw happened to
    show.
    """
    run = 0
    for m in reversed(hyp_masses):
        if m != 1:
            break
        run += 1
    return run


def mean(xs):
    return sum(xs) / len(xs)


def main():
    all_doc_ids = set(DECLINE_DOCS) | set(GAIN_DOCS)
    docs = load_target_documents(all_doc_ids)
    missing = all_doc_ids - docs.keys()
    if missing:
        raise ValueError(f"documents not found in {CORPUS_PATH}: {missing}")

    fewshot_builder = functools.partial(build_fewshot_prompt, examples=build_examples())

    conditions = [
        ("zero-shot", LLM_OUTPUT_DIR, ZERO_RESAMPLE_DIR, None),
        ("few-shot", FEWSHOT_OUTPUT_DIR, FEWSHOT_RESAMPLE_DIR, fewshot_builder),
    ]

    per_sample_rows = []
    summary_rows = []
    failure_rows = []

    for group, doc_ids in (("decline", DECLINE_DOCS), ("gain", GAIN_DOCS)):
        for doc_id in doc_ids:
            tokens, ref_masses = docs[doc_id]
            genre = genre_of(doc_id)
            for condition, primary_dir, resample_dir, builder in conditions:
                print(f"[{group}] {doc_id} ({condition}): drawing {N_SAMPLES} samples...", flush=True)
                # Sample 0 reads/writes the main pipeline's cache dir (reused,
                # no re-query); samples 1..N-1 use the resample-only cache
                # dir so they never collide with or overwrite the primary run.
                kwargs = {} if builder is None else {"prompt_builder": builder}
                # sample0 is the main pipeline's single cached run (n_samples=1
                # still raises ValueError on failure, same as ever -- these 8
                # documents were already known-good from the original report).
                sample0 = segment_document(tokens, ref_masses, doc_id, primary_dir, n_samples=1, **kwargs)
                # n_samples=N_SAMPLES-1 (>=2, see constant above) returns
                # (results, failures): a bad fresh sample must not lose the
                # other resampled draws, so failures are recorded, not raised.
                rest, rest_failures = segment_document(
                    tokens, ref_masses, doc_id, resample_dir, n_samples=N_SAMPLES - 1, **kwargs
                )
                for sample_idx, reason in rest_failures:
                    print(f"    sample {sample_idx + 1} FAILED: {reason}", flush=True)
                    failure_rows.append(
                        {
                            "group": group,
                            "doc_id": doc_id,
                            "genre": genre,
                            "condition": condition,
                            "sample": sample_idx + 1,
                            "reason": reason,
                        }
                    )
                samples = [sample0] + rest

                if not samples:
                    print(f"    all samples failed for {doc_id} ({condition}); skipping summary", flush=True)
                    continue

                metrics_this_doc = []
                for i, hyp_masses in enumerate(samples):
                    precision, recall = boundary_precision_recall(ref_masses, hyp_masses)
                    f1 = boundary_f1(ref_masses, hyp_masses)
                    collapse_run = trailing_all_boundary_run(hyp_masses)
                    row = {
                        "group": group,
                        "doc_id": doc_id,
                        "genre": genre,
                        "condition": condition,
                        "sample": i,
                        "precision": precision,
                        "recall": recall,
                        "f1": f1,
                        "hyp_segs": len(hyp_masses),
                        "trailing_collapse_run": collapse_run,
                    }
                    per_sample_rows.append(row)
                    metrics_this_doc.append(row)

                precisions = [r["precision"] for r in metrics_this_doc]
                recalls = [r["recall"] for r in metrics_this_doc]
                f1s = [r["f1"] for r in metrics_this_doc]
                summary_rows.append(
                    {
                        "group": group,
                        "doc_id": doc_id,
                        "genre": genre,
                        "condition": condition,
                        "n_samples": len(metrics_this_doc),
                        "precision_mean": mean(precisions),
                        "precision_min": min(precisions),
                        "precision_max": max(precisions),
                        "recall_mean": mean(recalls),
                        "recall_min": min(recalls),
                        "recall_max": max(recalls),
                        "f1_mean": mean(f1s),
                        "f1_min": min(f1s),
                        "f1_max": max(f1s),
                        "max_trailing_collapse_run": max(r["trailing_collapse_run"] for r in metrics_this_doc),
                    }
                )

    print("\n=== Per-document resampling summary (precision, mean [min-max]) ===\n")
    header = f"{'group':8s} {'doc_id':28s} {'condition':10s} {'n':>2s} {'precision':>22s} {'recall':>22s} {'f1':>22s} {'max_run':>8s}"
    print(header)
    print("-" * len(header))
    for r in summary_rows:
        p = f"{r['precision_mean']:.3f} [{r['precision_min']:.3f}-{r['precision_max']:.3f}]"
        rc = f"{r['recall_mean']:.3f} [{r['recall_min']:.3f}-{r['recall_max']:.3f}]"
        f = f"{r['f1_mean']:.3f} [{r['f1_min']:.3f}-{r['f1_max']:.3f}]"
        print(
            f"{r['group']:8s} {r['doc_id']:28s} {r['condition']:10s} {r['n_samples']:2d} "
            f"{p:>22s} {rc:>22s} {f:>22s} {r['max_trailing_collapse_run']:8d}"
        )

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    with open(results_dir / "eng.rst.gum_dev_resampling_per_sample.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(per_sample_rows[0].keys()))
        writer.writeheader()
        writer.writerows(per_sample_rows)

    with open(results_dir / "eng.rst.gum_dev_resampling_summary.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    if failure_rows:
        with open(results_dir / "eng.rst.gum_dev_resampling_failures.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(failure_rows[0].keys()))
            writer.writeheader()
            writer.writerows(failure_rows)
        print(f"\n{len(failure_rows)} sample(s) failed to parse/align -- see eng.rst.gum_dev_resampling_failures.csv")

    print(
        f"\nWrote results/eng.rst.gum_dev_resampling_per_sample.csv "
        f"({len(per_sample_rows)} rows) and eng.rst.gum_dev_resampling_summary.csv "
        f"({len(summary_rows)} rows)."
    )


if __name__ == "__main__":
    main()

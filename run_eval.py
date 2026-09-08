"""Step 5: scale to the full eng.rst.gum dev split, produce a results table,
and compare against the published DISRPT 2023 system score.

Run with: python3 run_eval.py
"""
import csv
from pathlib import Path

from disrpt_reader import iter_tok_documents
from llm_segmenter import segment_document
from metrics import (
    boundary_f1,
    boundary_precision_recall,
    boundary_similarity,
    corpus_micro_boundary_prf,
    window_diff,
)

CORPUS_PATH = "corpora/disrpt/eng.rst.gum/eng.rst.gum_dev.tok"
LLM_OUTPUT_DIR = Path("llm_output")

# Published DISRPT 2023 baseline for eng.rst.gum, Plain track (.tok input, no
# gold syntax), DisCut* system, test partition (Table 3 of Braud et al. 2023,
# https://aclanthology.org/2023.disrpt-1.1/). Not directly comparable to the
# numbers below: this is a fine-tuned system scored on the *test* split,
# while everything here runs on the *dev* split (the only one downloaded).
DISRPT_2023_GUM_PLAIN_BASELINE = {"precision": 94.95, "recall": 93.98, "f1": 94.46}


def genre_of(doc_id: str) -> str:
    # doc_id format: GUM_<genre>_<name>
    return doc_id.split("_")[1]


def main():
    docs = list(iter_tok_documents(CORPUS_PATH))
    print(f"Loaded {len(docs)} documents from {CORPUS_PATH}\n")

    rows = []
    failures = []

    for doc_id, tokens, ref_masses in docs:
        try:
            hyp_masses = segment_document(tokens, ref_masses, doc_id, LLM_OUTPUT_DIR)
        except ValueError as e:
            failures.append((doc_id, str(e)))
            continue

        precision, recall = boundary_precision_recall(ref_masses, hyp_masses)
        rows.append(
            {
                "doc_id": doc_id,
                "genre": genre_of(doc_id),
                "n_tokens": len(tokens),
                "ref_segs": len(ref_masses),
                "hyp_segs": len(hyp_masses),
                "precision": precision,
                "recall": recall,
                "f1": boundary_f1(ref_masses, hyp_masses),
                "window_diff": window_diff(ref_masses, hyp_masses),
                "boundary_similarity": boundary_similarity(ref_masses, hyp_masses),
                "ref_masses": ref_masses,
                "hyp_masses": hyp_masses,
            }
        )

    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit("# eng.rst.gum dev -- LLM discourse segmentation results")
    emit()
    emit(f"{len(rows)} of {len(docs)} documents scored; {len(failures)} failed alignment.")
    emit()

    if failures:
        emit("## Alignment failures (excluded from all metrics below)")
        emit()
        for doc_id, reason in failures:
            emit(f"- {doc_id}: {reason}")
        emit()

    emit("## Per-document results")
    emit()
    header = f"{'doc_id':30s} {'genre':14s} {'n_tok':>6s} {'ref':>4s} {'hyp':>4s} {'P':>6s} {'R':>6s} {'F1':>6s} {'WD':>6s} {'BS':>6s}"
    emit(header)
    emit("-" * len(header))
    for r in rows:
        emit(
            f"{r['doc_id']:30s} {r['genre']:14s} {r['n_tokens']:6d} {r['ref_segs']:4d} {r['hyp_segs']:4d} "
            f"{r['precision']:6.3f} {r['recall']:6.3f} {r['f1']:6.3f} {r['window_diff']:6.3f} {r['boundary_similarity']:6.3f}"
        )
    emit()

    emit("## Per-genre breakdown (mean of per-document scores; macro average)")
    emit()
    genres = sorted({r["genre"] for r in rows})
    header2 = f"{'genre':14s} {'n_docs':>6s} {'mean_F1':>8s} {'mean_WD':>8s} {'mean_BS':>8s} {'micro_P':>8s} {'micro_R':>8s} {'micro_F1':>9s}"
    emit(header2)
    emit("-" * len(header2))
    genre_rows_out = []
    for genre in genres:
        genre_rows = [r for r in rows if r["genre"] == genre]
        n = len(genre_rows)
        mean_f1 = sum(r["f1"] for r in genre_rows) / n
        mean_wd = sum(r["window_diff"] for r in genre_rows) / n
        mean_bs = sum(r["boundary_similarity"] for r in genre_rows) / n
        micro_p, micro_r, micro_f1 = corpus_micro_boundary_prf(
            [(r["ref_masses"], r["hyp_masses"]) for r in genre_rows]
        )
        emit(
            f"{genre:14s} {n:6d} {mean_f1:8.3f} {mean_wd:8.3f} {mean_bs:8.3f} "
            f"{micro_p:8.3f} {micro_r:8.3f} {micro_f1:9.3f}"
        )
        genre_rows_out.append(
            {
                "genre": genre,
                "n_docs": n,
                "mean_f1": mean_f1,
                "mean_window_diff": mean_wd,
                "mean_boundary_similarity": mean_bs,
                "micro_precision": micro_p,
                "micro_recall": micro_r,
                "micro_f1": micro_f1,
            }
        )
    emit()

    emit("## Corpus-level aggregate (all documents pooled)")
    emit()
    macro_f1 = sum(r["f1"] for r in rows) / len(rows)
    macro_wd = sum(r["window_diff"] for r in rows) / len(rows)
    macro_bs = sum(r["boundary_similarity"] for r in rows) / len(rows)
    micro_p, micro_r, micro_f1 = corpus_micro_boundary_prf([(r["ref_masses"], r["hyp_masses"]) for r in rows])
    emit(f"macro mean F1 (unweighted mean over {len(rows)} docs): {macro_f1:.4f}")
    emit(f"macro mean WindowDiff: {macro_wd:.4f}")
    emit(f"macro mean Boundary Similarity: {macro_bs:.4f}")
    emit()
    emit("micro-averaged boundary P/R/F1 (DISRPT's own scoring methodology, seg_eval.py):")
    emit(f"  precision={micro_p:.4f}  recall={micro_r:.4f}  f1={micro_f1:.4f}")
    emit()

    emit("## Comparison against published DISRPT 2023 baseline (eng.rst.gum, Plain track, DisCut*)")
    emit()
    emit(
        "Caveat: the published score is a fine-tuned system evaluated on the "
        "*test* partition; the numbers above are zero/few-shot prompting "
        "evaluated on the *dev* partition (the only split downloaded here). "
        "Not a controlled comparison -- reported for context only."
    )
    emit()
    b = DISRPT_2023_GUM_PLAIN_BASELINE
    emit(f"{'':20s} {'precision':>10s} {'recall':>10s} {'f1':>10s}")
    emit(f"{'DISRPT 2023 DisCut*':20s} {b['precision']:10.2f} {b['recall']:10.2f} {b['f1']:10.2f}")
    emit(f"{'this pipeline (dev)':20s} {micro_p * 100:10.2f} {micro_r * 100:10.2f} {micro_f1 * 100:10.2f}")

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    Path("results/eng.rst.gum_dev.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_csvs(results_dir, rows, failures, genre_rows_out, macro_f1, macro_wd, macro_bs, micro_p, micro_r, micro_f1)


def write_csvs(results_dir, rows, failures, genre_rows, macro_f1, macro_wd, macro_bs, micro_p, micro_r, micro_f1):
    doc_fields = [
        "doc_id",
        "genre",
        "n_tokens",
        "ref_segs",
        "hyp_segs",
        "precision",
        "recall",
        "f1",
        "window_diff",
        "boundary_similarity",
    ]
    with open(results_dir / "eng.rst.gum_dev_per_document.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=doc_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with open(results_dir / "eng.rst.gum_dev_failures.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["doc_id", "reason"])
        writer.writerows(failures)

    genre_fields = [
        "genre",
        "n_docs",
        "mean_f1",
        "mean_window_diff",
        "mean_boundary_similarity",
        "micro_precision",
        "micro_recall",
        "micro_f1",
    ]
    with open(results_dir / "eng.rst.gum_dev_per_genre.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=genre_fields)
        writer.writeheader()
        writer.writerows(genre_rows)

    b = DISRPT_2023_GUM_PLAIN_BASELINE
    with open(results_dir / "eng.rst.gum_dev_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["n_docs_scored", len(rows)])
        writer.writerow(["n_docs_failed", len(failures)])
        writer.writerow(["macro_mean_f1", macro_f1])
        writer.writerow(["macro_mean_window_diff", macro_wd])
        writer.writerow(["macro_mean_boundary_similarity", macro_bs])
        writer.writerow(["corpus_micro_precision", micro_p])
        writer.writerow(["corpus_micro_recall", micro_r])
        writer.writerow(["corpus_micro_f1", micro_f1])
        writer.writerow(["disrpt_2023_discut_test_precision", b["precision"] / 100])
        writer.writerow(["disrpt_2023_discut_test_recall", b["recall"] / 100])
        writer.writerow(["disrpt_2023_discut_test_f1", b["f1"] / 100])


if __name__ == "__main__":
    main()

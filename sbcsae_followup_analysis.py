"""Phase 2 stage 4, follow-up to the inventory/tokeniser reports (item 5):
whole-corpus checks on the fusion rule, the still-raising undocumented
patterns, and a re-run of the zero-word-IU breakdown after the reader and
tokeniser fixes. SBC037 excluded throughout. Terminal output only -- no
processed transcript text in any committed file.
"""
import random
import re
from collections import Counter, defaultdict

from sbcsae_reader import iter_trn_documents
from sbcsae_tokenizer import Cue, TokenizeError, Word, tokenize, words_only

EXCLUDE = {"SBC037"}


def all_ius():
    for doc_id, units, *_ in iter_trn_documents():
        if doc_id in EXCLUDE:
            continue
        for u in units:
            yield doc_id, u.text


def section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main():
    texts = list(all_ius())
    n_total = len(texts)
    print(f"Total IUs analysed (excl. SBC037): {n_total}")

    # ---- 1. Fusion rule -------------------------------------------------
    section("1. Fusion rule: counts and examples")
    fused_words = []  # (doc_id, iu_text, Word)
    per_file_ius = Counter()
    for doc_id, text in texts:
        per_file_ius[doc_id] += 1
        try:
            items = tokenize(text)
        except TokenizeError:
            continue
        for w in words_only(items):
            if w.n_fragments > 1:
                fused_words.append((doc_id, text, w))

    print(f"Total fusions (words assembled from >1 fragment): {len(fused_words)}")
    by_frag_count = Counter(w.n_fragments for _, _, w in fused_words)
    print("by fragment count:", dict(sorted(by_frag_count.items())))
    by_file = Counter(d for d, _, _ in fused_words)
    print(f"files with at least one fusion: {len(by_file)} of {len(per_file_ius)}")

    random.seed(0)
    sample = random.sample(fused_words, min(20, len(fused_words)))
    print("\n20 random examples, raw IU -> fused word (raw form -> normalised):")
    for doc_id, iu_text, w in sample:
        print(f"  {doc_id}: IU={iu_text!r}  word.raw={w.raw!r} -> word.text={w.text!r}")

    # ---- 2. ~ # * + and <<TAG ... TAG>> ----------------------------------
    section("2. ~ # * + and <<TAG ... TAG>> -- counts, examples, tag names")

    for ch, name in [("~", "tilde"), ("#", "hash"), ("*", "star"), ("+", "plus")]:
        occs = [(d, t) for d, t in texts if ch in t]
        n_files = len({d for d, t in occs})
        total = sum(t.count(ch) for d, t in occs)
        print(f"\n'{ch}' ({name}): {total} occurrences in {len(occs)} IUs, {n_files} files")
        for d, t in occs[:10]:
            print(f"    {d}: {t!r}")

    dbl_open_re = re.compile(r"<<([A-Za-z]+)")
    dbl_close_re = re.compile(r"([A-Za-z]+)>>")
    open_tags = Counter()
    close_tags = Counter()
    dbl_examples = []
    for d, t in texts:
        for m in dbl_open_re.finditer(t):
            open_tags[m.group(1)] += 1
            dbl_examples.append((d, t))
        for m in dbl_close_re.finditer(t):
            close_tags[m.group(1)] += 1

    print(f"\n<<TAG ... TAG>>: {sum(open_tags.values())} opens, {sum(close_tags.values())} closes")
    print("distinct open tag names:", dict(open_tags))
    print("distinct close tag names:", dict(close_tags))
    print("10 examples:")
    seen = set()
    shown = 0
    for d, t in dbl_examples:
        if t in seen:
            continue
        seen.add(t)
        print(f"    {d}: {t!r}")
        shown += 1
        if shown >= 10:
            break

    # ---- 3. Zero-word IUs: proportion of each file's own IU count -------
    # The composition breakdown (by category, by raw count per file) now
    # lives in sbcsae_tokenizer_validate.py only -- this script used to
    # have its own, separate copy of that classifier, which disagreed with
    # the validator's cruder one (236 vs 242 breath_only; reconciled and
    # retired, see reports/phase2_tokeniser.md S4). This section keeps only
    # the one thing the validator doesn't compute: proportion of each
    # file's OWN IU count, not raw counts, which is what makes SBC013
    # visible as the worst file despite not having the most zero-word IUs
    # in absolute terms.
    section("3. Zero-word IUs as a proportion of each file's own IU count")

    zero_word_by_file = Counter()
    n_raised = 0
    for doc_id, text in texts:
        try:
            items = tokenize(text)
        except TokenizeError:
            n_raised += 1
            continue
        if words_only(items):
            continue
        zero_word_by_file[doc_id] += 1

    print(f"raised: {n_raised} of {n_total}")
    print("top 15 by proportion:")
    props = sorted(
        ((d, zero_word_by_file.get(d, 0) / per_file_ius[d]) for d in per_file_ius),
        key=lambda kv: -kv[1],
    )
    for d, p in props[:15]:
        print(f"  {d}: {100*p:5.2f}%  ({zero_word_by_file.get(d,0)} of {per_file_ius[d]} IUs)")


if __name__ == "__main__":
    main()

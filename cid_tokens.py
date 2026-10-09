"""Phase 3 stage 1, step 2: the token tier of the archive's *_all.TextGrid.

Per speaker: token count, pause (#) count, pause duration distribution,
tokens ending in "-", and the distinct non-plain-word forms.

The forms themselves are transcript material (CID is embargoed) and go to
the terminal only, with --forms. The default output is counts by
structural class, which is what the committed report may contain.
"""
import re
import statistics
import sys
from collections import Counter

from cid_textgrid import ARCHIVE_CID, SPEAKERS, read_textgrid

ALL_DIR = ARCHIVE_CID / "unsorted"
# MG has no *_all.TextGrid. tokens/<spk>_tokens.TextGrid carries a token tier
# that is interval-for-interval identical to *_all's for the other 15
# speakers (checked, reports/phase3_data.md §1), so MG is read from there
# and reported as a separate, marked row -- not folded into the totals.
MG_TOKENS = ARCHIVE_CID / "tokens" / "MG_tokens.TextGrid"

_L = "a-zàâäçéèêëîïôöùûüÿœæ"
# Lower-case letters, optionally joined by internal apostrophes/hyphens,
# optionally ending in an elided apostrophe: "aujourd'hui", "peut-être", "l'".
PLAIN = re.compile(rf"[{_L}]+(?:['-][{_L}]+)*'?")

# Mutually exclusive, first match wins. Order is a reporting choice only.
CLASSES = [
    ("pause #", lambda w: w == "#"),
    ("empty label", lambda w: w.strip() == ""),
    ("no letters", lambda w: not re.search(r"[^\W\d_]", w)),
    ("contains =", lambda w: "=" in w),
    ("contains digit", lambda w: re.search(r"\d", w) is not None),
    ("ends in -", lambda w: w.endswith("-")),
    ("starts with -", lambda w: w.startswith("-")),
    ("contains _", lambda w: "_" in w),
    ("contains upper-case", lambda w: w != w.lower()),
    ("other character", lambda w: True),
]


def classify(w: str) -> str:
    if PLAIN.fullmatch(w):
        return "plain"
    for name, pred in CLASSES:
        if pred(w):
            return name
    raise AssertionError


def quartiles(xs):
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return min(xs), q[0], q[1], q[2], max(xs)


def main(show_forms: bool):
    present = {p.name.split("_")[0] for p in ALL_DIR.glob("*_all.TextGrid")}
    print("speakers without *_all.TextGrid:", sorted(set(SPEAKERS) - present))
    hdr = ("spk", "intervals", "words", "#", "#_min", "#_q1", "#_med", "#_q3", "#_max",
           "ends-", "non-plain_types", "non-plain_tokens", "contiguous")
    print("\t".join(hdr))
    by_class = {}
    all_pause = []
    totals = Counter()
    forms_all = Counter()
    for spk in sorted(present) + ["MG*"]:
        tg = read_textgrid(MG_TOKENS if spk == "MG*" else ALL_DIR / f"{spk}_all.TextGrid")
        items = tg.tier("token").items
        labels = [i.text for i in items]
        pauses = [i.xmax - i.xmin for i in items if i.text == "#"]
        if spk != "MG*":
            all_pause += pauses
        contiguous = all(a.xmax == b.xmin for a, b in zip(items, items[1:]))
        cls = Counter()
        nonplain = Counter()
        for w in labels:
            c = classify(w)
            cls[c] += 1
            if c != "plain":
                nonplain[w] += 1
        by_class[spk] = cls
        if spk == "MG*":
            print(spk, len(labels), len(labels) - cls["pause #"] - cls["empty label"], len(pauses),
                  *(f"{x:.3f}" for x in quartiles(pauses)), sum(w.endswith("-") for w in labels),
                  len([k for k in nonplain if k != "#"]),
                  sum(v for k, v in nonplain.items() if k != "#"), contiguous,
                  "(tokens/MG_tokens.TextGrid; not in ALL)", sep="\t")
            if show_forms:
                print(f"  forms {spk}:", nonplain.most_common())
            continue
        forms_all.update(nonplain)
        n_trunc = sum(w.endswith("-") for w in labels)
        n_words = len(labels) - cls["pause #"] - cls["empty label"]
        np_tok = sum(v for k, v in nonplain.items() if k != "#")
        np_typ = len([k for k in nonplain if k != "#"])
        qs = quartiles(pauses)
        print(spk, len(labels), n_words, len(pauses), *(f"{x:.3f}" for x in qs),
              n_trunc, np_typ, np_tok, contiguous, sep="\t")
        totals.update(intervals=len(labels), words=n_words, pauses=len(pauses), trunc=n_trunc,
                      np_tok=np_tok)
        if show_forms:
            print(f"  forms {spk}:", nonplain.most_common())
    qs = quartiles(all_pause)
    print("ALL", totals["intervals"], totals["words"], totals["pauses"],
          *(f"{x:.3f}" for x in qs), totals["trunc"], len([k for k in forms_all if k != "#"]),
          totals["np_tok"], "", sep="\t")

    names = ["plain"] + [n for n, _ in CLASSES]
    print("\ntoken class by speaker (exclusive, first match):")
    print("spk\t" + "\t".join(names))
    for spk, cls in by_class.items():
        print(spk + "\t" + "\t".join(str(cls[n]) for n in names))
    print("ALL\t" + "\t".join(str(sum(c[n] for s, c in by_class.items() if s != "MG*")) for n in names))

    # distinct forms per class, corpus-wide
    print("\ndistinct non-plain forms per class (all speakers):")
    per = Counter(classify(w) for w in forms_all)
    for n in names[1:]:
        print(f"  {n}\t{per[n]} types\t{sum(v for w, v in forms_all.items() if classify(w) == n)} tokens")
    # Forms with no letters at all are markup, not speech; safe to name.
    print("no-letter forms:", [(w, c) for w, c in forms_all.most_common() if classify(w) in
                               ("no letters", "pause #", "empty label")])
    if show_forms:
        print("\nALL non-plain forms:", forms_all.most_common())


if __name__ == "__main__":
    main("--forms" in sys.argv)

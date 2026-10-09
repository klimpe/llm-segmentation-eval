"""Phase 3 stage 1, step 5: IP and AP label codes.

Distribution of labels on the IP and AP tiers, per file, in the deposit's
prosody/ (including low-kappa/), and in every archive TextGrid carrying a
tier named ip/ap (any case, any -suffix). Then: does the archive use the
same code set, and do per-label totals over the deposit files reproduce
descr.txt? Labels here are annotation codes, not transcript text.
No interpretation of the codes.
"""
import re
import sys
from collections import Counter
from pathlib import Path

from cid_textgrid import (ARCHIVE, DEPOSIT, EncodingUndetermined, TextGridFormatError,
                          public_path, read_textgrid, write_csv)

PROSODY = DEPOSIT / "prosody"
LEVEL = re.compile(r"^(ip|ap)(\b|[-_])", re.I)


# "AP" is also a speaker code: AP_token / AP_ipu / AP_story are speaker
# AP's tiers (archive narrative files), not accentual-phrase tiers.
NOT_LEVEL = re.compile(r"^AP[-_](token|ipu|story|narr\w*)$", re.I)


def level(name):
    m = LEVEL.match(name)
    return m.group(1).upper() if m and not NOT_LEVEL.match(name) else None


def label_dists(tg):
    """[(level, tier name, label Counter)] for every ip/ap tier; an archive
    file may carry several (one per coder)."""
    return [(level(t.name), t.name, Counter(i.text for i in t.items))
            for t in tg.tiers if level(t.name)]


def label_dist(tg):
    """{level: (tier name, Counter)}; exactly one tier per level expected."""
    ds = label_dists(tg)
    out = {lv: (name, c) for lv, name, c in ds}
    if len(out) != len(ds):
        raise ValueError("more than one tier for a level")
    return out


def show(rel, dists):
    for lv, name, c in dists:
        print(f"  {rel}\t{lv} (tier {name!r})\t{len(c)} labels\t" +
              " ".join(f"{k!r}:{v}" for k, v in sorted(c.items())))


# Only labels of this shape are written to a committed table: an optional
# level word or "?" (plus the few short variants seen on the archive's
# ip/ap tiers), optionally followed by a two-digit code. Everything else is
# counted under "<other>", so no free text can reach the CSV.
SAFE_LABEL = re.compile(r"^(|IP|AP|ip|ap|ip\?|ap\?\?|apa|an|ep|ipip|\?)( \d\d)?$")


ARCH_ROWS = {}


def safe_label(lab):
    return lab if SAFE_LABEL.match(lab) else "<other>"


def main(archive_files):
    dep = {}
    for p in sorted(PROSODY.rglob("*.TextGrid")):
        rel = str(p.relative_to(PROSODY))
        tg = read_textgrid(p)
        dep[rel] = (label_dist(tg), tg)
    print("deposit prosody/ files:")
    for rel, (d, tg) in dep.items():
        print(f"  {rel}\t{tg.encoding}\ttiers {[t.name for t in tg.tiers]}\tspan {tg.xmax - tg.xmin:.3f}s")
    print("\nlabel distribution per file (deposit):")
    for rel, (d, _) in dep.items():
        show(rel, [(lv, *d[lv]) for lv in ("IP", "AP") if lv in d])

    # descr.txt check: which subset of files reproduces its totals?
    for lv in ("IP", "AP"):
        top = Counter()
        for rel, (d, _) in dep.items():
            if "/" not in rel and lv in d:
                top += d[lv][1]
        allf = Counter()
        for rel, (d, _) in dep.items():
            if lv in d:
                allf += d[lv][1]
        print(f"\n{lv} totals, top-level files only ({sum(top.values())} items): {dict(sorted(top.items()))}")
        print(f"{lv} totals, incl. low-kappa ({sum(allf.values())} items): {dict(sorted(allf.items()))}")
    top_dur = sum(tg.xmax - tg.xmin for rel, (d, tg) in dep.items() if "/" not in rel)
    print(f"total duration, top-level files: {top_dur:.3f}s")

    code = re.compile(r"^(IP|AP) (\d\d)$")
    dep_codes = {lv: set() for lv in ("IP", "AP")}
    non_code = Counter()
    for rel, (d, _) in dep.items():
        for lv, (_, c) in d.items():
            for lab, n in c.items():
                m = code.match(lab.strip())
                if m and m.group(1) == lv:
                    dep_codes[lv].add(m.group(2))
                elif lab.strip():
                    non_code[(lv, lab)] += n
    print("\ndeposit two-digit codes:", {k: sorted(v) for k, v in dep_codes.items()})
    print("deposit non-empty labels not of the form '<IP|AP> NN':", dict(non_code))

    print("\narchive TextGrids with an ip/ap tier:")
    arch_labels = {"IP": Counter(), "AP": Counter()}
    n_files = 0
    for p in archive_files:
        try:
            tg = read_textgrid(p)
        except (EncodingUndetermined, TextGridFormatError):
            continue  # reported in step 1; not silently: counted there
        ds = label_dists(tg)
        if not ds:
            continue
        n_files += 1
        show(str(p.relative_to(ARCHIVE)), ds)
        for i, (lv, name, c) in enumerate(ds):
            arch_labels[lv] += c
            ARCH_ROWS[(str(p.relative_to(ARCHIVE)), lv, f"{name}" if [x[1] for x in ds].count(name) == 1
                       else f"{name}#{i + 1}")] = c
    print(f"\n{n_files} archive files with ip/ap tiers")
    for lv in ("IP", "AP"):
        print(f"archive {lv} label set ({len(arch_labels[lv])}): {dict(sorted(arch_labels[lv].items()))}")

    # --- committed tables ---
    rows = []
    for rel, (d, _) in dep.items():
        for lv in ("IP", "AP"):
            name, c = d[lv]
            for lab, n in sorted(c.items()):
                if safe_label(lab) != lab:
                    raise ValueError(f"deposit label outside the code set in {rel}")
                rows.append({"source": "deposit", "file": "prosody/" + rel, "level": lv, "tier": name,
                             "label": lab, "count": n})
    for (rel, lv, name), c in sorted(ARCH_ROWS.items()):
        merged = Counter()
        for lab, n in c.items():
            merged[safe_label(lab)] += n
        for lab, n in sorted(merged.items()):
            rows.append({"source": "archive", "file": public_path(rel), "level": lv,
                         "tier": public_path(name), "label": lab, "count": n})
    write_csv("phase3_ipap_labels.csv", ["source", "file", "level", "tier", "label", "count"], rows)


if __name__ == "__main__":
    scope = sys.argv[1] if len(sys.argv) > 1 else "cid"
    root = ARCHIVE / "these_data" / "data" / "CID" if scope == "cid" else ARCHIVE
    main(sorted(p for p in root.rglob("*") if p.suffix.lower() == ".textgrid"))

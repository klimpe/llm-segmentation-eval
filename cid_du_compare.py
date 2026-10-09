"""Phase 3 stage 1, step 4: discourse units, archive (2012) vs deposit (2015).

For every deposit DU file (discourse/A, B, C) and every archive DU
annotation of the same speaker (DU/naive, DU/naive/original, DU/expert,
including the per-speaker tiers of the two-speaker NHLL files), compares
boundary sets by time, in both directions. Also A/ and B/ against C/.

Unit count = intervals with a non-blank label. Boundary = every internal
interval edge (each interval's xmin except the first). Counts only; no
conclusion about which version to use.
"""
import bisect
from collections import Counter
from pathlib import Path

from cid_textgrid import ARCHIVE_CID, DEPOSIT, SPEAKERS, public_path, read_textgrid, write_csv

TOL = 0.020

# The two-speaker NHLL files carry NH in the first DU tier and LL in the
# second (their token tiers have NH's and LL's token counts, 8088 and 4619,
# matching *_all.TextGrid). Referred to by index, not by the coder name in
# the file name.
NHLL = {"NHLL-0-15-adesoyer.TextGrid": "NHLL#1", "NHLL-0-15-mmartinez.TextGrid": "NHLL#2",
        "NHLL-mdesoyer.TextGrid": "NHLL#3", "NHLL-mmassot.TextGrid": "NHLL#4"}


def tier_stats(tier):
    items = tier.items
    units = sum(1 for i in items if i.text.strip())
    bounds = sorted({i.xmin for i in items[1:]})
    return units, bounds, (items[0].xmin, items[-1].xmax)


def labelled_window(tier):
    u = [i for i in tier.items if i.text.strip() and not i.text.startswith("dummy")]
    return u[0].xmin, u[-1].xmax


def archive_annotations():
    """{speaker: [(label, tier)]}"""
    out = {s: [] for s in SPEAKERS}
    du = ARCHIVE_CID / "DU"
    for p in sorted(du.rglob("*.TextGrid")):
        rel = str(p.relative_to(du))
        if p.name in NHLL:
            tg = read_textgrid(p)
            du_tiers = [t for t in tg.tiers if t.name.lower().replace(" ", "-").startswith("du")]
            assert len(du_tiers) == 2, (rel, [t.name for t in du_tiers])
            out["NH"].append((f"{Path(rel).parent}/{NHLL[p.name]}[NH]", du_tiers[0]))
            out["LL"].append((f"{Path(rel).parent}/{NHLL[p.name]}[LL]", du_tiers[1]))
            continue
        spk = p.name[:2]
        assert spk in out, rel
        tg = read_textgrid(p)
        assert len(tg.tiers) == 1, rel
        out[spk].append((rel, tg.tiers[0]))
    return out


def deposit_annotations():
    out = {}
    for sub in ("A", "B", "C"):
        for p in sorted((DEPOSIT / "discourse" / sub).glob("*.TextGrid")):
            tg = read_textgrid(p)
            assert len(tg.tiers) == 1
            out.setdefault(p.name[:2], []).append((f"{sub}/{p.name}", tg.tiers[0]))
    return out


def directional(xs, ys):
    """For each boundary in xs: exact in ys, within TOL (not exact), or absent."""
    c = Counter()
    for x in xs:
        k = bisect.bisect_left(ys, x)
        if k < len(ys) and ys[k] == x:
            c["exact"] += 1
            continue
        d = min((abs(x - ys[j]) for j in (k - 1, k) if 0 <= j < len(ys)), default=float("inf"))
        c["within20" if d <= TOL else "only"] += 1
    return c


def compare(a, b):
    ua, ba, sa = tier_stats(a)
    ub, bb, sb = tier_stats(b)
    ab, ba_ = directional(ba, bb), directional(bb, ba)
    return ua, ub, len(ba), len(bb), ab, ba_, sa, sb


def fmt(name_a, name_b, r):
    ua, ub, na, nb, ab, ba, sa, sb = r
    return (f"  {name_a} vs {name_b}: units {ua} / {ub}; boundaries {na} / {nb}; "
            f"A->B exact {ab['exact']} ±20ms {ab['within20']} only-A {ab['only']}; "
            f"B->A exact {ba['exact']} ±20ms {ba['within20']} only-B {ba['only']}; "
            f"span {sa[0]:.3f}-{sa[1]:.3f} / {sb[0]:.3f}-{sb[1]:.3f}")


ROWS = []


def category(label):
    """DU label with the deposit's trailing two-digit suffix removed."""
    lab = label.strip()
    return lab.rsplit(" ", 1)[0] if lab[-3:-2] == " " and lab[-2:].isdigit() else lab


def record(spk, name_a, a, name_b, b, scope, lo=None, hi=None):
    _, bnd_a, _ = tier_stats(a)
    _, bnd_b, _ = tier_stats(b)
    if scope == "window":
        bnd_a = [x for x in bnd_a if lo <= x <= hi]
        bnd_b = [x for x in bnd_b if lo <= x <= hi]
    ab, ba = directional(bnd_a, bnd_b), directional(bnd_b, bnd_a)
    same_iv = [(i.xmin, i.xmax) for i in a.items] == [(i.xmin, i.xmax) for i in b.items]
    ROWS.append({
        "speaker": spk, "file_a": public_path(name_a), "file_b": public_path(name_b), "scope": scope,
        "window_start_s": "" if lo is None else round(lo, 3), "window_end_s": "" if hi is None else round(hi, 3),
        # unit counts are whole-tier; left blank for window rows
        "units_a": tier_stats(a)[0] if scope == "whole" else "",
        "units_b": tier_stats(b)[0] if scope == "whole" else "",
        "boundaries_a": len(bnd_a), "boundaries_b": len(bnd_b),
        "a_exact": ab["exact"], "a_within_20ms": ab["within20"], "a_only": ab["only"],
        "b_exact": ba["exact"], "b_within_20ms": ba["within20"], "b_only": ba["only"],
        "identical_intervals": same_iv,
        "identical_categories": same_iv and all(category(x.text) == category(y.text)
                                                for x, y in zip(a.items, b.items)),
    })


def main():
    arch, dep = archive_annotations(), deposit_annotations()
    print("archive DU annotations per speaker:",
          {s: len(v) for s, v in arch.items()})
    print("deposit DU files per speaker:", {s: [n for n, _ in v] for s, v in dep.items()})
    print("speakers in both:", sorted(s for s in dep if arch.get(s)))
    for spk in SPEAKERS:
        if spk not in dep:
            continue
        print(f"\n{spk}")
        for dn, dt in dep[spk]:
            for an, at in arch[spk]:
                print(fmt(dn, an, compare(dt, at)))
                record(spk, "deposit/" + dn, dt, "archive/DU/" + an, at, "whole")
        cs = [x for x in dep[spk] if x[0].startswith("C/")]
        for dn, dt in dep[spk]:
            if dn.startswith(("A/", "B/")):
                for cn, ct in cs:
                    print(fmt(dn, cn, compare(dt, ct)) + "   [deposit vs deposit]")
                    record(spk, "deposit/" + dn, dt, "deposit/" + cn, ct, "whole")
                    # A/ and B/ cover part of the recording only; restrict both
                    # boundary sets to A/B's labelled window (ignoring the
                    # "dummy" filler intervals B/ uses outside it).
                    lo, hi = labelled_window(dt)
                    ba = [b for b in tier_stats(dt)[1] if lo <= b <= hi]
                    bc = [b for b in tier_stats(ct)[1] if lo <= b <= hi]
                    x, y = directional(ba, bc), directional(bc, ba)
                    record(spk, "deposit/" + dn, dt, "deposit/" + cn, ct, "window", lo, hi)
                    print(f"      within {lo:.3f}-{hi:.3f}s: boundaries {len(ba)} / {len(bc)}; "
                          f"A->B exact {x['exact']} ±20ms {x['within20']} only-A {x['only']}; "
                          f"B->A exact {y['exact']} ±20ms {y['within20']} only-B {y['only']}")


if __name__ == "__main__":
    main()
    write_csv("phase3_du_comparison.csv", list(ROWS[0]), ROWS)

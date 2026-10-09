"""Phase 3 stage 1, step 3: do other tiers' boundaries coincide with token
boundaries in the archive's *_all.TextGrid?

A boundary is every internal interval edge of a tier (each interval's xmin
except the first). Each is located against the token tier: exactly on a
token edge (float equality of the parsed values), strictly inside a token
interval (split by whether that interval is the pause "#" or not), or
outside the token tier's span. Offsets are to the nearest token edge.
Counts only.
"""
import bisect
import statistics
import sys
from collections import Counter

from cid_textgrid import ARCHIVE_CID, DEPOSIT, SPEAKERS, read_textgrid, write_csv

ALL_DIR = ARCHIVE_CID / "unsorted"
MG_TOKENS = ARCHIVE_CID / "tokens" / "MG_tokens.TextGrid"
TIERS = ("ip", "ap", "ipu", "periode", "degand-simon")
# Offset bins in ms (upper bounds, inclusive); 0 is exact.
BINS = (0.001, 1, 5, 10, 20, 50, 100, 500, float("inf"))


def bin_label(ms):
    lo = 0
    for hi in BINS:
        if ms <= hi:
            return f"({lo},{hi}]" if hi != float("inf") else f">{lo}"
        lo = hi


def locate(tokens, edges, t):
    """('exact'|'in_word'|'in_pause'|'outside', offset_ms to nearest token edge)."""
    k = bisect.bisect_left(edges, t)
    if k < len(edges) and edges[k] == t:
        return "exact", 0.0
    # signed: boundary time minus nearest token edge (positive = later)
    near = min((t - edges[j] for j in (k - 1, k) if 0 <= j < len(edges)), key=abs) * 1000
    if t < edges[0] or t > edges[-1]:
        return "outside", near
    # tokens are contiguous apart from four documented gaps (step 2); find
    # the interval containing t directly rather than assuming contiguity.
    j = bisect.bisect_right([i.xmin for i in tokens], t) - 1
    if j >= 0 and tokens[j].xmin < t < tokens[j].xmax:
        return ("in_pause" if tokens[j].text == "#" else "in_word"), near
    return "in_gap", near


def analyse(spk):
    tg = read_textgrid(ALL_DIR / f"{spk}_all.TextGrid")
    tokens = tg.tier("token").items
    edges = sorted({i.xmin for i in tokens} | {i.xmax for i in tokens})
    out = {}
    for name in TIERS:
        hits = [t for t in tg.tiers if t.name == name]
        if not hits:
            out[name] = None
            continue
        tier = hits[0]
        where, bins, signed = Counter(), Counter(), []
        for iv in tier.items[1:]:
            w, off = locate(tokens, edges, iv.xmin)
            where[w] += 1
            if w != "exact":
                bins[bin_label(abs(off))] += 1
                signed.append(off)
        out[name] = (len(tier.items) - 1, where, bins, signed)
    return out


# Rows for the committed tables, filled by main() and deposit_pu().
SUMMARY, OFFSETS = [], []
WHERE = ("exact", "in_word", "in_pause", "in_gap", "outside")


def record(comparison, spk, tier, n, where, bins, signed):
    row = {"comparison": comparison, "speaker": spk, "tier": tier, "boundaries": n}
    row.update({k: where[k] for k in WHERE})
    row["exact_share"] = round(where["exact"] / n, 4) if n else ""
    if len(signed) >= 2:
        q = statistics.quantiles(signed, n=4, method="inclusive")
        row.update(signed_min_ms=round(min(signed), 1), signed_q1_ms=round(q[0], 1),
                   signed_median_ms=round(q[1], 1), signed_q3_ms=round(q[2], 1),
                   signed_max_ms=round(max(signed), 1))
    row["earlier_than_edge"] = sum(x < 0 for x in signed)
    row["later_than_edge"] = sum(x > 0 for x in signed)
    SUMMARY.append(row)
    for b in bin_order():
        OFFSETS.append({"comparison": comparison, "speaker": spk, "tier": tier,
                        "abs_offset_bin_ms": b, "boundaries": bins[b]})


def bin_order():
    lo, out = 0, []
    for hi in BINS:
        out.append(f"({lo},{hi}]" if hi != float("inf") else f">{lo}")
        lo = hi
    return out


def main(speakers):
    total = {n: (0, Counter(), Counter(), []) for n in TIERS}
    for spk in speakers:
        res = analyse(spk)
        print(f"\n{spk}")
        for name, r in res.items():
            if r is None:
                print(f"  {name}: tier absent")
                continue
            n, where, bins, signed = r
            print(f"  {name}: {n} boundaries; " + ", ".join(f"{k} {where[k]}" for k in
                  ("exact", "in_word", "in_pause", "in_gap", "outside")))
            if bins:
                print("     non-exact offsets (ms): " + ", ".join(f"{b} {c}" for b, c in
                      sorted(bins.items(), key=lambda kv: float(kv[0].strip('(>').split(',')[0]))))
            print("     " + signed_summary(signed))
            record("all_tier_vs_token", spk, name, n, where, bins, signed)
            tn, tw, tb, ts = total[name]
            total[name] = (tn + n, tw + where, tb + bins, ts + signed)
    if len(speakers) > 1:
        print("\nALL")
        for name, (n, where, bins, signed) in total.items():
            record("all_tier_vs_token", "ALL", name, n, where, bins, signed)
            print(f"  {name}: {n} boundaries; " + ", ".join(f"{k} {where[k]}" for k in
                  ("exact", "in_word", "in_pause", "in_gap", "outside")))
            print("     non-exact offsets (ms): " + ", ".join(f"{b} {c}" for b, c in
                  sorted(bins.items(), key=lambda kv: float(kv[0].strip('(>').split(',')[0]))))
            print("     " + signed_summary(signed))


def signed_summary(xs):
    if len(xs) < 2:
        return f"signed offsets (ms): n={len(xs)}"
    q = statistics.quantiles(xs, n=4, method="inclusive")
    neg = sum(x < 0 for x in xs)
    return (f"signed offsets (ms), non-exact: n={len(xs)} min {min(xs):.1f} q1 {q[0]:.1f} "
            f"med {q[1]:.1f} q3 {q[2]:.1f} max {max(xs):.1f}; earlier than edge {neg}, later {len(xs) - neg}")


def deposit_pu(speakers):
    """Supplementary: the deposit's prosody/ IP and AP tiers (all 16 speakers,
    four of them under low-kappa/) against the archive token tier (MG's from
    tokens/MG_tokens.TextGrid, which is identical to *_all for the others)."""
    total = {lv: (0, Counter(), Counter(), []) for lv in ("IP", "AP")}
    for spk in speakers:
        pu = DEPOSIT / "prosody" / f"{spk}_PU.TextGrid"
        if not pu.exists():
            pu = DEPOSIT / "prosody" / "low-kappa" / f"D_{spk}_PU.TextGrid"
        src = MG_TOKENS if spk == "MG" else ALL_DIR / f"{spk}_all.TextGrid"
        tokens = read_textgrid(src).tier("token").items
        edges = sorted({i.xmin for i in tokens} | {i.xmax for i in tokens})
        tg = read_textgrid(pu)
        print(f"\n{spk} ({pu.relative_to(DEPOSIT)})")
        for t in tg.tiers:
            lv = t.name[:2].upper()
            where, bins, signed = Counter(), Counter(), []
            for iv in t.items[1:]:
                w, off = locate(tokens, edges, iv.xmin)
                where[w] += 1
                if w != "exact":
                    bins[bin_label(abs(off))] += 1
                    signed.append(off)
            n = len(t.items) - 1
            print(f"  {t.name}: {n} boundaries; " + ", ".join(f"{k} {where[k]}" for k in
                  ("exact", "in_word", "in_pause", "in_gap", "outside")))
            print("     " + signed_summary(signed))
            record("deposit_pu_vs_token", spk, t.name, n, where, bins, signed)
            tn, tw, tb, ts = total[lv]
            total[lv] = (tn + n, tw + where, tb + bins, ts + signed)
    print("\nALL (deposit IP/AP vs archive token tier)")
    for lv, (n, where, bins, signed) in total.items():
        record("deposit_pu_vs_token", "ALL", lv, n, where, bins, signed)
        print(f"  {lv}: {n} boundaries; " + ", ".join(f"{k} {where[k]}" for k in
              ("exact", "in_word", "in_pause", "in_gap", "outside")))
        print("     non-exact offsets (ms): " + ", ".join(f"{b} {c}" for b, c in
              sorted(bins.items(), key=lambda kv: float(kv[0].strip('(>').split(',')[0]))))
        print("     " + signed_summary(signed))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--deposit-pu"]:
        deposit_pu(sys.argv[2:] or list(SPEAKERS))
        sys.exit()
    if sys.argv[1:]:
        main(sys.argv[1:])
        sys.exit()
    # Full run: both comparisons, all speakers, and the committed tables.
    main(sorted(p.name.split("_")[0] for p in ALL_DIR.glob("*_all.TextGrid")))
    deposit_pu(list(SPEAKERS))
    cols = ["comparison", "speaker", "tier", "boundaries", *WHERE, "exact_share",
            "signed_min_ms", "signed_q1_ms", "signed_median_ms", "signed_q3_ms", "signed_max_ms",
            "earlier_than_edge", "later_than_edge"]
    write_csv("phase3_alignment.csv", cols, SUMMARY)
    write_csv("phase3_alignment_offsets.csv",
              ["comparison", "speaker", "tier", "abs_offset_bin_ms", "boundaries"], OFFSETS)

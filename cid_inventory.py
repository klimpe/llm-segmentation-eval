"""Phase 3 stage 1, step 1: inventory of the CID archive and deposit.

Prints to the terminal only. Reports file names, encodings, tier names and
counts; never transcript text.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from cid_textgrid import (ARCHIVE, ARCHIVE_CID, DEPOSIT, SPEAKERS,
                          EncodingUndetermined, TextGridFormatError,
                          public_path, read_textgrid, write_csv)

SPEAKER_RE = re.compile(r"(?<![A-Z])(" + "|".join(SPEAKERS) + r")(?![A-Za-z])")


def speakers_in_name(name: str) -> set[str]:
    return set(SPEAKER_RE.findall(name))


# Archive areas listed directory by directory in the committed tables.
# Everything else in the archive (the thesis working tree: drafts,
# figures, other corpora) is collapsed to "<top-level dir>/*".
CID_AREAS = ("CID", "these_data/data/CID", "these_data/data/stratCID")


def table_dir(source: str, d: str) -> str:
    if source == "deposit" or any(d == a or d.startswith(a + "/") for a in CID_AREAS):
        return public_path(d)
    return d.split("/", 1)[0] + "/*" if "/" in d else d


def all_files(root: Path):
    return sorted(p for p in root.rglob("*") if p.is_file())


def main():
    dir_rows = []
    for label, root in (("archive", ARCHIVE), ("deposit", DEPOSIT.parent.parent)):
        files = all_files(root)
        print(f"\n=== {label}: {root}  ({len(files)} files)")
        by_dir = Counter(str(p.parent.relative_to(root)) for p in files)
        agg = Counter()
        for d, n in by_dir.items():
            agg[table_dir(label, d)] += n
        dir_rows += [{"source": label, "directory": d, "files": n} for d, n in sorted(agg.items())]
        if label == "archive":
            top = Counter(p.relative_to(root).parts[0] if len(p.relative_to(root).parts) > 1 else "."
                          for p in files)
            print("files by top-level directory:")
            for d, n in sorted(top.items()):
                print(f"  {n:6d}  {d}")
            print("files by directory under these_data/data/CID:")
            for d, n in sorted(by_dir.items()):
                if d.startswith("these_data/data/CID"):
                    print(f"  {n:6d}  {d}")
        else:
            for d, n in sorted(by_dir.items()):
                print(f"  {n:6d}  {d}")

    # Every TextGrid, both sources: encoding and tier names.
    print("\n=== TextGrids")
    enc_by_dir = defaultdict(Counter)
    sig_by_dir = defaultdict(Counter)
    failures = []
    per_file = {}
    for label, root in (("archive", ARCHIVE), ("deposit", DEPOSIT)):
        for p in all_files(root):
            if p.suffix.lower() != ".textgrid":
                continue
            rel = f"{label}/{p.relative_to(root)}"
            d = str(Path(rel).parent)
            try:
                tg = read_textgrid(p)
            except (EncodingUndetermined, TextGridFormatError) as e:
                failures.append((rel, type(e).__name__, str(e)[:80]))
                enc_by_dir[d]["FAILED"] += 1
                continue
            enc_by_dir[d][tg.encoding] += 1
            names = tuple(f"{t.name}{'' if t.cls == 'IntervalTier' else '(pt)'}" for t in tg.tiers)
            sig_by_dir[d][names] += 1
            per_file[rel] = (tg.encoding, names)

    print("\nencoding by directory (all TextGrids):")
    tot = Counter()
    for d in sorted(enc_by_dir):
        tot.update(enc_by_dir[d])
        print(f"  {d}: {dict(enc_by_dir[d])}")
    print(f"  TOTAL: {dict(tot)}")

    print(f"\nfailures: {len(failures)}")
    for f in failures:
        print("  ", *f)

    focus = [r for r in per_file
             if r.startswith("deposit/")
             or "/unsorted/" in r and r.endswith("_all.TextGrid")
             or "/CID/DU/" in r]
    print("\nper-file encoding and tiers (deposit, archive *_all, archive DU/):")
    for r in sorted(focus):
        enc, names = per_file[r]
        print(f"  {r}\t{enc}\t{', '.join(names)}")

    print("\ntier signatures by directory (all TextGrids):")
    for d in sorted(sig_by_dir):
        for sig, n in sig_by_dir[d].most_common():
            print(f"  {d}\t{n}\t{', '.join(sig)}")

    print("\nspeaker coverage by directory (from file names, CID-relevant dirs):")
    cov = defaultdict(set)
    for r in per_file:
        if r.startswith("deposit/") or "/CID/" in r or "TRASP" in r:
            cov[str(Path(r).parent)] |= speakers_in_name(Path(r).name)
    for d in sorted(cov):
        missing = sorted(set(SPEAKERS) - cov[d])
        print(f"  {d}\t{len(cov[d])}/16\tmissing: {' '.join(missing) if missing else '-'}")

    # --- committed tables (counts, paths, tier names; no labels) ---
    write_csv("phase3_files_by_directory.csv", ["source", "directory", "files"], dir_rows)
    def split(d):
        src, _, rest = d.partition("/")
        return src, table_dir(src, rest)
    enc_agg = Counter()
    for d, c in enc_by_dir.items():
        for e, n in c.items():
            enc_agg[(*split(d), e)] += n
    write_csv("phase3_encodings.csv", ["source", "directory", "encoding", "files"],
              [{"source": s_, "directory": d, "encoding": e, "files": n}
               for (s_, d, e), n in sorted(enc_agg.items())])
    refused = Counter((*split(str(Path(r).parent)), err) for r, err, _ in failures)
    write_csv("phase3_refused_textgrids.csv", ["source", "directory", "error", "files"],
              [{"source": s_, "directory": d, "error": err, "files": n}
               for (s_, d, err), n in sorted(refused.items())])
    write_csv("phase3_tiers_by_file.csv",
              ["source", "file", "encoding", "tier_index", "tier", "point_tier"],
              [{"source": r.split("/", 1)[0], "file": public_path(r.split("/", 1)[1]),
                "encoding": per_file[r][0], "tier_index": i + 1,
                "tier": public_path(t.removesuffix("(pt)")), "point_tier": t.endswith("(pt)")}
               for r in sorted(focus) for i, t in enumerate(per_file[r][1])])
    write_csv("phase3_speaker_coverage.csv", ["source", "directory", "speaker", "present"],
              [{"source": split(d)[0], "directory": split(d)[1], "speaker": spk, "present": spk in cov[d]}
               for d in sorted(cov) for spk in SPEAKERS if "/*" not in split(d)[1]])

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

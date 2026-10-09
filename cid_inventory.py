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
                          read_textgrid)

SPEAKER_RE = re.compile(r"(?<![A-Z])(" + "|".join(SPEAKERS) + r")(?![A-Za-z])")


def speakers_in_name(name: str) -> set[str]:
    return set(SPEAKER_RE.findall(name))


def all_files(root: Path):
    return sorted(p for p in root.rglob("*") if p.is_file())


def main():
    for label, root in (("archive", ARCHIVE), ("deposit", DEPOSIT.parent.parent)):
        files = all_files(root)
        print(f"\n=== {label}: {root}  ({len(files)} files)")
        by_dir = Counter(str(p.parent.relative_to(root)) for p in files)
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
            except (EncodingUndetermined, TextGridFormatError, UnicodeDecodeError) as e:
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

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

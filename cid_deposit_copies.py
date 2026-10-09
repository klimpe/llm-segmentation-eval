"""Phase 3 stage 1: which deposit discourse/ and prosody/ files have an
identical copy in the archive's these_data/data/stratCID/ (reports/
phase3_data.md §4.5, §5.3).

Identical = for prosody, the same tier names and every interval (xmin,
xmax, label) equal; for discourse (single-tier files), some tier of the
archive file with every interval equal. Writes reports/
phase3_deposit_copies.csv (paths and tier names only).
"""
from cid_textgrid import (ARCHIVE, DEPOSIT, EncodingUndetermined, TextGridFormatError,
                          public_path, read_textgrid, write_csv)

STRAT = ARCHIVE / "these_data" / "data" / "stratCID"


def sig(tier):
    return [(i.xmin, i.xmax, i.text) if hasattr(i, "xmin") else (i.time, i.mark) for i in tier.items]


def main():
    archive = {}
    for q in sorted(STRAT.rglob("*.TextGrid")):
        try:
            archive[q] = read_textgrid(q)
        except (EncodingUndetermined, TextGridFormatError):
            continue
    rows = []
    for kind in ("prosody", "discourse"):
        for p in sorted((DEPOSIT / kind).rglob("*.TextGrid")):
            dt = read_textgrid(p)
            hits = []
            for q, at in archive.items():
                if kind == "prosody":
                    if ([t.name for t in at.tiers] == [t.name for t in dt.tiers]
                            and all(sig(a) == sig(b) for a, b in zip(at.tiers, dt.tiers))):
                        hits.append((q, ""))
                else:
                    hits += [(q, t.name) for t in at.tiers if sig(t) == sig(dt.tiers[0])]
            rel = f"{kind}/{p.relative_to(DEPOSIT / kind)}"
            print(rel, [str(q.relative_to(STRAT)) for q, _ in hits])
            for q, tier in hits or [(None, "")]:
                rows.append({"deposit_file": rel,
                             "archive_copy": "" if q is None else public_path(str(q.relative_to(ARCHIVE))),
                             "archive_tier": public_path(tier)})
    write_csv("phase3_deposit_copies.csv", ["deposit_file", "archive_copy", "archive_tier"], rows)


if __name__ == "__main__":
    main()

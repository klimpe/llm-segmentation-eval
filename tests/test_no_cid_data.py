"""CID is under embargo until 2065 (Code du Patrimoine AR048, privacy) and
this repository is public. Nothing from the CID archive (~/work2/these) or
the Ortolang deposit (~/work2/ortolang-000918) may be tracked here.

Fails if any tracked file sits under a path component named these/ or
ortolang-*/, is a TextGrid by extension, or contains a Praat TextGrid header
in any of the encodings the CID files use (ASCII/UTF-8, UTF-16 either byte
order) -- so a renamed or embedded TextGrid is caught too, not only *.TextGrid.
Also checks that the two data roots resolve outside the repository.
"""
import fnmatch
import subprocess
from pathlib import Path

from cid_textgrid import ARCHIVE, DEPOSIT

REPO_ROOT = Path(__file__).resolve().parent.parent

# Built by concatenation so this file does not itself contain the header.
_HEADER = 'File type = "oo' + 'TextFile"'
_NEEDLES = [_HEADER.encode(enc) for enc in ("utf-8", "utf-16-be", "utf-16-le")]


def _tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True,
                         capture_output=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def test_tracked_files_are_listed():
    # Guard against the checks below passing vacuously.
    assert len(_tracked()) > 20


def test_no_tracked_file_under_a_cid_data_directory():
    bad = [p for p in _tracked()
           if any(part == "these" or fnmatch.fnmatch(part, "ortolang-*")
                  for part in Path(p).parts[:-1])]
    assert not bad, f"tracked files under these/ or ortolang-*/: {bad}"


def test_no_tracked_textgrid():
    bad = []
    for p in _tracked():
        path = REPO_ROOT / p
        if p.lower().endswith(".textgrid"):
            bad.append(p)
            continue
        if path.is_symlink() or not path.is_file():
            continue
        data = path.read_bytes()
        if any(n in data for n in _NEEDLES):
            bad.append(p)
    assert not bad, f"tracked TextGrid content: {bad}"


def test_no_tracked_symlink_into_cid_data():
    roots = [r.resolve() for r in (ARCHIVE, DEPOSIT.parent.parent)]
    bad = []
    for p in _tracked():
        path = REPO_ROOT / p
        if path.is_symlink():
            target = path.resolve()
            if any(target == r or r in target.parents for r in roots):
                bad.append(p)
    assert not bad, f"tracked symlinks into CID data: {bad}"


def test_cid_data_roots_are_outside_the_repository():
    repo = REPO_ROOT.resolve()
    for root in (ARCHIVE, DEPOSIT.parent.parent):
        r = root.resolve()
        assert r != repo and repo not in r.parents, f"{root} resolves inside the repository"

"""Phase 3 (CID): strict Praat TextGrid reading, in place, from outside the repo.

CID is under embargo (Code du Patrimoine AR048) and this repository is
public: nothing here writes transcript text anywhere. The data stays in
ARCHIVE / DEPOSIT and is read where it lies.

Encoding is detected per file, explicitly, and a file that is none of the
recognised encodings raises -- never decoded with substitution, never
guessed with a permissive fallback (latin-1 decodes any byte string, which
is exactly the turn-a-problem-into-plausible-data failure to avoid).
"""
import re
from dataclasses import dataclass
from pathlib import Path

ARCHIVE = Path.home() / "work2" / "these"
DEPOSIT = Path.home() / "work2" / "ortolang-000918" / "ortolang-000918" / "2"
ARCHIVE_CID = ARCHIVE / "these_data" / "data" / "CID"

SPEAKERS = ("AB", "AC", "AG", "AP", "BX", "CM", "EB", "IM",
            "LJ", "LL", "MB", "MG", "ML", "NH", "SR", "YM")


class EncodingUndetermined(ValueError):
    pass


class TextGridFormatError(ValueError):
    pass


def detect_encoding(raw: bytes) -> str:
    """Name of the codec this file is in. Raises if it is none we recognise."""
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be-bom"
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le-bom"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if b"\x00" in raw:
        # UTF-16 without BOM, or binary: not guessing which.
        raise EncodingUndetermined("NUL bytes and no BOM")
    if all(b < 0x80 for b in raw):
        return "ascii"
    try:
        raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        raise EncodingUndetermined(f"not ASCII, not valid UTF-8: {e}") from None
    return "utf-8"


_CODEC = {
    "utf-16-be-bom": "utf-16",   # the BOM tells the codec the byte order
    "utf-16-le-bom": "utf-16",
    "utf-8-sig": "utf-8-sig",
    "ascii": "ascii",
    "utf-8": "utf-8",
}


def read_text(path: Path) -> tuple[str, str]:
    raw = Path(path).read_bytes()
    enc = detect_encoding(raw)
    # Line ends normalised as Praat does on reading, including inside a
    # label (a few disfluency labels contain a CRLF).
    try:
        text = raw.decode(_CODEC[enc], errors="strict")
    except UnicodeDecodeError as e:
        # e.g. a UTF-8 BOM in front of bytes that are not UTF-8
        raise EncodingUndetermined(f"BOM says {enc}, content does not decode: {e}") from None
    return text.replace("\r\n", "\n").replace("\r", "\n"), enc


@dataclass
class Interval:
    xmin: float
    xmax: float
    text: str


@dataclass
class Point:
    time: float
    mark: str


@dataclass
class Tier:
    cls: str       # "IntervalTier" or "TextTier"
    name: str
    xmin: float
    xmax: float
    items: list    # list[Interval] or list[Point]


@dataclass
class TextGrid:
    xmin: float
    xmax: float
    tiers: list
    encoding: str

    def tier(self, name: str) -> Tier:
        hits = [t for t in self.tiers if t.name == name]
        if len(hits) != 1:
            raise KeyError(f"{len(hits)} tiers named {name!r}")
        return hits[0]


# Praat's text reader takes only strings, numbers and <flags> from the file
# and ignores the labels around them ("xmin =", "intervals [3]:"), which is
# what lets one reader handle both the long and the short format. The
# bracketed indices of the long format are numbers too, so they are matched
# (and dropped) as their own token before the number pattern sees them.
_TOKEN = re.compile(
    r'"((?:[^"]|"")*)"'                       # 1: string, "" escapes a quote
    r'|(\[\s*\d*\s*\])'                       # 2: long-format index, ignored
    r'|(-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)'  # 3: number
    r'|(<exists>|<absent>)'                    # 4: flag
)


def _tokens(text: str):
    for m in _TOKEN.finditer(text):
        if m.group(1) is not None:
            yield ("s", m.group(1).replace('""', '"'))
        elif m.group(3) is not None:
            yield ("n", m.group(3))
        elif m.group(4) is not None:
            yield ("f", m.group(4))


def parse(text: str, encoding: str = "") -> TextGrid:
    toks = list(_tokens(text))
    pos = 0

    def take(kind):
        nonlocal pos
        if pos >= len(toks):
            raise TextGridFormatError(f"unexpected end of file, wanted {kind}")
        k, v = toks[pos]
        if k != kind:
            raise TextGridFormatError(f"token {pos}: wanted {kind}, got {k} {v!r}")
        pos += 1
        return v

    # "ooTextFile short" is the older header of the short format; Praat
    # still reads it.
    if take("s") not in ("ooTextFile", "ooTextFile short") or take("s") != "TextGrid":
        raise TextGridFormatError("not a Praat text TextGrid")
    xmin, xmax = float(take("n")), float(take("n"))
    if take("f") != "<exists>":
        return TextGrid(xmin, xmax, [], encoding)
    n_tiers = int(take("n"))
    tiers = []
    for _ in range(n_tiers):
        cls, name = take("s"), take("s")
        txmin, txmax, n = float(take("n")), float(take("n")), int(take("n"))
        items = []
        if cls == "IntervalTier":
            for _ in range(n):
                items.append(Interval(float(take("n")), float(take("n")), take("s")))
        elif cls == "TextTier":
            for _ in range(n):
                items.append(Point(float(take("n")), take("s")))
        else:
            raise TextGridFormatError(f"unknown tier class {cls!r}")
        tiers.append(Tier(cls, name, txmin, txmax, items))
    if pos != len(toks):
        raise TextGridFormatError(f"{len(toks) - pos} trailing tokens")
    return TextGrid(xmin, xmax, tiers, encoding)


def read_textgrid(path: Path) -> TextGrid:
    text, enc = read_text(path)
    return parse(text, enc)


# --- committed result tables -------------------------------------------------

REPORTS = Path(__file__).resolve().parent / "reports"

# Annotators' names as they occur in file and tier names (both sources).
# Each person gets a fixed placeholder, so that two coders' files for the
# same speaker stay distinct after replacement. Coders are otherwise
# referred to by the archive's own two-letter initials.
_PEOPLE = [
    (r"Anita(?:[-_]?El[Hh]ajj|elhajj)?", "<p1>"),
    (r"Julie", "<p2>"),
    (r"antoine", "<p3>"),
    (r"irina", "<p4>"),
    (r"laurent", "<p5>"),
    (r"adesoyer", "<p6>"),
    (r"mdesoyer", "<p7>"),
    (r"mmartinez", "<p8>"),
    (r"mmassot", "<p9>"),
    (r"Stephane", "<p10>"),
    (r"Bertille", "<p11>"),
    (r"Brigitte", "<p12>"),
    (r"roxane", "<p13>"),
]
_PEOPLE_RE = [(re.compile(pat, re.I), rep) for pat, rep in _PEOPLE]
_PERSON = re.compile("|".join(pat for pat, _ in _PEOPLE), re.I)


def public_path(rel: str) -> str:
    """File, directory or tier name with personal names replaced."""
    for rx, rep in _PEOPLE_RE:
        rel = rx.sub(rep, rel)
    return rel


def write_csv(name: str, fieldnames, rows):
    """Write reports/<name>. Counts, codes and paths only -- never labels
    taken from a transcript tier."""
    import csv
    path = REPORTS / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {path.relative_to(REPORTS.parent)} ({len(rows)} rows)")

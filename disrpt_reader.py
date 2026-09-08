from collections.abc import Iterator

from masses import flags_to_masses


def iter_tok_documents(path: str) -> Iterator[tuple[str, list[str], list[int]]]:
    """Parse every document out of a DISRPT .tok file, yielding
    (doc_id, tokens, masses) for each in file order.

    .tok format: tab-separated columns (token index, token, 8 unused columns,
    misc), one token per line. A `# newdoc_id = <id>` comment line starts each
    document; a blank line separates documents. A token line's misc column
    contains `BeginSeg=Yes` iff a new discourse unit begins at that token.
    """
    tokens: list[str] = []
    flags: list[bool] = []
    current_id: str | None = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            if line.startswith("# newdoc_id ="):
                if current_id is not None:
                    yield current_id, tokens, flags_to_masses(flags)
                current_id = line.split("=", 1)[1].strip()
                tokens = []
                flags = []
                continue

            if current_id is None or not line.strip():
                continue  # before the first document, or a blank separator line

            fields = line.split("\t")
            if "-" in fields[0]:
                continue  # CoNLL-U multiword-token range row (e.g. "1-2  What'd"):
                # a grouping header, not a token; the sub-token rows that
                # follow carry the real annotations (matches DISRPT's own
                # utils/seg_eval.py, which skips these the same way)

            tokens.append(fields[1])
            misc = fields[-1]
            flags.append("BeginSeg=Yes" in misc.split("|"))

    if current_id is not None:
        yield current_id, tokens, flags_to_masses(flags)


def read_tok_document(path: str, doc_id: str | None = None) -> tuple[str, list[str], list[int]]:
    """Parse one document out of a DISRPT .tok file into (doc_id, tokens, masses).

    If doc_id is None, parses the first document in the file. Raises
    ValueError if doc_id is given but not found.
    """
    for current_id, tokens, masses in iter_tok_documents(path):
        if doc_id is None or current_id == doc_id:
            return current_id, tokens, masses

    raise ValueError(f"document {doc_id!r} not found in {path}")

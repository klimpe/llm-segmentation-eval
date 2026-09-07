from masses import flags_to_masses


def read_tok_document(path: str, doc_id: str | None = None) -> tuple[str, list[int]]:
    """Parse one document out of a DISRPT .tok file into (doc_id, masses).

    .tok format: tab-separated columns (token index, token, 8 unused columns,
    misc), one token per line. A `# newdoc_id = <id>` comment line starts each
    document; a blank line ends it. A token line's misc column contains
    `BeginSeg=Yes` iff a new discourse unit begins at that token.

    If doc_id is None, parses the first document in the file. Raises
    ValueError if doc_id is given but not found.
    """
    flags: list[bool] = []
    current_id: str | None = None
    found = False

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            if line.startswith("# newdoc_id ="):
                if found:
                    break  # requested (or first) document is complete
                current_id = line.split("=", 1)[1].strip()
                if doc_id is None or current_id == doc_id:
                    found = True
                    flags = []
                continue

            if not found:
                continue

            if not line.strip():
                break  # blank line ends the document

            fields = line.split("\t")
            misc = fields[-1]
            flags.append("BeginSeg=Yes" in misc.split("|"))

    if not found:
        raise ValueError(f"document {doc_id!r} not found in {path}")

    return current_id, flags_to_masses(flags)

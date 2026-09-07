import json
import re
from pathlib import Path

from anthropic import Anthropic

from masses import assert_comparable, flags_to_masses

DEFAULT_MODEL = "claude-sonnet-5"

PROMPT_TEMPLATE = """You segment text into elementary discourse units (EDUs), \
following RST-DT-style segmentation guidelines: most clauses are separate \
units, including adnominal and other nested/subordinate clauses; \
coordinated clauses are usually split; simple noun phrases, single \
prepositional phrases, and other short constituents are usually not split \
out on their own.

Below is a tokenized document, one token per line, each prefixed with its \
1-indexed position. Identify every token position at which a new EDU \
begins (the first token always begins one).

Respond with nothing but a JSON array of the 1-indexed positions where a \
new EDU begins, e.g. [1, 4, 9, 15]. No other text, no markdown fences.

{numbered_tokens}
"""


def build_prompt(tokens: list[str]) -> str:
    numbered_tokens = "\n".join(f"{i + 1}\t{tok}" for i, tok in enumerate(tokens))
    return PROMPT_TEMPLATE.format(numbered_tokens=numbered_tokens)


def _default_client() -> Anthropic:
    # The installed Brotli build's Decompressor API doesn't match what this
    # environment's httpx2 expects (Brotli 1.1.0's process() takes no
    # keyword arguments, but httpx2 calls it with output_buffer_limit=...),
    # so responses hang/crash mid-decode. Disable brotli in the request so
    # the server sends gzip instead.
    return Anthropic(default_headers={"accept-encoding": "gzip, deflate"})


def call_model(prompt: str, model: str = DEFAULT_MODEL, client: Anthropic | None = None) -> str:
    client = client or _default_client()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def parse_boundary_indices(raw_output: str) -> list[int]:
    """Extract the JSON array of 1-indexed boundary-start positions from raw
    model output. Raises ValueError if no array of integers can be found."""
    match = re.search(r"\[[\d,\s]*\]", raw_output)
    if not match:
        raise ValueError("no JSON array of indices found in model output")
    try:
        indices = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed JSON array in model output: {e}") from e
    if not all(isinstance(i, int) for i in indices):
        raise ValueError(f"non-integer entries in boundary indices: {indices}")
    return indices


def indices_to_masses(indices: list[int], n_tokens: int) -> list[int]:
    """Convert 1-indexed EDU-start positions into masses. The first token
    always starts a unit regardless of whether the model included it."""
    out_of_range = [i for i in indices if not (1 <= i <= n_tokens)]
    if out_of_range:
        raise ValueError(f"boundary indices out of range [1,{n_tokens}]: {out_of_range}")
    flags = [False] * n_tokens
    for i in indices:
        flags[i - 1] = True
    flags[0] = True
    return flags_to_masses(flags)


def segment_document(
    tokens: list[str],
    ref_masses: list[int],
    doc_id: str,
    output_dir: Path,
    model: str = DEFAULT_MODEL,
    client: Anthropic | None = None,
) -> list[int]:
    """Prompt the model to segment `tokens`, caching and persisting the raw
    response under output_dir/{doc_id}.txt (one file per document; reused on
    a later call instead of re-querying). Parses the response into masses and
    verifies they cover the same number of tokens as ref_masses. Raises
    ValueError on any parse or alignment failure -- callers must catch this,
    set the document aside, and report it, never compute a metric on it.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / f"{doc_id}.txt"

    if raw_path.exists():
        raw_output = raw_path.read_text(encoding="utf-8")
    else:
        prompt = build_prompt(tokens)
        raw_output = call_model(prompt, model=model, client=client)
        raw_path.write_text(raw_output, encoding="utf-8")

    indices = parse_boundary_indices(raw_output)
    hyp_masses = indices_to_masses(indices, len(tokens))
    assert_comparable(ref_masses, hyp_masses)
    return hyp_masses

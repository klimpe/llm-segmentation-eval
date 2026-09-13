import json
import re
from pathlib import Path

from anthropic import Anthropic

from masses import assert_comparable, flags_to_masses, masses_to_boundaries

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


FEWSHOT_PROMPT_TEMPLATE = """You segment text into elementary discourse units (EDUs), \
following RST-DT-style segmentation guidelines: most clauses are separate \
units, including adnominal and other nested/subordinate clauses; \
coordinated clauses are usually split; simple noun phrases, single \
prepositional phrases, and other short constituents are usually not split \
out on their own.

Here are worked examples of correct segmentation, in the same format you \
will use to answer: a tokenized excerpt, one token per line prefixed with \
its 1-indexed position, followed by the correct JSON array of EDU-start \
positions.

{examples}
Now segment the following document the same way.

Below is a tokenized document, one token per line, each prefixed with its \
1-indexed position. Identify every token position at which a new EDU \
begins (the first token always begins one).

Respond with nothing but a JSON array of the 1-indexed positions where a \
new EDU begins, e.g. [1, 4, 9, 15]. No other text, no markdown fences.

{numbered_tokens}
"""

FEWSHOT_EXAMPLE_TEMPLATE = """Example {n}:
{numbered_tokens}

Correct EDU-start positions: {indices}

"""


def _numbered_tokens(tokens: list[str]) -> str:
    return "\n".join(f"{i + 1}\t{tok}" for i, tok in enumerate(tokens))


def build_fewshot_prompt(tokens: list[str], examples: list[tuple[list[str], list[int]]]) -> str:
    """Same task and instructions as build_prompt, with worked examples shown
    first: each is (example_tokens, example_boundary_indices), drawn from
    reference-annotated data (train split only -- never dev or test).
    """
    examples_text = "".join(
        FEWSHOT_EXAMPLE_TEMPLATE.format(n=i, numbered_tokens=_numbered_tokens(ex_tokens), indices=ex_indices)
        for i, (ex_tokens, ex_indices) in enumerate(examples, start=1)
    )
    return FEWSHOT_PROMPT_TEMPLATE.format(examples=examples_text, numbered_tokens=_numbered_tokens(tokens))


def _default_client() -> Anthropic:
    # The installed Brotli build's Decompressor API doesn't match what this
    # environment's httpx2 expects (Brotli 1.1.0's process() takes no
    # keyword arguments, but httpx2 calls it with output_buffer_limit=...),
    # so responses hang/crash mid-decode. Disable brotli in the request so
    # the server sends gzip instead.
    return Anthropic(default_headers={"accept-encoding": "gzip, deflate"})


def call_model(
    prompt: str, model: str = DEFAULT_MODEL, client: Anthropic | None = None, temperature: float = 0
) -> str:
    client = client or _default_client()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        # This task just needs a JSON array back, not a rationale. With
        # thinking left on its default, some responses burned the entire
        # max_tokens budget on thinking (stop_reason="max_tokens",
        # thinking_tokens=8192) and returned zero text blocks -- an
        # alignment failure for every such document. Disabling it fixes
        # this and is cheaper.
        thinking={"type": "disabled"},
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _coerce_index(value) -> int:
    if isinstance(value, bool):  # bool is a subclass of int in Python; reject true/false
        raise TypeError(f"boolean is not a valid index: {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)  # raises ValueError if not a clean integer string
    raise TypeError(f"cannot interpret {value!r} as an integer index")


def parse_boundary_indices(raw_output: str) -> list[int]:
    """Extract the JSON array of 1-indexed boundary-start positions from raw
    model output. Raises ValueError if no array of integers can be found.

    Greedy match from the first "[" to the last "]": if the model wraps its
    answer in extra text containing stray brackets, this either still finds
    the real (single) array, or fails loudly on malformed JSON -- never
    silently parses a wrong, smaller bracket pair as the real answer.

    Individual elements that are numeric strings (e.g. "1" instead of 1,
    seen in practice) are accepted; anything else non-integer is rejected.
    """
    match = re.search(r"\[.*\]", raw_output, re.DOTALL)
    if not match:
        raise ValueError("no JSON array of indices found in model output")
    try:
        indices = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed JSON array in model output: {e}") from e
    try:
        return [_coerce_index(i) for i in indices]
    except (TypeError, ValueError) as e:
        raise ValueError(f"non-integer entries in boundary indices: {indices}") from e


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


def masses_to_indices(masses: list[int]) -> list[int]:
    """Inverse of indices_to_masses: 1-indexed EDU-start positions from
    masses, including the trivial first one. Used to render reference-
    annotated excerpts as worked examples in a few-shot prompt."""
    return [1] + sorted(b + 1 for b in masses_to_boundaries(masses))


def segment_document(
    tokens: list[str],
    ref_masses: list[int],
    doc_id: str,
    output_dir: Path,
    model: str = DEFAULT_MODEL,
    client: Anthropic | None = None,
    prompt_builder=build_prompt,
) -> list[int]:
    """Prompt the model to segment `tokens`, caching and persisting the raw
    response under output_dir/{doc_id}.txt (one file per document; reused on
    a later call instead of re-querying). Parses the response into masses and
    verifies they cover the same number of tokens as ref_masses. Raises
    ValueError on any parse or alignment failure -- callers must catch this,
    set the document aside, and report it, never compute a metric on it.

    A cached file that turns out to be empty or otherwise unusable (e.g. a
    response truncated mid-JSON) is not treated as a valid cache hit: it is
    retried once with a fresh call, which overwrites it.

    prompt_builder defaults to the zero-shot build_prompt; pass e.g.
    functools.partial(build_fewshot_prompt, examples=...) for a few-shot
    variant. Use a separate output_dir per prompt variant so caches don't mix.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / f"{doc_id}.txt"

    if raw_path.exists():
        cached_output = raw_path.read_text(encoding="utf-8")
        try:
            return _parse_and_align(cached_output, ref_masses, tokens)
        except ValueError:
            pass  # cached response is unusable; fall through to a fresh call

    prompt = prompt_builder(tokens)
    raw_output = call_model(prompt, model=model, client=client)
    raw_path.write_text(raw_output, encoding="utf-8")
    return _parse_and_align(raw_output, ref_masses, tokens)


def _parse_and_align(raw_output: str, ref_masses: list[int], tokens: list[str]) -> list[int]:
    indices = parse_boundary_indices(raw_output)
    hyp_masses = indices_to_masses(indices, len(tokens))
    assert_comparable(ref_masses, hyp_masses)
    return hyp_masses

import json

import pytest

from llm_segmenter import (
    build_fewshot_prompt,
    build_prompt,
    indices_to_masses,
    masses_to_indices,
    parse_boundary_indices,
    segment_document,
)


class _TextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Usage:
    """Stands in for anthropic.types.Usage: enough of the real pydantic
    model's interface (model_dump) for call_model's usage-sidecar logging
    to exercise against, with fixed token counts (not asserted on by any
    test here -- only that a sidecar gets written at all)."""

    def __init__(self):
        self.input_tokens = 100
        self.output_tokens = 20

    def model_dump(self, mode="python"):
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}


class _Response:
    def __init__(self, text):
        self.content = [_TextBlock(text)]
        self.usage = _Usage()


class StubClient:
    """Stands in for anthropic.Anthropic: records calls, returns canned text."""

    def __init__(self, reply_text):
        self.reply_text = reply_text
        self.call_count = 0
        self.messages = self

    def create(self, **kwargs):
        self.call_count += 1
        self.last_kwargs = kwargs
        return _Response(self.reply_text)


def test_build_prompt_numbers_tokens_from_one():
    prompt = build_prompt(["Hello", "world", "."])
    assert "1\tHello" in prompt
    assert "2\tworld" in prompt
    assert "3\t." in prompt


def test_build_fewshot_prompt_includes_examples_and_target():
    examples = [(["Foo", "bar", "."], [1, 3]), (["Baz", "qux"], [1])]
    prompt = build_fewshot_prompt(["Hello", "world", "."], examples)

    assert "Example 1:" in prompt
    assert "1\tFoo" in prompt
    assert "3\t." in prompt
    assert "Correct EDU-start positions: [1, 3]" in prompt
    assert "Example 2:" in prompt
    assert "1\tBaz" in prompt
    assert "Correct EDU-start positions: [1]" in prompt
    # the target document itself still appears, same as zero-shot
    assert "1\tHello" in prompt
    assert "2\tworld" in prompt


def test_build_fewshot_prompt_with_no_examples_still_has_target():
    prompt = build_fewshot_prompt(["Hello"], [])
    assert "1\tHello" in prompt


def test_parse_boundary_indices_plain_json():
    assert parse_boundary_indices("[1, 4, 9, 15]") == [1, 4, 9, 15]


def test_parse_boundary_indices_amid_prose():
    raw = "Sure, here are the boundaries:\n[1, 4, 9]\nHope that helps!"
    assert parse_boundary_indices(raw) == [1, 4, 9]


def test_parse_boundary_indices_empty_array():
    assert parse_boundary_indices("[]") == []


def test_parse_boundary_indices_no_array_raises():
    with pytest.raises(ValueError, match="no JSON array"):
        parse_boundary_indices("I don't know how to segment this.")


def test_parse_boundary_indices_tolerates_quoted_element():
    # observed in practice: the model quoted the first element as a string
    assert parse_boundary_indices('["1", 2, 36, 40]') == [1, 2, 36, 40]


def test_parse_boundary_indices_wrapped_in_tags_multiline():
    raw = "<answer>\n[1, 4,\n9]\n</answer>"
    assert parse_boundary_indices(raw) == [1, 4, 9]


def test_parse_boundary_indices_rejects_float():
    with pytest.raises(ValueError, match="non-integer"):
        parse_boundary_indices("[1, 4.5, 9]")


def test_parse_boundary_indices_rejects_bool():
    with pytest.raises(ValueError, match="non-integer"):
        parse_boundary_indices("[1, true, 9]")


def test_parse_boundary_indices_rejects_non_numeric_string():
    with pytest.raises(ValueError, match="non-integer"):
        parse_boundary_indices('[1, "four", 9]')


def test_indices_to_masses_matches_docstring_example():
    # 10 tokens, boundaries after token 3 and token 7 -> starts at 1, 4, 8
    assert indices_to_masses([1, 4, 8], 10) == [3, 4, 3]


def test_indices_to_masses_inserts_missing_first_token():
    # the model need not (and is asked not to have to) restate the trivial
    # boundary at token 1
    assert indices_to_masses([4, 8], 10) == [3, 4, 3]


def test_indices_to_masses_out_of_range_raises():
    with pytest.raises(ValueError, match="out of range"):
        indices_to_masses([1, 11], 10)

    with pytest.raises(ValueError, match="out of range"):
        indices_to_masses([1, 0], 10)


def test_indices_to_masses_sum_matches_n_tokens():
    masses = indices_to_masses([1, 5, 5, 8], 10)  # duplicate index tolerated
    assert sum(masses) == 10


def test_masses_to_indices_matches_docstring_example():
    assert masses_to_indices([3, 4, 3]) == [1, 4, 8]


def test_masses_to_indices_round_trips_with_indices_to_masses():
    masses = [3, 4, 3]
    n_tokens = sum(masses)
    indices = masses_to_indices(masses)
    assert indices_to_masses(indices, n_tokens) == masses


def test_segment_document_uses_custom_prompt_builder(tmp_path):
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 8]")
    seen_prompts = []

    def recording_builder(toks):
        seen_prompts.append(toks)
        return "CUSTOM PROMPT MARKER"

    segment_document(tokens, ref_masses, "doc1", tmp_path, client=client, prompt_builder=recording_builder)

    assert seen_prompts == [tokens]
    assert client.last_kwargs["messages"][0]["content"] == "CUSTOM PROMPT MARKER"


def test_segment_document_persists_and_parses(tmp_path):
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 8]")

    hyp_masses = segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    assert hyp_masses == [3, 4, 3]
    assert client.call_count == 1
    assert (tmp_path / "doc1.txt").read_text() == "[1, 4, 8]"


def test_segment_document_uses_cache_on_second_call(tmp_path):
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 8]")

    segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)
    segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    assert client.call_count == 1  # second call reused the cached file


def test_segment_document_writes_usage_sidecar_on_fresh_call(tmp_path):
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 8]")

    segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    usage = json.loads((tmp_path / "doc1.usage.json").read_text())
    assert usage == {"input_tokens": 100, "output_tokens": 20}


def test_segment_document_does_not_rewrite_usage_sidecar_on_cache_hit(tmp_path):
    # A cache hit never calls the model, so it has no new response.usage
    # to log -- an old sidecar (or none at all, for cache files written
    # before usage logging existed) is left exactly as it is.
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 8]")

    segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)
    sidecar_path = tmp_path / "doc1.usage.json"
    original_usage_text = sidecar_path.read_text()

    client.reply_text = "[1, 5, 8]"  # would prove a fresh call happened, if one did
    segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    assert client.call_count == 1
    assert sidecar_path.read_text() == original_usage_text


def test_segment_document_retries_on_empty_cached_file(tmp_path):
    # an empty cache file (e.g. left behind by a response that burned its
    # whole token budget on thinking and returned no text) must not be
    # treated as a valid cache hit
    (tmp_path / "doc1.txt").write_text("")
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 8]")

    hyp_masses = segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    assert hyp_masses == [3, 4, 3]
    assert client.call_count == 1
    assert (tmp_path / "doc1.txt").read_text() == "[1, 4, 8]"


def test_segment_document_retries_on_truncated_cached_content(tmp_path):
    # a non-empty but truncated/unparseable cache file (e.g. a response cut
    # off mid-JSON-array) must also not be treated as a valid cache hit
    (tmp_path / "doc1.txt").write_text("[1, 4, 8")  # missing closing bracket
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 8]")

    hyp_masses = segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    assert hyp_masses == [3, 4, 3]
    assert client.call_count == 1
    assert (tmp_path / "doc1.txt").read_text() == "[1, 4, 8]"


def test_segment_document_still_raises_when_retry_also_fails(tmp_path):
    (tmp_path / "doc1.txt").write_text("garbage, no array here")
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("still no array")  # the fresh call also fails to parse

    with pytest.raises(ValueError, match="no JSON array"):
        segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    assert client.call_count == 1  # exactly one fresh attempt, no retry loop
    assert (tmp_path / "doc1.txt").read_text() == "still no array"  # overwritten for diagnosis


def test_segment_document_raises_on_alignment_failure_but_still_persists_raw(tmp_path):
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 20]")  # 20 is out of range for a 10-token doc

    with pytest.raises(ValueError, match="out of range"):
        segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    # raw output must be on disk for diagnosis even though parsing failed
    assert (tmp_path / "doc1.txt").read_text() == "[1, 4, 20]"

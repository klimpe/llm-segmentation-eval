import pytest

from llm_segmenter import (
    build_prompt,
    indices_to_masses,
    parse_boundary_indices,
    segment_document,
)


class _TextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text):
        self.content = [_TextBlock(text)]


class StubClient:
    """Stands in for anthropic.Anthropic: records calls, returns canned text."""

    def __init__(self, reply_text):
        self.reply_text = reply_text
        self.call_count = 0
        self.messages = self

    def create(self, **kwargs):
        self.call_count += 1
        return _Response(self.reply_text)


def test_build_prompt_numbers_tokens_from_one():
    prompt = build_prompt(["Hello", "world", "."])
    assert "1\tHello" in prompt
    assert "2\tworld" in prompt
    assert "3\t." in prompt


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


def test_segment_document_raises_on_alignment_failure_but_still_persists_raw(tmp_path):
    tokens = ["a"] * 10
    ref_masses = [3, 4, 3]
    client = StubClient("[1, 4, 20]")  # 20 is out of range for a 10-token doc

    with pytest.raises(ValueError, match="out of range"):
        segment_document(tokens, ref_masses, "doc1", tmp_path, client=client)

    # raw output must be on disk for diagnosis even though parsing failed
    assert (tmp_path / "doc1.txt").read_text() == "[1, 4, 20]"

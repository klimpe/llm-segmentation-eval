import os

import pytest

from disrpt_reader import read_tok_document

CORPUS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "corpora", "disrpt", "eng.rst.gum", "eng.rst.gum_dev.tok"
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(CORPUS_PATH), reason="corpus data not present (gitignored, download separately)"
)


def test_first_document_token_count():
    doc_id, masses = read_tok_document(CORPUS_PATH)
    assert doc_id == "GUM_academic_exposure"
    # eyeballed against the source file: 964 token lines, 110 lines with
    # BeginSeg=Yes (including the first token)
    assert sum(masses) == 964
    assert len(masses) == 110


def test_named_document_matches_first():
    by_default = read_tok_document(CORPUS_PATH)
    by_name = read_tok_document(CORPUS_PATH, doc_id="GUM_academic_exposure")
    assert by_default == by_name


def test_second_document():
    doc_id, masses = read_tok_document(CORPUS_PATH, doc_id="GUM_academic_librarians")
    assert doc_id == "GUM_academic_librarians"
    assert sum(masses) > 0


def test_unknown_document_raises():
    with pytest.raises(ValueError, match="not found"):
        read_tok_document(CORPUS_PATH, doc_id="does_not_exist")

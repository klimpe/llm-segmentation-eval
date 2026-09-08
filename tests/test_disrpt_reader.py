import os

import pytest

from disrpt_reader import iter_tok_documents, read_tok_document

CORPUS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "corpora", "disrpt", "eng.rst.gum", "eng.rst.gum_dev.tok"
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(CORPUS_PATH), reason="corpus data not present (gitignored, download separately)"
)


def test_first_document_token_count():
    doc_id, tokens, masses = read_tok_document(CORPUS_PATH)
    assert doc_id == "GUM_academic_exposure"
    # eyeballed against the source file: 964 token lines, 110 lines with
    # BeginSeg=Yes (including the first token)
    assert len(tokens) == 964
    assert sum(masses) == 964
    assert len(masses) == 110
    assert tokens[0] == "Introduction"
    assert tokens[1] == "Research"


def test_named_document_matches_first():
    by_default = read_tok_document(CORPUS_PATH)
    by_name = read_tok_document(CORPUS_PATH, doc_id="GUM_academic_exposure")
    assert by_default == by_name


def test_second_document():
    doc_id, tokens, masses = read_tok_document(CORPUS_PATH, doc_id="GUM_academic_librarians")
    assert doc_id == "GUM_academic_librarians"
    assert len(tokens) == sum(masses) > 0


def test_unknown_document_raises():
    with pytest.raises(ValueError, match="not found"):
        read_tok_document(CORPUS_PATH, doc_id="does_not_exist")


def test_multiword_token_rows_are_skipped_not_counted():
    # GUM_conversation_grounded opens with a CoNLL-U multiword-token range
    # row ("1-2  What'd"), which is a grouping header, not a token: it must
    # not be counted, and the real BeginSeg=Yes annotation lives on the
    # sub-token row that follows.
    doc_id, tokens, masses = read_tok_document(CORPUS_PATH, doc_id="GUM_conversation_grounded")
    assert tokens[0] == "What"
    assert tokens[1] == "'d"
    assert masses[0] >= 1  # first segment starts at token 0, not the range row


def test_iter_tok_documents_covers_whole_corpus():
    docs = list(iter_tok_documents(CORPUS_PATH))
    assert len(docs) == 24
    # published DISRPT stats for eng.rst.gum dev: 2790 EDUs (segments).
    # token count is NOT compared here: the published "dev_toks" figure
    # counts CoNLL-U multiword-token range rows as tokens (a quirk of how
    # that table was tallied); ours correctly excludes them (verified by
    # the exact segment-count match, and by hand above for one document).
    total_segs = sum(len(masses) for _, _, masses in docs)
    assert total_segs == 2790
    for doc_id, tokens, masses in docs:
        assert sum(masses) == len(tokens), doc_id

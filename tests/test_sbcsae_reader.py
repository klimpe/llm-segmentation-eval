"""Phase 2, stage 4 follow-up: non-participant (">"-prefixed) speaker
exclusion in the reader (sbcsae_reader.read_trn_document).
"""
from sbcsae_reader import read_trn_document


def _write(tmp_path, doc_id, lines):
    path = tmp_path / f"{doc_id}.trn"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_non_participant_speaker_line_excluded(tmp_path):
    path = _write(
        tmp_path,
        "SBCTEST",
        [
            "1.00\t2.00\tJOE:\tHello there.",
            "2.00\t3.00\t>ENV:\t((DOOR_SLAMS))",
            "3.00\t4.00\tJOE:\tWhat was that.",
        ],
    )
    doc_id, units, n_raw, nul_rows, excluded_rows = read_trn_document(path)
    assert [u.speaker for u in units] == ["JOE", "JOE"]
    assert [u.text for u in units] == ["Hello there.", "What was that."]
    assert len(excluded_rows) == 1
    assert excluded_rows[0]["reason"] == "non_participant_speaker"
    assert ">ENV" in excluded_rows[0]["content"]


def test_non_participant_speaker_excluded_even_with_real_words(tmp_path):
    # Confirmed this session: a few >ENV/>MAC lines do tokenise to real
    # words (SBC008/SBC013). Excluded regardless -- the source, not the
    # text, is what disqualifies it.
    path = _write(
        tmp_path,
        "SBCTEST2",
        [
            "1.00\t2.00\tJOE:\tHello.",
            "2.00\t3.00\t>ENV:\tto= expose himself to a person,",
        ],
    )
    doc_id, units, n_raw, nul_rows, excluded_rows = read_trn_document(path)
    assert len(units) == 1
    assert [r["reason"] for r in excluded_rows] == ["non_participant_speaker"]


def test_non_participant_speaker_continuation_line_also_excluded(tmp_path):
    # A blank-speaker continuation line inherits the ">"-prefixed current
    # speaker and must be excluded too, not just the line with the label.
    path = _write(
        tmp_path,
        "SBCTEST3",
        [
            "1.00\t2.00\t>MAC:\tfirst part",
            "2.00\t3.00\t\tsecond part, no speaker field",
            "3.00\t4.00\tJOE:\tReal speech.",
        ],
    )
    doc_id, units, n_raw, nul_rows, excluded_rows = read_trn_document(path)
    assert len(units) == 1
    assert units[0].speaker == "JOE"
    assert len(excluded_rows) == 2
    assert all(r["reason"] == "non_participant_speaker" for r in excluded_rows)

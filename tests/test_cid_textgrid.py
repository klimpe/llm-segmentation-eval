"""cid_textgrid on synthetic input only -- no CID material in this file.

The reader was also checked against Praat itself on the 191 TextGrids the
stage-1 steps use (tier names, interval counts, summed times, summed label
lengths; 0 mismatches) -- reports/phase3_data.md §1.
"""
import pytest

from cid_textgrid import EncodingUndetermined, TextGridFormatError, detect_encoding, parse, read_textgrid

LONG = '''File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0
xmax = 2.5
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "token"
        xmin = 0
        xmax = 2.5
        intervals: size = 3
        intervals [1]:
            xmin = 0
            xmax = 1
            text = "a"
        intervals [2]:
            xmin = 1
            xmax = 1.5
            text = "say ""b"""
        intervals [3]:
            xmin = 1.5
            xmax = 2.5
            text = "#"
    item [2]:
        class = "TextTier"
        name = "pts"
        xmin = 0
        xmax = 2.5
        points: size = 1
        points [1]:
            number = 1.25
            mark = "p"
'''

SHORT = '''File type = "ooTextFile"
Object class = "TextGrid"

0
2.5
<exists>
1
"IntervalTier"
"token"
0
2.5
2
0
1e0
"a"
1
2.5
""
'''


def test_long_format():
    tg = parse(LONG)
    tok = tg.tier("token")
    assert [(i.xmin, i.xmax, i.text) for i in tok.items] == [(0, 1, "a"), (1, 1.5, 'say "b"'), (1.5, 2.5, "#")]
    pts = tg.tier("pts")
    assert pts.cls == "TextTier" and [(p.time, p.mark) for p in pts.items] == [(1.25, "p")]


def test_short_format():
    tg = parse(SHORT)
    assert [(i.xmin, i.xmax, i.text) for i in tg.tier("token").items] == [(0, 1, "a"), (1, 2.5, "")]


def test_truncated_file_raises():
    with pytest.raises(TextGridFormatError):
        parse(SHORT.rsplit("\n", 3)[0])


def test_encodings():
    assert detect_encoding(b"abc") == "ascii"
    assert detect_encoding("é".encode("utf-8")) == "utf-8"
    assert detect_encoding(b"\xfe\xff\x00a") == "utf-16-be-bom"
    assert detect_encoding(b"\xef\xbb\xbfa") == "utf-8-sig"
    with pytest.raises(EncodingUndetermined):
        detect_encoding("é".encode("latin-1"))     # never guessed as latin-1
    with pytest.raises(EncodingUndetermined):
        detect_encoding("a".encode("utf-16-be"))   # no BOM: not guessed


def test_bom_with_undecodable_content_raises(tmp_path):
    p = tmp_path / "x.TextGrid"
    p.write_bytes(b"\xef\xbb\xbf" + "é".encode("latin-1"))
    with pytest.raises(EncodingUndetermined):
        read_textgrid(p)


def test_utf16_and_crlf_inside_label(tmp_path):
    p = tmp_path / "x.TextGrid"
    p.write_bytes(LONG.replace("\n", "\r\n").replace('"a"', '"\r\nM"').encode("utf-16"))
    tg = read_textgrid(p)
    assert tg.encoding in ("utf-16-be-bom", "utf-16-le-bom")
    assert tg.tier("token").items[0].text == "\nM"   # as Praat reads it


def test_old_short_format_header():
    # Praat's older short-format header, used by e.g. the archive's phonemes/.
    tg = parse(SHORT.replace('"ooTextFile"', '"ooTextFile short"', 1))
    assert len(tg.tier("token").items) == 2

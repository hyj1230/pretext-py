from pretext_py.intl_segmenter_py import graphemeSegments, String
from ._unicode_testdata import TESTDATA_GRAPHEME


print('Unicode® official test suite')


def segment(py_str):
    for i in graphemeSegments(String(py_str)):
        yield str(i['segment'])

for _input, expected in TESTDATA_GRAPHEME:
    assert list(segment(_input)) == expected

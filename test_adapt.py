from pretext_py import layout_test
from pretext_py.test_intl_segmenter import unicode
from pretext_py.test_intl_segmenter import grapheme
from pretext_py.test_intl_segmenter import word

layout_test.test_measurement_invariants()
layout_test.test_use_default_segmenter()
layout_test.test_prepare_invariants()
layout_test.test_rich_inline_invariants()
layout_test.test_layout_invariants()

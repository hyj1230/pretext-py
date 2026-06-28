from ._word_testdata import TEST_WORD
from pretext_py.intl_segmenter_py.word import WC_ALetter, WC_Numeric, word_category, unicode_word_bounds, ascii_word_bounds, is_word_like
import random


def test_words():

    # 额外测试用例
    EXTRA_TESTS = [
        (
            "🇦🇫🇦🇽🇦🇱🇩🇿🇦🇸🇦🇩🇦🇴",
            ["🇦🇫", "🇦🇽", "🇦🇱", "🇩🇿", "🇦🇸", "🇦🇩", "🇦🇴"],
        ),
        ("🇦🇫🇦🇽🇦🇱🇩🇿🇦🇸🇦🇩🇦", ["🇦🇫", "🇦🇽", "🇦🇱", "🇩🇿", "🇦🇸", "🇦🇩", "🇦"]),
        (
            "🇦a🇫🇦🇽a🇦🇱🇩🇿🇦🇸🇦🇩🇦",
            ["🇦", "a", "🇫🇦", "🇽", "a", "🇦🇱", "🇩🇿", "🇦🇸", "🇦🇩", "🇦"],
        ),
        (
            "\U0001f468\u200d\U0001f468\u200d\U0001f466",
            ["\U0001f468\u200d\U0001f468\u200d\U0001f466"],
        ),
        ("😌👎🏼", ["😌", "👎🏼"]),
        ("hello world", ["hello", " ", "world"]),
        ("🇨🇦🇨🇭🇿🇲🇿 hi", ["🇨🇦", "🇨🇭", "🇿🇲", "🇿", " ", "hi"]),
    ]

    for s, expected_words in TEST_WORD + EXTRA_TESTS:
        # 正向边界测试
        forward_bounds = list(map(lambda m:m[1], unicode_word_bounds(s)))
        assert (
            forward_bounds == expected_words
        ), f"Forward word boundaries test for ({s!r}, {expected_words!r}) failed. Got {forward_bounds!r}"

        # 正向偏移量测试
        forward_indices = [offset for offset, _ in unicode_word_bounds(s)]
        # 计算期望的偏移量序列
        expected_offsets = []
        current = 0
        for w in expected_words:
            expected_offsets.append(current)
            current += len(w)
        assert (
            forward_indices == expected_offsets
        ), f"Forward word indices test for ({s!r}, {expected_words!r}) failed. Got {forward_indices!r}, expected {expected_offsets!r}"

    print("All word boundary tests passed.")


test_words()



def test_syriac_abbr_mark():
    """U+070F 的 Word_Break 类别应为 ALetter"""
    cat = word_category(ord('\u070f'))
    assert cat == WC_ALetter, f"Expected ALetter, got {cat}"

def test_end_of_ayah_cat():
    """U+06DD 的 Word_Break 类别应为 Numeric"""
    cat = word_category(ord('\u06dd'))
    assert cat == WC_Numeric, f"Expected Numeric, got {cat}"

def test_ascii_word_bound_indices_various_cases():
    """ASCII 边界分割的固定案例"""
    s = "Hello, world!"
    words = list(unicode_word_bounds(s))
    expected = [
        (0, "Hello"),
        (5, ","),
        (6, " "),
        (7, "world"),
        (12, "!"),
    ]
    assert words == expected, f"Got {words}"

def test_ascii_word_indices_various_cases():
    """ASCII 单词提取的固定案例"""
    s = "Hello, world! can't e.g. var1 123,456 foo_bar example.com 127.0.0.1:9090"
    d = map(lambda k:k[1], unicode_word_bounds(s))
    words = list(filter(is_word_like, d))
    expected = [
        "Hello", "world", "can't", "e.g", "var1", "123,456",
        "foo_bar", "example.com", "127.0.0.1", "9090",
    ]
    assert words == expected, f"Got {words}"

# ----------------------------------------------------------------------
# 模拟 proptest 的随机测试
# ----------------------------------------------------------------------

def random_ascii_string(min_len=0, max_len=99) -> str:
    """生成长度在 min_len..=max_len 的随机 ASCII 字符串（字符范围 U+0000..U+007F）"""
    length = random.randint(min_len, max_len)
    return ''.join(chr(random.randint(0, 127)) for _ in range(length))


def proptest_ascii_matches_unicode_word_indices(num_cases=10000):
    """快速路径与通用路径在任意 ASCII 输入上的正向结果必须一致"""
    for _ in range(num_cases):
        s = random_ascii_string(0, 99)
        fast = list(unicode_word_bounds(s))
        uni = list(ascii_word_bounds(s))
        assert fast == uni, f"Mismatch for {s!r}:\nfast: {fast}\nuni: {uni}"


print("Running fixed word tests...")
test_syriac_abbr_mark()
test_end_of_ayah_cat()
test_ascii_word_bound_indices_various_cases()
test_ascii_word_indices_various_cases()
print("Running property tests (this may take a moment)...")
proptest_ascii_matches_unicode_word_indices(10000)
print("All property tests passed.")
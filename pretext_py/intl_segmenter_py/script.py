from .core import findUnicodeRangeIndex
from ._script_data import arabic_ranges


# Check if the given code point is included in Unicode \\p{Script=Arabic} property
def isArabic(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, arabic_ranges) >= 0

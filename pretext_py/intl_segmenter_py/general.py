from .core import findUnicodeRangeIndex
from ._general_data import letter_ranges, alphabetic_ranges, numeric_ranges, \
                           mark_ranges, punctuation_ranges, symbol_ranges, \
                           co_ranges, nd_ranges, nl_ranges


# Check if the given code point is included in Unicode \\p{L} general property
def isLetter(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, letter_ranges) >= 0


# Check if the given code point is included in Unicode \\p{Alphabetic} dervied property
def isAlphabetic(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, alphabetic_ranges) >= 0


# Check if the given code point is included in Unicode \\p{N} general property
def isNumeric(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, numeric_ranges) >= 0


# Check if the given code point is included in Unicode \\p{M} general property
def isMark(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, mark_ranges) >= 0


def isAlphanumeric(cp: int) -> bool:
    return isAlphabetic(cp) or isNumeric(cp)


# Check if the given code point is included in Unicode \\p{P} general property
def isPunctuation(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, punctuation_ranges) >= 0


# Check if the given code point is included in Unicode \\p{S} general property
def isSymbol(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, symbol_ranges) >= 0


# Check if the given code point is included in Unicode \\p{Co} general property
def isCo(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, co_ranges) >= 0


# Check if the given code point is included in Unicode \\p{Nd} general property
def isNd(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, nd_ranges) >= 0


# Check if the given code point is included in Unicode \\p{Nl} general property
def isNl(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, nl_ranges) >= 0

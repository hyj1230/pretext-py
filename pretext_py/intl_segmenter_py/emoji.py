from .core import findUnicodeRangeIndex
from ._emoji_data import emoji_presentation_ranges, extended_pictographic_ranges


# An alias to {@link isExtendedPictographic}
# @deprecated in favor of {@link isExtendedPictographic}, will be removed in v1.
def isEmoji(cp: int) -> bool:
    return isExtendedPictographic(cp)


# Check if the given code point is included in Unicode \\p{Emoji_Presentation} script property
def isEmojiPresentation(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, emoji_presentation_ranges) >= 0


# Check if the given code point is included in Unicode \\p{Extended_Pictographic} script property
def isExtendedPictographic(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, extended_pictographic_ranges) >= 0

# Copyright 2012-2018 The Rust Project Developers. See the COPYRIGHT
# file at the top-level directory of this distribution and at
# http://rust-lang.org/COPYRIGHT.
#
# Licensed under the MIT license
# <LICENSE-MIT or http://opensource.org/licenses/MIT>.
#
# Modified original Rust library [source code]
# (https://github.com/unicode-rs/unicode-segmentation/blob/1f88570/src/grapheme.rs)
#
# to create JavaScript library [unicode-segmenter]
# (https://github.com/cometkim/unicode-segmenter)
# 
# This is a Python rewrite of the original JavaScript source code.
# Modifications and Python translation copyright (C) 2026 hyj1230


from .core import findUnicodeRangeIndex
from ._grapheme_data import grapheme_ranges  # , GraphemeCategory
from ._incb_data import consonant_ranges
from .compat_util import String


BMP_MAX = 0xFFFF


# Unicode segmentation by extended grapheme rules.
# 这完全兼容于 {@link Intl.Segmenter.segment} API
# @see https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter/segment
def graphemeSegments(_input: String):
    cp = _input.codePointAt(0)

    # do nothing on empty string
    if cp is None:
        return

    cursor = 1 if cp <= BMP_MAX else 2  # 当前光标位置
    length = _input.length  # 输入字符串的总长度
    
    catBefore = cat(cp)  # Category of codepoint immediately preceding cursor
    catAfter = 0  # Category of codepoint immediately preceding cursor.
    _catBegin = catBefore  # Beginning category of a segment
    
    # The number of RI codepoints preceding `cursor`.
    riCount = 0

    # Tracks if Extended_Pictographic was seen in the current Extend* sequence for GB11
    extPic = catBefore == 4

    # Emoji state for GB11: tracks if we've seen Extended_Pictographic followed by Extend* ZWJ
    # Only relevant when catBefore == ZWJ and extPic (catAfter == Extended_Pictographic)
    emoji = False

    # InCB=Consonant - segment started with Indic consonant
    consonant = False

    # InCB=Linker - seen a linker after consonant
    linker = False

    index = 0
    _hd = cp # Memoize the beginning code point of the segment.
    
    while cursor < length:
        cp: int = _input.codePointAt(cursor)
        catAfter = cat(cp)
    
        boundary = True
    
        # GB3: CR × LF
        if catBefore == 1:
            boundary = catAfter != 6
        
        # GB4: (Control | CR | LF) ÷
        elif catBefore == 2 or catBefore == 6:
            boundary = True
        
        # GB5: ÷ (Control | CR | LF)
        elif catAfter == 1 or catAfter == 2 or catAfter == 6:
            boundary = True
        
        # GB9, GB9a: × (Extend | ZWJ | SpacingMark) - most common no-break case
        elif catAfter == 3 or catAfter == 14 or catAfter == 11:
            boundary = False
        
        # GB9b: Prepend ×
        elif catBefore == 9:
            boundary = False
        
        # GB11: ExtPic Extend* ZWJ × ExtPic
        elif catBefore == 14 and extPic:
            boundary = not emoji
        
        # GB12, GB13: RI × RI (odd count means no break)
        elif catBefore == 10 and catAfter == 10:
            # riCount is count BEFORE current RI, so odd means this is 2nd, 4th, etc.
            boundary = riCount % 2 == 1
            riCount += 1
        
        # GB6: L × (L | V | LV | LVT)
        elif catBefore == 5:
            boundary = not (catAfter == 5 or catAfter == 13 or catAfter == 7 or catAfter == 8)
        
        # GB7: (LV | V) × (V | T)
        elif (catBefore == 7 or catBefore == 13) and (catAfter == 13 or catAfter == 12):
            boundary = False
        
        # GB8: (LVT | T) × T
        elif (catBefore == 8 or catBefore == 12) and catAfter == 12:
            boundary = False
        
        # GB9c: InCB=Consonant InCB=Extend* InCB=Linker InCB=Extend* × InCB=Consonant
        elif catAfter == 0 and consonant and linker and isIndicConjunctConsonant(cp):
            boundary = False
        
        # else GB999: ÷ Any
    
        if boundary:
            yield {
                'segment': _input.slice(index, cursor),
                'index': index,
                'input': _input,
                '_hd': _hd,
                '_catBegin': _catBegin,
                '_catEnd': catBefore,
            }
    
            # Reset segment state
            extPic = catAfter == 4
            emoji = False
            consonant = False
            linker = False
            riCount = 0
            index = cursor
            _catBegin = catAfter
            _hd = cp
        
        # Update state for continuing segment
        else:
            # emoji state for GB11: ExtPic Extend* ZWJ × ExtPic
            if catAfter == 14 and extPic:
                emoji = True
          
            # InCB state for GB9c
            elif cp >= 2325:
                if not consonant and catBefore == 0:
                    consonant = isIndicConjunctConsonant(_hd)
                
                if consonant and (catAfter == 3 or catAfter == 14):
                  # ZWNJ(U+200C) has InCB=None, it should break the GB9c pattern
                    linker = cp != 0x200C and (
                        linker
                        or cp == 0x094D   # Devanagari Sign Virama
                        or cp == 0x09CD   # Bengali Sign Virama
                        or cp == 0x0A4D   # Gurmukhi Sign Virama
                        or cp == 0x0ACD   # Gujarati Sign Virama
                        or cp == 0x0B4D   # Oriya Sign Virama
                        or cp == 0x0C4D   # Telugu Sign Virama
                        or cp == 0x0D4D   # Malayalam Sign Virama
                        or cp == 0x1039   # Myanmar Sign Virama
                        or cp == 0x17D2   # Khmer Sign Coeng
                        or cp == 0x1A60   # Tai Tham Sign Sakot
                        or cp == 0x1B44   # Balinese Adeg Adeg
                        or cp == 0x1BAB   # Sundanese Sign Virama
                        or cp == 0xA9C0   # Javanese Pangkon
                        or cp == 0xAAF6   # Meetei Mayek Virama
                        or cp == 0x10A3F  # Kharoshthi Virama
                        or cp == 0x11133  # Chakma Virama
                        or cp == 0x113D0  # Tulu-Tigalari Conjoiner
                        or cp == 0x1193E  # Dives Akuru Virama
                        or cp == 0x11A47  # Zanabazar Square Subjoiner
                        or cp == 0x11A99  # Soyombo Subjoiner
                        or cp == 0x11F42  # Kawi Conjoiner
                    )
                else:
                    linker = False
    
        cursor += 1 if cp <= BMP_MAX else 2
        catBefore = catAfter

    if index < length:
        yield {
            'segment': _input.slice(index),
            'index': index,
            'input': _input,
            '_hd': _hd,
            '_catBegin': _catBegin,
            '_catEnd': catBefore,
        }


# Count number of extended grapheme clusters in given text.
# 
# NOTE:
#
# This function is a small wrapper around {@link graphemeSegments}.
#
# If you call it more than once at a time, consider memoization
# or use {@link graphemeSegments} or {@link splitGraphemes} once instead
def countGraphemes(text: String):
    count = 0
    for _ in graphemeSegments(text): count += 1
    return count



# Split given text into extended grapheme clusters.
def splitGraphemes(text: String):
  for s in graphemeSegments(text): yield s['segment']


# Segmented 4-bit packed lookup tables for BMP code points.
# 
# Memory and code size optimization: Skip regions that can be easily inlined
# - 0x3000-0x9FFF (CJK): 28,672 codepoints, only 12 non-Any ranges
# - 0xAC00-0xD7A3 (Hangul syllables): 11,172 codepoints, LV or LVT computed at runtime
# - 0xD7A4-0xD7FF (Hangul Jamo Extended-B): 92 codepoints, only 2 non-Any ranges
# - 0xE000-0xFDFF (Private Use): 7,680 codepoints, only 1 non-Any range
# - 0xFE00-0xFFFF (Specials): 512 codepoints -> very rare and small, binary search fallback
# 
# Hangul syllables note:
# - LV syllables: single codepoints at 0xAC00 + n*28
# - LVT syllables: 27 consecutive codepoints after each LV
# 
# Indexed category segments (4-bit packed, 2 categories per byte):
# - SEG0: 0x0080-0x2FFF (12,160 codepoints -> 6,080 bytes)
# - SEG1: 0xA000-0xABFF (3,072 codepoints -> 1,536 bytes)
#
# Total index size: 7,616 bytes (~7.4KB)
SEG0_MIN, SEG0_MAX = 0x0080, 0x2FFF
SEG1_MIN, SEG1_MAX = 0xA000, 0xABFF
SEG0 = bytearray(6080)
SEG1 = bytearray(1536)

def _build_table() -> int:
    cursor: int = 0
    while True:
        start, end, _cat = grapheme_ranges[cursor]
        if start > SEG1_MAX: break
        cursor += 1
    
        # Skip inlined ranges
        if end < SEG0_MIN or (start > SEG0_MAX and end < SEG1_MIN): continue
    
        for cp in range(start, end+1):
            seg, idx = None, 0
    
            if cp <= SEG0_MAX:
                seg = SEG0
                idx = (cp - SEG0_MIN) >> 1
            else:
                seg = SEG1
                idx = (cp - SEG1_MIN) >> 1
    
            seg[idx] = (seg[idx] & 0x0F) | (_cat << 4) if cp & 1 else (seg[idx] & 0xF0) | _cat

    return cursor

SEG_CURSOR: int = _build_table()



# `Grapheme_Cluster_Break` property value of a given codepoint
# @see https://www.unicode.org/reports/tr29/tr29-43.html#Default_Grapheme_Cluster_Table
def cat(cp: int) -> int:
    # ASCII 快速路径
    if cp < SEG0_MIN:
        if cp >= 32: return 0
        if cp == 10: return 6
        if cp == 13: return 1
        return 2
    
    # Index Segment 0: 0x0080-0x2FFF
    if cp <= SEG0_MAX:
        byte = SEG0[(cp - SEG0_MIN) >> 1]
        return byte >> 4 if cp & 1 else byte & 0x0F

    # CJK 快速路径 : 0x3000-0x9FFF
    if cp < SEG1_MIN:
        if cp < 0x3030: return 3 if cp >= 0x302A else 0
        if cp < 0x309B:
            if cp == 0x3030 or cp == 0x303D: return 4
            return 3 if cp >= 0x3099 else 0
        if cp == 0x3297 or cp == 0x3299: return 4
        return 0

    # Index Segment 1: 0xA000-0xABFF
    if cp <= SEG1_MAX:
        byte = SEG1[(cp - SEG1_MIN) >> 1]
        return byte >> 4 if cp & 1 else byte & 0x0F

    # 韩文音节路径 : 0xAC00-0xD7A3
    if cp <= 0xD7A3:
        return 7 if (cp - 0xAC00) % 28 == 0 else 8  # LV : LVT

    # 韩文辅音扩展-B 路径 : 0xD7A4-0xD7FF
    if cp <= 0xD7FF:
        if cp <= 0xD7C6: return 13 if cp >= 0xD7B0 else 0  # V
        return 12 if cp >= 0xD7CB else 0  # T

    # 私有用户区快速路径: 0xE000-0xFDFF
    if cp < 0xFE00:
        return 3 if cp == 0xFB1E else 0
    
    # 特殊字符 (0xFE00-0xFFFF) and Non-BMP
    idx = findUnicodeRangeIndex(cp, grapheme_ranges, SEG_CURSOR)
    return 0 if idx < 0 else grapheme_ranges[idx][2]


def isIndicConjunctConsonant(cp: int) -> bool:
    return findUnicodeRangeIndex(cp, consonant_ranges) >= 0


# Copyright 2012-2014 The Rust Project Developers. See the COPYRIGHT
# file at the top-level directory of this distribution and at
# http://rust-lang.org/COPYRIGHT.
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
# 
# This is a Python rewrite of the original Rust source code.
# Modifications and Python translation copyright (C) 2026 hyj1230

from .emoji import isExtendedPictographic
from .general import isNd, isLetter, isNl
from ._word_data import word_category


# WordCat
WC_ALetter = 0
WC_Any = 1
WC_CR = 2
WC_Double_Quote = 3
WC_Extend = 4
WC_ExtendNumLet = 5
WC_Format = 6
WC_Hebrew_Letter = 7
WC_Katakana = 8
WC_LF = 9
WC_MidLetter = 10
WC_MidNum = 11
WC_MidNumLet = 12
WC_Newline = 13
WC_Numeric = 14
WC_Regional_Indicator = 15
WC_Single_Quote = 16
WC_WSegSpace = 17
WC_ZWJ = 18

# UWordBoundsState
State_Start = 0
State_Letter = 1
State_HLetter = 2
State_Numeric = 3
State_Katakana = 4
State_ExtendNumLet = 5
State_Regional = 6   # stores a RegionalState inside
State_FormatExtend = 7  # stores a FormatExtendType inside
State_Zwj = 8
State_Emoji = 9
State_WSegSpace = 10

# FormatExtendType
ExtendType_AcceptAny = 0
ExtendType_AcceptNone = 1
ExtendType_RequireLetter = 2
ExtendType_RequireHLetter = 3
ExtendType_AcceptQLetter = 4
ExtendType_RequireNumeric = 5

# RegionalState
Regional_Half = 0
Regional_Full = 1
Regional_Unknown = 2

# ----------------------------------------------------------------------
# UWordBounds – forward/backward iterator over word boundary segments
# ----------------------------------------------------------------------

def unicode_word_bounds(s: str):
    offset = 0
    cached_cat = None          # 相当于 self.cat
    n = len(s)

    while offset < n:
        # 每轮开始，重置状态变量
        state = State_Start
        cat = WC_Any
        savecat = WC_Any
        saveidx = 0
        skipped_format_extend = False
        take_curr = True
        take_cat = True
        regional = None         # 原 self._regional
        fmt_ext_type = None     # 原 self._fmt_ext_type

        idx = offset              # 当前指针，相当于原 idx

        for curr in range(offset, n):
            ch = ord(s[curr])
            idx = curr
            prev_zwj = (cat == WC_ZWJ)

            # 使用缓存的类别（对应原 self.cat）
            if cached_cat is not None:
                cat = cached_cat
                cached_cat = None
            else:
                cat = word_category(ch)
            take_cat = True

            # WB4: 跳过 Extend / Format / ZWJ（非 Start 状态时）
            if state != State_Start:
                if cat in (WC_Extend, WC_Format, WC_ZWJ):
                    skipped_format_extend = True
                    continue

            # WB3c: ZWJ + ExtPict
            if prev_zwj and isExtendedPictographic(ch):
                state = State_Emoji
                continue

            # ----- 大状态机 -----
            if state == State_Start:
                if cat == WC_CR:
                    # WB3: CR × LF
                    if idx + 1 < n and word_category(ord(s[idx + 1])) == WC_LF:
                        idx += 1
                    break               # WB3a
                # 根据首字符分类分发
                if cat == WC_ALetter:
                    state = State_Letter
                elif cat == WC_Hebrew_Letter:
                    state = State_HLetter
                elif cat == WC_Numeric:
                    state = State_Numeric
                elif cat == WC_Katakana:
                    state = State_Katakana
                elif cat == WC_ExtendNumLet:
                    state = State_ExtendNumLet
                elif cat == WC_Regional_Indicator:
                    state = State_Regional
                    regional = Regional_Half
                elif cat in (WC_LF, WC_Newline):
                    break               # WB3a
                elif cat == WC_ZWJ:
                    state = State_Zwj
                elif cat == WC_WSegSpace:
                    state = State_WSegSpace
                else:
                    # WB4 lookahead?
                    if idx + 1 < n:
                        ncat = word_category(ord(s[idx + 1]))
                        if ncat in (WC_Format, WC_Extend, WC_ZWJ):
                            state = State_FormatExtend
                            fmt_ext_type = ExtendType_AcceptNone
                            cached_cat = ncat
                            continue
                    break  # WB999

            elif state == State_WSegSpace:
                if cat == WC_WSegSpace and not skipped_format_extend:
                    state = State_WSegSpace
                else:
                    take_curr = False
                    break

            elif state == State_Zwj:
                take_curr = False
                break

            elif state in (State_Letter, State_HLetter):
                if cat == WC_ALetter:
                    state = State_Letter
                elif cat == WC_Hebrew_Letter:
                    state = State_HLetter
                elif cat == WC_Numeric:
                    state = State_Numeric
                elif cat == WC_ExtendNumLet:
                    state = State_ExtendNumLet
                elif cat == WC_Double_Quote and state == State_HLetter:
                    savecat = cat
                    saveidx = idx
                    state = State_FormatExtend
                    fmt_ext_type = ExtendType_RequireHLetter
                elif cat == WC_Single_Quote and state == State_HLetter:
                    state = State_FormatExtend
                    fmt_ext_type = ExtendType_AcceptQLetter
                elif cat in (WC_MidLetter, WC_MidNumLet, WC_Single_Quote):
                    savecat = cat
                    saveidx = idx
                    state = State_FormatExtend
                    fmt_ext_type = ExtendType_RequireLetter
                else:
                    take_curr = False
                    break

            elif state == State_Numeric:
                if cat == WC_Numeric:
                    state = State_Numeric
                elif cat == WC_ALetter:
                    state = State_Letter
                elif cat == WC_Hebrew_Letter:
                    state = State_HLetter
                elif cat == WC_ExtendNumLet:
                    state = State_ExtendNumLet
                elif cat in (WC_MidNum, WC_MidNumLet, WC_Single_Quote):
                    savecat = cat
                    saveidx = idx
                    state = State_FormatExtend
                    fmt_ext_type = ExtendType_RequireNumeric
                else:
                    take_curr = False
                    break

            elif state == State_Katakana:
                if cat == WC_Katakana:
                    state = State_Katakana
                elif cat == WC_ExtendNumLet:
                    state = State_ExtendNumLet
                else:
                    take_curr = False
                    break

            elif state == State_ExtendNumLet:
                if cat == WC_ExtendNumLet:
                    state = State_ExtendNumLet
                elif cat == WC_ALetter:
                    state = State_Letter
                elif cat == WC_Hebrew_Letter:
                    state = State_HLetter
                elif cat == WC_Numeric:
                    state = State_Numeric
                elif cat == WC_Katakana:
                    state = State_Katakana
                else:
                    take_curr = False
                    break

            elif state == State_Regional:
                if regional == Regional_Full:
                    take_curr = False
                    break
                elif regional == Regional_Half:
                    if cat == WC_Regional_Indicator:
                        regional = Regional_Full
                    else:
                        take_curr = False
                        break

            elif state == State_Emoji:
                take_curr = False
                break

            elif state == State_FormatExtend:
                t = fmt_ext_type
                if t == ExtendType_RequireNumeric and cat == WC_Numeric:
                    state = State_Numeric
                elif t in (ExtendType_RequireLetter, ExtendType_AcceptQLetter) and cat == WC_ALetter:
                    state = State_Letter
                elif t in (ExtendType_RequireLetter, ExtendType_AcceptQLetter) and cat == WC_Hebrew_Letter:
                    state = State_HLetter
                elif t == ExtendType_RequireHLetter and cat == WC_Hebrew_Letter:
                    state = State_HLetter
                elif t in (ExtendType_AcceptNone, ExtendType_AcceptQLetter):
                    take_curr = False
                    take_cat = False
                    break
                else:
                    break   # rewind

        # ----- 循环后处理 -----
        # FormatExtend 回溯
        if state == State_FormatExtend:
            t = fmt_ext_type
            if t in (ExtendType_RequireLetter, ExtendType_RequireHLetter, ExtendType_RequireNumeric):
                idx = saveidx
                cat = savecat
                take_curr = False

        # 根据 take_curr / take_cat 调整结束位置，并设置下一轮缓存的 cat
        if take_curr:
            idx += 1
            cached_cat = None
        elif take_cat:
            cached_cat = cat
        else:
            cached_cat = None

        # 切出当前片段并更新 offset
        segment = s[offset:idx]
        yield (offset, segment)
        offset = idx


# ----------------------------------------------------------------------
# AsciiWordBoundIter – fast path for ASCII-only strings
# ----------------------------------------------------------------------

def is_infix(b: str, prev: str, _next: str) -> bool:
    if b in ('.', ',', ';', "'") and prev.isdigit() and _next.isdigit():
        return True
    if b in ("'", '.', ':') and prev.isalpha() and _next.isalpha():
        return True
    return False


def ascii_word_bounds(_input: str):
    offset = 0
    length = len(_input)
    
    while offset < length:
        i = 0
        ch0 = _input[offset + i]
        # space run
        if ch0 == ' ':
            i = offset + 1
            while i < length and _input[i] == ' ':
                i += 1
            yield (offset, _input[offset : i])
            offset = i
            continue

        # core run
        if ch0.isalnum() or ch0 == '_':
            i = offset + 1
            while i < length:
                b = _input[i]
                if (b.isalnum() or b == '_') or (i + 1 < length and is_infix(b, _input[i - 1], _input[i + 1])):
                    i += 1
                else:
                    break
            yield (offset, _input[offset : i])
            offset = i
            continue

        # CR+LF
        if ch0 == '\r' and length - offset >= 2 and _input[offset + 1] == '\n':
            yield (offset, _input[offset : offset+2])
            offset += 2
            continue

        # single char
        yield (offset, _input[offset : offset + 1])
        offset += 1
        
def word_bounds(s: str):
    if s.isascii(): return ascii_word_bounds(s)
    return unicode_word_bounds(s)

# ----------------------------------------------------------------------
# Filtering helpers
# ----------------------------------------------------------------------

def is_word_char(ch: int) -> bool:  # 暂定为判断L、N、M
    if ch == 0xFF9F or ch == 0xFF9E:
        return False
    return isLetter(ch) or isNd(ch) or isNl(ch)

def is_word_like(s: str) -> bool:
    return any(map(lambda c: is_word_char(ord(c)), s))


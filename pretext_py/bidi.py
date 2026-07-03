# Simplified bidi metadata helper for the rich prepareWithSegments() path,
# forked from pdf.js via Sebastian's text-layout. It classifies characters
# into bidi _types, computes embedding levels, and maps them onto prepared
# segments for custom rendering. The line-breaking engine does not consume
# these levels.

from .bidi_data import latin1BidiTypes, nonLatin1BidiRanges
from .intl_segmenter_py import String


def classifyCodePoint(code_point: int) -> str:
    """Return the bidi type for a single Unicode code point."""
    if code_point <= 0x00FF:
        return latin1BidiTypes[code_point]

    lo = 0
    hi = len(nonLatin1BidiRanges) - 1
    while lo <= hi:
        mid = (lo + hi) >> 1
        start, end, bidi_type = nonLatin1BidiRanges[mid]
        if code_point < start:
            hi = mid - 1
            continue
        if code_point > end:
            lo = mid + 1
            continue
        return bidi_type

    return 'L'


def computeBidiLevels(string: String):
    length = string.length
    if length == 0: return None

    _types = [None] * length
    sawBidi = False

    # Keep the resolved bidi classes aligned to UTF-16 code-unit offsets,
    # because the rich prepared segments index back into the normalized string
    # with JavaScript string offsets.
    i = 0
    while i < length:
        first = string.charCodeAt(i)
        codePoint = first
        codeUnitLength = 1
    
        if first >= 0xD800 and first <= 0xDBFF and i + 1 < length:
            second = string.charCodeAt(i + 1)
            if second >= 0xDC00 and second <= 0xDFFF:
                codePoint = ((first - 0xD800) << 10) + (second - 0xDC00) + 0x10000
                codeUnitLength = 2
    
        t = classifyCodePoint(codePoint)
        if t == 'R' or t == 'AL' or t == 'AN': sawBidi = True
        for j in range(codeUnitLength):
            _types[i + j] = t
        i += codeUnitLength

    if not sawBidi: return None

    # Use the first strong character to pick the paragraph base direction.
    # Rich-path bidi metadata is only an approximation, but this keeps mixed
    # LTR/RTL text aligned with the common UBA paragraph rule.
    startLevel = 0
    for i in range(length):
        t = _types[i]
        if t == 'L':
            startLevel = 0
            break
        if t == 'R' or t == 'AL':
            startLevel = 1
            break

    levels = bytearray(length)
    for i in range(length): levels[i] = startLevel

    e = 'R' if startLevel & 1 else 'L'
    sor = e

    # W1-W7
    lastType = sor
    for i in range(length):
        if _types[i] == 'NSM': _types[i] = lastType
        else: lastType = _types[i]
    lastType = sor
    
    for i in range(length):
        t = _types[i]
        if t == 'EN': _types[i] = 'AN' if lastType == 'AL' else 'EN'
        elif t == 'R' or t == 'L' or t == 'AL': lastType = t

    for i in range(length):
        if _types[i] == 'AL': _types[i] = 'R'

    for i in range(1, length - 1):
        if _types[i] == 'ES' and _types[i - 1] == 'EN' and _types[i + 1] == 'EN':
            _types[i] = 'EN'
        if (
          _types[i] == 'CS' and \
          (_types[i - 1] == 'EN' or _types[i - 1] == 'AN') and \
          _types[i + 1] == _types[i - 1]
        ):
            _types[i] = _types[i - 1]
        
    for i in range(length):
        if _types[i] != 'EN': continue
        # 向左扫描
        j = i - 1
        while j >= 0 and _types[j] == 'ET':
            _types[j] = 'EN'
            j -= 1
        
        # 向右扫描
        j = i + 1
        while j < length and _types[j] == 'ET':
            _types[j] = 'EN'
            j += 1

    for i in range(length):
        t = _types[i]
        if t == 'WS' or t == 'ES' or t == 'ET' or t == 'CS': _types[i] = 'ON'
        
    lastType = sor
    for i in range(length):
        t = _types[i]
        if t == 'EN': _types[i] = 'L' if lastType == 'L' else 'EN'
        elif t == 'R' or t == 'L': lastType = t

    # N1-N2
    for i in range(length):
        if _types[i] != 'ON': continue
        end = i + 1
        while end < length and _types[end] == 'ON': end += 1
        before = _types[i - 1] if i > 0 else sor
        after = _types[end] if end < length else sor
        bDir = 'R' if before != 'L' else 'L'
        aDir = 'R' if after != 'L' else 'L'
        if bDir == aDir:
            for j in range(i, end): _types[j] = bDir

        i = end - 1
      
    for i in range(length):
        if _types[i] == 'ON': _types[i] = e

    # I1-I2
    for i in range(length):
        t = _types[i]
        if (levels[i] & 1) == 0:
            if t == 'R': levels[i] += 1
            elif t == 'AN' or t == 'EN': levels[i] += 2
        elif t == 'L' or t == 'AN' or t == 'EN':
            levels[i] += 1

    return levels


def computeSegmentLevels(normalized: String, segStarts):
    bidiLevels = computeBidiLevels(normalized)
    if bidiLevels is None: return None

    segLevels = bytearray(len(segStarts))
    for i in range(len(segStarts)):
        segLevels[i] = bidiLevels[segStarts[i]]

    return segLevels

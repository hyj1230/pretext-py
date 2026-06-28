from .intl_segmenter_py import Segmenter, String, isArabic, isMark, isNd, isPunctuation, isSymbol, isCo, isEmojiPresentation
import re


collapsibleWhitespaceRunRe = re.compile(r'[ \t\n\r\f]+')
needsWhitespaceNormalizationRe = re.compile(r'[\t\n\r\f]| {2,}|^ | \Z')  # 用 \Z 替代 $


def getWhiteSpaceProfile(whiteSpace: str = None):
    mode = whiteSpace or 'normal'
    if mode == 'pre-wrap':
        return {
            'mode': mode, 
            'preserveOrdinarySpaces': True, 
            'preserveHardBreaks': True
        }
    else:
        return {
            'mode': mode,
            'preserveOrdinarySpaces': False, 
            'preserveHardBreaks': False
        }


def normalizeWhitespaceNormal(text: String) -> String:
    _text = str(text)
    if not needsWhitespaceNormalizationRe.search(_text):
        return text

    normalized = String(collapsibleWhitespaceRunRe.sub(' ', _text))
    if normalized.charCodeAt(0) == 0x20:
        normalized = normalized.slice(1)
    if normalized.length > 0 and normalized.charCodeAt(normalized.length - 1) == 0x20:
        normalized = normalized.slice(0, -1)

    return normalized


def normalizeWhitespacePreWrap(text: String) -> String:
    _text = str(text)
    if not re.search(r'[\r\f]', _text):
        return String(_text.replace('\r\n', '\n'))
  
    return String(_text.replace('\r\n', '\n').replace('\r', '\n').replace('\f', '\n'))


sharedWordSegmenter: Segmenter = None
segmenterLocale: str = None


def getSharedWordSegmenter() -> Segmenter:
    global sharedWordSegmenter  # pylint:disable=W0603
    if sharedWordSegmenter is None:
        sharedWordSegmenter = Segmenter(segmenterLocale, {'granularity': 'word' })
    
    return sharedWordSegmenter


def clearAnalysisCaches():
    global sharedWordSegmenter  # pylint:disable=W0603
    sharedWordSegmenter = None


def setAnalysisLocale(locale: str = None):
    global segmenterLocale, sharedWordSegmenter  # pylint:disable=W0603
    nextLocale = locale or None
    if segmenterLocale == nextLocale: return
    segmenterLocale = nextLocale
    sharedWordSegmenter = None
    

def containsArabicScript(text: String) -> bool:
    return any(map(lambda s: isArabic(ord(s)), str(text)))



def isCJKCodePoint(codePoint: int) -> bool:
    return (
        (codePoint >= 0x4E00 and codePoint <= 0x9FFF) or
        (codePoint >= 0x3400 and codePoint <= 0x4DBF) or
        (codePoint >= 0x20000 and codePoint <= 0x2A6DF) or
        (codePoint >= 0x2A700 and codePoint <= 0x2B73F) or
        (codePoint >= 0x2B740 and codePoint <= 0x2B81F) or
        (codePoint >= 0x2B820 and codePoint <= 0x2CEAF) or
        (codePoint >= 0x2CEB0 and codePoint <= 0x2EBEF) or
        (codePoint >= 0x2EBF0 and codePoint <= 0x2EE5D) or
        (codePoint >= 0x2F800 and codePoint <= 0x2FA1F) or
        (codePoint >= 0x30000 and codePoint <= 0x3134F) or
        (codePoint >= 0x31350 and codePoint <= 0x323AF) or
        (codePoint >= 0x323B0 and codePoint <= 0x33479) or
        (codePoint >= 0xF900 and codePoint <= 0xFAFF) or
        (codePoint >= 0x3000 and codePoint <= 0x303F) or
        (codePoint >= 0x3040 and codePoint <= 0x309F) or
        (codePoint >= 0x3130 and codePoint <= 0x318F) or
        (codePoint >= 0x30A0 and codePoint <= 0x30FF) or
        (codePoint >= 0xAC00 and codePoint <= 0xD7AF) or
        (codePoint >= 0xFF00 and codePoint <= 0xFFEF)
    )


def isCJK(s: String) -> bool:
    i: int = 0
    while i < s.length:
        first = s.charCodeAt(i)
        if first < 0x3000:
            i += 1
            continue

        if first >= 0xD800 and first <= 0xDBFF and i + 1 < s.length:
            second = s.charCodeAt(i + 1)
            if second >= 0xDC00 and second <= 0xDFFF:
                codePoint = ((first - 0xD800) << 10) + (second - 0xDC00) + 0x10000
                if isCJKCodePoint(codePoint): return True
                i += 2
                continue
        if isCJKCodePoint(first): return True
        i += 1
    return False


def endsWithLineStartProhibitedText(text: String) -> bool:
    last: String = getLastCodePoint(text)
    return last is not None and (str(last) in kinsokuStart or str(last) in leftStickyPunctuation)


keepAllGlueChars = set([
  '\u00A0',
  '\u202F',
  '\u2060',
  '\uFEFF',
])


keepAllDashBreakChars = set([
  '-',
  '\u2010',
  '\u2013',
  '\u2014',
])


def endsWithKeepAllGlueText(text: String) -> bool:
    last = getLastCodePoint(text)
    return last is not None and str(last) in keepAllGlueChars


def endsWithKeepAllDashBreakText(text: String) -> bool:
    last = getLastCodePoint(text)
    return last is not None and str(last) in keepAllDashBreakChars


def canContinueKeepAllTextRun(previousText: String, breakAfterPunctuation: bool) -> bool:
    if endsWithKeepAllGlueText(previousText): return False
    if not breakAfterPunctuation: return True
    if endsWithLineStartProhibitedText(previousText): return False
    if endsWithKeepAllDashBreakText(previousText): return False
    return True


kinsokuStart = set([
  '\uFF0C',
  '\uFF0E',
  '\uFF01',
  '\uFF1A',
  '\uFF1B',
  '\uFF1F',
  '\u3001',
  '\u3002',
  '\u30FB',
  '\uFF09',
  '\u3015',
  '\u3009',
  '\u300B',
  '\u300D',
  '\u300F',
  '\u3011',
  '\u3017',
  '\u3019',
  '\u301B',
  '\u30FC',
  '\u3005',
  '\u303B',
  '\u309D',
  '\u309E',
  '\u30FD',
  '\u30FE',
])


kinsokuEnd = set([
  '"',
  '(', '[', '{',
  '¡', '¿',
  '“', '‘', '‚', '„', '«', '‹',
  '\u2E18',
  '\uFF08',
  '\u3014',
  '\u3008',
  '\u300A',
  '\u300C',
  '\u300E',
  '\u3010',
  '\u3016',
  '\u3018',
  '\u301A',
])


forwardStickyGlue = set([
  "'", '’',
])


leftStickyPunctuation = set([
  '.', ',', '!', '?', ':', ';',
  '\u060C',
  '\u061B',
  '\u061F',
  '\u0964',
  '\u0965',
  '\u104A',
  '\u104B',
  '\u104C',
  '\u104D',
  '\u104F',
  ')', ']', '}',
  '%',
  '"',
  '”', '’', '»', '›',
  '…',
])


arabicNoSpaceTrailingPunctuation = set([
  ':',
  '.',
  '\u060C',
  '\u061B',
])

myanmarMedialGlue = set([
  '\u104F',
])

closingQuoteChars = set([
  '”', '’', '»', '›',
  '\u300D',
  '\u300F',
  '\u3011',
  '\u300B',
  '\u3009',
  '\u3015',
  '\uFF09',
])


def isLeftStickyPunctuationSegment(segment: String) -> bool:
    if isEscapedQuoteClusterSegment(segment): return True
    sawPunctuation = False
    for ch in str(segment):
        if ch in leftStickyPunctuation or isLineBreakNumericAffix(ch):
            sawPunctuation = True
            continue
        if sawPunctuation and isMark(ord(ch)): continue
        return False

    return sawPunctuation


def isCJKLineStartProhibitedSegment(segment: String) -> bool:
    for ch in str(segment):
        if ch not in kinsokuStart and ch not in leftStickyPunctuation: return False
    return segment.length > 0


def isForwardStickyClusterSegment(segment: String) -> bool:
    if isEscapedQuoteClusterSegment(segment): return True
    for ch in str(segment):
        if (
          ch not in kinsokuEnd and \
          ch not in forwardStickyGlue and \
          not isMark(ord(ch)) and \
          not isLineBreakNumericAffix(ch)
        ):
            return False

    return segment.length > 0


def isEscapedQuoteClusterSegment(segment: String) -> bool:
    sawQuote = False
    for ch in str(segment):
        if ch == '\\' or isMark(ord(ch)): continue
        if ch in kinsokuEnd or ch in leftStickyPunctuation or ch in forwardStickyGlue:
            sawQuote = True
            continue
        return False
    return sawQuote


def previousCodePointStart(text: String, end: int) -> int:
    last = end - 1
    if last <= 0: return max(last, 0)

    lastCodeUnit: int = text.charCodeAt(last)
    if lastCodeUnit < 0xDC00 or lastCodeUnit > 0xDFFF: return last

    maybeHigh: int = last - 1
    if maybeHigh < 0: return last

    highCodeUnit: int = text.charCodeAt(maybeHigh)
    return maybeHigh if highCodeUnit >= 0xD800 and highCodeUnit <= 0xDBFF else last


def getLastCodePoint(text: String) -> String:
    if text.length == 0: return None
    start = previousCodePointStart(text, text.length)
    return text.slice(start)


def getFirstSignificantCodePoint(text: String) -> str:
    for ch in str(text):
        if not isMark(ord(ch)): return ch
    return None


def getLastSignificantCodePoint(text: String) -> String:
    end = text.length
    while end > 0:
        start = previousCodePointStart(text, end)
        ch = text.slice(start, end)
        if not isMark(ord(str(ch))): return ch
        end = start

    return None


# Unicode line-break PR/PO classes from UAX #14, stored as start/end pairs.
lineBreakNumericAffixRanges = (
  0x0024, 0x0025, 0x002B, 0x002B, 0x005C, 0x005C, 0x00A2, 0x00A5, 0x00B0, 0x00B1,
  0x058F, 0x058F, 0x0609, 0x060B, 0x066A, 0x066A, 0x07FE, 0x07FF, 0x09F2, 0x09F3,
  0x09F9, 0x09FB, 0x0AF1, 0x0AF1, 0x0BF9, 0x0BF9, 0x0D79, 0x0D79, 0x0E3F, 0x0E3F,
  0x17DB, 0x17DB, 0x2030, 0x2037, 0x2057, 0x2057, 0x20A0, 0x20CF, 0x2103, 0x2103,
  0x2109, 0x2109, 0x2116, 0x2116, 0x2212, 0x2213, 0xA838, 0xA838, 0xFDFC, 0xFDFC,
  0xFE69, 0xFE6A, 0xFF04, 0xFF05, 0xFFE0, 0xFFE1, 0xFFE5, 0xFFE6,
  0x11FDD, 0x11FE0, 0x1E2FF, 0x1E2FF, 0x1ECAC, 0x1ECAC, 0x1ECB0, 0x1ECB0,
)


def isCodePointInRanges(codePoint: int, ranges) -> bool:
    for i in range(0, len(ranges), 2):
        if codePoint >= ranges[i] and codePoint <= ranges[i + 1]: return True
  
    return False


def isLineBreakNumericAffix(ch: str) -> bool:
    if not ch: return False

    return isCodePointInRanges(ord(ch[0]), lineBreakNumericAffixRanges)


def endsWithLineBreakNumericAffix(text: String) -> bool:
    last: String = getLastSignificantCodePoint(text)
    return last is not None and isLineBreakNumericAffix(str(last))


def startsWithDecimalDigit(text: String) -> bool:
    first: str = getFirstSignificantCodePoint(text)
    return first is not None and isNd(ord(first))


def splitTrailingForwardStickyCluster(text: String):
    chars = str(text)
    splitIndex = len(chars)

    while splitIndex > 0:
        ch = chars[splitIndex - 1]
        if isMark(ord(ch)):
            splitIndex -= 1
            continue
        if ch in kinsokuEnd or ch in forwardStickyGlue:
            splitIndex -= 1
            continue
        break

    if splitIndex <= 0 or splitIndex == len(chars): return None
    return {
        'head': String(chars[:splitIndex]),
        'tail': String(chars[splitIndex:])
    }


def getRepeatableSingleCharRunChar(text: String, isWordLike: bool, kind: str):
    flag = kind == 'text' and not isWordLike and text.length == 1 and text != '-' and text != '—'
    return text if flag else None


def materializeDeferredSingleCharRun(texts, chars, lengths, index: int) -> String:
    ch = chars[index]
    text = texts[index]
    if ch is None: return text

    length = lengths[index]
    if text.length == length: return text

    materialized = ch.repeat(length)
    texts[index] = materialized
    return materialized


def hasArabicNoSpacePunctuation(containsArabic: bool, lastCodePoint) -> bool:
  return containsArabic and lastCodePoint is not None and str(lastCodePoint) in arabicNoSpaceTrailingPunctuation


def endsWithMyanmarMedialGlue(segment: String) -> bool:
    lastCodePoint: String = getLastCodePoint(segment)
    return lastCodePoint is not None and str(lastCodePoint) in myanmarMedialGlue


def splitLeadingSpaceAndMarks(segment: String):
    if segment.length < 2 or segment.charCodeAt(0) != 32: return None
    marks = segment.slice(1)
    
    if all(map(lambda s: isMark(ord(s)), str(marks))):
        return {'space': String(' '), 'marks': marks}

    return None


def endsWithClosingQuote(text: String) -> bool:
    end = text.length
    while end > 0:
        start = previousCodePointStart(text, end)
        ch = str(text.slice(start, end))
        if ch in closingQuoteChars: return True
        if ch not in leftStickyPunctuation: return False
        end = start
    return False


def classifySegmentBreakChar(ch: str, whiteSpaceProfile) -> str:
    if whiteSpaceProfile['preserveOrdinarySpaces'] or whiteSpaceProfile['preserveHardBreaks']:
        if ch == ' ': return 'preserved-space'
        if ch == '\t': return 'tab'
        if whiteSpaceProfile['preserveHardBreaks'] and ch == '\n': return 'hard-break'
    if ch == ' ': return 'space'
    if ch == '\u00A0' or ch == '\u202F' or ch == '\u2060' or ch == '\uFEFF':
        return 'glue'
    if ch == '\u200B': return 'zero-width-break'
    if ch == '\u00AD': return 'soft-hyphen'
    return 'text'


# All characters that classifySegmentBreakChar maps to a non-'text' kind.
breakChar = (0x20, 9, 10, 0xA0, 0xAD, 0x200B, 0x202F, 0x2060, 0xFEFF)


def joinTextParts(parts) -> String:
    if len(parts) == 1:
        return String(parts[0])
    return String(''.join(map(str, parts)))


def joinReversedPrefixParts(prefixParts, tail) -> String:
    parts = []
    for i in range(len(prefixParts) - 1, -1, -1):
        parts.append(prefixParts[i]) 
    parts.append(tail)
    return joinTextParts(parts)


def splitSegmentByBreakKind(segment: String, isWordLike: bool, start: int, whiteSpaceProfile):
    if not segment.contain_code(breakChar):
        return [{'text': segment, 'isWordLike': isWordLike, 'kind': 'text', 'start': start}]

    pieces = []
    currentKind = None
    currentTextParts = []
    currentStart = start
    currentWordLike = False
    offset = 0

    for ch in str(segment):
        kind: str = classifySegmentBreakChar(ch, whiteSpaceProfile)
        wordLike: bool = kind == 'text' and isWordLike
    
        if currentKind is not None and kind == currentKind and wordLike == currentWordLike:
            currentTextParts.append(ch)
            offset += String.measure_length(ch)
            continue
    
        if currentKind is not None:
            pieces.append({
                'text': String(''.join(currentTextParts)),
                'isWordLike': currentWordLike,
                'kind': currentKind,
                'start': currentStart,
            })
    
        currentKind = kind
        currentTextParts = [ch]
        currentStart = start + offset
        currentWordLike = wordLike
        offset += String.measure_length(ch)

    if currentKind is not None:
        pieces.append({
            'text': String(''.join(currentTextParts)),
            'isWordLike': currentWordLike,
            'kind': currentKind,
            'start': currentStart,
        })

    return pieces


def isTextRunBoundary(kind: str) -> bool:
  return (
      kind == 'space' or \
      kind == 'preserved-space' or \
      kind == 'zero-width-break' or \
      kind == 'hard-break'
  )


urlSchemeSegmentRe = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:\Z')  # 这里用 \Z 代替 $

def isUrlLikeRunStart(segmentation, index: int) -> bool:
    text = str(segmentation['texts'][index])
    if text.startswith('www.'): return True
    return (
        urlSchemeSegmentRe.match(text) and
        index + 1 < segmentation['len'] and
        segmentation['kinds'][index + 1] == 'text' and
        segmentation['texts'][index + 1] == '//'
    )


def isUrlQueryBoundarySegment(text: String) -> bool:
    text = str(text)
    return '?' in text and ('://' in text or text.startswith('www.'))


def mergeUrlLikeRuns(segmentation):
    texts = segmentation['texts'][:]
    isWordLike = segmentation['isWordLike'][:]
    kinds = segmentation['kinds'][:]
    starts = segmentation['starts'][:]
 
    for i in range(segmentation['len']):
        if kinds[i] != 'text' or not isUrlLikeRunStart(segmentation, i): continue
    
        mergedParts = [texts[i]]
        j = i + 1
        while j < segmentation['len'] and not isTextRunBoundary(kinds[j]):
            mergedParts.append(texts[j])
            isWordLike[i] = True
            endsQueryPrefix = '?' in str(texts[j])
            kinds[j] = 'text'
            texts[j] = String('')
            j += 1
            if endsQueryPrefix: break
        texts[i] = joinTextParts(mergedParts)

    compactLen = 0
    for read in range(len(texts)):
        text = texts[read]
        if text.length == 0: continue
        if compactLen != read:
            texts[compactLen] = text
            isWordLike[compactLen] = isWordLike[read]
            kinds[compactLen] = kinds[read]
            starts[compactLen] = starts[read]
        compactLen += 1

    return {
        'len': compactLen,
        'texts': texts[:compactLen],
        'isWordLike': isWordLike[:compactLen],
        'kinds': kinds[:compactLen],
        'starts': starts[:compactLen],
    }


def mergeUrlQueryRuns(segmentation):
    texts = []
    isWordLike = []
    kinds = []
    starts = []

    i = 0
    while i < segmentation['len']:
        text = segmentation['texts'][i]
        texts.append(text)
        isWordLike.append(segmentation['isWordLike'][i])
        kinds.append(segmentation['kinds'][i])
        starts.append(segmentation['starts'][i])
    
        if not isUrlQueryBoundarySegment(text):
            i += 1
            continue
    
        nextIndex = i + 1
        if (
          nextIndex >= segmentation['len'] or \
          isTextRunBoundary(segmentation['kinds'][nextIndex])
        ):
            i += 1
            continue
    
        queryParts = []
        queryStart = segmentation['starts'][nextIndex]
        j = nextIndex
        while j < segmentation['len'] and not isTextRunBoundary(segmentation['kinds'][j]):
            queryParts.append(segmentation['texts'][j])
            j += 1
    
        if len(queryParts) > 0:
            texts.append(joinTextParts(queryParts))
            isWordLike.append(True)
            kinds.append('text')
            starts.append(queryStart)
            i = j - 1
        i += 1

    return {
        'len': len(texts),
        'texts': texts,
        'isWordLike': isWordLike,
        'kinds': kinds,
        'starts': starts,
    }


numericJoinerChars = set([
  ':', '-', '/', '×', ',', '.', '+',
  '\u2013',
  '\u2014',
])


noSpaceWordBreakAfterChars = set([
  '?',
  '\u058A',
  '-',
  '\u2010',
  '\u2012',
  '\u2013',
  '\u2014',
  '\u2026',
  '\u203C',
  '\u203D',
  '\u2049',
])


def isAsciiWordInternalSymbolCode(code: int) -> bool:
    return (
      (code >= 0x21 and code <= 0x2F and code != 0x2D) or \
      (code >= 0x3A and code <= 0x40 and code != 0x3F) or \
      (code >= 0x5B and code <= 0x60) or \
      (code >= 0x7B and code <= 0x7E)
    )


def isNoSpaceWordInternalSymbol(ch: str) -> bool:
    code = ord(ch[0])
    if code < 0x80: return isAsciiWordInternalSymbolCode(code)

    return (
      ch not in noSpaceWordBreakAfterChars and \
      not isEmojiPresentation(code) and \
      (isPunctuation(code) or isSymbol(code) or isCo(code))
    )


def isNoSpaceWordInternalSymbolSegment(text: String) -> bool:
    sawSymbol = False
    for ch in str(text):
        if isMark(ord(ch)): continue
        if not isNoSpaceWordInternalSymbol(ch): return False
        sawSymbol = True
    return sawSymbol


def endsWithNoSpaceWordJoiner(text: String) -> bool:
    end = text.length
    while end > 0:
        start = previousCodePointStart(text, end)
        ch = str(text.slice(start, end))
        if isMark(ord(ch)):
            end = start
            continue
        return isNoSpaceWordInternalSymbol(ch) or isLineBreakNumericAffix(ch)
    return False


def canJoinNoSpaceWordBoundary(
    leftText: String,
    leftWordLike: bool,
    rightText: String,
    rightWordLike: bool,
) -> bool:
    leftSymbol = not leftWordLike and isNoSpaceWordInternalSymbolSegment(str(leftText))
    rightSymbol = not rightWordLike and isNoSpaceWordInternalSymbolSegment(str(rightText))
    leftAffix = endsWithLineBreakNumericAffix(leftText)
    leftEndsJoiner = (leftWordLike or leftAffix) and endsWithNoSpaceWordJoiner(leftText)

    if not leftSymbol and not rightSymbol and not leftEndsJoiner: return False
    if isCJK(leftText) or isCJK(rightText): return False

    return (leftWordLike or leftSymbol or leftAffix) and (rightWordLike or rightSymbol)


def segmentContainsDecimalDigit(text: String) -> bool:
    for ch in str(text):
        if isNd(ord(ch)): return True
    return False


def isNumericRunSegment(text: String) -> bool:
    if text.length == 0: return False
    for ch in str(text):
        if isNd(ord(ch)) or ch in numericJoinerChars: continue
        return False
    return True


def mergeNumericRuns(segmentation):
    texts = []
    isWordLike = []
    kinds = []
    starts = []

    i = 0
    while i < segmentation['len']:
        text = segmentation['texts'][i]
        kind = segmentation['kinds'][i]
    
        if kind == 'text' and isNumericRunSegment(text) and segmentContainsDecimalDigit(text):
            mergedParts = [text]
            j = i + 1
            while (
              j < segmentation['len'] and \
              segmentation['kinds'][j] == 'text' and \
              isNumericRunSegment(segmentation['texts'][j])
            ):
                mergedParts.append(segmentation['texts'][j])
                j += 1
          
    
            texts.append(joinTextParts(mergedParts))
            isWordLike.append(True)
            kinds.append('text')
            starts.append(segmentation['starts'][i])
            i = j - 1
            i += 1
            continue

        texts.append(text)
        isWordLike.append(segmentation['isWordLike'][i])
        kinds.append(kind)
        starts.append(segmentation['starts'][i])
        i += 1

    return {
        'len': len(texts),
        'texts': texts,
        'isWordLike': isWordLike,
        'kinds': kinds,
        'starts': starts,
    }


def mergeNoSpaceWordChains(segmentation):
    texts = []
    isWordLike = []
    kinds = []
    starts = []

    i = 0
    while i < segmentation['len']:
        text = segmentation['texts'][i]
        kind = segmentation['kinds'][i]
        wordLike = segmentation['isWordLike'][i]
    
        if kind == 'text':
            mergedParts = [text]
            j = i + 1
            mergedWordLike = wordLike
    
            while (
              j < segmentation['len'] and \
              segmentation['kinds'][j] == 'text' and \
              canJoinNoSpaceWordBoundary(
                segmentation['texts'][j - 1],
                segmentation['isWordLike'][j - 1],
                segmentation['texts'][j],
                segmentation['isWordLike'][j],
              )
            ):
                nextText = segmentation['texts'][j]
                mergedParts.append(nextText)
                mergedWordLike = mergedWordLike or segmentation['isWordLike'][j]
                j += 1
          
    
            if j > i + 1:
                texts.append(joinTextParts(mergedParts))
                isWordLike.append(mergedWordLike)
                kinds.append('text')
                starts.append(segmentation['starts'][i])
                i = j
                continue
          

        texts.append(text)
        isWordLike.append(wordLike)
        kinds.append(kind)
        starts.append(segmentation['starts'][i])
        i += 1

    return {
        'len': len(texts),
        'texts': texts,
        'isWordLike': isWordLike,
        'kinds': kinds,
        'starts': starts,
    }



def splitHyphenatedNumericRuns(segmentation):
    texts = []
    isWordLike = []
    kinds = []
    starts = []

    for i in range(segmentation['len']):
        text = segmentation['texts'][i]
        if segmentation['kinds'][i] == 'text' and '-' in str(text):
            parts = str(text).split('-')
            shouldSplit = len(parts) > 1
            for j in range(len(parts)):
                part = String(parts[j])
                if not shouldSplit: break
                if (
                  part.length == 0 or \
                  not segmentContainsDecimalDigit(part) or \
                  not isNumericRunSegment(part)
                ):
                    shouldSplit = False
        
            if shouldSplit:
                offset = 0
                for j in range(len(parts)):
                    part = parts[j]
                    splitText = String(f'{part}-' if j < len(parts) - 1 else part)
                    texts.append(splitText)
                    isWordLike.append(True)
                    kinds.append('text')
                    starts.append(segmentation['starts'][i] + offset)
                    offset += splitText.length
                continue
    
        texts.append(text)
        isWordLike.append(segmentation['isWordLike'][i])
        kinds.append(segmentation['kinds'][i])
        starts.append(segmentation['starts'][i])

    return {
        'len': len(texts),
        'texts': texts,
        'isWordLike': isWordLike,
        'kinds': kinds,
        'starts': starts,
    }


def mergeGlueConnectedTextRuns(segmentation):
    texts = []
    isWordLike = []
    kinds = []
    starts = []

    read = 0
    while read < segmentation['len']:
        textParts = [segmentation['texts'][read]]
        wordLike = segmentation['isWordLike'][read]
        kind = segmentation['kinds'][read]
        start = segmentation['starts'][read]
    
        if kind == 'glue':
            glueParts = [textParts[0]]
            glueStart = start
            read += 1
            while read < segmentation['len'] and segmentation['kinds'][read] == 'glue':
                glueParts.append(segmentation['texts'][read])
                read += 1
          
            glueText = joinTextParts(glueParts)

            if read < segmentation['len'] and segmentation['kinds'][read] == 'text':
                textParts[0] = glueText
                textParts.append(segmentation['texts'][read])
                wordLike = segmentation['isWordLike'][read]
                kind = 'text'
                start = glueStart
                read += 1
            else:
                texts.append(glueText)
                isWordLike.append(False)
                kinds.append('glue')
                starts.append(glueStart)
                continue
        else:
            read += 1
    
        if kind == 'text':
            while read < segmentation['len'] and segmentation['kinds'][read] == 'glue':
                glueParts = []
                while read < segmentation['len'] and segmentation['kinds'][read] == 'glue':
                    glueParts.append(segmentation['texts'][read])
                    read += 1
                
                glueText = joinTextParts(glueParts)
        
                if read < segmentation['len'] and segmentation['kinds'][read] == 'text':
                    textParts += [glueText, segmentation['texts'][read]]
                    wordLike = wordLike or segmentation['isWordLike'][read]
                    read += 1
                    continue
        
                textParts.append(glueText)
    
        texts.append(joinTextParts(textParts))
        isWordLike.append(wordLike)
        kinds.append(kind)
        starts.append(start)

    return {
        'len': len(texts),
        'texts': texts,
        'isWordLike': isWordLike,
        'kinds': kinds,
        'starts': starts,
    }


def carryTrailingForwardStickyAcrossCJKBoundary(segmentation):
    texts = segmentation['texts'][:]
    isWordLike = segmentation['isWordLike'][:]
    kinds = segmentation['kinds'][:]
    starts = segmentation['starts'][:]
    for i in range(len(texts) - 1):
        if kinds[i] != 'text' or kinds[i + 1] != 'text': continue
        if not isCJK(texts[i]) or not isCJK(texts[i + 1]): continue
    
        split = splitTrailingForwardStickyCluster(texts[i])
        if split is None: continue
    
        texts[i] = split['head']
        texts[i + 1] = split['tail'] + texts[i + 1]
        starts[i + 1] = starts[i] + split['head'].length

    return {
        'len': len(texts),
        'texts': texts,
        'isWordLike': isWordLike,
        'kinds': kinds,
        'starts': starts,
    }


def pad_inplace(lsts, target_len, fill_value=None):
    for lst in lsts:
        lst.extend([fill_value] * (target_len - len(lst)))


def buildMergedSegmentation(normalized: String, profile, whiteSpaceProfile):
    wordSegmenter = getSharedWordSegmenter()
    mergedLen = 0
    mergedTexts = []
    mergedTextParts = []
    mergedWordLike = []
    mergedKinds = []
    mergedStarts = []
    # Track repeatable single-char punctuation runs structurally so identical
    # merges stay O(1) instead of re-scanning the accumulated segment each time.
    mergedSingleCharRunChars = []
    mergedSingleCharRunLengths = []
    mergedContainsCJK = []
    mergedContainsArabicScript = []
    mergedEndsWithClosingQuote = []
    mergedEndsWithMyanmarMedialGlue = []
    mergedHasArabicNoSpacePunctuation = []

    for s in wordSegmenter.segment(normalized):
        for piece in splitSegmentByBreakKind(s['segment'], s.get('isWordLike', False), s['index'], whiteSpaceProfile):
            isText = piece['kind'] == 'text'
            repeatableSingleCharRunChar: String = getRepeatableSingleCharRunChar(piece['text'], piece['isWordLike'], piece['kind'])
            pieceContainsCJK: bool = isCJK(piece['text'])
            pieceContainsArabicScript: bool = containsArabicScript(piece['text'])
            pieceLastCodePoint: String = getLastCodePoint(piece['text'])
            pieceEndsWithClosingQuote: bool = endsWithClosingQuote(piece['text'])
            pieceEndsWithMyanmarMedialGlue: bool = endsWithMyanmarMedialGlue(piece['text'])
            prevIndex = mergedLen - 1
    
            def appendPieceToPrevious():
                if mergedSingleCharRunChars[prevIndex] is not None:  # pylint: disable=W0640
                    mergedTextParts[prevIndex] = [  # pylint: disable=W0640
                        materializeDeferredSingleCharRun(
                            mergedTexts,
                            mergedSingleCharRunChars,
                            mergedSingleCharRunLengths,
                            prevIndex,  # pylint: disable=W0640
                        ),
                    ]
                    mergedSingleCharRunChars[prevIndex] = None  # pylint: disable=W0640
                
                mergedTextParts[prevIndex].append(piece['text'])  # pylint: disable=W0640
                mergedWordLike[prevIndex] = mergedWordLike[prevIndex] or piece['isWordLike']  # pylint: disable=W0640
                mergedContainsCJK[prevIndex] = mergedContainsCJK[prevIndex] or pieceContainsCJK  # pylint: disable=W0640
                mergedContainsArabicScript[prevIndex] = mergedContainsArabicScript[prevIndex] or pieceContainsArabicScript  # pylint: disable=W0640
                mergedEndsWithClosingQuote[prevIndex] = pieceEndsWithClosingQuote  # pylint: disable=W0640
                mergedEndsWithMyanmarMedialGlue[prevIndex] = pieceEndsWithMyanmarMedialGlue  # pylint: disable=W0640
                mergedHasArabicNoSpacePunctuation[prevIndex] = hasArabicNoSpacePunctuation(  # pylint: disable=W0640
                    mergedContainsArabicScript[prevIndex],  # pylint: disable=W0640
                    pieceLastCodePoint,  # pylint: disable=W0640
                )
    
            # First-pass keeps: no-space script-specific joins and punctuation glue
            # that depend on the immediately preceding text run.
            if (
                profile['carryCJKAfterClosingQuote'] and \
                isText and \
                mergedLen > 0 and \
                mergedKinds[prevIndex] == 'text' and \
                pieceContainsCJK and \
                mergedContainsCJK[prevIndex] and \
                mergedEndsWithClosingQuote[prevIndex]
            ):
                appendPieceToPrevious()
            elif (
                isText and \
                mergedLen > 0 and \
                mergedKinds[prevIndex] == 'text' and \
                isCJKLineStartProhibitedSegment(piece['text']) and \
                mergedContainsCJK[prevIndex]
            ):
                appendPieceToPrevious()
            elif (
                isText and \
                mergedLen > 0 and \
                mergedKinds[prevIndex] == 'text' and \
                mergedEndsWithMyanmarMedialGlue[prevIndex]
            ):
                appendPieceToPrevious()
            elif (
                isText and \
                mergedLen > 0 and \
                mergedKinds[prevIndex] == 'text' and \
                piece['isWordLike'] and \
                pieceContainsArabicScript and \
                mergedHasArabicNoSpacePunctuation[prevIndex]
            ):
                appendPieceToPrevious()
                mergedWordLike[prevIndex] = True
            elif (
                repeatableSingleCharRunChar is not None and \
                mergedLen > 0 and \
                mergedKinds[prevIndex] == 'text' and \
                mergedSingleCharRunChars[prevIndex] == repeatableSingleCharRunChar
            ):
                _l = mergedSingleCharRunLengths[prevIndex]
                mergedSingleCharRunLengths[prevIndex] = (1 if _l is None else _l) + 1
            elif (
                isText and \
                not piece['isWordLike'] and \
                mergedLen > 0 and \
                mergedKinds[prevIndex] == 'text' and \
                not mergedContainsCJK[prevIndex] and \
                (
                  isLeftStickyPunctuationSegment(piece['text']) or \
                  (piece['text'] == '-' and mergedWordLike[prevIndex])
                )
            ):
                appendPieceToPrevious()
            else:
                if mergedLen >= len(mergedTexts):
                    pad_inplace(
                        [mergedTexts, mergedTextParts, mergedWordLike, 
                         mergedKinds, mergedStarts, mergedSingleCharRunChars,
                         mergedSingleCharRunLengths, mergedContainsCJK, 
                         mergedContainsArabicScript, mergedEndsWithClosingQuote,
                         mergedEndsWithMyanmarMedialGlue, mergedHasArabicNoSpacePunctuation],
                        mergedLen + 1 
                   )
                mergedTexts[mergedLen] = piece['text']
                mergedTextParts[mergedLen] = [piece['text']]
                mergedWordLike[mergedLen] = piece['isWordLike']
                mergedKinds[mergedLen] = piece['kind']
                mergedStarts[mergedLen] = piece['start']
                mergedSingleCharRunChars[mergedLen] = repeatableSingleCharRunChar
                mergedSingleCharRunLengths[mergedLen] = 0 if repeatableSingleCharRunChar is None else 1
                mergedContainsCJK[mergedLen] = pieceContainsCJK
                mergedContainsArabicScript[mergedLen] = pieceContainsArabicScript
                mergedEndsWithClosingQuote[mergedLen] = pieceEndsWithClosingQuote
                mergedEndsWithMyanmarMedialGlue[mergedLen] = pieceEndsWithMyanmarMedialGlue
                mergedHasArabicNoSpacePunctuation[mergedLen] = hasArabicNoSpacePunctuation(
                  pieceContainsArabicScript,
                  pieceLastCodePoint,
                )
                mergedLen += 1


    for i in range(mergedLen):
        if mergedSingleCharRunChars[i] is not None:
            mergedTexts[i] = materializeDeferredSingleCharRun(
                mergedTexts,
                mergedSingleCharRunChars,
                mergedSingleCharRunLengths,
                i,
            )
            continue
        mergedTexts[i] = joinTextParts(mergedTextParts[i])

    # Later passes operate on the merged text stream itself: contextual escaped
    # quote glue, forward-sticky carry, compaction, then the broader URL/numeric
    # and Arabic-leading-mark fixes.
    for i in range(1, mergedLen):
        if (
          mergedKinds[i] == 'text' and \
          not mergedWordLike[i] and \
          isEscapedQuoteClusterSegment(mergedTexts[i]) and \
          mergedKinds[i - 1] == 'text' and \
          not mergedContainsCJK[i - 1]
        ):
            mergedTexts[i - 1] += mergedTexts[i]
            mergedWordLike[i - 1] = mergedWordLike[i - 1] or mergedWordLike[i]
            mergedTexts[i] = String('')
  

    forwardStickyPrefixParts = [None] * mergedLen
    nextLiveIndex = -1

    for i in range(mergedLen - 1, -1, -1):
        text = mergedTexts[i]
        if text.length == 0: continue
    
        if (
          mergedKinds[i] == 'text' and \
          not mergedWordLike[i] and \
          nextLiveIndex >= 0 and \
          mergedKinds[nextLiveIndex] == 'text' and \
          (
            isForwardStickyClusterSegment(text) or \
            (text == '-' and startsWithDecimalDigit(mergedTexts[nextLiveIndex]))
          )
        ):
            prefixParts = forwardStickyPrefixParts[nextLiveIndex]
            if prefixParts is None: prefixParts = []
            prefixParts.append(text)
            forwardStickyPrefixParts[nextLiveIndex] = prefixParts
            mergedStarts[nextLiveIndex] = mergedStarts[i]
            mergedTexts[i] = String('')
            continue
    
        nextLiveIndex = i

    for i in range(mergedLen):
        prefixParts = forwardStickyPrefixParts[i]
        if prefixParts is None: continue
        mergedTexts[i] = joinReversedPrefixParts(prefixParts, mergedTexts[i])

    compactLen = 0
    for read in range(mergedLen):
        text = mergedTexts[read]
        if text.length == 0: continue
        if compactLen != read:
            mergedTexts[compactLen] = text
            mergedWordLike[compactLen] = mergedWordLike[read]
            mergedKinds[compactLen] = mergedKinds[read]
            mergedStarts[compactLen] = mergedStarts[read]
        compactLen += 1

    compacted = mergeGlueConnectedTextRuns({
        'len': compactLen,
        'texts': mergedTexts[:compactLen],
        'isWordLike': mergedWordLike[:compactLen],
        'kinds': mergedKinds[:compactLen],
        'starts': mergedStarts[:compactLen],
    })
    
    withMergedUrls = carryTrailingForwardStickyAcrossCJKBoundary(
      mergeNoSpaceWordChains(
        splitHyphenatedNumericRuns(mergeNumericRuns(mergeUrlQueryRuns(mergeUrlLikeRuns(compacted)))),
      ),
    )

    for i in range(withMergedUrls['len'] - 1):
        split = splitLeadingSpaceAndMarks(withMergedUrls['texts'][i])
        if split is None: continue
        if (
          (withMergedUrls['kinds'][i] != 'space' and withMergedUrls['kinds'][i] != 'preserved-space') or \
          withMergedUrls['kinds'][i + 1] != 'text' or \
          not containsArabicScript(withMergedUrls['texts'][i + 1])
        ):
            continue
    
        withMergedUrls['texts'][i] = split['space']
        withMergedUrls['isWordLike'][i] = False
        withMergedUrls['kinds'][i] = 'preserved-space' if withMergedUrls['kinds'][i] == 'preserved-space' else 'space'
        withMergedUrls['texts'][i + 1] = split['marks'] + withMergedUrls['texts'][i + 1]
        withMergedUrls['starts'][i + 1] = withMergedUrls['starts'][i] + split['space'].length

    return withMergedUrls


def compileAnalysisChunks(segmentation, whiteSpaceProfile):
    if segmentation['len'] == 0: return []
    if not whiteSpaceProfile['preserveHardBreaks']:
        return [{
          'startSegmentIndex': 0,
          'endSegmentIndex': segmentation['len'],
          'consumedEndSegmentIndex': segmentation['len'],
        }]

    chunks = []
    startSegmentIndex = 0

    for i in range(segmentation['len']):
        if segmentation['kinds'][i] != 'hard-break': continue
    
        chunks.append({
          'startSegmentIndex': startSegmentIndex,
          'endSegmentIndex': i,
          'consumedEndSegmentIndex': i + 1,
        })
        startSegmentIndex = i + 1

    if startSegmentIndex < segmentation['len']:
        chunks.append({
          'startSegmentIndex': startSegmentIndex,
          'endSegmentIndex': segmentation['len'],
          'consumedEndSegmentIndex': segmentation['len'],
        })

    return chunks


def mergeKeepAllTextSegments(normalized: String, segmentation, breakAfterPunctuation: bool):
    if segmentation['len'] <= 1: return segmentation

    texts = []
    isWordLike = []
    kinds = []
    starts = []
    
    groupStart = -1
    groupContainsCJK = False

    def pushOriginalText(index: int):
        texts.append(segmentation['texts'][index])
        isWordLike.append(segmentation['isWordLike'][index])
        kinds.append('text')
        starts.append(segmentation['starts'][index])

    def pushMergedText(start: int, end: int):
        wordLike = False
    
        for i in range(start, end):
            wordLike = wordLike or segmentation['isWordLike'][i]
    
        sourceStart = segmentation['starts'][start]
        sourceEnd = segmentation['starts'][end] if end < segmentation['len'] else normalized.length
        texts.append(normalized.slice(sourceStart, sourceEnd))
        isWordLike.append(wordLike)
        kinds.append('text')
        starts.append(sourceStart)

    def flushGroup(end: int):
        nonlocal groupContainsCJK, groupStart
        if groupStart < 0: return
    
        if groupContainsCJK:
            if groupStart + 1 == end:
                pushOriginalText(groupStart)
            else:
                pushMergedText(groupStart, end)
        else:
            for i in range(groupStart, end): pushOriginalText(i)
    
        groupStart = -1
        groupContainsCJK = False

    for i in range(segmentation['len']):
        text = segmentation['texts'][i]
        kind = segmentation['kinds'][i]
    
        if kind == 'text':
            if (
              groupStart >= 0 and \
              not canContinueKeepAllTextRun(segmentation['texts'][i - 1], breakAfterPunctuation)
            ):
                flushGroup(i)
          
            if groupStart < 0: groupStart = i
            groupContainsCJK = groupContainsCJK or isCJK(text)
            continue
        
        flushGroup(i)
        texts.append(text)
        isWordLike.append(segmentation['isWordLike'][i])
        kinds.append(kind)
        starts.append(segmentation['starts'][i])

    flushGroup(segmentation['len'])

    return {
        'len': len(texts),
        'texts': texts,
        'isWordLike': isWordLike,
        'kinds': kinds,
        'starts': starts,
    }


def analyzeText(text: String, profile, whiteSpace: str = 'normal', wordBreak: str = 'normal'):
    whiteSpaceProfile = getWhiteSpaceProfile(whiteSpace)
    normalized: String = normalizeWhitespacePreWrap(text) if whiteSpaceProfile['mode'] == 'pre-wrap' else normalizeWhitespaceNormal(text)
    if normalized.length == 0:
        return {
          'normalized': normalized,
          'chunks': [],
          'len': 0,
          'texts': [],
          'isWordLike': [],
          'kinds': [],
          'starts': [],
        }

    mergedSegmentation = buildMergedSegmentation(normalized, profile, whiteSpaceProfile)
    segmentation = mergeKeepAllTextSegments(normalized, mergedSegmentation, profile['breakKeepAllAfterPunctuation']) if wordBreak == 'keep-all' else mergedSegmentation

    return {
      'normalized': normalized,
      'chunks': compileAnalysisChunks(segmentation, whiteSpaceProfile),
      **segmentation,
    }

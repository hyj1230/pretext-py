# 基于 canvas measureText 的浏览器环境文本测量
#
# 问题：基于 DOM 的文本测量（getBoundingClientRect、offsetHeight）会强制同步布局重排。
# 当组件各自独立测量文本时，每次测量都会触发整个文档的重排。这种读写交错操作，
# 对 500 个文本块而言，每帧可能造成 30ms 以上的开销。
#
# 解决方案：围绕 canvas measureText 设计的两阶段测量。
#   prepare(text, font) —— 通过 Intl.Segmenter 对文本进行分词，使用 canvas 测量每个词组的宽度，
#     缓存宽度值，并在需要表情符号修正时，对每种字体执行一次缓存的 DOM 校准读取。
#     在文本首次出现时调用一次。
#   layout(prepared, maxWidth, lineHeight) —— 仅通过算术运算遍历缓存的词宽度，
#     统计行数并计算高度。在每次尺寸调整时调用。每段文本耗时约 0.0002ms。
#
# 国际化：Intl.Segmenter 处理 CJK（按字符断行）、泰文、阿拉伯文等。
#   双向文本：为混合 LTR/RTL 自定义渲染提供简化的富文本路径元数据。
#   标点合并："better." 作为一个整体测量（与 CSS 行为一致）。
#   尾随空白：悬挂在行末而不触发换行（CSS 行为）。
#   overflow-wrap：预先测量的字素宽度支持字符级断词。
#
# 表情符号修正：在 macOS 上，Chrome/Firefox 的 canvas 在字号 <24px 时测量的表情符号宽度
#   比 DOM 宽（Apple Color Emoji 字体）。对于给定字号，每个表情符号字素的膨胀系数是恒定的，
#   与字体无关。通过对比 canvas 与实际 DOM 表情符号宽度自动检测（每种字体仅一次缓存的 DOM 读取）。
#   Safari 的 canvas 与 DOM 结果一致（都宽于 fontSize），因此修正系数为零。
#
# 限制：
#   - system-ui 字体：在 macOS 上，canvas 解析出的光学变体与 DOM 不同。
#     为保证精度，请使用指定字体（Helvetica、Inter 等）。
#     参见 RESEARCH.md 中的“发现：system-ui 字体解析不匹配”。
#
# 基于 Sebastian Markbage 的文本布局研究（github.com/chenglou/text-layout）。


from .bidi import computeSegmentLevels
from .analysis import (
  analyzeText,
  canContinueKeepAllTextRun,
  clearAnalysisCaches,
  endsWithClosingQuote,
  isCJK,
  isNumericRunSegment,
  kinsokuEnd,
  kinsokuStart,
  leftStickyPunctuation,
  setAnalysisLocale,
  joinTextParts
)

from .measurement import (
  clearMeasurementCaches,
  getCorrectedSegmentWidth,
  getSegmentBreakableFitAdvances,
  getEngineProfile,
  getFontMeasurementState,
  getSegmentMetrics,
  textMayContainEmoji,
)

from .line_text import (
  buildLineTextFromRange,
  clearLineTextCaches,
  getLineTextCache,
)

from .line_break import (
  countPreparedLines,
  measurePreparedLineGeometry,
  normalizePreparedLineStart,
  stepPreparedLineGeometryFromChunk,
  walkPreparedLinesRaw,
)

from .intl_segmenter_py import Segmenter, String
import re


sharedGraphemeSegmenter: Segmenter = None


def getSharedGraphemeSegmenter() -> Segmenter:
    global sharedGraphemeSegmenter  # pylint:disable=W0603
    if sharedGraphemeSegmenter is None:
        sharedGraphemeSegmenter = Segmenter(None, {'granularity': 'grapheme'})
  
    return sharedGraphemeSegmenter


def createEmptyPrepared(includeSegments: bool):
    if includeSegments:
        return {
          'widths': [],
          'lineEndFitAdvances': [],
          'lineEndPaintAdvances': [],
          'kinds': [],
          'simpleLineWalkFastPath': True,
          'segLevels': None,
          'breakableFitAdvances': [],
          'breakablePreferredBreaks': [],
          'letterSpacing': 0,
          'spacingGraphemeCounts': [],
          'discretionaryHyphenWidth': 0,
          'tabStopAdvance': 0,
          'chunks': [],
          'segments': [],
        }
    return {
        'widths': [],
        'lineEndFitAdvances': [],
        'lineEndPaintAdvances': [],
        'kinds': [],
        'simpleLineWalkFastPath': True,
        'segLevels': None,
        'breakableFitAdvances': [],
        'breakablePreferredBreaks': [],
        'letterSpacing': 0,
        'spacingGraphemeCounts': [],
        'discretionaryHyphenWidth': 0,
        'tabStopAdvance': 0,
        'chunks': [],
    } 
    

def buildBaseCjkUnits(segText: String, engineProfile):
    units = []
    unitParts = []
    unitStart = 0
    unitContainsCJK = False
    unitEndsWithClosingQuote = False
    unitIsSingleKinsokuEnd = False

    def pushUnit():
        nonlocal unitParts, unitStart, unitContainsCJK, unitEndsWithClosingQuote, unitIsSingleKinsokuEnd
        if len(unitParts) == 0: return
        units.append({
          'text': joinTextParts(unitParts),
          'start': unitStart,
        })
        unitParts = []
        unitContainsCJK = False
        unitEndsWithClosingQuote = False
        unitIsSingleKinsokuEnd = False

    def startUnit(grapheme: String, start, graphemeContainsCJK: bool):
        nonlocal unitParts, unitStart, unitContainsCJK, unitEndsWithClosingQuote, unitIsSingleKinsokuEnd
        unitParts = [grapheme]
        unitStart = start
        unitContainsCJK = graphemeContainsCJK
        unitEndsWithClosingQuote = endsWithClosingQuote(grapheme)
        unitIsSingleKinsokuEnd = str(grapheme) in kinsokuEnd

    def appendToUnit(grapheme: String, graphemeContainsCJK: bool):
        nonlocal unitParts, unitStart, unitContainsCJK, unitEndsWithClosingQuote, unitIsSingleKinsokuEnd
        unitParts.append(grapheme)
        unitContainsCJK = unitContainsCJK or graphemeContainsCJK
        graphemeEndsWithClosingQuote = endsWithClosingQuote(grapheme)
        if grapheme.length == 1 and str(grapheme) in leftStickyPunctuation:
            unitEndsWithClosingQuote = unitEndsWithClosingQuote or graphemeEndsWithClosingQuote
        else:
            unitEndsWithClosingQuote = graphemeEndsWithClosingQuote
        unitIsSingleKinsokuEnd = False

    for gs in getSharedGraphemeSegmenter().segment(segText):
        grapheme = gs['segment']
        graphemeContainsCJK = isCJK(grapheme)
    
        if len(unitParts) == 0:
            startUnit(grapheme, gs['index'], graphemeContainsCJK)
            continue
    
        if (
          unitIsSingleKinsokuEnd or \
          str(grapheme) in kinsokuStart or \
          str(grapheme) in leftStickyPunctuation or \
          (engineProfile['carryCJKAfterClosingQuote'] and \
            graphemeContainsCJK and unitEndsWithClosingQuote)
        ):
            appendToUnit(grapheme, graphemeContainsCJK)
            continue
    
        if not unitContainsCJK and not graphemeContainsCJK:
            appendToUnit(grapheme, graphemeContainsCJK)
            continue
    
        pushUnit()
        startUnit(grapheme, gs['index'], graphemeContainsCJK)

    pushUnit()
    return units


def mergeKeepAllTextUnits(
  segText: String,
  units,
  breakAfterPunctuation: bool,
):
    if len(units) <= 1: return units

    merged = []
    groupStart = -1
    groupContainsCJK = False

    def pushMergedUnit(start: int, end: int):
        sourceStart = units[start]['start']
        sourceEnd = units[end]['start'] if end < len(units) else segText.length
    
        merged.append({
          'text': segText.slice(sourceStart, sourceEnd),
          'start': sourceStart,
        })

    def flushGroup(end: int):
        nonlocal groupStart, groupContainsCJK
        if groupStart < 0: return
    
        if groupContainsCJK:
            if groupStart + 1 == end:
                merged.append(units[groupStart])
            else:
                pushMergedUnit(groupStart, end)
        else:
          for i in range(groupStart, end): merged.append(units[i])
    
        groupStart = -1
        groupContainsCJK = False

    for i in range(len(units)):
        unit = units[i]
        if (
          groupStart >= 0 and \
          not canContinueKeepAllTextRun(units[i - 1]['text'], breakAfterPunctuation)
        ):
            flushGroup(i)
        if groupStart < 0: groupStart = i
        groupContainsCJK = groupContainsCJK or isCJK(unit['text'])

    flushGroup(len(units))
    return merged


def countRenderedSpacingGraphemes(text: String, kind):
    if (
      kind == 'zero-width-break' or \
      kind == 'soft-hyphen' or \
      kind == 'hard-break'
    ):
        return 0

    if kind == 'tab': return 1

    count = 0
    for _ in getSharedGraphemeSegmenter().segment(text):
        count += 1
    return count
    

def isPreferredBreakGrapheme(grapheme: str) -> bool:
  return (
    grapheme == '-' or \
    grapheme == '\u058A' or \
    grapheme == '\u2010' or \
    grapheme == '\u2012' or \
    grapheme == '\u2013' or \
    grapheme == '\u2014'
  )


def getBreakablePreferredBreaks(text: String):
    if not re.search(r'[-\u058A\u2010\u2012\u2013\u2014]', str(text)): return None
  
    breaks = []
    graphemeIndex = 0
    for gs in getSharedGraphemeSegmenter().segment(text):
        graphemeIndex += 1
        if isPreferredBreakGrapheme(str(gs['segment'])): breaks.append(graphemeIndex)

    return None if len(breaks) == 0 else breaks


def addInternalLetterSpacing(width, graphemeCount: int, letterSpacing: int):
    return width + (graphemeCount - 1) * letterSpacing if graphemeCount > 1 else width


def measureAnalysis(
  analysis,
  font: str,
  includeSegments: bool,
  wordBreak: str,
  letterSpacing: int,
):
    engineProfile = getEngineProfile()
    _res = getFontMeasurementState(
      font,
      textMayContainEmoji(analysis['normalized']),
    )
    cache, emojiCorrection = _res['cache'], _res['emojiCorrection']
    discretionaryHyphenWidth = \
        getCorrectedSegmentWidth(String('-'), getSegmentMetrics('-', cache), emojiCorrection) + \
        (0 if letterSpacing == 0 else letterSpacing * 2)
    spaceWidth = getCorrectedSegmentWidth(String(' '), getSegmentMetrics(' ', cache), emojiCorrection)
    tabStopAdvance = spaceWidth * 8
    hasLetterSpacing = letterSpacing != 0

    if analysis['len'] == 0: return createEmptyPrepared(includeSegments)

    widths = []
    lineEndFitAdvances = []
    lineEndPaintAdvances = []
    kinds = []
    simpleLineWalkFastPath = not hasLetterSpacing
    segStarts = [] if includeSegments else None
    breakableFitAdvances = []
    breakablePreferredBreaks = []
    spacingGraphemeCounts = []
    segments = [] if includeSegments else None
    chunks = []
    chunkStartSegmentIndex = 0

    def pushMeasuredSegment(
      text: String,
      width,
      lineEndFitAdvance,
      lineEndPaintAdvance,
      kind,
      start,
      breakableFitAdvance,
      breakablePreferredBreak,
      spacingGraphemeCount,
    ):
        nonlocal simpleLineWalkFastPath
        if kind != 'text' and kind != 'space' and kind != 'zero-width-break':
            simpleLineWalkFastPath = False
        widths.append(width)
        lineEndFitAdvances.append(lineEndFitAdvance)
        lineEndPaintAdvances.append(lineEndPaintAdvance)
        kinds.append(kind)
        if segStarts is not None: segStarts.append(start)
        breakableFitAdvances.append(breakableFitAdvance)
        breakablePreferredBreaks.append(breakablePreferredBreak)
        if hasLetterSpacing: spacingGraphemeCounts.append(spacingGraphemeCount)
        if segments is not None: segments.append(text)

    def pushMeasuredTextSegment(
      text: String,
      textMetrics,
      kind,
      start,
      wordLike: bool,
      allowOverflowBreaks: bool,
    ):
        spacingGraphemeCount = countRenderedSpacingGraphemes(text, kind) if hasLetterSpacing else 0
       
        width = addInternalLetterSpacing(
          getCorrectedSegmentWidth(text, textMetrics, emojiCorrection),
          spacingGraphemeCount,
          letterSpacing,
        )
        baseLineEndFitAdvance = 0 if kind == 'space' or kind == 'preserved-space' or kind == 'zero-width-break' else width
        lineEndFitAdvance = 0 if baseLineEndFitAdvance == 0 else baseLineEndFitAdvance + (letterSpacing if spacingGraphemeCount > 0 else 0)
        lineEndPaintAdvance = 0 if kind == 'space' or kind == 'zero-width-break' else width
    
        if allowOverflowBreaks and wordLike and text.length > 1:
            fitMode = 'sum-graphemes'
            if letterSpacing != 0:
                fitMode = 'segment-prefixes'
            elif isNumericRunSegment(text):
                fitMode = 'pair-context'
            elif engineProfile['preferPrefixWidthsForBreakableRuns']:
                fitMode = 'segment-prefixes'
          
            fitAdvances = getSegmentBreakableFitAdvances(
                text,
                textMetrics,
                cache,
                emojiCorrection,
                fitMode,
            )
            preferredBreaks = None if fitAdvances is None or wordBreak == 'keep-all' else getBreakablePreferredBreaks(text)
            pushMeasuredSegment(
                text,
                width,
                lineEndFitAdvance,
                lineEndPaintAdvance,
                kind,
                start,
                fitAdvances,
                preferredBreaks,
                spacingGraphemeCount,
            )
            return

        pushMeasuredSegment(
          text,
          width,
          lineEndFitAdvance,
          lineEndPaintAdvance,
          kind,
          start,
          None,
          None,
          spacingGraphemeCount,
        )

    for mi in range(analysis['len']):
        segText = analysis['texts'][mi]
        segWordLike = analysis['isWordLike'][mi]
        segKind = analysis['kinds'][mi]
        segStart = analysis['starts'][mi]
    
        if segKind == 'soft-hyphen':
            pushMeasuredSegment(
                segText,
                0,
                discretionaryHyphenWidth,
                discretionaryHyphenWidth,
                segKind,
                segStart,
                None,
                None,
                0,
            )
            continue
    
        if segKind == 'hard-break':
            endSegmentIndex = len(widths)
            pushMeasuredSegment(segText, 0, 0, 0, segKind, segStart, None, None, 0)
            chunks.append({
                'startSegmentIndex': chunkStartSegmentIndex,
                'endSegmentIndex': endSegmentIndex,
                'consumedEndSegmentIndex': len(widths),
            })
            chunkStartSegmentIndex = len(widths)
            continue
    
        if segKind == 'tab':
            pushMeasuredSegment(
                segText,
                0,
                0,
                0,
                segKind,
                segStart,
                None,
                None,
                countRenderedSpacingGraphemes(segText, segKind) if hasLetterSpacing else 0,
            )
            continue
    
        segMetrics = getSegmentMetrics(str(segText), cache)
        # print('segText:', segText, 'containsCJK:', segMetrics['containsCJK'])
        if segKind == 'text' and segMetrics['containsCJK']:
            baseUnits = buildBaseCjkUnits(segText, engineProfile)
            measuredUnits =  mergeKeepAllTextUnits(segText, baseUnits, engineProfile['breakKeepAllAfterPunctuation']) if wordBreak == 'keep-all' else baseUnits
    
            for i in range(len(measuredUnits)):
                unit = measuredUnits[i]
                unitMetrics = getSegmentMetrics(str(unit['text']), cache)
                pushMeasuredTextSegment(
                  unit['text'],
                  unitMetrics,
                  'text',
                  segStart + unit['start'],
                  segWordLike,
                  wordBreak == 'keep-all' or not unitMetrics['containsCJK'],
                )
            continue
        
    
        pushMeasuredTextSegment(segText, segMetrics, segKind, segStart, segWordLike, True)


    if chunkStartSegmentIndex < len(widths):
        chunks.append({
          'startSegmentIndex': chunkStartSegmentIndex,
          'endSegmentIndex': len(widths),
          'consumedEndSegmentIndex': len(widths),
        })
    segLevels = None if segStarts is None else computeSegmentLevels(analysis['normalized'], segStarts)
    if segments is not None:
        return {
            "widths": widths,
            "lineEndFitAdvances": lineEndFitAdvances,
            "lineEndPaintAdvances": lineEndPaintAdvances,
            "kinds": kinds,
            "simpleLineWalkFastPath": simpleLineWalkFastPath,
            "segLevels": segLevels,
            "breakableFitAdvances": breakableFitAdvances,
            "breakablePreferredBreaks": breakablePreferredBreaks,
            "letterSpacing": letterSpacing,
            "spacingGraphemeCounts": spacingGraphemeCounts,
            "discretionaryHyphenWidth": discretionaryHyphenWidth,
            "tabStopAdvance": tabStopAdvance,
            "chunks": chunks,
            "segments": segments,
        }
    return {
        "widths": widths,
        "lineEndFitAdvances": lineEndFitAdvances,
        "lineEndPaintAdvances": lineEndPaintAdvances,
        "kinds": kinds,
        "simpleLineWalkFastPath": simpleLineWalkFastPath,
        "segLevels": segLevels,
        "breakableFitAdvances": breakableFitAdvances,
        "breakablePreferredBreaks": breakablePreferredBreaks,
        "letterSpacing": letterSpacing,
        "spacingGraphemeCounts": spacingGraphemeCounts,
        "discretionaryHyphenWidth": discretionaryHyphenWidth,
        "tabStopAdvance": tabStopAdvance,
        "chunks": chunks,
    }
    

def prepareInternal(
    text: String,
    font: str,
    includeSegments: bool,
    options = None,
):
    options = options or {}
    wordBreak = options.get('wordBreak', 'normal')
    letterSpacing = options.get('letterSpacing', 0)
    analysis = analyzeText(text, getEngineProfile(), options.get('whiteSpace', None), wordBreak)
    return measureAnalysis(analysis, font, includeSegments, wordBreak, letterSpacing)


# Prepare text for layout. Segments the text, measures each segment via canvas,
# and stores the widths for fast relayout at any width. Call once per text block
# (e.g. when a comment first appears). The result is width-independent — the
# same PreparedText can be laid out at any maxWidth and lineHeight via layout().
#
# Steps:
#   1. Normalize collapsible whitespace (CSS white-space: normal behavior)
#   2. Segment via Intl.Segmenter (handles CJK, Thai, etc.)
#   3. Merge punctuation into preceding word ("better." as one unit)
#   4. Split CJK words into individual graphemes (per-character line breaks)
#   5. Measure each segment via canvas measureText, cache by (segment, font)
#   6. Pre-measure graphemes of long words (for overflow-wrap: break-word)
#   7. Correct emoji canvas inflation (auto-detected per font size)
#   8. Optionally compute rich-path bidi metadata for custom renderers
def prepare(text, font: str, options = None):
    text = String(text)
    return prepareInternal(text, font, False, options)


# Rich variant used by callers that need enough information to render the
# laid-out lines themselves.
def prepareWithSegments(text, font: str, options = None):
    text = String(text)
    return prepareInternal(text, font, True, options)


# Layout prepared text at a given max width and caller-provided lineHeight.
# Pure arithmetic on cached widths — no canvas calls, no DOM reads, no string
# operations, no allocations.
# ~0.0002ms per text block. Call on every resize.
#
# Line breaking rules (matching CSS white-space: normal + overflow-wrap: break-word):
#   - Break before any non-space segment that would overflow the line
#   - Trailing whitespace hangs past the line edge (doesn't trigger breaks)
#   - Segments wider than maxWidth are broken at grapheme boundaries
def layout(prepared, maxWidth, lineHeight):
    # Keep the resize hot path specialized. `layoutWithLines()` shares the same
    # break semantics but also tracks line ranges; the extra bookkeeping is too
    # expensive to pay on every hot-path `layout()` call.
    lineCount = countPreparedLines(prepared, maxWidth)
    return {'lineCount': lineCount, 'height': lineCount * lineHeight }


def createLayoutLine(prepared, cache, width, startSegmentIndex, startGraphemeIndex, endSegmentIndex, endGraphemeIndex):
    return {
        'text': buildLineTextFromRange(
            prepared,
            cache,
            startSegmentIndex,
            startGraphemeIndex,
            endSegmentIndex,
            endGraphemeIndex,
        ),
        'width': width,
        'start': {
            'segmentIndex': startSegmentIndex,
            'graphemeIndex': startGraphemeIndex,
        },
        'end': {
            'segmentIndex': endSegmentIndex,
            'graphemeIndex': endGraphemeIndex,
        },
    }


def createLayoutLineRange(width, startSegmentIndex, startGraphemeIndex, endSegmentIndex, endGraphemeIndex):
    return {
        'width': width,
        'start': {
            'segmentIndex': startSegmentIndex,
            'graphemeIndex': startGraphemeIndex,
        },
        'end': {
            'segmentIndex': endSegmentIndex,
            'graphemeIndex': endGraphemeIndex,
        },
    }


def materializeLineRange(prepared, line):
    return createLayoutLine(
        prepared,
        getLineTextCache(prepared),
        line['width'],
        line['start']['segmentIndex'],
        line['start']['graphemeIndex'],
        line['end']['segmentIndex'],
        line['end']['graphemeIndex'],
    )


# Batch low-level line-range pass. This is the non-materializing counterpart
# to layoutWithLines(), useful for shrinkwrap and other aggregate stats work.
def walkLineRanges(prepared, maxWidth, onLine):
    if len(prepared['widths']) == 0:
        return 0

    def line_callback(width, startSegmentIndex, startGraphemeIndex, endSegmentIndex, endGraphemeIndex):
        onLine(createLayoutLineRange(
            width,
            startSegmentIndex,
            startGraphemeIndex,
            endSegmentIndex,
            endGraphemeIndex,
        ))

    return walkPreparedLinesRaw(prepared, maxWidth, line_callback)


def measureLineStats(prepared, maxWidth):
    return measurePreparedLineGeometry(prepared, maxWidth)


# Intrinsic-width helper for rich/userland layout work. This asks "how wide is
# the prepared text when container width is not the thing forcing wraps?".
# Explicit hard breaks still count, so this returns the widest forced line.
def measureNaturalWidth(prepared):
    maxWidth = 0
    def callback(width, *args):
        nonlocal maxWidth
        if width > maxWidth:
            maxWidth = width
    walkPreparedLinesRaw(prepared, float('inf'), callback)
    return maxWidth


def layoutNextLine(prepared, start, maxWidth):
    internal = prepared
    end = {
        'segmentIndex': start['segmentIndex'],
        'graphemeIndex': start['graphemeIndex'],
    }
    chunkIndex = normalizePreparedLineStart(internal, end)
    if chunkIndex < 0:
        return None

    lineStartSegmentIndex = end['segmentIndex']
    lineStartGraphemeIndex = end['graphemeIndex']
    width = stepPreparedLineGeometryFromChunk(internal, end, chunkIndex, maxWidth)
    if width is None:
        return None

    return createLayoutLine(
        prepared,
        getLineTextCache(prepared),
        width,
        lineStartSegmentIndex,
        lineStartGraphemeIndex,
        end['segmentIndex'],
        end['graphemeIndex'],
    )


def layoutNextLineRange(prepared, start, maxWidth):
    internal = prepared
    end = {
        'segmentIndex': start['segmentIndex'],
        'graphemeIndex': start['graphemeIndex'],
    }
    chunkIndex = normalizePreparedLineStart(internal, end)
    if chunkIndex < 0:
        return None

    lineStartSegmentIndex = end['segmentIndex']
    lineStartGraphemeIndex = end['graphemeIndex']
    width = stepPreparedLineGeometryFromChunk(internal, end, chunkIndex, maxWidth)
    if width is None:
        return None

    return createLayoutLineRange(
        width,
        lineStartSegmentIndex,
        lineStartGraphemeIndex,
        end['segmentIndex'],
        end['graphemeIndex'],
    )

# Rich layout API for callers that want the actual line contents and widths.
# Caller still supplies lineHeight at layout time. Mirrors layout()'s break
# decisions, but keeps extra per-line bookkeeping so it should stay off the
# resize hot path.
def layoutWithLines(prepared, maxWidth, lineHeight):
    lines = []
    if len(prepared['widths']) == 0:
        return {'lineCount': 0, 'height': 0, 'lines': lines}

    graphemeCache = getLineTextCache(prepared)

    def line_callback(width, startSegmentIndex, startGraphemeIndex, endSegmentIndex, endGraphemeIndex):
        lines.append(createLayoutLine(
            prepared,
            graphemeCache,
            width,
            startSegmentIndex,
            startGraphemeIndex,
            endSegmentIndex,
            endGraphemeIndex,
        ))

    lineCount = walkPreparedLinesRaw(prepared, maxWidth, line_callback)

    return {'lineCount': lineCount, 'height': lineCount * lineHeight, 'lines': lines}


def clearCache():
    global sharedGraphemeSegmenter  # pylint:disable=W0603
    clearAnalysisCaches()
    sharedGraphemeSegmenter = None
    clearLineTextCaches()
    clearMeasurementCaches()


def setLocale(locale: str = None):
    setAnalysisLocale(locale)
    clearCache()

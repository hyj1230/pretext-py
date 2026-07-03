from .measurement import getEngineProfile
import math


def consumesAtLineStart(kind) -> bool:
    return kind == 'space' or kind == 'zero-width-break' or kind == 'soft-hyphen'


def breaksAfter(kind) -> bool:
    return (
        kind == 'space' or \
        kind == 'preserved-space' or \
        kind == 'tab' or \
        kind == 'zero-width-break' or \
        kind == 'soft-hyphen'
    )


def normalizeLineStartSegmentIndex(
    prepared,
    segmentIndex: int,
    endSegmentIndex = None,
):
    if endSegmentIndex is None: endSegmentIndex = len(prepared['widths'])
    while segmentIndex < endSegmentIndex:
        kind = prepared['kinds'][segmentIndex]
        if not consumesAtLineStart(kind): break
        segmentIndex += 1

    return segmentIndex


def getTabAdvance(lineWidth, tabStopAdvance):
    if tabStopAdvance <= 0: return 0

    remainder = lineWidth % tabStopAdvance
    if abs(remainder) <= 1e-6: return tabStopAdvance
    return tabStopAdvance - remainder


def getLeadingLetterSpacing(
  prepared,
  hasContent: bool,
  segmentIndex: int,
):
    return prepared['letterSpacing'] if (
      prepared['letterSpacing'] != 0 and \
      hasContent and \
      prepared['spacingGraphemeCounts'][segmentIndex] > 0
    ) else 0


def getLineEndContribution(leadingSpacing, segmentContribution):
    return 0 if segmentContribution == 0 else leadingSpacing + segmentContribution


def getTabTrailingLetterSpacing(
  prepared,
  segmentIndex: int,
):
    return prepared['letterSpacing'] if (
      prepared['letterSpacing'] != 0 and \
      prepared['spacingGraphemeCounts'][segmentIndex] > 0
    ) else 0


def getWholeSegmentFitContribution(
  prepared,
  kind: str,
  segmentIndex: int,
  leadingSpacing,
  segmentWidth,
):
    segmentContribution = (segmentWidth + getTabTrailingLetterSpacing(prepared, segmentIndex)) if kind == 'tab' else prepared['lineEndFitAdvances'][segmentIndex]
    return getLineEndContribution(leadingSpacing, segmentContribution)


def getBreakOpportunityFitContribution(
  prepared,
  kind: str,
  segmentIndex: int,
  leadingSpacing,
):
    segmentContribution = 0 if kind == 'tab' else prepared['lineEndFitAdvances'][segmentIndex]
    return getLineEndContribution(leadingSpacing, segmentContribution)


def getLineEndPaintContribution(
  prepared,
  kind: str,
  segmentIndex: int,
  leadingSpacing,
  segmentWidth,
):
    segmentContribution = segmentWidth if kind == 'tab' else prepared['lineEndPaintAdvances'][segmentIndex]
    return getLineEndContribution(leadingSpacing, segmentContribution)


def getBreakableGraphemeAdvance(
  prepared,
  hasContent: bool,
  baseAdvance,
):
    return baseAdvance + prepared['letterSpacing'] if prepared['letterSpacing'] != 0 and hasContent else baseAdvance


def getBreakableCandidateFitWidth(
  prepared,
  candidatePaintWidth,
):
    return candidatePaintWidth if prepared['letterSpacing'] == 0 else candidatePaintWidth + prepared['letterSpacing']


def getNextPreferredBreakIndex(
  preferredBreaks,
  preferredBreakIndex: int,
  graphemeEnd,
):
    index = preferredBreakIndex
    while index < len(preferredBreaks) and preferredBreaks[index] < graphemeEnd:
        index += 1
    return index


def getTerminalLetterSpacing(prepared, startSegmentIndex, startGraphemeIndex, endSegmentIndex, endGraphemeIndex):
    if prepared['letterSpacing'] == 0:
        return 0

    if endGraphemeIndex > 0:
        return prepared['letterSpacing'] if prepared['spacingGraphemeCounts'][endSegmentIndex] > 0 else 0

    for i in range(endSegmentIndex - 1, startSegmentIndex - 1, -1):
        kind = prepared['kinds'][i]
        if kind in ('space', 'zero-width-break', 'hard-break'):
            continue
        if kind == 'soft-hyphen':
            if i == endSegmentIndex - 1:
                return 0
            continue

        if i == startSegmentIndex and startGraphemeIndex > 0:
            return prepared['letterSpacing']

        return prepared['letterSpacing'] if prepared['spacingGraphemeCounts'][i] > 0 else 0

    return 0

def finalizeLinePaintWidth(
  prepared,
  width,
  startSegmentIndex,
  startGraphemeIndex,
  endSegmentIndex,
  endGraphemeIndex,
):
    return width + getTerminalLetterSpacing(
      prepared,
      startSegmentIndex,
      startGraphemeIndex,
      endSegmentIndex,
      endGraphemeIndex,
    )


def findChunkIndexForStart(prepared, segmentIndex):
    lo = 0
    hi = len(prepared['chunks'])

    while lo < hi:
        mid = int(math.floor((lo + hi) / 2))
        if segmentIndex < prepared['chunks'][mid]['consumedEndSegmentIndex']:
            hi = mid
        else:
            lo = mid + 1

    return lo if lo < len(prepared['chunks']) else -1


def normalizeLineStartInChunk(prepared, chunkIndex, cursor):
    segmentIndex = cursor['segmentIndex']
    if cursor['graphemeIndex'] > 0:
        return chunkIndex

    chunk = prepared['chunks'][chunkIndex]
    if chunk['startSegmentIndex'] == chunk['endSegmentIndex'] and segmentIndex == chunk['startSegmentIndex']:
        cursor['segmentIndex'] = segmentIndex
        cursor['graphemeIndex'] = 0
        return chunkIndex

    if segmentIndex < chunk['startSegmentIndex']:
        segmentIndex = chunk['startSegmentIndex']
    segmentIndex = normalizeLineStartSegmentIndex(prepared, segmentIndex, chunk['endSegmentIndex'])
    if segmentIndex < chunk['endSegmentIndex']:
        cursor['segmentIndex'] = segmentIndex
        cursor['graphemeIndex'] = 0
        return chunkIndex

    if chunk['consumedEndSegmentIndex'] >= len(prepared['widths']):
        return -1
    cursor['segmentIndex'] = chunk['consumedEndSegmentIndex']
    cursor['graphemeIndex'] = 0
    return chunkIndex + 1


# Mutates `cursor` to the next renderable line start and returns its chunk index.
def normalizePreparedLineStart(prepared, cursor):
    if cursor['segmentIndex'] >= len(prepared['widths']):
        return -1

    chunkIndex = findChunkIndexForStart(prepared, cursor['segmentIndex'])
    if chunkIndex < 0:
        return -1
    return normalizeLineStartInChunk(prepared, chunkIndex, cursor)


def normalizeLineStartChunkIndexFromHint(prepared, chunkIndex, cursor):
    if cursor['segmentIndex'] >= len(prepared['widths']):
        return -1

    nextChunkIndex = chunkIndex
    while (
        nextChunkIndex < len(prepared['chunks']) and
        cursor['segmentIndex'] >= prepared['chunks'][nextChunkIndex]['consumedEndSegmentIndex']
    ):
        nextChunkIndex += 1
    if nextChunkIndex >= len(prepared['chunks']):
        return -1
    return normalizeLineStartInChunk(prepared, nextChunkIndex, cursor)


def countPreparedLines(prepared, maxWidth):
    return walkPreparedLinesRaw(prepared, maxWidth)


def walkPreparedLinesSimple(prepared, maxWidth, onLine=None):
    widths = prepared['widths']
    kinds = prepared['kinds']
    breakableFitAdvances = prepared['breakableFitAdvances']
    breakablePreferredBreaks = prepared['breakablePreferredBreaks']

    if len(widths) == 0:
        return 0

    engineProfile = getEngineProfile()
    lineFitEpsilon = engineProfile['lineFitEpsilon']
    fitLimit = maxWidth + lineFitEpsilon

    lineCount = 0
    lineW = 0
    hasContent = False
    lineStartSegmentIndex = 0
    lineStartGraphemeIndex = 0
    lineEndSegmentIndex = 0
    lineEndGraphemeIndex = 0
    pendingBreakSegmentIndex = -1
    pendingBreakPaintWidth = 0

    def clearPendingBreak():
        nonlocal pendingBreakSegmentIndex, pendingBreakPaintWidth
        pendingBreakSegmentIndex = -1
        pendingBreakPaintWidth = 0

    def emitCurrentLine(endSegmentIndex=None, endGraphemeIndex=None, width=None):
        nonlocal lineCount, lineW, hasContent, lineStartSegmentIndex, lineStartGraphemeIndex
        nonlocal lineEndSegmentIndex, lineEndGraphemeIndex, pendingBreakSegmentIndex, pendingBreakPaintWidth
        if endSegmentIndex is None:
            endSegmentIndex = lineEndSegmentIndex
        if endGraphemeIndex is None:
            endGraphemeIndex = lineEndGraphemeIndex
        if width is None:
            width = lineW
        lineCount += 1
        if onLine is not None:
            onLine(
                width,
                lineStartSegmentIndex,
                lineStartGraphemeIndex,
                endSegmentIndex,
                endGraphemeIndex,
            )
        lineW = 0
        hasContent = False
        clearPendingBreak()

    def startLineAtSegment(segmentIndex, width):
        nonlocal hasContent, lineStartSegmentIndex, lineStartGraphemeIndex
        nonlocal lineEndSegmentIndex, lineEndGraphemeIndex, lineW
        hasContent = True
        lineStartSegmentIndex = segmentIndex
        lineStartGraphemeIndex = 0
        lineEndSegmentIndex = segmentIndex + 1
        lineEndGraphemeIndex = 0
        lineW = width

    def startLineAtGrapheme(segmentIndex, graphemeIndex, width):
        nonlocal hasContent, lineStartSegmentIndex, lineStartGraphemeIndex
        nonlocal lineEndSegmentIndex, lineEndGraphemeIndex, lineW
        hasContent = True
        lineStartSegmentIndex = segmentIndex
        lineStartGraphemeIndex = graphemeIndex
        lineEndSegmentIndex = segmentIndex
        lineEndGraphemeIndex = graphemeIndex + 1
        lineW = width

    def appendWholeSegment(segmentIndex, width):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        if not hasContent:
            startLineAtSegment(segmentIndex, width)
            return
        lineW += width
        lineEndSegmentIndex = segmentIndex + 1
        lineEndGraphemeIndex = 0

    def appendBreakableSegmentFrom(segmentIndex, startGraphemeIndex):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        nonlocal pendingBreakSegmentIndex, pendingBreakPaintWidth, lineCount
        fitAdvances = breakableFitAdvances[segmentIndex]
        preferredBreaks = breakablePreferredBreaks[segmentIndex] if segmentIndex < len(breakablePreferredBreaks) else None
        preferredBreakIndex = -1 if preferredBreaks is None else getNextPreferredBreakIndex(preferredBreaks, 0, startGraphemeIndex + 1)
        lastPreferredBreakEnd = -1
        lastPreferredBreakWidth = 0

        g = startGraphemeIndex
        while g < len(fitAdvances):
            gw = fitAdvances[g]

            if not hasContent:
                startLineAtGrapheme(segmentIndex, g, gw)
            elif lineW + gw > fitLimit:
                if preferredBreaks is not None and lastPreferredBreakEnd > startGraphemeIndex:
                    emitCurrentLine(segmentIndex, lastPreferredBreakEnd, lastPreferredBreakWidth)
                    g = lastPreferredBreakEnd
                    preferredBreakIndex = getNextPreferredBreakIndex(preferredBreaks, preferredBreakIndex, g + 1)
                    lastPreferredBreakEnd = -1
                    lastPreferredBreakWidth = 0
                    continue
                emitCurrentLine()
                startLineAtGrapheme(segmentIndex, g, gw)
            else:
                lineW += gw
                lineEndSegmentIndex = segmentIndex
                lineEndGraphemeIndex = g + 1

            graphemeEnd = g + 1
            if preferredBreaks is not None and preferredBreakIndex < len(preferredBreaks) and preferredBreaks[preferredBreakIndex] == graphemeEnd:
                lastPreferredBreakEnd = graphemeEnd
                lastPreferredBreakWidth = lineW
                preferredBreakIndex += 1
            g += 1

        if hasContent and lineEndSegmentIndex == segmentIndex and lineEndGraphemeIndex == len(fitAdvances):
            lineEndSegmentIndex = segmentIndex + 1
            lineEndGraphemeIndex = 0

    i = 0
    while i < len(widths):
        if not hasContent:
            i = normalizeLineStartSegmentIndex(prepared, i)
            if i >= len(widths):
                break

        w = widths[i]
        kind = kinds[i]
        breakAfter = breaksAfter(kind)

        if not hasContent:
            if w > fitLimit and breakableFitAdvances[i] is not None:
                appendBreakableSegmentFrom(i, 0)
            else:
                startLineAtSegment(i, w)
            if breakAfter:
                pendingBreakSegmentIndex = i + 1
                pendingBreakPaintWidth = lineW - w
            i += 1
            continue

        newW = lineW + w
        if newW > fitLimit:
            if breakAfter:
                appendWholeSegment(i, w)
                emitCurrentLine(i + 1, 0, lineW - w)
                i += 1
                continue

            if pendingBreakSegmentIndex >= 0:
                if (lineEndSegmentIndex > pendingBreakSegmentIndex or
                    (lineEndSegmentIndex == pendingBreakSegmentIndex and lineEndGraphemeIndex > 0)):
                    emitCurrentLine()
                    continue
                emitCurrentLine(pendingBreakSegmentIndex, 0, pendingBreakPaintWidth)
                continue

            if w > fitLimit and breakableFitAdvances[i] is not None:
                emitCurrentLine()
                appendBreakableSegmentFrom(i, 0)
                i += 1
                continue

            emitCurrentLine()
            continue

        appendWholeSegment(i, w)
        if breakAfter:
            pendingBreakSegmentIndex = i + 1
            pendingBreakPaintWidth = lineW - w
        i += 1

    if hasContent:
        emitCurrentLine()
    return lineCount


def walkPreparedLinesRaw(prepared, maxWidth, onLine=None):
    if prepared['simpleLineWalkFastPath']:
        return walkPreparedLinesSimple(prepared, maxWidth, onLine)

    widths = prepared['widths']
    kinds = prepared['kinds']
    breakableFitAdvances = prepared['breakableFitAdvances']
    breakablePreferredBreaks = prepared['breakablePreferredBreaks']
    discretionaryHyphenWidth = prepared['discretionaryHyphenWidth']
    chunks = prepared['chunks']

    if len(widths) == 0 or len(chunks) == 0:
        return 0

    engineProfile = getEngineProfile()
    lineFitEpsilon = engineProfile['lineFitEpsilon']
    fitLimit = maxWidth + lineFitEpsilon

    lineCount = 0
    lineW = 0
    hasContent = False
    lineStartSegmentIndex = 0
    lineStartGraphemeIndex = 0
    lineEndSegmentIndex = 0
    lineEndGraphemeIndex = 0
    pendingBreakSegmentIndex = -1
    pendingBreakFitWidth = 0
    pendingBreakPaintWidth = 0
    pendingBreakKind = None

    def clearPendingBreak():
        nonlocal pendingBreakSegmentIndex, pendingBreakFitWidth, pendingBreakPaintWidth, pendingBreakKind
        pendingBreakSegmentIndex = -1
        pendingBreakFitWidth = 0
        pendingBreakPaintWidth = 0
        pendingBreakKind = None

    def getCurrentLinePaintWidth():
        if (pendingBreakKind == 'soft-hyphen' and
            pendingBreakSegmentIndex == lineEndSegmentIndex and
            lineEndGraphemeIndex == 0):
            return pendingBreakPaintWidth
        return lineW

    def emitCurrentLine(endSegmentIndex=None, endGraphemeIndex=None, width=None):
        nonlocal lineCount, lineW, hasContent, lineStartSegmentIndex, lineStartGraphemeIndex
        nonlocal lineEndSegmentIndex, lineEndGraphemeIndex, pendingBreakSegmentIndex, pendingBreakFitWidth, pendingBreakPaintWidth, pendingBreakKind
        if endSegmentIndex is None:
            endSegmentIndex = lineEndSegmentIndex
        if endGraphemeIndex is None:
            endGraphemeIndex = lineEndGraphemeIndex
        if width is None:
            width = getCurrentLinePaintWidth()
        lineCount += 1
        if onLine is not None:
            onLine(
                finalizeLinePaintWidth(
                    prepared, width,
                    lineStartSegmentIndex, lineStartGraphemeIndex,
                    endSegmentIndex, endGraphemeIndex
                ),
                lineStartSegmentIndex, lineStartGraphemeIndex,
                endSegmentIndex, endGraphemeIndex
            )
        lineW = 0
        hasContent = False
        clearPendingBreak()

    def startLineAtSegment(segmentIndex, width):
        nonlocal hasContent, lineStartSegmentIndex, lineStartGraphemeIndex
        nonlocal lineEndSegmentIndex, lineEndGraphemeIndex, lineW
        hasContent = True
        lineStartSegmentIndex = segmentIndex
        lineStartGraphemeIndex = 0
        lineEndSegmentIndex = segmentIndex + 1
        lineEndGraphemeIndex = 0
        lineW = width

    def startLineAtGrapheme(segmentIndex, graphemeIndex, width):
        nonlocal hasContent, lineStartSegmentIndex, lineStartGraphemeIndex
        nonlocal lineEndSegmentIndex, lineEndGraphemeIndex, lineW
        hasContent = True
        lineStartSegmentIndex = segmentIndex
        lineStartGraphemeIndex = graphemeIndex
        lineEndSegmentIndex = segmentIndex
        lineEndGraphemeIndex = graphemeIndex + 1
        lineW = width

    def appendWholeSegment(segmentIndex, advance):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        if not hasContent:
            startLineAtSegment(segmentIndex, advance)
            return
        lineW += advance
        lineEndSegmentIndex = segmentIndex + 1
        lineEndGraphemeIndex = 0

    def updatePendingBreakForWholeSegment(kind: str, breakAfter: bool, segmentIndex, segmentWidth, leadingSpacing, advance):
        if not breakAfter:
            return
        nonlocal pendingBreakSegmentIndex, pendingBreakFitWidth, pendingBreakPaintWidth, pendingBreakKind
        fitAdvance = getBreakOpportunityFitContribution(prepared, kind, segmentIndex, leadingSpacing)
        paintAdvance = getLineEndPaintContribution(prepared, kind, segmentIndex, leadingSpacing, segmentWidth)
        pendingBreakSegmentIndex = segmentIndex + 1
        pendingBreakFitWidth = lineW - advance + fitAdvance
        pendingBreakPaintWidth = lineW - advance + paintAdvance
        pendingBreakKind = kind

    def appendBreakableSegmentFrom(segmentIndex, startGraphemeIndex):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        nonlocal pendingBreakSegmentIndex, pendingBreakFitWidth, pendingBreakPaintWidth, pendingBreakKind, lineCount
        fitAdvances = breakableFitAdvances[segmentIndex]
        preferredBreaks = breakablePreferredBreaks[segmentIndex] if segmentIndex < len(breakablePreferredBreaks) else None
        preferredBreakIndex = -1 if preferredBreaks is None else getNextPreferredBreakIndex(preferredBreaks, 0, startGraphemeIndex + 1)
        lastPreferredBreakEnd = -1
        lastPreferredBreakWidth = 0

        g = startGraphemeIndex
        while g < len(fitAdvances):
            baseGw = fitAdvances[g]

            if not hasContent:
                startLineAtGrapheme(segmentIndex, g, baseGw)
            else:
                gw = getBreakableGraphemeAdvance(prepared, True, baseGw)
                candidatePaintWidth = lineW + gw
                if getBreakableCandidateFitWidth(prepared, candidatePaintWidth) > fitLimit:
                    if preferredBreaks is not None and lastPreferredBreakEnd > startGraphemeIndex:
                        emitCurrentLine(segmentIndex, lastPreferredBreakEnd, lastPreferredBreakWidth)
                        g = lastPreferredBreakEnd
                        preferredBreakIndex = getNextPreferredBreakIndex(preferredBreaks, preferredBreakIndex, g + 1)
                        lastPreferredBreakEnd = -1
                        lastPreferredBreakWidth = 0
                        continue
                    emitCurrentLine()
                    startLineAtGrapheme(segmentIndex, g, baseGw)
                else:
                    lineW = candidatePaintWidth
                    lineEndSegmentIndex = segmentIndex
                    lineEndGraphemeIndex = g + 1

            graphemeEnd = g + 1
            if preferredBreaks is not None and preferredBreakIndex < len(preferredBreaks) and preferredBreaks[preferredBreakIndex] == graphemeEnd:
                lastPreferredBreakEnd = graphemeEnd
                lastPreferredBreakWidth = lineW
                preferredBreakIndex += 1
            g += 1

        if hasContent and lineEndSegmentIndex == segmentIndex and lineEndGraphemeIndex == len(fitAdvances):
            lineEndSegmentIndex = segmentIndex + 1
            lineEndGraphemeIndex = 0

    def emitEmptyChunk(chunk):
        nonlocal lineCount, pendingBreakSegmentIndex, pendingBreakFitWidth, pendingBreakPaintWidth, pendingBreakKind
        lineCount += 1
        if onLine is not None:
            onLine(0, chunk['startSegmentIndex'], 0, chunk['consumedEndSegmentIndex'], 0)
        clearPendingBreak()

    for chunkIndex in range(len(chunks)):
        chunk = chunks[chunkIndex]
        if chunk['startSegmentIndex'] == chunk['endSegmentIndex']:
            emitEmptyChunk(chunk)
            continue

        hasContent = False
        lineW = 0
        lineStartSegmentIndex = chunk['startSegmentIndex']
        lineStartGraphemeIndex = 0
        lineEndSegmentIndex = chunk['startSegmentIndex']
        lineEndGraphemeIndex = 0
        clearPendingBreak()

        i = chunk['startSegmentIndex']
        while i < chunk['endSegmentIndex']:
            if not hasContent:
                i = normalizeLineStartSegmentIndex(prepared, i, chunk['endSegmentIndex'])
                if i >= chunk['endSegmentIndex']:
                    break

            kind = kinds[i]
            breakAfter = breaksAfter(kind)
            leadingSpacing = getLeadingLetterSpacing(prepared, hasContent, i)
            if kind == 'tab':
                w = getTabAdvance(lineW + leadingSpacing, prepared['tabStopAdvance'])
            else:
                w = widths[i]
            advance = leadingSpacing + w
            fitAdvance = getWholeSegmentFitContribution(prepared, kind, i, leadingSpacing, w)

            if kind == 'soft-hyphen':
                if hasContent:
                    lineEndSegmentIndex = i + 1
                    lineEndGraphemeIndex = 0
                    pendingBreakSegmentIndex = i + 1
                    pendingBreakFitWidth = lineW + discretionaryHyphenWidth
                    pendingBreakPaintWidth = lineW + discretionaryHyphenWidth
                    pendingBreakKind = kind
                i += 1
                continue

            if not hasContent:
                if fitAdvance > fitLimit and breakableFitAdvances[i] is not None:
                    appendBreakableSegmentFrom(i, 0)
                else:
                    startLineAtSegment(i, w)
                updatePendingBreakForWholeSegment(kind, breakAfter, i, w, leadingSpacing, advance)
                i += 1
                continue

            newFitW = lineW + fitAdvance
            if newFitW > fitLimit:
                currentBreakFitWidth = lineW + getBreakOpportunityFitContribution(prepared, kind, i, leadingSpacing)
                currentBreakPaintWidth = lineW + getLineEndPaintContribution(prepared, kind, i, leadingSpacing, w)

                if breakAfter and currentBreakFitWidth <= fitLimit:
                    appendWholeSegment(i, advance)
                    emitCurrentLine(i + 1, 0, currentBreakPaintWidth)
                    i += 1
                    continue

                if pendingBreakSegmentIndex >= 0 and pendingBreakFitWidth <= fitLimit:
                    if (lineEndSegmentIndex > pendingBreakSegmentIndex or
                        (lineEndSegmentIndex == pendingBreakSegmentIndex and lineEndGraphemeIndex > 0)):
                        emitCurrentLine()
                        continue
                    nextSegmentIndex = pendingBreakSegmentIndex
                    emitCurrentLine(nextSegmentIndex, 0, pendingBreakPaintWidth)
                    i = nextSegmentIndex
                    continue

                if fitAdvance > fitLimit and breakableFitAdvances[i] is not None:
                    emitCurrentLine()
                    appendBreakableSegmentFrom(i, 0)
                    i += 1
                    continue

                emitCurrentLine()
                continue

            appendWholeSegment(i, advance)
            updatePendingBreakForWholeSegment(kind, breakAfter, i, w, leadingSpacing, advance)
            i += 1

        if hasContent:
            finalPaintWidth = pendingBreakPaintWidth if pendingBreakSegmentIndex == chunk['consumedEndSegmentIndex'] else lineW
            emitCurrentLine(chunk['consumedEndSegmentIndex'], 0, finalPaintWidth)

    return lineCount


def stepPreparedChunkLineGeometry(prepared, cursor, chunkIndex, maxWidth):
    chunk = prepared['chunks'][chunkIndex]
    if chunk['startSegmentIndex'] == chunk['endSegmentIndex']:
        cursor['segmentIndex'] = chunk['consumedEndSegmentIndex']
        cursor['graphemeIndex'] = 0
        return 0

    widths = prepared['widths']
    kinds = prepared['kinds']
    breakableFitAdvances = prepared['breakableFitAdvances']
    breakablePreferredBreaks = prepared['breakablePreferredBreaks']
    discretionaryHyphenWidth = prepared['discretionaryHyphenWidth']

    engineProfile = getEngineProfile()
    lineFitEpsilon = engineProfile['lineFitEpsilon']
    fitLimit = maxWidth + lineFitEpsilon

    lineStartSegmentIndex = cursor['segmentIndex']
    lineStartGraphemeIndex = cursor['graphemeIndex']
    lineW = 0
    hasContent = False
    lineEndSegmentIndex = cursor['segmentIndex']
    lineEndGraphemeIndex = cursor['graphemeIndex']
    pendingBreakSegmentIndex = -1
    pendingBreakFitWidth = 0
    pendingBreakPaintWidth = 0
    pendingBreakKind = None

    def getCurrentLinePaintWidth():
        if (pendingBreakKind == 'soft-hyphen' and
            pendingBreakSegmentIndex == lineEndSegmentIndex and
            lineEndGraphemeIndex == 0):
            return pendingBreakPaintWidth
        return lineW

    def finishLine(endSegmentIndex=None, endGraphemeIndex=None, width=None):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        nonlocal pendingBreakSegmentIndex, pendingBreakFitWidth, pendingBreakPaintWidth, pendingBreakKind
        if not hasContent:
            return None
        if endSegmentIndex is None:
            endSegmentIndex = lineEndSegmentIndex
        if endGraphemeIndex is None:
            endGraphemeIndex = lineEndGraphemeIndex
        if width is None:
            width = getCurrentLinePaintWidth()
        cursor['segmentIndex'] = endSegmentIndex
        cursor['graphemeIndex'] = endGraphemeIndex
        return finalizeLinePaintWidth(
            prepared, width,
            lineStartSegmentIndex, lineStartGraphemeIndex,
            endSegmentIndex, endGraphemeIndex
        )

    def startLineAtSegment(segmentIndex, width):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        hasContent = True
        lineEndSegmentIndex = segmentIndex + 1
        lineEndGraphemeIndex = 0
        lineW = width

    def startLineAtGrapheme(segmentIndex, graphemeIndex, width):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        hasContent = True
        lineEndSegmentIndex = segmentIndex
        lineEndGraphemeIndex = graphemeIndex + 1
        lineW = width

    def appendWholeSegment(segmentIndex, advance):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        if not hasContent:
            startLineAtSegment(segmentIndex, advance)
            return
        lineW += advance
        lineEndSegmentIndex = segmentIndex + 1
        lineEndGraphemeIndex = 0

    def updatePendingBreakForWholeSegment(kind, breakAfter, segmentIndex, segmentWidth, leadingSpacing, advance):
        nonlocal pendingBreakSegmentIndex, pendingBreakFitWidth, pendingBreakPaintWidth, pendingBreakKind
        if not breakAfter:
            return
        fitAdvance = getBreakOpportunityFitContribution(prepared, kind, segmentIndex, leadingSpacing)
        paintAdvance = getLineEndPaintContribution(prepared, kind, segmentIndex, leadingSpacing, segmentWidth)
        pendingBreakSegmentIndex = segmentIndex + 1
        pendingBreakFitWidth = lineW - advance + fitAdvance
        pendingBreakPaintWidth = lineW - advance + paintAdvance
        pendingBreakKind = kind

    def appendBreakableSegmentFrom(segmentIndex, startGraphemeIndex):
        nonlocal hasContent, lineW, lineEndSegmentIndex, lineEndGraphemeIndex
        nonlocal pendingBreakSegmentIndex, pendingBreakFitWidth, pendingBreakPaintWidth, pendingBreakKind
        fitAdvances = breakableFitAdvances[segmentIndex]
        preferredBreaks = breakablePreferredBreaks[segmentIndex] if segmentIndex < len(breakablePreferredBreaks) else None
        if preferredBreaks is None:
            preferredBreakIndex = -1
        else:
            preferredBreakIndex = getNextPreferredBreakIndex(preferredBreaks, 0, startGraphemeIndex + 1)
        lastPreferredBreakEnd = -1
        lastPreferredBreakWidth = 0

        for g in range(startGraphemeIndex, len(fitAdvances)):
            baseGw = fitAdvances[g]

            if not hasContent:
                startLineAtGrapheme(segmentIndex, g, baseGw)
            else:
                gw = getBreakableGraphemeAdvance(prepared, True, baseGw)
                candidatePaintWidth = lineW + gw
                if getBreakableCandidateFitWidth(prepared, candidatePaintWidth) > fitLimit:
                    if preferredBreaks is not None and lastPreferredBreakEnd > startGraphemeIndex:
                        return finishLine(segmentIndex, lastPreferredBreakEnd, lastPreferredBreakWidth)
                    return finishLine()
                lineW = candidatePaintWidth
                lineEndSegmentIndex = segmentIndex
                lineEndGraphemeIndex = g + 1

            graphemeEnd = g + 1
            if preferredBreaks is not None and preferredBreakIndex < len(preferredBreaks) and preferredBreaks[preferredBreakIndex] == graphemeEnd:
                lastPreferredBreakEnd = graphemeEnd
                lastPreferredBreakWidth = lineW
                preferredBreakIndex += 1

        if hasContent and lineEndSegmentIndex == segmentIndex and lineEndGraphemeIndex == len(fitAdvances):
            lineEndSegmentIndex = segmentIndex + 1
            lineEndGraphemeIndex = 0
        return None

    def maybeFinishAtSoftHyphen():
        if pendingBreakKind != 'soft-hyphen' or pendingBreakSegmentIndex < 0:
            return None
        if pendingBreakFitWidth <= fitLimit:
            return finishLine(pendingBreakSegmentIndex, 0, pendingBreakPaintWidth)
        return None

    startIdx = cursor['segmentIndex']
    for i in range(startIdx, chunk['endSegmentIndex']):
        kind = kinds[i]
        breakAfter = breaksAfter(kind)
        startGraphemeIndex = cursor['graphemeIndex'] if i == cursor['segmentIndex'] else 0
        leadingSpacing = getLeadingLetterSpacing(prepared, hasContent, i)
        if kind == 'tab':
            w = getTabAdvance(lineW + leadingSpacing, prepared['tabStopAdvance'])
        else:
            w = widths[i]
        advance = leadingSpacing + w
        fitAdvance = getWholeSegmentFitContribution(prepared, kind, i, leadingSpacing, w)

        if kind == 'soft-hyphen' and startGraphemeIndex == 0:
            if hasContent:
                lineEndSegmentIndex = i + 1
                lineEndGraphemeIndex = 0
                pendingBreakSegmentIndex = i + 1
                pendingBreakFitWidth = lineW + discretionaryHyphenWidth
                pendingBreakPaintWidth = lineW + discretionaryHyphenWidth
                pendingBreakKind = kind
            continue

        if not hasContent:
            if startGraphemeIndex > 0:
                line = appendBreakableSegmentFrom(i, startGraphemeIndex)
                if line is not None:
                    return line
            elif fitAdvance > fitLimit and breakableFitAdvances[i] is not None:
                line = appendBreakableSegmentFrom(i, 0)
                if line is not None:
                    return line
            else:
                startLineAtSegment(i, w)
            updatePendingBreakForWholeSegment(kind, breakAfter, i, w, leadingSpacing, advance)
            continue

        newFitW = lineW + fitAdvance
        if newFitW > fitLimit:
            currentBreakFitWidth = lineW + getBreakOpportunityFitContribution(prepared, kind, i, leadingSpacing)
            currentBreakPaintWidth = lineW + getLineEndPaintContribution(prepared, kind, i, leadingSpacing, w)

            softBreakLine = maybeFinishAtSoftHyphen()
            if softBreakLine is not None:
                return softBreakLine

            if breakAfter and currentBreakFitWidth <= fitLimit:
                appendWholeSegment(i, advance)
                return finishLine(i + 1, 0, currentBreakPaintWidth)

            if pendingBreakSegmentIndex >= 0 and pendingBreakFitWidth <= fitLimit:
                if (lineEndSegmentIndex > pendingBreakSegmentIndex or
                    (lineEndSegmentIndex == pendingBreakSegmentIndex and lineEndGraphemeIndex > 0)):
                    return finishLine()
                return finishLine(pendingBreakSegmentIndex, 0, pendingBreakPaintWidth)

            if fitAdvance > fitLimit and breakableFitAdvances[i] is not None:
                currentLine = finishLine()
                if currentLine is not None:
                    return currentLine
                line = appendBreakableSegmentFrom(i, 0)
                if line is not None:
                    return line

            return finishLine()

        appendWholeSegment(i, advance)
        updatePendingBreakForWholeSegment(kind, breakAfter, i, w, leadingSpacing, advance)

    if pendingBreakSegmentIndex == chunk['consumedEndSegmentIndex'] and lineEndGraphemeIndex == 0:
        return finishLine(chunk['consumedEndSegmentIndex'], 0, pendingBreakPaintWidth)

    return finishLine(chunk['consumedEndSegmentIndex'], 0, lineW)


def stepPreparedSimpleLineGeometry(prepared, cursor, maxWidth):
    widths = prepared['widths']
    kinds = prepared['kinds']
    breakableFitAdvances = prepared['breakableFitAdvances']
    breakablePreferredBreaks = prepared['breakablePreferredBreaks']

    engineProfile = getEngineProfile()
    lineFitEpsilon = engineProfile['lineFitEpsilon']
    fitLimit = maxWidth + lineFitEpsilon

    lineW = 0
    hasContent = False
    lineEndSegmentIndex = cursor['segmentIndex']
    lineEndGraphemeIndex = cursor['graphemeIndex']
    pendingBreakSegmentIndex = -1
    pendingBreakPaintWidth = 0

    startIdx = cursor['segmentIndex']
    for i in range(startIdx, len(widths)):
        kind = kinds[i]
        breakAfter = breaksAfter(kind)
        startGraphemeIndex = cursor['graphemeIndex'] if i == cursor['segmentIndex'] else 0
        breakableFitAdvance = breakableFitAdvances[i]
        w = widths[i]

        if not hasContent:
            if startGraphemeIndex > 0 or (w > fitLimit and breakableFitAdvance is not None):
                fitAdvances = breakableFitAdvance
                preferredBreaks = breakablePreferredBreaks[i] if i < len(breakablePreferredBreaks) else None
                if preferredBreaks is None:
                    preferredBreakIndex = -1
                else:
                    preferredBreakIndex = getNextPreferredBreakIndex(preferredBreaks, 0, startGraphemeIndex + 1)
                lastPreferredBreakEnd = -1
                lastPreferredBreakWidth = 0
                firstGraphemeWidth = fitAdvances[startGraphemeIndex]

                hasContent = True
                lineW = firstGraphemeWidth
                lineEndSegmentIndex = i
                lineEndGraphemeIndex = startGraphemeIndex + 1
                if preferredBreaks is not None and preferredBreakIndex < len(preferredBreaks) and preferredBreaks[preferredBreakIndex] == lineEndGraphemeIndex:
                    lastPreferredBreakEnd = lineEndGraphemeIndex
                    lastPreferredBreakWidth = lineW
                    preferredBreakIndex += 1

                for g in range(startGraphemeIndex + 1, len(fitAdvances)):
                    gw = fitAdvances[g]
                    if lineW + gw > fitLimit:
                        if preferredBreaks is not None and lastPreferredBreakEnd > startGraphemeIndex:
                            cursor['segmentIndex'] = i
                            cursor['graphemeIndex'] = lastPreferredBreakEnd
                            return lastPreferredBreakWidth
                        cursor['segmentIndex'] = lineEndSegmentIndex
                        cursor['graphemeIndex'] = lineEndGraphemeIndex
                        return lineW
                    lineW += gw
                    lineEndSegmentIndex = i
                    lineEndGraphemeIndex = g + 1
                    if preferredBreaks is not None and preferredBreakIndex < len(preferredBreaks) and preferredBreaks[preferredBreakIndex] == lineEndGraphemeIndex:
                        lastPreferredBreakEnd = lineEndGraphemeIndex
                        lastPreferredBreakWidth = lineW
                        preferredBreakIndex += 1

                if lineEndSegmentIndex == i and lineEndGraphemeIndex == len(fitAdvances):
                    lineEndSegmentIndex = i + 1
                    lineEndGraphemeIndex = 0
            else:
                hasContent = True
                lineW = w
                lineEndSegmentIndex = i + 1
                lineEndGraphemeIndex = 0
            if breakAfter:
                pendingBreakSegmentIndex = i + 1
                pendingBreakPaintWidth = lineW - w
            continue

        if lineW + w > fitLimit:
            if breakAfter:
                cursor['segmentIndex'] = i + 1
                cursor['graphemeIndex'] = 0
                return lineW

            if pendingBreakSegmentIndex >= 0:
                if (lineEndSegmentIndex > pendingBreakSegmentIndex or
                    (lineEndSegmentIndex == pendingBreakSegmentIndex and lineEndGraphemeIndex > 0)):
                    cursor['segmentIndex'] = lineEndSegmentIndex
                    cursor['graphemeIndex'] = lineEndGraphemeIndex
                    return lineW
                cursor['segmentIndex'] = pendingBreakSegmentIndex
                cursor['graphemeIndex'] = 0
                return pendingBreakPaintWidth

            cursor['segmentIndex'] = lineEndSegmentIndex
            cursor['graphemeIndex'] = lineEndGraphemeIndex
            return lineW

        lineW += w
        lineEndSegmentIndex = i + 1
        lineEndGraphemeIndex = 0
        if breakAfter:
            pendingBreakSegmentIndex = i + 1
            pendingBreakPaintWidth = lineW - w

    if not hasContent:
        return None
    cursor['segmentIndex'] = lineEndSegmentIndex
    cursor['graphemeIndex'] = lineEndGraphemeIndex
    return lineW


def stepPreparedLineGeometryFromChunk(prepared, cursor, chunkIndex, maxWidth):
    if prepared['simpleLineWalkFastPath']:
        return stepPreparedSimpleLineGeometry(prepared, cursor, maxWidth)
    return stepPreparedChunkLineGeometry(prepared, cursor, chunkIndex, maxWidth)


def stepPreparedLineGeometry(prepared, cursor, maxWidth):
    chunkIndex = normalizePreparedLineStart(prepared, cursor)
    if chunkIndex < 0:
        return None
    return stepPreparedLineGeometryFromChunk(prepared, cursor, chunkIndex, maxWidth)


def measurePreparedLineGeometry(prepared, maxWidth):
    if len(prepared['widths']) == 0:
        return {
            'lineCount': 0,
            'maxLineWidth': 0,
        }

    cursor = {
        'segmentIndex': 0,
        'graphemeIndex': 0,
    }
    lineCount = 0
    maxLineWidth = 0

    if not prepared['simpleLineWalkFastPath']:
        chunkIndex = normalizePreparedLineStart(prepared, cursor)
        while chunkIndex >= 0:
            lineWidth = stepPreparedChunkLineGeometry(prepared, cursor, chunkIndex, maxWidth)
            if lineWidth is None:
                return {
                    'lineCount': lineCount,
                    'maxLineWidth': maxLineWidth,
                }
            lineCount += 1
            if lineWidth > maxLineWidth:
                maxLineWidth = lineWidth
            chunkIndex = normalizeLineStartChunkIndexFromHint(prepared, chunkIndex, cursor)
        return {
            'lineCount': lineCount,
            'maxLineWidth': maxLineWidth,
        }

    while True:
        lineWidth = stepPreparedLineGeometry(prepared, cursor, maxWidth)
        if lineWidth is None:
            return {
                'lineCount': lineCount,
                'maxLineWidth': maxLineWidth,
            }
        lineCount += 1
        if lineWidth > maxLineWidth:
            maxLineWidth = lineWidth

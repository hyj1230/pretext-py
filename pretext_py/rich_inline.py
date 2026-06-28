from .layout import measureNaturalWidth, prepareWithSegments
from .line_text import  buildLineTextFromRange, getLineTextCache
from .line_break import stepPreparedLineGeometry
from .intl_segmenter_py import String
import re

# Helper for rich-text inline flow under `white-space: normal`.
# It keeps the core layout API low-level while taking over the boring shared
# work that rich inline demos kept reimplementing in userland:
# - collapsed boundary whitespace across item boundaries
# - atomic inline boxes like pills
# - per-item extra horizontal chrome such as padding/borders

COLLAPSIBLE_BOUNDARY_RE = re.compile(r'[ \t\n\f\r]+')
LEADING_COLLAPSIBLE_BOUNDARY_RE = re.compile(r'^[ \t\n\f\r]+')
TRAILING_COLLAPSIBLE_BOUNDARY_RE = re.compile(r'[ \t\n\f\r]+\Z')  # 用 \Z 代替 $
EMPTY_LAYOUT_CURSOR = {'segmentIndex': 0, 'graphemeIndex': 0}
RICH_INLINE_START_CURSOR = {
    'itemIndex': 0,
    'segmentIndex': 0,
    'graphemeIndex': 0,
}

def cloneCursor(cursor):
    return {
        'segmentIndex': cursor['segmentIndex'],
        'graphemeIndex': cursor['graphemeIndex'],
    }

def isLineStartCursor(cursor):
    return cursor['segmentIndex'] == 0 and cursor['graphemeIndex'] == 0

def getCollapsedSpaceWidth(font, letterSpacing, cache):
    cacheKey = f"{font}\u0000{letterSpacing}"
    cached = cache.get(cacheKey)
    if cached is not None:
        return cached

    options = None if letterSpacing == 0 else {'letterSpacing': letterSpacing}
    joinedWidth = measureNaturalWidth(prepareWithSegments('A A', font, options))
    compactWidth = measureNaturalWidth(prepareWithSegments('AA', font, options))
    collapsedWidth = max(0, joinedWidth - compactWidth)
    cache[cacheKey] = collapsedWidth
    return collapsedWidth

def prepareWholeItemLine(prepared):
    end = {'segmentIndex': 0, 'graphemeIndex': 0}
    width = stepPreparedLineGeometry(prepared, end, float('inf'))
    if width is None:
        return None
    return {
        'endGraphemeIndex': end['graphemeIndex'],
        'endSegmentIndex': end['segmentIndex'],
        'width': width,
    }


def endsInsideFirstSegment(segmentIndex, graphemeIndex):
    return segmentIndex == 0 and graphemeIndex > 0


def prepareRichInline(items):
    preparedItems = []
    itemsBySourceItemIndex = [None] * len(items)
    collapsedSpaceWidthCache = {}
    pendingGapWidth = 0

    for index, item in enumerate(items):
        letterSpacing = item.get('letterSpacing', 0)
        hasLeadingWhitespace = bool(LEADING_COLLAPSIBLE_BOUNDARY_RE.search(str(item['text'])))
        hasTrailingWhitespace = bool(TRAILING_COLLAPSIBLE_BOUNDARY_RE.search(str(item['text'])))
        trimmedText: String = String(re.sub(LEADING_COLLAPSIBLE_BOUNDARY_RE, '', str(item['text'])))
        trimmedText: String = String(re.sub(TRAILING_COLLAPSIBLE_BOUNDARY_RE, '', str(trimmedText)))

        if trimmedText.length == 0:
            if COLLAPSIBLE_BOUNDARY_RE.search(str(item['text'])) and pendingGapWidth == 0:
                pendingGapWidth = getCollapsedSpaceWidth(item['font'], letterSpacing, collapsedSpaceWidthCache)
            continue

        gapBefore = (
            pendingGapWidth if pendingGapWidth > 0 else
            getCollapsedSpaceWidth(item['font'], letterSpacing, collapsedSpaceWidthCache) if hasLeadingWhitespace else
            0
        )
        prepared = prepareWithSegments(
            trimmedText,
            item['font'],
            None if letterSpacing == 0 else {'letterSpacing': letterSpacing}
        )
        wholeLine = prepareWholeItemLine(prepared)
        if wholeLine is None:
            pendingGapWidth = (
                getCollapsedSpaceWidth(item['font'], letterSpacing, collapsedSpaceWidthCache)
                if hasTrailingWhitespace else 0
            )
            continue

        preparedItem = {
            'break': item.get('break', 'normal'),
            'endGraphemeIndex': wholeLine['endGraphemeIndex'],
            'endSegmentIndex': wholeLine['endSegmentIndex'],
            'extraWidth': item.get('extraWidth', 0),
            'gapBefore': gapBefore,
            'naturalWidth': wholeLine['width'],
            'prepared': prepared,
            'sourceItemIndex': index,
        }
        preparedItems.append(preparedItem)
        itemsBySourceItemIndex[index] = preparedItem

        pendingGapWidth = (
            getCollapsedSpaceWidth(item['font'], letterSpacing, collapsedSpaceWidthCache)
            if hasTrailingWhitespace else 0
        )

    return {'items': preparedItems, 'itemsBySourceItemIndex': itemsBySourceItemIndex}


def stepRichInlineLine(flow, maxWidth, cursor, collectFragment=None):
    if len(flow['items']) == 0 or cursor['itemIndex'] >= len(flow['items']):
        return None

    safeWidth = max(1, maxWidth)
    lineWidth = 0
    remainingWidth = safeWidth
    itemIndex = cursor['itemIndex']

    while itemIndex < len(flow['items']):
        item = flow['items'][itemIndex]
        if (
            not isLineStartCursor(cursor) and
            cursor['segmentIndex'] == item['endSegmentIndex'] and
            cursor['graphemeIndex'] == item['endGraphemeIndex']
        ):
            itemIndex += 1
            cursor['segmentIndex'] = 0
            cursor['graphemeIndex'] = 0
            continue

        gapBefore = 0 if lineWidth == 0 else item['gapBefore']
        atItemStart = isLineStartCursor(cursor)

        if item['break'] == 'never':
            if not atItemStart:
                itemIndex += 1
                cursor['segmentIndex'] = 0
                cursor['graphemeIndex'] = 0
                continue

            occupiedWidth = item['naturalWidth'] + item['extraWidth']
            totalWidth = gapBefore + occupiedWidth
            if lineWidth > 0 and totalWidth > remainingWidth:
                break

            if collectFragment is not None:
                collectFragment(
                    item,
                    gapBefore,
                    occupiedWidth,
                    cloneCursor(EMPTY_LAYOUT_CURSOR),
                    {
                        'segmentIndex': item['endSegmentIndex'],
                        'graphemeIndex': item['endGraphemeIndex'],
                    }
                )
            lineWidth += totalWidth
            remainingWidth = max(0, safeWidth - lineWidth)
            itemIndex += 1
            cursor['segmentIndex'] = 0
            cursor['graphemeIndex'] = 0
            continue

        reservedWidth = gapBefore + item['extraWidth']
        if lineWidth > 0 and reservedWidth >= remainingWidth:
            break

        if atItemStart:
            totalWidth = reservedWidth + item['naturalWidth']
            if totalWidth <= remainingWidth:
                if collectFragment is not None:
                    collectFragment(
                        item,
                        gapBefore,
                        item['naturalWidth'] + item['extraWidth'],
                        cloneCursor(EMPTY_LAYOUT_CURSOR),
                        {
                            'segmentIndex': item['endSegmentIndex'],
                            'graphemeIndex': item['endGraphemeIndex'],
                        }
                    )
                lineWidth += totalWidth
                remainingWidth = max(0, safeWidth - lineWidth)
                itemIndex += 1
                cursor['segmentIndex'] = 0
                cursor['graphemeIndex'] = 0
                continue

        availableWidth = max(1, remainingWidth - reservedWidth)
        lineEnd = {
            'segmentIndex': cursor['segmentIndex'],
            'graphemeIndex': cursor['graphemeIndex'],
        }
        lineWidthForItem = stepPreparedLineGeometry(item['prepared'], lineEnd, availableWidth)
        if lineWidthForItem is None:
            itemIndex += 1
            cursor['segmentIndex'] = 0
            cursor['graphemeIndex'] = 0
            continue
        if (
            cursor['segmentIndex'] == lineEnd['segmentIndex'] and
            cursor['graphemeIndex'] == lineEnd['graphemeIndex']
        ):
            itemIndex += 1
            cursor['segmentIndex'] = 0
            cursor['graphemeIndex'] = 0
            continue

        itemOccupiedWidth = lineWidthForItem + item['extraWidth']
        lineWidthContribution = gapBefore + itemOccupiedWidth

        # The lower-level walker may force one unit to make progress. If that unit
        # only fits on a fresh line, wrap before this rich item instead.
        if lineWidth > 0 and atItemStart and lineWidthContribution > remainingWidth:
            break

        # If the only thing we can fit after paying the boundary gap is a partial
        # slice of the item's first segment, prefer wrapping before the item so we
        # keep whole-word-style boundaries when they exist. But once the current
        # line can consume a real breakable unit from the item, stay greedy and
        # keep filling the line.
        if (
            lineWidth > 0 and
            atItemStart and
            gapBefore > 0 and
            endsInsideFirstSegment(lineEnd['segmentIndex'], lineEnd['graphemeIndex'])
        ):
            freshLineEnd = {'segmentIndex': 0, 'graphemeIndex': 0}
            freshLineWidth = stepPreparedLineGeometry(
                item['prepared'],
                freshLineEnd,
                max(1, safeWidth - item['extraWidth']),
            )
            if (
                freshLineWidth is not None and
                (
                    freshLineEnd['segmentIndex'] > lineEnd['segmentIndex'] or
                    (
                        freshLineEnd['segmentIndex'] == lineEnd['segmentIndex'] and
                        freshLineEnd['graphemeIndex'] > lineEnd['graphemeIndex']
                    )
                )
            ):
                break

        if collectFragment is not None:
            collectFragment(
                item,
                gapBefore,
                itemOccupiedWidth,
                cloneCursor(cursor),
                {
                    'segmentIndex': lineEnd['segmentIndex'],
                    'graphemeIndex': lineEnd['graphemeIndex'],
                }
            )
        lineWidth += lineWidthContribution
        remainingWidth = max(0, safeWidth - lineWidth)

        if (
            lineEnd['segmentIndex'] == item['endSegmentIndex'] and
            lineEnd['graphemeIndex'] == item['endGraphemeIndex']
        ):
            itemIndex += 1
            cursor['segmentIndex'] = 0
            cursor['graphemeIndex'] = 0
            continue

        cursor['segmentIndex'] = lineEnd['segmentIndex']
        cursor['graphemeIndex'] = lineEnd['graphemeIndex']
        break

    if lineWidth == 0:
        return None

    cursor['itemIndex'] = itemIndex
    return lineWidth


def layoutNextRichInlineLineRange(prepared, maxWidth, start=None):
    if start is None:
        start = RICH_INLINE_START_CURSOR
    
    flow = prepared
    end = {
        'itemIndex': start['itemIndex'],
        'segmentIndex': start['segmentIndex'],
        'graphemeIndex': start['graphemeIndex'],
    }
    fragments = []

    def collect_fragment(item, gapBefore, occupiedWidth, fragmentStart, fragmentEnd):
        fragments.append({
            'itemIndex': item['sourceItemIndex'],
            'gapBefore': gapBefore,
            'occupiedWidth': occupiedWidth,
            'start': fragmentStart,
            'end': fragmentEnd,
        })

    width = stepRichInlineLine(flow, maxWidth, end, collect_fragment)
    if width is None:
        return None

    return {
        'fragments': fragments,
        'width': width,
        'end': end,
    }


def materializeFragmentText(item, fragment):
    return buildLineTextFromRange(
        item['prepared'],
        getLineTextCache(item['prepared']),
        fragment['start']['segmentIndex'],
        fragment['start']['graphemeIndex'],
        fragment['end']['segmentIndex'],
        fragment['end']['graphemeIndex'],
    )

# Bridge from cheap range walking to full fragment text. Lets callers do
# shrinkwrap/virtualization/probing work first, then only pay for text on the
# lines they actually render.
def materializeRichInlineLineRange(prepared, line):
    flow = prepared
    fragments = []

    for fragment in line['fragments']:
        item = flow['itemsBySourceItemIndex'][fragment['itemIndex']]
        if item is None:
            raise RuntimeError('Missing rich-text inline item for fragment')
        fragments.append({
            'itemIndex': fragment['itemIndex'],
            'text': materializeFragmentText(item, fragment),
            'gapBefore': fragment['gapBefore'],
            'occupiedWidth': fragment['occupiedWidth'],
            'start': fragment['start'],
            'end': fragment['end'],
        })

    return {
        'fragments': fragments,
        'width': line['width'],
        'end': line['end'],
    }


def walkRichInlineLineRanges(prepared, maxWidth, onLine):
    lineCount = 0
    cursor = RICH_INLINE_START_CURSOR.copy()  # 避免修改原常量

    while True:
        line = layoutNextRichInlineLineRange(prepared, maxWidth, cursor)
        if line is None:
            return lineCount
        onLine(line)
        lineCount += 1
        cursor = line['end']


def measureRichInlineStats(prepared, maxWidth):
    flow = prepared
    lineCount = 0
    maxLineWidth = 0
    cursor = {
        'itemIndex': 0,
        'segmentIndex': 0,
        'graphemeIndex': 0,
    }

    while True:
        lineWidth = stepRichInlineLine(flow, maxWidth, cursor)
        if lineWidth is None:
            return {
                'lineCount': lineCount,
                'maxLineWidth': maxLineWidth,
            }
        lineCount += 1
        if lineWidth > maxLineWidth:
            maxLineWidth = lineWidth

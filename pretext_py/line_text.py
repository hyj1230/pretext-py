from .intl_segmenter_py import Segmenter, String


sharedGraphemeSegmenter: Segmenter = None
sharedLineTextCaches = {}

def getSharedGraphemeSegmenter() -> Segmenter:
    global sharedGraphemeSegmenter  # pylint:disable=W0603
    if sharedGraphemeSegmenter is None:
        sharedGraphemeSegmenter = Segmenter(None, {'granularity': 'grapheme'})
  
    return sharedGraphemeSegmenter


def getSegmentGraphemes(segmentIndex: int, segments, cache: dict):
    graphemes = cache.get(segmentIndex, None)
    if graphemes is not None: return graphemes

    graphemes = []
    graphemeSegmenter = getSharedGraphemeSegmenter()
    for gs in graphemeSegmenter.segment(segments[segmentIndex]):
        graphemes.append(gs['segment'])
    cache[segmentIndex] = graphemes
    return graphemes


def lineHasDiscretionaryHyphen(kinds, startSegmentIndex: int, endSegmentIndex: int) -> bool:
  return (
    endSegmentIndex > startSegmentIndex and \
    kinds[endSegmentIndex - 1] == 'soft-hyphen'
  )


def appendSegmentGraphemeRange(text: String, graphemes, startGraphemeIndex: int, endGraphemeIndex: int) -> String:
    for i in range(startGraphemeIndex, endGraphemeIndex):
        text = text + graphemes[i]
    return text


def getLineTextCache(prepared: dict):
    cache = sharedLineTextCaches.get(id(prepared), None)
    if cache is not None: return cache

    cache = {}
    sharedLineTextCaches[id(prepared)] = cache
    return cache


def buildLineTextFromRange(
  prepared: dict,
  cache: dict,
  startSegmentIndex: int,
  startGraphemeIndex: int,
  endSegmentIndex: int,
  endGraphemeIndex: int,
) -> String:
    text = String('')
    endsWithDiscretionaryHyphen = lineHasDiscretionaryHyphen(
      prepared['kinds'],
      startSegmentIndex,
      endSegmentIndex,
    )

    for i in range(startSegmentIndex, endSegmentIndex):
        if prepared['kinds'][i] == 'soft-hyphen' or prepared['kinds'][i] == 'hard-break': continue
        if i == startSegmentIndex and startGraphemeIndex > 0:
            graphemes = getSegmentGraphemes(i, prepared['segments'], cache)
            text = appendSegmentGraphemeRange(text, graphemes, startGraphemeIndex, len(graphemes))
        else:
            text = text + prepared['segments'][i]

    if endGraphemeIndex > 0:
        if endsWithDiscretionaryHyphen: text += String('-')
        graphemes = getSegmentGraphemes(endSegmentIndex, prepared['segments'], cache)
        text = appendSegmentGraphemeRange(
          text,
          graphemes,
          startGraphemeIndex if startSegmentIndex == endSegmentIndex else 0,
          endGraphemeIndex,
        )
    elif endsWithDiscretionaryHyphen:
        text += '-'

    return text


def clearLineTextCaches():
    global sharedGraphemeSegmenter, sharedLineTextCaches  # pylint:disable=W0603
    sharedGraphemeSegmenter = None
    sharedLineTextCaches = {}

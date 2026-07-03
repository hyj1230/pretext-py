from .analysis import isCJK
from .intl_segmenter_py import isEmojiPresentation, isExtendedPictographic, Segmenter, String
from .py_canvas import get_context
import re


def isRegionalIndicator(cp: int):
    return 0x1f1e6 <= cp <= 0x1f1ff


measureContext = None
segmentMetricCaches = {}
cachedEngineProfile = None

# Safari 的前缀适配策略对普通单词规模的文本段很有用，但让它测量超大段落的每个增长前缀会重新导致性能问题的超线性路径。超过此大小时，切换到更便宜的 pair-context 模型，保持公有行为线性。
MAX_PREFIX_FIT_GRAPHEMES = 96

sharedGraphemeSegmenter: Segmenter = None
emojiCorrectionCache = {}


def getMeasureContext():
    global measureContext  # pylint:disable=W0603
    if measureContext is not None: return measureContext

    context = get_context()
    measureContext = context()
    return measureContext


def getSegmentMetricCache(font: str):
    cache = segmentMetricCaches.get(font, None)
    if cache is None:
        cache = {}
        segmentMetricCaches[font] = cache
    return cache

# debug_cache = set()
def getSegmentMetrics(seg: str, cache):
    metrics = cache.get(seg, None)
    
    if metrics is None:
        # debug_cache.add(seg)
        ctx = getMeasureContext()
        metrics = {
          'width': ctx.measureText(seg)['width'],
          'containsCJK': isCJK(String(seg)),
        }
        cache[seg] = metrics
    return metrics


def getEngineProfile():
    global cachedEngineProfile  # pylint:disable=W0603
    if cachedEngineProfile is not None: return cachedEngineProfile
    
    navigator = None

    if navigator is None:
        cachedEngineProfile = {
          'lineFitEpsilon': 0.005,
          'carryCJKAfterClosingQuote': False,
          'breakKeepAllAfterPunctuation': True,
          'preferPrefixWidthsForBreakableRuns': False,
        }
        return cachedEngineProfile

    isSafari = False
    isChromium = True

    cachedEngineProfile = {
      'lineFitEpsilon': 1 / 64 if isSafari else 0.005,
      'carryCJKAfterClosingQuote': isChromium,
      'breakKeepAllAfterPunctuation': not isSafari,
      'preferPrefixWidthsForBreakableRuns': isSafari,
    }
    return cachedEngineProfile


def parseFontSize(font: str) -> float:
    match = re.search(r'(\d+(?:\.\d+)?)\s*px', font)
    if match:
        return float(match.group(1))
    return 16.0


def getSharedGraphemeSegmenter() -> Segmenter:
    global sharedGraphemeSegmenter  # pylint:disable=W0603
    if sharedGraphemeSegmenter is None:
        sharedGraphemeSegmenter = Segmenter(None, {'granularity': 'grapheme'})
  
    return sharedGraphemeSegmenter


def isEmojiGrapheme(g: String) -> bool:
    return any(map(lambda s: isEmojiPresentation(ord(s)), str(g))) or g.contain_code((0xFE0F))


def textMayContainEmoji(g: String) -> bool:
    return any(map(lambda s: isEmojiPresentation(ord(s)) or isExtendedPictographic(ord(s)) or isRegionalIndicator(ord(s)), str(g))) or g.contain_code((0xFE0F, 0x20E3))


def getEmojiCorrection(font: str, fontSize: float) -> float:  # pylint:disable=W0613
    correction = emojiCorrectionCache.get(font)
    if correction is not None: return correction

    correction = 0  # 没有 DOM，无法进行修正
    emojiCorrectionCache[font] = correction
    return correction


def countEmojiGraphemes(text: String) -> int:
    count = 0
    graphemeSegmenter = getSharedGraphemeSegmenter()
    for g in graphemeSegmenter.segment(text):
        if isEmojiGrapheme(g['segment']): count += 1

    return count

def getEmojiCount(seg: String, metrics) -> int:
    if 'emojiCount' not in metrics:
        metrics['emojiCount'] = countEmojiGraphemes(seg)
    return metrics['emojiCount']


def getCorrectedSegmentWidth(seg: String, metrics, emojiCorrection: float) -> float:
    if emojiCorrection == 0: return metrics['width']
    return metrics['width'] - getEmojiCount(seg, metrics) * emojiCorrection


def getSegmentBreakableFitAdvances(seg: String, metrics, cache, emojiCorrection: float, mode: str):
    if 'breakableFitAdvances' in metrics and metrics['breakableFitMode'] == mode:
        return metrics['breakableFitAdvances']
 
    metrics['breakableFitMode'] = mode
    graphemeSegmenter = getSharedGraphemeSegmenter()
    graphemes = list(map(lambda gs: gs['segment'], graphemeSegmenter.segment(seg)))
  
    if len(graphemes) <= 1:
        metrics['breakableFitAdvances'] = None
        return metrics['breakableFitAdvances']

    if mode == 'sum-graphemes':
          advances = []
          for grapheme in graphemes:
              graphemeMetrics = getSegmentMetrics(str(grapheme), cache)
              advances.append(getCorrectedSegmentWidth(grapheme, graphemeMetrics, emojiCorrection))
        
          metrics['breakableFitAdvances'] = advances
          return metrics['breakableFitAdvances']

    if mode == 'pair-context' or len(graphemes) > MAX_PREFIX_FIT_GRAPHEMES:
        advances = []
        previousGrapheme: String = None
        previousWidth = 0
    
        for grapheme in graphemes:
            graphemeMetrics = getSegmentMetrics(str(grapheme), cache)
            currentWidth = getCorrectedSegmentWidth(grapheme, graphemeMetrics, emojiCorrection)
    
            if previousGrapheme is None:
                advances.append(currentWidth)
            else:
                pair = previousGrapheme + grapheme
                pairMetrics = getSegmentMetrics(str(pair), cache)
                advances.append(getCorrectedSegmentWidth(pair, pairMetrics, emojiCorrection) - previousWidth)
    
            previousGrapheme = grapheme
            previousWidth = currentWidth

        metrics['breakableFitAdvances'] = advances
        return metrics['breakableFitAdvances']

    advances = []
    prefix = String('')
    prefixWidth = 0

    for grapheme in graphemes:
        prefix = prefix + grapheme
        prefixMetrics = getSegmentMetrics(str(prefix), cache)
        nextPrefixWidth = getCorrectedSegmentWidth(prefix, prefixMetrics, emojiCorrection)
        advances.append(nextPrefixWidth - prefixWidth)
        prefixWidth = nextPrefixWidth

    metrics['breakableFitAdvances'] = advances
    return metrics['breakableFitAdvances']


def getFontMeasurementState(font: str, needsEmojiCorrection: bool):
    ctx = getMeasureContext()
    ctx.font = font
    cache = getSegmentMetricCache(font)
    fontSize = parseFontSize(font)
    emojiCorrection = getEmojiCorrection(font, fontSize) if needsEmojiCorrection else 0
    return {'cache': cache, 'fontSize': fontSize, 'emojiCorrection': emojiCorrection}

def clearMeasurementCaches():
    global sharedGraphemeSegmenter  # pylint:disable=W0603
    segmentMetricCaches.clear()
    emojiCorrectionCache.clear()
    sharedGraphemeSegmenter = None

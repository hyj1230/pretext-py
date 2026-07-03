from .grapheme import graphemeSegments
from .word import word_bounds, is_word_like
from .compat_util import String
        

# 适配 `Intl.Segmenter` API
# @see https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter
class Segmenter:
    custom_grapheme = None
    custom_word = None
    def __init__(self, locale: str, options = None):
        self.p_options = options or {}
        granularity = self.p_options.get('granularity', 'grapheme')
        
        if granularity == 'grapheme':
            pass
        elif granularity == 'word':
            pass
        elif granularity == 'sentence':
            raise TypeError('Unicode "sentence" segmenter is currently not implemented')
        else:
            raise TypeError(f'Value {granularity} out of range for Intl.Segmenter options property granularity')
    
        self.p_locale: str = locale or 'en'
        self.p_granularity: str = granularity
  
    # Impelements {@link Intl.Segmenter.segment}
    # @see https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter/segment
    def segment(self, _input: String):
        return SegmentsAdapter(_input, self.p_granularity, self.p_locale, self.p_options)

    # Impelements {@link Intl.Segmenter.resolvedOptions}
    # @see https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter/resolvedOptions
    def resolvedOptions(self):
        return {
          'locale': self.p_locale,
          'granularity': self.p_granularity,
        }


# @see https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter/segment/Segments
class SegmentsAdapter:
    def __init__(self, _input: String, granularity: str, locale: str, options: dict):
        self.input = _input
        self.granularity = granularity
        self.locale = locale
        self.options = options
    
    def __iter__(self):
        if self.granularity == 'grapheme':
            if Segmenter.custom_grapheme is None:
                for i in graphemeSegments(String(self.input)):
                    yield {'segment': i['segment'], 'index': i['index'], 'input': i['input']}
            else:
                index = 0
                s = String(self.input)
                for segment in Segmenter.custom_grapheme(str(self.input), self.locale, self.options):
                    segment = String(segment)
                    yield {'segment': segment, 'index': index, 'input': s}
                    index += segment.length
    
        elif self.granularity == 'word':
            if Segmenter.custom_word is None:
                s = String(self.input)
                index = 0
                for _, c in word_bounds(str(self.input)):
                    segment = String(c)
                    yield {'segment': segment, 'index': index, 'input': s, 'isWordLike': is_word_like(c)}
                    index += segment.length
            else:
                s = String(self.input)
                index = 0
                for res in Segmenter.custom_word(str(self.input), self.locale, self.options):
                    if isinstance(res, str):
                        _is_word_like = is_word_like(res)
                        segment = String(res)
                    elif isinstance(res, tuple):
                        _is_word_like = is_word_like(res[0]) if res[1] is None else res[1]
                        segment = String(res[0])
                    yield {'segment': segment, 'index': index, 'input': s, 'isWordLike': _is_word_like}
                    index += segment.length
    
    # @see https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter/segment/Segments/containing
    def containing(self, codeUnitIndex=0):
        offset = 0
        if self.granularity == 'grapheme':
            if Segmenter.custom_grapheme is None:
                for x in graphemeSegments(self.input):
                    offset += x['segment'].length
                    if codeUnitIndex < offset:
                        return x
            else:
                for segment in Segmenter.custom_grapheme(str(self.input), self.locale, self.options):
                    segment = String(segment)
                    offset += segment.length
                    if codeUnitIndex < offset:
                        return {'segment': segment, 'index': offset - segment.length, 'input': String(self.input)}
                    
        elif self.granularity == 'word':
            if Segmenter.custom_word is None:
                for _, c in word_bounds(str(self.input)):
                    segment = String(c)
                    offset += segment.length
                    if codeUnitIndex < offset:
                        return {'segment': segment, 'index': offset - segment.length, 'input': String(self.input), 'isWordLike': is_word_like(c)}
            else:
                for res in Segmenter.custom_word(str(self.input), self.locale, self.options):
                    if isinstance(res, str):
                        _is_word_like = is_word_like(res)
                        segment = String(res)
                    elif isinstance(res, tuple):
                        _is_word_like = is_word_like(res[0]) if res[1] is None else res[1]
                        segment = String(res[0])
                    offset += segment.length
                    if codeUnitIndex < offset:
                        return {'segment': segment, 'index': offset - segment.length, 'input': String(self.input), 'isWordLike': _is_word_like}
        return None  # undefined


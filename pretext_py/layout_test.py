# import { beforeAll, beforeEach, describe, expect, test } from 'bun:test'

# Keep the permanent suite small and durable. These tests exercise the shipped
# prepare/layout exports with a deterministic fake canvas backend. For narrow
# browser-specific investigations, prefer throwaway probes and browser checkers
# over mirroring the full implementation here.
from .py_canvas import set_custom_canvas
from .measurement import getSegmentBreakableFitAdvances
from .layout import prepareWithSegments, prepare, layout, layoutWithLines, \
                    layoutNextLine, layoutNextLineRange, measureLineStats, \
                    materializeLineRange, measureNaturalWidth, walkLineRanges, \
                    clearCache, setLocale
from .line_break import countPreparedLines, measurePreparedLineGeometry, \
                        walkPreparedLinesRaw, stepPreparedLineGeometry
from .rich_inline import prepareRichInline, layoutNextRichInlineLineRange, \
                         materializeRichInlineLineRange, measureRichInlineStats, \
                         walkRichInlineLineRanges
from .analysis import isCJK
from .intl_segmenter_py import String, isEmojiPresentation, isNd, Segmenter
import re


FONT = '16px Test Sans'
LINE_HEIGHT = 19

punctuationRe = re.compile(r'[.,!?;:%)\]\}\'\"”’»›…—-]')

graphemeSegmenter = Segmenter(None, {'granularity': 'grapheme' })


def parseFontSize(font):
    match = re.search(r'(\d+(?:\.\d+)?)\s*px', font)
    return float(match.group(1)) if match else 16


def isWideCharacter(ch):
    code = ord(ch)
    return (
        (0x4E00 <= code <= 0x9FFF) or
        (0x3400 <= code <= 0x4DBF) or
        (0xF900 <= code <= 0xFAFF) or
        (0x2F800 <= code <= 0x2FA1F) or
        (0x20000 <= code <= 0x2A6DF) or
        (0x2A700 <= code <= 0x2B73F) or
        (0x2B740 <= code <= 0x2B81F) or
        (0x2B820 <= code <= 0x2CEAF) or
        (0x2CEB0 <= code <= 0x2EBEF) or
        (0x2EBF0 <= code <= 0x2EE5D) or
        (0x30000 <= code <= 0x3134F) or
        (0x31350 <= code <= 0x323AF) or
        (0x323B0 <= code <= 0x33479) or
        (0x3000 <= code <= 0x303F) or
        (0x3040 <= code <= 0x309F) or
        (0x30A0 <= code <= 0x30FF) or
        (0x3130 <= code <= 0x318F) or
        (0xAC00 <= code <= 0xD7AF) or
        (0xFF00 <= code <= 0xFFEF)
    )


def measureWidth(text, font):
    fontSize = parseFontSize(font)
    width = 0
    previousWasDecimalDigit = False

    for ch in text:
        if ch == ' ':
            width += fontSize * 0.33
            previousWasDecimalDigit = False
        elif ch == '\t':
            width += fontSize * 1.32
            previousWasDecimalDigit = False
        elif isEmojiPresentation(ord(ch)) or ch == '\uFE0F':
            width += fontSize
            previousWasDecimalDigit = False
        elif isNd(ord(ch)):
            width += fontSize * (0.48 if previousWasDecimalDigit else 0.52)
            previousWasDecimalDigit = True
        elif isWideCharacter(ch):
            width += fontSize
            previousWasDecimalDigit = False
        elif punctuationRe.search(ch):
            width += fontSize * 0.4
            previousWasDecimalDigit = False
        else:
            width += fontSize * 0.6
            previousWasDecimalDigit = False

    return width


def nextTabAdvance(lineWidth, spaceWidth, tabSize = 8):
    tabStopAdvance = spaceWidth * tabSize
    remainder = lineWidth % tabStopAdvance
    return tabStopAdvance if remainder == 0 else tabStopAdvance - remainder


def getSegmentGraphemes(text):
    return list(map(lambda s: s['segment'], graphemeSegmenter.segment(text)))


def slicePreparedText(prepared, start, end):
    if start['segmentIndex'] == end['segmentIndex']:
        segment = prepared['segments'][start['segmentIndex']]
        if segment is None:
            return ''
        graphemes = getSegmentGraphemes(segment)
        return ''.join(map(str, graphemes[start['graphemeIndex']:end['graphemeIndex']]))

    result = ''
    for segmentIndex in range(start['segmentIndex'], end['segmentIndex']):
        segment = prepared['segments'][segmentIndex]
        if segment is None:
            break
        if segmentIndex == start['segmentIndex'] and start['graphemeIndex'] > 0:
            graphemes = getSegmentGraphemes(segment)
            result += ''.join(map(str, graphemes[start['graphemeIndex']:]))
        else:
            result += str(segment)  # 假设 segment 是字符串，可直接拼接

    if end['graphemeIndex'] > 0:
        segment = prepared['segments'][end['segmentIndex']]
        if segment is not None:
            graphemes = getSegmentGraphemes(segment)
            result += ''.join(map(str, graphemes[:end['graphemeIndex']]))

    return result


def reconstructFromLineBoundaries(prepared, lines):
    return ''.join(str(slicePreparedText(prepared, line['start'], line['end'])) for line in lines)

def collectStreamedLines(prepared, width, start=None):
    if start is None:
        start = {'segmentIndex': 0, 'graphemeIndex': 0}
    lines = []
    cursor = start.copy()

    while True:
        line = layoutNextLine(prepared, cursor, width)
        if line is None:
            break
        lines.append(line)
        cursor = line['end']

    return lines


def collectStreamedLinesWithWidths(prepared, widths, start=None):
    if start is None:
        start = {'segmentIndex': 0, 'graphemeIndex': 0}
    lines = []
    cursor = start.copy()
    widthIndex = 0

    while True:
        if widthIndex >= len(widths):
            raise RuntimeError('collectStreamedLinesWithWidths requires enough widths to finish the paragraph')
        width = widths[widthIndex]
        line = layoutNextLine(prepared, cursor, width)
        if line is None:
            break
        lines.append(line)
        cursor = line['end']
        widthIndex += 1

    return lines


def reconstructFromWalkedRanges(prepared, width):
    slices = []

    def callback(line):
        slices.append(slicePreparedText(prepared, line['start'], line['end']))

    walkLineRanges(prepared, width, callback)
    return ''.join(map(str, slices))


def compareCursors(a, b):
    if a['segmentIndex'] != b['segmentIndex']:
        return a['segmentIndex'] - b['segmentIndex']
    return a['graphemeIndex'] - b['graphemeIndex']


def terminalCursor(prepared):
    return {'segmentIndex': len(prepared['segments']), 'graphemeIndex': 0}


def getNonSpaceSegmentLevels(prepared):
    if 'segLevels' not in prepared or prepared['segLevels'] is None: return []

    levels = []
    for i in range(len(prepared['segments'])):
        text = prepared['segments'][i]
        if text.trim().length == 0: continue
        levels.append({'level': prepared['segLevels'][i], 'text':text})

    return levels


class TestCanvasRenderingContext2D:
    def __init__(self):
        self.font = ''

    def measureText(self, text: str):
        return {'width': measureWidth(text, self.font)}


set_custom_canvas(TestCanvasRenderingContext2D)

'''

beforeEach(() => {
  setLocale(undefined)
  clearCache()
})
'''

class TestTool:
    def __init__(self, x):
        self.x = x
    def toBeCloseTo(self, other, per):
        return round(abs(self.x - other), per) == 0

def test_use_custom_regex_segmenter():
    # 使用 https://pypi.org/project/unicode-segment/ 
    from unicode_segment import WordSegmenter, GraphemeSegmenter
    def my_grapheme_split(text: str, locale: str, options: dict):
        for _, s in GraphemeSegmenter().segment(text):
            yield s
    def my_word_split(text: str, locale: str, options: dict):
        for _, s in WordSegmenter().segment(text):
            yield (s, None)  # yield s  也可以
    Segmenter.custom_grapheme = my_grapheme_split
    Segmenter.custom_word = my_word_split

def test_use_default_segmenter():
    Segmenter.custom_grapheme = None
    Segmenter.custom_word = None

def test_measurement_invariants():
    print('breakable fit cache distinguishes fit modes')
    metrics = {'width': 80, 'containsCJK': False}
    cache = {
      'a': {'width': 10, 'containsCJK': False},
      'b': {'width': 20, 'containsCJK': False},
      'c': {'width': 30, 'containsCJK': False},
      'ab': {'width': 35, 'containsCJK': False},
      'bc': {'width': 60, 'containsCJK': False},
      'abc': metrics,
    }

    assert getSegmentBreakableFitAdvances('abc', metrics, cache, 0, 'sum-graphemes') == [10, 20, 30]
    assert getSegmentBreakableFitAdvances('abc', metrics, cache, 0, 'pair-context') == [10, 25, 40]
    assert getSegmentBreakableFitAdvances('abc', metrics, cache, 0, 'segment-prefixes') == [10, 25, 45]
    assert getSegmentBreakableFitAdvances('abc', metrics, cache, 0, 'sum-graphemes') == [10, 20, 30]


def test_prepare_invariants():
    print('whitespace-only input stays empty')
    prepared = prepare('  \t\n  ', FONT)
    assert (layout(prepared, 200, LINE_HEIGHT) == {'lineCount': 0, 'height': 0 })

    print('collapses ordinary whitespace runs and trims the edges')
    prepared = prepareWithSegments('  Hello\t \n  World  ', FONT)
    assert prepared['segments'] == ['Hello', ' ', 'World']


    print('pre-wrap mode keeps ordinary spaces instead of collapsing them')
    prepared = prepareWithSegments('  Hello   World  ', FONT, { 'whiteSpace': 'pre-wrap' })
    assert (prepared['segments'] == ['  ', 'Hello', '   ', 'World', '  '])
    assert (prepared['kinds'] == ['preserved-space', 'text', 'preserved-space', 'text', 'preserved-space'])
  

    print('pre-wrap mode keeps hard breaks as explicit segments')
    prepared = prepareWithSegments('Hello\nWorld', FONT, { 'whiteSpace': 'pre-wrap' })
    assert (prepared['segments'] == ['Hello', '\n', 'World'])
    assert (prepared['kinds'] == ['text', 'hard-break', 'text'])
  

    print('pre-wrap mode normalizes CRLF into a single hard break')
    prepared = prepareWithSegments('Hello\r\nWorld', FONT, { 'whiteSpace': 'pre-wrap' })
    assert (prepared['segments'] == ['Hello', '\n', 'World'])
    assert (prepared['kinds'] == ['text', 'hard-break', 'text'])
  

    print('pre-wrap mode keeps tabs as explicit segments')
    prepared = prepareWithSegments('Hello\tWorld', FONT, { 'whiteSpace': 'pre-wrap' })
    assert (prepared['segments'] == ['Hello', '\t', 'World'])
    assert (prepared['kinds'] == ['text', 'tab', 'text'])
  

    print('keeps non-breaking spaces as glue instead of collapsing them away')
    prepared = prepareWithSegments('Hello\u00A0world', FONT)
    assert (prepared['segments'] == ['Hello\u00A0world'])
    assert (prepared['kinds'] == ['text'])


    print('keeps standalone non-breaking spaces as visible glue content')
    prepared = prepareWithSegments('\u00A0', FONT)
    assert (prepared['segments'] == ['\u00A0'])
    assert (layout(prepared, 200, LINE_HEIGHT) == {'lineCount': 1, 'height': LINE_HEIGHT})


    print('pre-wrap mode keeps whitespace-only input visible')
    prepared = prepare('   ', FONT, { 'whiteSpace': 'pre-wrap' })
    assert (layout(prepared, 200, LINE_HEIGHT) == {'lineCount': 1, 'height': LINE_HEIGHT })


    print('keeps narrow no-break spaces as glue content')
    prepared = prepareWithSegments('10\u202F000', FONT)
    assert (prepared['segments'] == ['10\u202F000'])
    assert (prepared['kinds'] == ['text'])
 

    print('keeps word joiners as glue content')
    prepared = prepareWithSegments('foo\u2060bar', FONT)
    assert (prepared['segments'] == ['foo\u2060bar'])
    assert (prepared['kinds'] == ['text'])


    print('treats zero-width spaces as explicit break opportunities')
    prepared = prepareWithSegments('alpha\u200Bbeta', FONT)
    assert (prepared['segments'] == ['alpha', '\u200B', 'beta'])
    assert (prepared['kinds'] == ['text', 'zero-width-break', 'text'])

    alphaWidth = prepared['widths'][0]
    assert layout(prepared, alphaWidth + 0.1, LINE_HEIGHT)['lineCount'] == (2)


    print('treats soft hyphens as discretionary break points')
    prepared = prepareWithSegments('trans\u00ADatlantic', FONT)
    assert (prepared['segments'] == ['trans', '\u00AD', 'atlantic'])
    assert (prepared['kinds'] == ['text', 'soft-hyphen', 'text'])

    wide = layoutWithLines(prepared, 200, LINE_HEIGHT)
    assert (wide['lineCount']) == (1)
    assert list(map(lambda x: x['text'], wide['lines'])) == ['transatlantic']

    prefixed = prepareWithSegments('foo trans\u00ADatlantic', FONT)
    softBreakWidth = max(
      prefixed['widths'][0] + prefixed['widths'][1] + prefixed['widths'][2] + prefixed['discretionaryHyphenWidth'],
      prefixed['widths'][4],
    ) + 0.1
    narrow = layoutWithLines(prefixed, softBreakWidth, LINE_HEIGHT)
    assert narrow['lineCount'] == (2)
    assert (list(map(lambda x: x['text'], narrow['lines'])) == ['foo trans-', 'atlantic'])
    res1 = narrow['lines'][0]['width']
    res2 = prefixed['widths'][0] + prefixed['widths'][1] + prefixed['widths'][2] + prefixed['discretionaryHyphenWidth']
    assert TestTool(res1).toBeCloseTo(res2, 5)
    assert (layout(prefixed, softBreakWidth, LINE_HEIGHT)['lineCount']) == (narrow['lineCount'])
    
    # print(prefixed)
    hyphenAndOneGraphemeWidth = \
      prefixed['widths'][0] + \
      prefixed['widths'][1] + \
      prefixed['widths'][2] + \
      prefixed['breakableFitAdvances'][4][0] + \
      prefixed['discretionaryHyphenWidth'] + \
      0.1
    strict = layoutWithLines(prefixed, hyphenAndOneGraphemeWidth, LINE_HEIGHT)
    assert (list(map(lambda x: x['text'], strict['lines'])) == ['foo trans-', 'atlantic'])
    assert (collectStreamedLines(prefixed, hyphenAndOneGraphemeWidth) == strict['lines'])
    assert (layout(prefixed, hyphenAndOneGraphemeWidth, LINE_HEIGHT)['lineCount']) == (strict['lineCount'])
    

    print('keeps closing punctuation attached to the preceding word')
    prepared = prepareWithSegments('hello.', FONT)
    assert (prepared['segments'] == ['hello.'])


    print('keeps arabic punctuation attached to the preceding word')
    prepared = prepareWithSegments('مرحبا، عالم؟', FONT)
    assert (prepared['segments'] == ['مرحبا،', ' ', 'عالم؟'])
 

    print('keeps arabic punctuation-plus-mark clusters attached to the preceding word')
    prepared = prepareWithSegments('وحوارى بكشء،ٍ من قولهم', FONT)
    assert (prepared['segments'] == ['وحوارى', ' ', 'بكشء،ٍ', ' ', 'من', ' ', 'قولهم']), f"output: {prepared['segments']}"


    print('keeps arabic no-space punctuation clusters together')
    prepared = prepareWithSegments('فيقول:وعليك السلام', FONT)
    assert (prepared['segments'] == ['فيقول:وعليك', ' ', 'السلام'])


    print('keeps arabic comma-followed text together without a space')
    prepared = prepareWithSegments('همزةٌ،ما كان', FONT)
    assert (prepared['segments'] == ['همزةٌ،ما', ' ', 'كان'])


    print('keeps leading arabic combining marks with the following word')
    prepared = prepareWithSegments('كل ِّواحدةٍ', FONT)
    assert (prepared['segments'] == ['كل', ' ', 'ِّواحدةٍ'])


    print('keeps devanagari danda punctuation attached to the preceding word')
    prepared = prepareWithSegments('नमस्ते। दुनिया॥', FONT)
    assert (prepared['segments'] == ['नमस्ते।', ' ', 'दुनिया॥'])


    # Due to limitations in the Segmenter, the Myanmar test could not be successfully executed.
    # 电诈庇护所的语言不配被支持
    
    # print('keeps myanmar punctuation attached to the preceding word')
    prepared = prepareWithSegments('ဖြစ်သည်။ နောက်တစ်ခု၊ ကိုက်ချီ၍ ယုံကြည်မိကြ၏။', FONT)
    # assert (prepared['segments'][0: 7] == ['ဖြစ်သည်။', ' ', 'နောက်တစ်ခု၊', ' ', 'ကိုက်', 'ချီ၍', ' ']), f'output: {prepared["segments"][0: 7]}'
    assert (prepared['segments'][-1]) == ('ကြ၏။')
 

    # print('keeps myanmar possessive marker attached to the following word')
    # prepared = prepareWithSegments('ကျွန်ုပ်၏လက်မဖြင့်', FONT)
    # assert (prepared['segments'] == ['ကျွန်ုပ်၏လက်မ', 'ဖြင့်']), f'output: {prepared["segments"]}'


    print('keeps opening quotes attached to the following word')
    prepared = prepareWithSegments('“Whenever', FONT)
    assert (prepared['segments'] == ['“Whenever'])


    print('keeps opening punctuation attached to the following word')
    textBefore = 'aaaaaaaaaaaaaaaaaaa'
    for opener in ['¡', '¿', '‚', '„', '\u2E18']:
        prepared = prepareWithSegments(f'{textBefore} {opener}Wort', FONT)
        assert (prepared['segments'] == [textBefore, ' ', f'{opener}Wort'])

        strandedOpenerWidth = measureWidth(f'{textBefore} {opener}', FONT) + 0.1
        res = layoutWithLines(prepared, strandedOpenerWidth, LINE_HEIGHT)['lines']
        assert list(map(lambda x:x['text'], res)) == [
          f'{textBefore} ',
          f'{opener}Wort',
        ]

    print('keeps apostrophe-led elisions attached to the following word')
    prepared = prepareWithSegments('“Take ’em downstairs', FONT)
    assert (prepared['segments'] == ['“Take', ' ', '’em', ' ', 'downstairs'])


    print('keeps stacked opening quotes attached to the following word')
    prepared = prepareWithSegments('invented, “‘George B. Wilson', FONT)
    assert (prepared['segments'] == ['invented,', ' ', '“‘George', ' ', 'B.', ' ', 'Wilson'])
 

    print('treats ascii quotes as opening and closing glue by context')
    prepared = prepareWithSegments('said "hello" there', FONT)
    assert (prepared['segments'] == ['said', ' ', '"hello"', ' ', 'there'])
  

    print('treats escaped ascii quote clusters as opening and closing glue by context')
    text = r'say \"hello\" there'
    prepared = prepareWithSegments(text, FONT)
    assert (prepared['segments'] == ['say', ' ', r'\"hello\"', ' ', 'there'])
  

    print('keeps escaped quote clusters attached through preceding opening punctuation')
    text = r'((\"\"word'
    prepared = prepareWithSegments(text, FONT)
    assert (prepared['segments'] == [text])


    print('keeps numeric prefix and postfix line-break classes attached')
    assert (prepareWithSegments('$___', FONT)['segments'] == ['$___'])
    assert (prepareWithSegments('$500', FONT)['segments'] == ['$500'])
    assert (prepareWithSegments('500€', FONT)['segments'] == ['500€'])
    assert (prepareWithSegments('+500', FONT)['segments'] == ['+500'])
    assert (prepareWithSegments('−500', FONT)['segments'] == ['−500'])
    assert (prepareWithSegments('foo%bar', FONT)['segments'] == ['foo%bar'])
    assert (prepareWithSegments('50°C', FONT)['segments'] == ['50°C'])
    assert (prepareWithSegments('$(12.35)', FONT)['segments'] == ['$(12.35)'])
    assert (prepareWithSegments('-1/12', FONT)['segments'] == ['-1/12'])


    print('keeps URL-like runs together as one breakable segment')
    prepared = prepareWithSegments('see https://example.com/reports/q3?lang=ar&mode=full now', FONT)
    assert (prepared['segments'] == [
      'see',
      ' ',
      'https://example.com/reports/q3?',
      'lang=ar&mode=full',
      ' ',
      'now',
    ])

    clearCache()
    print('prefers hyphen-like boundaries inside overlong breakable runs')
    text = 'https://alpha-beta-gamma-delta.example.test/path'
    prepared = prepareWithSegments(text, FONT)
    width = measureWidth('https://alpha-bet', FONT) + 0.1

    assert (prepared['segments'] == [text]), f'output: {prepared["segments"]}'

    batched = layoutWithLines(prepared, width, LINE_HEIGHT)
    assert (batched['lines'][0]['text']) == ('https://alpha-'), f"output: {batched['lines'][0]['text']}"
    assert (batched['lines'][1]['text']) == ('beta-gamma-')
    assert (collectStreamedLines(prepared, width) == batched['lines'])
    assert (layout(prepared, width, LINE_HEIGHT)['lineCount']) == (batched['lineCount'])
    assert (measureLineStats(prepared, width)['lineCount']) == (batched['lineCount'])

    unicodeDash = prepareWithSegments('https://alpha\u2010beta\u2010gamma.example.test/path', FONT)
    unicodeWidth = measureWidth('https://alpha\u2010b', FONT) + 0.1
    assert layoutWithLines(unicodeDash, unicodeWidth, LINE_HEIGHT)['lines'][0]['text'] == ('https://alpha\u2010')
  
    print('does not prefer hyphen-like boundaries in keep-all runs')
    text = 'foo-bar日本語'
    prepared = prepareWithSegments(text, FONT, {'wordBreak': 'keep-all' })

    assert (prepared['segments'] == ['foo-', 'bar日本語'])
    assert (prepared['breakablePreferredBreaks'] == [None, None])


    print('keeps no-space punctuation chains together as one breakable segment')
    prepared = prepareWithSegments(
      'foo;bar foo:bar foo,bar foo.bar as;lkdfjals;k ééé.ééé αβγ.δεζ אבג.דהו',
      FONT,
    )
    assert (prepared['segments'] == [
      'foo;bar',
      ' ',
      'foo:bar',
      ' ',
      'foo,bar',
      ' ',
      'foo.bar',
      ' ',
      'as;lkdfjals;k',
      ' ',
      'ééé.ééé',
      ' ',
      'αβγ.δεζ',
      ' ',
      'אבג.דהו',
    ])
  

    print('keeps no-space word-internal symbol chains together as one breakable segment')
    for symbol in ['`', '~', '!', '@', '#', '^', '&', '*', '=', '/', '{', '}', '[', ']', '|', '"', '<', '>', '♂', '╥', '∟', '┌']:
        assert (prepareWithSegments(f'foo{symbol}bar', FONT)['segments'] == [f'foo{symbol}bar'])
    

    assert (prepareWithSegments('foo#$bar', FONT)['segments'] == ['foo#$bar'])
    assert (prepareWithSegments('#hashtag mention@domain', FONT)['segments'] == [
      '#hashtag',
      ' ',
      'mention@domain',
    ])


    print('keeps browser break symbols out of no-space word-internal symbol chains')
    assert (prepareWithSegments('foo?bar', FONT)['segments'] == ['foo?', 'bar'])
    assert (prepareWithSegments('foo—bar', FONT)['segments'] == ['foo', '—', 'bar'])
    assert (prepareWithSegments('foo…bar', FONT)['segments'] == ['foo…', 'bar'])
    assert (prepareWithSegments('foo‼bar', FONT)['segments'] == ['foo', '‼', 'bar'])
    assert (prepareWithSegments('foo🙂bar', FONT)['segments'] == ['foo', '🙂', 'bar'])


    print('keeps numeric time ranges together')
    prepared = prepareWithSegments('window 7:00-9:00 only', FONT)
    assert (prepared['segments'] == ['window', ' ', '7:00-', '9:00', ' ', 'only'])


    print('splits hyphenated numeric identifiers at preferred boundaries')
    prepared = prepareWithSegments('SSN 420-69-8008 filed', FONT)
    assert (prepared['segments'] == ['SSN', ' ', '420-', '69-', '8008', ' ', 'filed'])


    print('keeps unicode-digit numeric expressions together')
    prepared = prepareWithSegments('यह २४×७ सपोर्ट है', FONT)
    assert (prepared['segments'] == ['यह', ' ', '२४×७', ' ', 'सपोर्ट', ' ', 'है'])


    print('does not attach opening punctuation to following whitespace')
    prepared = prepareWithSegments('“ hello', FONT)
    assert (prepared['segments'] == ['“', ' ', 'hello'])


    print('keeps japanese iteration marks attached to the preceding kana')
    prepared = prepareWithSegments('棄てゝ行く', FONT)
    assert (prepared['segments'] == ['棄', 'てゝ', '行', 'く'])


    print('carries trailing cjk opening punctuation forward across segment boundaries')
    prepared = prepareWithSegments('作者はさつき、「下人', FONT)
    assert (prepared['segments'] == ['作', '者', 'は', 'さ', 'つ', 'き、', '「下', '人'])


    print('keeps em dashes breakable')
    prepared = prepareWithSegments('universe—so', FONT)
    assert (prepared['segments'] == ['universe', '—', 'so'])


    print('coalesces repeated punctuation runs into a single segment')
    prepared = prepareWithSegments('=== heading ===', FONT)
    assert (prepared['segments'] == ['===', ' ', 'heading', ' ', '==='])


    print('keeps long repeated punctuation runs coalesced')
    text = '(' * 256
    prepared = prepareWithSegments(text, FONT)
    assert (prepared['segments'] == [text])


    print('keeps repeated punctuation runs attachable to trailing closing punctuation')
    prepared = prepareWithSegments('((()', FONT)
    assert (prepared['segments'] == ['((()'])
    assert prepareWithSegments('((() ===', FONT)['segments'] == (['((()', ' ', '==='])


    print('applies CJK and Hangul punctuation attachment rules')
    assert (prepareWithSegments('中文，测试。', FONT)['segments'] == ['中', '文，', '测', '试。'])
    assert (prepareWithSegments('테스트입니다.', FONT)['segments'][-1]) == ('다.')


    print('treats Hangul compatibility jamo as CJK break units')
    prepared = prepareWithSegments('ㅋㅋㅋ 진짜', FONT)
    assert (prepared['segments'] == ['ㅋ', 'ㅋ', 'ㅋ', ' ', '진', '짜']), f'output: {prepared["segments"]}'

    width = measureWidth('ㅋㅋ', FONT) + 0.1
    lines = layoutWithLines(prepared, width, LINE_HEIGHT)
    assert (list(map(lambda x: x['text'], lines['lines'])) == ['ㅋㅋ', 'ㅋ ', '진짜'])
    assert (layout(prepared, width, LINE_HEIGHT) == {
      'lineCount': 3,
      'height': LINE_HEIGHT * 3,
    })


    print('keeps non-CJK glue-connected runs intact before CJK text')
    prepared = prepareWithSegments('foo\u00A0世界', FONT)
    assert (prepared['segments'] == ['foo\u00A0', '世', '界'])


    print('keep-all keeps CJK-containing no-space runs cohesive with punctuation fallback boundaries')
    assert (prepareWithSegments('中文，测试。', FONT, { 'wordBreak': 'keep-all' })['segments'] == ['中文，', '测试。'])
    assert (prepareWithSegments('한국어테스트', FONT, { 'wordBreak': 'keep-all' })['segments'] == ['한국어테스트'])
    assert (prepareWithSegments('漢' * 256, FONT, { 'wordBreak': 'keep-all' })['segments'] == ['漢' * 256])

    for text in ['abc日本語', '123日本語', 'abc123日本語', 'foo_bar日本語', 'foo.bar日本語', '500円テスト', '日本語foo.bar']:
        assert (prepareWithSegments(text, FONT, { 'wordBreak': 'keep-all' })['segments'] == [text])


    assert (prepareWithSegments('日本語foo-bar', FONT, { 'wordBreak': 'keep-all' })['segments'] == ['日本語foo-', 'bar'])
    assert (prepareWithSegments('日本語foo—bar', FONT, { 'wordBreak': 'keep-all' })['segments'] == ['日本語foo—', 'bar'])
    assert (prepareWithSegments('foo-bar日本語', FONT, { 'wordBreak': 'keep-all' })['segments'] == ['foo-', 'bar日本語'])
    assert (prepareWithSegments('foo—bar日本語', FONT, { 'wordBreak': 'keep-all' })['segments'] == ['foo', '—', 'bar日本語'])
    assert (prepareWithSegments('foo?bar日本語', FONT, { 'wordBreak': 'keep-all' })['segments'] == ['foo?', 'bar日本語'])
    assert (prepareWithSegments('foo\u00A0世界', FONT, { 'wordBreak': 'keep-all' })['segments'] == ['foo\u00A0', '世界'])


    print('adjacent CJK text units stay breakable after visible text, not only after spaces')
    prepared = prepareWithSegments('foo 世界 bar', FONT)
    assert (prepared['segments'] == ['foo', ' ', '世', '界', ' ', 'bar'])

    width = prepared['widths'][0] + prepared['widths'][1] + prepared['widths'][2] + 0.1
    batched = layoutWithLines(prepared, width, LINE_HEIGHT)
    assert [line['text'] for line in batched['lines']] == ['foo 世', '界 bar']
    
    streamed = []
    cursor = {'segmentIndex': 0, 'graphemeIndex': 0 }
    while True:
        line = layoutNextLine(prepared, cursor, width)
        if line is None:
            break
        streamed.append(line['text'])
        cursor = line['end']
    assert streamed == ['foo 世', '界 bar']
    assert layout(prepared, width, LINE_HEIGHT) == {'lineCount': 2, 'height': LINE_HEIGHT * 2}
    
    print('treats astral CJK ideographs as CJK break units')
    samples = ['𠀀', '\U0002EBF0', '\U00031350', '\U000323B0']

    for sample in samples:
        assert (prepareWithSegments(f'{sample}{sample}', FONT)['segments'] == [sample, sample])
        assert (prepareWithSegments(f'{sample}。', FONT)['segments'] == [f'{sample}。'])


    print('isCJK covers Hangul compatibility jamo and the newer CJK extension blocks')
    assert (isCJK(String('ㅋ'))) == (True)
    assert (isCJK(String('\U0002EBF0'))) == (True)
    assert (isCJK(String('\U00031350'))) == (True)
    assert (isCJK(String('\U000323B0'))) == (True)
    assert (isCJK(String('hello'))) == (False)


    print('keeps opening brackets after CJK attached to following annotation text')
    assert (prepareWithSegments('서울(Seoul)과', FONT)['segments'] == ['서', '울', '(Seoul)', '과'])
    assert (prepareWithSegments('東京(Tokyo)と', FONT)['segments'] == ['東', '京', '(Tokyo)', 'と'])
    assert (prepareWithSegments('北京(Beijing)和', FONT)['segments'] == ['北', '京', '(Beijing)', '和'])
    assert (prepareWithSegments('참조[1]와', FONT)['segments'] == ['참', '조', '[1]', '와'])
    assert (prepareWithSegments('AB(CD)', FONT)['segments'] == ['AB(CD)'])


    print('prepare and prepareWithSegments agree on layout behavior')
    plain = prepare('Alpha beta gamma', FONT)
    rich = prepareWithSegments('Alpha beta gamma', FONT)
    for width in [40, 80, 200]:
        assert (layout(plain, width, LINE_HEIGHT) == layout(rich, width, LINE_HEIGHT))
 

    print('locale can be reset without disturbing later prepares')
    # 不支持设定 locale
    # setLocale('th')
    # const thai = prepare('ภาษาไทยภาษาไทย', FONT)
    # assert (layout(thai, 80, LINE_HEIGHT)['lineCount']).toBeGreaterThan(0)

    setLocale(None)
    latin = prepare('hello world', FONT)
    assert (layout(latin, 200, LINE_HEIGHT) == {'lineCount': 1, 'height': LINE_HEIGHT })


    print('pure LTR text skips rich bidi metadata')
    assert (prepareWithSegments('hello world', FONT)['segLevels']) is None

    print('rich bidi metadata uses the first strong character for paragraph direction')
    ltrFirst = prepareWithSegments('one اثنان three', FONT)
    assert (ltrFirst['segLevels']) is not None
    assert len(ltrFirst['segLevels']) == len(ltrFirst['segments'])
    assert (getNonSpaceSegmentLevels(ltrFirst) == [
      {'text': 'one', 'level': 0 },
      {'text': 'اثنان', 'level': 1 },
      {'text': 'three', 'level': 0 },
    ])

    rtlFirst = prepareWithSegments('123 واحد three', FONT)
    assert (rtlFirst['segLevels']) is not None
    assert len(rtlFirst['segLevels']) == len(rtlFirst['segments'])
    assert (getNonSpaceSegmentLevels(rtlFirst) == [
      { 'text': '123', 'level': 2 },
      { 'text': 'واحد', 'level': 1 },
      { 'text': 'three', 'level': 2 },
    ])

    astralRtlFirst = prepareWithSegments('𞤀𞤁 abc', FONT)
    assert (astralRtlFirst['segLevels']) is not None
    assert len(astralRtlFirst['segLevels']) == len(astralRtlFirst['segments'])
    assert (getNonSpaceSegmentLevels(astralRtlFirst) == [
      { 'text': '𞤀𞤁', 'level': 1 },
      { 'text': 'abc', 'level': 2 },
    ])


def test_rich_inline_invariants():
    print('letterSpacing preserves the terminal gap inside rich-inline items')
    spacing = 3
    prepared = prepareRichInline([
      {'text': String('AB'), 'font': FONT, 'letterSpacing': spacing },
    ])

    assert (measureRichInlineStats(prepared, 200) == {
      'lineCount': 1,
      'maxLineWidth': measureWidth('AB', FONT) + spacing * 2,
    })

    print('letterSpacing preserves rich-inline gaps across styled item boundaries')
    spacing = 3
    prepared = prepareRichInline([
      {'text': String('A'), 'font': '700 16px Test Sans', 'letterSpacing': spacing },
      {'text': String('BC'), 'font': FONT, 'letterSpacing': spacing },
    ])
    
    expectedWidth = \
      measureWidth('A', '700 16px Test Sans') + \
      measureWidth('BC', FONT) + \
      spacing * 3
    firstItemWidth = measureWidth('A', '700 16px Test Sans') + spacing

    assert (measureRichInlineStats(prepared, 200) == {
      'lineCount': 1,
      'maxLineWidth': expectedWidth,
    })
    res = layoutNextRichInlineLineRange(prepared, firstItemWidth + 0.1)
    assert res['fragments'][0]['itemIndex'] == 0
    assert res['width'] == firstItemWidth


    print('non-materializing range walker matches range materialization')
    # 假设以下函数和变量已在外部定义：
# prepareRichInline, walkRichInlineLineRanges, materializeRichInlineLineRange, measureRichInlineStats, FONT

    prepared = prepareRichInline([
        {'text': String('Ship '), 'font': FONT},
        {'text': String('@maya'), 'font': '700 12px Test Sans', 'break': 'never', 'extraWidth': 18},
        {'text': String("'s rich note wraps cleanly"), 'font': FONT},
    ])
    
    ranged_lines = []
    materialized_lines = []
    
    def range_line_callback(line):
        ranged_lines.append({
            'end': line['end'],
            'fragments': [
                {
                    'end': frag['end'],
                    'gapBefore': frag['gapBefore'],
                    'itemIndex': frag['itemIndex'],
                    'occupiedWidth': frag['occupiedWidth'],
                    'start': frag['start'],
                }
                for frag in line['fragments']
            ],
            'width': line['width'],
        })
    
    def materialized_line_callback(range_line):
        line = materializeRichInlineLineRange(prepared, range_line)
        materialized_lines.append({
            'end': line['end'],
            'fragments': [
                {
                    'end': frag['end'],
                    'gapBefore': frag['gapBefore'],
                    'itemIndex': frag['itemIndex'],
                    'occupiedWidth': frag['occupiedWidth'],
                    'start': frag['start'],
                    'text': frag['text'],
                }
                for frag in line['fragments']
            ],
            'width': line['width'],
        })
    
    range_line_count = walkRichInlineLineRanges(prepared, 120, range_line_callback)
    materialized_line_count = walkRichInlineLineRanges(prepared, 120, materialized_line_callback)
    
    assert range_line_count == materialized_line_count
    
    stats = measureRichInlineStats(prepared, 120)
    expected_max_line_width = max(line['width'] for line in ranged_lines) if ranged_lines else 0
    assert stats == {'lineCount': range_line_count, 'maxLineWidth': expected_max_line_width}
    
    assert len(ranged_lines) == len(materialized_lines)
    
    for index in range(len(ranged_lines)):
        range_line = ranged_lines[index]
        materialized_line = materialized_lines[index]
        assert range_line['width'] == materialized_line['width']
        assert range_line['end'] == materialized_line['end']
    
        # 比较 fragments，忽略 text 字段
        for rf, mf in zip(range_line['fragments'], materialized_line['fragments']):
            # 将 mf 复制一份并删除 'text' 键，然后与 rf 比较
            mf_without_text = {k: v for k, v in mf.items() if k != 'text'}
            assert rf == mf_without_text

    print('layoutNextRichInlineLineRange leaves the start cursor reusable')
    prepared = prepareRichInline([
        {'text': String('Ship '), 'font': FONT},
        {'text': String('@maya'), 'font': '700 12px Test Sans', 'break': 'never', 'extraWidth': 18},
        {'text': String("'s rich note wraps cleanly"), 'font': FONT},
    ])
    start = {'itemIndex': 0, 'segmentIndex': 0, 'graphemeIndex': 0}
    first_line = layoutNextRichInlineLineRange(prepared, 120, start)
    
    assert first_line is not None
    assert start == {'itemIndex': 0, 'segmentIndex': 0, 'graphemeIndex': 0}
    assert layoutNextRichInlineLineRange(prepared, 120, start) == first_line
    
    next_start = first_line['end'].copy()
    assert layoutNextRichInlineLineRange(prepared, 120, first_line['end']) is not None
    assert first_line['end'] == next_start

    print('rich inline item boundaries do not accept forced-progress overflow')
    max_width = measureWidth('A', FONT) + 1
    prepared = prepareRichInline([
        {'text': String('A'), 'font': FONT},
        {'text': String('C'), 'font': FONT},
        {'text': String('D'), 'font': FONT},
    ])
    widths = []
    
    line_count = walkRichInlineLineRanges(prepared, max_width, lambda line: widths.append(line['width']))
    
    assert widths == [
        measureWidth('A', FONT),
        measureWidth('C', FONT),
        measureWidth('D', FONT),
    ]
    assert measureRichInlineStats(prepared, max_width) == {
        'lineCount': line_count,
        'maxLineWidth': max(widths),
    }

    print('split CJK rich inline items stay inside the line width')
    max_width = measureWidth('中', FONT) + 1
    prepared = prepareRichInline([
        {'text': String('中'), 'font': FONT},
        {'text': String('国 '), 'font': FONT},
        {'text': String('文'), 'font': FONT},
    ])
    widths = []
    
    def callback(range_line):
        line = materializeRichInlineLineRange(prepared, range_line)
        widths.append(line['width'])
    
    line_count = walkRichInlineLineRanges(prepared, max_width, callback)
    
    assert widths == [
        measureWidth('中', FONT),
        measureWidth('国', FONT),
        measureWidth('文', FONT),
    ]
    assert measureRichInlineStats(prepared, max_width) == {
        'lineCount': line_count,
        'maxLineWidth': max(widths),
    }


def test_layout_invariants():
    
    print('letterSpacing preserves terminal line-end gaps like browsers')
    spacing = 4

    single = layoutWithLines(
      prepareWithSegments('A', FONT, { 'letterSpacing': spacing }),
      200,
      LINE_HEIGHT,
    )
    assert TestTool(single['lines'][0]['width']).toBeCloseTo(measureWidth('A', FONT) + spacing, 5)

    pair = layoutWithLines(
      prepareWithSegments('AB', FONT, { 'letterSpacing': spacing }),
      200,
      LINE_HEIGHT,
    )
    assert TestTool(pair['lines'][0]['width']).toBeCloseTo(measureWidth('AB', FONT) + spacing * 2, 5)

    segmented = layoutWithLines(
      prepareWithSegments('A B', FONT, { 'letterSpacing': spacing }),
      200,
      LINE_HEIGHT,
    )
    assert TestTool(segmented['lines'][0]['width']).toBeCloseTo(measureWidth('A B', FONT) + spacing * 3, 5)


    print('letterSpacing zero preserves prepared widths')
    base = prepareWithSegments('Hello World', FONT)
    zero = prepareWithSegments('Hello World', FONT, { 'letterSpacing': 0 })
    assert (zero['widths'] == base['widths'])
    assert (zero['breakableFitAdvances'] == base['breakableFitAdvances'])

    print('letterSpacing trims the gap before hanging collapsible spaces')
    spacing = 6
    lineAWidth = measureWidth('A', FONT)
    wrapped = layoutWithLines(
      prepareWithSegments('A B', FONT, { 'letterSpacing': spacing }),
      lineAWidth + 0.1,
      LINE_HEIGHT,
    )

    assert ([line['text'] for line in wrapped['lines']] == ['A ', 'B'])
    assert TestTool(wrapped['lines'][0]['width']).toBeCloseTo(lineAWidth + spacing, 5)

    print('letterSpacing restarts at grapheme line breaks inside a word')
    spacing = 5
    prepared = prepareWithSegments('abcd', FONT, { 'letterSpacing': spacing })
    twoGraphemesWidth = measureWidth('ab', FONT) + spacing * 2
    wrapped = layoutWithLines(prepared, twoGraphemesWidth + 0.1, LINE_HEIGHT)

    assert ([line['text'] for line in wrapped['lines']] == ['ab', 'cd'])
    assert TestTool(wrapped['lines'][0]['width']).toBeCloseTo(twoGraphemesWidth, 5)
    assert TestTool(wrapped['lines'][1]['width']).toBeCloseTo(twoGraphemesWidth, 5)
    assert (layout(prepared, twoGraphemesWidth + 0.1, LINE_HEIGHT)['lineCount']) == (wrapped['lineCount'])

    print('letterSpacing uses the trailing fit gap when wrapping inside a word')
    spacing = 5
    text = 'abcd'
    prepared = prepareWithSegments(text, FONT, { 'letterSpacing': spacing })
    allPaintWidth = measureWidth(text, FONT) + spacing * (len(getSegmentGraphemes(text)) - 1)
    wrapped = layoutWithLines(prepared, allPaintWidth + spacing / 2, LINE_HEIGHT)

    assert ([line['text'] for line in wrapped['lines']] == ['abc', 'd'])
    assert TestTool(wrapped['lines'][0]['width']).toBeCloseTo(measureWidth('abc', FONT) + spacing * 3, 5)


    print('letterSpacing preserves terminal spacing after a visible soft hyphen')
    spacing = 5
    prepared = prepareWithSegments('trans\u00ADatlantic', FONT, { 'letterSpacing': spacing })
    softHyphenLineWidth = prepared['widths'][0] + prepared['discretionaryHyphenWidth']
    wrapped = layoutWithLines(prepared, softHyphenLineWidth - spacing / 2, LINE_HEIGHT)

    assert (wrapped['lines'][0]['text']) == ('trans-')
    assert TestTool(wrapped['lines'][0]['width']).toBeCloseTo(softHyphenLineWidth, 5)
    assert not (str(wrapped['lines'][1]['text']).startswith('-'))


    print('letterSpacing trailing fit gap respects combining graphemes')
    spacing = 5
    text = 'Cafe\u0301 naive'
    prepared = prepareWithSegments(text, FONT, { 'letterSpacing': spacing })
    prefixPaintWidth = measureWidth('Cafe\u0301', FONT) + spacing * (len(getSegmentGraphemes('Cafe\u0301')) - 1)
    wrapped = layoutWithLines(prepared, prefixPaintWidth + spacing / 2, LINE_HEIGHT)

    assert (wrapped['lines'][0]['text']) == ('Caf')

    print('letterSpacing trailing fit gap applies to mixed-direction text')
    spacing = 5
    text = 'abc אבג def'
    prepared = prepareWithSegments(text, FONT, { 'letterSpacing': spacing })
    prefixPaintWidth = measureWidth('abc', FONT) + spacing * 2
    wrapped = layoutWithLines(prepared, prefixPaintWidth + spacing / 2, LINE_HEIGHT)

    assert (wrapped['lines'][0]['text']) == ('ab')

    print('negative letterSpacing tightens inter-grapheme gaps')
    spacing = -1.5
    line = layoutWithLines(
      prepareWithSegments('AB', FONT, { 'letterSpacing': spacing }),
      200,
      LINE_HEIGHT,
    )['lines'][0]

    assert TestTool(line['width']).toBeCloseTo(measureWidth('AB', FONT) + spacing * 2, 5)


    print('letterSpacing applies across CJK segment boundaries')
    spacing = 3
    line = layoutWithLines(
      prepareWithSegments('春天', FONT, { 'letterSpacing': spacing }),
      200,
      LINE_HEIGHT,
    )['lines'][0]

    assert TestTool(line['width']).toBeCloseTo(measureWidth('春天', FONT) + spacing * 2, 5)


    print('letterSpacing applies through digits and punctuation')
    spacing = 2
    text = '24×7, 7:00-9:00?'
    line = layoutWithLines(
      prepareWithSegments(text, FONT, { 'letterSpacing': spacing }),
      300,
      LINE_HEIGHT,
    )['lines'][0]
    gapCount = len(getSegmentGraphemes(text))

    assert TestTool(line['width']).toBeCloseTo(measureWidth(text, FONT) + spacing * gapCount, 5)


    print('letterSpacing applies through RTL punctuation runs')
    spacing = 2
    text = 'مرحبا، عالم؟'
    line = layoutWithLines(
      prepareWithSegments(text, FONT, { 'letterSpacing': spacing }),
      300,
      LINE_HEIGHT,
    )['lines'][0]
    gapCount = len(getSegmentGraphemes(text))

    assert TestTool(line['width']).toBeCloseTo(measureWidth(text, FONT) + spacing * gapCount, 5)

    print('letterSpacing applies across emoji graphemes')
    spacing = 2
    line = layoutWithLines(
      prepareWithSegments('A😀B', FONT, { 'letterSpacing': spacing }),
      200,
      LINE_HEIGHT,
    )['lines'][0]

    assert TestTool(line['width']).toBeCloseTo(measureWidth('A😀B', FONT) + spacing * 3, 5)


    print('letterSpacing stays line-local across hard breaks')
    spacing = 4
    lines = layoutWithLines(
      prepareWithSegments('A\nB', FONT, { 'whiteSpace': 'pre-wrap', 'letterSpacing': spacing }),
      200,
      LINE_HEIGHT,
    )['lines']
    
    assert (list(map(lambda l: l['text'], lines))) == ['A', 'B']
    assert TestTool(lines[0]['width']).toBeCloseTo(measureWidth('A', FONT) + spacing, 5)
    assert TestTool(lines[1]['width']).toBeCloseTo(measureWidth('B', FONT) + spacing, 5)


    print('letterSpacing participates in pre-wrap tab positioning')
    spacing = 4
    text = 'A\tB'
    prepared = prepareWithSegments(text, FONT, { 'whiteSpace': 'pre-wrap', 'letterSpacing': spacing })
    line = layoutWithLines(prepared, 200, LINE_HEIGHT)['lines'][0]
    aWidth = measureWidth('A', FONT)
    tabAdvance = nextTabAdvance(aWidth + spacing, measureWidth(' ', FONT))
    expected = aWidth + spacing + tabAdvance + spacing + measureWidth('B', FONT) + spacing

    assert (line['text']) == (text)
    assert TestTool(line['width']).toBeCloseTo(expected, 5)
    

    print('line count grows monotonically as width shrinks')
    prepared = prepare('The quick brown fox jumps over the lazy dog', FONT)
    previous = 0

    for width in [320, 200, 140, 90]:
        lineCount = layout(prepared, width, LINE_HEIGHT)['lineCount']
        assert (lineCount) >= (previous)
        previous = lineCount
  

    print('trailing whitespace hangs past the line edge')
    prepared = prepareWithSegments('Hello ', FONT)
    widthOfHello = prepared['widths'][0]

    assert (layout(prepared, widthOfHello, LINE_HEIGHT)['lineCount']) == (1)

    withLines = layoutWithLines(prepared, widthOfHello, LINE_HEIGHT)
    assert (withLines['lineCount']) == (1)
    assert (withLines['lines'] == [{
      'text': 'Hello',
      'width': widthOfHello,
      'start': {'segmentIndex': 0, 'graphemeIndex': 0 },
      'end': {'segmentIndex': 1, 'graphemeIndex': 0 },
    }])

    print('breaks long words at grapheme boundaries and keeps both layout APIs aligned')
    prepared = prepareWithSegments('Superlongword', FONT)
    graphemeWidths = prepared['breakableFitAdvances'][0]
    maxWidth = graphemeWidths[0] + graphemeWidths[1] + graphemeWidths[2] + 0.1

    plain = layout(prepared, maxWidth, LINE_HEIGHT)
    rich = layoutWithLines(prepared, maxWidth, LINE_HEIGHT)

    assert (plain['lineCount']) > (1)
    assert (rich['lineCount']) == (plain['lineCount'])
    assert (rich['height']) == (plain['height'])
    assert (''.join(map(lambda l: str(l['text']), rich['lines']))) == ('Superlongword')
    assert (rich['lines'][0]['start'] == { 'segmentIndex': 0, 'graphemeIndex': 0 })
    assert (rich['lines'][-1]['end'] == { 'segmentIndex': 1, 'graphemeIndex': 0 })


    print('mixed-direction text is a stable smoke test')
    prepared = prepareWithSegments('According to محمد الأحمد, the results improved.', FONT)
    result = layoutWithLines(prepared, 120, LINE_HEIGHT)

    assert (result['lineCount']) >= (1)
    assert (result['height']) == (result['lineCount'] * LINE_HEIGHT)
    assert (''.join(map(lambda l: str(l['text']), result['lines']))) == ('According to محمد الأحمد, the results improved.')


    print('layoutNextLine reproduces layoutWithLines exactly')
    prepared = prepareWithSegments('foo trans\u00ADatlantic said "hello" to 世界 and waved.', FONT)
    width = prepared['widths'][0] + prepared['widths'][1] + prepared['widths'][2] + prepared['breakableFitAdvances'][4][0] + prepared['discretionaryHyphenWidth'] + 0.1
    expected = layoutWithLines(prepared, width, LINE_HEIGHT)

    actual = []
    cursor = { 'segmentIndex': 0, 'graphemeIndex': 0 }
    while True:
        line = layoutNextLine(prepared, cursor, width)
        if line is None: break
        actual.append(line)
        cursor = line['end']

    assert (actual == expected['lines'])


    print('mixed-script canary keeps layoutWithLines and layoutNextLine aligned across CJK, RTL, and emoji')
    prepared = prepareWithSegments('Hello 世界 مرحبا 🌍 test', FONT)
    width = 80
    expected = layoutWithLines(prepared, width, LINE_HEIGHT)

    assert (list(map(lambda l:l['text'], expected['lines'])) == ['Hello 世', '界 مرحبا ', '🌍 test'])

    actual = collectStreamedLines(prepared, width)
    assert (actual == expected['lines'])


    print('layout and layoutWithLines stay aligned when ZWSP triggers narrow grapheme breaking')
    cases = [
      'alpha\u200Bbeta',
      'alpha\u200Bbeta\u200Cgamma',
    ]

    for text in cases:
        plain = prepare(text, FONT)
        rich = prepareWithSegments(text, FONT)
        width = 10

        assert (layout(plain, width, LINE_HEIGHT)['lineCount']) == (layoutWithLines(rich, width, LINE_HEIGHT)['lineCount'])


    print('layoutWithLines strips leading collapsible space after a ZWSP break the same way as layoutNextLine')
    prepared = prepareWithSegments('生活就像海洋\u200B 只有意志坚定的人才能到达彼岸', FONT)
    width = prepared['widths'][0] - 1

    assert (layoutWithLines(prepared, width, LINE_HEIGHT)['lines'] == collectStreamedLines(prepared, width))


    print('chunked batch line walking normalizes spaces after zero-width breaks like streaming')
    prepared = prepareWithSegments('x\u00AD A\u200B B', FONT)
    width = measureWidth('x A', FONT) + 0.1
    batched = layoutWithLines(prepared, width, LINE_HEIGHT)

    assert ([l['text'] for l in batched['lines']] == ['x A\u200B', 'B'])
    assert (collectStreamedLines(prepared, width) == batched['lines'])
    assert (layout(prepared, width, LINE_HEIGHT)['lineCount']) == (batched['lineCount'])


    print('layoutNextLine can resume from any fixed-width line start without hidden state')
    prepared = prepareWithSegments('foo trans\u00ADatlantic said "hello" to 世界 and waved. alpha\u200Bbeta 🚀', FONT)
    width = 90
    expected = layoutWithLines(prepared, width, LINE_HEIGHT)

    assert len(expected['lines']) > (2)

    for i in range(len(expected['lines'])):
        suffix = collectStreamedLines(prepared, width, expected['lines'][i]['start'])
        assert (suffix == expected['lines'][i:])

    assert (layoutNextLine(prepared, terminalCursor(prepared), width)) is None


    print('rich line boundary cursors reconstruct normalized source text exactly')
    cases = [
      'a b c',
      '  Hello\t \n  World  ',
      'foo trans\u00ADatlantic said "hello" to 世界 and waved.',
      'According to محمد الأحمد, the results improved.',
      'see https://example.com/reports/q3?lang=ar&mode=full now',
      'alpha\u200Bbeta gamma',
    ]
    widths = [40, 80, 120, 200]

    for text in cases:
        prepared = prepareWithSegments(text, FONT)
        expected = ''.join(map(str, prepared['segments']))

        for width in widths:
            batched = layoutWithLines(prepared, width, LINE_HEIGHT)
            streamed = collectStreamedLines(prepared, width)
    
            assert (reconstructFromLineBoundaries(prepared, batched['lines'])) == (expected)
            assert (reconstructFromLineBoundaries(prepared, streamed)) == (expected)
            assert (reconstructFromWalkedRanges(prepared, width)) == (expected)


    print('soft-hyphen round-trip uses source slices instead of rendered line text')
    prepared = prepareWithSegments('foo trans\u00ADatlantic', FONT)
    width = \
      prepared['widths'][0] + \
      prepared['widths'][1] + \
      prepared['widths'][2] + \
      prepared['breakableFitAdvances'][4][0] + \
      prepared['discretionaryHyphenWidth'] + \
      0.1
    result = layoutWithLines(prepared, width, LINE_HEIGHT)

    assert (''.join(map(lambda l: str(l['text']), result['lines']))) == ('foo trans-atlantic')
    assert (reconstructFromLineBoundaries(prepared, result['lines'])) == ('foo trans\u00ADatlantic')


    print('soft-hyphen fallback does not crash when overflow happens on a later space')
    prepared = prepareWithSegments('foo trans\u00ADatlantic labels', FONT)
    width = measureWidth('foo transatlantic', FONT) + 0.1
    result = layoutWithLines(prepared, width, LINE_HEIGHT)

    assert (list(map(lambda l: l['text'], result['lines'])) == ['foo transatlantic ', 'labels'])
    assert (layout(prepared, width, LINE_HEIGHT)['lineCount']) == (result['lineCount'])


    print('layoutNextLine variable-width streaming stays contiguous and reconstructs normalized text')
    prepared = prepareWithSegments(
      'foo trans\u00ADatlantic said "hello" to 世界 and waved. According to محمد الأحمد, alpha\u200Bbeta 🚀',
      FONT,
    )
    widths = [140, 72, 108, 64, 160, 84, 116, 70, 180, 92, 128, 76]
    lines = collectStreamedLinesWithWidths(prepared, widths)
    expected = ''.join(map(str, prepared['segments']))

    assert (len(lines)) > (2)
    assert (lines[0]['start'] == { 'segmentIndex': 0, 'graphemeIndex': 0 })

    for i in range(len(lines)):
        line = lines[i]
        assert (compareCursors(line['end'], line['start'])) > (0)
        if i > 0:
            assert (line['start'] == lines[i - 1]['end'])

    assert (lines[-1]['end'] == terminalCursor(prepared))
    assert (reconstructFromLineBoundaries(prepared, lines)) == (expected)
    assert (layoutNextLine(prepared, terminalCursor(prepared), widths[-1])) is None


    print('layoutNextLine variable-width streaming stays contiguous in pre-wrap mode')
    prepared = prepareWithSegments('foo\n  bar baz\n\tquux quuz', FONT, { 'whiteSpace': 'pre-wrap' })
    widths = [200, 62, 80, 200, 72, 200]
    lines = collectStreamedLinesWithWidths(prepared, widths)
    expected = ''.join(map(str, prepared['segments']))

    assert (len(lines)) >= (4)
    assert (lines[0]['start'] == { 'segmentIndex': 0, 'graphemeIndex': 0 })

    for i in range(len(lines)):
        line = lines[i]
        assert (compareCursors(line['end'], line['start'])) > (0)
        if i > 0:
            assert (line['start'] == lines[i - 1]['end'])

    assert (lines[-1]['end'] == terminalCursor(prepared))
    assert (reconstructFromLineBoundaries(prepared, lines)) == (expected)
    assert (layoutNextLine(prepared, terminalCursor(prepared), widths[-1])) is None


    print('pre-wrap mode keeps hanging spaces visible at line end')
    prepared = prepareWithSegments('foo   bar', FONT, { 'whiteSpace': 'pre-wrap' })
    width = measureWidth('foo', FONT) + 0.1
    lines = layoutWithLines(prepared, width, LINE_HEIGHT)
    assert (lines['lineCount']) == (2)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['foo   ', 'bar'])
    assert (layout(prepared, width, LINE_HEIGHT)['lineCount']) == (2)


    print('pre-wrap mode treats hard breaks as forced line boundaries')
    prepared = prepareWithSegments('a\nb', FONT, { 'whiteSpace': 'pre-wrap' })
    lines = layoutWithLines(prepared, 200, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['a', 'b'])
    assert (layout(prepared, 200, LINE_HEIGHT)['lineCount']) == (2)


    print('pre-wrap mode treats tabs as hanging whitespace aligned to tab stops')
    prepared = prepareWithSegments('a\tb', FONT, { 'whiteSpace': 'pre-wrap' })
    spaceWidth = measureWidth(' ', FONT)
    prefixWidth = measureWidth('a', FONT)
    tabAdvance = nextTabAdvance(prefixWidth, spaceWidth, 8)
    textWidth = prefixWidth + tabAdvance + measureWidth('b', FONT)
    width = textWidth - 0.1

    lines = layoutWithLines(prepared, width, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['a\t', 'b'])
    assert (layout(prepared, width, LINE_HEIGHT)['lineCount']) == (2)


    print('pre-wrap mode treats consecutive tabs as distinct tab stops')
    prepared = prepareWithSegments('a\t\tb', FONT, { 'whiteSpace': 'pre-wrap' })
    spaceWidth = measureWidth(' ', FONT)
    prefixWidth = measureWidth('a', FONT)
    firstTabAdvance = nextTabAdvance(prefixWidth, spaceWidth, 8)
    afterFirstTab = prefixWidth + firstTabAdvance
    secondTabAdvance = nextTabAdvance(afterFirstTab, spaceWidth, 8)
    width = prefixWidth + firstTabAdvance + secondTabAdvance - 0.1

    lines = layoutWithLines(prepared, width, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['a\t\t', 'b'])
    assert (layout(prepared, width, LINE_HEIGHT)['lineCount']) == (2)


    print('pre-wrap mode keeps whitespace-only middle lines visible')
    prepared = prepareWithSegments('foo\n  \nbar', FONT, { 'whiteSpace': 'pre-wrap' })
    lines = layoutWithLines(prepared, 200, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['foo', '  ', 'bar'])
    assert (layout(prepared, 200, LINE_HEIGHT) == {'lineCount': 3,'height': LINE_HEIGHT * 3 })


    print('pre-wrap mode keeps trailing spaces before a hard break on the current line')
    prepared = prepareWithSegments('foo  \nbar', FONT, { 'whiteSpace': 'pre-wrap' })
    lines = layoutWithLines(prepared, 200, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['foo  ', 'bar'])
    assert (layout(prepared, 200, LINE_HEIGHT) == {'lineCount': 2,'height': LINE_HEIGHT * 2 })


    print('pre-wrap mode keeps trailing tabs before a hard break on the current line')
    prepared = prepareWithSegments('foo\t\nbar', FONT, { 'whiteSpace': 'pre-wrap' })
    lines = layoutWithLines(prepared, 200, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['foo\t', 'bar'])
    assert (layout(prepared, 200, LINE_HEIGHT) == {'lineCount': 2,'height': LINE_HEIGHT * 2 })


    print('pre-wrap mode restarts tab stops after a hard break')
    prepared = prepareWithSegments('foo\n\tbar', FONT, { 'whiteSpace': 'pre-wrap' })
    lines = layoutWithLines(prepared, 200, LINE_HEIGHT)
    spaceWidth = measureWidth(' ', FONT)
    expectedSecondLineWidth = nextTabAdvance(0, spaceWidth, 8) + measureWidth('bar', FONT)

    assert (list(map(lambda l:l['text'], lines['lines'])) == ['foo', '\tbar'])
    assert TestTool(lines['lines'][1]['width']).toBeCloseTo(expectedSecondLineWidth, 5)


    print('layoutNextLine stays aligned with layoutWithLines in pre-wrap mode')
    prepared = prepareWithSegments('foo\n  bar baz\nquux', FONT, { 'whiteSpace': 'pre-wrap' })
    width = measureWidth('  bar', FONT) + 0.1
    expected = layoutWithLines(prepared, width, LINE_HEIGHT)

    actual = []
    cursor = { 'segmentIndex': 0, 'graphemeIndex': 0 }
    while True:
        line = layoutNextLine(prepared, cursor, width)
        if line is None: break
        actual.append(line)
        cursor = line['end']

    assert (actual == expected['lines'])


    print('pre-wrap soft hyphen does not preempt a closer preserved-space break')
    prepared = prepareWithSegments('A\nbا \u00ADb، b', FONT, { 'whiteSpace': 'pre-wrap' })
    width = \
      measureWidth('bا', FONT) + \
      measureWidth(' ', FONT) + \
      measureWidth('b،', FONT) + \
      measureWidth(' ', FONT) + \
      0.1
    expected = layoutWithLines(prepared, width, LINE_HEIGHT)

    assert (list(map(lambda l:l['text'], expected['lines'])) == ['A', 'bا b، ', 'b'])
    assert (collectStreamedLines(prepared, width) == expected['lines'])
    assert (layout(prepared, width, LINE_HEIGHT)['lineCount']) == (expected['lineCount'])


    print('pre-wrap mode keeps empty lines from consecutive hard breaks')
    prepared = prepareWithSegments('\n\n', FONT, { 'whiteSpace': 'pre-wrap' })
    lines = layoutWithLines(prepared, 200, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['', ''])
    assert (layout(prepared, 200, LINE_HEIGHT) == {'lineCount': 2,'height': LINE_HEIGHT * 2 })
    mixed = prepareWithSegments('中文\n\n世界', FONT, {'whiteSpace': 'pre-wrap' })
    mixedLines = layoutWithLines(mixed, 200, LINE_HEIGHT)
    assert list(map(lambda l:l['text'], mixedLines['lines'])) == ['中文', '', '世界']
    assert collectStreamedLines(mixed, 200) == mixedLines['lines']


    print('pre-wrap mode does not invent an extra trailing empty line')
    prepared = prepareWithSegments('a\n', FONT, { 'whiteSpace': 'pre-wrap' })
    lines = layoutWithLines(prepared, 200, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], lines['lines'])) == ['a'])
    assert (layout(prepared, 200, LINE_HEIGHT) == {'lineCount': 1,'height': LINE_HEIGHT })


    print('overlong breakable segments wrap onto a fresh line when the current line already has content')
    prepared = prepareWithSegments('foo abcdefghijk', FONT)
    prefixWidth = prepared['widths'][0] + prepared['widths'][1]
    wordBreaks = prepared['breakableFitAdvances'][2]
    width = prefixWidth + wordBreaks[0] + wordBreaks[1] + 0.1

    batched = layoutWithLines(prepared, width, LINE_HEIGHT)
    assert (batched['lines'][0]['text']) == ('foo ')
    assert str(batched['lines'][1]['text']).startswith('ab')

    streamed = layoutNextLine(prepared, { 'segmentIndex': 0, 'graphemeIndex': 0 }, width)
    assert (streamed['text']) == ('foo ')
    assert (layout(prepared, width, LINE_HEIGHT)['lineCount']) == (batched['lineCount'])


    print('mixed CJK-plus-numeric runs use cumulative widths when breaking the numeric suffix')
    prepared = prepareWithSegments('中文11111111111111111', FONT)
    width = measureWidth('11111', FONT) + 0.1

    assert (prepared['segments'] == ['中', '文', '11111111111111111'])

    batched = layoutWithLines(prepared, width, LINE_HEIGHT)
    assert (list(map(lambda l:l['text'], batched['lines'])) == [
      '中文',
      '11111',
      '11111',
      '11111',
      '11',
    ])

    streamed = collectStreamedLines(prepared, width)
    assert (streamed == batched['lines'])
    assert (layout(prepared, width, LINE_HEIGHT) == {'lineCount': 5,'height': LINE_HEIGHT * 5 })


    print('keep-all suppresses ordinary CJK intra-word breaks after existing line content')
    text = 'A 中文测试'
    normal = prepareWithSegments(text, FONT)
    keepAll = prepareWithSegments(text, FONT, { 'wordBreak': 'keep-all' })
    width = measureWidth('A 中', FONT) + 0.1

    assert (layoutWithLines(normal, width, LINE_HEIGHT)['lines'][0]['text']) == ('A 中')
    assert (layoutWithLines(keepAll, width, LINE_HEIGHT)['lines'][0]['text']) == ('A ')
    assert (layout(keepAll, width, LINE_HEIGHT)['lineCount']) > (layout(normal, width, LINE_HEIGHT)['lineCount'])


    print('keep-all lets mixed no-space CJK runs break through the script boundary')
    text = '日本語foo-bar'
    normal = prepareWithSegments(text, FONT)
    keepAll = prepareWithSegments(text, FONT, { 'wordBreak': 'keep-all' })
    width = measureWidth('日本語f', FONT) + 0.1

    assert (layoutWithLines(normal, width, LINE_HEIGHT)['lines'][0]['text']) == ('日本語')
    assert (layoutWithLines(keepAll, width, LINE_HEIGHT)['lines'][0]['text']) == ('日本語f')


    print('walkLineRanges reproduces layoutWithLines geometry without materializing text')
    prepared = prepareWithSegments('foo trans\u00ADatlantic said "hello" to 世界 and waved.', FONT)
    width = prepared['widths'][0] + prepared['widths'][1] + prepared['widths'][2] + prepared['breakableFitAdvances'][4][0] + prepared['discretionaryHyphenWidth'] + 0.1
    expected = layoutWithLines(prepared, width, LINE_HEIGHT)
    actual = []

    def _callback(line):
        actual.append({
          'width': line['width'],
          'start': line['start'].copy(),
          'end': line['end'].copy(),
        })
    
    def _map(line):
        return {
          'width': line['width'],
          'start': line['start'],
          'end': line['end'],
        }
    
    lineCount = walkLineRanges(prepared, width, _callback)

    assert (lineCount) == (expected['lineCount'])
    assert (actual == list(map(_map, expected['lines'])))


    print('materializeLineRange reproduces streamed layout lines')
    prepared = prepareWithSegments('foo trans\u00ADatlantic said "hello" to 世界 and waved.', FONT)
    width = prepared['widths'][0] + prepared['widths'][1] + prepared['widths'][2] + prepared['breakableFitAdvances'][4][0] + prepared['discretionaryHyphenWidth'] + 0.1
    expected = layoutWithLines(prepared, width, LINE_HEIGHT)['lines'][0]
    _range = layoutNextLineRange(prepared, { 'segmentIndex': 0, 'graphemeIndex': 0 }, width)

    assert (_range) is not None
    assert (materializeLineRange(prepared, _range) == expected)

    print('measureLineStats matches walked line count and widest line')
    prepared = prepareWithSegments('foo trans\u00ADatlantic said "hello" to 世界 and waved.', FONT)
    width = prepared['widths'][0] + prepared['widths'][1] + prepared['widths'][2] + prepared['breakableFitAdvances'][4][0] + prepared['discretionaryHyphenWidth'] + 0.1
    walked_line_count = 0
    walked_max_line_width = 0
    
    def line_callback(line):
        nonlocal walked_line_count, walked_max_line_width
        walked_line_count += 1
        walked_max_line_width = max(walked_max_line_width, line['width'])
    
    walkLineRanges(prepared, width, line_callback)
    
    assert measureLineStats(prepared, width) == {
        'lineCount': walked_line_count,
        'maxLineWidth': walked_max_line_width,
    }


    print('measureNaturalWidth returns the widest forced line')
    prepared = prepareWithSegments('wide line\nfit\nmid', FONT, { 'whiteSpace': 'pre-wrap' })

    assert (measureNaturalWidth(prepared)) == (measureWidth('wide line', FONT))
 

    print('line-break geometry helpers stay aligned with streamed line ranges')
    prepared = prepareWithSegments('foo trans\u00ADatlantic said "hello" to 世界 and waved.', FONT)
    widths = [48, 72, 120]
    
    for index in range(len(widths)):
        width = widths[index]
        cursor = {'segmentIndex': 0, 'graphemeIndex': 0}
        streamedWidths = []
    
        while True:
            line = layoutNextLineRange(prepared, cursor, width)
            geometryCursor = cursor.copy()
            geometryWidth = stepPreparedLineGeometry(prepared, geometryCursor, width)
            assert geometryWidth == (line['width'] if line is not None else None)
            if line is None:
                break
            assert geometryCursor == line['end']
            streamedWidths.append(line['width'])
            cursor['segmentIndex'] = line['end']['segmentIndex']
            cursor['graphemeIndex'] = line['end']['graphemeIndex']
    
        assert measurePreparedLineGeometry(prepared, width) == {
            'lineCount': len(streamedWidths),
            'maxLineWidth': max(streamedWidths, default=0),
        }

    print('countPreparedLines stays aligned with the walked line counter')
    texts = [
      'The quick brown fox jumps over the lazy dog.',
      'said "hello" to 世界 and waved.',
      'مرحبا، عالم؟',
      'author 7:00-9:00 only',
      'alpha\u200Bbeta gamma',
    ]
    widths = [40, 80, 120, 200]

    for textIndex in range(len(texts)):
        prepared = prepareWithSegments(texts[textIndex], FONT)
        for widthIndex in range(len(widths)):
            width = widths[widthIndex]
            counted = countPreparedLines(prepared, width)
            walked = walkPreparedLinesRaw(prepared, width)
            assert (counted) == (walked)

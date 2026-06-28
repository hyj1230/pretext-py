from pretext_py.intl_segmenter_py.grapheme import graphemeSegments, splitGraphemes, countGraphemes
from pretext_py.intl_segmenter_py import String
from pretext_py.intl_segmenter_py._grapheme_data import GraphemeCategory
from copy import deepcopy


def normalize(l):
    new = deepcopy(l)
    for i in new:
        i['input'] = str(i['input'])
        i['segment'] = str(i['segment'])
    return new

_api = (graphemeSegments, splitGraphemes, countGraphemes)
graphemeSegments = lambda s: normalize(list(_api[0](String(s))))
countGraphemes = lambda s: _api[2](String(s))
splitGraphemes = lambda s: list(map(str, _api[1](String(s))))


print('test graphemeSegments')
def test_graphemeSegments():

    assert graphemeSegments('') == []
    assert \
      graphemeSegments('abc123') == \
      [
        { 'segment': 'a', 'index': 0, 'input': 'abc123', '_hd': String('a').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Any'] },
        { 'segment': 'b', 'index': 1, 'input': 'abc123', '_hd': String('b').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Any'] },
        { 'segment': 'c', 'index': 2, 'input': 'abc123', '_hd': String('c').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Any'] },
        { 'segment': '1', 'index': 3, 'input': 'abc123', '_hd': String('1').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Any'] },
        { 'segment': '2', 'index': 4, 'input': 'abc123', '_hd': String('2').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Any'] },
        { 'segment': '3', 'index': 5, 'input': 'abc123', '_hd': String('3').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Any'] },
      ]


def test_composition():
    assert \
      graphemeSegments('a̐éö̲\r\n') == \
      [
        { 'segment': 'a̐', 'index': 0, 'input': 'a̐éö̲\r\n', '_hd': String('a̐').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Extend'] },
        { 'segment': 'é', 'index': 2, 'input': 'a̐éö̲\r\n', '_hd': String('é').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Extend'] },
        { 'segment': 'ö̲', 'index': 4, 'input': 'a̐éö̲\r\n', '_hd': String('ö̲').codePointAt(0), '_catBegin': GraphemeCategory['Any'], '_catEnd': GraphemeCategory['Extend'] },
        { 'segment': '\r\n', 'index': 7, 'input': 'a̐éö̲\r\n', '_hd': String('\r\n').codePointAt(0), '_catBegin': GraphemeCategory['CR'], '_catEnd': GraphemeCategory['LF'] },
      ]


def test_flags():
    assert \
      graphemeSegments('🇷🇸🇮🇴') == \
      [
        { 'segment': '🇷🇸', 'index': 0, 'input': '🇷🇸🇮🇴', '_hd': String('🇷🇸').codePointAt(0), '_catBegin': GraphemeCategory['Regional_Indicator'], '_catEnd': GraphemeCategory['Regional_Indicator'] },
        { 'segment': '🇮🇴', 'index': 4, 'input': '🇷🇸🇮🇴', '_hd': String('🇮🇴').codePointAt(0), '_catBegin': GraphemeCategory['Regional_Indicator'], '_catEnd': GraphemeCategory['Regional_Indicator'] },
      ]
    
def test_flags_incompleted():
    assert \
      graphemeSegments('🇷🇸🇮') == \
      [
        { 'segment': '🇷🇸', 'index': 0, 'input': '🇷🇸🇮', '_hd': String('🇷🇸').codePointAt(0), '_catBegin': GraphemeCategory['Regional_Indicator'], '_catEnd': GraphemeCategory['Regional_Indicator'] },
        { 'segment': '🇮', 'index': 4, 'input': '🇷🇸🇮', '_hd': String('🇮').codePointAt(0), '_catBegin': GraphemeCategory['Regional_Indicator'], '_catEnd': GraphemeCategory['Regional_Indicator'] },
      ]


def test_emoji():
    assert \
      graphemeSegments('👻👩‍👩‍👦‍👦') == \
      [
        { 'segment': '👻', 'index': 0, 'input': '👻👩‍👩‍👦‍👦', '_hd': String('👻').codePointAt(0), '_catBegin': GraphemeCategory['Extended_Pictographic'], '_catEnd': GraphemeCategory['Extended_Pictographic'] },
        { 'segment': '👩‍👩‍👦‍👦', 'index': 2, 'input': '👻👩‍👩‍👦‍👦', '_hd': String('👩‍👩‍👦‍👦').codePointAt(0), '_catBegin': GraphemeCategory['Extended_Pictographic'], '_catEnd': GraphemeCategory['Extended_Pictographic'] },
      ]

test_graphemeSegments()
test_composition()
test_flags()
test_flags_incompleted()
test_emoji()


print('test countGraphemes')
def test_latin():
    assert countGraphemes('abcd') == 4

def test_flags_count():
    assert countGraphemes('🇷🇸🇮🇴') == 2

def test_emoji_count():
    assert countGraphemes('👻👩‍👩‍👦‍👦') == 2
    assert countGraphemes('🌷🎁💩😜👍🏳️‍🌈') == 6

def test_diacritics():
    assert countGraphemes('Ĺo͂řȩm̅') == 5

def test_Jamo():
    assert countGraphemes('뎌쉐') == 2

def test_Hindi():
    assert countGraphemes('अनुच्छेद') == 4

def test_demonic():
    assert countGraphemes('Z͑ͫ̓ͪ̂ͫ̽͏̴̙̤̞͉͚̯̞̠͍A̴̵̜̰͔ͫ͗͢L̠ͨͧͩ͘G̴̻͈͍͔̹̑͗̎̅͛́Ǫ̵̹̻̝̳͂̌̌͘!͖̬̰̙̗̿̋ͥͥ̂ͣ̐́́͜͞') == 6


test_latin()
test_flags_count()
test_emoji_count()
test_diacritics()
test_Jamo()
test_Hindi()
test_demonic()


print('test_splitGrapheme')
def test_latin_split():
    assert \
      splitGraphemes('abcd') == \
      ['a', 'b', 'c', 'd']
    
def test_flags_split():
    assert \
      splitGraphemes('🇷🇸🇮🇴') == \
      ['🇷🇸', '🇮🇴'] 

def test_emoji_split():
    assert \
      splitGraphemes('👻👩‍👩‍👦‍👦') == ['👻', '👩‍👩‍👦‍👦']
    
    assert \
      splitGraphemes('🌷🎁💩😜👍🏳️‍🌈') == \
      ['🌷', '🎁', '💩', '😜', '👍', '🏳️‍🌈']


def test_diacritics_split():
    assert \
      splitGraphemes('Ĺo͂řȩm̅') == \
      ['Ĺ', 'o͂', 'ř', 'ȩ', 'm̅']

def test_Jamo_split():
    assert \
      splitGraphemes('가갉') == \
      ['가', '갉']

def test_Hindi_split():
    assert \
      splitGraphemes('अनुच्छेद') == \
      ['अ', 'नु', 'च्छे', 'द']

def test_demonic_split():
    assert \
      splitGraphemes('Z͑ͫ̓ͪ̂ͫ̽͏̴̙̤̞͉͚̯̞̠͍A̴̵̜̰͔ͫ͗͢L̠ͨͧͩ͘G̴̻͈͍͔̹̑͗̎̅͛́Ǫ̵̹̻̝̳͂̌̌͘!͖̬̰̙̗̿̋ͥͥ̂ͣ̐́́͜͞') == \
      ['Z͑ͫ̓ͪ̂ͫ̽͏̴̙̤̞͉͚̯̞̠͍', 'A̴̵̜̰͔ͫ͗͢', 'L̠ͨͧͩ͘', 'G̴̻͈͍͔̹̑͗̎̅͛́', 'Ǫ̵̹̻̝̳͂̌̌͘', '!͖̬̰̙̗̿̋ͥͥ̂ͣ̐́́͜͞']


test_latin_split()
test_flags_split()
test_emoji_split()
test_diacritics_split()
test_Jamo_split()
test_Hindi_split()
test_demonic_split()


print('test break category')
def test_break_category():
    cats = {
        'Extended_Pictographic': [
          '🏴',
          '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
          '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
          '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
        ],
    }

    for cat in cats:
        cases = cats[cat]
        for case in cases:
            expected = GraphemeCategory[cat] 
            d = _api[0](String(case))
            assert next(d)['_catBegin'] == expected
test_break_category()

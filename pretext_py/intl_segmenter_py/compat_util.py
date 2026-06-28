import math


def get_encode_type():
    check_str = '𠮷'
    be = check_str.encode('utf-16be')
    le = check_str.encode('utf-16le')
    if be[0] * 0x100 + be[1] == 55362:
        return 'utf-16be'
    if le[0] * 0x100 + le[1] == 55362:
        return 'utf-16le'
    raise EnvironmentError


ENCODE_TYPE = get_encode_type()


WhiteSpace = set((
  # ECMA-262 5.1 标准第 7.2 节中定义的空白符 (WhiteSpace)
  0x0009,  # 制表符 (Tab)                TAB
  0x000B,  # 垂直制表符 (Vertical Tab)    VT
  0x000C,  # 换页符 (Form Feed)           FF
  0x0020,  # 空格 (Space)                SP
  0x00A0,  # 不换行空格 (No-break space)  NBSP
  0xFEFF,  # 字节顺序标记 (Byte Order Mark) BOM

  # ECMA-262 5.1 标准第 7.3 节中定义的换行符 (LineTerminator)
  0x000A,  # 换行符 (Line Feed)           LF
  0x000D,  # 回车符 (Carriage Return)     CR
  0x2028,  # 行分隔符 (Line Separator)     LS
  0x2029,  # 段落分隔符 (Paragraph Separator) PS

  # Unicode 6.3.0 中的空白符 (类别为 'Zs')
  0x1680,  # 欧甘空格符 (Ogham Space Mark)
  0x2000,  # EN 宽空格 (EN QUAD)
  0x2001,  # EM 宽空格 (EM QUAD)
  0x2002,  # EN 空格 (EN SPACE)
  0x2003,  # EM 空格 (EM SPACE)
  0x2004,  # 三分之一 EM 空格 (THREE-PER-EM SPACE)
  0x2005,  # 四分之一 EM 空格 (FOUR-PER-EM SPACE)
  0x2006,  # 六分之一 EM 空格 (SIX-PER-EM SPACE)
  0x2007,  # 数字空格 (FIGURE SPACE)
  0x2008,  # 标点空格 (PUNCTUATION SPACE)
  0x2009,  # 细空格 (THIN SPACE)
  0x200A,  # 超细空格 (HAIR SPACE)
  0x2028,  # 行分隔符 (LINE SEPARATOR)   # 注意：此条目在换行符部分已列出
  0x2029,  # 段落分隔符 (PARAGRAPH SEPARATOR) # 注意：此条目在换行符部分已列出
  0x202F,  # 窄不换行空格 (NARROW NO-BREAK SPACE)
  0x205F,  # 中数学空格 (MEDIUM MATHEMATICAL SPACE)
  0x3000,  # 表意文字空格 (IDEOGRAPHIC SPACE) # 即全角空格
))
WhiteSpace = ''.join(map(chr, WhiteSpace))


class String:
    def __init__(self, data):
        if isinstance(data, str):
            self.data = data.encode(ENCODE_TYPE)
        elif isinstance(data, String):
            self.data = data.data
        elif isinstance(data, (bytes, bytearray)):
            self.data = data
        else:
            raise ValueError('Unknown data type')
    
    @property
    def length(self):
        return len(self.data) // 2
    
    def charCodeAt(self, index: int):
        if index < 0 or index >= self.length:
            return math.nan
        return self.data[index * 2] * 0x100 + self.data[index * 2 + 1]
    
    def _codePointAt(self, index: int):  # @deprecate
        if index < 0 or index >= self.length:
            return None
        first = self.data[index * 2] * 0x100 + self.data[index * 2 + 1]
        if not (0xD800 <= first <= 0xDBFF) and not (0xDC00 <= first <= 0xDFFF):
            return first
        if (0xDC00 <= first <= 0xDFFF) or (index + 1 == self.length):
            return first
        second = self.data[index * 2 + 2] * 0x100 + self.data[index * 2 + 3]
        if not (0xDC00 <= second <= 0xDFFF):
            return first
        return (first - 0xD800) * 0x400 + (second - 0xDC00) + 0x10000
    
    def codePointAt(self, index: int):
        if index < 0 or index >= self.length:
            return None
        first = self.data[index * 2] * 0x100 + self.data[index * 2 + 1]
        # 尝试解码代理对（仅当 first 是高代理且存在有效的低代理时）
        if 0xD800 <= first <= 0xDBFF and index + 1 < self.length:
            second = self.data[index * 2 + 2] * 0x100 + self.data[index * 2 + 3]
            if 0xDC00 <= second <= 0xDFFF:
                return (first - 0xD800) * 0x400 + (second - 0xDC00) + 0x10000
        return first
    
    def __str__(self):
        return self.data.decode(ENCODE_TYPE)
    
    def __repr__(self):
        return repr(self.data.decode(ENCODE_TYPE))

    def slice(self, start: int, end: int = None):
        start = start or 0
        start = max(start + self.length, 0) if start < 0 else start
        end = self.length if end is None or end >= self.length else end
        end = max(end + self.length, 0) if end < 0 else end
        
        if start >= self.length or end <= start:
            return String('')
        
        return String(self.data[start * 2: end * 2])
     
    def __eq__(self, other):
        if isinstance(other, String):
            return self.data == other.data
        if isinstance(other, str):
            return str(self) == other
        return False
    
    def __bool__(self):
        return bool(self.data)
    
    def __add__(self, other):
        if isinstance(other, str):
            other = String(other)
        if isinstance(other, String):
            return String(self.data + other.data)
        else:
            raise TypeError
    
    def contain_code(self, codes: tuple):
        for i in range(0, len(self.data), 2):
            ch = self.data[i] * 0x100 + self.data[i + 1]
            if ch in codes: return True
        return False
   
    def repeat(self, count: int):
        return String(self.data * count)
   
    @staticmethod
    def measure_length(s: int):
        return len(s.encode(ENCODE_TYPE)) // 2
    
    def trim(self):
        return String(str(self).strip(WhiteSpace))


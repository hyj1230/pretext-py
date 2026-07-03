# 用于处理 Unicode 字符范围数据的工具函数
# 提供紧凑解码和二分查找功能


def decodeUnicodeData(data: str, cats: str = ''):
    """
    将压缩的 Unicode 范围编码字符串解码为范围列表。

    压缩格式说明：
      - 数据字符串由逗号分隔的 base36 数字组成。
      - 每两个数字表示一个范围：奇数位是起始码点，偶数位是区间长度（结束 - 起始）。
      - 类别参数 cats 是可选的，每个字符也是 base36 数字，
        按顺序对应每个范围的类别值；若省略，则类别默认为 0。
    
    注意：
      - base 可以在几个字符中保存极大的数字。
      - 此时最大的码点是 0xE01F0 (918,000)
      - 类别的最大值为 23; https://www.unicode.org/reports/tr29/tr29-45.html#Table_Word_Break_Property_Values
      - 最长范围是 42,720; CJK UNIFIED IDEOGRAPH-20000..CJK UNIFIED IDEOGRAPH-2A6DF

    Args:
        data: UnicodeDataEncoding 压缩字符串。
        cats: 可选的类别编码字符串，长度应与范围数量一致。

    Returns:
        列表，每个元素为 [起始码点, 结束码点, 类别]。
    """
    
    buf = []
    nums = map(lambda s: int(s, 36) if s else 0, data.split(','))
    n = 0
    for i, num in enumerate(nums):
        if i % 2:
            buf.append([n, n + num, (int(cats[i >> 1], 36) if cats else 0)])
        else:
            n = num
    return buf


def findUnicodeRangeIndex(cp: int, ranges, lo: int = 0, hi: int = None):
    """
    在已排序的 Unicode 范围数组中，使用二分查找定位指定码点所属的范围索引。

    Args:
        cp: 要查找的 Unicode 码点（整数）。
        ranges: 已按起始码点升序排列的范围列表，每个元素为 [起始, 结束, 类别]。
        lo: 查找区间左边界索引，默认为 0。
        hi: 查找区间右边界索引，默认为 len(ranges) - 1。

    Returns:
        如果 cp 落在某个范围内，返回该范围的索引；否则返回 -1。
    """
    
    if hi is None:
        hi = len(ranges) - 1

    while lo <= hi:
        mid = lo + hi >> 1
        _range = ranges[mid]
        
        if cp < _range[0]: hi = mid - 1
        elif cp > _range[1]: lo = mid + 1
        else: return mid

    return -1

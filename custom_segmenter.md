# 自定义 Intl.Sgementer

## 概述

`Segmenter.custom_grapheme` 和 `Segmenter.custom_word` 是类级别的可替换属性，允许您为 `Segmenter` 实例提供自定义的字符串分割逻辑，替代默认的 grapheme（字素）和 word（单词）分段实现。

---

## `Segmenter.custom_grapheme`

### 作用
覆盖默认的字素分段算法。当设置该属性后，所有 `Segmenter` 实例（`granularity: 'grapheme'`）都将使用您提供的函数来分割字符串。

### 函数签名
```python
custom_grapheme(input_str: str, locale: str, options: dict) -> Iterable[str]
```

#### 参数
| 参数       | 类型   | 说明                                                                 |
|-----------|--------|----------------------------------------------------------------------|
| `input_str` | `str`  | 需要分割的原始字符串。                                                |
| `locale`    | `str`  | 创建 `Segmenter` 时传入的语言环境（如 `'en'`, `'zh-CN'`）。           |
| `options`   | `dict` | 创建 `Segmenter` 时传入的选项对象（包含 `granularity` 等属性）。      |

#### 返回值
一个 **可迭代对象**（如列表、生成器），其中的每个元素是一个 **字符串**，代表一个单独的字素段（grapheme segment）。

### 示例
```python
from pretext_py import Segmenter

def my_grapheme_split(text: str, locale: str, options: dict):
    # 简单示例：按单个字符分割（不推荐用于生产）
    for ch in text:
        yield ch

Segmenter.custom_grapheme = my_grapheme_split

segmenter = Segmenter('en', {'granularity': 'grapheme'})
segments = segmenter.segment("Hello 👨‍👩‍👧‍👦")
for s in segments:
    print(s['segment'])
```

---

## `Segmenter.custom_word`

### 作用
覆盖默认的单词分段算法。当设置该属性后，所有 `Segmenter` 实例（`granularity: 'word'`）将使用您提供的函数来分割字符串。

### 函数签名
```python
custom_word(input_str: str, locale: str, options: dict) -> Iterable[Union[str, Tuple[str, Optional[bool]]]]
```

#### 参数
| 参数       | 类型   | 说明                                                                 |
|-----------|--------|----------------------------------------------------------------------|
| `input_str` | `str`  | 需要分割的原始字符串。                                                |
| `locale`    | `str`  | 创建 `Segmenter` 时传入的语言环境。                                  |
| `options`   | `dict` | 创建 `Segmenter` 时传入的选项对象。                                   |

#### 返回值
一个 **可迭代对象**，每个元素可以是：
- **`str`** ：仅提供分段文本。`isWordLike` 属性将由内部函数 `is_word_like()` 自动判断。
- **`Tuple[str, Optional[bool]]`** ：形式为 `(segment, is_word_like)`，其中 `is_word_like` 为布尔值或 `None`。若为 `None`，则同样使用 `is_word_like(segment)` 计算。

`isWordLike` 表示该段是否应被视为“像单词”（例如用于区分单词、空格、标点）。

### 示例
```python
from pretext_py import Segmenter
from typing import Iterable, Tuple

def my_word_split(text: str, locale: str, options: dict) -> Iterable[Tuple[str, bool]]:
    # 按空格分割，并标记每个段为“像单词”（除了纯空格段）
    for part in text.split(' '):
        if part == '':
            yield (' ', False)   # 空格段，不是单词
        else:
            yield (part, True)

Segmenter.custom_word = my_word_split

segmenter = Segmenter('en', {'granularity': 'word'})
segments = segmenter.segment("Hello world!")
for s in segments:
    print(s['segment'], s['isWordLike'])
# 输出:
# Hello True
#   False
# world! True
```

---

## 重置自定义函数

将属性设为 `None` 即可恢复默认行为：
```python
Segmenter.custom_grapheme = None
Segmenter.custom_word = None
```

---

## 注意事项

1. **类级别作用域**：这两个属性属于 `Segmenter` 类本身，修改后会影响**所有**实例（包括已创建和将来创建的）。
2. **性能**：自定义函数每次调用 `segment()` 或 `containing()` 时都会被执行。对长字符串请确保高效实现。

---

# Custom Intl.Segmenter

## Overview

`Segmenter.custom_grapheme` and `Segmenter.custom_word` are class-level replaceable attributes that allow you to provide custom string segmentation logic, overriding the default grapheme and word segmentation implementations.

---

## `Segmenter.custom_grapheme`

### Purpose
Overrides the default grapheme segmentation algorithm. When set, all `Segmenter` instances (with `granularity: 'grapheme'`) will use your provided function to split strings.

### Function Signature
```python
custom_grapheme(input_str: str, locale: str, options: dict) -> Iterable[str]
```

#### Parameters
| Parameter | Type   | Description |
|-----------|--------|-------------|
| `input_str` | `str`  | The raw string to be segmented. |
| `locale`    | `str`  | The locale passed when creating the `Segmenter` (e.g., `'en'`, `'zh-CN'`). |
| `options`   | `dict` | The options object passed when creating the `Segmenter` (contains `granularity`, etc.). |

#### Return Value
An **iterable** (e.g., list, generator) where each element is a **string** representing a single grapheme segment.

### Example
```python
from pretext_py import Segmenter

def my_grapheme_split(text: str, locale: str, options: dict):
    # Simple example: split by individual character (not recommended for production)
    for ch in text:
        yield ch

Segmenter.custom_grapheme = my_grapheme_split

segmenter = Segmenter('en', {'granularity': 'grapheme'})
segments = segmenter.segment("Hello 👨‍👩‍👧‍👦")
for s in segments:
    print(s['segment'])
```

---

## `Segmenter.custom_word`

### Purpose
Overrides the default word segmentation algorithm. When set, all `Segmenter` instances (with `granularity: 'word'`) will use your provided function.

### Function Signature
```python
custom_word(input_str: str, locale: str, options: dict) -> Iterable[Union[str, Tuple[str, Optional[bool]]]]
```

#### Parameters
| Parameter | Type   | Description |
|-----------|--------|-------------|
| `input_str` | `str`  | The raw string to be segmented. |
| `locale`    | `str`  | The locale passed when creating the `Segmenter`. |
| `options`   | `dict` | The options object passed when creating the `Segmenter`. |

#### Return Value
An **iterable** where each element can be:
- **`str`** : Only the segmented text. The `isWordLike` property will be automatically determined by the internal `is_word_like()` function.
- **`Tuple[str, Optional[bool]]`** : Form `(segment, is_word_like)`, where `is_word_like` is a boolean or `None`. If `None`, `is_word_like(segment)` is used to compute the value.

`isWordLike` indicates whether the segment should be considered "word-like" (e.g., to distinguish words from spaces, punctuation).

### Example
```python
from pretext_py import Segmenter
from typing import Iterable, Tuple

def my_word_split(text: str, locale: str, options: dict) -> Iterable[Tuple[str, bool]]:
    # Split by spaces, marking non-space parts as word-like
    for part in text.split(' '):
        if part == '':
            yield (' ', False)   # space segment, not word-like
        else:
            yield (part, True)

Segmenter.custom_word = my_word_split

segmenter = Segmenter('en', {'granularity': 'word'})
segments = segmenter.segment("Hello world!")
for s in segments:
    print(s['segment'], s['isWordLike'])
# Output:
# Hello True
#   False
# world! True
```

---

## Resetting Custom Functions

Set the attribute to `None` to restore default behavior:
```python
Segmenter.custom_grapheme = None
Segmenter.custom_word = None
```

---

## Important Notes

1. **Class-level scope**: These attributes belong to the `Segmenter` class itself. Modifying them affects **all** instances (both already created and future ones). For instance-level customization, consider subclassing or factory functions.
2. **Performance**: The custom function is executed every time `segment()` or `containing()` is called. Ensure efficient implementation for long strings.
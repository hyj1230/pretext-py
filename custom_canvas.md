# 自定义 Canvas 渲染上下文文档

## 概述

`set_custom_canvas` 是 `pretext_py` 库提供的一个全局配置函数，允许您替换默认的 Canvas 渲染上下文实现。通过传入一个符合 `CanvasRenderingContext2D` 接口的类实例，您可以自定义文本测量、图形绘制等行为，从而适配不同的渲染后端或测试环境。

---

## 函数签名

```python
set_custom_canvas(canvas_class: type) -> None
```

### 参数

| 参数 | 类型 | 说明 |
|--------------|--------|----------------------------------------------------------------------|
| `canvas_class` | `type` | 一个类（或类实例），必须实现 `measureText` 方法，并可选实现其他 Canvas 方法。 |

**要求**：
- 传入的类（或对象）至少应包含 `measureText(text: str) -> dict` 方法，返回一个包含 `'width'` 键的字典（或可索引对象），表示文本宽度。
- 如果您的实现还包含 `font` 属性，可在 `measureText` 中使用以计算正确的宽度。

### 返回值

`None`（该函数仅为全局配置，无返回值）。

---

## 示例

### 基础示例：自定义文本测量

```python
from pretext_py import set_custom_canvas

# 假设有一个测量宽度的辅助函数
def measureWidth(text: str, font: str) -> float:
    # 自定义测量逻辑，例如基于字体和字符宽度表
    return len(text) * 8.0 # 简化示例

class TestCanvasRenderingContext2D:
    def __init__(self):
        self.font = '' # 可存储当前字体

    def measureText(self, text: str):
        # 必须返回包含 'width' 键的字典
        return {'width': measureWidth(text, self.font)}

# 设置自定义 canvas
set_custom_canvas(TestCanvasRenderingContext2D)

# 之后，所有使用 Canvas 的渲染操作都会调用此自定义类
```

---

## 重置默认 Canvas

若要恢复默认的 Canvas 实现，可传入 `None` 或重新调用不带参数（具体视库实现而定，通常允许传入 `None`）：

```python
set_custom_canvas(None) # 恢复内置 Canvas
```

---

## 注意事项
1. **接口兼容性**：您的自定义类**必须**实现 `measureText` 方法，否则在需要测量文本宽度时会抛出 `AttributeError`。
2. **返回值格式**：`measureText` 返回的字典必须包含 `'width'` 键，其值为数值类型（`int` 或 `float`）。缺少该键会导致运行时错误。

---

# Custom Canvas Rendering Context Documentation

## Overview

`set_custom_canvas` is a global configuration function provided by the `pretext_py` library, allowing you to replace the default Canvas rendering context implementation. By passing a class that conforms to the `CanvasRenderingContext2D` interface, you can customize text measurement, drawing, etc., to adapt to different rendering backends or test environments.

---

## Function Signature

```python
set_custom_canvas(canvas_class: type) -> None
```

### Parameters

| Parameter | Type | Description |
|----------------|--------|-------------|
| `canvas_class` | `type` | A class (or an instance) that must implement the `measureText` method, and optionally other Canvas methods. |

**Requirements**:
- The passed class (or object) must at least have a `measureText(text: str) -> dict` method, returning a dictionary (or indexable object) containing a `'width'` key representing the text width.
- If your implementation also includes a `font` attribute, you can use it inside `measureText` to compute accurate widths.
- Other Canvas methods (such as `fillText`, `strokeText`, etc.) can be implemented as needed, but currently only `measureText` is required.

### Return Value

`None` (this function is a global configuration, no return value).

---

## Examples

### Basic Example: Custom Text Measurement

```python
from pretext_py import set_custom_canvas

# Assume a helper function for width measurement
def measureWidth(text: str, font: str) -> float:
    # Custom logic, e.g., based on font and character width table
    return len(text) * 8.0 # simplified example

class TestCanvasRenderingContext2D:
    def __init__(self):
        self.font = '' # can store current font

    def measureText(self, text: str):
        # Must return a dict with key 'width'
        return {'width': measureWidth(text, self.font)}

# Set custom canvas
set_custom_canvas(TestCanvasRenderingContext2D)

# From now on, all Canvas rendering operations will use this custom class
```

---

## Restoring Default Canvas

To revert to the default Canvas implementation, pass `None` (or call without an argument, depending on library implementation, usually `None` is accepted):

```python
set_custom_canvas(None) # Restore built-in Canvas
```

---

## Important Notes

1. **Interface Compatibility**: Your custom class **must** implement `measureText`; otherwise, an `AttributeError` will be raised when text width measurement is needed.
2. **Return Format**: The dictionary returned by `measureText` must contain a `'width'` key with a numeric value (`int` or `float`). Missing this key will cause runtime errors.
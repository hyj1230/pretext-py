![](/screenshot_computer.jpg)
![](/demo_editorial_engine.png)  
![](/demo_dragon.jpg)

## English:

# Pretext-py

A Python rewrite of [chenglou/pretext](https://github.com/chenglou/pretext/commit/796b4691ca782ec44df9eb5d470abeca4d25732f) — fast, accurate, and concise text measurement and layout.

## Compatibility

### Intl.Segmenter

This project uses another project of mine: [intl-segmenter-py](https://github.com/hyj1230/intl-segmenter-py).
Due to technical reasons, **setting `locales` is not currently supported**. Therefore, we additionally provide a way to customize the `Segmenter`; see [custom_segmenter.md](/custom_segmenter.md).
If you have any information on fully implementing `Intl.Segmenter`, please let me know.

### measureText

Only a simple implementation using `pygame` is provided in `pretext_py/py_canvas`. Therefore, when using this project, you should also replace the `measureText` implementation; see [custom_canvas.md](/custom_canvas.md).

## Tests

Only two tests in `pretext_py/layout_test.py` currently fail, because the built‑in `Intl.Segmenter` still has minor differences from the JavaScript version.

## Demo

Currently two demos have been ported:

1. [dragon_fast.py](/dragon_fast.py) – Due to font and pygame limitations, some characters (e.g., Arabic and emoji) may not render correctly.
2. [editorial_engine.py](/editorial_engine.py) – Renders very well with excellent visual effects.

---

## 中文：

# Pretext-py

使用 Python 重写的 [chenglou/pretext](https://github.com/chenglou/pretext/commit/796b4691ca782ec44df9eb5d470abeca4d25732f) —— 快速、准确、简洁的文本测量与布局。

## 兼容性

### Intl.Segmenter

使用了我的另一个项目：[intl-segmenter-py](https://github.com/hyj1230/intl-segmenter-py)。
由于技术原因，**暂不支持 `locales` 的设置**，因此我们额外提供了自定义 `Segmenter` 的方法，详见 [custom_segmenter.md](/custom_segmenter.md)。
如果你有关于完整实现 `Intl.Segmenter` 的任何信息，欢迎告知我。

### measureText

仅在 `pretext_py/py_canvas` 中使用 `pygame` 进行了简单实现，因此在使用本项目时，您也应替换 `measureText` 的实现，详见 [custom_canvas.md](/custom_canvas.md)。

## 测试

`pretext_py/layout_test.py` 中仅有两个测试未通过，因为内置的 `Intl.Segmenter` 与 JavaScript 版本仍存在些许差异。

## 示例

目前还原了两个示例：

1. [dragon_fast.py](/dragon_fast.py) – 由于字体和 pygame 的限制，部分文字（如阿拉伯语和 emoji）可能无法正常渲染。
2. [editorial_engine.py](/editorial_engine.py) – 渲染效果非常出色，视觉效果极佳。

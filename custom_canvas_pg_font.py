import re
import pygame
pygame.font.init()


# ------------------- 1. 字体信息解析 -------------------
class ParsedFont:
    """从 CSS font 简写字符串解析出的样式信息"""
    def __init__(self, font_str: str):
        self.font_str = font_str.strip()
        pattern = r'''(?ix)
            ^\s*
            (normal|italic|oblique)?\s*               # style
            (normal|bold|bolder|lighter|[1-9]00?)?\s* # weight
            (\d+(?:\.\d+)?)(px|pt)?\s*                # size
            (?:\/\s*\S+\s*)?                          # line-height (忽略)
            (.+)                                      # family
            \s*$
        '''
        m = re.match(pattern, self.font_str)
        if not m:
            raise ValueError(f"无法解析 font 字符串: {self.font_str!r}")

        self.style = (m.group(1) or "normal").lower()     # normal, italic, oblique
        self.weight_str = (m.group(2) or "normal").lower()
        self.size_px = float(m.group(3))                  # 点数（1px ≈ 1pt）
        # 字体族列表（逗号分隔）
        self.families = [f.strip().strip("'\"") for f in m.group(5).split(",") if f.strip()]

        # 转换 weight 为数值
        weight_map = {
            "normal": 400, "bold": 700,
            "bolder": 700, "lighter": 300,
        }
        self.weight = weight_map.get(self.weight_str,
                                     int(self.weight_str) if self.weight_str.isdigit() else 400)

    @property
    def is_bold(self) -> bool:
        return self.weight >= 700

    @property
    def is_oblique(self) -> bool:
        return self.style in ("italic", "oblique")


# ------------------- 2. 字体注册与缓存 -------------------
class FontRegistry:
    """
    管理 family → 字体文件的映射，支持粗体/斜体的文件回退和缓存。
    """
    def __init__(self):
        # 存储已注册的字体文件路径
        self._paths = {}
        # 缓存已加载的 Font 对象，键为 (family, bold, oblique, size)
        self._font_cache = {}

    def register(self, family: str,
                 regular: str,
                 bold = None,
                 italic = None,
                 bold_italic = None):
        """注册一个字体族的各种变体文件路径。"""
        family = family.lower()
        self._paths[(family, False, False)] = regular
        if bold:   self._paths[(family, True, False)] = bold
        if italic: self._paths[(family, False, True)] = italic
        if bold_italic: self._paths[(family, True, True)] = bold_italic

    def get_font_path_and_native_style(self, family: str, bold: bool, oblique: bool):
        """
        返回最匹配的字体文件路径以及该文件原生支持的样式标志。
        查找优先级：精确匹配 → 单变体 + 合成另一个 → 常规
        """
        family = family.lower()
        candidates = [
            (family, bold, oblique),
            (family, bold, False) if oblique else None,
            (family, False, oblique) if bold else None,
            (family, False, False),
        ]
        for key in candidates:
            if key is not None and key in self._paths:
                return self._paths[key], key[1], key[2]   # path, native_bold, native_oblique
        return None, False, False

    def get_font(self, family: str, bold: bool, oblique: bool, size: float):
        """
        获取 pygame.font.Font 对象（带缓存），若原生不支持所需样式则自动模拟。
        """
        size_int = int(round(max(1.0, size)))
        key = (family.lower(), bold, oblique, size_int)
        if key in self._font_cache:
            return self._font_cache[key]

        path, native_bold, native_oblique = self.get_font_path_and_native_style(family, bold, oblique)

        if path is not None:
            font = pygame.font.Font(path, size_int)
        else:
            # 回退到默认字体（pygame 内置字体，可通过 set_bold/set_italic 模拟）
            font = pygame.font.Font(None, size_int)

        # 若原生不支持且需要该样式，则模拟
        if bold and not native_bold:
            font.set_bold(True)
        if oblique and not native_oblique:
            font.set_italic(True)

        self._font_cache[key] = font
        return font


# ------------------- 3. 核心测量函数 -------------------
class Context:
    """
    提供类似 Canvas 的 measureText 功能，可设置全局注册表。
    """
    def __init__(self, registry = None):
        self.registry = registry or FontRegistry()
        self._font = '10px sans-serif'
        self.font_parse = ParsedFont(self._font)

    @property
    def font(self):
        return self._font

    @font.setter
    def font(self, value):
        self._font = value
        self.font_parse = ParsedFont(self._font)

    def get_font(self):
        """根据当前样式获取字体对象"""
        size = max(1.0, self.font_parse.size_px)
        family = self.font_parse.families[0]
        bold = self.font_parse.is_bold
        oblique = self.font_parse.is_oblique
        return self.registry.get_font(family, bold, oblique, size)

    def measureText(self, text: str) -> float:
        """
        测量文本渲染后的宽度（像素）。
        :return: 宽度（浮点数）
        """
        font = self.get_font()
        width = font.size(text)[0]
        return {'width': width}


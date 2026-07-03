import re

def pygame_init():
    import pygame.freetype
    from pygame.freetype import STYLE_NORMAL, STYLE_STRONG, STYLE_OBLIQUE
    pygame.freetype.init()
    return STYLE_NORMAL, STYLE_STRONG, STYLE_OBLIQUE, pygame


USE_CUSTOM_CANVES = False
CUSTOM_CANVES = None


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


# ------------------- 2. 字体注册与回退 -------------------
class FontRegistry:
    """
    管理 family → 字体文件的映射，支持粗体/斜体的文件回退和合成。
    """
    def __init__(self):
        # 存储已注册的字体文件路径
        self._paths = {}
        # 缓存已加载的 Font 对象
        self._fonts = {}

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

    def get_font(self, family: str, bold: bool, oblique: bool):
        """
        返回 (Font对象, 需要额外应用的 style 标志)。
        如果没有精确匹配的文件，则用最接近的文件 + STYLE_STRONG/STYLE_OBLIQUE 合成。
        """
        STYLE_NORMAL, STYLE_STRONG, STYLE_OBLIQUE, pygame = pygame_init()
        family = family.lower()
        # 查找优先级：精确匹配 → 单变体 + 合成另一个 → 常规
        candidates = [
            (family, bold, oblique),
            (family, bold, False) if oblique else None,
            (family, False, oblique) if bold else None,
            (family, False, False),
        ]
        path = None
        for key in candidates:
            if key is None:
                continue
            if key in self._paths:
                path = self._paths[key]
                # 记录哪些样式是由文件原生支持的
                native_bold = key[1]
                native_oblique = key[2]
                break

        if path:
            cache_key = (family, bold, oblique)
            if cache_key not in self._fonts:
                self._fonts[cache_key] = pygame.freetype.Font(path)
            font = self._fonts[cache_key]
        else:
            # 完全无注册时，使用 pygame 默认字体（不支持原生粗斜体）
            font = pygame.freetype.Font(None)
            native_bold = False
            native_oblique = False

        # 计算需要额外合成的样式
        extra_style = STYLE_NORMAL
        if bold and not native_bold:
            extra_style |= STYLE_STRONG
        if oblique and not native_oblique:
            extra_style |= STYLE_OBLIQUE

        return font, extra_style


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
        font, extra_style = self.registry.get_font(
            family=self.font_parse.families[0],
            bold=self.font_parse.is_bold,
            oblique=self.font_parse.is_oblique,
        )
        
        font.style = extra_style          # 注意：这会覆盖原有 style，因此用额外合成标志
        font.kerning = True
        font.origin = True
        font.pad = True
        return font
        
    def measureText(self, text: str) -> float:
        """
        测量文本渲染后的宽度（像素）。

        :param text: 要测量的文本
        :param font_spec: CSS font 字符串，例如 'italic bold 24px Arial'
        :return: 宽度（浮点数）
        """
        size = max(1.0, self.font_parse.size_px)
        # w = self.get_font().render(text, size=size)[0].get_rect().width
        w1 = self.get_font().get_rect(text, size=size).width
        return {'width': w1}


def get_context():
    if USE_CUSTOM_CANVES:
        return CUSTOM_CANVES
    return Context


def set_custom_canvas(custom_canvas):
    global CUSTOM_CANVES, USE_CUSTOM_CANVES  # pylint:disable=W0603
    CUSTOM_CANVES = custom_canvas
    USE_CUSTOM_CANVES = True

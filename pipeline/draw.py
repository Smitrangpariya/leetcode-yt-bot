"""Shared drawing helpers: fonts, text wrapping, syntax-highlighted code panel."""
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from pygments.lexers import JavaLexer, PythonLexer
from pygments.token import Token
import config

W, H = 1920, 1080

BG = (15, 17, 26)
PANEL = (24, 28, 42)
PANEL_HI = (40, 52, 86)
TEXT = (226, 230, 240)
MUTED = (140, 150, 175)
ACCENT = (255, 196, 61)
GREEN, AMBER, RED, BLUE = (74, 222, 128), (251, 191, 36), (248, 113, 113), (96, 165, 250)
DIFF_COLOR = {"Easy": GREEN, "Medium": AMBER, "Hard": RED}


def _find_font_path(candidates: list[str]) -> str | None:
    """Finds real TTF font path across Windows, Ubuntu/Linux, macOS, or project assets."""
    search_dirs: list[Path] = [
        Path(__file__).resolve().parent.parent / "assets" / "fonts"
    ]

    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", "C:\\Windows")
        search_dirs.append(Path(windir) / "Fonts")
    elif sys.platform == "darwin":
        search_dirs.extend([
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path.home() / "Library/Fonts"
        ])
    else:  # Linux / Ubuntu / GitHub Actions CI
        search_dirs.extend([
            Path("/usr/share/fonts/truetype/jetbrains-mono"),
            Path("/usr/share/fonts/truetype/dejavu"),
            Path("/usr/share/fonts/truetype/liberation"),
            Path("/usr/share/fonts/truetype/freefont"),
            Path("/usr/share/fonts/truetype"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".fonts"
        ])

    for name in candidates:
        for d in search_dirs:
            p = d / name
            if p.exists():
                return str(p)
        try:
            ImageFont.truetype(name, 20)
            return name
        except OSError:
            pass
    return None


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    """Loads fonts across Windows, Ubuntu Linux (GitHub Actions), and macOS."""
    if mono:
        candidates = [
            str(config.ASSETS / "JetBrainsMono-Regular.ttf"),
            "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
            "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        ]
    elif bold:
        candidates = [
            str(config.ASSETS / "Inter-Bold.ttf"),
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            str(config.ASSETS / "Inter-Regular.ttf"),
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split():
            test = f"{cur} {word}".strip()
            if draw.textlength(test, font=fnt) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def hex_to_rgb(h: str, default=(255, 196, 61)):
    try:
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default


def pill(draw, xy, text, fnt, fill, fg=(12, 14, 22), pad=(22, 10)):
    x, y = xy
    w = draw.textlength(text, font=fnt) + pad[0] * 2
    h = fnt.size + pad[1] * 2
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=fill)
    draw.text((x + pad[0], y + pad[1] - 2), text, font=fnt, fill=fg)
    return x + w + 14


# ---------- syntax highlighting ----------
def _color(tt):
    if tt in Token.Comment:
        return (106, 115, 140)
    if tt in Token.Keyword:
        return (198, 120, 221)
    if tt in Token.Name.Function or tt in Token.Name.Class:
        return (97, 175, 239)
    if tt in Token.Name.Builtin:
        return (86, 182, 194)
    if tt in Token.Literal.String:
        return (152, 195, 121)
    if tt in Token.Literal.Number:
        return (209, 154, 102)
    if tt in Token.Operator:
        return (86, 182, 194)
    return (220, 223, 228)


def tokenize(code: str) -> list[list[tuple[str, tuple]]]:
    """Tokenizes code with JavaLexer or PythonLexer based on code characteristics."""
    lines: list[list] = [[]]
    is_java = any(kw in code for kw in ("public ", "class ", "int[]", "void ", "String ", "Map<", "new ", "{", "}"))
    lexer = JavaLexer() if is_java else PythonLexer()

    for tt, val in lexer.get_tokens(code.rstrip("\n")):
        parts = val.split("\n")
        for i, p in enumerate(parts):
            if i > 0:
                lines.append([])
            if p:
                lines[-1].append((p, _color(tt)))
    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    return lines


def _dim(c, panel=PANEL, k=0.62):
    return tuple(int(c[i] * (1 - k) + panel[i] * k) for i in range(3))


def draw_code(img: Image.Image, code: str, box: tuple, visible: int | None = None,
              active: tuple | None = None, accent=ACCENT) -> None:
    """Draw a code panel. visible = number of lines revealed; active = (first, last) highlighted lines."""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=22, fill=PANEL)
    toks = tokenize(code)
    n = len(toks)
    pad = 26
    line_h = min(52, (y1 - y0 - 2 * pad) // max(n, 1))
    fsz = max(18, int(line_h * 0.66))
    f = font(fsz, mono=True)
    gutter = int(fsz * 2.4)
    visible = n if visible is None else visible
    for i, segs in enumerate(toks, 1):
        if i > visible:
            break
        y = y0 + pad + (i - 1) * line_h
        is_act = active and active[0] <= i <= active[1]
        if is_act:
            d.rectangle((x0 + 10, y - 2, x1 - 10, y + line_h - 4), fill=PANEL_HI)
            d.rectangle((x0 + 10, y - 2, x0 + 16, y + line_h - 4), fill=accent)
        dim = active is not None and not is_act
        d.text((x0 + pad, y), str(i), font=f, fill=_dim(MUTED) if dim else MUTED)
        x = x0 + pad + gutter
        for text, col in segs:
            d.text((x, y), text, font=f, fill=_dim(col) if dim else col)
            x += d.textlength(text, font=f)
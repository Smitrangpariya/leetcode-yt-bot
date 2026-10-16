"""Thumbnail: bold hook text, gradient from a trending-inspired palette, code card, difficulty chip."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from . import draw as D

TW, TH = 1280, 720

PALETTES = [  # fallback palettes (rotated by problem id)
    ("#1b1464", "#0f7bff", "#ffd400"),
    ("#2b0a3d", "#ff3d71", "#fff176"),
    ("#06283d", "#00c2a8", "#ffe14d"),
    ("#2d1b00", "#ff7a18", "#ffffff"),
]


def make(problem: dict, meta: dict, code: str, out: Path) -> Path:
    pal = meta.get("palette") or {}
    fb = PALETTES[int(str(problem["id"]).isdigit() and problem["id"] or 0) % len(PALETTES)]
    bg1 = D.hex_to_rgb(pal.get("bg1", fb[0]), D.hex_to_rgb(fb[0]))
    bg2 = D.hex_to_rgb(pal.get("bg2", fb[1]), D.hex_to_rgb(fb[1]))
    acc = D.hex_to_rgb(pal.get("accent", fb[2]), D.hex_to_rgb(fb[2]))

    img = Image.new("RGB", (TW, TH), bg1)
    px = img.load()
    for y in range(TH):  # diagonal gradient
        for x in range(0, TW):
            t = (x / TW * 0.6 + y / TH * 0.4)
            px[x, y] = tuple(int(bg1[i] * (1 - t) + bg2[i] * t) for i in range(3))

    # Java code card (right), slightly shadowed; formatted to fit cleanly
    lines = [(l[:36] + "…") if len(l) > 38 else l for l in code.splitlines()[:8]]
    cw, ch = 640, 360
    card = Image.new("RGB", (cw, ch), D.PANEL)
    D.draw_code(card, "\n".join(lines), (0, 0, cw, ch), active=None)
    shadow = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((600, 240, 600 + cw, 240 + ch), radius=24, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(18))).convert("RGB")
    img.paste(card, (580, 220))

    d = ImageDraw.Draw(img)
    # Badges
    x = D.pill(d, (50, 40), f"LeetCode #{problem['id']}", D.font(34, True), (255, 255, 255))
    x = D.pill(d, (x, 40), problem["difficulty"].upper(), D.font(34, True), D.DIFF_COLOR.get(problem["difficulty"], acc))
    D.pill(d, (x, 40), "JAVA", D.font(34, True), acc, fg=(12, 14, 22))

    # Hook text (scaled TrueType font)
    text = (meta.get("thumb_text") or problem["title"]).upper()
    fnt = D.font(114, True)
    lines = D.wrap(d, text, fnt, 510)
    if len(lines) > 3:
        fnt = D.font(88, True)
        lines = D.wrap(d, text, fnt, 510)
    y = 140
    for i, ln in enumerate(lines[:4]):
        col = acc if i == len(lines[:4]) - 1 else (255, 255, 255)
        d.text((50, y), ln, font=fnt, fill=col, stroke_width=7, stroke_fill=(10, 10, 20))
        y += fnt.size + 10

    sub = meta.get("thumb_sub") or "ALL APPROACHES"
    D.pill(d, (50, TH - 110), sub.upper(), D.font(40, True), acc)
    img.save(out, quality=92)
    return out
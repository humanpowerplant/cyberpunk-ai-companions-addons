"""Render original geometric release title cards, not game screenshots.

Optional publishing tool: Pillow and a Japanese-capable system font are needed.
No web request, game asset, official logo, UI capture, or font file is bundled.
"""
from pathlib import Path
import argparse
import html
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "media/titlecards"
W, H = 1920, 1080
BG, PANEL, TEXT, MUTED, CYAN, GOLD = "#08191f", "#102a32", "#edf7f7", "#a8c1c9", "#4bd6d1", "#f7ca65"


def render(kind, font_path):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', f'<rect width="{W}" height="{H}" fill="{BG}"/>']

    def rect(box, fill, outline=None, radius=0, width=2):
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
        x, y, right, bottom = box
        svg.append(f'<rect x="{x}" y="{y}" width="{right-x}" height="{bottom-y}" rx="{radius}" fill="{fill or "none"}" stroke="{outline or "none"}" stroke-width="{width}"/>')

    def line(points, fill=CYAN, width=3):
        draw.line(points, fill=fill, width=width)
        svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{fill}" stroke-width="{width}"/>')

    def text(x, y, value, size=36, fill=TEXT):
        font = ImageFont.truetype(str(font_path), size)
        draw.text((x, y), value, font=font, fill=fill, anchor="lt")
        svg.append(f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" font-family="BIZ UDGothic, Noto Sans CJK JP, Yu Gothic, sans-serif" font-size="{size}" fill="{fill}">{html.escape(value)}</text>')

    def box(x, y, width, height, title, note=None):
        rect((x, y, x+width, y+height), PANEL, CYAN, 16)
        text(x+25, y+22, title, 34)
        if note:
            text(x+25, y+76, note, 24, MUTED)

    for x in range(40, W, 80):
        line([(x, 0), (x, H)], "#0d252c", 1)
    for y in range(40, H, 80):
        line([(0, y), (W, y)], "#0d252c", 1)
    rect((48, 48, W-48, H-48), None, "#28535d", 22)
    rect((92, 104, 110, 884), CYAN)
    text(146, 110, "AI COMPANIONS", 46, CYAN)
    text(148, 174, "COMMUNITY ADD-ON", 24, MUTED)

    if kind == "japanese":
        text(144, 278, "日本語会話・", 92)
        text(144, 402, "人物設定拡張", 92)
        text(148, 559, "一人称・呼び方・人物像を、日本語で。", 34, MUTED)
        for x, label in ((148, "人物設定"), (410, "ゲーム状況"), (704, "会話の自然さ")):
            width = 236 if x == 148 else 268
            rect((x, 668, x+width, 742), PANEL, "#28535d", 12)
            text(x+22, 688, label, 31, GOLD)
        box(1160, 280, 580, 125, "人物設定", "一人称 / 話し方 / 知識の範囲")
        line([(1450, 405), (1450, 465)])
        box(1160, 465, 580, 125, "日本語の会話", "利用者が選んだAIプロバイダー")
        line([(1450, 650), (1450, 590)])
        box(1160, 650, 580, 125, "現在のゲーム状況", "取得できた場所・クエスト・所持金等")
        text(1170, 819, "機能の概念図 / 実ゲーム画面ではありません", 22, MUTED)
        text(148, 824, "AI Companions 0.4.6向け", 32, CYAN)
    else:
        text(144, 267, "PARTY", 108)
        text(144, 405, "CONVERSATIONS", 92)
        text(148, 547, "AND CODEX BRIDGE", 48, GOLD)
        text(148, 657, "Let companions talk. Let V answer.", 33, MUTED)
        text(148, 721, "Optional Codex. Your chosen provider.", 29, MUTED)
        box(1160, 300, 260, 120, "NPC A")
        box(1490, 300, 260, 120, "NPC B")
        line([(1420, 360), (1490, 360)], GOLD)
        line([(1490, 377), (1420, 377)], CYAN)
        line([(1290, 420), (1290, 520), (1450, 520)])
        line([(1620, 420), (1620, 520), (1450, 520)])
        line([(1450, 520), (1450, 590)], GOLD)
        box(1310, 590, 280, 120, "V", "Optional replies")
        text(1170, 772, "Shared experiences. Individual reactions.", 24, MUTED)
        text(1170, 822, "Concept diagram / not a game screenshot", 22, MUTED)
        text(148, 824, "CLI cloud access uses your own account.", 28, CYAN)
    rect((92, 922, 1828, 988), "#0b222a", None, 10)
    text(124, 944, "Requires AI Companions 0.4.6  /  Cyberpunk 2077 2.5  /  Unofficial add-on", 26, MUTED)
    svg.append("</svg>")
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(OUT / f"{kind}-cover-1920x1080.png")
    image.resize((960, 540), Image.Resampling.LANCZOS).save(OUT / f"{kind}-thumbnail-960x540.png")
    (OUT / f"{kind}-cover.svg").write_text("\n".join(svg)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    candidates = [args.font] if args.font else [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/BIZ-UDGothicB.ttc", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")]
    font = next((p for p in candidates if p and p.is_file()), None)
    if not font:
        raise SystemExit("Supply --font with a Japanese-capable system font")
    for kind in ("japanese", "codex"):
        render(kind, font)
    print("Rendered two original title cards and thumbnails; no screenshots or game assets used.")


if __name__ == "__main__":
    main()

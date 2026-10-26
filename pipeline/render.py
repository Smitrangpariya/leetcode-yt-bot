"""Compiles visual beat frames + TTS audio segments into final 1080p MP4."""
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import config
from . import draw as D

W, H = 1920, 1080
PAD = 70


def _draw_header(img: Image.Image, problem: dict, title: str = ""):
    """Draws top navigation bar with problem info and channel branding."""
    d = ImageDraw.Draw(img)
    f_sub = D.font(26, bold=True)
    prob_str = f"LeetCode #{problem.get('id', '1')} • {problem.get('title', 'Problem')}"
    d.text((PAD, 50), prob_str, font=f_sub, fill=D.MUTED)

    channel_title = config.CHANNEL_NAME
    f_chan = D.font(28, bold=True)
    w_chan = d.textlength(channel_title, font=f_chan)
    d.text((W - PAD - w_chan, 48), channel_title, font=f_chan, fill=D.ACCENT)


def _draw_bottom_subtitle(img: Image.Image, text: str):
    """Draws clean subtitle pill at the bottom."""
    if not text:
        return
    d = ImageDraw.Draw(img)
    f = D.font(26)
    lines = D.wrap(d, text, f, W - (PAD * 2) - 80)
    if not lines:
        return

    card_h = len(lines[:2]) * 36 + 32
    card_y = H - card_h - 40
    d.rounded_rectangle((PAD, card_y, W - PAD, card_y + card_h), radius=16, fill=(20, 24, 34), outline=D.PANEL_HI, width=2)
    y = card_y + 16
    for line in lines[:2]:
        d.text((PAD + 40, y), line, font=f, fill=D.TEXT)
        y += 36



def _draw_info_cards(img: Image.Image, cards: list[dict], top: int):
    """Draw strategy/complexity cards on explanatory text slides."""
    if not cards:
        return

    d = ImageDraw.Draw(img)
    gap = 22
    count = len(cards)
    card_w = (W - 2 * PAD - gap * (count - 1)) // count
    card_h = 330

    for i, card in enumerate(cards):
        x = PAD + i * (card_w + gap)
        d.rounded_rectangle(
            (x, top, x + card_w, top + card_h),
            radius=22,
            fill=D.PANEL,
            outline=D.PANEL_HI,
            width=2,
        )

        label = str(card.get("label", "")).upper()
        label_font = D.font(22, bold=True)
        for line_no, line in enumerate(D.wrap(d, label, label_font, card_w - 48)[:2]):
            d.text((x + 24, top + 24 + line_no * 28), line, font=label_font, fill=D.ACCENT)

        value = str(card.get("value", ""))
        value_font = D.font(34, bold=True)
        value_lines = D.wrap(d, value, value_font, card_w - 48)[:2]
        value_y = top + 94
        for line in value_lines:
            d.text((x + 24, value_y), line, font=value_font, fill=D.GREEN)
            value_y += 42

        detail = str(card.get("detail", ""))
        detail_font = D.font(25)
        detail_lines = D.wrap(d, detail, detail_font, card_w - 48)[:4]
        detail_y = max(top + 166, value_y + 8)
        for line in detail_lines:
            if detail_y > top + card_h - 32:
                break
            d.text((x + 24, detail_y), line, font=detail_font, fill=D.TEXT)
            detail_y += 33


def _draw_array_visual(img: Image.Image, visual: dict, top: int):
    """Draw input array values and zero-based indices as a compact diagram."""
    values = visual.get("values", [])
    if not values:
        return

    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        (PAD, top, W - PAD, top + 220),
        radius=22,
        fill=D.PANEL,
        outline=D.PANEL_HI,
        width=2,
    )
    d.text(
        (PAD + 28, top + 18),
        "SAMPLE ARRAY  •  ZERO-BASED INDEX",
        font=D.font(23, bold=True),
        fill=D.ACCENT,
    )

    gap = 10
    inner_w = W - 2 * PAD - 56
    cell_w = min(150, (inner_w - gap * (len(values) - 1)) // len(values))
    total_w = len(values) * cell_w + (len(values) - 1) * gap
    start_x = (W - total_w) // 2
    highlights = set(visual.get("highlight_indices", []))

    for index, value in enumerate(values):
        x = start_x + index * (cell_w + gap)
        highlighted = index in highlights
        d.rounded_rectangle(
            (x, top + 64, x + cell_w, top + 132),
            radius=12,
            fill=D.PANEL_HI if highlighted else D.BG,
            outline=D.ACCENT if highlighted else D.PANEL_HI,
            width=2,
        )

        text = str(value)
        value_font = D.font(27, bold=highlighted, mono=True)
        while len(text) > 1 and d.textlength(text, font=value_font) > cell_w - 14:
            text = text[:-1]

        d.text(
            (x + cell_w / 2, top + 98),
            text,
            font=value_font,
            fill=D.TEXT,
            anchor="mm",
        )
        d.text(
            (x + cell_w / 2, top + 163),
            f"index {index}",
            font=D.font(19),
            fill=D.ACCENT if highlighted else D.MUTED,
            anchor="mm",
        )


def render_frame(beat: dict, problem: dict) -> Image.Image:
    spec = beat.get("spec", {})
    layout = spec.get("layout", "text")
    say = beat.get("say", "")

    img = Image.new("RGB", (W, H), D.BG)
    d = ImageDraw.Draw(img)

    if layout == "title":
        diff = problem.get("difficulty", "Easy")
        x = D.pill(d, (PAD, 180), f"LeetCode #{problem.get('id', '1')}", D.font(32, True), (255, 255, 255))
        x = D.pill(d, (x, 180), diff.upper(), D.font(32, True), D.DIFF_COLOR.get(diff, D.ACCENT))
        D.pill(d, (x, 180), "JAVA", D.font(32, True), D.ACCENT)

        f_hero = D.font(92, bold=True)
        d.text((PAD, 290), problem.get("title", "Problem"), font=f_hero, fill=(255, 255, 255))

        f_sub = D.font(40)
        d.text((PAD, 410), "All approaches, explained step by step", font=f_sub, fill=D.ACCENT)

        topics = spec.get("topics", "")
        if topics:
            d.text((PAD, 470), topics, font=D.font(28), fill=D.MUTED)

    elif layout == "text":
        _draw_header(img, problem)
        head = spec.get("heading", "")
        d.text((PAD, 130), head, font=D.font(52, bold=True), fill=D.ACCENT)

        paras = spec.get("paras", [])
        y = 220
        for p in paras:
            lines = D.wrap(d, p, D.font(34), W - (PAD * 2))
            for line in lines:
                d.text((PAD, y), line, font=D.font(34), fill=D.TEXT)
                y += 48
            y += 20

        example = spec.get("example")
        if example:
            card_box = (PAD, y + 10, W - PAD, y + 170)
            d.rounded_rectangle(card_box, radius=18, fill=D.PANEL, outline=D.PANEL_HI, width=2)
            ey = y + 35
            for k, v in example:
                D.pill(d, (PAD + 30, ey), k, D.font(24, True), D.ACCENT)
                d.text((PAD + 170, ey + 4), str(v), font=D.font(28, mono=True), fill=D.TEXT)
                ey += 56

        cards = spec.get("cards", [])
        if cards:
            _draw_info_cards(img, cards, top=max(y + 28, 350))

        array_visual = spec.get("array_visual")
        if array_visual:
            visual_top = max(y + (190 if example else 30), 390)
            _draw_array_visual(img, array_visual, top=visual_top)

    elif layout == "code":
        _draw_header(img, problem)
        head = spec.get("heading", "")
        d.text((PAD, 120), head, font=D.font(42, bold=True), fill=D.ACCENT)

        code_text = spec.get("code", "")
        visible = spec.get("visible")
        active = spec.get("active")
        cw = 1080
        ch = 700

        code_panel = Image.new("RGB", (cw, ch), D.PANEL)
        D.draw_code(code_panel, code_text, (0, 0, cw, ch), visible=visible, active=active)
        img.paste(code_panel, (PAD, 190))

        mode = spec.get("mode")
        rx = PAD + cw + 40
        rw = W - rx - PAD
        r_box = (rx, 190, rx + rw, 190 + ch)
        d.rounded_rectangle(r_box, radius=22, fill=D.PANEL, outline=D.PANEL_HI, width=2)

        if mode == "step":
            step_idx, step_tot = spec.get("step", (1, 1))
            d.text((rx + 35, 225), f"Step {step_idx} of {step_tot}", font=D.font(36, bold=True), fill=D.TEXT)
            lines_tuple = spec.get("active", (1, 1))
            d.text((rx + 35, 275), f"Lines {lines_tuple[0]}-{lines_tuple[1]}", font=D.font(24), fill=D.MUTED)

            d.text((rx + 35, 340), "Live variables", font=D.font(28, bold=True), fill=D.ACCENT)
            watch = spec.get("watch", {})
            vy = 400
            if watch:
                for var_k, var_v in watch.items():
                    d.rounded_rectangle((rx + 35, vy, rx + rw - 35, vy + 75), radius=12, fill=D.BG, outline=D.PANEL_HI)
                    d.text((rx + 55, vy + 12), str(var_k), font=D.font(22), fill=D.BLUE)
                    d.text((rx + 55, vy + 40), str(var_v)[:30], font=D.font(24, mono=True), fill=D.TEXT)
                    vy += 90
            else:
                d.text((rx + 35, vy), "Tracing execution...", font=D.font(24), fill=D.MUTED)

        elif mode == "done":
            d.text((rx + 35, 230), "Complexity", font=D.font(38, bold=True), fill=D.ACCENT)
            d.text((rx + 35, 310), "Time", font=D.font(26), fill=D.MUTED)
            d.text((rx + 35, 350), spec.get("time", "O(N)"), font=D.font(38, bold=True, mono=True), fill=D.GREEN)

            d.text((rx + 35, 450), "Space", font=D.font(26), fill=D.MUTED)
            d.text((rx + 35, 490), spec.get("space", "O(1)"), font=D.font(38, bold=True, mono=True), fill=D.BLUE)

        else:
            d.text((rx + 35, 230), "Writing the code...", font=D.font(32), fill=D.MUTED)

    elif layout == "table":
        _draw_header(img, problem)
        d.text((PAD, 130), "Side by Side", font=D.font(52, bold=True), fill=D.ACCENT)

        tbl_box = (PAD, 220, W - PAD, 680)
        d.rounded_rectangle(tbl_box, radius=22, fill=D.PANEL, outline=D.PANEL_HI, width=2)

        d.text((PAD + 50, 260), "Approach", font=D.font(30, bold=True), fill=D.MUTED)
        d.text((PAD + 650, 260), "Time", font=D.font(30, bold=True), fill=D.MUTED)
        d.text((PAD + 1200, 260), "Space", font=D.font(30, bold=True), fill=D.MUTED)
        d.line([(PAD, 320), (W - PAD, 320)], fill=D.PANEL_HI, width=2)

        ty = 360
        for i, (name, t_comp, s_comp) in enumerate(spec.get("rows", [])):
            if i % 2 == 1:
                d.rectangle((PAD + 2, ty - 15, W - PAD - 2, ty + 65), fill=(30, 35, 52))
            is_opt = "optimal" in name.lower() or "hash" in name.lower()
            col = D.GREEN if is_opt else D.TEXT
            d.text((PAD + 50, ty), name[:32], font=D.font(32, bold=True), fill=col)
            d.text((PAD + 650, ty), t_comp, font=D.font(32, mono=True), fill=col)
            d.text((PAD + 1200, ty), s_comp, font=D.font(32, mono=True), fill=col)
            ty += 90

    elif layout == "outro":
        card_box = (200, 180, W - 200, H - 240)
        d.rounded_rectangle(card_box, radius=24, fill=D.PANEL, outline=D.PANEL_HI, width=2)

        d.text((280, 250), "Thanks for watching!", font=D.font(72, bold=True), fill=(255, 255, 255))
        d.text((280, 350), "A new LeetCode problem every single day.", font=D.font(40, bold=True), fill=D.ACCENT)
        d.text((280, 420), "Subscribe and turn on the bell so you never miss one.", font=D.font(32), fill=D.MUTED)
        d.text((280, 520), config.CHANNEL_NAME, font=D.font(44, bold=True), fill=D.ACCENT)

    _draw_bottom_subtitle(img, say)
    return img


def build_video(beats: list[dict], problem: dict, work_dir: Path, seed: int = 1) -> tuple[Path, list[str]]:
    """Synthesizes voice, renders visual frames, and compiles MP4 with FFmpeg."""
    from . import tts

    frames_dir = work_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    audio_dir = work_dir / "audio"
    audio_dir.mkdir(exist_ok=True)

    concat_file = work_dir / "concat.txt"
    chapters = []
    current_time = 0.0

    print(f"\nCompiling {len(beats)} beats using {config.LANGUAGE.upper()} narration...")

    with open(concat_file, "w", encoding="utf-8") as f_concat:
        for idx, beat in enumerate(beats):
            chapter = beat.get("chapter")
            if chapter:
                mins = int(current_time // 60)
                secs = int(current_time % 60)
                chapters.append(f"{mins:02d}:{secs:02d} {chapter}")

            frame_img = render_frame(beat, problem)
            frame_path = frames_dir / f"beat_{idx:03d}.png"
            frame_img.save(frame_path)

            say_text = beat.get("say", "")
            audio_path = audio_dir / f"beat_{idx:03d}.mp3"

            if say_text.strip():
                # Reuse valid cached audio if already downloaded
                if audio_path.exists() and audio_path.stat().st_size > 1000:
                    dur = tts.get_audio_duration(audio_path)
                else:
                    dur = tts.synthesize(say_text, audio_path)
                    time.sleep(0.25)  # Gentle delay between requests to avoid 403 blocks
            else:
                dur = beat.get("dur", 0.1)

            f_concat.write(f"file '{frame_path.resolve().as_posix()}'\n")
            f_concat.write(f"duration {dur:.3f}\n")
            current_time += dur
            print(f"  beat {idx + 1}/{len(beats)} done ({dur:.1f}s)", flush=True)
    
        if beats:
            last_frame = frames_dir / f"beat_{len(beats)-1:03d}.png"
            f_concat.write(f"file '{last_frame.resolve().as_posix()}'\n")
            f_concat.write("duration 3.500\n")

    combined_audio = work_dir / "full_audio.mp3"
    tts.combine_audios([audio_dir / f"beat_{i:03d}.mp3" for i in range(len(beats))], combined_audio)

    output_video = work_dir / "final.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(combined_audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(output_video)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_video, chapters

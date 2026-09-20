"""Simple image card generator (PIL) — Instagram feed image ke liye"""
from PIL import Image, ImageDraw, ImageFont


def _wrap(text, width=18):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines[:6]


def _font(size):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()


def make_card(hook, footer="CGL PREPARATION DAILY"):
    """1080x1350 (4:5 feed) image with big hook text."""
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), (11, 20, 26))
    d = ImageDraw.Draw(img)

    # accent bar
    d.rectangle([0, 0, W, 14], fill=(251, 191, 36))
    d.rectangle([0, H - 14, W, H], fill=(251, 191, 36))

    # big hook text (centered)
    text = hook[:110]
    size = 88
    font = _font(size)
    lines = _wrap(text, 14)
    # fit vertically
    while len(lines) * int(size * 1.25) > H - 400 and size > 40:
        size -= 8
        font = _font(size)
        lines = _wrap(text, 14)
    y = (H - len(lines) * int(size * 1.25)) // 2
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        d.text(((W - tw) // 2, y), line, font=font, fill=(233, 237, 239))
        y += int(size * 1.25)

    # footer
    ffont = _font(36)
    bbox = d.textbbox((0, 0), footer, font=ffont)
    d.text(((W - (bbox[2] - bbox[0])) // 2, H - 120), footer, font=ffont, fill=(251, 191, 36))

    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()

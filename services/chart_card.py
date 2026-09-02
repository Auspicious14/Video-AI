import re
from pathlib import Path
from PIL import Image, ImageDraw
from services.renderer import _find_font

_NUMBER_PATTERN = re.compile(
    r'(\$?\d[\d,]*\.?\d*\s*(?:%|percent|million|billion|trillion|thousand|GW|TWh|kWh)?)',
    re.IGNORECASE,
)


def extract_key_stat(text: str) -> tuple[str, str] | None:
    """Pull the real number from narration instead of asking an AI image
    model to invent a chart — this is what was producing generic, wrong,
    duplicate-looking 'charts' with no real data behind them."""
    matches = _NUMBER_PATTERN.findall(text)
    if not matches:
        return None
    stat = max(matches, key=len).strip()
    return (stat, text.strip()) if len(stat) >= 2 else None


def create_stat_card(
    stat: str, context: str, output_path: Path, width: int, height: int,
    bg_color: tuple = (18, 20, 28), accent_color: tuple = (70, 120, 230),
) -> Path:
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    stat_font = _find_font(min(width, height) // 4)
    context_font = _find_font(min(width, height) // 22)

    stat_w = draw.textlength(stat, font=stat_font)
    draw.text(((width - stat_w) / 2, height * 0.38), stat, font=stat_font, fill=accent_color)

    max_w = int(width * 0.8)
    words, lines, current = context.split(), [], []
    for word in words:
        test = " ".join(current + [word])
        if draw.textlength(test, font=context_font) > max_w and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    for i, line in enumerate(lines[:2]):
        w = draw.textlength(line, font=context_font)
        draw.text(((width - w) / 2, height * 0.6 + i * (context_font.size + 10)), line, font=context_font, fill=(230, 230, 235))

    img.save(output_path, "JPEG", quality=92)
    return output_path
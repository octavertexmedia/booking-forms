"""Compose 1200×630 Open Graph images from the real Cafe Orelo flyer photo."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

FOREST = (11, 31, 18, 255)
FOREST_DEEP = (6, 20, 11, 255)
FOREST_MID = (20, 48, 28, 255)
LIME = (162, 212, 0, 255)
GOLD = (255, 213, 79, 255)
GOLD_DEEP = (245, 196, 0, 255)
MAGENTA = (226, 24, 106, 255)
PAPER = (255, 246, 220, 255)
WHITE = (255, 255, 255, 255)
INK = (16, 32, 22, 255)

CANVAS = (1200, 630)
PHOTO_W = 500

FONT_FILES = {
    "playfair": (
        "PlayfairDisplay-Bold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    ),
    "oswald": (
        "Oswald-SemiBold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    ),
    "outfit": (
        "Outfit-SemiBold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/outfit/Outfit%5Bwght%5D.ttf",
    ),
    "vibes": (
        "GreatVibes-Regular.ttf",
        "https://github.com/google/fonts/raw/main/ofl/greatvibes/GreatVibes-Regular.ttf",
    ),
}

MAC_FALLBACKS = {
    "playfair": [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
    ],
    "oswald": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "outfit": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "vibes": [
        "/System/Library/Fonts/Supplemental/Snell Roundhand.ttc",
        "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
    ],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _images_dir() -> Path:
    return _repo_root() / "workshop" / "static" / "workshop" / "images"


def _fonts_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "og_fonts"


def _ensure_font(name: str) -> Path | None:
    filename, url = FONT_FILES[name]
    dest = _fonts_dir() / filename
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            dest.write_bytes(response.read())
        if dest.stat().st_size > 1000:
            return dest
    except Exception:
        dest.unlink(missing_ok=True)
    for fallback in MAC_FALLBACKS[name]:
        path = Path(fallback)
        if path.exists():
            return path
    return None


def _font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _ensure_font(name)
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.load_default()


def _cover_crop(image: Image.Image, size: tuple[int, int], *, focus=(0.55, 0.42)) -> Image.Image:
    target_w, target_h = size
    src = image.convert("RGBA")
    scale = max(target_w / src.width, target_h / src.height)
    resized = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.Resampling.LANCZOS)
    left = int((resized.width - target_w) * focus[0])
    top = int((resized.height - target_h) * focus[1])
    left = max(0, min(left, resized.width - target_w))
    top = max(0, min(top, resized.height - target_h))
    return resized.crop((left, top, left + target_w, top + target_h))


def _flyer_photo() -> Image.Image:
    images = _images_dir()
    flyer = Image.open(images / "tiramisu-workshop-flyer.png")
    w, h = flyer.size
    # Right-hand chef + tiramisu on the square flyer — never stretch the whole card.
    box = (int(w * 0.515), int(h * 0.015), w, h)
    return flyer.crop(box)


def _white_logo() -> Image.Image:
    logo = Image.open(_images_dir() / "cafe-orelo-logo.png").convert("RGBA")
    rgb = ImageOps.invert(logo.convert("RGB"))
    rgb.putalpha(logo.getchannel("A"))
    return rgb


def _rounded_rect(draw: ImageDraw.ImageDraw, box, fill, radius: int) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _draw_text(draw, xy, text, font, fill, anchor="lt") -> None:
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def compose(variant: str = "home") -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, FOREST)
    draw = ImageDraw.Draw(canvas)

    # Soft vignette on the copy side.
    wash = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    wash_draw = ImageDraw.Draw(wash)
    wash_draw.rectangle((0, 0, 760, 630), fill=FOREST_DEEP)
    canvas = Image.alpha_composite(canvas, wash.filter(ImageFilter.GaussianBlur(48)))
    draw = ImageDraw.Draw(canvas)

    photo = _cover_crop(_flyer_photo(), (PHOTO_W, CANVAS[1]), focus=(0.35, 0.38))
    # Warm the photo slightly so cocoa and gold match the flyer.
    photo = ImageEnhance.Color(photo).enhance(1.08)
    photo = ImageEnhance.Contrast(photo).enhance(1.04)
    canvas.paste(photo, (CANVAS[0] - PHOTO_W, 0), photo)

    # Fade photo into forest so type stays readable.
    fade = Image.new("RGBA", (90, CANVAS[1]), (0, 0, 0, 0))
    fade_draw = ImageDraw.Draw(fade)
    for x in range(90):
        alpha = int(255 * (1 - x / 89))
        fade_draw.line((x, 0, x, CANVAS[1]), fill=(11, 31, 18, alpha))
    canvas.paste(fade, (CANVAS[0] - PHOTO_W, 0), fade)

    gold_rule = Image.new("RGBA", (8, CANVAS[1]), GOLD)
    canvas.paste(gold_rule, (CANVAS[0] - PHOTO_W - 8, 0))

    lime_edge = Image.new("RGBA", (CANVAS[0], 8), LIME)
    canvas.paste(lime_edge, (0, 0))
    canvas.paste(Image.new("RGBA", (CANVAS[0], 8), GOLD), (0, CANVAS[1] - 8))

    draw = ImageDraw.Draw(canvas)
    logo = _white_logo()
    logo.thumbnail((210, 90), Image.Resampling.LANCZOS)
    canvas.paste(logo, (56, 36), logo)

    playfair = _font("playfair", 78)
    playfair_sm = _font("playfair", 36)
    oswald = _font("oswald", 34)
    oswald_sm = _font("oswald", 22)
    outfit = _font("outfit", 26)
    outfit_sm = _font("outfit", 20)
    vibes = _font("vibes", 40)

    _draw_text(draw, (56, 138), "Learn. Create. Indulge.", vibes, GOLD)
    _draw_text(draw, (56, 196), "TIRAMISU", playfair, PAPER)
    _draw_text(draw, (56, 278), "MAKING WORKSHOP", oswald, LIME)

    banner = (56, 332, 430, 378)
    _rounded_rect(draw, banner, LIME, 22)
    _draw_text(draw, (243, 355), "EGGLESS TIRAMISU MAKING", oswald_sm, FOREST, anchor="mm")

    facts = [
        "Sunday 23 August 2026",
        "3:00 PM – 5:00 PM  ·  Cafe Orelo",
        "Chef Aanchal Wadhwa",
    ]
    y = 404
    for line in facts:
        _draw_text(draw, (56, y), line, outfit, PAPER)
        y += 34

    price_box = (56, 516, 248, 574)
    label_box = (248, 516, 430, 574)
    _rounded_rect(draw, price_box, MAGENTA, 8)
    _rounded_rect(draw, label_box, GOLD, 8)
    # square the meeting edge
    draw.rectangle((240, 516, 256, 574), fill=MAGENTA)
    draw.rectangle((248, 516, 256, 574), fill=GOLD)
    _draw_text(draw, (152, 545), "₹1499/-", playfair_sm, WHITE, anchor="mm")
    _draw_text(draw, (339, 545), "per seat", outfit_sm, INK, anchor="mm")

    footer = (
        "bookings.healthyome.in"
        if variant == "home"
        else "Book at bookings.healthyome.in"
    )
    _draw_text(draw, (56, 598), footer, outfit_sm, GOLD)

    if variant == "home":
        _draw_text(draw, (430, 598), "HealthyOme Bookings", outfit_sm, (255, 246, 220, 180), anchor="rt")

    return canvas.convert("RGB")


def compose_apple_touch() -> Image.Image:
    size = 180
    tile = Image.new("RGBA", (size, size), FOREST)
    logo = _white_logo()
    logo.thumbnail((148, 64), Image.Resampling.LANCZOS)
    x = (size - logo.width) // 2
    y = (size - logo.height) // 2
    tile.paste(logo, (x, y), logo)
    border = ImageDraw.Draw(tile)
    border.rectangle((4, 4, size - 5, size - 5), outline=GOLD, width=4)
    return tile


class Command(BaseCommand):
    help = "Render 1200×630 Cafe Orelo Open Graph images from the real flyer photo."

    def handle(self, *args, **options):
        images = _images_dir()
        images.mkdir(parents=True, exist_ok=True)
        home = compose("home")
        event = compose("event")
        home_path = images / "og-home.png"
        event_path = images / "og-tiramisu.png"
        home.save(home_path, "PNG", optimize=True)
        event.save(event_path, "PNG", optimize=True)

        apple = compose_apple_touch()
        apple_path = images / "apple-touch-icon.png"
        apple.save(apple_path, "PNG", optimize=True)

        self.stdout.write(self.style.SUCCESS(f"Wrote {home_path} ({home.size[0]}×{home.size[1]})"))
        self.stdout.write(self.style.SUCCESS(f"Wrote {event_path} ({event.size[0]}×{event.size[1]})"))
        self.stdout.write(self.style.SUCCESS(f"Wrote {apple_path} ({apple.size[0]}×{apple.size[1]})"))

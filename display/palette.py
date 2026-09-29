"""Colours used by the display: theme constants and map colour names."""

import colorsys

import pygame

Color = tuple[int, int, int]

BACKGROUND: Color = (24, 30, 49)
INTERIOR: Color = (34, 42, 68)
PANEL: Color = (29, 36, 58)
GRID: Color = (42, 51, 80)
LINK: Color = (84, 98, 148)
TRACK: Color = (48, 58, 92)
TEXT: Color = (222, 228, 242)
DIM: Color = (132, 143, 176)
ISSUE: Color = (255, 99, 120)
NEUTRAL: Color = (150, 160, 190)

# Softer than pure RGB so the colours sit well on the dark background.
_NAMED: dict[str, Color] = {
    "red": (232, 93, 106),
    "crimson": (220, 70, 90),
    "maroon": (176, 70, 90),
    "orange": (240, 154, 84),
    "yellow": (245, 208, 92),
    "gold": (236, 190, 70),
    "lime": (168, 216, 84),
    "green": (94, 200, 138),
    "teal": (72, 180, 168),
    "cyan": (86, 200, 214),
    "blue": (96, 156, 240),
    "navy": (86, 110, 190),
    "purple": (170, 128, 224),
    "violet": (150, 120, 230),
    "magenta": (226, 120, 188),
    "pink": (240, 150, 190),
    "brown": (170, 120, 90),
    "gray": (140, 148, 168),
    "grey": (140, 148, 168),
    "black": (72, 78, 98),
    "white": (232, 236, 244),
}


def mix(first: Color, second: Color, amount: float) -> Color:
    """Blend two colours: amount 0 gives first, 1 gives second."""
    return (
        round(first[0] + (second[0] - first[0]) * amount),
        round(first[1] + (second[1] - first[1]) * amount),
        round(first[2] + (second[2] - first[2]) * amount),
    )


def _lift(color: Color) -> Color:
    """Brighten colours that would vanish against the dark background."""
    luma = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
    if luma >= 110:
        return color
    return mix(color, (255, 255, 255), (110 - luma) / (255 - luma))


def resolve(name: str | None) -> Color:
    """Turn a map's ``color=`` value into an RGB triple.

    Unknown or missing names fall back to a neutral blue-grey, because the
    subject accepts any single word as a colour.
    """
    if not name:
        return NEUTRAL
    key = name.strip().lower()
    if key in _NAMED:
        return _NAMED[key]
    try:
        found = pygame.Color(key)
    except ValueError:
        return NEUTRAL
    return _lift((found.r, found.g, found.b))


def drone_color(drone_id: int) -> Color:
    """Return a pastel hue that is easy to tell apart from its neighbours."""
    hue = (drone_id * 0.6180339887) % 1.0
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.55, 1.0)
    return (round(red * 255), round(green * 255), round(blue * 255))

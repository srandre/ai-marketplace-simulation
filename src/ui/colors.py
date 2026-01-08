"""Color utilities and constants for the UI."""

from typing import Tuple


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


# Color palette
BACKGROUND = (26, 26, 46)
PRIMARY = (15, 52, 96)
SECONDARY = (22, 33, 62)
ACCENT = (233, 69, 96)
TEXT = (241, 241, 241)
TEXT_SECONDARY = (160, 160, 160)
SUCCESS = (46, 204, 113)
WARNING = (243, 156, 18)
ERROR = (231, 76, 60)
BORDER = (80, 80, 100)
HOVER = (40, 60, 120)
GOLD = (255, 215, 0)

# Resource colors
GOLD_COLOR = (255, 215, 0)
WOOD_COLOR = (139, 69, 19)
STONE_COLOR = (128, 128, 128)
FOOD_COLOR = (244, 164, 96)
TECHNOLOGY_COLOR = (65, 105, 225)
INFORMATION_COLOR = (147, 112, 219)

"""Color utilities and constants for the UI."""

from typing import Tuple
from ..utils.config import config
from ..models.enums import ResourceType


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


# Load UI colors from config
_ui_colors = config.get("ui.colors", {})

# Color palette from config
BACKGROUND = hex_to_rgb(config.get("ui.background_color", "#1a1a2e"))
PRIMARY = hex_to_rgb(_ui_colors.get("primary", "#0f3460"))
SECONDARY = hex_to_rgb(_ui_colors.get("secondary", "#16213e"))
ACCENT = hex_to_rgb(_ui_colors.get("accent", "#ff6b6b"))  # Brighter red/pink for better contrast
TEXT = (255, 255, 255)  # Pure white for maximum contrast on grey panels
TEXT_SECONDARY = (200, 200, 200)  # Light grey instead of medium grey
SUCCESS = (80, 200, 120)  # Brighter green
WARNING = (255, 180, 50)  # Brighter orange
ERROR = (255, 100, 100)  # Brighter red
BORDER = (80, 80, 100)
HOVER = (40, 60, 120)
GOLD = (255, 215, 0)

# New UI appearance - grey panels with transparency
PANEL_GREY = (90, 90, 90)  # Darker grey for better text contrast
PANEL_ALPHA = 220  # Slightly more opaque for better text readability (0-255, where 255 is fully opaque)
PANEL_BORDER_GREY = (180, 180, 180)  # Brighter grey for borders
BUTTON_GREY = (100, 100, 100)  # Darker grey for buttons
BUTTON_HOVER_GREY = (130, 130, 130)  # Lighter grey for button hover
BUTTON_DISABLED_GREY = (70, 70, 70)  # Darker grey for disabled buttons

# Text colors for vintage background (no panel)
BACKGROUND_TEXT = (40, 30, 20)  # Dark brown for text on vintage background
BACKGROUND_TEXT_SECONDARY = (60, 50, 40)  # Medium brown for secondary text on vintage background

# Resource colors from config
def get_resource_color(resource_type: ResourceType) -> Tuple[int, int, int]:
    """Get RGB color for a resource type from config."""
    resource_config = config.get(f"resources.{resource_type.value}", {})
    hex_color = resource_config.get("color", "#FFFFFF")
    return hex_to_rgb(hex_color)
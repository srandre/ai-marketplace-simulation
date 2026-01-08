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
ACCENT = hex_to_rgb(_ui_colors.get("accent", "#e94560"))
TEXT = hex_to_rgb(_ui_colors.get("text", "#f1f1f1"))
TEXT_SECONDARY = hex_to_rgb(_ui_colors.get("text_secondary", "#a0a0a0"))
SUCCESS = hex_to_rgb(_ui_colors.get("success", "#2ecc71"))
WARNING = hex_to_rgb(_ui_colors.get("warning", "#f39c12"))
ERROR = hex_to_rgb(_ui_colors.get("error", "#e74c3c"))
BORDER = (80, 80, 100)
HOVER = (40, 60, 120)
GOLD = (255, 215, 0)

# Resource colors from config
def get_resource_color(resource_type: ResourceType) -> Tuple[int, int, int]:
    """Get RGB color for a resource type from config."""
    resource_config = config.get(f"resources.{resource_type.value}", {})
    hex_color = resource_config.get("color", "#FFFFFF")
    return hex_to_rgb(hex_color)

# Pre-computed resource colors for backwards compatibility
GOLD_COLOR = get_resource_color(ResourceType.GOLD)
WOOD_COLOR = get_resource_color(ResourceType.WOOD)
STONE_COLOR = get_resource_color(ResourceType.STONE)
FOOD_COLOR = get_resource_color(ResourceType.FOOD)
TECHNOLOGY_COLOR = get_resource_color(ResourceType.TECHNOLOGY)
INFORMATION_COLOR = get_resource_color(ResourceType.INFORMATION)

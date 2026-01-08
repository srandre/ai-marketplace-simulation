"""Resource metadata utilities."""

from typing import Dict, List, Tuple
from ..models.enums import Era, ResourceType
from .config import config


def get_resource_name(resource_type: ResourceType) -> str:
    """Get the display name for a resource type from config."""
    resource_config = config.get(f"resources.{resource_type.value}", {})
    return resource_config.get("name", resource_type.value.capitalize())


def get_resource_symbol(resource_type: ResourceType) -> str:
    """Get the symbol (emoji) for a resource type from config."""
    resource_config = config.get(f"resources.{resource_type.value}", {})
    return resource_config.get("symbol", "")


def get_resource_color(resource_type: ResourceType) -> str:
    """Get the hex color for a resource type from config."""
    resource_config = config.get(f"resources.{resource_type.value}", {})
    return resource_config.get("color", "#FFFFFF")


def get_resource_color_rgb(resource_type: ResourceType) -> Tuple[int, int, int]:
    """Get the RGB color tuple for a resource type from config."""
    hex_color = get_resource_color(resource_type)
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def get_all_resource_metadata(resource_type: ResourceType) -> Dict:
    """Get all metadata for a resource type."""
    return {
        "name": get_resource_name(resource_type),
        "symbol": get_resource_symbol(resource_type),
        "color": get_resource_color(resource_type),
        "color_rgb": get_resource_color_rgb(resource_type),
    }


def is_resource_unlocked_in_era(resource_type: ResourceType, era: Era) -> bool:
    """Check if a resource is unlocked in the given era based on config."""
    eras_config = config.get("eras", [])

    for era_cfg in eras_config:
        if era_cfg.get("index") == era.value:
            unlocked_resources = era_cfg.get("unlocked_resources", [])
            return resource_type.value in unlocked_resources

    # If era not found in config, assume all basic resources are unlocked
    return resource_type in [ResourceType.GOLD, ResourceType.WOOD, ResourceType.STONE, ResourceType.FOOD]


def get_unlocked_resources_for_era(era: Era) -> List[ResourceType]:
    """Get list of resources unlocked in the given era based on config."""
    eras_config = config.get("eras", [])

    for era_cfg in eras_config:
        if era_cfg.get("index") == era.value:
            unlocked_resources = era_cfg.get("unlocked_resources", [])
            return [ResourceType[r] for r in unlocked_resources if r in ResourceType.__members__]

    # Default to basic resources if era not found
    return [ResourceType.GOLD, ResourceType.WOOD, ResourceType.STONE, ResourceType.FOOD]

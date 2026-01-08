"""Shared resource display utilities including emoji mappings."""

from ..models.enums import ResourceType, GeneratorType

# Resource emoji mappings
RESOURCE_EMOJIS = {
    ResourceType.GOLD: "💰",
    ResourceType.WOOD: "🪵",
    ResourceType.STONE: "🪨",
    ResourceType.FOOD: "🌾",
    ResourceType.TECHNOLOGY: "⚙️",
    ResourceType.INFORMATION: "💾",
}

# String-based resource emoji mappings (for when we only have the string value)
RESOURCE_EMOJIS_STR = {
    "GOLD": "💰",
    "WOOD": "🪵",
    "STONE": "🪨",
    "FOOD": "🌾",
    "TECHNOLOGY": "⚙️",
    "INFORMATION": "💾",
}

# Generator emoji mappings
GENERATOR_EMOJIS = {
    GeneratorType.LUMBER_CAMP: "🪵",
    GeneratorType.QUARRY: "🪨",
    GeneratorType.FARM: "🌾",
    GeneratorType.MINE: "💰",
    GeneratorType.FACTORY: "⚙️",
    GeneratorType.DATACENTER: "💾",
}


def get_resource_emoji(resource_type: ResourceType) -> str:
    """Get emoji for a resource type."""
    return RESOURCE_EMOJIS.get(resource_type, "❓")


def get_resource_emoji_str(resource_str: str) -> str:
    """Get emoji for a resource string value."""
    return RESOURCE_EMOJIS_STR.get(resource_str, "❓")


def get_generator_emoji(generator_type: GeneratorType) -> str:
    """Get emoji for a generator type."""
    return GENERATOR_EMOJIS.get(generator_type, "❓")


def format_resource_display(resource_type: ResourceType, amount: int) -> str:
    """Format a resource with its emoji and amount."""
    emoji = get_resource_emoji(resource_type)
    return f"{amount} {emoji}"


def format_resources_dict(resources: dict) -> str:
    """Format a dictionary of resources with emojis."""
    parts = []
    for resource_type, amount in resources.items():
        if amount > 0:
            if isinstance(resource_type, ResourceType):
                emoji = get_resource_emoji(resource_type)
            else:
                emoji = get_resource_emoji_str(resource_type)
            parts.append(f"{amount} {emoji}")
    return " ".join(parts)

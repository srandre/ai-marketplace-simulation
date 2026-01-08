"""Shared resource display utilities including emoji mappings."""

from ..models.enums import ResourceType, GeneratorType
from ..utils.config import config


def _load_resource_emojis():
    """Load resource emojis from config."""
    emojis = {}
    emojis_str = {}

    for resource_type in ResourceType:
        resource_config = config.get(f"resources.{resource_type.value}", {})
        symbol = resource_config.get("symbol", "❓")
        emojis[resource_type] = symbol
        emojis_str[resource_type.value] = symbol

    return emojis, emojis_str


# Resource emoji mappings loaded from config
RESOURCE_EMOJIS, RESOURCE_EMOJIS_STR = _load_resource_emojis()

# Generator emoji mappings (loaded dynamically from generator blueprints)
def _load_generator_emojis():
    """Load generator emojis based on what they produce."""
    # Map generators to the resources they produce
    generator_to_resource = {
        GeneratorType.MINE: ResourceType.GOLD,
        GeneratorType.LUMBER_CAMP: ResourceType.WOOD,
        GeneratorType.QUARRY: ResourceType.STONE,
        GeneratorType.FARM: ResourceType.FOOD,
        GeneratorType.FACTORY: ResourceType.TECHNOLOGY,
        GeneratorType.DATACENTER: ResourceType.INFORMATION,
    }

    emojis = {}
    for gen_type, resource_type in generator_to_resource.items():
        emojis[gen_type] = RESOURCE_EMOJIS.get(resource_type, "❓")

    return emojis


GENERATOR_EMOJIS = _load_generator_emojis()


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

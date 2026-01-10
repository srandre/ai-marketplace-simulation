"""Generator models for resource production."""

from typing import TYPE_CHECKING, Dict, Optional

from pydantic import BaseModel, Field

from .enums import GeneratorType, ResourceType
from ..utils.config import config

if TYPE_CHECKING:
    from .resource import ResourceInventory


class Generator(BaseModel):
    """Represents a resource generator building."""

    generator_type: GeneratorType
    produces: ResourceType
    generation_amount: int = Field(default=10)
    required_era: int = Field(default=0)

    def generate(self) -> int:
        """Generate resources."""
        return self.generation_amount

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class GeneratorBlueprint(BaseModel):
    """Blueprint for building a generator with costs."""

    generator_type: GeneratorType
    name: str
    produces: ResourceType
    base_cost: Dict[ResourceType, int] = Field(default_factory=dict)
    base_cost_either: Optional[Dict[ResourceType, int]] = None  # For Farm which accepts WOOD or STONE
    required_era: int = Field(default=0)

    def get_current_cost(self, count_built: int) -> Dict[ResourceType, int]:
        """
        Calculate current cost based on progressive pricing.

        Formula: current_cost = base_cost * (2^count_built)
        """
        multiplier = 2 ** count_built
        return {
            resource_type: cost * multiplier
            for resource_type, cost in self.base_cost.items()
        }

    def can_pay_with_either(
        self, inventory: "ResourceInventory", count_built: int
    ) -> Optional[ResourceType]:
        """
        Check if can pay with either WOOD or STONE (for Farm).

        Returns the resource type that can be used, or None.
        Formula: required_amount = base_cost * (2^count_built)
        """
        if self.base_cost_either is None:
            return None

        multiplier = 2 ** count_built

        # Check each allowed resource type
        for resource_type, base_amount in self.base_cost_either.items():
            required_amount = base_amount * multiplier
            if inventory.has(resource_type, required_amount):
                return resource_type

        return None

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class GeneratorManager:
    """Manages generator blueprints and creation."""

    def __init__(self):
        self.blueprints: Dict[GeneratorType, GeneratorBlueprint] = {}

    def register_blueprint(self, blueprint: GeneratorBlueprint) -> None:
        """Register a generator blueprint."""
        self.blueprints[blueprint.generator_type] = blueprint

    def get_blueprint(self, generator_type: GeneratorType) -> Optional[GeneratorBlueprint]:
        """Get a generator blueprint by type."""
        return self.blueprints.get(generator_type)

    def create_generator(
        self, generator_type: GeneratorType, era_index: int
    ) -> Optional[Generator]:
        """Create a generator instance from blueprint."""
        blueprint = self.get_blueprint(generator_type)
        if blueprint is None:
            return None

        # Get base generation from config based on era
        eras_config = config.get("eras", [])
        base_generation = 10  # Default fallback

        for era_cfg in eras_config:
            if era_cfg.get("index") == era_index:
                base_generation = era_cfg.get("base_generation", 10)
                break

        return Generator(
            generator_type=generator_type,
            produces=blueprint.produces,
            generation_amount=base_generation,
            required_era=blueprint.required_era,
        )

    def get_all_blueprints(self) -> Dict[GeneratorType, GeneratorBlueprint]:
        """Get all registered blueprints."""
        return self.blueprints.copy()

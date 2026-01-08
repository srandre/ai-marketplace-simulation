"""Nation model representing a player in the game."""

from typing import Dict, List

from pydantic import BaseModel, Field

from .enums import Era, GeneratorType, ResourceType
from .generator import Generator
from .resource import ResourceInventory


class Nation(BaseModel):
    """Represents a nation (player) in the game."""

    id: int
    name: str
    code: str  # ISO country code for flag image (e.g., "us", "cn", "jp")
    era: Era = Field(default=Era.ORIGIN)
    inventory: ResourceInventory = Field(default_factory=ResourceInventory)
    generators: List[Generator] = Field(default_factory=list)
    relationships: Dict[int, int] = Field(default_factory=dict)  # nation_id -> relationship_score

    def add_generator(self, generator: Generator) -> None:
        """Add a generator to the nation."""
        self.generators.append(generator)

    def generate_resources(self, era_multiplier: int) -> Dict[ResourceType, int]:
        """
        Generate resources from all generators.

        Returns a dictionary of resources generated.
        """
        generated: Dict[ResourceType, int] = {}

        for generator in self.generators:
            resource_type = generator.produces
            amount = generator.generate(era_multiplier)

            if resource_type not in generated:
                generated[resource_type] = 0
            generated[resource_type] += amount

            # Add to inventory
            self.inventory.add(resource_type, amount)

        return generated

    def can_advance_to_era(self, requirements: Dict[ResourceType, int]) -> bool:
        """Check if nation has resources to advance to next era."""
        return self.inventory.has_multiple(requirements)

    def advance_era(self) -> bool:
        """Advance to the next era if possible."""
        if self.era == Era.ORIGIN:
            self.era = Era.STRUCTURING
            return True
        elif self.era == Era.STRUCTURING:
            self.era = Era.INFORMATION
            return True
        elif self.era == Era.INFORMATION:
            self.era = Era.DOMINATION
            return True
        return False

    def get_relationship(self, nation_id: int) -> int:
        """Get relationship score with another nation."""
        return self.relationships.get(nation_id, 0)

    def update_relationship(self, nation_id: int, delta: int, min_val: int = -100, max_val: int = 100) -> None:
        """Update relationship score with another nation."""
        current = self.get_relationship(nation_id)
        new_value = max(min_val, min(max_val, current + delta))
        self.relationships[nation_id] = new_value

    def get_generator_count(self, generator_type: GeneratorType) -> int:
        """Count how many generators of a specific type this nation has."""
        return sum(1 for g in self.generators if g.generator_type == generator_type)

    def to_summary_dict(self) -> Dict:
        """Convert to a summary dictionary for AI context."""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "era": self.era.value,
            "resources": self.inventory.to_dict(),
            "generators": [
                {
                    "type": g.generator_type.value,
                    "produces": g.produces.value,
                    "amount": g.generation_amount,
                }
                for g in self.generators
            ],
            "relationships": self.relationships.copy(),
        }

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
        use_enum_values = False

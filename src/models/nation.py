"""Nation model representing a player in the game."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .enums import Era, GeneratorType, ResourceType
from .generator import Generator
from .resource import ResourceInventory
from ..utils.config import config


class DecisionMemory(BaseModel):
    """Stores a single decision made by the AI."""

    round_number: int
    turn_number: int
    decision_type: str  # "TRADE", "BUILD", "TRADE_RESPONSE", etc.
    decision: Dict[str, Any]  # The full decision JSON
    reasoning: str
    outcome: str = ""  # What happened after the decision (optional)


class Nation(BaseModel):
    """Represents a nation (player) in the game."""

    id: int
    name: str
    code: str  # ISO country code for flag image (e.g., "us", "cn", "jp")
    era: Era = Field(default=Era.ORIGIN)
    inventory: ResourceInventory = Field(default_factory=ResourceInventory)
    generators: List[Generator] = Field(default_factory=list)
    relationships: Dict[int, int] = Field(default_factory=dict)  # nation_id -> relationship_score
    memory: List[DecisionMemory] = Field(default_factory=list)  # AI decision history

    def add_generator(self, generator: Generator) -> None:
        """Add a generator to the nation."""
        self.generators.append(generator)

    def generate_resources(self) -> Dict[ResourceType, int]:
        """
        Generate resources from all generators.

        Returns a dictionary of resources generated.
        """
        generated: Dict[ResourceType, int] = {}

        for generator in self.generators:
            resource_type = generator.produces
            amount = generator.generate()

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
        """Advance to the next era if possible, based on config."""
        # Get all eras from config, sorted by index
        eras_config = config.get("eras", [])
        eras_sorted = sorted(eras_config, key=lambda e: e.get("index", 0))

        # Find current era index
        current_index = self.era.value

        # Find next era
        for era_cfg in eras_sorted:
            if era_cfg.get("index") == current_index + 1:
                # Found the next era
                try:
                    new_era_index = era_cfg.get("index")
                    self.era = Era(new_era_index)

                    # Update all existing generators to produce at the new era's rate
                    new_base_generation = era_cfg.get("base_generation", 10)
                    for generator in self.generators:
                        generator.generation_amount = new_base_generation

                    return True
                except ValueError:
                    return False

        # No next era available
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

    def add_decision_to_memory(
        self,
        round_number: int,
        turn_number: int,
        decision_type: str,
        decision: Dict[str, Any],
        reasoning: str,
        outcome: str = ""
    ) -> None:
        """Add a decision to this nation's memory."""
        memory_entry = DecisionMemory(
            round_number=round_number,
            turn_number=turn_number,
            decision_type=decision_type,
            decision=decision,
            reasoning=reasoning,
            outcome=outcome
        )
        self.memory.append(memory_entry)

    def get_memory_context(self, max_entries: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent decision history for AI context.
        Returns the most recent decisions to include in prompts.
        """
        # Get the last N decisions
        recent_memories = self.memory[-max_entries:] if len(self.memory) > max_entries else self.memory

        return [
            {
                "round": mem.round_number,
                "turn": mem.turn_number,
                "type": mem.decision_type,
                "decision": mem.decision,
                "reasoning": mem.reasoning,
                "outcome": mem.outcome
            }
            for mem in recent_memories
        ]

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

"""Central game state management."""

import random
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ..models.enums import Era, GeneratorType, ResourceType
from ..models.game_log import GameLog
from ..models.generator import GeneratorBlueprint, GeneratorManager
from ..models.nation import Nation
from ..models.resource import ResourceInventory
from ..models.transaction import TransactionHistory
from ..utils.config import config


class GameState(BaseModel):
    """Central state for the entire game."""

    nations: List[Nation] = Field(default_factory=list)
    turn_number: int = Field(default=1)  # Individual turn counter (increments each nation)
    round_number: int = Field(default=1)  # Complete round counter (increments after all nations play)
    turn_order: List[int] = Field(default_factory=list)  # Nation IDs in order
    current_nation_index: int = Field(default=0)
    generator_manager: GeneratorManager = Field(default_factory=GeneratorManager)
    generator_counts: Dict[GeneratorType, int] = Field(default_factory=dict)  # Global counts
    transaction_history: TransactionHistory = Field(default_factory=TransactionHistory)
    game_log: GameLog = Field(default_factory=GameLog)
    is_initialized: bool = Field(default=False)
    winner_nation_id: Optional[int] = Field(default=None)  # Set when a nation reaches Era of Domination
    game_over: bool = Field(default=False)

    def initialize_game(self) -> None:
        """Initialize the game with nations and starting resources."""
        if self.is_initialized:
            return

        # Load configuration
        num_players = config.get("game.num_players", 10)
        nation_pool = config.get("nations.pool", [])

        # Shuffle and select nations
        selected_nations = random.sample(nation_pool, min(num_players, len(nation_pool)))

        # Initialize generator blueprints
        self._initialize_generators()

        # Create nations
        available_generators = [
            GeneratorType.MINE,
            GeneratorType.LUMBER_CAMP,
            GeneratorType.QUARRY,
            GeneratorType.FARM,
        ]

        # Ensure at least one generator is assigned
        assigned_generators = []
        for i in range(num_players):
            if i < len(available_generators):
                assigned_generators.append(available_generators[i % len(available_generators)])
            else:
                assigned_generators.append(random.choice(available_generators))

        # Shuffle to randomize
        random.shuffle(assigned_generators)

        # Get initial era from config
        initial_era_index = config.get("game.initial_era", 0)
        initial_era = Era(initial_era_index)

        for i, nation_data in enumerate(selected_nations):
            nation = Nation(
                id=i,
                name=nation_data["name"],
                code=nation_data["code"],
                era=initial_era,
                inventory=ResourceInventory(),
            )

            # Add starting generator
            generator_type = assigned_generators[i]
            generator = self.generator_manager.create_generator(generator_type, 0)
            if generator:
                nation.add_generator(generator)
                self._increment_generator_count(generator_type)

            self.nations.append(nation)

        # Randomize turn order
        self.turn_order = list(range(len(self.nations)))
        random.shuffle(self.turn_order)

        self.is_initialized = True

    def _initialize_generators(self) -> None:
        """Initialize generator blueprints from configuration."""
        generators_config = config.get("generators", {})

        for gen_type_str, gen_config in generators_config.items():
            try:
                generator_type = GeneratorType[gen_type_str]
                produces = ResourceType[gen_config["produces"]]

                base_cost = {}
                if "base_cost" in gen_config:
                    for resource_str, amount in gen_config["base_cost"].items():
                        base_cost[ResourceType[resource_str]] = amount

                base_cost_either = None
                if "base_cost_either" in gen_config:
                    base_cost_either = {}
                    for resource_str, amount in gen_config["base_cost_either"].items():
                        base_cost_either[ResourceType[resource_str]] = amount

                blueprint = GeneratorBlueprint(
                    generator_type=generator_type,
                    name=gen_config["name"],
                    produces=produces,
                    base_cost=base_cost,
                    base_cost_either=base_cost_either,
                    required_era=gen_config.get("required_era", 0),
                )

                self.generator_manager.register_blueprint(blueprint)
            except (KeyError, ValueError) as e:
                print(f"Error loading generator {gen_type_str}: {e}")

    def get_current_nation(self) -> Optional[Nation]:
        """Get the nation whose turn it currently is."""
        if not self.turn_order or self.current_nation_index >= len(self.turn_order):
            return None
        nation_id = self.turn_order[self.current_nation_index]
        return self.get_nation(nation_id)

    def get_nation(self, nation_id: int) -> Optional[Nation]:
        """Get a nation by ID."""
        for nation in self.nations:
            if nation.id == nation_id:
                return nation
        return None

    def advance_turn(self) -> None:
        """Advance to the next nation's turn."""
        self.current_nation_index += 1

        # If we've gone through all nations, start a new round
        if self.current_nation_index >= len(self.turn_order):
            self.current_nation_index = 0
            self.round_number += 1
            self.turn_number = 1  # Reset turn number at start of new round
        else:
            self.turn_number += 1  # Increment turn within the round

    def _increment_generator_count(self, generator_type: GeneratorType) -> None:
        """Increment global count of a generator type."""
        if generator_type not in self.generator_counts:
            self.generator_counts[generator_type] = 0
        self.generator_counts[generator_type] += 1

    def get_generator_count(self, generator_type: GeneratorType) -> int:
        """Get global count of a generator type."""
        return self.generator_counts.get(generator_type, 0)

    def get_era_config(self, era: Era) -> Dict:
        """Get configuration for a specific era."""
        eras = config.get("eras", [])
        for era_config in eras:
            if era_config["index"] == era.value:
                return era_config
        return {}

    def get_era_advancement_requirements(self, current_era: Era) -> Optional[Dict[ResourceType, int]]:
        """Get resource requirements to advance from current era."""
        if current_era == Era.ORIGIN:
            reqs = config.get("era_advancement.era_1_requirements", {})
        elif current_era == Era.STRUCTURING:
            reqs = config.get("era_advancement.era_2_requirements", {})
        elif current_era == Era.INFORMATION:
            reqs = config.get("era_advancement.era_3_requirements", {})
        elif current_era == Era.DOMINATION:
            return None  # Max era reached
        else:
            return None

        # Convert string keys to ResourceType
        return {ResourceType[k]: v for k, v in reqs.items()}

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

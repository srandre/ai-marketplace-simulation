"""Building system for constructing generators."""

from typing import Optional

from ..models.enums import GeneratorType, LogType, ResourceType
from ..models.nation import Nation
from .game_state import GameState


class BuildingManager:
    """Manages construction of generators."""

    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def can_build(self, nation: Nation, generator_type: GeneratorType) -> tuple[bool, str]:
        """
        Check if a nation can build a generator.

        Returns (can_build, reason).
        """
        blueprint = self.game_state.generator_manager.get_blueprint(generator_type)
        if not blueprint:
            return False, "Generator type not found"

        # Check era requirement
        if blueprint.required_era > nation.era.value:
            return False, f"Requires era {blueprint.required_era}"

        # Check resources
        count_built = self.game_state.get_generator_count(generator_type)

        # Special case: Farm can pay with either WOOD or STONE
        if blueprint.base_cost_either is not None:
            resource_type = blueprint.can_pay_with_either(nation.inventory, count_built)
            if resource_type:
                return True, f"Can pay with {resource_type.value}"
            else:
                # Show which resources are accepted
                multiplier = 2 ** count_built
                options = [f"{amount * multiplier} {rt.value}" for rt, amount in blueprint.base_cost_either.items()]
                return False, f"Need either: {' or '.join(options)}"

        # Normal case: specific resources required
        current_cost = blueprint.get_current_cost(count_built)
        if nation.inventory.has_multiple(current_cost):
            return True, "Has required resources"
        else:
            missing = []
            for resource_type, amount in current_cost.items():
                has = nation.inventory.get(resource_type)
                if has < amount:
                    missing.append(f"{amount - has} {resource_type.value}")
            return False, f"Missing: {', '.join(missing)}"

    def build_generator(
        self, nation: Nation, generator_type: GeneratorType, payment_resource: Optional[ResourceType] = None
    ) -> tuple[bool, str]:
        """
        Build a generator for a nation.

        Args:
            nation: The nation building the generator
            generator_type: The type of generator to build
            payment_resource: Optional specific resource to use for payment (for Farm)

        Returns (success, message).
        """
        can_build, reason = self.can_build(nation, generator_type)
        if not can_build:
            return False, reason

        blueprint = self.game_state.generator_manager.get_blueprint(generator_type)
        if not blueprint:
            return False, "Generator type not found"

        count_built = self.game_state.get_generator_count(generator_type)

        # Deduct resources
        if blueprint.base_cost_either is not None:
            # Farm case - can pay with either WOOD or STONE
            multiplier = 2 ** count_built

            # Use specified payment resource if provided
            if payment_resource is not None:
                if payment_resource not in blueprint.base_cost_either:
                    options = [rt.value for rt in blueprint.base_cost_either.keys()]
                    return False, f"Invalid payment resource. Must be one of: {', '.join(options)}"

                required_amount = blueprint.base_cost_either[payment_resource] * multiplier
                if not nation.inventory.has(payment_resource, required_amount):
                    return False, f"Insufficient {payment_resource.value}: need {required_amount}, have {nation.inventory.get(payment_resource)}"
                resource_type = payment_resource
            else:
                # Fall back to automatic selection
                resource_type = blueprint.can_pay_with_either(nation.inventory, count_built)
                if not resource_type:
                    return False, "Insufficient resources"

            required_amount = blueprint.base_cost_either[resource_type] * multiplier
            nation.inventory.remove(resource_type, required_amount)
            cost_paid = {resource_type: required_amount}
        else:
            # Normal case
            current_cost = blueprint.get_current_cost(count_built)
            if not nation.inventory.remove_multiple(current_cost):
                return False, "Insufficient resources"

            cost_paid = current_cost

        # Create and add generator
        generator = self.game_state.generator_manager.create_generator(
            generator_type, nation.era.value
        )
        if not generator:
            return False, "Failed to create generator"

        nation.add_generator(generator)
        self.game_state._increment_generator_count(generator_type)

        # Log the build
        from ..ui.resource_display import get_resource_emoji
        cost_parts = [f"{v} {get_resource_emoji(k)}" for k, v in cost_paid.items()]
        cost_str = ", ".join(cost_parts)
        self.game_state.game_log.add_entry(
            log_type=LogType.BUILD,
            turn_number=self.game_state.turn_number,
            round_number=self.game_state.round_number,
            summary=f"{nation.name} built {blueprint.name} for {cost_str}",
            nations_involved=[nation.id],
            details={
                "generator_type": generator_type.value,
                "cost": {k.value: v for k, v in cost_paid.items()},
                "total_count": self.game_state.get_generator_count(generator_type),
            },
        )

        return True, f"Successfully built {blueprint.name}"

    def get_available_generators(self, nation: Nation) -> list[GeneratorType]:
        """Get list of generators the nation can potentially build."""
        available = []

        for generator_type in GeneratorType:
            blueprint = self.game_state.generator_manager.get_blueprint(generator_type)
            if blueprint and blueprint.required_era <= nation.era.value:
                available.append(generator_type)

        return available

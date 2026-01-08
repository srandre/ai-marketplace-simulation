"""Turn management and execution."""

from ..models.enums import Era, LogType
from .game_state import GameState


class TurnManager:
    """Manages turn flow and automatic actions."""

    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def start_turn(self, nation_id: int) -> None:
        """
        Start a nation's turn.

        Performs automatic actions:
        1. Generate resources from generators
        2. Check for era advancement
        """
        nation = self.game_state.get_nation(nation_id)
        if not nation:
            return

        # 1. Generate resources
        self._generate_resources(nation)

        # 2. Check for era advancement
        self._check_era_advancement(nation)

    def _generate_resources(self, nation) -> None:
        """Generate resources from all generators."""
        era_config = self.game_state.get_era_config(nation.era)
        era_multiplier = era_config.get("generation_multiplier", 1)

        generated = nation.generate_resources(era_multiplier)

        if generated:
            from ..ui.resource_display import format_resources_dict

            generation_summary = format_resources_dict(generated)

            self.game_state.game_log.add_entry(
                log_type=LogType.GENERATION,
                turn_number=self.game_state.turn_number,
                round_number=self.game_state.round_number,
                summary=f"{nation.name} generated {generation_summary}",
                nations_involved=[nation.id],
                details={"generated": {k.value: v for k, v in generated.items()}},
            )

    def _check_era_advancement(self, nation) -> None:
        """Check if nation can advance to next era and do so if possible."""
        if nation.era == Era.INFORMATION:
            return  # Already at max era

        requirements = self.game_state.get_era_advancement_requirements(nation.era)
        if not requirements:
            return

        if nation.can_advance_to_era(requirements):
            old_era = nation.era
            nation.advance_era()

            self.game_state.game_log.add_entry(
                log_type=LogType.ERA_ADVANCEMENT,
                turn_number=self.game_state.turn_number,
                round_number=self.game_state.round_number,
                summary=f"{nation.name} advanced to {nation.era.name}!",
                nations_involved=[nation.id],
                details={
                    "old_era": old_era.value,
                    "new_era": nation.era.value,
                    "requirements_met": {k.value: v for k, v in requirements.items()},
                },
            )

    def end_turn(self) -> None:
        """End a nation's turn."""
        # Advance to next nation
        self.game_state.advance_turn()

    def get_era_multiplier(self, era: Era) -> int:
        """Get the resource generation multiplier for an era."""
        era_config = self.game_state.get_era_config(era)
        return era_config.get("generation_multiplier", 1)

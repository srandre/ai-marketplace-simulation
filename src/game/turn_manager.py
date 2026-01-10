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
        generated = nation.generate_resources()

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
        requirements = self.game_state.get_era_advancement_requirements(nation.era)
        if not requirements:
            return  # Already at max era or no requirements defined

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

            # Check if nation reached max era (game over condition)
            # If no more advancement requirements exist, they've reached the final era
            next_requirements = self.game_state.get_era_advancement_requirements(nation.era)
            if next_requirements is None:
                self.game_state.winner_nation_id = nation.id
                self.game_state.game_over = True
                self.game_state.game_log.add_entry(
                    log_type=LogType.ACTION,
                    turn_number=self.game_state.turn_number,
                    round_number=self.game_state.round_number,
                    summary=f"🏆 {nation.name} has achieved the final era ({nation.era.name}) and won the game!",
                    nations_involved=[nation.id],
                    details={"event": "game_over", "winner": nation.id},
                )

    def end_turn(self) -> None:
        """End a nation's turn."""
        # Advance to next nation
        self.game_state.advance_turn()

    def get_era_multiplier(self, era: Era) -> int:
        """Get the resource generation multiplier for an era."""
        era_config = self.game_state.get_era_config(era)
        return era_config.get("generation_multiplier", 1)

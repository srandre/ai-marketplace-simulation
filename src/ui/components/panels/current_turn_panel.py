"""Current turn info panel component."""

import pygame
from typing import Dict, Any, Optional
from ... import colors


class CurrentTurnPanel:
    """Panel displaying current turn information or winner."""

    def __init__(self, panel, flag_images: Dict[str, Dict[str, pygame.Surface]],
                 font_small: pygame.font.Font, font_medium: pygame.font.Font):
        self.panel = panel
        self.flag_images = flag_images
        self.font_small = font_small
        self.font_medium = font_medium

    def draw_panel_background(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the panel background and title."""
        self.panel.draw(screen, font)

    def draw_content(self, screen: pygame.Surface, game_state: Any,
                    turn_executor: Any) -> None:
        """Draw current turn info or winner if game is over."""
        x = self.panel.rect.x + 10
        y = self.panel.rect.y + 50

        # Check if game is over
        if game_state.game_over and game_state.winner_nation_id is not None:
            self._draw_winner(screen, game_state, x, y)
            return

        current_nation = game_state.get_current_nation()
        if not current_nation:
            return

        self._draw_current_turn(screen, current_nation, turn_executor, x, y)

    def _draw_winner(self, screen: pygame.Surface, game_state: Any,
                    x: int, y: int) -> None:
        """Draw winner information."""
        winner = game_state.get_nation(game_state.winner_nation_id)
        if not winner:
            return

        # Display winner
        winner_text = "🏆 Winner:"
        winner_surf = self.font_medium.render(winner_text, True, colors.GOLD)
        screen.blit(winner_surf, (x, y))

        # Winner flag
        winner_width = self.font_medium.size(winner_text)[0]
        flag_x = x + winner_width + 20
        if winner.name in self.flag_images:
            flag_img = self.flag_images[winner.name]['medium']
            screen.blit(flag_img, (flag_x, y - 2))

        # Winner name
        nation_x = flag_x + 40
        nation_text = winner.name
        nation_surf = self.font_medium.render(nation_text, True, colors.GOLD)
        screen.blit(nation_surf, (nation_x, y))

    def _draw_current_turn(self, screen: pygame.Surface, current_nation: Any,
                          turn_executor: Any, x: int, y: int) -> None:
        """Draw current turn information."""
        # Current Turn label with nation
        turn_text = "Current Turn:"
        turn_surf = self.font_medium.render(turn_text, True, colors.TEXT)
        screen.blit(turn_surf, (x, y))

        # Nation flag
        turn_width = self.font_medium.size(turn_text)[0]
        flag_x = x + turn_width + 20
        if current_nation.name in self.flag_images:
            flag_img = self.flag_images[current_nation.name]['medium']
            screen.blit(flag_img, (flag_x, y - 2))

        # Nation name
        nation_x = flag_x + 40
        nation_text = current_nation.name
        nation_surf = self.font_medium.render(nation_text, True, colors.TEXT)
        screen.blit(nation_surf, (nation_x, y))

        # Status text on the SAME line
        status_x = nation_x + self.font_medium.size(nation_text)[0] + 10

        if turn_executor.status.is_busy():
            status_text = turn_executor.status.get_action()
            if status_text:
                status_display = f"- {status_text}"

                max_width = (
                    self.panel.rect.width
                    - (status_x - self.panel.rect.x)
                    - 10
                )

                while self.font_small.size(status_display)[0] > max_width and len(status_display) > 10:
                    status_display = status_display[:-4] + "..."

                status_surf = self.font_small.render(status_display, True, colors.WARNING)
                screen.blit(status_surf, (status_x, y + 4))

        # Era on second line
        y += 35
        era_text = f"Era: {current_nation.era.name}"
        era_surf = self.font_small.render(era_text, True, colors.ACCENT)
        screen.blit(era_surf, (x, y))

        # Error (below)
        error = turn_executor.status.get_error()
        if error:
            y += 25
            error_surf = self.font_small.render(f"Error: {error[:50]}", True, colors.ERROR)
            screen.blit(error_surf, (x, y))

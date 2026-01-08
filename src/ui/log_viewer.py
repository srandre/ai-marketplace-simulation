"""Log viewer window for detailed game logs."""

import pygame

from ..game.game_state import GameState
from . import colors


class LogViewer:
    """Displays game logs in a separate overlay."""

    def __init__(self):
        self.scroll_offset = 0
        self.selected_log_index = -1
        self.show_details = False
        self.selected_nation_id = -1
        self.rect = None  # Will be set when drawing

    def handle_event(self, event: pygame.event.Event):
        """
        Handle events.

        Returns:
            "close" - Close the log viewer
            True - Event was consumed
            False - Event was not handled
        """
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "close"  # Signal to close log viewer

        if not self.rect.collidepoint(pygame.mouse.get_pos()):
            return False

        if event.type == pygame.MOUSEWHEEL:
            self.scroll_offset = max(0, self.scroll_offset - event.y * 20)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check if clicking on a log entry
            relative_y = event.pos[1] - self.rect.y - 50 + self.scroll_offset
            clicked_index = int(relative_y // 40)

            if 0 <= clicked_index < 20:  # Max visible entries
                self.selected_log_index = clicked_index
                self.show_details = True
                return True

        return False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font, game_state: GameState) -> None:
        """Draw the log viewer overlay."""
        # Semi-transparent background
        overlay = pygame.Surface((screen.get_width(), screen.get_height()))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        # Calculate centered log viewer window
        log_width = min(1000, screen.get_width() - 100)
        log_height = min(600, screen.get_height() - 100)
        log_x = (screen.get_width() - log_width) // 2
        log_y = (screen.get_height() - log_height) // 2
        self.rect = pygame.Rect(log_x, log_y, log_width, log_height)

        # Log viewer window
        pygame.draw.rect(screen, colors.SECONDARY, self.rect)
        pygame.draw.rect(screen, colors.ACCENT, self.rect, 3)

        # Title
        title_font = pygame.font.Font(None, 32)
        title = title_font.render("Game Logs", True, colors.TEXT)
        screen.blit(title, (self.rect.x + 20, self.rect.y + 10))

        # Close instruction
        close_text = font.render("Press ESC to close", True, colors.TEXT_SECONDARY)
        screen.blit(close_text, (self.rect.x + self.rect.width - 150, self.rect.y + 15))

        # Draw logs
        self._draw_logs(screen, font, game_state)

        # Draw details if selected
        if self.show_details and self.selected_log_index >= 0:
            self._draw_log_details(screen, font, game_state)

    def _draw_logs(self, screen: pygame.Surface, font: pygame.font.Font, game_state: GameState) -> None:
        """Draw the list of log entries."""
        logs = game_state.game_log.get_recent(50)
        logs.reverse()  # Show most recent first

        x = self.rect.x + 10
        y = self.rect.y + 50

        visible_height = self.rect.height - 60
        y_pos = -self.scroll_offset

        for i, log in enumerate(logs):
            if y_pos >= 0 and y_pos < visible_height:
                # Draw log entry
                entry_rect = pygame.Rect(x, y + y_pos, self.rect.width - 20, 35)

                if i == self.selected_log_index:
                    pygame.draw.rect(screen, colors.HOVER, entry_rect)

                # Turn number
                turn_text = f"T{log.turn_number}"
                text_surf = font.render(turn_text, True, colors.WARNING)
                screen.blit(text_surf, (x + 5, y + y_pos + 5))

                # Summary
                summary_text = log.summary[:80] + "..." if len(log.summary) > 80 else log.summary
                text_surf = font.render(summary_text, True, colors.TEXT)
                screen.blit(text_surf, (x + 60, y + y_pos + 5))

                pygame.draw.line(screen, colors.BORDER,
                               (x, y + y_pos + 35),
                               (x + self.rect.width - 20, y + y_pos + 35))

            y_pos += 40

            if y_pos > visible_height:
                break

    def _draw_log_details(self, screen: pygame.Surface, font: pygame.font.Font, game_state: GameState) -> None:
        """Draw detailed view of selected log entry."""
        logs = game_state.game_log.get_recent(50)
        logs.reverse()

        if self.selected_log_index >= len(logs):
            return

        log_entry = logs[self.selected_log_index]

        # Details panel
        details_rect = pygame.Rect(
            self.rect.x + self.rect.width + 20,
            self.rect.y,
            600,
            self.rect.height
        )

        pygame.draw.rect(screen, colors.PRIMARY, details_rect)
        pygame.draw.rect(screen, colors.ACCENT, details_rect, 3)

        x = details_rect.x + 10
        y = details_rect.y + 10

        # Title
        title_font = pygame.font.Font(None, 28)
        title = title_font.render("Log Details", True, colors.TEXT)
        screen.blit(title, (x, y))

        y += 40

        # Log type
        type_text = f"Type: {log_entry.log_type.value}"
        text = font.render(type_text, True, colors.ACCENT)
        screen.blit(text, (x, y))

        y += 30

        # Summary
        summary_text = "Summary:"
        text = font.render(summary_text, True, colors.TEXT)
        screen.blit(text, (x, y))

        y += 25
        # Word wrap summary
        words = log_entry.summary.split()
        line = ""
        for word in words:
            test_line = line + word + " "
            if font.size(test_line)[0] < details_rect.width - 40:
                line = test_line
            else:
                text = font.render(line, True, colors.TEXT_SECONDARY)
                screen.blit(text, (x + 10, y))
                y += 20
                line = word + " "
        if line:
            text = font.render(line, True, colors.TEXT_SECONDARY)
            screen.blit(text, (x + 10, y))
            y += 30

        # AI decisions if any
        if log_entry.ai_decisions:
            y += 10
            ai_text = "AI Decisions:"
            text = font.render(ai_text, True, colors.SUCCESS)
            screen.blit(text, (x, y))

            y += 25
            for ai_decision in log_entry.ai_decisions[:2]:  # Show max 2
                nation = game_state.get_nation(ai_decision.nation_id)
                if nation:
                    nation_text = f"{nation.flag} {nation.name}"
                    text = font.render(nation_text, True, colors.TEXT)
                    screen.blit(text, (x + 10, y))
                    y += 20

                    # Show truncated response
                    response_preview = ai_decision.response[:60] + "..."
                    text = font.render(response_preview, True, colors.TEXT_SECONDARY)
                    screen.blit(text, (x + 20, y))
                    y += 25

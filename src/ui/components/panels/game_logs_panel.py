"""Game logs panel component."""

import pygame
import re
from typing import Dict, Any, Optional
from ... import colors
from ....utils.config import config
from ..base_panel import ScrollablePanel
from ..utils import ScrollbarManager
from .. import draw_rounded_rect_border


class GameLogsPanel(ScrollablePanel):
    """Panel displaying game logs with selection support."""

    def __init__(self, panel, scrollbar_manager: ScrollbarManager,
                 flag_images: Dict[str, Dict[str, pygame.Surface]],
                 font_small: pygame.font.Font):
        super().__init__(panel, 'logs', scrollbar_manager)
        self.flag_images = flag_images
        self.font_small = font_small
        self.selected_log = None
        self.line_height = 25

    def draw_content(self, screen: pygame.Surface, game_state: Any) -> None:
        """Draw game logs inline in the panel with scrolling."""
        max_logs = config.get("ui.max_logs_displayed", 10000)
        logs = game_state.game_log.get_recent(max_logs)
        logs.reverse()  # Newest first

        x = self.panel.rect.x + 10

        # Create clipping area (leave space for scrollbar)
        clip_rect = pygame.Rect(
            self.panel.rect.x + 5,
            self.panel.rect.y + 45,
            self.panel.rect.width - 25,
            self.panel.rect.height - 50
        )
        screen.set_clip(clip_rect)

        # Start y position with scroll offset
        y = self.panel.rect.y + 50 - self.scroll_offset

        for log in logs:
            # Skip if above visible area
            if y + self.line_height < clip_rect.top:
                y += self.line_height
                continue

            # Stop if below visible area
            if y > clip_rect.bottom:
                break

            # Highlight selected log
            if self.selected_log == log:
                highlight_rect = pygame.Rect(
                    self.panel.rect.x + 8,
                    y - 1,
                    self.panel.rect.width - 30,
                    self.line_height - 2
                )
                draw_rounded_rect_border(screen, colors.ACCENT, highlight_rect, width=2, border_radius=5)

            self._draw_log_entry(screen, log, game_state, x, y, clip_rect)
            y += self.line_height

        # Update content height for scrollbar
        self.content_height = len(logs) * self.line_height

        screen.set_clip(None)

    def _draw_log_entry(self, screen: pygame.Surface, log: Any, game_state: Any,
                       x: int, y: int, clip_rect: pygame.Rect) -> None:
        """Draw a single log entry."""
        # Round.Turn format (e.g., R1.T1, R1.T2, R2.T1)
        round_turn_text = f"R{log.round_number}.T{log.turn_number}"
        text_surf = self.font_small.render(round_turn_text, True, colors.WARNING)
        screen.blit(text_surf, (x, y))

        # Flags
        flag_x = x + 55
        if log.nations_involved and self.flag_images:
            for nation_id in log.nations_involved[:2]:
                nation = game_state.get_nation(nation_id)
                if nation and nation.name in self.flag_images:
                    flag_img = self.flag_images[nation.name]['small']
                    screen.blit(flag_img, (flag_x, y - 1))
                    flag_x += 28

        # Summary (truncated to fit)
        summary_clean = re.sub(r'[\U0001F1E6-\U0001F1FF]{2}', '', log.summary)
        max_summary_width = self.panel.rect.width - (flag_x - x) - 20

        # Truncate summary to fit
        summary_text = summary_clean
        while self.font_small.size(summary_text)[0] > max_summary_width and len(summary_text) > 10:
            summary_text = summary_text[:-4] + "..."

        text_surf = self.font_small.render(summary_text, True, colors.TEXT)
        screen.blit(text_surf, (flag_x + 5, y))

    def handle_click(self, mouse_pos: tuple, game_state: Any) -> bool:
        """Handle click on log entry. Returns True if selection changed."""
        if not self.panel.rect.collidepoint(mouse_pos):
            return False

        clicked_log = self._get_log_at_position(mouse_pos, game_state)
        if clicked_log:
            if self.selected_log == clicked_log:
                # Deselect if clicking the same log
                self.selected_log = None
            else:
                # Select the new log
                self.selected_log = clicked_log
            return True

        return False

    def _get_log_at_position(self, mouse_pos: tuple, game_state: Any) -> Optional[Any]:
        """Get the log entry at the given mouse position."""
        max_logs = config.get("ui.max_logs_displayed", 10000)
        logs = game_state.game_log.get_recent(max_logs)
        logs.reverse()

        y = self.panel.rect.y + 50 - self.scroll_offset

        for log in logs:
            # Check if mouse is within this log's bounds
            if y <= mouse_pos[1] < y + self.line_height:
                if self.panel.rect.x <= mouse_pos[0] <= self.panel.rect.x + self.panel.rect.width:
                    return log
            y += self.line_height

        return None

    def get_hovered_log(self, mouse_pos: tuple, game_state: Any) -> Optional[Any]:
        """Get the log entry currently being hovered over."""
        if not self.panel.rect.collidepoint(mouse_pos):
            return None
        return self._get_log_at_position(mouse_pos, game_state)

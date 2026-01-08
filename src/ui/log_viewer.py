"""Log viewer window for detailed game logs."""

import json
import pygame

from ..game.game_state import GameState
from . import colors


class LogViewer:
    """Displays game logs in a separate overlay."""

    def __init__(self):
        self.scroll_offset = 0
        self.selected_log_index = 0  # Default to first log
        self.details_scroll = 0  # Scroll for details panel
        self.rect = None  # Will be set when drawing
        self.scrollbar_dragging = False
        self.details_scrollbar_dragging = False
        self.selected_log_id = None  # Track which specific log is selected (turn_number, timestamp)

    def handle_event(self, event: pygame.event.Event):
        """Handle events."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "close"

        if not self.rect or not self.rect.collidepoint(pygame.mouse.get_pos()):
            return False

        # Handle scrollbar dragging
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_x, mouse_y = pygame.mouse.get_pos()

            # Check scrollbar clicks
            if hasattr(self, 'scrollbar_rect') and self.scrollbar_rect:
                if self.scrollbar_rect.collidepoint(mouse_x, mouse_y):
                    self.scrollbar_dragging = True
                    return True

            if hasattr(self, 'details_scrollbar_rect') and self.details_scrollbar_rect:
                if self.details_scrollbar_rect.collidepoint(mouse_x, mouse_y):
                    self.details_scrollbar_dragging = True
                    return True

            # Check log entry clicks - need to get logs to track selection
            logs_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 50,
                                   self.rect.width // 2 - 20, self.rect.height - 60)
            if logs_rect.collidepoint(mouse_x, mouse_y):
                # We need access to game_state here, but we don't have it in handle_event
                # So we'll just track the index and update selected_log_id in _draw_logs_panel
                relative_y = mouse_y - logs_rect.y + self.scroll_offset
                clicked_index = int(relative_y // 40)
                self.selected_log_index = clicked_index
                self.details_scroll = 0  # Reset details scroll
                # Signal that we need to update selected_log_id
                self._pending_selection = True
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.scrollbar_dragging = False
            self.details_scrollbar_dragging = False

        if event.type == pygame.MOUSEMOTION:
            if self.scrollbar_dragging and hasattr(self, 'scrollbar_track'):
                # Calculate scroll from mouse position
                track_y = self.scrollbar_track.y
                track_height = self.scrollbar_track.height
                mouse_y = pygame.mouse.get_pos()[1]
                relative_y = mouse_y - track_y
                scroll_ratio = max(0, min(1, relative_y / track_height))

                if hasattr(self, 'max_scroll'):
                    self.scroll_offset = int(scroll_ratio * self.max_scroll)
                return True

            if self.details_scrollbar_dragging and hasattr(self, 'details_scrollbar_track'):
                track_y = self.details_scrollbar_track.y
                track_height = self.details_scrollbar_track.height
                mouse_y = pygame.mouse.get_pos()[1]
                relative_y = mouse_y - track_y
                scroll_ratio = max(0, min(1, relative_y / track_height))

                if hasattr(self, 'details_max_scroll'):
                    self.details_scroll = int(scroll_ratio * self.details_max_scroll)
                return True

        if event.type == pygame.MOUSEWHEEL:
            mouse_x, mouse_y = pygame.mouse.get_pos()

            # Check which panel to scroll
            if self.rect:
                mid_x = self.rect.x + self.rect.width // 2
                if mouse_x < mid_x:
                    # Scroll logs list
                    self.scroll_offset = max(0, self.scroll_offset - event.y * 30)
                else:
                    # Scroll details
                    self.details_scroll = max(0, self.details_scroll - event.y * 30)
            return True

        return False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font, game_state: GameState, flag_images: dict = None) -> None:
        """Draw the log viewer overlay."""
        self.flag_images = flag_images or {}

        # Semi-transparent background
        overlay = pygame.Surface((screen.get_width(), screen.get_height()))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        # Calculate centered window - wider to accommodate both panels
        log_width = min(1400, screen.get_width() - 100)
        log_height = min(700, screen.get_height() - 100)
        log_x = (screen.get_width() - log_width) // 2
        log_y = (screen.get_height() - log_height) // 2
        self.rect = pygame.Rect(log_x, log_y, log_width, log_height)

        # Main window background
        pygame.draw.rect(screen, colors.SECONDARY, self.rect)
        pygame.draw.rect(screen, colors.ACCENT, self.rect, 3)

        # Title
        title_font = pygame.font.Font(None, 32)
        title = title_font.render("Game Logs", True, colors.TEXT)
        screen.blit(title, (self.rect.x + 20, self.rect.y + 10))

        # Close instruction
        close_text = font.render("Press ESC to close", True, colors.TEXT_SECONDARY)
        screen.blit(close_text, (self.rect.x + self.rect.width - 200, self.rect.y + 15))

        # Split into two panels
        panel_width = self.rect.width // 2 - 15

        # Left panel: Logs list
        self._draw_logs_panel(screen, font, game_state,
                            self.rect.x + 10, self.rect.y + 50,
                            panel_width, self.rect.height - 60)

        # Right panel: Details
        self._draw_details_panel(screen, font, game_state,
                                self.rect.x + self.rect.width // 2 + 5, self.rect.y + 50,
                                panel_width, self.rect.height - 60)

    def _draw_logs_panel(self, screen, font, game_state, x, y, width, height):
        """Draw the logs list panel with scrollbar."""
        logs = game_state.game_log.get_recent(50)
        logs.reverse()

        # If user just clicked a log, update the selected_log_id
        if hasattr(self, '_pending_selection') and self._pending_selection:
            if self.selected_log_index < len(logs):
                log = logs[self.selected_log_index]
                self.selected_log_id = (log.turn_number, log.timestamp)
            self._pending_selection = False

        # Find the index of the currently selected log
        if self.selected_log_id is not None:
            # Try to find the log with the matching ID
            found = False
            for i, log in enumerate(logs):
                if (log.turn_number, log.timestamp) == self.selected_log_id:
                    self.selected_log_index = i
                    found = True
                    break
            # If not found (log was removed?), default to newest
            if not found:
                self.selected_log_index = 0
                if logs:
                    self.selected_log_id = (logs[0].turn_number, logs[0].timestamp)
        else:
            # No log selected yet, default to newest
            self.selected_log_index = 0
            if logs:
                self.selected_log_id = (logs[0].turn_number, logs[0].timestamp)

        # Ensure selected index is valid
        if self.selected_log_index >= len(logs):
            self.selected_log_index = max(0, len(logs) - 1)

        # Calculate scrolling
        item_height = 40
        total_height = len(logs) * item_height
        self.max_scroll = max(0, total_height - height)
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset))

        # Clip area for logs
        clip_rect = pygame.Rect(x, y, width - 20, height)
        screen.set_clip(clip_rect)

        y_pos = y - self.scroll_offset
        for i, log in enumerate(logs):
            if y_pos + item_height >= y and y_pos < y + height:
                # Highlight selected
                entry_rect = pygame.Rect(x, y_pos, width - 20, item_height - 2)
                if i == self.selected_log_index:
                    pygame.draw.rect(screen, colors.HOVER, entry_rect)

                # Turn number
                turn_text = f"T{log.turn_number}"
                text_surf = font.render(turn_text, True, colors.WARNING)
                screen.blit(text_surf, (x + 5, y_pos + 10))

                # Flags
                flag_x = x + 60
                if log.nations_involved and self.flag_images:
                    for nation_id in log.nations_involved[:2]:
                        nation = game_state.get_nation(nation_id)
                        if nation and nation.name in self.flag_images:
                            flag_img = self.flag_images[nation.name]['small']
                            screen.blit(flag_img, (flag_x, y_pos + 11))
                            flag_x += 30

                # Summary
                import re
                summary_clean = re.sub(r'[\U0001F1E6-\U0001F1FF]{2}', '', log.summary)
                summary_text = summary_clean[:50] + "..." if len(summary_clean) > 50 else summary_clean
                text_surf = font.render(summary_text, True, colors.TEXT)
                screen.blit(text_surf, (flag_x + 5, y_pos + 10))

            y_pos += item_height

        screen.set_clip(None)

        # Draw scrollbar
        if self.max_scroll > 0:
            scrollbar_x = x + width - 15
            scrollbar_width = 10
            scrollbar_height = height

            # Track
            self.scrollbar_track = pygame.Rect(scrollbar_x, y, scrollbar_width, scrollbar_height)
            pygame.draw.rect(screen, colors.PRIMARY, self.scrollbar_track)

            # Handle
            handle_height = max(30, int(scrollbar_height * (height / total_height)))
            handle_y = y + int((self.scroll_offset / self.max_scroll) * (scrollbar_height - handle_height))
            self.scrollbar_rect = pygame.Rect(scrollbar_x, handle_y, scrollbar_width, handle_height)
            pygame.draw.rect(screen, colors.ACCENT, self.scrollbar_rect)

    def _draw_details_panel(self, screen, font, game_state, x, y, width, height):
        """Draw the details panel with AI decisions."""
        logs = game_state.game_log.get_recent(50)
        logs.reverse()

        if self.selected_log_index >= len(logs):
            return

        log_entry = logs[self.selected_log_index]

        # Calculate content height for scrolling
        content_lines = []

        # Type
        content_lines.append(("Type:", colors.ACCENT, 0))
        content_lines.append((f"  {log_entry.log_type.value}", colors.TEXT, 0))
        content_lines.append(("", colors.TEXT, 0))

        # Summary
        content_lines.append(("Summary:", colors.TEXT, 0))
        words = log_entry.summary.split()
        line = ""
        for word in words:
            test_line = line + word + " "
            if font.size(test_line)[0] < width - 60:
                line = test_line
            else:
                content_lines.append((f"  {line}", colors.TEXT_SECONDARY, 0))
                line = word + " "
        if line:
            content_lines.append((f"  {line}", colors.TEXT_SECONDARY, 0))
        content_lines.append(("", colors.TEXT, 0))

        # AI Decisions
        if log_entry.ai_decisions:
            content_lines.append(("AI Decisions:", colors.SUCCESS, 0))
            for ai_decision in log_entry.ai_decisions:
                nation = game_state.get_nation(ai_decision.nation_id)
                if nation:
                    content_lines.append((f"  {nation.name}:", colors.TEXT, 0))

                    # Parse and format JSON response
                    try:
                        response_data = json.loads(ai_decision.response)
                        formatted = json.dumps(response_data, indent=2)
                        for line in formatted.split('\n'):
                            if len(line) > 70:
                                # Wrap long lines
                                chunks = [line[i:i+70] for i in range(0, len(line), 70)]
                                for chunk in chunks:
                                    content_lines.append((f"    {chunk}", colors.TEXT_SECONDARY, 0))
                            else:
                                content_lines.append((f"    {line}", colors.TEXT_SECONDARY, 0))
                    except:
                        # Fallback if not valid JSON
                        response_text = ai_decision.response[:200]
                        for line in response_text.split('\n'):
                            content_lines.append((f"    {line[:70]}", colors.TEXT_SECONDARY, 0))

                    content_lines.append(("", colors.TEXT, 0))

        # Calculate scrolling
        line_height = 20
        total_content_height = len(content_lines) * line_height
        self.details_max_scroll = max(0, total_content_height - height)
        self.details_scroll = max(0, min(self.details_max_scroll, self.details_scroll))

        # Clip area
        clip_rect = pygame.Rect(x, y, width - 20, height)
        screen.set_clip(clip_rect)

        # Draw content
        y_pos = y - self.details_scroll
        for text, color, indent in content_lines:
            if y_pos >= y - line_height and y_pos < y + height:
                text_surf = font.render(text, True, color)
                screen.blit(text_surf, (x + 10, y_pos))
            y_pos += line_height

        screen.set_clip(None)

        # Draw scrollbar
        if self.details_max_scroll > 0:
            scrollbar_x = x + width - 15
            scrollbar_width = 10

            # Track
            self.details_scrollbar_track = pygame.Rect(scrollbar_x, y, scrollbar_width, height)
            pygame.draw.rect(screen, colors.PRIMARY, self.details_scrollbar_track)

            # Handle
            handle_height = max(30, int(height * (height / total_content_height)))
            handle_y = y + int((self.details_scroll / self.details_max_scroll) * (height - handle_height))
            self.details_scrollbar_rect = pygame.Rect(scrollbar_x, handle_y, scrollbar_width, handle_height)
            pygame.draw.rect(screen, colors.ACCENT, self.details_scrollbar_rect)

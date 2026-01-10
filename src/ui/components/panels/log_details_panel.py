"""Log details panel component."""

import pygame
import pyperclip
import json
from typing import Dict, Any, Optional, Tuple
from ... import colors
from ...resource_display import format_resources_dict
from ..base_panel import ScrollablePanel
from ..utils import ScrollbarManager
from .. import draw_rounded_rect, draw_rounded_rect_border


class LogDetailsPanel(ScrollablePanel):
    """Panel displaying detailed view of selected log entry."""

    def __init__(self, panel, scrollbar_manager: ScrollbarManager,
                 font_small: pygame.font.Font):
        super().__init__(panel, 'detail', scrollbar_manager)
        self.font_small = font_small
        self.copy_button_rect = None
        self.line_height = 20
        self.small_line_height = 18

    def draw_content(self, screen: pygame.Surface, selected_log: Any,
                    game_state: Any) -> None:
        """Draw detailed view of selected log entry."""
        if not selected_log:
            return

        x = self.panel.rect.x + 10
        y_start = self.panel.rect.y + 50

        # Create clipping area (leave space for scrollbar)
        clip_rect = pygame.Rect(
            self.panel.rect.x + 10,
            self.panel.rect.y + 45,
            self.panel.rect.width - 30,
            self.panel.rect.height - 50
        )
        screen.set_clip(clip_rect)

        y = y_start - self.scroll_offset

        # Log type and turn
        header = f"{selected_log.log_type.value} - Turn {selected_log.turn_number}"
        text_surf = self.font_small.render(header, True, colors.WARNING)
        if y >= clip_rect.top and y < clip_rect.bottom:
            screen.blit(text_surf, (x, y))
        y += self.line_height + 5

        # Summary (wrap text)
        max_summary_width = clip_rect.width - 10
        y = self._draw_wrapped_text(
            screen, selected_log.summary, x, y, max_summary_width,
            clip_rect, self.line_height, colors.TEXT
        )
        y += 10

        # Details section
        y = self._draw_details_section(screen, selected_log, game_state, x, y, clip_rect)

        # AI Decision section
        y = self._draw_ai_decisions_section(screen, selected_log, game_state, x, y, clip_rect)

        screen.set_clip(None)

        # Update content height for scrollbar
        self.content_height = y - y_start + self.scroll_offset

    def _draw_details_section(self, screen: pygame.Surface, log: Any, game_state: Any,
                             x: int, y: int, clip_rect: pygame.Rect) -> int:
        """Draw details section and return new y position."""
        if not log.details:
            return y

        # Check if there's actual content to display
        has_content = (
            'trade_offers' in log.details or
            'offer' in log.details or
            'counter_offer' in log.details or
            'generated' in log.details or
            'failure_reason' in log.details
        )

        if not has_content:
            return y

        detail_label = self.font_small.render("Details:", True, colors.ACCENT)
        if y >= clip_rect.top and y < clip_rect.bottom:
            screen.blit(detail_label, (x, y))
        y += self.line_height

        # Format details based on log type
        if 'trade_offers' in log.details:
            for trade_offer in log.details['trade_offers']:
                target_id = trade_offer.get('target_nation_id')
                if target_id is not None:
                    target_nation = game_state.get_nation(target_id)
                    if target_nation:
                        target_text = f"Trading with {target_nation.name}:"
                        text_surf = self.font_small.render(target_text, True, colors.TEXT_SECONDARY)
                        if y >= clip_rect.top and y < clip_rect.bottom:
                            screen.blit(text_surf, (x + 10, y))
                        y += self.small_line_height

                y = self._draw_trade_offer_details(screen, trade_offer, x + 20, y, clip_rect)
                y += self.small_line_height

        if 'offer' in log.details:
            y = self._draw_trade_offer_details(screen, log.details['offer'], x + 10, y, clip_rect)
        elif 'counter_offer' in log.details:
            text_surf = self.font_small.render("Counter-offer:", True, colors.TEXT_SECONDARY)
            if y >= clip_rect.top and y < clip_rect.bottom:
                screen.blit(text_surf, (x + 10, y))
            y += self.small_line_height
            y = self._draw_trade_offer_details(screen, log.details['counter_offer'], x + 20, y, clip_rect)
        elif 'generated' in log.details:
            gen_dict = log.details['generated']
            gen_text = format_resources_dict(gen_dict)
            text_surf = self.font_small.render(f"Resources: {gen_text}", True, colors.TEXT_SECONDARY)
            if y >= clip_rect.top and y < clip_rect.bottom:
                screen.blit(text_surf, (x + 10, y))
            y += self.small_line_height

        # Display failure reason for failed builds
        if 'failure_reason' in log.details:
            failure_text = f"Reason: {log.details['failure_reason']}"
            y = self._draw_wrapped_text(
                screen, failure_text, x + 10, y, clip_rect.width - 20,
                clip_rect, self.small_line_height, colors.ERROR
            )

        y += 10
        return y

    def _draw_ai_decisions_section(self, screen: pygame.Surface, log: Any, game_state: Any,
                                   x: int, y: int, clip_rect: pygame.Rect) -> int:
        """Draw AI decisions section and return new y position."""
        if not log.ai_decisions:
            return y

        for decision in log.ai_decisions:
            nation = game_state.get_nation(decision.nation_id)
            if nation:
                ai_label = self.font_small.render(f"AI Decision - {nation.name}:", True, colors.ACCENT)
                if y >= clip_rect.top and y < clip_rect.bottom:
                    screen.blit(ai_label, (x, y))
                y += self.line_height + 5

                # Response section
                response_label = self.font_small.render("Response:", True, colors.ACCENT)
                if y >= clip_rect.top and y < clip_rect.bottom:
                    screen.blit(response_label, (x + 10, y))
                y += self.small_line_height

                y = self._draw_wrapped_text(
                    screen, decision.response, x + 20, y, self.panel.rect.width - 40,
                    clip_rect, self.small_line_height, colors.TEXT_SECONDARY
                )
                y += 10

                # Prompt section
                prompt_label = self.font_small.render("User Prompt:", True, colors.ACCENT)
                if y >= clip_rect.top and y < clip_rect.bottom:
                    screen.blit(prompt_label, (x + 10, y))
                y += self.small_line_height

                y = self._draw_wrapped_text(
                    screen, decision.prompt, x + 20, y, self.panel.rect.width - 40,
                    clip_rect, self.small_line_height, colors.TEXT_SECONDARY
                )
                y += 10

        return y

    def _draw_trade_offer_details(self, screen: pygame.Surface, offer: dict,
                                  x: int, y: int, clip_rect: pygame.Rect) -> int:
        """Draw trade offer details and return new y position."""
        # Offering
        if 'offering' in offer and offer['offering']:
            offering_text = "Offering: " + format_resources_dict(offer['offering'])
            text_surf = self.font_small.render(offering_text, True, colors.TEXT_SECONDARY)
            if y >= clip_rect.top and y < clip_rect.bottom:
                screen.blit(text_surf, (x, y))
            y += self.small_line_height

        # Requesting
        if 'requesting' in offer and offer['requesting']:
            requesting_text = "Requesting: " + format_resources_dict(offer['requesting'])
            text_surf = self.font_small.render(requesting_text, True, colors.TEXT_SECONDARY)
            if y >= clip_rect.top and y < clip_rect.bottom:
                screen.blit(text_surf, (x, y))
            y += self.small_line_height

        return y

    def _draw_wrapped_text(self, screen: pygame.Surface, text: str, x: int, y: int,
                          max_width: int, clip_rect: pygame.Rect,
                          line_height: int, color: tuple) -> int:
        """Draw text with word wrapping and return new y position. Beautifies JSON if found."""

        def wrap_and_draw_line(line_text: str, start_y: int, indent_pixels: int = 0) -> int:
            """Wrap and draw a single line of text with indentation."""
            current_y = start_y
            actual_x = x + indent_pixels
            available_width = max_width - indent_pixels

            if available_width <= 0:
                available_width = max_width
                actual_x = x

            while len(line_text) > 0:
                if self.font_small.size(line_text)[0] <= available_width:
                    if current_y >= clip_rect.top and current_y < clip_rect.bottom:
                        text_surf = self.font_small.render(line_text, True, color)
                        screen.blit(text_surf, (actual_x, current_y))
                    current_y += line_height
                    break
                else:
                    # Find best split point
                    left, right = 0, len(line_text)
                    best_split = 1

                    while left <= right:
                        mid = (left + right) // 2
                        if mid == 0:
                            break
                        test_str = line_text[:mid]
                        if self.font_small.size(test_str)[0] <= available_width:
                            best_split = mid
                            left = mid + 1
                        else:
                            right = mid - 1

                    part = line_text[:best_split]
                    remaining = line_text[best_split:]

                    # Try to find a space to break on
                    space_idx = part.rfind(' ')
                    if space_idx > best_split * 0.7:
                        part = line_text[:space_idx]
                        remaining = line_text[space_idx:].lstrip()

                    if current_y >= clip_rect.top and current_y < clip_rect.bottom:
                        text_surf = self.font_small.render(part, True, color)
                        screen.blit(text_surf, (actual_x, current_y))
                    current_y += line_height
                    line_text = remaining

            return current_y

        # Try to parse as JSON
        try:
            json_obj = json.loads(text)
            beautified = json.dumps(json_obj, indent=2)

            for line in beautified.split('\n'):
                stripped = line.lstrip()
                indent_chars = len(line) - len(stripped)
                indent_pixels = indent_chars * 5
                y = wrap_and_draw_line(stripped, y, indent_pixels)
            return y
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # No JSON, draw as regular text
        for line in text.split('\n'):
            y = wrap_and_draw_line(line, y, 0)

        return y

    def draw_copy_button(self, screen: pygame.Surface) -> None:
        """Draw copy button in the detail panel."""
        button_width = 60
        button_height = 24
        button_x = self.panel.rect.x + self.panel.rect.width - button_width - 15
        button_y = self.panel.rect.y + 10

        self.copy_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)

        mouse_pos = pygame.mouse.get_pos()
        is_hover = self.copy_button_rect.collidepoint(mouse_pos)

        button_color = colors.HOVER if is_hover else colors.PRIMARY
        border_color = colors.ACCENT if is_hover else colors.BORDER
        draw_rounded_rect(screen, button_color, self.copy_button_rect, border_radius=5)
        draw_rounded_rect_border(screen, border_color, self.copy_button_rect, border_radius=5, width=2)

        text_surf = self.font_small.render("Copy", True, colors.TEXT)
        text_rect = text_surf.get_rect(center=self.copy_button_rect.center)
        screen.blit(text_surf, text_rect)

    def handle_copy_button_click(self, mouse_pos: tuple, selected_log: Any,
                                 game_state: Any) -> bool:
        """Handle click on copy button. Returns True if clicked."""
        if self.copy_button_rect and self.copy_button_rect.collidepoint(mouse_pos):
            self._copy_log_to_clipboard(selected_log, game_state)
            return True
        return False

    def _copy_log_to_clipboard(self, log: Any, game_state: Any) -> None:
        """Copy selected log to clipboard."""
        text = self._extract_log_text(log, game_state)
        try:
            pyperclip.copy(text)
            print("[INFO] Log copied to clipboard")
        except Exception as e:
            print(f"[ERROR] Failed to copy to clipboard: {e}")

    def _extract_log_text(self, log: Any, game_state: Any) -> str:
        """Extract all text from a log entry for copying."""
        lines = []

        # Header
        lines.append(f"{log.log_type.value} - Turn {log.turn_number}")
        lines.append("")

        # Summary
        lines.append(log.summary)
        lines.append("")

        # Details
        if log.details:
            lines.append("=== Details ===")
            lines.append(json.dumps(log.details, indent=2))
            lines.append("")

        # AI Decisions
        if log.ai_decisions:
            for decision in log.ai_decisions:
                nation = game_state.get_nation(decision.nation_id)
                if nation:
                    lines.append(f"=== AI Decision - {nation.name} ===")
                    lines.append("")
                    lines.append("Response:")
                    lines.append(decision.response)
                    lines.append("")
                    lines.append("User Prompt:")
                    lines.append(decision.prompt)
                    lines.append("")

        return "\n".join(lines)

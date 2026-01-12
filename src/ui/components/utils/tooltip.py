"""Tooltip rendering utilities."""

import pygame
from typing import Tuple, List, Optional
from ... import colors
from .. import draw_rounded_rect, draw_rounded_rect_border


class TooltipRenderer:
    """Handles tooltip rendering for UI elements."""

    @staticmethod
    def draw_simple_tooltip(screen: pygame.Surface, font: pygame.font.Font,
                          text: str, mouse_pos: Tuple[int, int],
                          screen_width: int, screen_height: int,
                          padding: int = 10) -> None:
        """Draw a simple single-line tooltip near the mouse cursor."""
        text_surf = font.render(text, True, colors.TEXT)
        tooltip_width = text_surf.get_width() + padding * 2
        tooltip_height = text_surf.get_height() + padding * 2

        # Position tooltip near mouse, but keep it on screen
        tooltip_x = mouse_pos[0] + 15
        tooltip_y = mouse_pos[1] + 15

        # Keep tooltip on screen
        if tooltip_x + tooltip_width > screen_width:
            tooltip_x = mouse_pos[0] - tooltip_width - 5
        if tooltip_y + tooltip_height > screen_height:
            tooltip_y = mouse_pos[1] - tooltip_height - 5

        # Draw tooltip background
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        draw_rounded_rect(screen, colors.PANEL_GREY, tooltip_rect, border_radius=8, alpha=colors.PANEL_ALPHA)
        draw_rounded_rect_border(screen, colors.PANEL_BORDER_GREY, tooltip_rect, width=2, border_radius=8)

        # Draw tooltip text
        screen.blit(text_surf, (tooltip_x + padding, tooltip_y + padding))

    @staticmethod
    def draw_multiline_tooltip(screen: pygame.Surface, font: pygame.font.Font,
                              lines: List[str], position: Tuple[int, int],
                              screen_width: int, screen_height: int,
                              padding: int = 10, line_height: int = 20,
                              anchor: str = 'above') -> None:
        """Draw a multi-line tooltip at a specific position.

        Args:
            anchor: 'above', 'below', 'left', 'right' - where to place tooltip relative to position
        """
        # Calculate tooltip size
        max_width = max(font.size(line)[0] for line in lines)
        tooltip_width = max_width + padding * 2
        tooltip_height = len(lines) * line_height + padding * 2

        # Position based on anchor
        if anchor == 'above':
            tooltip_x = position[0] - tooltip_width // 2
            tooltip_y = position[1] - tooltip_height - 10
        elif anchor == 'below':
            tooltip_x = position[0] - tooltip_width // 2
            tooltip_y = position[1] + 10
        elif anchor == 'left':
            tooltip_x = position[0] - tooltip_width - 10
            tooltip_y = position[1] - tooltip_height // 2
        else:  # right
            tooltip_x = position[0] + 10
            tooltip_y = position[1] - tooltip_height // 2

        # Keep on screen
        if tooltip_x < 0:
            tooltip_x = 0
        if tooltip_x + tooltip_width > screen_width:
            tooltip_x = screen_width - tooltip_width
        if tooltip_y < 0:
            tooltip_y = position[1] + 10 if anchor == 'above' else 0
        if tooltip_y + tooltip_height > screen_height:
            tooltip_y = screen_height - tooltip_height

        # Draw tooltip background
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        draw_rounded_rect(screen, colors.PANEL_GREY, tooltip_rect, border_radius=8, alpha=colors.PANEL_ALPHA)
        draw_rounded_rect_border(screen, colors.PANEL_BORDER_GREY, tooltip_rect, width=2, border_radius=8)

        # Draw text lines
        y = tooltip_y + padding
        for line in lines:
            text_surf = font.render(line, True, colors.TEXT)
            screen.blit(text_surf, (tooltip_x + padding, y))
            y += line_height

    @staticmethod
    def draw_hovering_button_tooltip(screen: pygame.Surface, font: pygame.font.Font,
                                    text: str, button_rect: pygame.Rect,
                                    screen_width: int, screen_height: int) -> None:
        """Draw tooltip above a button."""
        padding = 10
        text_surf = font.render(text, True, colors.TEXT)
        tooltip_width = text_surf.get_width() + padding * 2
        tooltip_height = text_surf.get_height() + padding * 2

        # Position above the button
        tooltip_x = button_rect.centerx - tooltip_width // 2
        tooltip_y = button_rect.top - tooltip_height - 10

        # Keep on screen
        if tooltip_x < 0:
            tooltip_x = 0
        if tooltip_x + tooltip_width > screen_width:
            tooltip_x = screen_width - tooltip_width

        # Draw tooltip
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        draw_rounded_rect(screen, colors.PANEL_GREY, tooltip_rect, border_radius=8, alpha=colors.PANEL_ALPHA)
        draw_rounded_rect_border(screen, colors.PANEL_BORDER_GREY, tooltip_rect, width=2, border_radius=8)
        screen.blit(text_surf, (tooltip_x + padding, tooltip_y + padding))

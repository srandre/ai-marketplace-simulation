"""Base scrollable panel component."""

import pygame
from typing import Optional
from ..components import Panel
from .utils import ScrollbarManager


class ScrollablePanel:
    """Base class for panels with scrolling support."""

    def __init__(self, panel: Panel, panel_id: str,
                 scrollbar_manager: ScrollbarManager):
        """Initialize scrollable panel.

        Args:
            panel: The Panel component to render
            panel_id: Unique identifier for this panel (for drag tracking)
            scrollbar_manager: Shared scrollbar manager
        """
        self.panel = panel
        self.panel_id = panel_id
        self.scrollbar_manager = scrollbar_manager
        self.scroll_offset = 0
        self.content_height = 0  # Actual rendered content height

    def get_visible_height(self) -> int:
        """Get the visible height of the panel content area."""
        return self.panel.rect.height - 50

    def get_content_rect(self, margin: int = 5) -> pygame.Rect:
        """Get the clipping rectangle for content rendering."""
        return pygame.Rect(
            self.panel.rect.x + margin,
            self.panel.rect.y + 45,
            self.panel.rect.width - margin * 2 - 20,  # Leave space for scrollbar
            self.panel.rect.height - 50
        )

    def handle_scroll_wheel(self, mouse_pos: tuple, wheel_delta: int,
                           scroll_speed: int = 30) -> bool:
        """Handle mouse wheel scrolling. Returns True if scroll was handled."""
        if not self.panel.rect.collidepoint(mouse_pos):
            return False

        visible_height = self.get_visible_height()
        max_scroll = max(0, self.content_height - visible_height)

        self.scroll_offset -= wheel_delta * scroll_speed
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset))
        return True

    def is_scrollbar_clicked(self, mouse_pos: tuple) -> bool:
        """Check if mouse click is on this panel's scrollbar."""
        visible_height = self.get_visible_height()
        scrollbar_rect = self.scrollbar_manager.get_scrollbar_rect(self.panel.rect)
        return self.scrollbar_manager.is_point_in_scrollbar(
            mouse_pos, scrollbar_rect, self.content_height, visible_height
        )

    def start_scrollbar_drag(self, mouse_pos: tuple) -> None:
        """Start dragging this panel's scrollbar."""
        self.scrollbar_manager.start_drag(self.panel_id, mouse_pos[1], self.scroll_offset)

    def handle_scrollbar_drag(self, mouse_pos: tuple) -> None:
        """Update scroll position during drag."""
        if not self.scrollbar_manager.is_dragging(self.panel_id):
            return

        visible_height = self.get_visible_height()
        scrollbar_rect = self.scrollbar_manager.get_scrollbar_rect(self.panel.rect)
        self.scroll_offset = self.scrollbar_manager.handle_drag(
            mouse_pos[1], scrollbar_rect, self.content_height, visible_height
        )

    def draw_scrollbar(self, screen: pygame.Surface) -> None:
        """Draw scrollbar if needed."""
        visible_height = self.get_visible_height()
        self.scrollbar_manager.draw_scrollbar(
            screen, self.panel.rect, self.scroll_offset,
            self.content_height, visible_height
        )

    def draw_panel_background(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the panel background and title."""
        self.panel.draw(screen, font)

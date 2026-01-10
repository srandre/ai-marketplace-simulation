"""Scrollbar utility for scrollable panels."""

import pygame
from typing import Optional, Tuple
from ... import colors
from .. import draw_rounded_rect


class ScrollbarManager:
    """Manages scrollbar rendering and dragging for scrollable panels."""

    def __init__(self):
        self.dragging_target: Optional[str] = None  # ID of panel being dragged
        self.drag_start_y: int = 0
        self.drag_start_offset: int = 0

    def is_dragging(self, target_id: str) -> bool:
        """Check if a specific scrollbar is being dragged."""
        return self.dragging_target == target_id

    def start_drag(self, target_id: str, mouse_y: int, current_offset: int) -> None:
        """Start dragging a scrollbar."""
        self.dragging_target = target_id
        self.drag_start_y = mouse_y
        self.drag_start_offset = current_offset

    def stop_drag(self) -> None:
        """Stop dragging any scrollbar."""
        self.dragging_target = None

    def handle_drag(self, mouse_y: int, scrollbar_rect: pygame.Rect,
                    content_height: int, visible_height: int) -> int:
        """Calculate new scroll offset based on drag motion."""
        max_scroll = max(0, content_height - visible_height)

        # Calculate how much the mouse moved
        mouse_delta = mouse_y - self.drag_start_y

        # Convert mouse movement to scroll movement
        scrollbar_height = scrollbar_rect.height
        thumb_height = max(20, int((visible_height / content_height) * scrollbar_height))
        scrollable_area = scrollbar_height - thumb_height

        if scrollable_area > 0:
            scroll_delta = (mouse_delta / scrollable_area) * max_scroll
            new_offset = self.drag_start_offset + scroll_delta
            return int(max(0, min(max_scroll, new_offset)))

        return self.drag_start_offset

    def get_scrollbar_rect(self, panel_rect: pygame.Rect, width: int = 8,
                          margin: int = 5, top_offset: int = 45,
                          bottom_offset: int = 50) -> pygame.Rect:
        """Calculate scrollbar rectangle for a panel."""
        scrollbar_x = panel_rect.x + panel_rect.width - width - margin
        scrollbar_y = panel_rect.y + top_offset
        scrollbar_height = panel_rect.height - bottom_offset
        return pygame.Rect(scrollbar_x, scrollbar_y, width, scrollbar_height)

    def is_point_in_scrollbar(self, mouse_pos: Tuple[int, int],
                             scrollbar_rect: pygame.Rect,
                             content_height: int, visible_height: int) -> bool:
        """Check if mouse point is within scrollbar area."""
        # Only show scrollbar if content is larger than visible area
        if content_height <= visible_height:
            return False
        return scrollbar_rect.collidepoint(mouse_pos)

    def draw_scrollbar(self, screen: pygame.Surface, panel_rect: pygame.Rect,
                      scroll_offset: int, content_height: int, visible_height: int,
                      width: int = 8, margin: int = 5, top_offset: int = 45,
                      bottom_offset: int = 50) -> None:
        """Draw a scrollbar for a panel."""
        if content_height <= visible_height:
            return  # No scrollbar needed

        # Get scrollbar rect
        scrollbar_rect = self.get_scrollbar_rect(panel_rect, width, margin,
                                                 top_offset, bottom_offset)

        # Draw scrollbar background
        draw_rounded_rect(screen, colors.SECONDARY, scrollbar_rect, border_radius=6)

        # Calculate thumb size and position
        scrollbar_height = scrollbar_rect.height
        thumb_height = max(20, int((visible_height / content_height) * scrollbar_height))
        max_scroll = content_height - visible_height

        if max_scroll > 0:
            thumb_y = scrollbar_rect.y + int((scroll_offset / max_scroll) * (scrollbar_height - thumb_height))
        else:
            thumb_y = scrollbar_rect.y

        # Draw scrollbar thumb
        thumb_rect = pygame.Rect(scrollbar_rect.x, thumb_y, width, thumb_height)
        draw_rounded_rect(screen, colors.TEXT_SECONDARY, thumb_rect, border_radius=6)

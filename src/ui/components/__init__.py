"""UI components for the game interface."""

import pygame
from typing import Callable, Optional

from .. import colors


def draw_rounded_rect(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    rect: pygame.Rect,
    border_radius: int = 10
) -> None:
    """Draw a rounded rectangle."""
    pygame.draw.rect(surface, color, rect, border_radius=border_radius)


def draw_rounded_rect_border(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    rect: pygame.Rect,
    width: int = 2,
    border_radius: int = 10
) -> None:
    """Draw a rounded rectangle border."""
    pygame.draw.rect(surface, color, rect, width=width, border_radius=border_radius)


class Button:
    """A clickable button component."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        onclick: Callable[[], None],
        enabled: bool = True,
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.onclick = onclick
        self.enabled = enabled
        self.hovered = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle mouse events. Returns True if event was handled."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.enabled and self.rect.collidepoint(event.pos):
                self.onclick()
                return True
        return False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the button."""
        if not self.enabled:
            bg_color = colors.SECONDARY
            text_color = colors.TEXT_SECONDARY
        elif self.hovered:
            bg_color = colors.HOVER
            text_color = colors.TEXT
        else:
            bg_color = colors.PRIMARY
            text_color = colors.TEXT

        draw_rounded_rect(screen, bg_color, self.rect, border_radius=8)
        draw_rounded_rect_border(screen, colors.BORDER, self.rect, width=2, border_radius=8)

        text_surf = font.render(self.text, True, text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)


class Panel:
    """A rectangular panel for grouping content."""

    def __init__(self, x: int, y: int, width: int, height: int, title: str = ""):
        self.rect = pygame.Rect(x, y, width, height)
        self.title = title

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the panel."""
        draw_rounded_rect(screen, colors.SECONDARY, self.rect, border_radius=10)
        draw_rounded_rect_border(screen, colors.BORDER, self.rect, width=2, border_radius=10)

        if self.title:
            title_surf = font.render(self.title, True, colors.TEXT)
            screen.blit(title_surf, (self.rect.x + 10, self.rect.y + 10))


class ScrollableList:
    """A scrollable list of items."""

    def __init__(self, x: int, y: int, width: int, height: int, item_height: int = 30):
        self.rect = pygame.Rect(x, y, width, height)
        self.item_height = item_height
        self.scroll_offset = 0
        self.items = []
        self.selected_index = -1

    def set_items(self, items: list) -> None:
        """Set the list items."""
        self.items = items
        self.scroll_offset = 0

    def handle_event(self, event: pygame.event.Event) -> Optional[int]:
        """Handle events. Returns selected index if an item was clicked."""
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll_offset = max(0, min(
                len(self.items) * self.item_height - self.rect.height,
                self.scroll_offset - event.y * 20
            ))
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                relative_y = event.pos[1] - self.rect.y + self.scroll_offset
                clicked_index = int(relative_y // self.item_height)
                if 0 <= clicked_index < len(self.items):
                    self.selected_index = clicked_index
                    return clicked_index

        return None

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the scrollable list."""
        # Create a surface for clipping
        list_surface = pygame.Surface((self.rect.width, self.rect.height))
        list_surface.fill(colors.SECONDARY)

        y_pos = -self.scroll_offset
        for i, item in enumerate(self.items):
            if y_pos + self.item_height >= 0 and y_pos < self.rect.height:
                item_rect = pygame.Rect(0, y_pos, self.rect.width, self.item_height)

                if i == self.selected_index:
                    pygame.draw.rect(list_surface, colors.HOVER, item_rect)
                elif i % 2 == 0:
                    pygame.draw.rect(list_surface, colors.PRIMARY, item_rect)

                pygame.draw.rect(list_surface, colors.BORDER, item_rect, 1)

                text_surf = font.render(str(item), True, colors.TEXT)
                list_surface.blit(text_surf, (5, y_pos + 5))

            y_pos += self.item_height

        screen.blit(list_surface, self.rect.topleft)
        draw_rounded_rect_border(screen, colors.BORDER, self.rect, width=2, border_radius=10)


__all__ = [
    'Button',
    'Panel',
    'ScrollableList',
    'draw_rounded_rect',
    'draw_rounded_rect_border',
]

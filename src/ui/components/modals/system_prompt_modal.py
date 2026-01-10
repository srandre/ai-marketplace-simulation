"""System prompt modal component."""

import pygame
import pyperclip
from typing import Tuple
from ... import colors
from .. import draw_rounded_rect, draw_rounded_rect_border
from ..utils import ScrollbarManager


class SystemPromptModal:
    """Modal dialog for displaying system prompt with scrolling and copy."""

    def __init__(self, font_small: pygame.font.Font, font_large: pygame.font.Font,
                 scrollbar_manager: ScrollbarManager):
        self.font_small = font_small
        self.font_large = font_large
        self.scrollbar_manager = scrollbar_manager
        self.scroll_offset = 0
        self.content_height = 0
        self.copy_button_rect = None
        self.is_visible = False

    def show(self) -> None:
        """Show the modal."""
        self.is_visible = True
        self.scroll_offset = 0

    def hide(self) -> None:
        """Hide the modal."""
        self.is_visible = False
        self.scroll_offset = 0

    def toggle(self) -> None:
        """Toggle modal visibility."""
        if self.is_visible:
            self.hide()
        else:
            self.show()

    def get_modal_rect(self, screen_width: int, screen_height: int) -> pygame.Rect:
        """Calculate modal rectangle."""
        modal_width = min(800, screen_width - 100)
        modal_height = min(600, screen_height - 100)
        modal_x = (screen_width - modal_width) // 2
        modal_y = (screen_height - modal_height) // 2
        return pygame.Rect(modal_x, modal_y, modal_width, modal_height)

    def handle_click(self, mouse_pos: Tuple[int, int], screen_width: int,
                    screen_height: int) -> bool:
        """Handle mouse click. Returns True if modal should close."""
        modal_rect = self.get_modal_rect(screen_width, screen_height)

        if not modal_rect.collidepoint(mouse_pos):
            # Clicked outside modal (backdrop)
            return True

        # Check if clicked on copy button
        if self.copy_button_rect and self.copy_button_rect.collidepoint(mouse_pos):
            return False  # Don't close modal

        # Check if clicked on scrollbar
        if self._is_scrollbar_clicked(mouse_pos, screen_width, screen_height):
            self.scrollbar_manager.start_drag('modal', mouse_pos[1], self.scroll_offset)

        return False

    def handle_scroll_wheel(self, mouse_pos: Tuple[int, int], wheel_delta: int,
                           screen_width: int, screen_height: int) -> bool:
        """Handle mouse wheel scrolling. Returns True if handled."""
        modal_rect = self.get_modal_rect(screen_width, screen_height)

        if not modal_rect.collidepoint(mouse_pos):
            return False

        # Calculate max scroll
        content_height = modal_rect.height - 140
        max_scroll = max(0, self.content_height - content_height)

        self.scroll_offset -= wheel_delta * 30
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset))
        return True

    def handle_scrollbar_drag(self, mouse_pos: Tuple[int, int],
                             screen_width: int, screen_height: int) -> None:
        """Update scroll position during drag."""
        if not self.scrollbar_manager.is_dragging('modal'):
            return

        modal_rect = self.get_modal_rect(screen_width, screen_height)
        scrollbar_rect = self._get_scrollbar_rect(modal_rect)
        content_height = modal_rect.height - 140

        self.scroll_offset = self.scrollbar_manager.handle_drag(
            mouse_pos[1], scrollbar_rect, self.content_height, content_height
        )

    def draw(self, screen: pygame.Surface, system_prompt: str,
            screen_width: int, screen_height: int) -> None:
        """Draw the modal."""
        # Draw backdrop
        backdrop = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, 180))
        screen.blit(backdrop, (0, 0))

        # Get modal rect
        modal_rect = self.get_modal_rect(screen_width, screen_height)

        # Draw modal background
        draw_rounded_rect(screen, colors.SECONDARY, modal_rect, border_radius=15)
        draw_rounded_rect_border(screen, colors.ACCENT, modal_rect, width=3, border_radius=15)

        # Draw title
        title_text = self.font_large.render("System Prompt", True, colors.ACCENT)
        title_rect = title_text.get_rect(centerx=modal_rect.centerx, top=modal_rect.top + 20)
        screen.blit(title_text, title_rect)

        # Draw close hint
        hint_text = self.font_small.render("Press ESC or click outside to close", True, colors.TEXT_SECONDARY)
        hint_rect = hint_text.get_rect(centerx=modal_rect.centerx, top=title_rect.bottom + 5)
        screen.blit(hint_text, hint_rect)

        # Create scrollable content area
        content_y = hint_rect.bottom + 20
        content_height = modal_rect.bottom - content_y - 20
        content_rect = pygame.Rect(
            modal_rect.left + 20,
            content_y,
            modal_rect.width - 40,
            content_height
        )

        # Draw content
        self._draw_content(screen, system_prompt, content_rect)

        # Draw copy button
        self._draw_copy_button(screen, modal_rect)

        # Draw scrollbar if needed
        if self.content_height > content_height:
            self._draw_scrollbar(screen, modal_rect, content_rect)

    def _draw_content(self, screen: pygame.Surface, system_prompt: str,
                     content_rect: pygame.Rect) -> None:
        """Draw scrollable content."""
        # Set clipping for content area
        screen.set_clip(content_rect)

        # Track starting Y position
        y_start = content_rect.top
        y = content_rect.top - self.scroll_offset
        line_height = 20

        for line in system_prompt.split('\n'):
            if line.strip():
                # Wrap long lines
                words = line.split(' ')
                current_line = ""
                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    test_surf = self.font_small.render(test_line, True, colors.TEXT)
                    if test_surf.get_width() <= content_rect.width - 20:
                        current_line = test_line
                    else:
                        # Draw current line
                        if current_line and y >= content_rect.top - line_height and y < content_rect.bottom:
                            text_surf = self.font_small.render(current_line, True, colors.TEXT)
                            screen.blit(text_surf, (content_rect.left + 10, y))
                        y += line_height
                        current_line = word

                # Draw remaining line
                if current_line and y >= content_rect.top - line_height and y < content_rect.bottom:
                    text_surf = self.font_small.render(current_line, True, colors.TEXT)
                    screen.blit(text_surf, (content_rect.left + 10, y))
                y += line_height
            else:
                # Empty line
                y += line_height // 2

        # Update content height
        self.content_height = y - y_start + self.scroll_offset

        # Reset clipping
        screen.set_clip(None)

    def _draw_copy_button(self, screen: pygame.Surface, modal_rect: pygame.Rect) -> None:
        """Draw copy button."""
        button_width = 60
        button_height = 28
        button_x = modal_rect.x + modal_rect.width - button_width - 25
        button_y = modal_rect.y + 60

        self.copy_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)

        mouse_pos = pygame.mouse.get_pos()
        is_hover = self.copy_button_rect.collidepoint(mouse_pos)

        button_color = colors.ACCENT if is_hover else colors.SECONDARY
        draw_rounded_rect(screen, button_color, self.copy_button_rect, border_radius=5)
        draw_rounded_rect_border(screen, colors.ACCENT, self.copy_button_rect, border_radius=5, width=2)

        text_color = colors.BACKGROUND if is_hover else colors.TEXT
        text_surf = self.font_small.render("Copy", True, text_color)
        text_rect = text_surf.get_rect(center=self.copy_button_rect.center)
        screen.blit(text_surf, text_rect)

    def _draw_scrollbar(self, screen: pygame.Surface, modal_rect: pygame.Rect,
                       content_rect: pygame.Rect) -> None:
        """Draw scrollbar."""
        scrollbar_width = 8
        scrollbar_x = modal_rect.right - scrollbar_width - 15
        scrollbar_y = content_rect.top
        scrollbar_height = content_rect.height

        # Draw scrollbar track
        track_rect = pygame.Rect(scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height)
        draw_rounded_rect(screen, colors.BORDER, track_rect, border_radius=4)

        # Calculate thumb size and position
        visible_height = content_rect.height
        thumb_height = max(20, int((visible_height / self.content_height) * scrollbar_height))
        max_scroll = self.content_height - visible_height

        if max_scroll > 0:
            thumb_y = scrollbar_y + int((self.scroll_offset / max_scroll) * (scrollbar_height - thumb_height))
        else:
            thumb_y = scrollbar_y

        # Draw thumb
        thumb_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)
        draw_rounded_rect(screen, colors.ACCENT, thumb_rect, border_radius=4)

    def _get_scrollbar_rect(self, modal_rect: pygame.Rect) -> pygame.Rect:
        """Get scrollbar rectangle."""
        scrollbar_width = 8
        content_height = modal_rect.height - 140
        scrollbar_x = modal_rect.right - scrollbar_width - 15
        scrollbar_y = modal_rect.top + 100
        return pygame.Rect(scrollbar_x, scrollbar_y, scrollbar_width, content_height)

    def _is_scrollbar_clicked(self, mouse_pos: Tuple[int, int],
                             screen_width: int, screen_height: int) -> bool:
        """Check if click is on scrollbar."""
        modal_rect = self.get_modal_rect(screen_width, screen_height)
        content_height = modal_rect.height - 140

        # Only show scrollbar if content is larger than visible area
        if self.content_height <= content_height:
            return False

        scrollbar_rect = self._get_scrollbar_rect(modal_rect)
        return scrollbar_rect.collidepoint(mouse_pos)

    def handle_copy_button_click(self, mouse_pos: Tuple[int, int],
                                 system_prompt: str) -> bool:
        """Handle click on copy button. Returns True if clicked."""
        if self.copy_button_rect and self.copy_button_rect.collidepoint(mouse_pos):
            try:
                pyperclip.copy(system_prompt)
                print("[INFO] System prompt copied to clipboard")
            except Exception as e:
                print(f"[ERROR] Failed to copy to clipboard: {e}")
            return True
        return False

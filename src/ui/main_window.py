"""Main game window with Pygame."""

import pygame
from typing import Optional

from ..game.game_controller import GameController
from ..models.enums import ResourceType
from ..utils.config import config
from . import colors
from .components import Button, Panel, draw_rounded_rect
from .components.utils import ScrollbarManager, TooltipRenderer
from .components.panels import (
    NationsPanel, CurrentTurnPanel, GameLogsPanel,
    LogDetailsPanel, GlobalResourcesBar
)
from .components.modals import SystemPromptModal


class MainWindow:
    """Main game window."""

    def __init__(self, controller: GameController):
        pygame.init()

        self.controller = controller

        # Create maximized window
        self.width = config.get("ui.window_width", 1600)
        self.height = config.get("ui.window_height", 900)

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("Rise of AI: Strategic Resource Game")

        # Maximize the window (platform-specific)
        import ctypes
        try:
            hwnd = pygame.display.get_wm_info()['window']
            ctypes.windll.user32.ShowWindow(hwnd, 3)  # 3 = SW_MAXIMIZE
        except:
            pass

        self.clock = pygame.time.Clock()
        self.fps = config.get("ui.fps", 60)

        # Fonts - use system font that supports emojis
        emoji_font = self._get_emoji_font()
        self.font_small = pygame.font.SysFont(emoji_font, 18)
        self.font_medium = pygame.font.SysFont(emoji_font, 24)
        self.font_large = pygame.font.SysFont(emoji_font, 32)
        self.font_title = pygame.font.SysFont(emoji_font, 48)

        # Game state
        self.running = True
        self.auto_mode = False

        # Shared managers
        self.scrollbar_manager = ScrollbarManager()
        self.tooltip_renderer = TooltipRenderer()

        # Tooltip state for logs
        self.tooltip_log = None
        self.tooltip_timer = 0
        self.tooltip_delay = 30

        # Info button state
        self.info_button_rect = None
        self.info_button_hovered = False

        # Async turn execution
        from ..game.async_turn_executor import AsyncTurnExecutor
        self.turn_executor = AsyncTurnExecutor(self.controller)
        self.turn_executor.on_turn_complete = self._on_turn_complete
        self.turn_executor.start()

        # Load flag images
        self.flag_images = self._load_flag_images()

        # UI Components - will be initialized in _setup_ui
        self.nations_panel: Optional[NationsPanel] = None
        self.current_turn_panel: Optional[CurrentTurnPanel] = None
        self.logs_panel: Optional[GameLogsPanel] = None
        self.details_panel: Optional[LogDetailsPanel] = None
        self.global_resources_bar: Optional[GlobalResourcesBar] = None
        self.system_prompt_modal: Optional[SystemPromptModal] = None
        self.buttons = []

        # Setup UI
        self._setup_ui()

    def _get_emoji_font(self) -> str:
        """Get a system font that supports emojis."""
        emoji_fonts = [
            'segoeuiemoji', 'seguiemj', 'segoe ui emoji',
            'arial unicode ms', 'apple color emoji',
            'noto color emoji', 'symbola', 'unifont',
        ]

        available_fonts = pygame.font.get_fonts()

        for font in emoji_fonts:
            if font.lower().replace(' ', '') in [f.lower().replace(' ', '') for f in available_fonts]:
                return font

        fallback_fonts = ['arial', 'helvetica', 'verdana', 'tahoma']
        for font in fallback_fonts:
            if font in available_fonts:
                return font

        return None

    def _load_flag_images(self) -> dict:
        """Load flag images from assets/flags directory."""
        from pathlib import Path

        flags = {}
        project_root = Path(__file__).parent.parent.parent
        flags_dir = project_root / "assets" / "flags"

        for nation in self.controller.game_state.nations:
            flag_filename = f"{nation.code}.png"
            flag_path = flags_dir / flag_filename

            if flag_path.exists():
                try:
                    flag_img = pygame.image.load(str(flag_path))
                    flag_small = pygame.transform.scale(flag_img, (24, 18))
                    flag_medium = pygame.transform.scale(flag_img, (32, 24))
                    flag_large = pygame.transform.scale(flag_img, (48, 36))
                    flags[nation.name] = {
                        'small': flag_small,
                        'medium': flag_medium,
                        'large': flag_large
                    }
                except Exception as e:
                    print(f"Error loading flag for {nation.name} ({nation.code}): {e}")
            else:
                print(f"Flag image not found: {flag_path}")

        return flags

    def _setup_ui(self) -> None:
        """Setup UI components."""
        # Responsive layout calculations
        button_height = 50
        button_y = self.height - 70
        button_width = 150
        button_spacing = 20

        # Buttons
        btn_auto = Button(
            button_spacing, button_y, button_width, button_height,
            f"Auto: {'ON' if self.auto_mode else 'OFF'}",
            self._toggle_auto_mode,
            enabled=True
        )

        btn_next_turn = Button(
            button_spacing * 2 + button_width, button_y, button_width, button_height,
            "Next Turn",
            self._next_turn,
            enabled=True
        )

        self.buttons = [btn_auto, btn_next_turn]

        # Info button in bottom right corner
        info_button_size = 40
        self.info_button_rect = pygame.Rect(
            self.width - info_button_size - button_spacing,
            button_y + (button_height - info_button_size) // 2,
            info_button_size,
            info_button_size
        )

        # Responsive panels
        panel_padding = 20
        nations_width = int(self.width * 0.35)
        right_panel_width = self.width - nations_width - panel_padding * 3

        current_turn_height = int((self.height - button_height - panel_padding * 4) * 0.3)
        logs_height = self.height - button_height - current_turn_height - panel_padding * 4

        # Nations panel
        nations_panel = Panel(
            panel_padding,
            panel_padding,
            nations_width,
            self.height - button_height - panel_padding * 3,
            "Nations"
        )
        self.nations_panel = NationsPanel(
            nations_panel, self.scrollbar_manager,
            self.flag_images, self.font_small
        )

        # Current turn panel
        round_title = f"Round {self.controller.game_state.round_number}"
        current_panel = Panel(
            nations_width + panel_padding * 2,
            panel_padding,
            right_panel_width,
            current_turn_height,
            round_title
        )
        self.current_turn_panel = CurrentTurnPanel(
            current_panel, self.flag_images,
            self.font_small, self.font_medium
        )

        # Logs panel (may be split if log is selected)
        if self.logs_panel and self.logs_panel.selected_log:
            # Split panel in half
            logs_panel_width = right_panel_width // 2 - panel_padding // 2
            detail_panel_width = right_panel_width // 2 - panel_padding // 2

            logs_panel = Panel(
                nations_width + panel_padding * 2,
                current_turn_height + panel_padding * 2,
                logs_panel_width,
                logs_height,
                "Game Logs"
            )

            detail_panel = Panel(
                nations_width + panel_padding * 2 + logs_panel_width + panel_padding,
                current_turn_height + panel_padding * 2,
                detail_panel_width,
                logs_height,
                "Log Details"
            )

            # Preserve selected log and scroll position when recreating
            selected_log = self.logs_panel.selected_log
            scroll_offset = self.logs_panel.scroll_offset
            self.logs_panel = GameLogsPanel(
                logs_panel, self.scrollbar_manager,
                self.flag_images, self.font_small
            )
            self.logs_panel.selected_log = selected_log
            self.logs_panel.scroll_offset = scroll_offset

            self.details_panel = LogDetailsPanel(
                detail_panel, self.scrollbar_manager, self.font_small
            )
        else:
            logs_panel = Panel(
                nations_width + panel_padding * 2,
                current_turn_height + panel_padding * 2,
                right_panel_width,
                logs_height,
                "Game Logs"
            )

            if self.logs_panel:
                # Preserve state when recreating
                selected_log = self.logs_panel.selected_log
                scroll_offset = self.logs_panel.scroll_offset
                self.logs_panel = GameLogsPanel(
                    logs_panel, self.scrollbar_manager,
                    self.flag_images, self.font_small
                )
                self.logs_panel.selected_log = selected_log
                self.logs_panel.scroll_offset = scroll_offset
            else:
                self.logs_panel = GameLogsPanel(
                    logs_panel, self.scrollbar_manager,
                    self.flag_images, self.font_small
                )

            self.details_panel = None

        # Global resources bar
        self.global_resources_bar = GlobalResourcesBar(self.font_small)

        # System prompt modal
        self.system_prompt_modal = SystemPromptModal(
            self.font_small, self.font_large, self.scrollbar_manager
        )

    def _toggle_auto_mode(self) -> None:
        """Toggle auto mode."""
        if self.controller.game_state.game_over:
            return

        self.auto_mode = not self.auto_mode
        self.buttons[0].text = f"Auto: {'ON' if self.auto_mode else 'OFF'}"

    def _next_turn(self) -> None:
        """Execute next turn asynchronously."""
        if not self.turn_executor.status.is_busy():
            print(f"\n{'='*60}")
            print(f"Queuing Turn {self.controller.game_state.turn_number}")
            print(f"{'='*60}")
            self.turn_executor.execute_turn_async()

    def _on_turn_complete(self) -> None:
        """Called when turn execution completes."""
        print(f"Turn {self.controller.game_state.turn_number} complete\n")

    def handle_events(self) -> None:
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # Handle ESC key to close modal
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and self.system_prompt_modal.is_visible:
                    self.system_prompt_modal.hide()

            # Handle window resize
            if event.type == pygame.VIDEORESIZE:
                self.width = event.w
                self.height = event.h
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                self._setup_ui()

            # Handle mouse clicks
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                self._handle_mouse_click(mouse_pos)

            # Handle mouse button release
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.scrollbar_manager.stop_drag()

            # Handle mouse motion for scrollbar dragging
            if event.type == pygame.MOUSEMOTION:
                mouse_pos = pygame.mouse.get_pos()
                if self.scrollbar_manager.dragging_target:
                    self._handle_scrollbar_drag(mouse_pos)

            # Handle mouse wheel for scrolling
            if event.type == pygame.MOUSEWHEEL:
                mouse_pos = pygame.mouse.get_pos()
                self._handle_scroll_wheel(mouse_pos, event.y)

            # Handle button events
            for button in self.buttons:
                if button.handle_event(event):
                    break

    def _handle_mouse_click(self, mouse_pos: tuple) -> None:
        """Handle mouse click events."""
        # If modal is open, handle modal interactions
        if self.system_prompt_modal.is_visible:
            # Check copy button first
            system_prompt = self.controller.decision_maker.system_prompt
            if self.system_prompt_modal.handle_copy_button_click(mouse_pos, system_prompt):
                return

            # Check if should close modal
            if self.system_prompt_modal.handle_click(mouse_pos, self.width, self.height):
                self.system_prompt_modal.hide()
            return

        # Check if clicked on info button
        if self.info_button_rect.collidepoint(mouse_pos):
            self.system_prompt_modal.show()
            return

        # Check if clicked on copy button in details panel
        if self.details_panel:
            if self.details_panel.handle_copy_button_click(
                mouse_pos, self.logs_panel.selected_log, self.controller.game_state
            ):
                return

        # Check if clicked on scrollbars
        if self.nations_panel.is_scrollbar_clicked(mouse_pos):
            self.nations_panel.start_scrollbar_drag(mouse_pos)
            return

        if self.logs_panel.is_scrollbar_clicked(mouse_pos):
            self.logs_panel.start_scrollbar_drag(mouse_pos)
            return

        if self.details_panel and self.details_panel.is_scrollbar_clicked(mouse_pos):
            self.details_panel.start_scrollbar_drag(mouse_pos)
            return

        # Check if clicked on a log entry
        if self.logs_panel.handle_click(mouse_pos, self.controller.game_state):
            self._setup_ui()  # Recalculate layout

    def _handle_scrollbar_drag(self, mouse_pos: tuple) -> None:
        """Handle scrollbar dragging."""
        if self.system_prompt_modal.is_visible:
            self.system_prompt_modal.handle_scrollbar_drag(mouse_pos, self.width, self.height)
            return

        self.nations_panel.handle_scrollbar_drag(mouse_pos)
        self.logs_panel.handle_scrollbar_drag(mouse_pos)
        if self.details_panel:
            self.details_panel.handle_scrollbar_drag(mouse_pos)

    def _handle_scroll_wheel(self, mouse_pos: tuple, wheel_delta: int) -> None:
        """Handle mouse wheel scrolling."""
        # Modal scrolling
        if self.system_prompt_modal.is_visible:
            self.system_prompt_modal.handle_scroll_wheel(mouse_pos, wheel_delta, self.width, self.height)
            return

        # Panel scrolling
        if self.nations_panel.handle_scroll_wheel(mouse_pos, wheel_delta):
            return

        if self.logs_panel.handle_scroll_wheel(mouse_pos, wheel_delta):
            return

        if self.details_panel and self.details_panel.handle_scroll_wheel(mouse_pos, wheel_delta):
            return

    def update(self) -> None:
        """Update game state."""
        game_over = self.controller.game_state.game_over
        is_busy = self.turn_executor.status.is_busy()

        # Update button states
        self.buttons[1].enabled = not is_busy and not self.auto_mode and not game_over
        self.buttons[0].enabled = not game_over

        # Disable auto mode if game is over
        if game_over and self.auto_mode:
            self.auto_mode = False
            self.buttons[0].text = "Auto: OFF"

        # Auto mode processing
        if self.auto_mode and not is_busy and not game_over:
            self._next_turn()

        # Update hover states
        mouse_pos = pygame.mouse.get_pos()
        self.info_button_hovered = self.info_button_rect.collidepoint(mouse_pos)
        self.global_resources_bar.update_hover(mouse_pos)

        # Update tooltip timer for logs
        if self.logs_panel.panel.rect.collidepoint(mouse_pos):
            hovered_log = self.logs_panel.get_hovered_log(mouse_pos, self.controller.game_state)
            if hovered_log == self.tooltip_log:
                self.tooltip_timer += 1
            else:
                self.tooltip_log = hovered_log
                self.tooltip_timer = 0
        else:
            self.tooltip_log = None
            self.tooltip_timer = 0

    def draw(self) -> None:
        """Draw the game window."""
        self.screen.fill(colors.BACKGROUND)

        # Draw panel backgrounds
        self.nations_panel.draw_panel_background(self.screen, self.font_medium)
        self.current_turn_panel.draw_panel_background(self.screen, self.font_medium)
        self.logs_panel.draw_panel_background(self.screen, self.font_medium)

        if self.details_panel:
            self.details_panel.draw_panel_background(self.screen, self.font_medium)

        # Draw panel contents
        self.nations_panel.draw_content(self.screen, self.controller.game_state)
        self.nations_panel.draw_scrollbar(self.screen)

        self.current_turn_panel.draw_content(
            self.screen, self.controller.game_state, self.turn_executor
        )

        self.logs_panel.draw_content(self.screen, self.controller.game_state)
        self.logs_panel.draw_scrollbar(self.screen)

        if self.details_panel and self.logs_panel.selected_log:
            self.details_panel.draw_content(
                self.screen, self.logs_panel.selected_log, self.controller.game_state
            )
            self.details_panel.draw_scrollbar(self.screen)
            self.details_panel.draw_copy_button(self.screen)

        # Draw buttons
        for button in self.buttons:
            button.draw(self.screen, self.font_medium)

        # Draw global resources bar
        self.global_resources_bar.draw(
            self.screen, self.controller.game_state, self.width, self.height
        )

        # Draw info button
        self._draw_info_button()

        # Draw tooltips
        if self.info_button_hovered and not self.system_prompt_modal.is_visible:
            self.tooltip_renderer.draw_hovering_button_tooltip(
                self.screen, self.font_small, "System Prompt",
                self.info_button_rect, self.width, self.height
            )

        # Global resource tooltip
        tooltip_data = self.global_resources_bar.get_tooltip_data(self.controller.game_state)
        if tooltip_data and not self.system_prompt_modal.is_visible:
            rt, gen_name, count, cost_text = tooltip_data
            lines = [gen_name, f"Built: {count}", f"Cost: {cost_text}"]
            rect = self.global_resources_bar.resource_rects[rt]
            self.tooltip_renderer.draw_multiline_tooltip(
                self.screen, self.font_small, lines,
                (rect.centerx, rect.top), self.width, self.height, anchor='above'
            )

        # Log tooltip
        if self.tooltip_log and self.tooltip_timer >= self.tooltip_delay:
            import re
            summary_clean = re.sub(r'[\U0001F1E6-\U0001F1FF]{2}', '', self.tooltip_log.summary)
            self.tooltip_renderer.draw_simple_tooltip(
                self.screen, self.font_small, summary_clean,
                pygame.mouse.get_pos(), self.width, self.height
            )

        # Draw modal last (on top of everything)
        if self.system_prompt_modal.is_visible:
            system_prompt = self.controller.decision_maker.system_prompt
            self.system_prompt_modal.draw(
                self.screen, system_prompt, self.width, self.height
            )

        pygame.display.flip()

    def _draw_info_button(self) -> None:
        """Draw circular info button."""
        if self.info_button_hovered:
            bg_color = colors.HOVER
            border_color = colors.ACCENT
        else:
            bg_color = colors.PRIMARY
            border_color = colors.BORDER

        center = self.info_button_rect.center
        radius = self.info_button_rect.width // 2
        pygame.draw.circle(self.screen, bg_color, center, radius)
        pygame.draw.circle(self.screen, border_color, center, radius, 2)

        i_text = self.font_medium.render("i", True, colors.TEXT)
        i_rect = i_text.get_rect(center=center)
        self.screen.blit(i_text, i_rect)

    def run(self) -> None:
        """Main game loop."""
        try:
            while self.running:
                self.handle_events()
                self.update()
                self.draw()
                self.clock.tick(self.fps)
        finally:
            self.turn_executor.stop()
            pygame.quit()

"""Main game window with Pygame."""

import pygame
from typing import Optional

from ..game.game_controller import GameController
from ..models.enums import ResourceType
from ..utils.config import config
from . import colors
from .components import Button, Panel, draw_rounded_rect, draw_rounded_rect_border
from .resource_display import get_resource_emoji, format_resources_dict, GENERATOR_EMOJIS


class MainWindow:
    """Main game window."""

    def __init__(self, controller: GameController):
        pygame.init()

        self.controller = controller

        # Create maximized window
        self.width = config.get("ui.window_width", 1600)
        self.height = config.get("ui.window_height", 900)

        # Create window and maximize it
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("AI Nations: Strategic Resource Game")

        # Maximize the window (platform-specific)
        import ctypes
        try:
            # Windows
            hwnd = pygame.display.get_wm_info()['window']
            ctypes.windll.user32.ShowWindow(hwnd, 3)  # 3 = SW_MAXIMIZE
        except:
            pass  # Not on Windows or failed

        self.clock = pygame.time.Clock()
        self.fps = config.get("ui.fps", 60)

        # Fonts - use system font that supports emojis
        # Try to find a font that supports emojis
        emoji_font = self._get_emoji_font()

        self.font_small = pygame.font.SysFont(emoji_font, 18)
        self.font_medium = pygame.font.SysFont(emoji_font, 24)
        self.font_large = pygame.font.SysFont(emoji_font, 32)
        self.font_title = pygame.font.SysFont(emoji_font, 48)

        # Game state
        self.running = True
        self.auto_mode = False
        self.nations_scroll_offset = 0
        self.logs_scroll_offset = 0
        self.selected_log = None  # Currently selected log for detailed view
        self.detail_scroll_offset = 0  # Scroll offset for detail panel

        # Scrollbar dragging state
        self.dragging_scrollbar = None  # 'logs' or 'detail'
        self.drag_start_y = 0
        self.drag_start_offset = 0

        # Tooltip state
        self.tooltip_log = None
        self.tooltip_timer = 0
        self.tooltip_delay = 30  # frames (~0.5 seconds at 60fps)
        self.info_button_hovered = False

        # Modal state
        self.show_system_prompt_modal = False
        self.modal_scroll_offset = 0

        # Async turn execution
        from ..game.async_turn_executor import AsyncTurnExecutor
        self.turn_executor = AsyncTurnExecutor(self.controller)
        self.turn_executor.on_turn_complete = self._on_turn_complete
        self.turn_executor.start()

        # Load flag images
        self.flag_images = self._load_flag_images()

        # UI Components
        self._setup_ui()

    def _get_emoji_font(self) -> str:
        """Get a system font that supports emojis."""
        # List of fonts that typically support emojis on different platforms
        emoji_fonts = [
            'segoeuiemoji',  # Windows
            'seguiemj',      # Windows
            'segoe ui emoji', # Windows
            'arial unicode ms',  # Cross-platform
            'apple color emoji',  # macOS
            'noto color emoji',  # Linux
            'symbola',       # Linux
            'unifont',       # Linux
        ]

        available_fonts = pygame.font.get_fonts()

        # Try to find an emoji font
        for font in emoji_fonts:
            if font.lower().replace(' ', '') in [f.lower().replace(' ', '') for f in available_fonts]:
                return font

        # Fallback to common fonts
        fallback_fonts = ['arial', 'helvetica', 'verdana', 'tahoma']
        for font in fallback_fonts:
            if font in available_fonts:
                return font

        # Last resort - return None to use pygame default
        return None

    def _load_flag_images(self) -> dict:
        """Load flag images from assets/flags directory based on nations in game."""
        from pathlib import Path

        flags = {}
        project_root = Path(__file__).parent.parent.parent
        flags_dir = project_root / "assets" / "flags"

        # Load flags for all nations in the game
        for nation in self.controller.game_state.nations:
            flag_filename = f"{nation.code}.png"
            flag_path = flags_dir / flag_filename

            if flag_path.exists():
                try:
                    # Load and scale flag image
                    flag_img = pygame.image.load(str(flag_path))
                    # Scale to different sizes
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
        self.btn_auto = Button(
            button_spacing, button_y, button_width, button_height,
            "Auto: OFF",
            self._toggle_auto_mode,
            enabled=True
        )

        self.btn_next_turn = Button(
            button_spacing * 2 + button_width, button_y, button_width, button_height,
            "Next Turn",
            self._next_turn,
            enabled=True
        )

        # Info button in bottom right corner
        info_button_size = 40
        self.info_button_rect = pygame.Rect(
            self.width - info_button_size - button_spacing,
            button_y + (button_height - info_button_size) // 2,
            info_button_size,
            info_button_size
        )

        self.buttons = [self.btn_auto, self.btn_next_turn]

        # Responsive panels - calculate based on screen size
        panel_padding = 20
        nations_width = int(self.width * 0.35)  # 35% for nations list
        right_panel_width = self.width - nations_width - panel_padding * 3

        # Current Turn panel - smaller height (30% of available space)
        current_turn_height = int((self.height - button_height - panel_padding * 4) * 0.3)

        # Game Logs panel - larger height (70% of available space)
        logs_height = self.height - button_height - current_turn_height - panel_padding * 4

        self.panel_nations = Panel(
            panel_padding,
            panel_padding,
            nations_width,
            self.height - button_height - panel_padding * 3,
            "Nations"
        )

        # Dynamic panel title based on round number
        round_title = f"Round {self.controller.game_state.round_number}"
        self.panel_current = Panel(
            nations_width + panel_padding * 2,
            panel_padding,
            right_panel_width,
            current_turn_height,
            round_title
        )

        # If a log is selected, split the logs panel in half
        if self.selected_log:
            logs_panel_width = right_panel_width // 2 - panel_padding // 2
            detail_panel_width = right_panel_width // 2 - panel_padding // 2

            self.panel_logs = Panel(
                nations_width + panel_padding * 2,
                current_turn_height + panel_padding * 2,
                logs_panel_width,
                logs_height,
                "Game Logs"
            )

            self.panel_detail = Panel(
                nations_width + panel_padding * 2 + logs_panel_width + panel_padding,
                current_turn_height + panel_padding * 2,
                detail_panel_width,
                logs_height,
                "Log Details"
            )
        else:
            self.panel_logs = Panel(
                nations_width + panel_padding * 2,
                current_turn_height + panel_padding * 2,
                right_panel_width,
                logs_height,
                "Game Logs"
            )

    def _toggle_auto_mode(self) -> None:
        """Toggle auto mode."""
        self.auto_mode = not self.auto_mode
        self.btn_auto.text = f"Auto: {'ON' if self.auto_mode else 'OFF'}"

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
                if event.key == pygame.K_ESCAPE and self.show_system_prompt_modal:
                    self.show_system_prompt_modal = False
                    self.modal_scroll_offset = 0

            # Handle window resize
            if event.type == pygame.VIDEORESIZE:
                self.width = event.w
                self.height = event.h
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                self._setup_ui()  # Recalculate layout

            # Handle mouse clicks
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
                mouse_pos = pygame.mouse.get_pos()

                # If modal is open, handle modal interactions
                if self.show_system_prompt_modal:
                    modal_rect = self._get_modal_rect()
                    if not modal_rect.collidepoint(mouse_pos):
                        # Clicked outside modal (backdrop), close it
                        self.show_system_prompt_modal = False
                        self.modal_scroll_offset = 0
                    continue  # Don't process other clicks when modal is open

                # Check if clicked on info button
                if self.info_button_rect.collidepoint(mouse_pos):
                    self.show_system_prompt_modal = True
                    self.modal_scroll_offset = 0
                    continue

                # Check if clicked on scrollbar
                scrollbar_clicked = self._check_scrollbar_click(mouse_pos)
                if scrollbar_clicked:
                    self.dragging_scrollbar = scrollbar_clicked
                    self.drag_start_y = mouse_pos[1]
                    if scrollbar_clicked == 'logs':
                        self.drag_start_offset = self.logs_scroll_offset
                    elif scrollbar_clicked == 'detail':
                        self.drag_start_offset = self.detail_scroll_offset
                # Check if clicked on a log entry
                elif self.panel_logs.rect.collidepoint(mouse_pos):
                    clicked_log = self._get_log_at_position(mouse_pos)
                    if clicked_log:
                        if self.selected_log == clicked_log:
                            # Deselect if clicking the same log
                            self.selected_log = None
                            self.detail_scroll_offset = 0
                        else:
                            # Select the new log
                            self.selected_log = clicked_log
                            self.detail_scroll_offset = 0
                        self._setup_ui()  # Recalculate layout

            # Handle mouse button release
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging_scrollbar = None

            # Handle mouse motion for scrollbar dragging
            if event.type == pygame.MOUSEMOTION and self.dragging_scrollbar:
                mouse_pos = pygame.mouse.get_pos()
                self._handle_scrollbar_drag(mouse_pos)

            # Handle mouse wheel for scrolling
            if event.type == pygame.MOUSEWHEEL:
                mouse_pos = pygame.mouse.get_pos()

                # Modal scrolling
                if self.show_system_prompt_modal:
                    modal_rect = self._get_modal_rect()
                    if modal_rect.collidepoint(mouse_pos):
                        # Calculate max scroll
                        system_prompt = self.controller.decision_maker.system_prompt
                        line_height = 20
                        total_content_height = len(system_prompt.split('\n')) * line_height
                        content_height = modal_rect.height - 140  # Account for title, hint, and padding
                        max_scroll = max(0, total_content_height - content_height)

                        self.modal_scroll_offset -= event.y * 30
                        self.modal_scroll_offset = max(0, min(max_scroll, self.modal_scroll_offset))
                    continue

                # Nations panel scrolling
                if self.panel_nations.rect.collidepoint(mouse_pos):
                    # Calculate max scroll based on content height
                    item_height = 90
                    total_content_height = len(self.controller.game_state.nations) * item_height
                    visible_height = self.panel_nations.rect.height - 50
                    max_scroll = max(0, total_content_height - visible_height)

                    self.nations_scroll_offset -= event.y * 30
                    self.nations_scroll_offset = max(0, min(max_scroll, self.nations_scroll_offset))

                # Logs panel scrolling
                elif self.panel_logs.rect.collidepoint(mouse_pos):
                    # Calculate max scroll based on content height
                    line_height = 25
                    logs_count = len(self.controller.game_state.game_log.get_recent(50))
                    total_content_height = logs_count * line_height
                    visible_height = self.panel_logs.rect.height - 50
                    max_scroll = max(0, total_content_height - visible_height)

                    self.logs_scroll_offset -= event.y * 30
                    self.logs_scroll_offset = max(0, min(max_scroll, self.logs_scroll_offset))

                # Detail panel scrolling (if a log is selected)
                elif self.selected_log and hasattr(self, 'panel_detail') and self.panel_detail.rect.collidepoint(mouse_pos):
                    # Scroll the detail panel
                    self.detail_scroll_offset -= event.y * 30
                    self.detail_scroll_offset = max(0, self.detail_scroll_offset)

            # Handle button events
            for button in self.buttons:
                if button.handle_event(event):
                    break

    def update(self) -> None:
        """Update game state."""
        # Update button states
        is_busy = self.turn_executor.status.is_busy()
        self.btn_next_turn.enabled = not is_busy and not self.auto_mode

        # Auto mode processing
        if self.auto_mode and not is_busy:
            self._next_turn()

        # Update info button hover state
        mouse_pos = pygame.mouse.get_pos()
        self.info_button_hovered = self.info_button_rect.collidepoint(mouse_pos)

        # Update tooltip timer
        if self.panel_logs.rect.collidepoint(mouse_pos):
            hovered_log = self._get_log_at_position(mouse_pos)
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

        # Draw panels
        self.panel_nations.draw(self.screen, self.font_medium)
        self.panel_current.draw(self.screen, self.font_medium)
        self.panel_logs.draw(self.screen, self.font_medium)

        # Draw detail panel if a log is selected
        if self.selected_log and hasattr(self, 'panel_detail'):
            self.panel_detail.draw(self.screen, self.font_medium)

        # Draw content
        self._draw_nations()
        self._draw_current_turn()
        self._draw_inline_logs()

        # Draw log details if selected
        if self.selected_log and hasattr(self, 'panel_detail'):
            self._draw_log_details()

        # Draw buttons
        for button in self.buttons:
            button.draw(self.screen, self.font_medium)

        # Draw global resources in bottom bar
        self._draw_global_resources_bar()

        # Draw info button
        self._draw_info_button()

        # Draw tooltip for info button if hovered
        if self.info_button_hovered and not self.show_system_prompt_modal:
            self._draw_info_tooltip()

        # Draw tooltip for logs if applicable
        if self.tooltip_log and self.tooltip_timer >= self.tooltip_delay:
            self._draw_tooltip()

        # Draw modal last (on top of everything)
        if self.show_system_prompt_modal:
            self._draw_system_prompt_modal()

        pygame.display.flip()

    def _draw_nations(self) -> None:
        """Draw nations list with scrolling."""
        # Create clipping surface for scrolling
        clip_rect = pygame.Rect(
            self.panel_nations.rect.x + 5,
            self.panel_nations.rect.y + 40,
            self.panel_nations.rect.width - 10,
            self.panel_nations.rect.height - 45
        )

        # Reorder nations: current nation at top, then in turn order
        turn_order = self.controller.game_state.turn_order
        current_idx = self.controller.game_state.current_nation_index

        # Set clipping area to prevent overflow
        self.screen.set_clip(clip_rect)

        # Reorder turn_order to put current nation first
        ordered_nation_ids = turn_order[current_idx:] + turn_order[:current_idx]

        # Convert to actual nation objects
        ordered_nations = [self.controller.game_state.get_nation(nid) for nid in ordered_nation_ids]
        ordered_nations = [n for n in ordered_nations if n is not None]  # Filter out None

        # Draw nations with scroll offset
        y_offset = 50 - self.nations_scroll_offset
        item_height = 90

        for nation in ordered_nations:
            x = self.panel_nations.rect.x + 10
            y = self.panel_nations.rect.y + y_offset

            # Skip if outside visible area
            if y + item_height < clip_rect.top or y > clip_rect.bottom:
                y_offset += item_height
                continue

            # Draw flag image
            flag_img = self.flag_images[nation.name]['medium']
            self.screen.blit(flag_img, (x, y + 2))
            text_x = x + 40
            
            header = f"{nation.name} - Era {nation.era.value}"
            text = self.font_small.render(header, True, colors.TEXT)
            self.screen.blit(text, (text_x, y + 3))

            # Generators - show as emojis grouped by type
            y += 25
            generator_emojis = self._get_generator_emojis(nation)
            if generator_emojis:
                gen_text = f"Gen: {generator_emojis}"
                text = self.font_small.render(gen_text, True, colors.TEXT_SECONDARY)
                self.screen.blit(text, (x + 20, y))

            # Resources (show all with emojis, with spacing for large numbers)
            y += 20
            res_x = x + 100
            for rt in ResourceType:
                emoji = get_resource_emoji(rt)
                amount = nation.inventory.get(rt)
                res_text = f"{emoji}{amount}"
                text = self.font_small.render(res_text, True, colors.TEXT_SECONDARY)
                self.screen.blit(text, (res_x, y))
                res_x += 100  # Fixed spacing between resources (accommodates up to 6 digits)

            y_offset += item_height

        # Reset clipping
        self.screen.set_clip(None)

    def _draw_current_turn(self) -> None:
        """Draw current turn info."""
        current_nation = self.controller.game_state.get_current_nation()
        if not current_nation:
            return

        x = self.panel_current.rect.x + 10
        y = self.panel_current.rect.y + 50

        # Current Turn label with nation
        turn_text = "Current Turn:"
        turn_surf = self.font_medium.render(turn_text, True, colors.TEXT)
        self.screen.blit(turn_surf, (x, y))

        # Nation flag
        turn_width = self.font_medium.size(turn_text)[0]
        flag_x = x + turn_width + 15
        flag_img = self.flag_images[current_nation.name]['medium']
        self.screen.blit(flag_img, (flag_x, y + 2))

        # Nation name
        nation_x = flag_x + 40
        nation_text = current_nation.name
        nation_surf = self.font_medium.render(nation_text, True, colors.TEXT)
        self.screen.blit(nation_surf, (nation_x, y))

        # 👉 Status text on the SAME line
        status_x = nation_x + self.font_medium.size(nation_text)[0] + 10

        if self.turn_executor.status.is_busy():
            status_text = self.turn_executor.status.get_action()
            if status_text:
                status_display = f"- {status_text}"

                max_width = (
                    self.panel_current.rect.width
                    - (status_x - self.panel_current.rect.x)
                    - 10
                )

                while self.font_small.size(status_display)[0] > max_width and len(status_display) > 10:
                    status_display = status_display[:-4] + "..."

                status_surf = self.font_small.render(status_display, True, colors.WARNING)
                self.screen.blit(status_surf, (status_x, y + 4))

        # Era on second line
        y += 35
        era_text = f"Era: {current_nation.era.name}"
        era_surf = self.font_small.render(era_text, True, colors.ACCENT)
        self.screen.blit(era_surf, (x, y))

        # Error (below)
        error = self.turn_executor.status.get_error()
        if error:
            y += 25
            error_surf = self.font_small.render(f"Error: {error[:50]}", True, colors.ERROR)
            self.screen.blit(error_surf, (x, y))


    def _draw_global_resources_bar(self) -> None:
        """Draw global resources next to buttons at bottom of screen."""
        # Calculate totals
        totals = {rt: 0 for rt in ResourceType}
        for nation in self.controller.game_state.nations:
            for rt in ResourceType:
                totals[rt] += nation.inventory.get(rt)

        # Start position after buttons
        button_spacing = 20
        button_width = 150
        x = button_spacing * 3 + button_width * 2 + 40
        y = self.height - 60

        # Draw "Global Resources" label
        label = self.font_small.render("Global Resources:", True, colors.TEXT_SECONDARY)
        self.screen.blit(label, (x, y - 5))

        # Draw each resource with emoji + number
        for rt in ResourceType:
            total = totals[rt]
            emoji = get_resource_emoji(rt)
            resource_text = f"{emoji}{total}"
            text = self.font_small.render(resource_text, True, colors.TEXT)
            self.screen.blit(text, (x, y + 15))
            x += 100  # Fixed spacing between resources

    def _get_log_at_position(self, mouse_pos: tuple) -> Optional[any]:
        """Get the log entry at the given mouse position."""
        logs = self.controller.game_state.game_log.get_recent(50)
        logs.reverse()  # Newest first

        line_height = 25
        y = self.panel_logs.rect.y + 50 - self.logs_scroll_offset

        for log in logs:
            # Check if mouse is within this log's bounds
            if y <= mouse_pos[1] < y + line_height:
                if self.panel_logs.rect.x <= mouse_pos[0] <= self.panel_logs.rect.x + self.panel_logs.rect.width:
                    return log
            y += line_height

        return None

    def _check_scrollbar_click(self, mouse_pos: tuple) -> Optional[str]:
        """Check if mouse click is on a scrollbar. Returns panel name or None."""
        # Check logs scrollbar
        logs_count = len(self.controller.game_state.game_log.get_recent(50))
        logs_content = logs_count * 25
        logs_visible = self.panel_logs.rect.height - 50
        if logs_content > logs_visible:
            scrollbar_rect = self._get_scrollbar_rect(self.panel_logs.rect)
            if scrollbar_rect.collidepoint(mouse_pos):
                return 'logs'

        # Check detail scrollbar
        if self.selected_log and hasattr(self, 'panel_detail'):
            scrollbar_rect = self._get_scrollbar_rect(self.panel_detail.rect)
            if scrollbar_rect.collidepoint(mouse_pos):
                return 'detail'

        return None

    def _get_scrollbar_rect(self, panel_rect: pygame.Rect) -> pygame.Rect:
        """Get the rectangle for a scrollbar."""
        scrollbar_width = 8
        scrollbar_x = panel_rect.x + panel_rect.width - scrollbar_width - 5
        scrollbar_y = panel_rect.y + 45
        scrollbar_height = panel_rect.height - 50
        return pygame.Rect(scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height)

    def _handle_scrollbar_drag(self, mouse_pos: tuple) -> None:
        """Handle scrollbar dragging based on mouse movement delta."""
        if self.dragging_scrollbar == 'logs':
            scrollbar_rect = self._get_scrollbar_rect(self.panel_logs.rect)

            # Calculate max scroll
            logs_count = len(self.controller.game_state.game_log.get_recent(50))
            total_content = logs_count * 25
            visible_height = self.panel_logs.rect.height - 50
            max_scroll = max(0, total_content - visible_height)

            # Calculate how much the mouse moved
            mouse_delta = mouse_pos[1] - self.drag_start_y

            # Convert mouse movement to scroll movement
            # The ratio is: how much scrollbar area corresponds to how much content
            scrollbar_height = scrollbar_rect.height
            thumb_height = max(20, int((visible_height / total_content) * scrollbar_height))
            scrollable_area = scrollbar_height - thumb_height

            if scrollable_area > 0:
                scroll_delta = (mouse_delta / scrollable_area) * max_scroll
                new_offset = self.drag_start_offset + scroll_delta
                self.logs_scroll_offset = int(max(0, min(max_scroll, new_offset)))

        elif self.dragging_scrollbar == 'detail':
            scrollbar_rect = self._get_scrollbar_rect(self.panel_detail.rect)

            # For detail panel, we need to calculate actual content height
            # This is a rough estimate - in a better implementation we'd track actual content height
            visible_height = self.panel_detail.rect.height - 50
            estimated_content = visible_height * 3
            max_scroll = max(0, estimated_content)

            # Calculate how much the mouse moved
            mouse_delta = mouse_pos[1] - self.drag_start_y

            # Convert mouse movement to scroll movement
            scrollbar_height = scrollbar_rect.height
            thumb_height = max(20, int((visible_height / estimated_content) * scrollbar_height))
            scrollable_area = scrollbar_height - thumb_height

            if scrollable_area > 0:
                scroll_delta = (mouse_delta / scrollable_area) * max_scroll
                new_offset = self.drag_start_offset + scroll_delta
                self.detail_scroll_offset = int(max(0, min(max_scroll, new_offset)))

    def _draw_scrollbar(self, panel_rect: pygame.Rect, scroll_offset: int,
                       content_height: int, visible_height: int) -> None:
        """Draw a scrollbar for a panel."""
        if content_height <= visible_height:
            return  # No scrollbar needed

        # Scrollbar dimensions
        scrollbar_width = 8
        scrollbar_x = panel_rect.x + panel_rect.width - scrollbar_width - 5
        scrollbar_y = panel_rect.y + 45
        scrollbar_height = panel_rect.height - 50

        # Draw scrollbar background
        bg_rect = pygame.Rect(scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height)
        draw_rounded_rect(self.screen, colors.SECONDARY, bg_rect, border_radius=6)

        # Calculate thumb size and position
        thumb_height = max(20, int((visible_height / content_height) * scrollbar_height))
        max_scroll = content_height - visible_height
        thumb_y = scrollbar_y + int((scroll_offset / max_scroll) * (scrollbar_height - thumb_height)) if max_scroll > 0 else scrollbar_y

        # Draw scrollbar thumb
        thumb_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)
        draw_rounded_rect(self.screen, colors.TEXT_SECONDARY, thumb_rect, border_radius=6)

    def _draw_inline_logs(self) -> None:
        """Draw game logs inline in the panel with scrolling."""
        logs = self.controller.game_state.game_log.get_recent(50)
        logs.reverse()  # Newest first

        x = self.panel_logs.rect.x + 10
        line_height = 25

        # Create clipping area (leave space for scrollbar)
        clip_rect = pygame.Rect(
            self.panel_logs.rect.x + 5,
            self.panel_logs.rect.y + 45,
            self.panel_logs.rect.width - 25,  # Leave space for scrollbar
            self.panel_logs.rect.height - 50
        )
        self.screen.set_clip(clip_rect)

        # Start y position with scroll offset
        y = self.panel_logs.rect.y + 50 - self.logs_scroll_offset

        for log in logs:
            # Skip if above visible area
            if y + line_height < clip_rect.top:
                y += line_height
                continue

            # Stop if below visible area
            if y > clip_rect.bottom:
                break

            # Highlight selected log
            if self.selected_log == log:
                highlight_rect = pygame.Rect(
                    self.panel_logs.rect.x + 5,
                    y - 2,
                    self.panel_logs.rect.width - 10,
                    line_height
                )
                draw_rounded_rect_border(self.screen, colors.ACCENT, highlight_rect, width=2, border_radius=5)

            # Round.Turn format (e.g., R1.T1, R1.T2, R2.T1)
            round_turn_text = f"R{log.round_number}.T{log.turn_number}"
            text_surf = self.font_small.render(round_turn_text, True, colors.WARNING)
            self.screen.blit(text_surf, (x, y))

            # Flags
            flag_x = x + 45
            if log.nations_involved and self.flag_images:
                for nation_id in log.nations_involved[:2]:
                    nation = self.controller.game_state.get_nation(nation_id)
                    if nation and nation.name in self.flag_images:
                        flag_img = self.flag_images[nation.name]['small']
                        self.screen.blit(flag_img, (flag_x, y + 2))
                        flag_x += 28

            # Summary (truncated to fit)
            import re
            summary_clean = re.sub(r'[\U0001F1E6-\U0001F1FF]{2}', '', log.summary)
            max_summary_width = self.panel_logs.rect.width - (flag_x - x) - 20

            # Truncate summary to fit
            summary_text = summary_clean
            while self.font_small.size(summary_text)[0] > max_summary_width and len(summary_text) > 10:
                summary_text = summary_text[:-4] + "..."

            text_surf = self.font_small.render(summary_text, True, colors.TEXT)
            self.screen.blit(text_surf, (flag_x + 5, y))

            y += line_height

        self.screen.set_clip(None)

        # Draw scrollbar
        logs_count = len(logs)
        total_content_height = logs_count * line_height
        visible_height = self.panel_logs.rect.height - 50
        self._draw_scrollbar(self.panel_logs.rect, self.logs_scroll_offset,
                           total_content_height, visible_height)

    def _get_resource_color(self, resource_type: ResourceType) -> tuple:
        """Get color for a resource type."""
        color_map = {
            ResourceType.GOLD: colors.GOLD_COLOR,
            ResourceType.WOOD: colors.WOOD_COLOR,
            ResourceType.STONE: colors.STONE_COLOR,
            ResourceType.FOOD: colors.FOOD_COLOR,
            ResourceType.TECHNOLOGY: colors.TECHNOLOGY_COLOR,
            ResourceType.INFORMATION: colors.INFORMATION_COLOR,
        }
        return color_map.get(resource_type, colors.TEXT)


    def _get_generator_emojis(self, nation) -> str:
        """Get emoji representation of generators grouped by type."""
        from ..models.enums import GeneratorType

        # Count generators by type
        gen_counts = {}
        for generator in nation.generators:
            gen_type = generator.generator_type
            gen_counts[gen_type] = gen_counts.get(gen_type, 0) + 1

        # Build emoji string using shared emoji map
        emoji_parts = []
        for gen_type in GeneratorType:
            count = gen_counts.get(gen_type, 0)
            if count > 0:
                emoji = GENERATOR_EMOJIS.get(gen_type, "❓")
                emoji_parts.append(emoji * count)

        return " ".join(emoji_parts)

    def _draw_log_details(self) -> None:
        """Draw detailed view of selected log entry."""
        if not self.selected_log or not hasattr(self, 'panel_detail'):
            return

        log = self.selected_log
        x = self.panel_detail.rect.x + 10
        y_start = self.panel_detail.rect.y + 50
        line_height = 20
        small_line_height = 18

        # Create clipping area (leave space for scrollbar)
        clip_rect = pygame.Rect(
            self.panel_detail.rect.x + 10,  # Align with text position
            self.panel_detail.rect.y + 45,
            self.panel_detail.rect.width - 30,  # Leave space for scrollbar and margins
            self.panel_detail.rect.height - 50
        )
        self.screen.set_clip(clip_rect)

        y = y_start - self.detail_scroll_offset

        # Log type and turn
        header = f"{log.log_type.value} - Turn {log.turn_number}"
        text_surf = self.font_small.render(header, True, colors.WARNING)
        if y >= clip_rect.top and y < clip_rect.bottom:
            self.screen.blit(text_surf, (x, y))
        y += line_height + 5

        # Summary (wrap text instead of truncating)
        max_summary_width = clip_rect.width - 10  # Leave margin
        y = self._draw_wrapped_text(
            log.summary,
            x,
            y,
            max_summary_width,
            clip_rect,
            line_height,
            colors.TEXT
        )
        y += 10  # Extra spacing after summary

        # Details section
        if log.details:
            # Check if there's actual content to display
            has_content = (
                'trade_offers' in log.details or
                'offer' in log.details or
                'counter_offer' in log.details or
                'generated' in log.details or
                'failure_reason' in log.details
            )

            if has_content:
                detail_label = self.font_small.render("Details:", True, colors.ACCENT)
                if y >= clip_rect.top and y < clip_rect.bottom:
                    self.screen.blit(detail_label, (x, y))
                y += line_height

            # Format details based on log type
            if 'trade_offers' in log.details:
                # Display trade offers from planning turn actions
                for trade_offer in log.details['trade_offers']:
                    target_id = trade_offer.get('target_nation_id')
                    if target_id is not None:
                        target_nation = self.controller.game_state.get_nation(target_id)
                        if target_nation:
                            target_text = f"Trading with {target_nation.name}:"
                            text_surf = self.font_small.render(target_text, True, colors.TEXT_SECONDARY)
                            if y >= clip_rect.top and y < clip_rect.bottom:
                                self.screen.blit(text_surf, (x + 10, y))
                            y += small_line_height

                    y = self._draw_trade_offer_details(trade_offer, x + 20, y, clip_rect, small_line_height)
                    y += small_line_height

            if 'offer' in log.details:
                # Trade response offer
                offer = log.details['offer']
                y = self._draw_trade_offer_details(offer, x + 10, y, clip_rect, small_line_height)
            elif 'counter_offer' in log.details:
                offer = log.details['counter_offer']
                text_surf = self.font_small.render("Counter-offer:", True, colors.TEXT_SECONDARY)
                if y >= clip_rect.top and y < clip_rect.bottom:
                    self.screen.blit(text_surf, (x + 10, y))
                y += small_line_height
                y = self._draw_trade_offer_details(offer, x + 20, y, clip_rect, small_line_height)
            elif 'generated' in log.details:
                gen_dict = log.details['generated']
                gen_text = format_resources_dict(gen_dict)
                text_surf = self.font_small.render(f"Resources: {gen_text}", True, colors.TEXT_SECONDARY)
                if y >= clip_rect.top and y < clip_rect.bottom:
                    self.screen.blit(text_surf, (x + 10, y))
                y += small_line_height

            # Display failure reason for failed builds
            if 'failure_reason' in log.details:
                failure_text = f"Reason: {log.details['failure_reason']}"
                y = self._draw_wrapped_text(
                    failure_text,
                    x + 10,
                    y,
                    clip_rect.width - 20,
                    clip_rect,
                    small_line_height,
                    colors.ERROR
                )

            y += 10

        # AI Decision section
        if log.ai_decisions:
            for decision in log.ai_decisions:
                nation = self.controller.game_state.get_nation(decision.nation_id)
                if nation:
                    ai_label = self.font_small.render(f"AI Decision - {nation.name}:", True, colors.ACCENT)
                    if y >= clip_rect.top and y < clip_rect.bottom:
                        self.screen.blit(ai_label, (x, y))
                    y += line_height + 5

                    # Prompt section
                    prompt_label = self.font_small.render("Prompt:", True, colors.TEXT_SECONDARY)
                    if y >= clip_rect.top and y < clip_rect.bottom:
                        self.screen.blit(prompt_label, (x + 10, y))
                    y += small_line_height

                    # Wrap prompt text
                    y = self._draw_wrapped_text(
                        decision.prompt,
                        x + 20,
                        y,
                        self.panel_detail.rect.width - 40,
                        clip_rect,
                        small_line_height,
                        colors.TEXT_SECONDARY
                    )
                    y += 10

                    # Response section
                    response_label = self.font_small.render("Response:", True, colors.TEXT_SECONDARY)
                    if y >= clip_rect.top and y < clip_rect.bottom:
                        self.screen.blit(response_label, (x + 10, y))
                    y += small_line_height

                    # Wrap response text
                    y = self._draw_wrapped_text(
                        decision.response,
                        x + 20,
                        y,
                        self.panel_detail.rect.width - 40,
                        clip_rect,
                        small_line_height,
                        colors.TEXT_SECONDARY
                    )
                    y += 15

        self.screen.set_clip(None)

        # Calculate total content height and draw scrollbar
        total_content_height = y - y_start + self.detail_scroll_offset
        visible_height = self.panel_detail.rect.height - 50
        self._draw_scrollbar(self.panel_detail.rect, self.detail_scroll_offset,
                           total_content_height, visible_height)

    def _draw_trade_offer_details(self, offer: dict, x: int, y: int, clip_rect: pygame.Rect, line_height: int) -> int:
        """Draw trade offer details and return new y position."""
        # Offering
        if 'offering' in offer and offer['offering']:
            offering_text = "Offering: " + format_resources_dict(offer['offering'])
            text_surf = self.font_small.render(offering_text, True, colors.TEXT_SECONDARY)
            if y >= clip_rect.top and y < clip_rect.bottom:
                self.screen.blit(text_surf, (x, y))
            y += line_height

        # Requesting
        if 'requesting' in offer and offer['requesting']:
            requesting_text = "Requesting: " + format_resources_dict(offer['requesting'])
            text_surf = self.font_small.render(requesting_text, True, colors.TEXT_SECONDARY)
            if y >= clip_rect.top and y < clip_rect.bottom:
                self.screen.blit(text_surf, (x, y))
            y += line_height

        return y

    def _draw_wrapped_text(self, text: str, x: int, y: int, max_width: int,
                          clip_rect: pygame.Rect, line_height: int, color: tuple) -> int:
        """Draw text with word wrapping and return new y position. Beautifies JSON if found."""
        import json

        def wrap_and_draw_line(line_text: str, start_y: int, indent_pixels: int = 0) -> int:
            """Wrap and draw a single line of text with indentation, returns new y position."""
            current_y = start_y
            actual_x = x + indent_pixels
            available_width = max_width - indent_pixels

            if available_width <= 0:
                available_width = max_width
                actual_x = x

            while len(line_text) > 0:
                if self.font_small.size(line_text)[0] <= available_width:
                    # Whole line fits
                    if current_y >= clip_rect.top and current_y < clip_rect.bottom:
                        text_surf = self.font_small.render(line_text, True, color)
                        self.screen.blit(text_surf, (actual_x, current_y))
                    current_y += line_height
                    break
                else:
                    # Line doesn't fit, need to wrap
                    # Find best split point (prefer spaces)
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

                    # Try to find a space near the split point to avoid breaking words
                    part = line_text[:best_split]
                    remaining = line_text[best_split:]

                    # Look back for a space to break on (but not too far)
                    space_idx = part.rfind(' ')
                    if space_idx > best_split * 0.7:  # Only if space is in last 30%
                        part = line_text[:space_idx]
                        remaining = line_text[space_idx:].lstrip()

                    # Draw the part that fits
                    if current_y >= clip_rect.top and current_y < clip_rect.bottom:
                        text_surf = self.font_small.render(part, True, color)
                        self.screen.blit(text_surf, (actual_x, current_y))
                    current_y += line_height
                    line_text = remaining

                    # For continuation lines, keep the same indentation
                    actual_x = x + indent_pixels

            return current_y

        # Try to parse the entire text as JSON first
        try:
            json_obj = json.loads(text)
            # Successfully parsed as pure JSON, beautify it
            beautified = json.dumps(json_obj, indent=2)

            for line in beautified.split('\n'):
                # Calculate indentation in pixels (2 spaces = ~10 pixels)
                stripped = line.lstrip()
                indent_chars = len(line) - len(stripped)
                indent_pixels = indent_chars * 5  # ~5 pixels per space

                y = wrap_and_draw_line(stripped, y, indent_pixels)
            return y
        except (json.JSONDecodeError, ValueError, TypeError):
            # Not pure JSON, check if it contains embedded JSON
            pass

        # Look for embedded JSON objects/arrays with nested structures
        def find_json_blocks(text_str: str):
            """Find JSON blocks in text, supporting nested structures."""
            blocks = []
            i = 0
            while i < len(text_str):
                if text_str[i] in '{[':
                    # Found potential JSON start
                    start_char = text_str[i]
                    end_char = '}' if start_char == '{' else ']'
                    depth = 1
                    j = i + 1
                    in_string = False
                    escape_next = False

                    while j < len(text_str) and depth > 0:
                        char = text_str[j]

                        if escape_next:
                            escape_next = False
                        elif char == '\\' and in_string:
                            escape_next = True
                        elif char == '"':
                            in_string = not in_string
                        elif not in_string:
                            if char == start_char:
                                depth += 1
                            elif char == end_char:
                                depth -= 1

                        j += 1

                    if depth == 0:
                        # Found complete JSON block
                        json_str = text_str[i:j]
                        try:
                            # Verify it's valid JSON
                            json.loads(json_str)
                            blocks.append((i, j, json_str))
                            i = j
                            continue
                        except:
                            pass

                i += 1

            return blocks

        json_blocks = find_json_blocks(text)

        if json_blocks:
            # Text contains embedded JSON, process in parts
            last_pos = 0
            for start, end, json_str in json_blocks:
                # Draw text before JSON
                if start > last_pos:
                    plain_text = text[last_pos:start]
                    for line in plain_text.split('\n'):
                        y = wrap_and_draw_line(line, y, 0)

                # Draw beautified JSON
                try:
                    json_obj = json.loads(json_str)
                    beautified = json.dumps(json_obj, indent=2)
                    for line in beautified.split('\n'):
                        # Calculate indentation
                        stripped = line.lstrip()
                        indent_chars = len(line) - len(stripped)
                        indent_pixels = indent_chars * 5
                        y = wrap_and_draw_line(stripped, y, indent_pixels)
                except:
                    # If parsing fails, just draw as text
                    y = wrap_and_draw_line(json_str, y, 0)

                last_pos = end

            # Draw remaining text after last JSON
            if last_pos < len(text):
                remaining_text = text[last_pos:]
                for line in remaining_text.split('\n'):
                    y = wrap_and_draw_line(line, y, 0)

            return y

        # No JSON found, draw as regular text with newline support
        for line in text.split('\n'):
            y = wrap_and_draw_line(line, y, 0)

        return y

    def _draw_tooltip(self) -> None:
        """Draw tooltip for truncated log text."""
        if not self.tooltip_log:
            return

        import re
        mouse_pos = pygame.mouse.get_pos()

        # Get full summary text
        summary_clean = re.sub(r'[\U0001F1E6-\U0001F1FF]{2}', '', self.tooltip_log.summary)

        # Calculate tooltip size
        padding = 10
        text_surf = self.font_small.render(summary_clean, True, colors.TEXT)
        tooltip_width = text_surf.get_width() + padding * 2
        tooltip_height = text_surf.get_height() + padding * 2

        # Position tooltip near mouse, but keep it on screen
        tooltip_x = mouse_pos[0] + 15
        tooltip_y = mouse_pos[1] + 15

        # Keep tooltip on screen
        if tooltip_x + tooltip_width > self.width:
            tooltip_x = mouse_pos[0] - tooltip_width - 5
        if tooltip_y + tooltip_height > self.height:
            tooltip_y = mouse_pos[1] - tooltip_height - 5

        # Draw tooltip background
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        draw_rounded_rect(self.screen, colors.SECONDARY, tooltip_rect, border_radius=8)
        draw_rounded_rect_border(self.screen, colors.ACCENT, tooltip_rect, width=2, border_radius=8)

        # Draw tooltip text
        self.screen.blit(text_surf, (tooltip_x + padding, tooltip_y + padding))

    def _draw_info_button(self) -> None:
        """Draw circular info button."""
        # Button colors based on hover state
        if self.info_button_hovered:
            bg_color = colors.HOVER
            border_color = colors.ACCENT
        else:
            bg_color = colors.PRIMARY
            border_color = colors.BORDER

        # Draw circle
        center = self.info_button_rect.center
        radius = self.info_button_rect.width // 2
        pygame.draw.circle(self.screen, bg_color, center, radius)
        pygame.draw.circle(self.screen, border_color, center, radius, 2)

        # Draw "i" text
        i_text = self.font_medium.render("i", True, colors.TEXT)
        i_rect = i_text.get_rect(center=center)
        self.screen.blit(i_text, i_rect)

    def _draw_info_tooltip(self) -> None:
        """Draw tooltip for info button."""
        # Create tooltip
        padding = 10
        text_surf = self.font_small.render("System Prompt", True, colors.TEXT)
        tooltip_width = text_surf.get_width() + padding * 2
        tooltip_height = text_surf.get_height() + padding * 2

        # Position above the button
        tooltip_x = self.info_button_rect.centerx - tooltip_width // 2
        tooltip_y = self.info_button_rect.top - tooltip_height - 10

        # Keep on screen
        if tooltip_x < 0:
            tooltip_x = 0
        if tooltip_x + tooltip_width > self.width:
            tooltip_x = self.width - tooltip_width

        # Draw tooltip
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        draw_rounded_rect(self.screen, colors.SECONDARY, tooltip_rect, border_radius=8)
        draw_rounded_rect_border(self.screen, colors.ACCENT, tooltip_rect, width=2, border_radius=8)
        self.screen.blit(text_surf, (tooltip_x + padding, tooltip_y + padding))

    def _get_modal_rect(self) -> pygame.Rect:
        """Get the modal rectangle."""
        modal_width = min(800, self.width - 100)
        modal_height = min(600, self.height - 100)
        modal_x = (self.width - modal_width) // 2
        modal_y = (self.height - modal_height) // 2
        return pygame.Rect(modal_x, modal_y, modal_width, modal_height)

    def _draw_system_prompt_modal(self) -> None:
        """Draw modal showing the system prompt."""
        # Draw backdrop
        backdrop = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, 180))  # Semi-transparent black
        self.screen.blit(backdrop, (0, 0))

        # Get modal rect
        modal_rect = self._get_modal_rect()

        # Draw modal background
        draw_rounded_rect(self.screen, colors.SECONDARY, modal_rect, border_radius=15)
        draw_rounded_rect_border(self.screen, colors.ACCENT, modal_rect, width=3, border_radius=15)

        # Draw title
        title_text = self.font_large.render("System Prompt", True, colors.ACCENT)
        title_rect = title_text.get_rect(centerx=modal_rect.centerx, top=modal_rect.top + 20)
        self.screen.blit(title_text, title_rect)

        # Draw close hint
        hint_text = self.font_small.render("Press ESC or click outside to close", True, colors.TEXT_SECONDARY)
        hint_rect = hint_text.get_rect(centerx=modal_rect.centerx, top=title_rect.bottom + 5)
        self.screen.blit(hint_text, hint_rect)

        # Create scrollable content area
        content_y = hint_rect.bottom + 20
        content_height = modal_rect.bottom - content_y - 20
        content_rect = pygame.Rect(
            modal_rect.left + 20,
            content_y,
            modal_rect.width - 40,
            content_height
        )

        # Set clipping for content area
        self.screen.set_clip(content_rect)

        # Get system prompt
        system_prompt = self.controller.decision_maker.system_prompt

        # Draw system prompt text with wrapping
        y = content_y - self.modal_scroll_offset
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
                            self.screen.blit(text_surf, (content_rect.left + 10, y))
                        y += line_height
                        current_line = word

                # Draw remaining line
                if current_line and y >= content_rect.top - line_height and y < content_rect.bottom:
                    text_surf = self.font_small.render(current_line, True, colors.TEXT)
                    self.screen.blit(text_surf, (content_rect.left + 10, y))
                y += line_height
            else:
                # Empty line
                y += line_height // 2

        # Reset clipping
        self.screen.set_clip(None)

        # Draw scrollbar if needed
        total_content_height = len(system_prompt.split('\n')) * line_height
        if total_content_height > content_height:
            self._draw_modal_scrollbar(modal_rect, content_rect, total_content_height, content_height)

    def _draw_modal_scrollbar(self, modal_rect: pygame.Rect, content_rect: pygame.Rect,
                             total_height: int, visible_height: int) -> None:
        """Draw scrollbar for modal."""
        scrollbar_width = 8
        scrollbar_x = modal_rect.right - scrollbar_width - 15
        scrollbar_y = content_rect.top
        scrollbar_height = content_rect.height

        # Draw scrollbar track
        track_rect = pygame.Rect(scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height)
        draw_rounded_rect(self.screen, colors.BORDER, track_rect, border_radius=4)

        # Calculate thumb size and position
        thumb_height = max(20, int((visible_height / total_height) * scrollbar_height))
        max_scroll = total_height - visible_height
        if max_scroll > 0:
            thumb_y = scrollbar_y + int((self.modal_scroll_offset / max_scroll) * (scrollbar_height - thumb_height))
        else:
            thumb_y = scrollbar_y

        # Draw thumb
        thumb_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)
        draw_rounded_rect(self.screen, colors.ACCENT, thumb_rect, border_radius=4)

    def run(self) -> None:
        """Main game loop."""
        try:
            while self.running:
                self.handle_events()
                self.update()
                self.draw()
                self.clock.tick(self.fps)
        finally:
            # Clean up async executor
            self.turn_executor.stop()
            pygame.quit()

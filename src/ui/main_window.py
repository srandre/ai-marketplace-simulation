"""Main game window with Pygame."""

import pygame

from ..game.game_controller import GameController
from ..models.enums import ResourceType
from ..utils.config import config
from . import colors
from .components import Button, Panel


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

        self.panel_current = Panel(
            nations_width + panel_padding * 2,
            panel_padding,
            right_panel_width,
            current_turn_height,
            "Current Turn"
        )

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

            # Handle window resize
            if event.type == pygame.VIDEORESIZE:
                self.width = event.w
                self.height = event.h
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                self._setup_ui()  # Recalculate layout

            # Handle mouse wheel for scrolling
            if event.type == pygame.MOUSEWHEEL:
                mouse_pos = pygame.mouse.get_pos()

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

    def draw(self) -> None:
        """Draw the game window."""
        self.screen.fill(colors.BACKGROUND)

        # Draw panels
        self.panel_nations.draw(self.screen, self.font_medium)
        self.panel_current.draw(self.screen, self.font_medium)
        self.panel_logs.draw(self.screen, self.font_medium)

        # Draw content
        self._draw_nations()
        self._draw_current_turn()
        self._draw_inline_logs()

        # Draw buttons
        for button in self.buttons:
            button.draw(self.screen, self.font_medium)

        # Draw global resources in bottom bar
        self._draw_global_resources_bar()

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
                emoji = self._get_resource_emoji(rt)
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

        # Turn number
        turn_text = f"Turn {self.controller.game_state.turn_number}:"
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

        # Draw each resource with emoji + number
        for rt in ResourceType:
            total = totals[rt]
            emoji = self._get_resource_emoji(rt)
            resource_text = f"{emoji}{total}"
            text = self.font_small.render(resource_text, True, colors.TEXT)
            self.screen.blit(text, (x, y + 15))
            x += 100  # Fixed spacing between resources

    def _draw_inline_logs(self) -> None:
        """Draw game logs inline in the panel with scrolling."""
        logs = self.controller.game_state.game_log.get_recent(50)
        logs.reverse()  # Newest first

        x = self.panel_logs.rect.x + 10
        line_height = 25

        # Create clipping area
        clip_rect = pygame.Rect(
            self.panel_logs.rect.x + 5,
            self.panel_logs.rect.y + 45,
            self.panel_logs.rect.width - 10,
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

            # Turn number
            turn_text = f"T{log.turn_number}"
            text_surf = self.font_small.render(turn_text, True, colors.WARNING)
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

    def _get_resource_emoji(self, resource_type: ResourceType) -> str:
        """Get emoji for a resource type."""
        emoji_map = {
            ResourceType.GOLD: "💰",
            ResourceType.WOOD: "🪵",
            ResourceType.STONE: "🪨",
            ResourceType.FOOD: "🌾",
            ResourceType.TECHNOLOGY: "⚙️",
            ResourceType.INFORMATION: "💾",
        }
        return emoji_map.get(resource_type, "❓")

    def _get_generator_emojis(self, nation) -> str:
        """Get emoji representation of generators grouped by type."""
        from ..models.enums import GeneratorType

        # Map generator types to emojis
        generator_emoji_map = {
            GeneratorType.LUMBER_CAMP: "🪵",
            GeneratorType.QUARRY: "🪨",
            GeneratorType.FARM: "🌾",
            GeneratorType.MINE: "💰",
            GeneratorType.FACTORY: "⚙️",
            GeneratorType.DATACENTER: "💾",
        }

        # Count generators by type
        gen_counts = {}
        for generator in nation.generators:
            gen_type = generator.generator_type
            gen_counts[gen_type] = gen_counts.get(gen_type, 0) + 1

        # Build emoji string
        emoji_parts = []
        for gen_type in GeneratorType:
            count = gen_counts.get(gen_type, 0)
            if count > 0:
                emoji = generator_emoji_map.get(gen_type, "❓")
                emoji_parts.append(emoji * count)

        return " ".join(emoji_parts)

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

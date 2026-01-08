"""Main game window with Pygame."""

import pygame

from ..game.game_controller import GameController
from ..models.enums import ResourceType
from ..utils.config import config
from . import colors
from .components import Button, Panel
from .log_viewer import LogViewer


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
        self.log_viewer_open = False
        self.log_viewer = LogViewer()
        self.nations_scroll_offset = 0

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

        self.btn_view_logs = Button(
            button_spacing * 3 + button_width * 2, button_y, button_width, button_height,
            "View Logs",
            self._toggle_log_viewer,
            enabled=True
        )

        self.buttons = [self.btn_auto, self.btn_next_turn, self.btn_view_logs]

        # Responsive panels - calculate based on screen size
        panel_padding = 20
        nations_width = int(self.width * 0.35)  # 35% for nations list
        right_panel_width = self.width - nations_width - panel_padding * 3
        right_panel_height = (self.height - button_height - panel_padding * 4) // 2

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
            right_panel_height,
            "Current Turn"
        )

        self.panel_resources = Panel(
            nations_width + panel_padding * 2,
            right_panel_height + panel_padding * 2,
            right_panel_width,
            right_panel_height,
            "Resources"
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

    def _toggle_log_viewer(self) -> None:
        """Toggle log viewer window."""
        self.log_viewer_open = not self.log_viewer_open
        # Reset selection when opening the viewer (will default to newest log)
        if self.log_viewer_open:
            self.log_viewer.selected_log_id = None

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

            # Handle mouse wheel for nations panel scrolling
            if event.type == pygame.MOUSEWHEEL:
                mouse_pos = pygame.mouse.get_pos()
                if self.panel_nations.rect.collidepoint(mouse_pos):
                    # Calculate max scroll based on content height
                    item_height = 90
                    total_content_height = len(self.controller.game_state.nations) * item_height
                    visible_height = self.panel_nations.rect.height - 50
                    max_scroll = max(0, total_content_height - visible_height)

                    self.nations_scroll_offset -= event.y * 30
                    self.nations_scroll_offset = max(0, min(max_scroll, self.nations_scroll_offset))

            # Handle log viewer events if open
            if self.log_viewer_open:
                result = self.log_viewer.handle_event(event)
                if result == "close":
                    self.log_viewer_open = False
                    continue
                elif result:
                    continue

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
        self.panel_resources.draw(self.screen, self.font_medium)

        # Draw content
        self._draw_nations()
        self._draw_current_turn()
        self._draw_resources()

        # Draw buttons
        for button in self.buttons:
            button.draw(self.screen, self.font_medium)

        # Draw log viewer if open
        if self.log_viewer_open:
            self.log_viewer.draw(self.screen, self.font_small, self.controller.game_state, self.flag_images)

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
            if nation.name in self.flag_images:
                flag_img = self.flag_images[nation.name]['medium']
                self.screen.blit(flag_img, (x, y + 2))
                text_x = x + 40
            else:
                # Fallback to country code if no flag image
                country_code = self._get_country_code(nation.name)
                code_text = self.font_medium.render(country_code, True, colors.ACCENT)
                self.screen.blit(code_text, (x, y))
                text_x = x + 45

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
        turn_text = f"Turn: {self.controller.game_state.turn_number}"
        text = self.font_medium.render(turn_text, True, colors.TEXT)
        self.screen.blit(text, (x, y))

        y += 40

        # Current nation with flag
        if current_nation.name in self.flag_images:
            flag_img = self.flag_images[current_nation.name]['large']
            self.screen.blit(flag_img, (x, y))
            text_x = x + 55
        else:
            # Fallback to country code
            country_code = self._get_country_code(current_nation.name)
            code_text = self.font_large.render(country_code, True, colors.ACCENT)
            self.screen.blit(code_text, (x, y))
            text_x = x + 65

        nation_text = current_nation.name
        text = self.font_large.render(nation_text, True, colors.TEXT)
        self.screen.blit(text, (text_x, y))

        y += 50

        # Era
        era_text = f"Era: {current_nation.era.name}"
        text = self.font_medium.render(era_text, True, colors.ACCENT)
        self.screen.blit(text, (x, y))

        y += 40

        # Status - show what's happening
        if self.turn_executor.status.is_busy():
            status_text = self.turn_executor.status.get_action()
            if status_text:
                # Wrap long text
                max_width = self.panel_current.rect.width - 20
                words = status_text.split()
                lines = []
                current_line = []

                for word in words:
                    test_line = ' '.join(current_line + [word])
                    test_surface = self.font_small.render(test_line, True, colors.WARNING)
                    if test_surface.get_width() <= max_width:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]

                if current_line:
                    lines.append(' '.join(current_line))

                for line in lines[:3]:  # Max 3 lines
                    text = self.font_small.render(line, True, colors.WARNING)
                    self.screen.blit(text, (x, y))
                    y += 25

        # Show error if any
        error = self.turn_executor.status.get_error()
        if error:
            text = self.font_small.render(f"Error: {error[:50]}", True, colors.ERROR)
            self.screen.blit(text, (x, y))

    def _draw_resources(self) -> None:
        """Draw global resource summary."""
        x = self.panel_resources.rect.x + 10
        y = self.panel_resources.rect.y + 50

        text = self.font_small.render("Global Resources Summary:", True, colors.TEXT)
        self.screen.blit(text, (x, y))

        y += 30

        # Calculate totals
        totals = {rt: 0 for rt in ResourceType}
        for nation in self.controller.game_state.nations:
            for rt in ResourceType:
                totals[rt] += nation.inventory.get(rt)

        for rt, total in totals.items():
            if total > 0:
                resource_text = f"{self._get_resource_emoji(rt)} {total}"
                color = self._get_resource_color(rt)
                text = self.font_small.render(resource_text, True, color)
                self.screen.blit(text, (x, y))
                y += 25

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

    def _get_country_code(self, country_name: str) -> str:
        """Get 2-letter country code from country name."""
        # Map common countries to their codes
        country_codes = {
            "United States": "US",
            "China": "CN",
            "Japan": "JP",
            "Germany": "DE",
            "United Kingdom": "GB",
            "France": "FR",
            "India": "IN",
            "Brazil": "BR",
            "Canada": "CA",
            "South Korea": "KR",
            "Australia": "AU",
            "Spain": "ES",
            "Mexico": "MX",
            "Italy": "IT",
            "Russia": "RU",
        }

        return country_codes.get(country_name, country_name[:2].upper())

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

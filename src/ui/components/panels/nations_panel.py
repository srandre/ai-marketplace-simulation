"""Nations list panel component."""

import pygame
from typing import Dict, Any
from ....models.enums import ResourceType
from ...resource_display import get_resource_emoji, GENERATOR_EMOJIS
from ... import colors
from ..base_panel import ScrollablePanel
from ..utils import ScrollbarManager


class NationsPanel(ScrollablePanel):
    """Panel displaying list of nations with their resources and generators."""

    def __init__(self, panel, scrollbar_manager: ScrollbarManager,
                 flag_images: Dict[str, Dict[str, pygame.Surface]],
                 font_small: pygame.font.Font):
        super().__init__(panel, 'nations', scrollbar_manager)
        self.flag_images = flag_images
        self.font_small = font_small

    def draw_content(self, screen: pygame.Surface, game_state: Any) -> None:
        """Draw nations list with scrolling."""
        # Create clipping surface for scrolling
        clip_rect = pygame.Rect(
            self.panel.rect.x + 5,
            self.panel.rect.y + 40,
            self.panel.rect.width - 10,
            self.panel.rect.height - 45
        )

        # Reorder nations: current nation at top, then in turn order
        turn_order = game_state.turn_order
        current_idx = game_state.current_nation_index

        # Set clipping area to prevent overflow
        screen.set_clip(clip_rect)

        # Reorder turn_order to put current nation first
        ordered_nation_ids = turn_order[current_idx:] + turn_order[:current_idx]

        # Convert to actual nation objects
        ordered_nations = [game_state.get_nation(nid) for nid in ordered_nation_ids]
        ordered_nations = [n for n in ordered_nations if n is not None]

        # Draw nations with scroll offset
        y_offset = 50 - self.scroll_offset
        item_height = 90

        for nation in ordered_nations:
            x = self.panel.rect.x + 10
            y = self.panel.rect.y + y_offset

            # Skip if outside visible area
            if y + item_height < clip_rect.top or y > clip_rect.bottom:
                y_offset += item_height
                continue

            self._draw_nation_item(screen, nation, x, y)
            y_offset += item_height

        # Update content height for scrollbar
        self.content_height = len(ordered_nations) * item_height

        # Reset clipping
        screen.set_clip(None)

    def _draw_nation_item(self, screen: pygame.Surface, nation: Any, x: int, y: int) -> None:
        """Draw a single nation item."""
        # Draw flag image
        if nation.name in self.flag_images:
            flag_img = self.flag_images[nation.name]['medium']
            screen.blit(flag_img, (x, y - 1))
        text_x = x + 45

        # Nation name and era
        header = f"{nation.name} - Era {nation.era.value}"
        text = self.font_small.render(header, True, colors.TEXT)
        screen.blit(text, (text_x, y + 3))

        # Generators - show as emojis grouped by type
        y += 25
        generator_emojis = self._get_generator_emojis(nation)
        if generator_emojis:
            gen_text = f"Gen: {generator_emojis}"
            text = self.font_small.render(gen_text, True, colors.TEXT_SECONDARY)
            screen.blit(text, (x + 20, y))

        # Resources (show all with emojis)
        y += 24
        inv_label = "Inv:"
        text = self.font_small.render(inv_label, True, colors.TEXT_SECONDARY)
        screen.blit(text, (x + 20, y))

        res_x = x + 60
        for rt in ResourceType:
            emoji = get_resource_emoji(rt)
            amount = nation.inventory.get(rt)
            res_text = f"{emoji}{amount}"
            text = self.font_small.render(res_text, True, colors.TEXT_SECONDARY)
            screen.blit(text, (res_x, y))
            res_x += 100

    def _get_generator_emojis(self, nation: Any) -> str:
        """Get emoji representation of generators grouped by type."""
        from ....models.enums import GeneratorType

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
                emoji = GENERATOR_EMOJIS.get(gen_type, "❓")
                emoji_parts.append(emoji * count)

        return " ".join(emoji_parts)

"""Global resources bar component."""

import pygame
from typing import Dict, Any, Optional, Tuple
from ....models.enums import ResourceType, GeneratorType
from ...resource_display import get_resource_emoji
from ... import colors
from .. import draw_rounded_rect_border


class GlobalResourcesBar:
    """Bar displaying global resources at bottom of screen."""

    def __init__(self, font_small: pygame.font.Font):
        self.font_small = font_small
        self.resource_rects: Dict[ResourceType, pygame.Rect] = {}
        self.hovered_resource: Optional[ResourceType] = None

    def draw(self, screen: pygame.Surface, game_state: Any, screen_width: int,
            screen_height: int) -> None:
        """Draw global resources bar."""
        # Calculate totals
        totals = {rt: 0 for rt in ResourceType}
        for nation in game_state.nations:
            for rt in ResourceType:
                totals[rt] += nation.inventory.get(rt)

        # Start position after buttons
        button_spacing = 20
        button_width = 150
        x = button_spacing * 3 + button_width * 2 + 40
        y = screen_height - 60

        # Draw "Global Resources" label
        label = self.font_small.render("Global Resources:", True, colors.TEXT_SECONDARY)
        screen.blit(label, (x, y - 5))

        # Clear previous rects
        self.resource_rects = {}

        # Draw each resource with emoji + number
        for rt in ResourceType:
            total = totals[rt]
            emoji = get_resource_emoji(rt)
            resource_text = f"{emoji}{total}"
            text = self.font_small.render(resource_text, True, colors.TEXT)

            # Store rectangle for hover detection
            text_rect = text.get_rect(topleft=(x, y + 15))
            self.resource_rects[rt] = text_rect

            # Highlight if hovered
            if self.hovered_resource == rt:
                highlight_rect = text_rect.inflate(6, 4)
                draw_rounded_rect_border(screen, colors.ACCENT, highlight_rect, width=2, border_radius=4)

            screen.blit(text, (x, y + 15))
            x += 100

    def update_hover(self, mouse_pos: Tuple[int, int]) -> None:
        """Update hovered resource based on mouse position."""
        self.hovered_resource = None
        for rt, rect in self.resource_rects.items():
            if rect.collidepoint(mouse_pos):
                self.hovered_resource = rt
                break

    def get_tooltip_data(self, game_state: Any) -> Optional[Tuple[ResourceType, str, int, str]]:
        """Get tooltip data for hovered resource.

        Returns: (resource_type, generator_name, count, cost_text) or None
        """
        if not self.hovered_resource:
            return None

        # Map resource types to their generator types
        resource_to_generator = {
            ResourceType.GOLD: GeneratorType.MINE,
            ResourceType.WOOD: GeneratorType.LUMBER_CAMP,
            ResourceType.STONE: GeneratorType.QUARRY,
            ResourceType.FOOD: GeneratorType.FARM,
            ResourceType.TECHNOLOGY: GeneratorType.FACTORY,
            ResourceType.INFORMATION: GeneratorType.DATACENTER,
        }

        rt = self.hovered_resource
        if rt not in resource_to_generator:
            return None

        gen_type = resource_to_generator[rt]
        count = game_state.get_generator_count(gen_type)
        blueprint = game_state.generator_manager.get_blueprint(gen_type)

        if not blueprint:
            return None

        # Build cost text
        cost_parts = []
        if blueprint.base_cost_either:
            # Farm case - show both options
            multiplier = 2 ** count
            options = []
            for res_type, base_amount in blueprint.base_cost_either.items():
                cost = base_amount * multiplier
                emoji = get_resource_emoji(res_type)
                options.append(f"{cost} {emoji}")
            cost_text = ' or '.join(options)
        else:
            # Normal case
            current_cost = blueprint.get_current_cost(count)
            for res_type, amount in current_cost.items():
                emoji = get_resource_emoji(res_type)
                cost_parts.append(f"{amount} {emoji}")
            cost_text = ' + '.join(cost_parts)

        return (rt, blueprint.name, count, cost_text)

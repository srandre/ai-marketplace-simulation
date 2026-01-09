"""AI decision-making coordinator."""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..models.enums import ResourceType
from ..models.nation import Nation
from ..models.transaction import TradeOffer
from .deepseek_client import DeepSeekClient
from .prompts import (
    create_build_phase_prompt,
    create_counter_offer_response_prompt,
    create_system_prompt,
    create_trade_response_prompt,
    create_trading_phase_prompt,
)

if TYPE_CHECKING:
    from ..models.generator import GeneratorManager


class DecisionMaker:
    """Coordinates AI decision-making for nations."""

    def __init__(self, generator_manager: "GeneratorManager"):
        self.client = DeepSeekClient()
        self.system_prompt = create_system_prompt(generator_manager)

    def decide_trading_phase(
        self,
        nation: Nation,
        game_state: Dict[str, Any],
        era_requirements: Dict[str, int],
        trades_completed: int = 0,
    ) -> tuple[Dict[str, Any], str, str]:
        """
        Decide whether to make a trade in the trading phase.

        Returns (decision_dict, user_prompt, ai_response).
        decision_dict format:
        {
            "trade": true/false,
            "target_nation_id": <id or null>,
            "offering": {"GOLD": 100} or {"WOOD": 50, ...},
            "requesting": {"WOOD": 50, ...} or {"GOLD": 100},
            "reasoning": "..."
        }
        """
        user_prompt = create_trading_phase_prompt(
            nation, game_state, era_requirements, trades_completed
        )

        default_decision = {
            "trade": False,
            "target_nation_id": None,
            "offering": {},
            "requesting": {},
            "reasoning": "Unable to process trading decision",
        }

        decision, raw_response = self.client.make_decision_with_fallback(
            self.system_prompt, user_prompt, default_decision
        )

        return decision, user_prompt, raw_response

    def decide_build_phase(
        self,
        nation: Nation,
        game_state: Dict[str, Any],
        era_requirements: Dict[str, int],
    ) -> tuple[Dict[str, Any], str, str]:
        """
        Decide whether to build a generator in the build phase.

        Returns (decision_dict, user_prompt, ai_response).
        decision_dict format:
        {
            "build": true/false,
            "generator_type": "MINE" or null,
            "payment_resource": "WOOD" or null (for FARM),
            "reasoning": "..."
        }
        """
        user_prompt = create_build_phase_prompt(
            nation, game_state, era_requirements
        )

        default_decision = {
            "build": False,
            "generator_type": None,
            "payment_resource": None,
            "reasoning": "Unable to process build decision",
        }

        decision, raw_response = self.client.make_decision_with_fallback(
            self.system_prompt, user_prompt, default_decision
        )

        return decision, user_prompt, raw_response

    def respond_to_trade_offer(
        self,
        nation: Nation,
        proposer_nation: Dict[str, Any],
        offer: Dict[str, Any],
        game_state: Dict[str, Any],
    ) -> tuple[Dict[str, Any], str, str]:
        """
        Decide how to respond to a trade offer.

        Returns (decision_dict, user_prompt, ai_response).
        """
        user_prompt = create_trade_response_prompt(
            nation, proposer_nation, offer, game_state
        )

        default_decision = {
            "decision": "REJECT",
            "reasoning": "Unable to process offer",
        }

        decision, raw_response = self.client.make_decision_with_fallback(
            self.system_prompt, user_prompt, default_decision
        )

        return decision, user_prompt, raw_response

    def respond_to_counter_offer(
        self,
        nation: Nation,
        responder_nation: Dict[str, Any],
        counter_offer: Dict[str, Any],
    ) -> tuple[Dict[str, Any], str, str]:
        """
        Decide whether to accept a counter-offer.

        Returns (decision_dict, user_prompt, ai_response).
        """
        user_prompt = create_counter_offer_response_prompt(
            nation, responder_nation, counter_offer
        )

        default_decision = {
            "decision": "REJECT",
            "reasoning": "Unable to process counter-offer",
        }

        decision, raw_response = self.client.make_decision_with_fallback(
            self.system_prompt, user_prompt, default_decision
        )

        return decision, user_prompt, raw_response

    @staticmethod
    def parse_trade_offer(offer_dict: Dict[str, Any]) -> Optional[TradeOffer]:
        """Parse a trade offer from AI response."""
        try:
            offering = {}
            requesting = {}

            if "offering" in offer_dict:
                for resource_str, amount in offer_dict["offering"].items():
                    try:
                        resource_type = ResourceType[resource_str.upper()]
                        offering[resource_type] = int(amount)
                    except (KeyError, ValueError):
                        continue

            if "requesting" in offer_dict:
                for resource_str, amount in offer_dict["requesting"].items():
                    try:
                        resource_type = ResourceType[resource_str.upper()]
                        requesting[resource_type] = int(amount)
                    except (KeyError, ValueError):
                        continue

            return TradeOffer(offering=offering, requesting=requesting)

        except Exception as e:
            print(f"Error parsing trade offer: {e}")
            return None

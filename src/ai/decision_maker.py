"""AI decision-making coordinator."""

from typing import Any, Dict, List, Optional

from ..models.enums import ResourceType
from ..models.nation import Nation
from ..models.transaction import TradeOffer
from .deepseek_client import DeepSeekClient
from .prompts import (
    create_combined_turn_decision_prompt,
    create_counter_offer_response_prompt,
    create_system_prompt,
    create_trade_response_prompt,
)


class DecisionMaker:
    """Coordinates AI decision-making for nations."""

    def __init__(self):
        self.client = DeepSeekClient()
        self.system_prompt = create_system_prompt()

    def decide_all_actions(
        self,
        nation: Nation,
        game_state: Dict[str, Any],
        era_requirements: Dict[str, int],
    ) -> tuple[Dict[str, Any], str, str]:
        """
        Decide all actions for a nation's turn at once.

        Returns (decision_dict, user_prompt, ai_response).
        decision_dict contains an "actions" list with TRADE and/or BUILD actions.
        """
        user_prompt = create_combined_turn_decision_prompt(
            nation, game_state, era_requirements
        )

        default_decision = {
            "actions": []  # Empty turn if decision fails
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

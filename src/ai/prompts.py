"""Prompt templates for AI decision-making."""

import json
from typing import Any, Dict, List

from ..models.nation import Nation


def create_system_prompt() -> str:
    """Create the system prompt that defines the AI's role."""
    return """You are an AI controlling a nation in a strategic resource management game.

Your goal is to advance through the eras by collecting resources and building generators.

GAME RULES:
- There are 3 eras: Era of Origin (0), Era of Structuring (1), Era of Information (2)
- You advance eras automatically when you have enough resources at turn start
- Each era unlocks new resources and multiplies generation by 10x
- Resources: Gold (💰), Wood (🪵), Stone (🪨), Food (🌾), Technology (⚙️), Information (💾)

GENERATORS:
- Lumber Camp (produces Wood): costs Stone
- Quarry (produces Stone): costs Wood
- Farm (produces Food): costs any resource
- Mine (produces Gold): costs Stone + Wood
- Factory (produces Technology): costs Food + Gold (Era 1+)
- Datacenter (produces Information): costs Gold + Technology (Era 2+)

Generator prices increase progressively: 1st costs base price, 2nd costs 2x base, 3rd costs 3x base, etc.

TURN ACTIONS:
You can do up to 3 actions per turn:
1. SELL: Propose a trade (offer resources for what you want)
2. BUY: Same as SELL (trading is bilateral)
3. BUILD: Construct a generator

DIPLOMACY:
- Successful trades improve relationships (+1)
- Failed trades hurt relationships (-1)
- Consider relationships when making offers
- Don't make extremely unfair offers that harm your reputation

STRATEGY:
- Focus on advancing to the next era
- Build generators to increase resource production
- Trade strategically to get resources you need
- Balance short-term needs with long-term goals
- Consider which nations have resources you need

You must respond with valid JSON only. No explanations outside the JSON structure."""


def create_action_decision_prompt(
    nation: Nation,
    game_state: Dict[str, Any],
    available_actions: List[str],
    era_requirements: Dict[str, int],
) -> str:
    """Create prompt for deciding which action to take."""

    # Build concise game state summary
    other_nations = []
    for other in game_state.get("nations", []):
        if other["id"] != nation.id:
            relationship = nation.get_relationship(other["id"])
            other_nations.append({
                "id": other["id"],
                "name": other["name"],
                "era": other["era"],
                "resources": other["resources"],
                "relationship": relationship,
            })

    # Recent transactions
    recent_trades = game_state.get("recent_transactions", [])[:5]  # Last 5 only

    prompt_data = {
        "your_nation": {
            "name": nation.name,
            "era": nation.era.value,
            "resources": nation.inventory.to_dict(),
            "generators": [
                {"type": g.generator_type.value, "produces": g.produces.value}
                for g in nation.generators
            ],
        },
        "goal": {
            "next_era_requirements": era_requirements,
            "current_era": nation.era.value,
        },
        "other_nations": other_nations,
        "recent_trades": recent_trades,
        "available_actions": available_actions,
        "generator_costs": game_state.get("generator_costs", {}),
    }

    prompt = f"""Analyze the current game state and decide your action.

GAME STATE:
{json.dumps(prompt_data, indent=2)}

AVAILABLE ACTIONS: {', '.join(available_actions)}

Decide which action to take. Consider:
1. What resources do you need for the next era?
2. What generators would help you most?
3. Which nations have resources you need?
4. What trades would be fair and beneficial?
5. You can only buy resources for a certain price if you have the gold for it.
6. You can only buy resources that exist.
7. You can only sell resources you have.
8. You can only sell resources for a certain price if the other nation has the gold for it.

Respond with JSON in this format:
{{
    "action": "SELL" | "BUY" | "BUILD" | "PASS",
    "reasoning": "brief explanation of your strategy",
    "details": {{
        // For SELL/BUY:
        "target_nation_id": 0,
        "offering": {{"GOLD": 10, "WOOD": 5}},
        "requesting": {{"STONE": 15}}

        // For BUILD:
        "generator_type": "MINE" | "LUMBER_CAMP" | "QUARRY" | "FARM" | "FACTORY" | "DATACENTER"
    }}
}}

Choose wisely to advance toward the next era!"""

    return prompt


def create_trade_response_prompt(
    nation: Nation,
    proposer_nation: Dict[str, Any],
    offer: Dict[str, Any],
    game_state: Dict[str, Any],
) -> str:
    """Create prompt for responding to a trade offer."""

    relationship = nation.get_relationship(proposer_nation["id"])

    prompt_data = {
        "your_nation": {
            "name": nation.name,
            "era": nation.era.value,
            "resources": nation.inventory.to_dict(),
        },
        "proposer": {
            "name": proposer_nation["name"],
            "relationship": relationship,
        },
        "offer": offer,
        "your_goal": game_state.get("era_requirements", {}),
    }

    prompt = f"""You received a trade offer. Decide whether to accept, counter, or reject.

TRADE OFFER:
{json.dumps(prompt_data, indent=2)}

The proposer offers: {offer.get('offering', {})}
The proposer requests: {offer.get('requesting', {})}

Consider:
1. Do you have what they're requesting?
2. Do you need what they're offering?
3. Is this a fair trade?
4. How is your relationship with them? (Current: {relationship})
5. Will this help you reach your era advancement goals?
6. You can only buy resources for a certain price if you have the gold for it.
7. You can only buy resources that exist.
8. You can only sell resources you have.
9. You can only sell resources for a certain price if the other nation has the gold for it.

Respond with JSON:
{{
    "decision": "ACCEPT" | "COUNTER" | "REJECT",
    "reasoning": "why you made this choice",
    "counter_offer": {{  // Only if decision is COUNTER
        "offering": {{"GOLD": 10}},
        "requesting": {{"STONE": 5}}
    }}
}}"""

    return prompt


def create_counter_offer_response_prompt(
    nation: Nation,
    responder_nation: Dict[str, Any],
    counter_offer: Dict[str, Any],
) -> str:
    """Create prompt for responding to a counter-offer."""

    relationship = nation.get_relationship(responder_nation["id"])

    prompt_data = {
        "your_nation": {
            "name": nation.name,
            "resources": nation.inventory.to_dict(),
        },
        "responder": {
            "name": responder_nation["name"],
            "relationship": relationship,
        },
        "counter_offer": counter_offer,
    }

    prompt = f"""The other nation made a counter-offer to your trade proposal.

COUNTER-OFFER:
{json.dumps(prompt_data, indent=2)}

They offer: {counter_offer.get('offering', {})}
They request: {counter_offer.get('requesting', {})}

Decide whether to accept or reject this counter-offer.

Respond with JSON:
{{
    "decision": "ACCEPT" | "REJECT",
    "reasoning": "why you made this choice"
}}"""

    return prompt

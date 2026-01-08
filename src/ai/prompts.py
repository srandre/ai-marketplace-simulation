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
You can do 0 to 3 actions per turn:
1. TRADE: Propose a trade to another nation
2. BUILD: Construct a generator

TRADING RULES (IMPORTANT):
- ALL trades must be gold-for-resources exchanges
- One side offers ONLY GOLD (no other resources)
- The other side offers one or more resources (but NO GOLD)
- Examples:
  ✓ VALID: Offer [100 GOLD] for [50 WOOD, 30 STONE]
  ✓ VALID: Offer [50 WOOD, 30 STONE] for [100 GOLD]
  ✗ INVALID: Offer [50 GOLD, 10 WOOD] for [30 STONE] (gold mixed with resources)
  ✗ INVALID: Offer [50 WOOD] for [30 STONE] (no gold on either side)

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


def create_combined_turn_decision_prompt(
    nation: Nation,
    game_state: Dict[str, Any],
    era_requirements: Dict[str, int],
) -> str:
    """Create prompt for deciding all actions for a turn at once."""

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
        "generator_costs": game_state.get("generator_costs", {}),
    }

    prompt = f"""Analyze the game state and plan ALL your actions for this turn.

GAME STATE:
{json.dumps(prompt_data, indent=2)}

You can take 0-3 actions this turn. Plan your complete turn strategy:
1. TRADE: Propose one trade to another nation (optional)
2. BUILD: Build one generator (optional)

Consider:
- What resources do you need for the next era?
- Should you trade first to get resources, then build?
- Which generators would help you most?
- Which nations have resources you need and might accept your offer?

TRADING RULES:
- To BUY: Offer ONLY GOLD, request resources (no gold)
- To SELL: Offer resources (no gold), request ONLY GOLD
- Check if you/target have the resources needed for the trade

Respond with JSON containing your full turn plan:
{{
    "actions": [
        {{
            "type": "TRADE",
            "reasoning": "why you're making this trade",
            "target_nation_id": 0,
            "offering": {{"GOLD": 100}},  // ONLY GOLD if buying
            "requesting": {{"WOOD": 50, "STONE": 30}}  // NO GOLD if buying
        }},
        {{
            "type": "BUILD",
            "reasoning": "why you're building this",
            "generator_type": "MINE"
        }}
    ]
}}

RULES:
- actions array can be empty [] if you choose to pass
- Maximum 1 TRADE and 1 BUILD action
- Each reasoning should be under 150 characters
- Order doesn't matter (we execute TRADE before BUILD)
- Check generator_costs for exact prices
- One side of trade must be ONLY GOLD, other side NO GOLD

Plan your turn to advance toward the next era!"""

    return prompt


def create_action_decision_prompt(
    nation: Nation,
    game_state: Dict[str, Any],
    available_actions: List[str],
    era_requirements: Dict[str, int],
) -> str:
    """Create prompt for deciding which action to take (legacy - single action)."""

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
4. TRADING RULES:
   - To BUY resources: Offer ONLY GOLD, request the resources you want
   - To SELL resources: Offer the resources, request ONLY GOLD
   - One side must be ONLY gold, the other side must NOT have gold
   - Check if you have enough gold to buy OR if the target has enough gold to buy from you
   - Check if the target has the resources you want to buy OR if you have resources they might want

Respond with JSON in this format:
{{
    "action": "SELL" | "BUY" | "BUILD" | "PASS",
    "reasoning": "brief 1-2 sentence explanation (max 150 chars)",
    "details": {{
        // For SELL (selling resources for gold):
        "target_nation_id": 0,
        "offering": {{"WOOD": 50, "STONE": 30}},  // Resources you're selling (NO GOLD)
        "requesting": {{"GOLD": 100}}  // ONLY GOLD

        // For BUY (buying resources with gold):
        "target_nation_id": 0,
        "offering": {{"GOLD": 100}},  // ONLY GOLD
        "requesting": {{"WOOD": 50, "STONE": 30}}  // Resources you want (NO GOLD)

        // For BUILD:
        "generator_type": "MINE" | "LUMBER_CAMP" | "QUARRY" | "FARM" | "FACTORY" | "DATACENTER"
    }}
}}

CRITICAL TRADING RULES:
- One side must be ONLY GOLD (nothing else)
- The other side must have NO GOLD (only other resources)
- Farm costs N of ANY single resource (not free!)
- Keep reasoning under 150 characters
- Check generator_costs in the game state for exact prices

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
3. Is this a fair trade (consider market value)?
4. How is your relationship with them? (Current: {relationship})
5. Will this help you reach your era advancement goals?

REMEMBER: All trades must follow the gold-only rule:
- One side must be ONLY GOLD
- The other side must have NO GOLD

Respond with JSON:
{{
    "decision": "ACCEPT" | "COUNTER" | "REJECT",
    "reasoning": "why you made this choice",
    "counter_offer": {{  // Only if decision is COUNTER
        // If they offered gold, you must offer resources (no gold)
        "offering": {{"WOOD": 30, "STONE": 20}},  // NO GOLD
        "requesting": {{"GOLD": 50}}  // ONLY GOLD

        // If they offered resources, you must offer gold
        "offering": {{"GOLD": 50}},  // ONLY GOLD
        "requesting": {{"WOOD": 30, "STONE": 20}}  // NO GOLD
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

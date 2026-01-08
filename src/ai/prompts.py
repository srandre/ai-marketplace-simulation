"""Prompt templates for AI decision-making."""

import json
from typing import Any, Dict, List, TYPE_CHECKING

from ..models.nation import Nation

if TYPE_CHECKING:
    from ..models.generator import GeneratorManager


def create_system_prompt(generator_manager: "GeneratorManager") -> str:
    """Create the system prompt that defines the AI's role with dynamic generator costs from config."""
    from ..utils.config import config

    # Build generator descriptions from config
    generator_descriptions = []
    blueprints = generator_manager.get_all_blueprints()

    for gen_type, blueprint in blueprints.items():
        # Format the cost
        if blueprint.base_cost_either is not None:
            # Farm case: can pay with either WOOD or STONE
            cost_parts = [f"{amount} {res_type.name}" for res_type, amount in blueprint.base_cost_either.items()]
            cost_str = " OR ".join(cost_parts)
        else:
            cost_parts = [f"{amount} {res_type.name}" for res_type, amount in blueprint.base_cost.items()]
            cost_str = " + ".join(cost_parts)

        # Add era requirement if applicable
        era_note = f" (Era {blueprint.required_era}+)" if blueprint.required_era > 0 else ""

        generator_descriptions.append(
            f"- {blueprint.name} (produces {blueprint.produces.name}): {cost_str}{era_note}"
        )

    generators_text = "\n".join(generator_descriptions)

    # Dynamically build era information from config
    eras_config = config.get("eras", [])
    eras_sorted = sorted(eras_config, key=lambda e: e.get("index", 0))

    # Build era list
    era_list = ", ".join([f"{e.get('name')} ({e.get('index')})" for e in eras_sorted])

    # Build resource unlocking section
    resource_unlocking_lines = []
    for era in eras_sorted:
        era_idx = era.get("index")
        era_name_short = era.get("name", "").replace("Era of ", "")
        unlocked = era.get("unlocked_resources", [])

        # Get emoji mapping
        resource_emojis = {
            "GOLD": "💰", "WOOD": "🪵", "STONE": "🪨",
            "FOOD": "🌾", "TECHNOLOGY": "⚙️", "INFORMATION": "💾"
        }

        if era_idx == 0:
            # First era - list all resources
            resource_text = ", ".join([r for r in unlocked])
        else:
            # Subsequent eras - show what's newly unlocked
            prev_era = eras_sorted[era_idx - 1] if era_idx > 0 else {"unlocked_resources": []}
            prev_unlocked = set(prev_era.get("unlocked_resources", []))
            new_resources = [r for r in unlocked if r not in prev_unlocked]

            if new_resources:
                resource_text = "+ " + ", ".join([f"{r} ({resource_emojis.get(r, '❓')})" for r in new_resources])
            else:
                resource_text = "All resources"

        resource_unlocking_lines.append(f"- Era {era_idx} ({era_name_short}): {resource_text}")

    resource_unlocking_text = "\n".join(resource_unlocking_lines)

    # Build era advancement requirements dynamically
    advancement_lines = []
    for i, era in enumerate(eras_sorted[:-1]):  # Exclude last era (no advancement from final era)
        next_era = eras_sorted[i + 1]
        requirements_key = f"era_advancement.era_{next_era.get('index')}_requirements"
        reqs = config.get(requirements_key, {})

        if reqs:
            reqs_text = ", ".join([f"{v} {k}" for k, v in reqs.items()])
            era_name_short = era.get("name", "").replace("Era of ", "")
            next_era_name_short = next_era.get("name", "").replace("Era of ", "")

            # Mark final era as WIN
            win_suffix = " = WIN" if i + 1 == len(eras_sorted) - 1 else ""
            advancement_lines.append(
                f"- Era {era.get('index')} → Era {next_era.get('index')} ({next_era_name_short}{win_suffix}): {reqs_text}"
            )

    advancement_text = "\n".join(advancement_lines)

    # Get final era name for the win condition text
    final_era_name = eras_sorted[-1].get("name", "final era") if eras_sorted else "final era"

    return f"""You are an AI controlling a nation in a strategic resource management game.

Your goal is to advance through the eras by collecting resources and building generators.

GAME RULES:
- There are {len(eras_sorted)} eras: {era_list}
- You advance eras automatically when you have enough resources at turn start
- Each era unlocks new resources and multiplies generation significantly
- Advancing to {final_era_name} guarantees your victory immediately
- Resources: Gold (💰), Wood (🪵), Stone (🪨), Food (🌾), Technology (⚙️), Information (💾)

RESOURCE UNLOCKING BY ERA:
{resource_unlocking_text}

⚠️ CRITICAL TRADING RULE: You can ONLY trade resources that BOTH you AND your trading partner have unlocked!
- Example: If you're in a later era and they're in an earlier era, you CANNOT trade advanced resources with them
- Always check the target nation's era before proposing a trade involving advanced resources

ERA ADVANCEMENT REQUIREMENTS (you advance automatically at turn start when you have these):
{advancement_text}

GENERATORS (base costs):
{generators_text}

Generator prices increase exponentially depending on how many of that type exist globally:
Current cost = base cost × 2^n (where n = number of that generator type already built by any nation)
e.g. if there are 4 MINES in the game, the cost to build a 5th one would be 80 Wood + 80 Stone

TURN STRUCTURE (Two Phases):
Each turn has two distinct phases:

PHASE 1 - TRADING PHASE (up to 2 trades):
- You can propose up to 2 trades total this phase
- After each trade proposal, if rejected, you get ONE retry with a different (or same) nation
- You can skip trading entirely or stop after the first trade
- Strategic example: Sell resources for gold, then buy different resources with that gold

PHASE 2 - BUILD PHASE (1 build):
- After trading completes, you can build ONE generator (or skip)
- If you cannot afford ANY generator, your turn is automatically skipped

TRADING RULES (CRITICAL):
- ALL trades must be gold-for-resources exchanges
- One side offers ONLY GOLD (no other resources)
- The other side offers one or more resources (but NO GOLD)
- Before proposing, verify the target nation HAS the resources you want
- Examples:
  ✓ VALID: Offer [100 GOLD] for [50 WOOD, 30 STONE]
  ✓ VALID: Offer [50 WOOD, 30 STONE] for [100 GOLD]
  ✗ INVALID: Offer [50 GOLD, 10 WOOD] for [30 STONE] (gold mixed with resources)
  ✗ INVALID: Offer [50 WOOD] for [30 STONE] (no gold on either side)
  ✗ INVALID: Offer [50 WOOD] for [30 GOLD] when the other nation has only [10 GOLD]

DIPLOMACY:
- Successful trades improve relationships (+1)
- Failed trades hurt relationships (-1)
- Consider relationships when making offers
- Don't make extremely unfair offers that harm your reputation

STRATEGY:
- Focus on advancing to the next era
- Build generators to increase resource production
- Use the trading phase strategically (sell then buy, or buy resources for building)
- Balance short-term needs with long-term goals
- Consider which nations have resources you need

You must respond with valid JSON only. No explanations outside the JSON structure."""


def _format_memory_context(nation) -> str:
    """Format nation's decision memory for inclusion in prompts."""
    memory = nation.get_memory_context(max_entries=20)

    if not memory:
        return "\n--- YOUR PREVIOUS DECISIONS ---\nNo previous decisions yet. This is your first turn.\n"

    memory_text = "\n--- YOUR PREVIOUS DECISIONS (Your Strategic Memory) ---\n"
    memory_text += "Review your past decisions to maintain strategic consistency:\n\n"

    for mem in memory:
        memory_text += f"Round {mem['round']}, Turn {mem['turn']} - {mem['type']}:\n"
        memory_text += f"  Decision: {mem['decision']}\n"
        if mem.get('outcome'):
            memory_text += f"  Outcome: {mem['outcome']}\n"
        memory_text = "\n--- END PREVIOUS DECISIONS ---\n"

    memory_text += "Use this history to inform your current strategy and maintain consistency.\n"
    return memory_text


def create_trading_phase_prompt(
    nation: Nation,
    game_state: Dict[str, Any],
    era_requirements: Dict[str, int],
    trades_completed: int = 0,
) -> str:
    """Create prompt for the trading phase (up to 2 trades)."""

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
    recent_trades = game_state.get("recent_transactions", [])[:5]

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

    trades_remaining = 2 - trades_completed

    if trades_completed == 0:
        phase_text = "TRADING PHASE - First Trade Opportunity (2 trades remaining)"
        instruction = "You can propose ONE trade to another nation, or skip. If accepted, you'll get another trade opportunity."
        strategy_note = "You can strategize: for example, sell resources you have for gold, then buy different resources with that gold."
    else:
        phase_text = "TRADING PHASE - Second Trade Opportunity (1 trade remaining)"
        instruction = """⚠️ IMPORTANT: Check your memory! You just completed a trade THIS TURN.
DO NOT contradict your previous trade:
- If you just SOLD a resource, DON'T buy it back immediately (wasteful!)
- If you just BOUGHT a resource, DON'T sell it back immediately (wasteful!)
- Your second trade should COMPLEMENT your first trade, not undo it

You can propose ONE final trade to any nation (same or different), or skip."""
        strategy_note = "This is your last trade opportunity this turn. Make it count and ensure it aligns with your first trade's strategy!"

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""
{phase_text}

GAME STATE:
{json.dumps(prompt_data, indent=2)}
{memory_context}

{instruction}

⚠️ CRITICAL TRADING RULES - READ CAREFULLY ⚠️

1. GOLD-ONLY RULE (MANDATORY):
   - One side offers ONLY GOLD (nothing else)
   - The other side offers ONLY RESOURCES (NO GOLD at all)
   - Examples:
     ✓ VALID: You offer {{"GOLD": 100}}, request {{"WOOD": 50, "STONE": 30}}
     ✓ VALID: You offer {{"WOOD": 50, "STONE": 30}}, request {{"GOLD": 100}}
     ✗ INVALID: You offer {{"GOLD": 100, "WOOD": 10}} (mixing gold with resources)
     ✗ INVALID: Both sides have resources but no gold

2. VERIFY TARGET NATION HAS WHAT YOU REQUEST (MANDATORY):
   ⚠️ BEFORE proposing a trade, CHECK the "other_nations" data above!

   If you want to BUY resources from a nation:
   - You offer: {{"GOLD": X}}
   - You request: {{"WOOD": Y, "STONE": Z}}
   - ⚠️ CHECK: Does the target nation have AT LEAST Y WOOD and Z STONE in their "resources"?
   - If NO → DO NOT propose this trade! It will fail and waste your opportunity!

   If you want to SELL resources for gold:
   - You offer: {{"WOOD": Y, "STONE": Z}}
   - You request: {{"GOLD": X}}
   - ⚠️ CHECK: Does the target nation have AT LEAST X GOLD in their "resources"?
   - If NO → DO NOT propose this trade! It will fail and waste your opportunity!

3. NEVER propose to a nation that rejected you before (check your memory)

STRATEGY:
- First, identify what resources you NEED for your goals
- Then, find which nations HAVE those resources (check "other_nations" resources)
- Only propose to nations that can fulfill your request
- {strategy_note}

⚠️ BEFORE RESPONDING, COMPLETE THIS VERIFICATION CHECKLIST:

Step 1: What do I need? (Check your resources vs era requirements)
Step 2: Who has what I need? (Check "other_nations" resources carefully)
Step 3: Can they afford my request? (If I'm buying, do they have resources? If I'm selling, do they have gold?)
Step 4: Is this trade valid? (One side gold only, other side resources only)

Respond with JSON:
{{
    "trade": true/false,
    "target_nation_id": <nation_id or null>,
    "offering": {{"GOLD": 100}} or {{"WOOD": 50, "STONE": 30}},
    "requesting": {{"WOOD": 50, "STONE": 30}} or {{"GOLD": 100}},
    "reasoning": "Step 3 verification: Target nation has [X GOLD / Y WOOD, Z STONE]. [Why this trade makes sense]"
}}

⚠️ Your reasoning MUST start by stating what the target nation HAS, then explain the trade logic.

Examples of GOOD reasoning:
- "Target has 200 GOLD. I'll sell them 50 WOOD for 100 GOLD to get gold for buildings"
- "Target has 80 WOOD and 60 STONE. I'll buy 50 WOOD with 100 GOLD to advance era"

Examples of BAD reasoning (NEVER do this):
- "Egypt has wood but no gold, so I'll sell stone for gold" ← WRONG! They have no gold!
- "I need resources so I'll trade" ← Didn't verify target has what I want!

If you don't want to trade, set trade: false and leave other fields null/empty."""

    return prompt


def create_build_phase_prompt(
    nation: Nation,
    game_state: Dict[str, Any],
    era_requirements: Dict[str, int],
) -> str:
    """Create prompt for the build phase (build one generator or skip)."""

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
        "generator_costs": game_state.get("generator_costs", {}),
    }

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""
BUILD PHASE

GAME STATE:
{json.dumps(prompt_data, indent=2)}
{memory_context}

You can now build ONE generator, or skip building.

BUILDING RULES:
- Check generator_costs for exact prices
- Prices increase exponentially: base_cost × 2^n (n = already built globally)
- For FARM: You MUST specify payment_resource (WOOD or STONE)
- For MINE, FACTORY or INFORMATION: You MUST have enough of both resource requirements to build one
- Only build if you have enough resources

STRATEGY:
- Which generator helps you reach the next era?
- Do you have enough resources for it?
- Will this generator produce resources you need?

Respond with JSON:
{{
    "build": true/false,
    "generator_type": "MINE" or null,
    "payment_resource": "WOOD" or "STONE" or null (only for FARM),
    "reasoning": "brief explanation (max 150 chars)"
}}

If you don't want to build (or can't afford anything), set build: false.
If you want to build, set build: true and specify the generator_type."""

    return prompt


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

You can take 0-2 actions this turn. Plan your complete turn strategy:
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
- If the trade is rejected, you may try one more time later, with a different (or same) trade and with a different nation

Respond with JSON containing your full turn plan:
{{
    "actions": [
        {{
            "type": "TRADE",
            "reasoning": "why you're making this trade",
            "target_nation_id": 0,
            "offering": {{"GOLD": 100}},
            "requesting": {{"WOOD": 50, "STONE": 30}}
        }},
        {{
            "type": "BUILD",
            "reasoning": "why you're building this",
            "generator_type": "MINE"
        }},
        {{
            "type": "BUILD",
            "reasoning": "building Farm with wood",
            "generator_type": "FARM",
            "payment_resource": "WOOD"
        }}
    ]
}}

RULES:
- actions array can be empty [] if you choose to pass
- Maximum 2 actions total: 1 TRADE and/or 1 BUILD (0-2 actions)
- Each reasoning should be under 150 characters
- Order doesn't matter (we execute TRADE before BUILD)
- Check generator_costs for exact prices
- One side of trade must be ONLY GOLD, other side NO GOLD
- IMPORTANT: Before proposing a trade, verify the target nation HAS the resources you're requesting
- When building a FARM, you MUST specify payment_resource (WOOD or STONE) since Farm can be built with either of those resources

Plan your turn to advance toward the next era!"""

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

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""You received a trade offer. Decide whether to accept, counter, or reject.

TRADE OFFER:
{json.dumps(prompt_data, indent=2)}
{memory_context}

The proposer offers: {offer.get('offering', {})}
The proposer requests: {offer.get('requesting', {})}

Consider:
1. Do you have what they're requesting?
2. Do you need what they're offering?
3. Is this a fair trade (consider market value)?
4. How is your relationship with them? (Current: {relationship})
5. Will this help you reach your era advancement goals?
6. Consider the feasibility of the transaction. If it mathematically can't be completed by any of the parts, do not accept it.

REMEMBER: All trades must follow the gold-only rule:
- One side must be ONLY GOLD
- The other side must have NO GOLD

Respond with JSON:
{{
    "decision": "ACCEPT" | "COUNTER" | "REJECT",
    "reasoning": "why you made this choice",
    "counter_offer": {{
        "offering": {{"WOOD": 30, "STONE": 20}},
        "requesting": {{"GOLD": 50}}
        "offering": {{"GOLD": 50}},
        "requesting": {{"WOOD": 30, "STONE": 20}}
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


def create_alternative_trade_prompt(
    nation: Nation,
    other_nations: List[Dict[str, Any]],
    original_offering: Dict[str, Any],
    original_requesting: Dict[str, Any],
    rejected_nation_id: int,
    game_state: Dict[str, Any],
) -> str:
    """Create prompt for finding an alternative trade partner after rejection."""

    # Find the rejected nation name
    rejected_nation_name = None
    for n in game_state.get("nations", []):
        if n.get("id") == rejected_nation_id:
            rejected_nation_name = n.get("name")
            break

    prompt = f"""Your trade proposal was REJECTED by {rejected_nation_name}.

YOUR NATION:
- Name: {nation.name}
- Resources: {json.dumps(nation.inventory.to_dict(), indent=2)}
- Era: {nation.era.value}

REJECTED TRADE:
- You offered: {json.dumps(original_offering, indent=2)}
- You requested: {json.dumps(original_requesting, indent=2)}

ALTERNATIVE PARTNERS AVAILABLE:
{json.dumps(other_nations, indent=2)}

GAME STATE:
{json.dumps(game_state, indent=2)}

You can attempt the SAME trade (same offering/requesting) with a DIFFERENT partner, OR try a DIFFERENT trade with a DIFFERENT partner, OR skip trading entirely.

IMPORTANT RULES:
1. You can only retry with a nation that HAS the resources you're requesting
2. One side must be ONLY GOLD, other side NO GOLD
3. Choose wisely - consider relationships and strategic value
4. If no good alternative exists, set retry: false
5. This is your last chance to trade. If it is rejected, you may not try trading again this turn

Respond with JSON:
{{
    "retry": true/false,
    "target_nation_id": <nation_id or null>,
    "reasoning": "why you chose this partner or why you're not retrying (max 100 chars)"
}}

Example responses:
{{"retry": true, "target_nation_id": 2, "reasoning": "USA has the resources and good relationship"}}
{{"retry": false, "target_nation_id": null, "reasoning": "No other nation has enough wood available"}}
"""

    return prompt

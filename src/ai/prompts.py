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

OBJECTIVE: Advance through eras by collecting resources and building generators. Reaching {final_era_name} = WIN.

ERAS ({len(eras_sorted)} total):
{era_list}

RESOURCE UNLOCKING BY ERA:
{resource_unlocking_text}

ERA ADVANCEMENT (automatic at turn start when you have these resources):
{advancement_text}

GENERATORS (base costs - increase exponentially as more are built globally):
{generators_text}

IMPORTANT: Generator costs scale as: current_cost = base_cost × 2^(total_built_globally)
Example: If 4 MINES exist globally, the 5th costs 80 WOOD + 80 STONE (10×2^4)

CRITICAL GAME MECHANICS:

RESOURCE GENERATION TIMING:
- Generators produce resources ONLY at the START of each turn (before trading)
- During trading, you can ONLY trade resources you CURRENTLY have in your inventory
- DO NOT assume nations have resources just because they have generators
- ALWAYS check the "resources" field, NOT the "generators" field
- Example: If a nation has a FARM generator but "resources": {{"FOOD": 0}}, they have NO FOOD to trade right now

TURN STRUCTURE:
1. RESOURCE GENERATION: All generators produce resources (automatic)
2. TRADING PHASE: Propose up to 2 trades using CURRENT resources only
   - If rejected, get ONE chance to retry with different/same partner
   - Can only trade what's in your "resources" inventory RIGHT NOW
3. BUILD PHASE: Build ONE generator using CURRENT resources or skip

You must respond with valid JSON only. No explanations outside the JSON structure.
Before answering with your JSON, make sure the decisions match your reasoning's bottom line"""


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
    memory_text += "\n--- END PREVIOUS DECISIONS ---\n"

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

    if trades_completed == 0:
        phase_text = "TRADING PHASE - Opportunity 1/2"
        complement_note = ""
    else:
        phase_text = "TRADING PHASE - Opportunity 2/2 (FINAL)"
        complement_note = "\nIMPORTANT: Your second trade should COMPLEMENT your first trade (don't immediately undo what you just did)."

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""
{phase_text}

GAME STATE:
{json.dumps(prompt_data, indent=2)}
{memory_context}
{complement_note}

GOLD-ONLY TRADING RULES:
- One side offers ONLY GOLD
- Other side offers ONLY resources (can be multiple: WOOD, STONE, FOOD, etc.)
- NEVER mix gold with resources on the same side
- Examples:
  ✓ Offer GOLD → Request WOOD (BUY)
  ✓ Offer GOLD → Request WOOD + STONE (BUY bundle)
  ✓ Offer WOOD + STONE → Request GOLD (SELL bundle)
  ✗ Offer GOLD + WOOD → anything (can't mix gold with resources)
  ✗ Offer WOOD → Request STONE (one side MUST be GOLD)

CRITICAL - TARGET NATIONS WITH GENERATORS:
Check target nation's generators! They're MORE LIKELY to accept if they can regenerate.
- Target has MINE? → Request GOLD from them (they'll regenerate it)
- Target has LUMBER_CAMP? → Request WOOD from them (they'll regenerate it)
- Target has QUARRY? → Request STONE from them (they'll regenerate it)
- Target has FARM? → Request FOOD from them (they'll regenerate it)

STEP-BY-STEP:
1. What do I need? (check "goal.next_era_requirements")
2. Do I have GOLD to buy, or resources to sell for GOLD?
3. Who has what I need AND generators for it?
4. Check "your_nation.resources" - do YOU have what you offer?
5. Check target's "resources" - do THEY have what you request?

Respond with JSON (keep reasoning ≤3 sentences):
{{
    "trade": true/false,
    "target_nation_id": <id or null>,
    "offering": {{"GOLD": 50}} or {{"WOOD": 50, "STONE": 30}},
    "requesting": {{"WOOD": 50}} or {{"GOLD": 50}},
    "reasoning": "I need X. [Name] has Y and [GENERATOR]. Buying/Selling/Skipping."
}}

GOOD examples:
- {{"trade": true, "offering": {{"GOLD": 100}}, "requesting": {{"WOOD": 50, "STONE": 50}}, "reasoning": "I need WOOD and STONE. USA has both and generators. Buying for 100 GOLD."}}
- {{"trade": true, "offering": {{"FOOD": 30, "WOOD": 20}}, "requesting": {{"GOLD": 50}}, "reasoning": "I need GOLD. Iran has 60 GOLD and MINE. Selling for 50 GOLD."}}
- {{"trade": false, "target_nation_id": null, "offering": {{}}, "requesting": {{}}, "reasoning": "I have 0 GOLD and nothing to sell. Skipping."}}

BAD examples:
- {{"offering": {{"GOLD": 50, "WOOD": 30}}, ...}} ← WRONG! Can't mix gold with resources
- {{"offering": {{"GOLD": 50}}, "requesting": {{"GOLD": 50}}}} ← WRONG! Can't trade gold for gold
- {{"offering": {{"WOOD": 50}}, "requesting": {{"STONE": 30}}}} ← WRONG! One side MUST be GOLD"""

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

Build ONE generator or skip.

RULES:
- Check "generator_costs" for exact current prices
- Verify YOU have enough resources (compare cost to "your_nation.resources")
- For FARM: specify payment_resource (WOOD or STONE)
- If you can't afford it, set build: false

STRATEGY:
- What do I need for next era? (check "goal.next_era_requirements")
- Which generator produces what I need?
- Can I afford it with my current resources?

IMPORTANT - GOLD IS CRITICAL:
- MINE produces GOLD (needed for all trades!)
- Without GOLD, you cannot BUY resources from other nations
- GOLD unlocks trading opportunities - prioritize MINE if you can afford it
- All era requirements include GOLD

Respond with JSON (keep reasoning ≤2 sentences):
{{
    "build": true/false,
    "generator_type": "LUMBER_CAMP" | "QUARRY" | "FARM" | "MINE" | "FACTORY" | "DATACENTER" | null,
    "payment_resource": "WOOD" | "STONE" | null (for FARM only),
    "reasoning": "What I have, what it costs, decision."
}}

GOOD examples:
- "I have 80 WOOD, 80 STONE. MINE costs 80+80. Building MINE."
- "I have 40 STONE. FARM costs 40. Paying with STONE. Building FARM."
- "I have 30 WOOD, 25 STONE. FARM costs 40. Cannot afford. Skipping."

BAD examples:
- Reasoning says "skip" but build: true (must match!)
- Reasoning says "build FARM" but generator_type: "MINE" (must match!)
- Not checking if you can afford it
- Long rambling analysis (keep it ≤2 sentences!)"""

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
            "generators": [
                {"type": g.generator_type.value, "produces": g.produces.value}
                for g in nation.generators
            ],
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

    prompt = f"""TRADE OFFER RECEIVED

OFFER DETAILS:
{json.dumps(prompt_data, indent=2)}
{memory_context}

They offer: {offer.get('offering', {})}
They request: {offer.get('requesting', {})}

RULES:
- You MUST have what they request (check "your_nation.resources")
- If you lack ANY requested resource → REJECT
- Resources are ALWAYS useful (for future eras, generators, other trades)

CRITICAL - WHEN TO ACCEPT:
Check YOUR generators (in "your_nation.generators"):
- MINE produces GOLD
- LUMBER_CAMP produces WOOD
- QUARRY produces STONE
- FARM produces FOOD

ACCEPT if you have a generator for what they request!
- They want GOLD and you have MINE? → ACCEPT (you'll regenerate GOLD next turn)
- They want WOOD and you have LUMBER_CAMP? → ACCEPT (you'll regenerate WOOD next turn)
- They want STONE and you have QUARRY? → ACCEPT (you'll regenerate STONE next turn)
- They want FOOD and you have FARM? → ACCEPT (you'll regenerate FOOD next turn)

Only REJECT if:
- You don't have what they request, OR
- You don't have a generator for it (you won't get it back)

Respond with JSON (keep reasoning ≤2 sentences):
{{
    "decision": "ACCEPT" | "REJECT",
    "reasoning": "They request X. I have [amount] and [GENERATOR]. Accepting/Rejecting."
}}

GOOD examples (notice they always mention their generator!):
- "They request 50 GOLD. I have 50 GOLD and MINE. Accepting."
- "They request 50 WOOD. I have 50 WOOD but no LUMBER_CAMP. Rejecting."
- "They request 80 STONE. I have 100 STONE and QUARRY. Accepting."

BAD examples:
- "I need WOOD for advancement, rejecting" (WRONG - if you have LUMBER_CAMP, accept!)
- Not mentioning your generators in reasoning"""

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

    prompt = f"""TRADE REJECTED by {rejected_nation_name}

YOUR NATION:
- Name: {nation.name}
- Resources: {json.dumps(nation.inventory.to_dict(), indent=2)}

REJECTED TRADE:
- You offered: {json.dumps(original_offering, indent=2)}
- You requested: {json.dumps(original_requesting, indent=2)}

ALTERNATIVE PARTNERS:
{json.dumps(other_nations, indent=2)}

OPTIONS:
1. Try SAME trade with different partner
2. Try DIFFERENT trade with different partner
3. Skip (retry: false) → ends trading phase

CRITICAL: Check "resources" field, NOT "generators" field!
- Generators produce NEXT turn, not now
- If nation has LUMBER_CAMP but resources.WOOD = 0 → they have NO WOOD now!

GOLD-ONLY TRADING RULES:
- One side ONLY GOLD, other side ONLY resources (can be multiple)
- NEVER mix gold with resources on same side
- Examples: ✓ GOLD for WOOD+STONE  ✓ WOOD+STONE for GOLD  ✗ GOLD+WOOD for anything

RULES:
- Verify YOU still have what you're offering
- Verify ALTERNATIVE nation has what you're requesting (check their "resources")
- If no good alternative → set retry: false

Respond with JSON (keep reasoning ≤3 sentences):
{{
    "retry": true/false,
    "target_nation_id": <id or null>,
    "offering": {{"GOLD": 50}} or {{"WOOD": 50, "STONE": 30}},
    "requesting": {{"WOOD": 50}} or {{"GOLD": 50}},
    "reasoning": "What I have, what they have, decision."
}}

GOOD examples:
- {{"retry": true, "target_nation_id": 2, "offering": {{"GOLD": 100}}, "requesting": {{"WOOD": 60, "STONE": 40}}, "reasoning": "I have 100 GOLD. USA has both. Retrying."}}
- {{"retry": false, "target_nation_id": null, "offering": {{}}, "requesting": {{}}, "reasoning": "No nation has what I need. Skipping."}}

BAD examples:
- {{"offering": {{"GOLD": 50, "WOOD": 30}}, ...}} ← WRONG! Can't mix gold with resources
- {{"offering": {{"WOOD": 50}}, "requesting": {{"STONE": 30}}}} ← WRONG! One side MUST be GOLD"""

    return prompt
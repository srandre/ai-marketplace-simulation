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
        phase_text = "TRADING PHASE - First Trade Opportunity (2 trades remaining)"
        instruction = """You can propose ONE trade to another nation, or skip.

NOTE: If you skip now, your trading phase ends and you move to the build phase.
If your trade is accepted, you'll get another trade opportunity. If your trade is rejected, you may retry with a different partner."""
        strategy_note = "You can strategize: for example, sell resources you have for gold, then buy different resources with that gold."
    else:
        phase_text = "TRADING PHASE - Second Trade Opportunity (1 trade remaining)"
        instruction = """IMPORTANT: Check your memory! You just completed a trade THIS TURN.
DO NOT contradict your previous trade:
- If you just SOLD a resource, DON'T buy it back immediately (wasteful!)
- If you just BOUGHT a resource, DON'T sell it back immediately (wasteful!)
- Your second trade should COMPLEMENT your first trade, not undo it

You can propose ONE final trade to any nation (same or different), or skip.

NOTE: This is your last trade opportunity this turn."""
        strategy_note = "This is your last trade opportunity this turn. Make it count and ensure it aligns with your first trade's strategy!"

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""
{phase_text}

GAME STATE:
{json.dumps(prompt_data, indent=2)}
{memory_context}

{instruction}

CRITICAL TRADING RULES - READ CAREFULLY 
1. GOLD-ONLY RULE (MANDATORY):
   - One side offers ONLY GOLD (nothing else)
   - The other side offers ONLY RESOURCES (NO GOLD at all)
   - Examples:
     ✓ VALID: You offer {{"GOLD": 100}}, request {{"WOOD": 50, "STONE": 30}}
     ✓ VALID: You offer {{"WOOD": 50, "STONE": 30}}, request {{"GOLD": 100}}
     ✗ INVALID: You offer {{"GOLD": 100, "WOOD": 10}} (mixing gold with resources)
     ✗ INVALID: Both sides have resources but no gold

2. VERIFY YOU HAVE WHAT YOU'RE OFFERING (MANDATORY):
   CHECK YOUR OWN RESOURCES FIRST!
   - If you want to offer GOLD → Do YOU have enough GOLD? Check "your_nation.resources.GOLD"
   - If you want to offer WOOD/STONE/FOOD → Do YOU have enough? Check "your_nation.resources"
   - If you DON'T have what you want to offer → YOU CANNOT MAKE THIS TRADE!

   Example: If your resources show {{"GOLD": 0, "WOOD": 50}}, you CANNOT offer GOLD in any trade!

3. VERIFY TARGET NATION HAS WHAT YOU REQUEST (MANDATORY):
   BEFORE proposing a trade, CHECK the "other_nations" data above!

   If you want to BUY resources from a nation:
   - You offer: {{"GOLD": X}}
   - You request: {{"WOOD": Y, "STONE": Z}}
   - CHECK: Does the target nation have AT LEAST Y WOOD and Z STONE in their "resources"?
   - If NO → DO NOT propose this trade! It will fail and waste your opportunity!

   If you want to SELL resources for gold:
   - You offer: {{"WOOD": Y, "STONE": Z}}
   - You request: {{"GOLD": X}}
   - CHECK: Does the target nation have AT LEAST X GOLD in their "resources"?
   - If NO → DO NOT propose this trade! It will fail and waste your opportunity!

4. NEVER propose to a nation that rejected you before (check your memory)

STRATEGY - STEP BY STEP:
1. What do I need? (Check era requirements vs your current resources)
2. Do I have GOLD? If YES → You can BUY resources! Look for nations that HAVE what you need
3. Do I have extra resources? If YES → You can SELL them for GOLD to nations that HAVE GOLD
4. Find the right trading partner (check "other_nations"):
   - If BUYING: Find who HAS the resources you need
   - If SELLING: Find who HAS enough GOLD to pay you
5. {strategy_note}

IMPORTANT: If you have GOLD and need resources, you should BUY (offer GOLD, request resources)!
Don't skip trading just because others don't have GOLD - you can use YOUR gold to buy FROM them!

MARKET DYNAMICS - SUPPLY AND DEMAND:

1. CHOOSING THE BEST TRADING PARTNER:
   When multiple nations have what you need, prefer nations with MORE of that resource:
   - If buying WOOD: Nation with 200 WOOD is better than nation with 80 WOOD (more supply = more likely to accept)
   - If selling for GOLD: Nation with 300 GOLD is better than nation with 100 GOLD (more buying power)
   - Nations with abundant resources are more likely to trade and can handle larger deals

2. PRICING BASED ON YOUR SCARCITY (ERA-RELATIVE):
   Adjust your offers based on how desperate you are RELATIVE TO YOUR ERA:

   First, check your era advancement requirements to understand what's "a lot" vs "scarce" in YOUR era:
   - Era 0 (Origin): Requirements are ~50 per resource
   - Era 1 (Industry): Requirements are ~500 per resource
   - Era 2 (Information): Requirements are ~5000-20000 per resource
   - Era 3 (Domination): Requirements are ~50000 per resource

   ABUNDANT = You have 4x+ your era advancement requirement
   COMFORTABLE = You have 2-4x your era advancement requirement
   LIMITED = You have 1-2x your era advancement requirement
   SCARCE = You have less than your era advancement requirement

   If you're BUYING and you have ABUNDANT GOLD (4x+ era requirement):
   - You can afford to pay MORE to ensure acceptance
   - Example Era 1: You have 2000 GOLD (4x of 500) → offer generous prices like 150 GOLD for 80 WOOD
   - Being generous increases your chance of acceptance

   If you're BUYING and you have LIMITED/SCARCE GOLD (1-2x era requirement):
   - Try to get fair deals, don't overpay
   - Example Era 1: You have 600 GOLD (barely above 500) → offer conservative prices like 90 GOLD for 80 WOOD

   If you're SELLING and you have EXCESS resources (3x+ era requirement):
   - You can offer MORE generous amounts to get GOLD quickly
   - Example Era 2: You have 18000 WOOD (3x of 6000) → sell 1000 WOOD for 1200 GOLD (generous amount)
   - Moving excess resources for gold is strategic

   If you're SELLING and you have LIMITED/SCARCE resources (less than 2x era requirement):
   - Ask for MORE GOLD per resource, don't undersell
   - Example Era 2: You have 7000 STONE (barely above 6000) → sell 400 STONE for 1000 GOLD (premium price)

   But remember: you can adjust these based on YOUR scarcity and THEIR abundance!

4. EXAMPLES OF MARKET-AWARE TRADING (ERA-RELATIVE):
   ✓ GOOD (Era 0): "I have 250 GOLD (5x of 50 requirement = abundant). USA has 180 WOOD. I'll offer 120 GOLD for 60 WOOD (generous) to ensure acceptance."
   ✓ GOOD (Era 1): "I have 400 WOOD (below 500 requirement = scarce). Japan has 2500 GOLD (5x of 500 = abundant). I'll sell 80 WOOD for 250 GOLD (premium price) since I'm near my advancement threshold."
   ✓ GOOD (Era 2): "I have 18000 STONE (3x of 6000 requirement = excess). Turkey has 8000 GOLD. I'll sell 2500 STONE for 3000 GOLD (generous amount) to convert excess."
   ✗ BAD (Era 1): "I have 550 GOLD (barely above 500 requirement = limited). I'll offer 500 GOLD for resources" ← spending almost all your gold when you're close to advancement threshold is risky!
   ✗ BAD (Era 0): "I have 35 WOOD (below 50 requirement = scarce). I'll sell 30 WOOD for 40 GOLD" ← undervaluing scarce resources when you need them for advancement!

BEFORE RESPONDING, COMPLETE THIS VERIFICATION CHECKLIST:

Step 1: What do I need? (Check your resources vs era requirements)
Step 2: Do I HAVE what I want to offer? (Check YOUR OWN resources - if offering GOLD, do you have GOLD? If offering WOOD, do you have WOOD?)
Step 3: Who has what I need? (Check "other_nations" resources carefully)
Step 4: Can they afford my request? (If I'm buying, do they have resources? If I'm selling, do they have gold?)
Step 5: Is this trade valid? (One side gold only, other side resources only)

CRITICAL: Your JSON response MUST match your reasoning!
- If your reasoning says "Therefore, I will skip trading", then trade MUST be false
- If your reasoning says "trade is invalid", then trade MUST be false
- If your reasoning says "I cannot sell/buy", then trade MUST be false
- If your reasoning says "Therefore, I will trade with X", then trade MUST be true and target_nation_id MUST be X's ID
- DO NOT write one thing in reasoning and different thing in JSON!

DOUBLE-CHECK YOUR target_nation_id:
If your reasoning mentions "Thailand" → find Thailand's ID in "other_nations" and use THAT ID
If your reasoning mentions "Turkey" → find Turkey's ID in "other_nations" and use THAT ID
Example: Reasoning says "Therefore, I will trade with Thailand" and Thailand's id is 1 → target_nation_id MUST be 1
WRONG: Reasoning says "Thailand" but target_nation_id is 2 (that's Turkey, not Thailand!)

WHEN TO SKIP (trade: false):
- No nation has what you're requesting (if buying)
- No nation has GOLD to pay you (if selling)
- You don't have what you want to offer
- You don't have a good strategic reason to trade right now
- You want to save your trades for later in the game

Skipping is a VALID strategic choice! Don't force a bad trade just because you're afraid to skip.

Respond with JSON:
{{
    "trade": true/false,
    "target_nation_id": <nation_id or null>,
    "offering": {{"GOLD": 100}} or {{"WOOD": 50, "STONE": 30}},
    "requesting": {{"WOOD": 50, "STONE": 30}} or {{"GOLD": 100}},
    "reasoning": "Target nation [NAME] has [X GOLD / Y WOOD, Z STONE]. [Explanation]. Therefore, I will [trade/skip]."
}}

Your reasoning MUST:
1. Start by stating what YOU have (your own resources)
2. State what the target nation HAS
3. End with "Therefore, I will trade with [NAME]" or "Therefore, I will skip trading"

Examples of GOOD reasoning:
- "I have 50 WOOD. Norway has 200 GOLD. I'll sell them 50 WOOD for 100 GOLD to get gold for buildings. Therefore, I will trade with Norway."
- "I have 100 GOLD. Egypt has 80 WOOD and 60 STONE. I'll buy 50 WOOD with 100 GOLD to advance era. Therefore, I will trade with Egypt."
- "I have 0 GOLD. Norway has 200 GOLD. I cannot buy from anyone without GOLD. Therefore, I will skip trading."
- "I have 50 WOOD but 0 GOLD. Egypt has 0 GOLD. I cannot sell to Egypt because they have no GOLD to pay me. Therefore, I will skip trading."

Examples of BAD reasoning (NEVER do this):
- "Egypt has wood but no gold, so I'll sell stone for gold" ← WRONG! They have no gold!
- "I need resources so I'll trade" ← Didn't verify YOU have what you're offering!
- "I'll offer 100 GOLD to buy WOOD" when you have 0 GOLD ← WRONG! You don't have GOLD!
- Reasoning says "Therefore, I will trade with Thailand" but JSON has target_nation_id: 2 (Turkey) ← WRONG! IDs don't match!
- Reasoning says "invalid" but JSON has trade: true ← WRONG! Must match!

NOTE: Setting trade: false ends your trading phase and moves you to the build phase."""

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
- Check generator_costs for exact prices (these are the ACTUAL current costs, already calculated)
- For FARM: You MUST specify payment_resource (WOOD or STONE)
- Only build if you can AFFORD it

BEFORE BUILDING, COMPLETE THIS VERIFICATION CHECKLIST:

Step 1: Which generator do I want to build?
Step 2: What does it cost? (Check "generator_costs" - these are EXACT current prices)
Step 3: Do I HAVE enough resources to afford it? (Compare cost to YOUR resources in "your_nation.resources")
Step 4: If you DON'T have enough → set build: false

CRITICAL VERIFICATION:
- If generator costs {{"WOOD": 80, "STONE": 80}} and you have {{"WOOD": 50, "STONE": 60}} → YOU CANNOT BUILD IT!
- If FARM costs {{"WOOD or STONE": 40}} and you have {{"WOOD": 30, "STONE": 10}} → YOU CANNOT BUILD IT!
- Always verify EVERY resource in the cost against YOUR resources

STRATEGY:
- Which generator helps you reach the next era?
- Do you have enough resources for it RIGHT NOW?
- Will this generator produce resources you need?

CRITICAL: Your JSON response MUST match your reasoning!
- If your reasoning says "build FARM", then build MUST be true and generator_type MUST be "FARM"
- If your reasoning says "cannot afford", then build MUST be false
- If your reasoning says "I will skip building", then build MUST be false
- If your reasoning says "I lack X" or "I cannot afford", then build MUST be false
- DO NOT write one thing in reasoning and different thing in JSON!

ABSOLUTE RULE - READ THIS CAREFULLY:
If your reasoning contains ANY of these phrases, then build MUST be false:
- "I cannot afford"
- "I lack"
- "Therefore, I will skip building"
- "I don't have enough"

If your reasoning says you CANNOT afford something, then build = false. Period. No exceptions.

REASONING FORMAT - KEEP IT SHORT AND FOCUSED:
Your reasoning should be 1-2 sentences maximum. Do NOT analyze multiple generators. Pick ONE and verify it.
Bad: "I have X. QUARRY costs Y. I can't afford QUARRY. LUMBER costs Z. I can't afford that either. FARM costs W..."
Good: "I have 50 WOOD. FARM costs 40 WOOD. I can afford it. Therefore, I will build FARM."

Respond with JSON:
{{
    "build": true/false,
    "generator_type": "LUMBER_CAMP" or "QUARRY" or "FARM" or "MINE" or "FACTORY" or "DATACENTER" or null,
    "payment_resource": "WOOD" or "STONE" (only for FARM) or null,
    "reasoning": "MAXIMUM 2 sentences. State: (1) what you have and what it costs, (2) Therefore conclusion"
}}

Your reasoning MUST:
1. Be VERY SHORT (1-2 sentences max)
2. Pick ONE generator to build (or skip)
3. State what YOU have and what IT costs
4. End with "Therefore, I will build [X]" or "Therefore, I will skip building"
5. The generator in "Therefore" MUST match the JSON generator_type field!

Examples of GOOD reasoning:
- "I have 80 WOOD, 80 STONE. MINE costs 80 WOOD + 80 STONE. I can afford it and need TECHNOLOGY. Therefore, I will build MINE."
- "I have 40 STONE, 20 WOOD. FARM costs 40 WOOD or STONE. I'll pay with STONE to save WOOD. Therefore, I will build FARM."
- "I have 30 WOOD, 25 STONE. FARM costs 40 (WOOD or STONE). I cannot afford any generator. Therefore, I will skip building."

Examples of BAD reasoning (NEVER do this):
- "I need MINE so I'll build it" ← WRONG! Didn't verify if you can afford it!
- "MINE costs 80 WOOD + 80 STONE. Therefore, I will build MINE" ← WRONG! Didn't check if YOU have 80 of each!
- "I can't afford QUARRY. I can't afford LUMBER. Therefore I will build FARM" ← WRONG! Too long, confusing!
- "I cannot afford it because I lack 50 GOLD. Therefore, I will skip building" but JSON has build: true ← WRONG! Must be false!
- Reasoning says "Therefore, I will build FARM" but JSON has generator_type: "QUARRY" ← WRONG! Must match!
- Reasoning says "skip" but JSON has build: true ← WRONG! Must match!

If you don't want to build (or can't afford anything), set build: false.
If you want to build, set build: true and specify the generator_type matching your reasoning."""

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

BEFORE RESPONDING, COMPLETE THIS VERIFICATION CHECKLIST:

Step 1: What are they requesting from me? (Check "offer.requesting")
Step 2: Do I HAVE what they're requesting? (Compare to YOUR resources in "your_nation.resources")
Step 3: If I DON'T have enough → I MUST REJECT (cannot complete the trade)
Step 4: What are they offering me? Do I need it?
Step 5: Is this a fair trade?

CRITICAL VERIFICATION:
- If they request {{"GOLD": 100}} and you have {{"GOLD": 50}} → YOU MUST REJECT! You don't have enough!
- If they request {{"WOOD": 50, "STONE": 30}} and you have {{"WOOD": 40, "STONE": 60}} → YOU MUST REJECT! You lack WOOD!
- Always verify EVERY resource they're requesting against YOUR resources

Consider:
1. Do you have what they're requesting? (MANDATORY CHECK - if NO, must REJECT)
2. Do you need what they're offering?
3. Is this a fair trade (consider market value)?
4. How is your relationship with them? (Current: {relationship})
5. Will this help you reach your era advancement goals?

REMEMBER: All trades must follow the gold-only rule:
- One side must be ONLY GOLD
- The other side must have NO GOLD

MARKET DYNAMICS - EVALUATING OFFERS (ERA-RELATIVE):

1. ASSESS YOUR SCARCITY RELATIVE TO YOUR ERA:
   Before deciding, check if you're ABUNDANT or SCARCE in what they're requesting:

   Compare what they want to YOUR era advancement requirements:
   - ABUNDANT = You have 4x+ your era requirement for that resource
   - COMFORTABLE = You have 2-4x your era requirement
   - LIMITED = You have 1-2x your era requirement
   - SCARCE = You have less than your era requirement

   If they want GOLD and you have ABUNDANT GOLD (4x+ era requirement):
   - You can afford to be generous, consider ACCEPTING even if slightly unfavorable
   - Example Era 1: They want 200 GOLD for 120 WOOD, you have 2500 GOLD (5x of 500) → ACCEPT (you have plenty)

   If they want GOLD and you have LIMITED/SCARCE GOLD (less than 2x era requirement):
   - Be more selective, demand better rates
   - Example Era 1: They want 300 GOLD for 180 WOOD, you have 650 GOLD (1.3x of 500) → COUNTER for 200 GOLD or REJECT

   If they want RESOURCES and you have ABUNDANT resources (4x+ era requirement):
   - You can afford to sell generously
   - Example Era 2: They want 1500 WOOD, you have 25000 WOOD (4x+ of 6000) → ACCEPT

   If they want RESOURCES and you have LIMITED/SCARCE resources (less than 2x era requirement):
   - Demand premium prices, don't undersell
   - Example Era 0: They want 30 WOOD for 40 GOLD, you have 70 WOOD (1.4x of 50) → COUNTER for 20 WOOD or demand 60 GOLD

2. ASSESS YOUR NEED:
   Check if what they're offering is CRITICAL to your advancement:

   If they're offering resources you DESPERATELY need (to advance era):
   - Be willing to pay premium or accept less favorable terms
   - Example: You need 30 WOOD for advancement, they offer 40 WOOD for 90 GOLD → ACCEPT (critical need)

   If they're offering resources you DON'T urgently need:
   - Demand better rates or REJECT
   - Example: You need WOOD but they're offering STONE → REJECT or COUNTER

3. FAIR VALUE REFERENCE (adjust based on scarcity):
   - 1 WOOD ≈ 1.5-2 GOLD (baseline)
   - 1 STONE ≈ 1.5-2 GOLD (baseline)
   - 1 FOOD ≈ 1.5-2 GOLD (baseline)
   - 1 TECHNOLOGY ≈ 2-3 GOLD (baseline)
   - 1 INFORMATION ≈ 2-3 GOLD (baseline)

   When YOU are abundant in what they want: Accept 1.2-1.5x rates (generous)
   When YOU are scarce in what they want: Demand 2-2.5x rates (premium)

4. EXAMPLES OF MARKET-AWARE RESPONSES (ERA-RELATIVE):
   ✓ GOOD (Era 0): "They want 80 GOLD for 50 WOOD. I have 300 GOLD (6x of 50 = abundant) and need WOOD urgently. Fair deal. ACCEPT."
   ✓ GOOD (Era 1): "They want 300 STONE for 400 GOLD. I have 750 STONE (1.5x of 500 = limited). This undervalues my limited supply. COUNTER for 200 STONE or 600 GOLD."
   ✓ GOOD (Era 2): "They want 2000 GOLD for 1200 WOOD. I have 7000 GOLD (1.4x of 5000 = limited) and need to save for building. REJECT."
   ✗ BAD (Era 0): "They want 50 WOOD for 60 GOLD. I have 200 WOOD (4x of 50 = abundant). REJECT." ← You're abundant, should accept or counter generously!
   ✗ BAD (Era 1): "They want 400 GOLD for 250 STONE. I have 600 GOLD (1.2x of 500 = limited). ACCEPT." ← You're limited in GOLD, should counter down!

Respond with JSON:
{{
    "decision": "ACCEPT" | "COUNTER" | "REJECT",
    "reasoning": "State what they request, what YOU have, then your decision",
    "counter_offer": {{
        "offering": {{"WOOD": 30, "STONE": 20}},
        "requesting": {{"GOLD": 50}}
    }} (only if decision is COUNTER, otherwise null)
}}

Examples of GOOD reasoning:
- "They request 100 GOLD. I have 150 GOLD and need their WOOD. Fair trade. Therefore, I will ACCEPT."
- "They request 50 WOOD. I only have 30 WOOD. I cannot complete this trade. Therefore, I will REJECT."
- "They request 80 STONE. I have 80 STONE but this is unfair (too much for 50 GOLD). Therefore, I will COUNTER."

Examples of BAD reasoning (NEVER do this):
- "Good trade, I'll accept" ← WRONG! Didn't verify you HAVE what they request!
- "I need their resources" ← WRONG! Didn't check if you can afford what they want!"""

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

BEFORE RESPONDING, VERIFY:

Step 1: What are they requesting from me? (Check their "requesting")
Step 2: Do I HAVE what they're requesting? (Compare to YOUR resources in "your_nation.resources")
Step 3: If I DON'T have enough → I MUST REJECT (cannot complete the trade)
Step 4: Is this counter-offer fair and beneficial?

CRITICAL VERIFICATION:
- If they request {{"GOLD": 100}} and you have {{"GOLD": 50}} → YOU MUST REJECT!
- If they request {{"WOOD": 50}} and you have {{"WOOD": 40}} → YOU MUST REJECT!
- Always verify EVERY resource they're requesting against YOUR resources

MARKET DYNAMICS - EVALUATING COUNTER-OFFERS (ERA-RELATIVE):

Check if the counter-offer is better or worse based on YOUR scarcity RELATIVE TO YOUR ERA:

Use these thresholds relative to your era advancement requirements:
- ABUNDANT = 4x+ era requirement
- COMFORTABLE = 2-4x era requirement
- LIMITED = 1-2x era requirement
- SCARCE = Less than era requirement

If they're asking for LESS than your original offer:
- This is better for you! Consider ACCEPTING if you can afford it
- Example Era 1: You offered 300 GOLD, they counter asking for 220 GOLD → ACCEPT

If they're asking for MORE than your original offer:
- Check YOUR scarcity: Are you ABUNDANT in what they want?
- If ABUNDANT (4x+ era requirement) → Consider ACCEPTING to close the deal
- If LIMITED/SCARCE (less than 2x era requirement) → REJECT, you can't afford premium pricing

If they're offering LESS than you requested:
- Check if you DESPERATELY need what they're offering
- If CRITICAL for era advancement → Consider ACCEPTING partial amount
- If NOT urgent → REJECT and try another partner

Examples (ERA-RELATIVE):
✓ (Era 0): "They counter with 70 GOLD for 50 WOOD (I offered 90 GOLD). I have 250 GOLD (5x of 50 = abundant). Better deal. ACCEPT."
✓ (Era 1): "They counter with 300 WOOD for 450 GOLD (I offered 350 GOLD). I have 650 GOLD (1.3x of 500 = limited). Can't afford premium. REJECT."
✗ (Era 2): "They counter with 1500 GOLD for 800 WOOD (I offered 1800 GOLD). REJECT." ← They're asking LESS gold, this is BETTER for you!

Decide whether to accept or reject this counter-offer.

Respond with JSON:
{{
    "decision": "ACCEPT" | "REJECT",
    "reasoning": "State what they request, what YOU have, then your decision"
}}

Examples of GOOD reasoning:
- "They request 80 GOLD. I have 120 GOLD and need their WOOD. Therefore, I will ACCEPT."
- "They request 50 WOOD. I only have 30 WOOD. I cannot fulfill this. Therefore, I will REJECT."

Examples of BAD reasoning (NEVER do this):
- "Fair deal, I'll accept" ← WRONG! Didn't verify you HAVE what they request!"""

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

You have TWO options:
1. Attempt the SAME trade (same offering/requesting) with a DIFFERENT partner
2. Propose a COMPLETELY DIFFERENT trade (different amounts or resources) with a DIFFERENT partner
3. Skip trading entirely

NOTE: If you set retry: false, your trading phase ends and you move to the build phase.

BEFORE RETRYING, COMPLETE THIS VERIFICATION CHECKLIST:

Step 1: Do I still HAVE what I want to offer? (Check YOUR resources - you might have traded them away)
Step 2: Does the alternative nation HAVE what I'm requesting? (Check their resources)
Step 3: If either answer is NO → set retry: false
Step 4: Follow the GOLD-ONLY RULE (one side ONLY GOLD, other side NO GOLD)

CRITICAL VERIFICATION:
- If you want to offer {{"GOLD": 100}} but you only have {{"GOLD": 50}} → DO NOT RETRY!
- If you want to request {{"WOOD": 50}} but alternative nation has {{"WOOD": 30}} → DO NOT RETRY!
- Always verify BOTH what you're offering (you must have it) AND what you're requesting (they must have it)

IMPORTANT RULES:
1. You must still HAVE what you want to offer
2. The alternative nation must HAVE what you're requesting
3. One side must be ONLY GOLD, other side NO GOLD
4. Choose wisely - consider relationships and strategic value
5. If no good alternative exists, set retry: false
6. You can propose different amounts or different resources than the rejected trade

MARKET DYNAMICS - CHOOSING BETTER PARTNERS:

Your trade was rejected. Use market dynamics to find a BETTER partner:

1. CHOOSE PARTNERS WITH MORE SUPPLY:
   Why was your trade rejected? Possibly because they didn't have enough or didn't want to trade.
   Look for nations with MORE of what you need:

   If you were BUYING resources:
   - Original partner had 80 WOOD and rejected
   - Look for nations with 150+ WOOD (more likely to accept)
   - They have abundance, more willing to sell

   If you were SELLING for GOLD:
   - Original partner had 120 GOLD and rejected
   - Look for nations with 250+ GOLD (more likely to buy)
   - They have more buying power

2. ADJUST YOUR OFFER TO BE MORE ATTRACTIVE (ERA-RELATIVE):
   If your original offer was borderline, make it MORE generous for the new partner:

   Use these thresholds relative to YOUR era advancement requirements:
   - ABUNDANT = 4x+ era requirement
   - COMFORTABLE = 2-4x era requirement
   - LIMITED = 1-2x era requirement
   - SCARCE = Less than era requirement

   If you have ABUNDANT resources (4x+ era requirement of what you're offering):
   - Increase the amount you're offering to sweeten the deal
   - Example Era 1: You have 2500 WOOD (5x of 500). Originally offered 200 WOOD for 250 GOLD → Now offer 280 WOOD for 250 GOLD

   If you have ABUNDANT GOLD (4x+ era requirement):
   - Increase your offer to ensure acceptance
   - Example Era 0: You have 250 GOLD (5x of 50). Originally offered 70 GOLD for 40 WOOD → Now offer 90 GOLD for 40 WOOD

3. CONSIDER COMPLETELY DIFFERENT TRADES:
   Maybe the market doesn't want what you're offering. Consider switching strategies:

   If you were trying to SELL resources but got rejected:
   - Maybe nobody wants to buy right now
   - Try BUYING instead if you have GOLD
   - Example: Switch from selling WOOD to buying STONE

   If you were trying to BUY but got rejected:
   - Maybe you need to get GOLD first
   - Try SELLING excess resources for GOLD instead
   - Example: Switch from buying WOOD to selling STONE for GOLD

4. EXAMPLES OF MARKET-AWARE ALTERNATIVE TRADES (ERA-RELATIVE):
   ✓ GOOD (Era 0): "Rejected by Turkey (90 WOOD). I have 250 GOLD (5x of 50 = abundant). USA has 200 WOOD (more supply). I'll offer 120 GOLD (more generous) for 60 WOOD."
   ✓ GOOD (Era 1): "Rejected by Egypt (800 GOLD). I have 2200 STONE (4.4x of 500 = abundant). Japan has 2500 GOLD (5x of 500 = more buying power). I'll sell 350 STONE for 450 GOLD."
   ✓ GOOD (Era 2): "Rejected by Norway. Nobody wants to buy WOOD. I have 7000 GOLD (1.4x of 5000 = limited). I'll switch strategy and BUY STONE from Thailand instead."
   ✗ BAD (Era 1): "Rejected by partner with 800 WOOD. New partner has 550 WOOD (less supply). I'll try them." ← Choose partners with MORE resources!
   ✗ BAD (Era 0): "I was rejected so I'll try the exact same offer with someone who has less." ← Be more generous or find better partners!

Respond with JSON:
{{
    "retry": true/false,
    "target_nation_id": <nation_id or null>,
    "offering": {{"GOLD": 100}} or {{"WOOD": 50, "STONE": 30}} (required if retry: true),
    "requesting": {{"WOOD": 50}} or {{"GOLD": 100}} (required if retry: true),
    "reasoning": "State what YOU have, what THEY have, then your decision"
}}

Examples of GOOD reasoning:
{{"retry": true, "target_nation_id": 2, "offering": {{"GOLD": 100}}, "requesting": {{"WOOD": 60}}, "reasoning": "I have 100 GOLD. USA has 80 WOOD. They can fulfill my request. Therefore, I will retry with USA."}}
{{"retry": true, "target_nation_id": 3, "offering": {{"STONE": 40}}, "requesting": {{"GOLD": 80}}, "reasoning": "I have 50 STONE. Japan has 150 GOLD. I'll sell STONE instead. Therefore, I will retry with Japan."}}
{{"retry": false, "target_nation_id": null, "offering": {{}}, "requesting": {{}}, "reasoning": "I have 0 GOLD left. I cannot offer GOLD anymore. Therefore, I will not retry."}}
{{"retry": false, "target_nation_id": null, "offering": {{}}, "requesting": {{}}, "reasoning": "No other nation has enough WOOD. Therefore, I will not retry."}}

Examples of BAD reasoning (NEVER do this):
- "I'll try with USA" ← WRONG! Didn't verify YOU have what you're offering!
- "USA has resources so I'll retry" ← WRONG! Didn't check if they have what YOU need!
- Missing "offering" or "requesting" when retry: true ← WRONG! Must specify the trade!
"""

    return prompt

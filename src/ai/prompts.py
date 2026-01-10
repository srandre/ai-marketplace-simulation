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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  REASONING MUST BE SHORT - MAXIMUM 3 SENTENCES ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DO NOT ramble. DO NOT analyze multiple options. Pick ONE and state it clearly.

CRITICAL: If you have a GENERATOR for what you're selling, MENTION IT in your reasoning!
This justifies why you can afford to sell - you'll regenerate it next turn.

Respond with JSON:
{{
    "trade": true/false,
    "target_nation_id": <nation_id or null>,
    "offering": {{"GOLD": 100}} or {{"WOOD": 50, "STONE": 30}},
    "requesting": {{"WOOD": 50, "STONE": 30}} or {{"GOLD": 100}},
    "reasoning": "MAXIMUM 3 sentences. What I have (mention generator!), what they have, decision."
}}

✓ EXCELLENT examples (SHORT, mentions generators):
- "I have 50 STONE and QUARRY (produces STONE). Belgium has 50 GOLD. Selling 30 STONE for 30 GOLD."
- "I have FARM (produces FOOD) and 100 FOOD. Egypt has 80 GOLD. Selling 50 FOOD for 60 GOLD."
- "I have MINE (produces GOLD) and 50 GOLD. Norway has 80 WOOD. Buying 50 WOOD for 50 GOLD."
- "I have 0 GOLD. Can't buy anything. Skipping."

✗ BAD examples (too long, rambles):
- "I have 50 STONE and 0 GOLD. Belgium and Pakistan have 50 GOLD each, but I cannot offer GOLD to buy resources because I have 0 GOLD. I could sell STONE for GOLD, but I have a QUARRY that produces STONE..." ← TOO LONG! You'll get confused!
- "Egypt has wood but no gold, so I'll sell stone for gold" ← WRONG! They have no gold!
- "I need resources so I'll trade" ← Didn't verify YOU have what you're offering!

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
6. Do I have any generators for the resource they're asking? If so, I should be more likely to accept, because I will generate more at the start of next turn.

REMEMBER: All trades must follow the gold-only rule:
- One side must be ONLY GOLD
- The other side must have NO GOLD

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  CRITICAL: GENERATORS DO NOT COUNT AS CURRENT RESOURCES! ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DO NOT trade for resources just because a nation has a GENERATOR!

- Generators produce resources at the START of NEXT turn
- You are trading RIGHT NOW, THIS turn
- If they have LUMBER_CAMP but "resources": {{"WOOD": 0}} → They have NO WOOD to trade RIGHT NOW!
- If they have MINE but "resources": {{"GOLD": 0}} → They have NO GOLD to trade RIGHT NOW!

ALWAYS CHECK THE "resources" FIELD, NOT THE "generators" FIELD!

Examples:
✗ BAD: "Denmark has LUMBER_CAMP (produces WOOD), so I'll trade for WOOD" ← WRONG! Check their resources!
✓ GOOD: "Denmark has 0 WOOD in resources, so they cannot fulfill my WOOD request. I will not retry."
✗ BAD: "Finland has MINE, so I'll request GOLD from them" ← WRONG! Do they have GOLD NOW?
✓ GOOD: "Finland has 50 GOLD in resources. They can fulfill my 50 GOLD request. I will retry."

CRITICAL VERIFICATION:
- If you want to offer {{"GOLD": 100}} but you only have {{"GOLD": 50}} → DO NOT RETRY!
- If you want to request {{"WOOD": 50}} but alternative nation has {{"WOOD": 30}} → DO NOT RETRY!
- If alternative nation has LUMBER_CAMP but {{"WOOD": 0}} in resources → DO NOT RETRY for WOOD!
- Always verify BOTH what you're offering (you must have it) AND what you're requesting (they must have it NOW)

IMPORTANT RULES:
1. You must still HAVE what you want to offer
2. The alternative nation must HAVE what you're requesting
3. One side must be ONLY GOLD, other side NO GOLD
4. Choose wisely - consider relationships and strategic value
5. If no good alternative exists, set retry: false
6. You can propose different amounts or different resources than the rejected trade

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
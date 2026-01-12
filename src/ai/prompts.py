"""Prompt templates for AI decision-making."""

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

        if era_idx == 0:
            # First era - list all resources
            resource_text = ", ".join([r for r in unlocked])
        else:
            # Subsequent eras - show what's newly unlocked
            prev_era = eras_sorted[era_idx - 1] if era_idx > 0 else {"unlocked_resources": []}
            prev_unlocked = set(prev_era.get("unlocked_resources", []))
            new_resources = [r for r in unlocked if r not in prev_unlocked]

            if new_resources:
                resource_text = "+ " + ", ".join(new_resources)
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
                f"- Era {era.get('index')} -> Era {next_era.get('index')} ({next_era_name_short}{win_suffix}): {reqs_text}"
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

CRITICAL - TO WIN THE GAME:
- You MUST reach {final_era_name} (highest era)
- Each era requires specific resources (see above)
- You can ONLY get resources from generators or trading
- Build the generators that produce what you need for the next era!
- Example: Need INFORMATION? Build DATACENTER. Need TECHNOLOGY? Build FACTORY.

GENERATORS (base costs - increase exponentially as more are built globally):
{generators_text}

IMPORTANT: Generator costs scale as: current_cost = base_cost * 2^(total_built_globally)
Example: If 4 MINES exist globally, the 5th costs 80 WOOD + 80 STONE (10*2^4)

CRITICAL GAME MECHANICS:

RESOURCE GENERATION TIMING:
- Generators produce resources ONLY at the START of each turn (before trading)
- During trading, you can ONLY trade resources you CURRENTLY have in your inventory
- DO NOT assume nations have resources just because they have generators
- Example: If a nation has a FARM generator but "resources": {{"FOOD": 0}}, they have NO FOOD to trade right now

TURN STRUCTURE:
1. RESOURCE GENERATION: All generators produce resources (automatic)
2. TRADING PHASE: Propose up to 2 trades using CURRENT resources only
   - Each trade MUST be between GOLD and ONE other resource only
   - If rejected, get ONE chance to retry with different/same partner
   - Can only trade what's in your "resources" inventory RIGHT NOW
3. BUILD PHASE: Build ONE generator using CURRENT resources or skip

You must respond with valid JSON only. No explanations outside the JSON structure.
MOST IMPORTANT TIP FOR PROPER GAMEPLAY: Make sure your top level decision in your JSON ("retry", "trade", "build", "decision"), 100% match the last sentence of your reasoning
Be sure to read any JSON received as VITAL information to back your decisions 

IMPORTANT:
You are operating under a strict execution contract.

If your response violates ANY rule defined here:
- The action will be rejected
- You will lose the turn
- Your nation will fall behind competitors

Your goal is not to be creative, but to produce VALID, EXECUTABLE actions that advance you toward victory."""


def _format_memory_context(nation) -> str:
    """Format nation's decision memory for inclusion in prompts."""
    memory = nation.get_memory_context(max_entries=20)

    if not memory:
        return "\n--- YOUR PREVIOUS DECISIONS ---\nNo previous decisions yet. This is your first turn.\n"

    memory_text = "\n--- YOUR PREVIOUS DECISIONS (Your Strategic Memory) ---\n"
    memory_text += "Review your past decisions to maintain strategic consistency:\n\n"

    for mem in memory:
        decision = mem.get('decision', {})
        decision_type = mem.get('type', 'unknown')

        # Format the decision in natural language based on type
        if decision_type == 'trade_proposal':
            offering = decision.get('offering', {})
            requesting = decision.get('requesting', {})
            target_name = decision.get('target_nation_name', decision.get('target_nation_id', 'unknown'))

            # Format resources
            offering_str = ", ".join([f"{res}={amt}" for res, amt in offering.items()]) if offering else "nothing"
            requesting_str = ", ".join([f"{res}={amt}" for res, amt in requesting.items()]) if requesting else "nothing"

            # Determine if buying or selling
            if 'GOLD' in offering:
                action = f"BUY {requesting_str} from {target_name} for {offering_str}"
            elif 'GOLD' in requesting:
                action = f"SELL {offering_str} to {target_name} for {requesting_str}"
            else:
                action = f"Trade {offering_str} with {target_name} for {requesting_str}"

            decision_str = f"Attempted to {action}"

        elif decision_type == 'trade_response':
            decision_val = decision.get('decision', 'UNKNOWN')
            reasoning = decision.get('reasoning', '')
            if reasoning:
                decision_str = f"{decision_val} a trade offer ({reasoning})"
            else:
                decision_str = f"{decision_val} a trade offer"

        elif decision_type == 'build':
            if decision.get('build'):
                gen_type = decision.get('generator_type', 'unknown')
                payment_res = decision.get('payment_resource')
                if payment_res:
                    decision_str = f"Built {gen_type} (paid with {payment_res})"
                else:
                    decision_str = f"Built {gen_type}"
            else:
                decision_str = "Skipped building (couldn't afford or chose not to)"

        elif decision_type == 'alternative_trade':
            if decision.get('retry'):
                offering = decision.get('offering', {})
                requesting = decision.get('requesting', {})
                target_name = decision.get('target_nation_name', decision.get('target_nation_id', 'unknown'))

                offering_str = ", ".join([f"{res}={amt}" for res, amt in offering.items()]) if offering else "nothing"
                requesting_str = ", ".join([f"{res}={amt}" for res, amt in requesting.items()]) if requesting else "nothing"

                if 'GOLD' in offering:
                    action = f"BUY {requesting_str} from {target_name} for {offering_str}"
                elif 'GOLD' in requesting:
                    action = f"SELL {offering_str} to {target_name} for {requesting_str}"
                else:
                    action = f"Trade {offering_str} with {target_name} for {requesting_str}"

                decision_str = f"Retried trade: {action}"
            else:
                decision_str = "Gave up on finding alternative trade partner"
        else:
            # Fallback for unknown decision types - try to extract meaningful info
            if isinstance(decision, dict):
                reasoning = decision.get('reasoning', '')
                if reasoning:
                    decision_str = f"Decision: {reasoning}"
                else:
                    # Try to format the dict nicely
                    parts = []
                    for key, val in decision.items():
                        if key != 'reasoning' and val:
                            parts.append(f"{key}={val}")
                    if parts:
                        decision_str = f"Decision: {', '.join(parts)}"
                    else:
                        decision_str = f"Decision type '{decision_type}' (details unknown)"
            else:
                decision_str = f"Decision: {decision}"

        memory_text += f"Round {mem['round']}, Turn {mem['turn']}: {decision_str}\n"

        # Add outcome if available
        if mem.get('outcome'):
            outcome = mem['outcome']
            if 'Trade invalid' in outcome:
                memory_text += f"  Result: FAILED - {outcome}\n"
            elif 'Trade accepted' in outcome or 'Trade executed' in outcome:
                memory_text += f"  Result: SUCCESS - {outcome}\n"
            elif 'Trade rejected' in outcome:
                memory_text += f"  Result: REJECTED - {outcome}\n"
            else:
                memory_text += f"  Result: {outcome}\n"

        memory_text += "\n"

    memory_text += "--- END PREVIOUS DECISIONS ---\n"
    memory_text += "Use this history to inform your current strategy and maintain consistency.\n"
    return memory_text


def _format_resources_natural(resources: Dict[str, int]) -> str:
    """Format resources as natural language, showing all resources including zeros."""
    parts = []
    for res, amt in resources.items():
        parts.append(f"{res}={amt}")
    return ", ".join(parts) if parts else "No resources"


def create_trading_phase_prompt(
    nation: Nation,
    game_state: Dict[str, Any],
    era_requirements: Dict[str, int],
    trades_completed: int = 0,
) -> str:
    """Create prompt for the trading phase (up to 2 trades)."""

    # Build natural language game state summary

    # Your nation info - format like other nations for consistency
    your_res_dict = nation.inventory.to_dict()

    # List what YOU have NOW (tradeable) - show all resources including zeros
    your_tradeable = []
    for res, amt in your_res_dict.items():
        your_tradeable.append(f"{res}={amt}")

    your_has_now = ", ".join(your_tradeable) if your_tradeable else "No resources"

    # List YOUR generators and what they produce
    your_gen_parts = []
    for g in nation.generators:
        gen_type = g.generator_type.value
        produces = g.produces.value
        your_gen_parts.append(f"{gen_type} -> {produces} next turn")

    if your_gen_parts:
        your_generators = ", ".join(your_gen_parts)
    else:
        your_generators = "None"

    # Goal info
    goal_parts = []
    for res, amt in era_requirements.items():
        current = nation.inventory.get(res)
        status = "[OK]" if current >= amt else "[X]"
        goal_parts.append(f"{res}={amt} {status}")
    goal_str = ", ".join(goal_parts)

    # Other nations info - show resources, generators, AND relationship
    other_nations_lines = []
    for other in game_state.get("nations", []):
        if other["id"] != nation.id:
            name = other["name"]
            other_id = other["id"]
            resources = other["resources"]
            generators = other.get("generators", [])

            # Get relationship with this nation
            relationship = nation.get_relationship(other_id)
            if relationship > 0:
                rel_str = f"+{relationship}"
            elif relationship < 0:
                rel_str = f"{relationship}"
            else:
                rel_str = "0"

            # Show only non-zero resources
            has_parts = []
            for res, amt in resources.items():
                if amt > 0:
                    has_parts.append(f"{res}={amt}")

            # Show generators
            gen_parts = []
            for gen in generators:
                gen_type = gen.get("type", "")
                gen_parts.append(gen_type)

            # Build the line
            if has_parts and gen_parts:
                has_str = ", ".join(has_parts)
                gen_str = ", ".join(gen_parts)
                other_nations_lines.append(f"  -{name} (REL:{rel_str}) HAS: {has_str} | GENERATORS: {gen_str}")
            elif has_parts:
                has_str = ", ".join(has_parts)
                other_nations_lines.append(f"  -{name} (REL:{rel_str}) HAS: {has_str} | GENERATORS: None")
            elif gen_parts:
                gen_str = ", ".join(gen_parts)
                other_nations_lines.append(f"  -{name} (REL:{rel_str}) HAS: NOTHING (cannot trade) | GENERATORS: {gen_str}")
            else:
                other_nations_lines.append(f"  -{name} (REL:{rel_str}) HAS: NOTHING (cannot trade) | GENERATORS: None")

    other_nations_str = "\n".join(other_nations_lines) if other_nations_lines else "  (No other nations)"

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

================================================================================
CRITICAL TRADING RULES - READ FIRST OR YOUR TRADE WILL BE REJECTED:
================================================================================

ALL TRADES MUST FOLLOW THIS FORMAT:
  GOLD <-> ONE RESOURCE

VALID TRADES (one side is GOLD, other side is ONE resource):
  [OK] Offer GOLD -> Request WOOD
  [OK] Offer GOLD -> Request STONE
  [OK] Offer WOOD -> Request GOLD
  [OK] Offer STONE -> Request GOLD

INVALID TRADES (will be REJECTED):
  [INVALID] Offer STONE -> Request WOOD (NO GOLD - INVALID!)
  [INVALID] Offer WOOD -> Request FOOD (NO GOLD - INVALID!)
  [INVALID] Offer GOLD -> Request WOOD + STONE (multiple resources - INVALID!)
  [INVALID] Offer WOOD + STONE -> Request GOLD (multiple resources - INVALID!)

IF YOU DON'T HAVE GOLD: You MUST sell a resource FOR gold first!
IF YOU HAVE GOLD: You can buy resources WITH gold!

================================================================================

CRITICAL - VERIFY RESOURCES BEFORE TRADING:
GENERATOR != HAVING THE RESOURCE RIGHT NOW!

When BUYING (you offer GOLD -> request RESOURCES):
1. Check YOUR resources: Do I have enough GOLD?
2. Check TARGET's resources: Does target have enough WOOD/STONE/FOOD?
3. Example: Indonesia has LUMBER_CAMP but resources.WOOD = 0 -> CANNOT buy WOOD (trade fails!)

When SELLING (you offer RESOURCES -> request GOLD):
1. Check YOUR resources: Do I have enough WOOD/STONE/FOOD?
2. Check TARGET's resources: Does target have enough GOLD?
3. Example: Egypt has MINE but resources.GOLD = 0 -> CANNOT sell to Egypt (trade fails!)

RELATIONSHIP SYSTEM (MANDATORY DECISION RULE):

- Relationship directly affects WHICH nations you are allowed to trade with.
- You MUST consider relationship when choosing a target nation.

RELATIONSHIP-INFLUENCED TRADE PROPOSALS (MANDATORY):

When PROPOSING a trade, relationship affects HOW FAIR the offer should be:

- REL >= +1:
  * You may propose efficient or slightly aggressive trades
  * The partner is more tolerant of imbalance

- REL = 0:
  * Propose FAIR or balanced trades
  * Avoid clearly one-sided offers

- REL <= -1:
  * Propose GENEROUS trades if you want acceptance
  * Or avoid proposing unless necessary

Relationship does NOT change trade legality,
but it DOES change how cautious or generous your offer must be.

STRATEGIC IMPORTANCE OF RELATIONSHIP (CRITICAL):

- Relationship is a LONG-TERM STRATEGIC RESOURCE.
- Higher relationship leads to:
  * Higher chance of future trade acceptance
  * Better access to scarce resources in later eras
  * Reduced trade friction over time

- ACCEPTING a reasonable trade to improve relationship
  can be BETTER than rejecting for short-term efficiency.

- You should actively SEEK to improve relationships,
  especially in early eras.

RELATIONSHIP CONSTRAINTS:
- REL >= +1: Preferred trade partners (actively choose them when possible)
- REL = 0: Neutral partners (allowed only if no positive-REL option exists)
- REL <= -1: Hostile partners (AVOID unless NO other valid option exists)

CRITICAL:
- If a nation with REL:+1 or higher has the resource you want,
  you MUST choose them over any REL:0 or REL:-1 nation.
- Ignoring relationship when selecting a partner is INVALID reasoning.


TRADE ACCEPTANCE TIP - PRIORITIZE NATIONS WITH MATCHING GENERATORS:
Nations with generators are MORE LIKELY to accept trades because they regenerate resources.

GENERATOR -> RESOURCE MAPPING (MEMORIZE THIS - DO NOT MIX THEM UP):
- MINE -> produces GOLD (NOT STONE, NOT WOOD)
- LUMBER_CAMP -> produces WOOD (NOT STONE, NOT GOLD)
- QUARRY -> produces STONE (NOT WOOD, NOT GOLD)
- FARM -> produces FOOD (NOT any other resource)
- FACTORY -> produces TECHNOLOGY
- DATACENTER -> produces INFORMATION

CRITICAL - MATCH GENERATOR TO RESOURCE YOU'RE REQUESTING:
- Requesting GOLD? -> PREFER nations with MINE in their GENERATORS
- Requesting WOOD? -> PREFER nations with LUMBER_CAMP in their GENERATORS
- Requesting STONE? -> PREFER nations with QUARRY in their GENERATORS
- Requesting FOOD? -> PREFER nations with FARM in their GENERATORS

If MULTIPLE nations have the resource, CHOOSE THE ONE WITH:
1. The MATCHING GENERATOR for that resource (they'll regenerate it)
2. POSITIVE relationship with you (more likely to accept)

WARNING: Do NOT mention a generator unless it PRODUCES what you're requesting!
WRONG: "Singapore has QUARRY, likely to accept WOOD trade" (QUARRY produces STONE, not WOOD!)
CORRECT: "Singapore has QUARRY, likely to accept STONE trade" (QUARRY produces STONE!)

CRITICAL - DON'T REPEAT FAILED TRADES:
- Check "YOUR PREVIOUS DECISIONS" section below
- If you see "Trade invalid" -> That trade violated the rules OR that nation lacks resources!
- If the reason was "NO GOLD" -> You tried to trade resource-for-resource (INVALID!)
- DON'T propose the same INVALID trade structure again
- Try a VALID trade: Either sell your resource FOR GOLD, or buy with GOLD

CRITICAL - DON'T DOUBLE-SPEND YOUR RESOURCES:
- If you already traded in this turn, your resources have changed!
- Check "your_nation.resources" carefully - these are your CURRENT resources
- Example: You had 100 GOLD, spent 50 on first trade -> Now you have 50 GOLD
- DON'T try to spend the same resources twice!

================================================================================
MANDATORY DECISION PROCESS (DO NOT SKIP ANY STEP):
================================================================================

Step 0: CHECK YOUR GOLD STATUS:
  - Look at YOUR resources (HAS NOW section above)
  - Do you have GOLD?
    -> YES: You can BUY resources (offer GOLD, request resource)
    -> NO: You MUST SELL resources (offer resource, request GOLD)

Step 1: Look at "OTHER NATIONS" list below
Step 2: Find nations that HAVE the resource I want to REQUEST in their HAS field
Step 3: CRITICAL: Nation MUST have the resource listed in HAS section (not just the generator!)
Step 4: If multiple nations have it, PREFER the one with the matching GENERATOR
Step 5: Pick ONE nation from that list
Step 6: VERIFY that nation has what you're requesting (CRITICAL!)
Step 7: READ their GENERATORS list to see EXACTLY which generators they have
Step 8: Write reasoning mentioning what they have AND what you're requesting
Step 9: Set target_nation_name to THAT EXACT SAME name
Step 10: FINAL CHECK - Does your trade have GOLD on one side? If NO, it's INVALID!

EXAMPLE (when you have NO GOLD - must SELL for GOLD):
- Step 0: Check my resources -> I have STONE=100, GOLD=0 -> I MUST SELL for GOLD
- I want GOLD
- I see: "Portugal HAS: GOLD=50 | GENERATORS: MINE"
- VERIFY: Portugal HAS GOLD=50 [OK] in HAS section AND GENERATORS shows MINE [OK]
- I write reasoning: "Portugal has GOLD=50 and MINE generator. Selling STONE for GOLD."
- I set: "target_nation_name": "Portugal"
- I set: "offering": {{"STONE": 50}}
- I set: "requesting": {{"GOLD": 50}}
- Final check: GOLD is on one side [OK] -> VALID TRADE

WRONG EXAMPLE (DO NOT DO THIS):
- I want WOOD but I have NO GOLD
- I see: "Indonesia HAS: WOOD=50 | GENERATORS: LUMBER_CAMP"
- I set: "offering": {{"STONE": 50}}, "requesting": {{"WOOD": 50}}
- Final check: GOLD on one side? NO! -> INVALID TRADE - WILL BE REJECTED!
- CORRECT: Sell STONE for GOLD first, THEN buy WOOD with GOLD next turn!

CRITICAL: If reasoning says "Germany has STONE" but you request GOLD, the trade WILL FAIL!
Your reasoning MUST mention the EXACT resource you're requesting from them!
DO NOT mention one nation in reasoning and put a different nation in target_nation_name!

Respond with JSON (reasoning: EXACTLY 2 sentences):

Sentence 1: State what the target nation HAS and the resource you are requesting.
Sentence 2: Explain why this trade is appropriate given your relationship level.

If relationship is NOT mentioned explicitly in sentence 2, the trade is INVALID.

Respond with JSON (reasoning: 2 sentences):
{{
    "reasoning": "Selling WOOD to Portugal for GOLD=50.",
    "trade": true/false,
    "target_nation_name": "Portugal",
    "offering": {{"WOOD": 50}},
    "requesting": {{"GOLD": 50}}
}}

CRITICAL: offering and requesting MUST each contain EXACTLY ONE resource type!
- Valid: {{"GOLD": 50}} or {{"WOOD": 50}}
- INVALID: {{"GOLD": 50, "WOOD": 30}} or {{"WOOD": 50, "STONE": 30}}

________________________________________________________________________________
CURRENT GAME STATE:

YOUR NATION: {nation.name}
  HAS NOW: {your_has_now}
  GENERATORS: {your_generators}

YOUR GOAL: Advance to Era {nation.era.value + 1}
  Requirements: {goal_str}

________________________________________________________________________________
OTHER NATIONS (Check resources AND generators):
________________________________________________________________________________
{other_nations_str}

CRITICAL: Only these resources listed above are available for trading RIGHT NOW!
TIP: Nations with GENERATORS for the resource you're requesting are MORE LIKELY to accept!

{memory_context}
{complement_note}
________________________________________________________________________________"""

    return prompt


def create_build_phase_prompt(
    nation: Nation,
    game_state: Dict[str, Any],
    era_requirements: Dict[str, int],
) -> str:
    """Create prompt for the build phase (build one generator or skip)."""

    # Format your nation
    your_res = _format_resources_natural(nation.inventory.to_dict())
    your_gens = []
    for g in nation.generators:
        your_gens.append(f"{g.generator_type.value} (->{g.generation_amount} {g.produces.value}/turn)")
    your_gens_str = ", ".join(your_gens) if your_gens else "None"

    # Format goal
    goal_parts = []
    for res, amt in era_requirements.items():
        current = nation.inventory.get(res)
        status = "[OK]" if current >= amt else "[X]"
        goal_parts.append(f"{res}={amt} {status}")
    goal_str = ", ".join(goal_parts)

    # Format generator costs
    costs_lines = []
    for gen_name, cost_data in game_state.get("generator_costs", {}).items():
        if "cost_either" in cost_data:
            # FARM case
            options = [f"{amt} {res}" for res, amt in cost_data["cost_either"].items()]
            cost_str = " OR ".join(options)
        else:
            parts = [f"{amt} {res}" for res, amt in cost_data.items()]
            cost_str = " + ".join(parts)
        costs_lines.append(f"  {gen_name}: {cost_str}")
    costs_str = "\n".join(costs_lines)

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""
BUILD PHASE

Build ONE generator or skip.

CRITICAL AFFORDABILITY CHECK (do this FIRST):

Step 1: Look at YOUR RESOURCES (see "Current Resources" below)
Step 2: Look at GENERATOR COSTS (see "GENERATOR COSTS (current prices)" section below)
Step 3: For EACH generator in the list, check if you can afford it:

HOW TO CHECK AFFORDABILITY:
- Compare YOUR resources to what the generator costs
- You need EVERY resource listed in the cost
- Example: If QUARRY costs "40 WOOD", you need >=40 WOOD
- Example: If MINE costs "80 STONE + 80 WOOD", you need >=80 STONE AND >=80 WOOD (BOTH!)
- Example: If FARM costs "80 WOOD OR 80 STONE", you need >=80 of either one (not both)

STEP-BY-STEP PROCESS:
1. Look at first generator in GENERATOR COSTS list below
2. Check: Do I have enough of EACH resource it requires?
3. If YES -> I CAN BUILD IT! Set build: true, generator_type: "NAME"
4. If NO -> Check next generator
5. If none affordable -> build: false, generator_type: null

Example 1: I have WOOD=50, STONE=0, and QUARRY costs "40 WOOD"
- QUARRY needs 40 WOOD -> I have 50 WOOD -> YES, I CAN BUILD QUARRY!

Example 2: I have WOOD=50, STONE=0, and MINE costs "80 STONE + 80 WOOD"
- MINE needs 80 STONE AND 80 WOOD -> I only have 50 WOOD and 0 STONE -> NO, CANNOT BUILD

Example 3: I have WOOD=100, STONE=0, and FARM costs "80 WOOD OR 80 STONE"
- FARM needs 80 WOOD OR 80 STONE -> I have 100 WOOD -> YES, I CAN BUILD FARM!

STOP! Before you skip building, read this:
"I need to save resources for trading" = WRONG THINKING!
Generators produce FOREVER. Trading gets you resources ONCE.
If you can afford ANY generator, BUILD IT! The resources you spend come back next turn PLUS you have the generator forever.

Example: You have 50 WOOD. QUARRY costs 40 WOOD.
BAD: "Skip building to save 50 WOOD for trading"
GOOD: "Build QUARRY! I'll have 10 WOOD left + 50 STONE/turn forever. I can trade the STONE next turn!"

CRITICAL - REASONING MUST MATCH DECISION:
- If reasoning says "cannot afford" -> build MUST be false
- If reasoning says "building" -> build MUST be true
- If reasoning says "skipping" -> build MUST be false
- NO contradictions allowed!

RULES:
- For FARM: specify payment_resource (WOOD or STONE)
- For all others: payment_resource must be null

STRATEGY - BUILDING IS ESSENTIAL (THINK LONG-TERM):
- Generators produce FOREVER - they pay back their cost in <1 turn, then infinite free resources!
- Example: QUARRY costs 40 WOOD, produces 50 STONE/turn -> Pays back in <1 turn, then FREE STONE FOREVER
- DON'T hoard resources! Spending 40 WOOD to get 50 STONE/turn forever is ALWAYS worth it!
- You can always trade to get more resources, but generators are permanent income!

CRITICAL MATH:
- If you have 50 WOOD and QUARRY costs 40 WOOD:
  BUILD IT! You'll have 10 WOOD left + 50 STONE/turn starting next turn
  DON'T skip to "save" the 50 WOOD - you're losing infinite STONE!

Priority order when multiple options available:
  1. MINE (produces GOLD - needed for ALL trades)
  2. Generator that produces what you need for next era
  3. Any other generator you can afford (free resources are always good!)

WHAT TO BUILD:
- Need GOLD for trading? -> Build MINE (costs 5 WOOD + 5 STONE)
- Need WOOD? -> Build LUMBER_CAMP (costs 10 STONE)
- Need STONE? -> Build QUARRY (costs 10 WOOD)
- Need FOOD? -> Build FARM (costs 10 WOOD or 10 STONE)

Respond with JSON (reasoning: 2 sentences):
{{
    "reasoning": "What I have, what it costs, decision." (this should ABSOLUTELY match what's answered in the other properties),
    "build": true/false,
    "generator_type": "LUMBER_CAMP" | "QUARRY" | "FARM" | "MINE" | "FACTORY" | "DATACENTER" | null,
    "payment_resource": "WOOD" | "STONE" | null (for FARM only)
}}

________________________________________________________________________________
CURRENT GAME STATE:

YOUR NATION: {nation.name}
  Current Resources: {your_res}
  Current Generators: {your_gens_str}

YOUR GOAL: Advance to Era {nation.era.value + 1}
  Requirements: {goal_str}

GENERATOR COSTS (current prices):
{costs_str}

{memory_context}
________________________________________________________________________________"""

    return prompt

def create_trade_response_prompt(
    nation: Nation,
    proposer_nation: Dict[str, Any],
    offer: Dict[str, Any],
    game_state: Dict[str, Any],
) -> str:
    """Create prompt for responding to a trade offer."""

    relationship = nation.get_relationship(proposer_nation["id"])

    # Format your nation
    your_res = _format_resources_natural(nation.inventory.to_dict())
    your_gens = []
    for g in nation.generators:
        your_gens.append(f"{g.generator_type.value} (->{g.generation_amount} {g.produces.value}/turn)")
    your_gens_str = ", ".join(your_gens) if your_gens else "None"

    # Format what they're offering and requesting
    offering_parts = [f"{amt} {res}" for res, amt in offer.get('offering', {}).items()]
    offering_str = ", ".join(offering_parts) if offering_parts else "Nothing"

    requesting_parts = [f"{amt} {res}" for res, amt in offer.get('requesting', {}).items()]
    requesting_str = ", ".join(requesting_parts) if requesting_parts else "Nothing"

    # Add memory context
    memory_context = _format_memory_context(nation)

    # Format relationship
    if relationship > 0:
        rel_str = f"+{relationship}"
        rel_note = "positive relationship - more inclined to accept"
    elif relationship < 0:
        rel_str = f"{relationship}"
        rel_note = "negative relationship - less inclined to accept"
    else:
        rel_str = "0"
        rel_note = "neutral relationship"

    prompt = f"""TRADE OFFER RECEIVED from {proposer_nation['name']} (REL:{rel_str})

They offer you: {offering_str}
They request from you: {requesting_str}

RELATIONSHIP CONTEXT:
- Your relationship with {proposer_nation['name']}: {rel_str} ({rel_note})
- Successful trade will increase relationship by +1
- Rejected trade will decrease relationship by -1

STRATEGIC IMPORTANCE OF RELATIONSHIP (CRITICAL):

- Relationship is a LONG-TERM STRATEGIC RESOURCE.
- Higher relationship leads to:
  * Higher chance of future trade acceptance
  * Better access to scarce resources in later eras
  * Reduced trade friction over time

- ACCEPTING a reasonable trade to improve relationship
  can be BETTER than rejecting for short-term efficiency.

- You should actively SEEK to improve relationships,
  especially in early eras.

RULES:
- You MUST have what they request (check your current resources below)
- If you lack ANY requested resource -> REJECT
- Resources are ALWAYS useful (for future eras, generators, other trades)
- Consider relationship when making borderline decisions

RELATIONSHIP-INFLUENCED EVALUATION (MANDATORY):

Evaluate the trade in this order:

1. Can I afford what they request without blocking era advancement?
   - If NO → REJECT (regardless of relationship)

2. Does the trade provide immediate or future value?
   - Resources, flexibility, or regeneration potential

3. Apply relationship as a modifier:
   - REL >= +1: Be more tolerant of low-efficiency trades
   - REL = 0: Require fair or neutral value
   - REL <= -1: Require clearly favorable value

Relationship ADJUSTS how good the trade must be,
but does NOT replace economic reasoning.

CRITICAL (NON-FORCING RULE):

- Relationship MUST influence the decision,
  but MUST NEVER force ACCEPT or REJECT by itself.

- Strategic viability ALWAYS comes first.
- Relationship acts as a WEIGHT, not a rule.


If you have a generator for what they request,
the cost is reduced because the resource will regenerate,
making acceptance MORE LIKELY.
- They want GOLD and you have MINE? -> ACCEPT (you'll regenerate GOLD next turn)
- They want WOOD and you have LUMBER_CAMP? -> ACCEPT (you'll regenerate WOOD next turn)
- They want STONE and you have QUARRY? -> ACCEPT (you'll regenerate STONE next turn)
- They want FOOD and you have FARM? -> ACCEPT (you'll regenerate FOOD next turn)
- They want TECHNOLOGY and you have FACTORY? -> ACCEPT (you'll regenerate TECHNOLOGY next turn)
- They want INFORMATION and you have DATACENTER? -> ACCEPT (you'll regenerate INFORMATION next turn)

Only REJECT if:
- You don't have what they request, OR
- You can't spare it (need for era requirements) and don't have a generator for it (you won't get it back)

Respond with JSON (reasoning: 2 sentences):

Sentence 1: Evaluate the trade economically (cost, regeneration, era needs).
Sentence 2: Explain how relationship influences your tolerance or risk assessment,
            without presenting it as the sole deciding factor.

IMPORTANT:
- Never accept a trade ONLY because of relationship.
- Never reject a viable trade ONLY because of relationship.
- Relationship refines judgment, it does not replace it.

Respond with JSON (reasoning: 2 sentences):
{{
    "reasoning": "They request X. I have [amount] and [GENERATOR]. Accepting/Rejecting." (this should ABSOLUTELY match what's answered in the other properties),
    "decision": "ACCEPT" | "REJECT"
}}

________________________________________________________________________________
CURRENT SITUATION:

YOUR NATION: {nation.name}
  Current Resources: {your_res}
  Your Generators: {your_gens_str}

TRADE OFFER:
  They give you: {offering_str}
  They want from you: {requesting_str}

{memory_context}
________________________________________________________________________________"""

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

    # Format your resources
    your_res = _format_resources_natural(nation.inventory.to_dict())

    # Format what you tried to trade
    offering_parts = [f"{amt} {res}" for res, amt in original_offering.items()]
    offering_str = ", ".join(offering_parts) if offering_parts else "Nothing"

    requesting_parts = [f"{amt} {res}" for res, amt in original_requesting.items()]
    requesting_str = ", ".join(requesting_parts) if requesting_parts else "Nothing"

    # Format alternative partners - show resources, generators, AND relationship
    alt_lines = []
    for other in other_nations:
        name = other["name"]
        other_id = other["id"]
        resources = other["resources"]
        generators = other.get("generators", [])

        # Get relationship with this nation
        relationship = nation.get_relationship(other_id)
        if relationship > 0:
            rel_str = f"+{relationship}"
        elif relationship < 0:
            rel_str = f"{relationship}"
        else:
            rel_str = "0"

        # Show only non-zero resources
        has_parts = []
        for res, amt in resources.items():
            if amt > 0:
                has_parts.append(f"{res}={amt}")

        # Show generators
        gen_parts = []
        for gen in generators:
            gen_type = gen.get("type", "")
            gen_parts.append(gen_type)

        # Build the line
        if has_parts and gen_parts:
            has_str = ", ".join(has_parts)
            gen_str = ", ".join(gen_parts)
            alt_lines.append(f"  -{name} (REL:{rel_str}) HAS: {has_str} | GENERATORS: {gen_str}")
        elif has_parts:
            has_str = ", ".join(has_parts)
            alt_lines.append(f"  -{name} (REL:{rel_str}) HAS: {has_str} | GENERATORS: None")
        elif gen_parts:
            gen_str = ", ".join(gen_parts)
            alt_lines.append(f"  -{name} (REL:{rel_str}) HAS: NOTHING (cannot trade) | GENERATORS: {gen_str}")
        else:
            alt_lines.append(f"  -{name} (REL:{rel_str}) HAS: NOTHING (cannot trade) | GENERATORS: None")

    alt_str = "\n".join(alt_lines) if alt_lines else "  (No alternatives available)"

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""TRADE REJECTED by {rejected_nation_name}

OPTIONS:
1. Try SAME trade with different partner
2. Try DIFFERENT trade with different partner
3. Skip (retry: false) -> ends trading phase

================================================================================
CRITICAL TRADING RULES - READ FIRST OR YOUR TRADE WILL BE REJECTED:
================================================================================

ALL TRADES MUST FOLLOW THIS FORMAT:
  GOLD <-> ONE RESOURCE

VALID TRADES:
  [OK] Offer GOLD -> Request WOOD
  [OK] Offer WOOD -> Request GOLD

INVALID TRADES (will be REJECTED):
  [INVALID] Offer STONE -> Request WOOD (NO GOLD - INVALID!)
  [INVALID] Offer WOOD -> Request FOOD (NO GOLD - INVALID!)
  [INVALID] Offer GOLD -> Request WOOD + STONE (multiple resources - INVALID!)

IF YOU DON'T HAVE GOLD: Sell a resource FOR gold!
IF YOU HAVE GOLD: Buy resources WITH gold!

================================================================================

CRITICAL: Check the HAS field, NOT just the GENERATORS field!
- Generators produce NEXT turn, not now
- Having a generator DOES NOT mean they have the resource NOW
- Example: "United States HAS: GOLD=50, STONE=10 | GENERATORS: LUMBER_CAMP"
  -> They have LUMBER_CAMP BUT NO WOOD RIGHT NOW (WOOD not in HAS section)
  -> You CANNOT trade with them for WOOD!

CRITICAL - DON'T DOUBLE-SPEND:
- Your resources shown above are CURRENT (after first trade)
- Example: You spent 50 GOLD on first trade -> resources now shows remaining GOLD
- DON'T try to offer resources you already spent!

================================================================================
MANDATORY DECISION PROCESS:
================================================================================

Step 1: Look at "ALTERNATIVE PARTNERS" list below
Step 2: Find nations that HAVE the resource I want to REQUEST in their HAS field
Step 3: CRITICAL: Nation MUST have the resource listed in HAS section (not just the generator!)
Step 4: If multiple nations have it, PREFER the one with the matching GENERATOR
Step 5: Pick ONE nation from that list
Step 6: VERIFY that nation has what you're requesting (CRITICAL!)
Step 7: READ their GENERATORS list to see EXACTLY which generators they have
Step 8: Write reasoning mentioning what you're requesting from them
Step 9: Set target_nation_name to THAT EXACT SAME name

EXAMPLE:
- I want WOOD
- I see: "Ireland HAS: GOLD=50, WOOD=10 | GENERATORS: LUMBER_CAMP, QUARRY"
- VERIFY: Ireland HAS WOOD=10 ✓ AND GENERATORS shows LUMBER_CAMP ✓
- I write reasoning: "Ireland has WOOD=10 and LUMBER_CAMP. Retrying for WOOD."
- I set: "target_nation_name": "Ireland"
- I set: "requesting": {{"WOOD": 10}}

WRONG EXAMPLE (DO NOT DO THIS):
- I want WOOD
- I see: "United States HAS: GOLD=50, STONE=10 | GENERATORS: MINE, LUMBER_CAMP"
- I write: "United States has WOOD and LUMBER_CAMP" <- WRONG! HAS section shows NO WOOD!

CRITICAL RELATIONSHIP FILTER:

- When selecting an alternative partner, you MUST apply the same relationship constraints:
  * Prefer REL:+1 or higher
  * Use REL:0 only if no positive option exists
  * Avoid REL:-1 or lower unless absolutely necessary

STRATEGIC IMPORTANCE OF RELATIONSHIP (CRITICAL):

- Relationship is a LONG-TERM STRATEGIC RESOURCE.
- Higher relationship leads to:
  * Higher chance of future trade acceptance
  * Better access to scarce resources in later eras
  * Reduced trade friction over time

- ACCEPTING a reasonable trade to improve relationship
  can be BETTER than rejecting for short-term efficiency.

- You should actively SEEK to improve relationships,
  especially in early eras.


If you retry with a nation that has a WORSE relationship than an available alternative,
the retry is INVALID.

CRITICAL: Your reasoning MUST mention the resource you're requesting!
WARNING: The nation name in reasoning MUST EXACTLY match target_nation_name!

Respond with JSON (reasoning: 2 sentences):
{{
    "reasoning": "Retrying with France for GOLD=50.",
    "retry": true/false,
    "target_nation_name": "France",
    "offering": {{"WOOD": 50}},
    "requesting": {{"GOLD": 50}}
}}

CRITICAL: offering and requesting MUST each contain EXACTLY ONE resource type!
- Valid: {{"GOLD": 50}} or {{"WOOD": 50}}
- INVALID: {{"GOLD": 50, "WOOD": 30}} or {{"WOOD": 50, "STONE": 30}}

________________________________________________________________________________
CURRENT SITUATION:

YOUR NATION: {nation.name}
  Current Resources: {your_res}

REJECTED TRADE:
  You offered: {offering_str}
  You requested: {requesting_str}

ALTERNATIVE PARTNERS (check their resources!):
{alt_str}

{memory_context}
________________________________________________________________________________"""

    return prompt
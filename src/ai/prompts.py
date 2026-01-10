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

CRITICAL - TO WIN THE GAME:
- You MUST reach {final_era_name} (highest era)
- Each era requires specific resources (see above)
- You can ONLY get resources from generators or trading
- Build the generators that produce what you need for the next era!
- Example: Need INFORMATION? Build DATACENTER. Need TECHNOLOGY? Build FACTORY.

GENERATORS (base costs - increase exponentially as more are built globally):
{generators_text}

IMPORTANT: Generator costs scale as: current_cost = base_cost × 2^(total_built_globally)
Example: If 4 MINES exist globally, the 5th costs 80 WOOD + 80 STONE (10×2^4)

CRITICAL GAME MECHANICS:

RESOURCE GENERATION TIMING:
- Generators produce resources ONLY at the START of each turn (before trading)
- During trading, you can ONLY trade resources you CURRENTLY have in your inventory
- DO NOT assume nations have resources just because they have generators
- Example: If a nation has a FARM generator but "resources": {{"FOOD": 0}}, they have NO FOOD to trade right now

TURN STRUCTURE:
1. RESOURCE GENERATION: All generators produce resources (automatic)
2. TRADING PHASE: Propose up to 2 trades using CURRENT resources only
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
            target_id = decision.get('target_nation_id')

            # Format resources
            offering_str = ", ".join([f"{res}={amt}" for res, amt in offering.items()]) if offering else "nothing"
            requesting_str = ", ".join([f"{res}={amt}" for res, amt in requesting.items()]) if requesting else "nothing"

            # Determine if buying or selling
            if 'GOLD' in offering:
                action = f"BUY {requesting_str} from nation {target_id} for {offering_str}"
            elif 'GOLD' in requesting:
                action = f"SELL {offering_str} to nation {target_id} for {requesting_str}"
            else:
                action = f"Trade {offering_str} with nation {target_id} for {requesting_str}"

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
                target_id = decision.get('target_nation_id')

                offering_str = ", ".join([f"{res}={amt}" for res, amt in offering.items()]) if offering else "nothing"
                requesting_str = ", ".join([f"{res}={amt}" for res, amt in requesting.items()]) if requesting else "nothing"

                if 'GOLD' in offering:
                    action = f"BUY {requesting_str} from nation {target_id} for {offering_str}"
                elif 'GOLD' in requesting:
                    action = f"SELL {offering_str} to nation {target_id} for {requesting_str}"
                else:
                    action = f"Trade {offering_str} with nation {target_id} for {requesting_str}"

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


def _format_nation_summary(nation_data: Dict[str, Any]) -> str:
    """Format a nation's info as natural language with VERY clear separation."""
    name = nation_data["name"]
    resources = nation_data["resources"]
    generators = nation_data.get("generators", [])

    # List what they HAVE NOW (tradeable) - show all resources including zeros
    tradeable_now = []
    for res, amt in resources.items():
        tradeable_now.append(f"{res}={amt}")

    has_now = ", ".join(tradeable_now) if tradeable_now else "No resources"

    # List generators and what they produce
    gen_parts = []
    for g in generators:
        gen_type = g["type"]
        produces = g["produces"]
        gen_parts.append(f"{gen_type} → {produces} next turn")

    if gen_parts:
        generators_str = ", ".join(gen_parts)
    else:
        generators_str = "None"

    return f"""{name}:
      HAS NOW: {has_now}
      GENERATORS: {generators_str}"""


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
        your_gen_parts.append(f"{gen_type} → {produces} next turn")

    if your_gen_parts:
        your_generators = ", ".join(your_gen_parts)
    else:
        your_generators = "None"

    # Goal info
    goal_parts = []
    for res, amt in era_requirements.items():
        current = nation.inventory.get(res)
        status = "✓" if current >= amt else "✗"
        goal_parts.append(f"{res}={amt} {status}")
    goal_str = ", ".join(goal_parts)

    # Other nations info
    other_nations_lines = []
    for other in game_state.get("nations", []):
        if other["id"] != nation.id:
            nation_summary = _format_nation_summary(other)
            other_nations_lines.append(f"  {other['id']}. {nation_summary}")
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

TRADING RULES:
- One side offers ONLY GOLD
- Other side offers ONLY resources (can be multiple: WOOD, STONE, FOOD, etc.)
- NEVER mix gold with resources on the same side
- Examples:
  ✓ Offer GOLD → Request WOOD (BUY)
  ✓ Offer GOLD → Request WOOD + STONE (BUY bundle)
  ✓ Offer WOOD + STONE → Request GOLD (SELL bundle)
  ✗ Offer GOLD + WOOD → anything (can't mix gold with resources)
  ✗ Offer WOOD → Request STONE (one side MUST be GOLD)

CRITICAL - VERIFY RESOURCES BEFORE TRADING:
GENERATOR ≠ HAVING THE RESOURCE RIGHT NOW!

When BUYING (you offer GOLD → request RESOURCES):
1. Check YOUR resources: Do I have enough GOLD?
2. Check TARGET's resources: Does target have enough WOOD/STONE/FOOD?
3. Example: Indonesia has LUMBER_CAMP but resources.WOOD = 0 → CANNOT buy WOOD (trade fails!)

When SELLING (you offer RESOURCES → request GOLD):
1. Check YOUR resources: Do I have enough WOOD/STONE/FOOD?
2. Check TARGET's resources: Does target have enough GOLD?
3. Example: Egypt has MINE but resources.GOLD = 0 → CANNOT sell to Egypt (trade fails!)

TARGET NATIONS WITH GENERATORS (Secondary consideration):
Nations with generators are MORE LIKELY to accept, but ONLY if they have the resource NOW:
- Target has MINE + has GOLD in resources? → Good target (will regenerate)
- Target has LUMBER_CAMP + has WOOD in resources? → Good target (will regenerate)
- Target has QUARRY + has STONE in resources? → Good target (will regenerate)
- Target has FARM + has FOOD in resources? → Good target (will regenerate)

CRITICAL - DON'T REPEAT FAILED TRADES:
- Check "YOUR PREVIOUS DECISIONS" section
- If you see "Outcome: Trade invalid" → That nation lacks resources!
- DON'T propose the same trade again to the same nation
- Try a DIFFERENT nation or DIFFERENT resources

CRITICAL - DON'T DOUBLE-SPEND YOUR RESOURCES:
- If you already traded in this turn, your resources have changed!
- Check "your_nation.resources" carefully - these are your CURRENT resources
- Example: You had 100 GOLD, spent 50 on first trade → Now you have 50 GOLD
- DON'T try to spend the same resources twice!

STEP-BY-STEP DECISION PROCESS:
1. What do I need? (check "goal.next_era_requirements")
2. Review previous decisions - Did any trades fail? If yes, avoid that nation/resource combo
3. Check MY resources in "your_nation.resources" - What can I offer?
4. For each potential trade partner, CHECK THEIR RESOURCES FIRST:
   - If I want to BUY WOOD: Does target have WOOD > 0 in their resources?
   - If I want to SELL for GOLD: Does target have GOLD > 0 in their resources?
5. Only AFTER confirming they have the resource, check if they have the generator (bonus)

Respond with JSON (keep reasoning <=3 sentences):
{{
    "trade": true/false,
    "target_nation_id": <id or null>,
    "offering": {{"GOLD": 50}} or {{"WOOD": 50, "STONE": 30}},
    "requesting": {{"WOOD": 50}} or {{"GOLD": 50}},
    "reasoning": "I need X. [Name] has Y and [GENERATOR]. Buying/Selling/Skipping." (this should ABSOLUTELY match what's answered in the other properties)
}}

________________________________________________________________________________
CURRENT GAME STATE:

YOUR NATION: {nation.name}
  HAS NOW: {your_has_now}
  GENERATORS: {your_generators}

YOUR GOAL: Advance to Era {nation.era.value + 1}
  Requirements: {goal_str}

________________________________________________________________________________
OTHER NATIONS - READ "HAS NOW" CAREFULLY! That's what you can trade for RIGHT NOW!
(GENERATORS shows what resources they'll produce NEXT turn - you CANNOT trade for future production!)
________________________________________________________________________________
{other_nations_str}

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
        your_gens.append(f"{g.generator_type.value} (→{g.generation_amount} {g.produces.value}/turn)")
    your_gens_str = ", ".join(your_gens) if your_gens else "None"

    # Format goal
    goal_parts = []
    for res, amt in era_requirements.items():
        current = nation.inventory.get(res)
        status = "✓" if current >= amt else "✗"
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
1. Look at YOUR resources below
2. Look at GENERATOR COSTS below
3. Can you afford it? Check EACH resource requirement
4. If you DON'T have enough → build: false, generator_type: null
5. If you DO have enough → build: true, generator_type: "TYPE"

CRITICAL - REASONING MUST MATCH DECISION:
- If reasoning says "cannot afford" → build MUST be false
- If reasoning says "building" → build MUST be true
- If reasoning says "skipping" → build MUST be false
- NO contradictions allowed!

RULES:
- For FARM: specify payment_resource (WOOD or STONE)
- For all others: payment_resource must be null

STRATEGY:
- What do I need for next era? (see requirements below)
- Which generator produces what I need?
- MINE produces GOLD (needed for all trades - prioritize if affordable)

Respond with JSON (keep reasoning <=2 sentences):
{{
    "build": true/false,
    "generator_type": "LUMBER_CAMP" | "QUARRY" | "FARM" | "MINE" | "FACTORY" | "DATACENTER" | null,
    "payment_resource": "WOOD" | "STONE" | null (for FARM only),
    "reasoning": "What I have, what it costs, decision." (this should ABSOLUTELY match what's answered in the other properties)
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
        your_gens.append(f"{g.generator_type.value} (→{g.generation_amount} {g.produces.value}/turn)")
    your_gens_str = ", ".join(your_gens) if your_gens else "None"

    # Format what they're offering and requesting
    offering_parts = [f"{amt} {res}" for res, amt in offer.get('offering', {}).items()]
    offering_str = ", ".join(offering_parts) if offering_parts else "Nothing"

    requesting_parts = [f"{amt} {res}" for res, amt in offer.get('requesting', {}).items()]
    requesting_str = ", ".join(requesting_parts) if requesting_parts else "Nothing"

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""TRADE OFFER RECEIVED from {proposer_nation['name']}

They offer you: {offering_str}
They request from you: {requesting_str}

RULES:
- You MUST have what they request (check your current resources below)
- If you lack ANY requested resource → REJECT
- Resources are ALWAYS useful (for future eras, generators, other trades)

CRITICAL - WHEN TO ACCEPT:
Check YOUR generators (see below):
- MINE produces GOLD
- LUMBER_CAMP produces WOOD
- QUARRY produces STONE
- FARM produces FOOD
- FACTORY produces TECHNOLOGY
- DATACENTER produces INFORMATION

ACCEPT if you have a generator for what they request!
- They want GOLD and you have MINE? → ACCEPT (you'll regenerate GOLD next turn)
- They want WOOD and you have LUMBER_CAMP? → ACCEPT (you'll regenerate WOOD next turn)
- They want STONE and you have QUARRY? → ACCEPT (you'll regenerate STONE next turn)
- They want FOOD and you have FARM? → ACCEPT (you'll regenerate FOOD next turn)
- They want TECHNOLOGY and you have FACTORY? → ACCEPT (you'll regenerate TECHNOLOGY next turn)
- They want INFORMATION and you have DATACENTER? → ACCEPT (you'll regenerate INFORMATION next turn)

Only REJECT if:
- You don't have what they request, OR
- You don't have a generator for it (you won't get it back)

Respond with JSON (keep reasoning <=2 sentences):
{{
    "decision": "ACCEPT" | "REJECT",
    "reasoning": "They request X. I have [amount] and [GENERATOR]. Accepting/Rejecting." (this should ABSOLUTELY match what's answered in the other properties)
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

    # Format alternative partners
    alt_lines = []
    for other in other_nations:
        nation_summary = _format_nation_summary(other)
        alt_lines.append(f"  {other['id']}. {nation_summary}")
    alt_str = "\n".join(alt_lines) if alt_lines else "  (No alternatives available)"

    # Add memory context
    memory_context = _format_memory_context(nation)

    prompt = f"""TRADE REJECTED by {rejected_nation_name}

OPTIONS:
1. Try SAME trade with different partner
2. Try DIFFERENT trade with different partner
3. Skip (retry: false) → ends trading phase

CRITICAL: Check "resources" field, NOT "generators" field!
- Generators produce NEXT turn, not now
- If nation has LUMBER_CAMP but resources.WOOD = 0 → they have NO WOOD now!

CRITICAL - DON'T DOUBLE-SPEND:
- Your resources shown above are CURRENT (after first trade)
- Example: You spent 50 GOLD on first trade → resources now shows remaining GOLD
- DON'T try to offer resources you already spent!

TRADING RULES:
- One side ONLY GOLD, other side ONLY resources (can be multiple)
- NEVER mix gold with resources on same side
- Examples: ✓ GOLD for WOOD+STONE  ✓ WOOD+STONE for GOLD  ✗ GOLD+WOOD for anything

RULES:
- Verify YOU still have what you're offering (check YOUR resources above)
- Verify ALTERNATIVE nation has what you're requesting (check their "resources")
- If no good alternative → set retry: false

Respond with JSON (keep reasoning <=3 sentences):
{{
    "retry": true/false,
    "target_nation_id": <id or null>,
    "offering": {{"GOLD": 50}} or {{"WOOD": 50, "STONE": 30}},
    "requesting": {{"WOOD": 50}} or {{"GOLD": 50}},
    "reasoning": "What I have, what they have, decision." (this should ABSOLUTELY match what's answered in the other properties)
}}

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
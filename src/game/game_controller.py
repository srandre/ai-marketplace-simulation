"""Main game controller coordinating all game systems."""

from typing import Dict

from ..ai.decision_maker import DecisionMaker
from ..models.enums import GeneratorType, LogType, ResourceType
from ..models.transaction import Transaction, TradeOffer
from .building import BuildingManager
from .game_state import GameState
from .trading import TradingManager
from .turn_manager import TurnManager


class GameController:
    """Main controller for game logic and AI coordination."""

    def __init__(self):
        self.game_state = GameState()
        self.game_state.initialize_game()  # Initialize first so generator_manager is available
        self.turn_manager = TurnManager(self.game_state)
        self.building_manager = BuildingManager(self.game_state)
        self.trading_manager = TradingManager(self.game_state)
        self.decision_maker = DecisionMaker(self.game_state.generator_manager)

    def initialize(self) -> None:
        """Initialize the game (already done in __init__)."""
        pass  # Game is now initialized in __init__

    def _build_game_state_summary(self) -> Dict:
        """Build a summary of the game state for AI decision-making."""
        nations_summary = []
        for nation in self.game_state.nations:
            nations_summary.append(nation.to_summary_dict())

        # Get recent transactions
        recent_trans = self.game_state.transaction_history.get_recent(10)
        trans_summary = []
        for t in recent_trans:
            trans_summary.append({
                "initiator_id": t.initiator_id,
                "responder_id": t.responder_id,
                "status": t.status.value,
                "offer": t.current_offer.to_dict(),
            })

        # Get generator costs
        generator_costs = {}
        for gen_type in GeneratorType:
            count = self.game_state.get_generator_count(gen_type)
            blueprint = self.game_state.generator_manager.get_blueprint(gen_type)
            if blueprint:
                cost = blueprint.get_current_cost(count)
                cost_info = {
                    k.value: v for k, v in cost.items()
                }
                # Add base_cost_either if applicable (e.g., Farm can pay with WOOD or STONE)
                if blueprint.base_cost_either is not None:
                    multiplier = 2 ** count
                    cost_either = {
                        rt.value: amount * multiplier
                        for rt, amount in blueprint.base_cost_either.items()
                    }
                    cost_info["cost_either"] = cost_either
                generator_costs[gen_type.value] = cost_info

        return {
            "nations": nations_summary,
            "recent_transactions": trans_summary,
            "generator_costs": generator_costs,
            "turn_number": self.game_state.turn_number,
        }


    def _process_trade_response(self, transaction: Transaction) -> str:
        """
        Process the responder's decision on a trade.

        Returns: "ACCEPTED", "REJECTED", or "COUNTER"
        """
        responder = self.game_state.get_nation(transaction.responder_id)
        initiator = self.game_state.get_nation(transaction.initiator_id)

        if not responder or not initiator:
            return "REJECTED"

        # Build context for responder
        game_state_summary = self._build_game_state_summary()
        era_reqs = self.game_state.get_era_advancement_requirements(responder.era)
        era_reqs_dict = {k.value: v for k, v in era_reqs.items()} if era_reqs else {}

        game_state_summary["era_requirements"] = era_reqs_dict

        # Ask AI for response
        decision, prompt, response = self.decision_maker.respond_to_trade_offer(
            responder,
            initiator.to_summary_dict(),
            transaction.current_offer.to_dict(),
            game_state_summary,
        )

        # Log AI decision with trade offer details
        log_entry = self.game_state.game_log.add_entry(
            log_type=LogType.AI_DECISION,
            turn_number=self.game_state.turn_number,
            round_number=self.game_state.round_number,
            summary=f"{responder.name} AI responding to trade",
            nations_involved=[initiator.id, responder.id],  # Include both nations
            details={
                "action_type": "TRADE_RESPONSE",
                "offer": transaction.current_offer.to_dict()  # Include the trade offer
            },
        )
        log_entry.add_ai_decision(responder.id, prompt, response)

        # Process response
        response_type = decision.get("decision", "REJECT")

        if response_type == "ACCEPT":
            self.trading_manager.accept_trade(transaction)
            return "ACCEPTED"
        elif response_type == "COUNTER":
            counter_offer_data = decision.get("counter_offer", {})
            counter_offer = self.decision_maker.parse_trade_offer(counter_offer_data)
            if counter_offer and counter_offer.is_valid():
                success, _ = self.trading_manager.counter_propose(transaction, counter_offer)
                if success:
                    # Ask initiator about counter-offer
                    self._process_counter_offer_response(transaction)
            return "COUNTER"
        else:  # REJECT
            self.trading_manager.reject_trade(transaction)
            return "REJECTED"

    def _process_counter_offer_response(self, transaction: Transaction) -> None:
        """Process initiator's response to a counter-offer."""
        initiator = self.game_state.get_nation(transaction.initiator_id)
        responder = self.game_state.get_nation(transaction.responder_id)

        if not initiator or not responder:
            return

        # Ask AI for response
        decision, prompt, response = self.decision_maker.respond_to_counter_offer(
            initiator,
            responder.to_summary_dict(),
            transaction.counter_offer.to_dict() if transaction.counter_offer else {},
        )

        # Log AI decision
        log_entry = self.game_state.game_log.add_entry(
            log_type=LogType.AI_DECISION,
            turn_number=self.game_state.turn_number,
            round_number=self.game_state.round_number,
            summary=f"{initiator.name} AI responding to counter-offer",
            nations_involved=[initiator.id],
            details={"action_type": "COUNTER_RESPONSE"},
        )
        log_entry.add_ai_decision(initiator.id, prompt, response)

        # Process response
        if decision.get("decision") == "ACCEPT":
            self.trading_manager.accept_trade(transaction)
        else:
            self.trading_manager.reject_trade(transaction)


    def _execute_trade_action(self, nation, action: Dict) -> str:
        """
        Execute a trade action from the combined turn plan.

        Returns: "ACCEPTED", "REJECTED", "COUNTER", or "INVALID"
        """
        target_id = action.get("target_nation_id")
        if target_id is None:
            return "INVALID"

        # Parse trade offer
        offering_dict = action.get("offering", {})
        requesting_dict = action.get("requesting", {})

        offering = {}
        requesting = {}

        for resource_str, amount in offering_dict.items():
            try:
                resource_type = ResourceType[resource_str.upper()]
                offering[resource_type] = int(amount)
            except (KeyError, ValueError):
                continue

        for resource_str, amount in requesting_dict.items():
            try:
                resource_type = ResourceType[resource_str.upper()]
                requesting[resource_type] = int(amount)
            except (KeyError, ValueError):
                continue

        trade_offer = TradeOffer(offering=offering, requesting=requesting)

        if not trade_offer.is_valid():
            print(f"Invalid trade offer from {nation.name}")
            return "INVALID"

        # Check if target has the requested resources
        target_nation = self.game_state.get_nation(target_id)
        if target_nation:
            for resource_type, amount in requesting.items():
                if not target_nation.inventory.has(resource_type, amount):
                    # Log the failed trade attempt
                    from ..models.enums import LogType
                    self.game_state.game_log.add_entry(
                        log_type=LogType.TRADE,
                        turn_number=self.game_state.turn_number,
                        round_number=self.game_state.round_number,
                        summary=f"{nation.name} trade failed: {target_nation.name} lacks resources",
                        nations_involved=[nation.id, target_id],
                        details={"offer": trade_offer.to_dict(), "reason": "Insufficient resources"},
                    )
                    return "INVALID"

        # Propose trade
        transaction = self.trading_manager.propose_trade(
            nation.id, target_id, trade_offer
        )

        if transaction:
            # Ask target nation to respond and store result
            result = self._process_trade_response(transaction)
            return result if result else "REJECTED"

        return "INVALID"

    def _execute_build_from_plan(self, nation, action: Dict) -> None:
        """Execute a build action from the combined turn plan."""
        gen_type_str = action.get("generator_type")

        if not gen_type_str:
            return

        try:
            generator_type = GeneratorType[gen_type_str.upper()]

            # Extract payment_resource for Farm builds
            payment_resource = None
            payment_resource_str = action.get("payment_resource")
            if payment_resource_str:
                try:
                    payment_resource = ResourceType[payment_resource_str.upper()]
                except (KeyError, ValueError):
                    pass  # Invalid resource type, will be handled by build_generator

            success, message = self.building_manager.build_generator(
                nation, generator_type, payment_resource=payment_resource
            )

            if not success:
                # Log the failed build attempt
                from ..models.enums import LogType
                self.game_state.game_log.add_entry(
                    log_type=LogType.BUILD,
                    turn_number=self.game_state.turn_number,
                    round_number=self.game_state.round_number,
                    summary=f"{nation.name} failed to build {gen_type_str}: {message}",
                    nations_involved=[nation.id],
                    details={
                        "generator_type": gen_type_str,
                        "failure_reason": message,
                    },
                )
        except (KeyError, ValueError) as e:
            # Log invalid generator type
            from ..models.enums import LogType
            self.game_state.game_log.add_entry(
                log_type=LogType.BUILD,
                turn_number=self.game_state.turn_number,
                round_number=self.game_state.round_number,
                summary=f"{nation.name} failed to build: invalid generator type '{gen_type_str}'",
                nations_involved=[nation.id],
                details={
                    "generator_type": gen_type_str,
                    "failure_reason": str(e),
                },
            )

    def _can_afford_any_generator(self, nation) -> bool:
        """Check if a nation can afford to build ANY generator."""
        for gen_type in GeneratorType:
            blueprint = self.game_state.generator_manager.get_blueprint(gen_type)
            if not blueprint:
                continue

            # Check era requirement
            if blueprint.required_era > nation.era.value:
                continue

            count_built = self.game_state.get_generator_count(gen_type)

            # Check if can pay with either resource (Farm case)
            if blueprint.base_cost_either:
                resource_type = blueprint.can_pay_with_either(nation.inventory, count_built)
                if resource_type:
                    return True
            else:
                # Check normal cost
                current_cost = blueprint.get_current_cost(count_built)
                if nation.inventory.has_multiple(current_cost):
                    return True

        return False

    def _request_alternative_trade(self, nation, rejected_action: Dict):
        """
        Ask AI for an alternative trade partner after rejection.

        Returns: Alternative trade action dict or None
        """
        from ..ai.prompts import create_alternative_trade_prompt

        rejected_target_id = rejected_action.get("target_nation_id")
        offering = rejected_action.get("offering", {})
        requesting = rejected_action.get("requesting", {})

        # Build game state summary
        game_state_summary = self._build_game_state_summary()
        era_reqs = self.game_state.get_era_advancement_requirements(nation.era)
        era_reqs_dict = {k.value: v for k, v in era_reqs.items()} if era_reqs else {}
        game_state_summary["era_requirements"] = era_reqs_dict

        # Get list of other nations (excluding the one that rejected and self)
        other_nations = [
            n.to_summary_dict()
            for n in self.game_state.nations
            if n.id != nation.id and n.id != rejected_target_id
        ]

        if not other_nations:
            return None

        # Create prompt for alternative trade
        user_prompt = create_alternative_trade_prompt(
            nation,
            other_nations,
            offering,
            requesting,
            rejected_target_id,
            game_state_summary
        )

        # Default decision: don't retry
        default_decision = {
            "retry": False,
            "target_nation_id": None,
            "reasoning": "Unable to determine alternative partner"
        }

        # Ask AI for alternative using standard decision maker pattern
        decision, _raw_response = self.decision_maker.client.make_decision_with_fallback(
            self.decision_maker.system_prompt,
            user_prompt,
            default_decision
        )

        # Check if AI wants to retry with a different partner
        if decision.get("retry") and decision.get("target_nation_id") is not None:
            return {
                "type": "TRADE",
                "target_nation_id": decision["target_nation_id"],
                "offering": offering,
                "requesting": requesting,
                "reasoning": decision.get("reasoning", "Retrying trade with alternative partner")
            }

        return None


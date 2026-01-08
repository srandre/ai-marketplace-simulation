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
        self.turn_manager = TurnManager(self.game_state)
        self.building_manager = BuildingManager(self.game_state)
        self.trading_manager = TradingManager(self.game_state)
        self.decision_maker = DecisionMaker()

    def initialize(self) -> None:
        """Initialize the game."""
        self.game_state.initialize_game()

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
                # Add base_cost_any if applicable (e.g., Farm)
                if blueprint.base_cost_any is not None:
                    required = blueprint.base_cost_any * (count + 1)
                    cost_info["cost_any_resource"] = required
                generator_costs[gen_type.value] = cost_info

        return {
            "nations": nations_summary,
            "recent_transactions": trans_summary,
            "generator_costs": generator_costs,
            "turn_number": self.game_state.turn_number,
        }


    def _process_trade_response(self, transaction: Transaction) -> None:
        """Process the responder's decision on a trade."""
        responder = self.game_state.get_nation(transaction.responder_id)
        initiator = self.game_state.get_nation(transaction.initiator_id)

        if not responder or not initiator:
            return

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
        elif response_type == "COUNTER":
            counter_offer_data = decision.get("counter_offer", {})
            counter_offer = self.decision_maker.parse_trade_offer(counter_offer_data)
            if counter_offer and counter_offer.is_valid():
                success, _ = self.trading_manager.counter_propose(transaction, counter_offer)
                if success:
                    # Ask initiator about counter-offer
                    self._process_counter_offer_response(transaction)
        else:  # REJECT
            self.trading_manager.reject_trade(transaction)

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


    def _execute_trade_action(self, nation, action: Dict) -> None:
        """Execute a trade action from the combined turn plan."""
        target_id = action.get("target_nation_id")
        if target_id is None:
            return

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
            return

        # Propose trade
        transaction = self.trading_manager.propose_trade(
            nation.id, target_id, trade_offer
        )

        if transaction:
            # Ask target nation to respond
            self._process_trade_response(transaction)

    def _execute_build_from_plan(self, nation, action: Dict) -> None:
        """Execute a build action from the combined turn plan."""
        gen_type_str = action.get("generator_type")

        if not gen_type_str:
            return

        try:
            generator_type = GeneratorType[gen_type_str.upper()]
            success, message = self.building_manager.build_generator(nation, generator_type)

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


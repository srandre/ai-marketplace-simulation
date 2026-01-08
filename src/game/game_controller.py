"""Main game controller coordinating all game systems."""

from typing import Dict, List

from ..ai.decision_maker import DecisionMaker
from ..models.enums import GeneratorType, LogType
from ..models.transaction import Transaction
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

    def execute_turn(self) -> None:
        """Execute one nation's turn completely."""
        current_nation = self.game_state.get_current_nation()
        if not current_nation:
            return

        print(f"Current Nation: {current_nation.name} (Era {current_nation.era.value})")

        # Start turn (resource generation, era advancement)
        self.turn_manager.start_turn(current_nation.id)

        # Get available actions
        available_actions = self._get_available_actions()

        # Execute AI actions
        print(f"Phase 1: SELL action")
        self._execute_sell_action(current_nation.id, available_actions)

        print(f"Phase 2: BUY action")
        self._execute_buy_action()

        print(f"Phase 3: BUILD action")
        self._execute_build_action(current_nation.id, available_actions)

        # End turn
        self.turn_manager.end_turn()
        print(f"Turn ended for {current_nation.name}")

    def _get_available_actions(self) -> List[str]:
        """Get list of available actions for the nation."""
        return ["SELL", "BUY", "BUILD", "PASS"]

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
                generator_costs[gen_type.value] = {
                    k.value: v for k, v in cost.items()
                }

        return {
            "nations": nations_summary,
            "recent_transactions": trans_summary,
            "generator_costs": generator_costs,
            "turn_number": self.game_state.turn_number,
        }

    def _execute_sell_action(self, nation_id: int, available_actions: List[str]) -> None:
        """Execute a sell/trade action."""
        if "SELL" not in available_actions and "BUY" not in available_actions:
            return

        nation = self.game_state.get_nation(nation_id)
        if not nation:
            return

        # Get era requirements
        era_reqs = self.game_state.get_era_advancement_requirements(nation.era)
        era_reqs_dict = {k.value: v for k, v in era_reqs.items()} if era_reqs else {}

        # Build game state
        game_state_summary = self._build_game_state_summary()

        # Ask AI for decision
        decision, prompt, response = self.decision_maker.decide_action(
            nation, game_state_summary, available_actions, era_reqs_dict
        )

        # Log AI decision
        log_entry = self.game_state.game_log.add_entry(
            log_type=LogType.AI_DECISION,
            turn_number=self.game_state.turn_number,
            summary=f"{nation.flag} AI deciding on SELL action",
            nations_involved=[nation_id],
            details={"action_type": "SELL"},
        )
        log_entry.add_ai_decision(nation_id, prompt, response)

        # Process decision
        if decision.get("action") in ["SELL", "BUY"]:
            self._process_trade_decision(nation, decision)

    def _execute_buy_action(self) -> None:
        """Execute a buy action (similar to sell, trading is bilateral)."""
        # In this implementation, SELL and BUY are the same
        # We already handled it in _execute_sell_action
        pass

    def _execute_build_action(self, nation_id: int, available_actions: List[str]) -> None:
        """Execute a build action."""
        if "BUILD" not in available_actions:
            return

        nation = self.game_state.get_nation(nation_id)
        if not nation:
            return

        # Get era requirements
        era_reqs = self.game_state.get_era_advancement_requirements(nation.era)
        era_reqs_dict = {k.value: v for k, v in era_reqs.items()} if era_reqs else {}

        # Build game state
        game_state_summary = self._build_game_state_summary()

        # Ask AI for decision
        decision, prompt, response = self.decision_maker.decide_action(
            nation, game_state_summary, available_actions, era_reqs_dict
        )

        # Log AI decision
        log_entry = self.game_state.game_log.add_entry(
            log_type=LogType.AI_DECISION,
            turn_number=self.game_state.turn_number,
            summary=f"{nation.flag} AI deciding on BUILD action",
            nations_involved=[nation_id],
            details={"action_type": "BUILD"},
        )
        log_entry.add_ai_decision(nation_id, prompt, response)

        # Process decision
        if decision.get("action") == "BUILD":
            self._process_build_decision(nation, decision)

    def _process_trade_decision(self, nation, decision: Dict) -> None:
        """Process a trade decision from AI."""
        details = decision.get("details", {})
        target_id = details.get("target_nation_id")

        if target_id is None:
            return

        # Parse trade offer
        trade_offer = self.decision_maker.parse_trade_offer(details)
        if not trade_offer or not trade_offer.is_valid():
            return

        # Propose trade
        transaction = self.trading_manager.propose_trade(
            nation.id, target_id, trade_offer
        )

        if transaction:
            # Ask target nation to respond
            self._process_trade_response(transaction)

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

        # Log AI decision
        log_entry = self.game_state.game_log.add_entry(
            log_type=LogType.AI_DECISION,
            turn_number=self.game_state.turn_number,
            summary=f"{responder.flag} AI responding to trade",
            nations_involved=[responder.id],
            details={"action_type": "TRADE_RESPONSE"},
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
            summary=f"{initiator.flag} AI responding to counter-offer",
            nations_involved=[initiator.id],
            details={"action_type": "COUNTER_RESPONSE"},
        )
        log_entry.add_ai_decision(initiator.id, prompt, response)

        # Process response
        if decision.get("decision") == "ACCEPT":
            self.trading_manager.accept_trade(transaction)
        else:
            self.trading_manager.reject_trade(transaction)

    def _process_build_decision(self, nation, decision: Dict) -> None:
        """Process a build decision from AI."""
        details = decision.get("details", {})
        gen_type_str = details.get("generator_type")

        if not gen_type_str:
            return

        try:
            generator_type = GeneratorType[gen_type_str.upper()]
            self.building_manager.build_generator(nation, generator_type)
        except (KeyError, ValueError):
            pass

    def get_game_state(self) -> GameState:
        """Get the current game state."""
        return self.game_state

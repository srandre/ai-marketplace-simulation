"""Trading system for resource exchange between nations."""

from typing import Optional

from ..models.enums import LogType, TransactionStatus
from ..models.transaction import TradeOffer, Transaction
from ..utils.config import config
from .game_state import GameState


class TradingManager:
    """Manages trading between nations."""

    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def propose_trade(
        self, initiator_id: int, responder_id: int, offer: TradeOffer
    ) -> Optional[Transaction]:
        """
        Initiate a trade proposal.

        Returns the Transaction object if valid, None otherwise.
        """
        initiator = self.game_state.get_nation(initiator_id)
        responder = self.game_state.get_nation(responder_id)

        if not initiator or not responder:
            return None

        if not offer.is_valid():
            # Log why the trade was invalid
            print(f"Invalid trade offer from {initiator.name}: Trade must have one side with ONLY gold and the other side with NO gold")
            return None

        # Check if initiator has the resources they're offering
        if not initiator.inventory.has_multiple(offer.offering):
            print(f"[TRADE FAILED] {initiator.name} lacks resources to offer: {offer.offering}")
            print(f"  Current inventory: {initiator.inventory.to_dict()}")
            return None

        # Create transaction
        transaction = Transaction(
            initiator_id=initiator_id,
            responder_id=responder_id,
            current_offer=offer,
            status=TransactionStatus.PROPOSED,
            turn_number=self.game_state.turn_number,
        )

        # Note: Trade proposal is now logged as part of the AI decision in async_turn_executor
        # No separate log entry needed here

        return transaction

    def accept_trade(self, transaction: Transaction) -> tuple[bool, str]:
        """
        Accept a trade and execute the resource transfer.

        Returns (success, message).
        """
        initiator = self.game_state.get_nation(transaction.initiator_id)
        responder = self.game_state.get_nation(transaction.responder_id)

        if not initiator or not responder:
            return False, "Nations not found"

        # Get the active offer (always the original offer now)
        active_offer = transaction.current_offer

        # Initiator offers, responder receives
        giver = initiator
        receiver = responder
        giving = active_offer.offering
        receiving = active_offer.requesting

        # Verify resources
        if not giver.inventory.has_multiple(giving):
            return False, "Giver has insufficient resources"

        if not receiver.inventory.has_multiple(receiving):
            return False, "Receiver has insufficient resources"

        # Execute transfer
        giver.inventory.remove_multiple(giving)
        receiver.inventory.remove_multiple(receiving)

        # Giver receives what receiver was offering
        for resource_type, amount in receiving.items():
            giver.inventory.add(resource_type, amount)

        # Receiver receives what giver was offering
        for resource_type, amount in giving.items():
            receiver.inventory.add(resource_type, amount)

        # Update transaction status
        transaction.complete()

        # Update relationships (successful trade)
        relationship_bonus = config.get("diplomacy.successful_trade_bonus", 1)
        initiator.update_relationship(
            responder.id,
            relationship_bonus,
            config.get("diplomacy.relationship_min", -100),
            config.get("diplomacy.relationship_max", 100),
        )
        responder.update_relationship(
            initiator.id,
            relationship_bonus,
            config.get("diplomacy.relationship_min", -100),
            config.get("diplomacy.relationship_max", 100),
        )

        # Add to transaction history
        self.game_state.transaction_history.add(transaction)

        # Log the completion
        self.game_state.game_log.add_entry(
            log_type=LogType.TRADE_COMPLETED,
            turn_number=self.game_state.turn_number,
            round_number=self.game_state.round_number,
            summary=f"{initiator.name} and {responder.name} completed trade",
            nations_involved=[transaction.initiator_id, transaction.responder_id],
            details={"offer": active_offer.to_dict()},
        )

        return True, "Trade completed successfully"

    def reject_trade(self, transaction: Transaction) -> None:
        """Reject a trade proposal."""
        initiator = self.game_state.get_nation(transaction.initiator_id)
        responder = self.game_state.get_nation(transaction.responder_id)

        if not initiator or not responder:
            return

        transaction.reject()

        # Update relationships (failed trade)
        relationship_penalty = config.get("diplomacy.failed_trade_penalty", -1)
        initiator.update_relationship(
            responder.id,
            relationship_penalty,
            config.get("diplomacy.relationship_min", -100),
            config.get("diplomacy.relationship_max", 100),
        )
        responder.update_relationship(
            initiator.id,
            relationship_penalty,
            config.get("diplomacy.relationship_min", -100),
            config.get("diplomacy.relationship_max", 100),
        )

        # Note: Trade rejection is now shown in the AI decision log
        # No separate log entry needed here

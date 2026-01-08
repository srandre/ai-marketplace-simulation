"""Transaction models for resource trading."""

from typing import Dict, Optional

from pydantic import BaseModel, Field

from .enums import ResourceType, TransactionStatus


class TradeOffer(BaseModel):
    """Represents a trade offer between two nations."""

    offering: Dict[ResourceType, int] = Field(default_factory=dict)  # What they're giving
    requesting: Dict[ResourceType, int] = Field(default_factory=dict)  # What they want

    def is_valid(self) -> bool:
        """
        Check if the offer is valid.

        Rules:
        - Must have both offering and requesting items
        - One side must have ONLY gold
        - The other side must have resources (but NOT gold)
        """
        has_offering = any(amount > 0 for amount in self.offering.values())
        has_requesting = any(amount > 0 for amount in self.requesting.values())

        if not (has_offering and has_requesting):
            return False

        # Check gold-only rule
        offering_resources = [rt for rt, amt in self.offering.items() if amt > 0]
        requesting_resources = [rt for rt, amt in self.requesting.items() if amt > 0]

        # One side must be ONLY gold
        offering_is_only_gold = (len(offering_resources) == 1 and
                                  offering_resources[0] == ResourceType.GOLD)
        requesting_is_only_gold = (len(requesting_resources) == 1 and
                                    requesting_resources[0] == ResourceType.GOLD)

        # The other side must NOT contain gold
        offering_has_gold = ResourceType.GOLD in offering_resources
        requesting_has_gold = ResourceType.GOLD in requesting_resources

        # Valid if one side is only gold and the other doesn't have gold
        if offering_is_only_gold and not requesting_has_gold:
            return True
        if requesting_is_only_gold and not offering_has_gold:
            return True

        return False

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "offering": {k.value: v for k, v in self.offering.items() if v > 0},
            "requesting": {k.value: v for k, v in self.requesting.items() if v > 0},
        }

    def __repr__(self) -> str:
        offering_str = ", ".join(f"{v} {k.value}" for k, v in self.offering.items() if v > 0)
        requesting_str = ", ".join(f"{v} {k.value}" for k, v in self.requesting.items() if v > 0)
        return f"TradeOffer(offering=[{offering_str}], requesting=[{requesting_str}])"

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class Transaction(BaseModel):
    """Represents a transaction between two nations."""

    initiator_id: int
    responder_id: int
    current_offer: TradeOffer
    counter_offer: Optional[TradeOffer] = None
    status: TransactionStatus = Field(default=TransactionStatus.PROPOSED)
    turn_number: int

    def accept(self) -> None:
        """Mark transaction as accepted."""
        self.status = TransactionStatus.ACCEPTED

    def reject(self) -> None:
        """Mark transaction as rejected."""
        self.status = TransactionStatus.REJECTED

    def counter_propose(self, counter_offer: TradeOffer) -> None:
        """Submit a counter offer."""
        self.counter_offer = counter_offer
        self.status = TransactionStatus.COUNTER_PROPOSED

    def complete(self) -> None:
        """Mark transaction as completed."""
        self.status = TransactionStatus.COMPLETED

    def get_active_offer(self) -> TradeOffer:
        """Get the currently active offer."""
        if self.status == TransactionStatus.COUNTER_PROPOSED and self.counter_offer:
            return self.counter_offer
        return self.current_offer

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class TransactionHistory(BaseModel):
    """Tracks transaction history for a game."""

    transactions: list[Transaction] = Field(default_factory=list)

    def add(self, transaction: Transaction) -> None:
        """Add a transaction to history."""
        self.transactions.append(transaction)

    def get_recent(self, limit: int = 10) -> list[Transaction]:
        """Get recent transactions."""
        return self.transactions[-limit:]

    def get_for_nation(self, nation_id: int, limit: int = 10) -> list[Transaction]:
        """Get recent transactions involving a specific nation."""
        relevant = [
            t for t in self.transactions
            if t.initiator_id == nation_id or t.responder_id == nation_id
        ]
        return relevant[-limit:]

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

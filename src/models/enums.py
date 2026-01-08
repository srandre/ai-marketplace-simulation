"""Enumerations for game entities."""

from enum import Enum


class ResourceType(str, Enum):
    """Types of resources in the game."""

    GOLD = "GOLD"
    WOOD = "WOOD"
    STONE = "STONE"
    FOOD = "FOOD"
    TECHNOLOGY = "TECHNOLOGY"
    INFORMATION = "INFORMATION"


class GeneratorType(str, Enum):
    """Types of resource generators."""

    MINE = "MINE"
    LUMBER_CAMP = "LUMBER_CAMP"
    QUARRY = "QUARRY"
    FARM = "FARM"
    FACTORY = "FACTORY"
    DATACENTER = "DATACENTER"


class Era(Enum):
    """Game eras."""

    ORIGIN = 0
    INDUSTRIAL = 1
    INFORMATION = 2
    DOMINATION = 3


class ActionType(str, Enum):
    """Types of actions a nation can take."""

    SELL = "SELL"
    BUY = "BUY"
    BUILD = "BUILD"
    PASS = "PASS"


class TransactionStatus(str, Enum):
    """Status of a transaction."""

    PROPOSED = "PROPOSED"
    COUNTER_PROPOSED = "COUNTER_PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class LogType(str, Enum):
    """Types of log entries."""

    TURN_START = "TURN_START"
    GENERATION = "GENERATION"
    ERA_ADVANCEMENT = "ERA_ADVANCEMENT"
    TRADE_PROPOSAL = "TRADE_PROPOSAL"
    TRADE_COUNTER = "TRADE_COUNTER"
    TRADE_ACCEPTED = "TRADE_ACCEPTED"
    TRADE_REJECTED = "TRADE_REJECTED"
    TRADE_COMPLETED = "TRADE_COMPLETED"
    BUILD = "BUILD"
    ACTION = "ACTION"
    AI_DECISION = "AI_DECISION"

"""Game logging system for tracking all actions and AI decisions."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .enums import LogType


class AIDecision(BaseModel):
    """Records an AI decision with prompt and response."""

    nation_id: int
    prompt: str
    response: str
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class LogEntry(BaseModel):
    """Represents a single log entry."""

    log_type: LogType
    turn_number: int
    timestamp: datetime = Field(default_factory=datetime.now)
    nations_involved: List[int] = Field(default_factory=list)
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    ai_decisions: List[AIDecision] = Field(default_factory=list)

    def add_ai_decision(self, nation_id: int, prompt: str, response: str) -> None:
        """Add an AI decision to this log entry."""
        self.ai_decisions.append(
            AIDecision(nation_id=nation_id, prompt=prompt, response=response)
        )

    def get_ai_decision_for_nation(self, nation_id: int) -> Optional[AIDecision]:
        """Get AI decision for a specific nation."""
        for decision in self.ai_decisions:
            if decision.nation_id == nation_id:
                return decision
        return None

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class GameLog(BaseModel):
    """Manages all game logs."""

    entries: List[LogEntry] = Field(default_factory=list)

    def add_entry(
        self,
        log_type: LogType,
        turn_number: int,
        summary: str,
        nations_involved: List[int] = None,
        details: Dict[str, Any] = None,
    ) -> LogEntry:
        """Add a new log entry."""
        entry = LogEntry(
            log_type=log_type,
            turn_number=turn_number,
            summary=summary,
            nations_involved=nations_involved or [],
            details=details or {},
        )
        self.entries.append(entry)
        return entry

    def get_recent(self, limit: int = 50) -> List[LogEntry]:
        """Get recent log entries."""
        return self.entries[-limit:]

    def get_for_turn(self, turn_number: int) -> List[LogEntry]:
        """Get all log entries for a specific turn."""
        return [e for e in self.entries if e.turn_number == turn_number]

    def get_for_nation(self, nation_id: int, limit: int = 50) -> List[LogEntry]:
        """Get log entries involving a specific nation."""
        relevant = [e for e in self.entries if nation_id in e.nations_involved]
        return relevant[-limit:]

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

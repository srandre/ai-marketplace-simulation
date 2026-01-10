"""Asynchronous turn executor for non-blocking AI decisions."""

import threading
from queue import Queue
from typing import Optional, Callable


class TurnStatus:
    """Status of the current turn execution."""

    def __init__(self):
        self.current_action = ""
        self.is_processing = False
        self.error: Optional[str] = None
        self.lock = threading.Lock()

    def set_action(self, action: str):
        """Update the current action being performed."""
        with self.lock:
            self.current_action = action

    def get_action(self) -> str:
        """Get the current action."""
        with self.lock:
            return self.current_action

    def set_processing(self, processing: bool):
        """Set processing status."""
        with self.lock:
            self.is_processing = processing

    def is_busy(self) -> bool:
        """Check if currently processing."""
        with self.lock:
            return self.is_processing

    def set_error(self, error: Optional[str]):
        """Set error message."""
        with self.lock:
            self.error = error

    def get_error(self) -> Optional[str]:
        """Get error message."""
        with self.lock:
            return self.error


class AsyncTurnExecutor:
    """Executes turns asynchronously in a background thread."""

    def __init__(self, game_controller):
        self.controller = game_controller
        self.status = TurnStatus()
        self.turn_queue = Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False
        self.on_turn_complete: Optional[Callable] = None

    def start(self):
        """Start the background worker thread."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()

    def stop(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)

    def execute_turn_async(self):
        """Queue a turn for execution."""
        if not self.status.is_busy():
            self.turn_queue.put("execute")

    def _worker(self):
        """Background worker that processes turns."""
        while self.running:
            try:
                # Wait for a turn to execute (blocking with timeout)
                task = self.turn_queue.get(timeout=0.1)

                if task == "execute":
                    self._execute_turn_with_status()

                    # Notify completion
                    if self.on_turn_complete:
                        self.on_turn_complete()

            except:
                # Queue empty, continue
                pass

    def _execute_turn_with_status(self):
        """Execute a turn with two-phase system: Trading Phase (up to 2 trades) -> Build Phase (1 build)."""
        try:
            self.status.set_processing(True)
            self.status.set_error(None)

            current_nation = self.controller.game_state.get_current_nation()
            if not current_nation:
                return

            # Start turn
            self.status.set_action(f"{current_nation.name} begins their turn")
            self.controller.turn_manager.start_turn(current_nation.id)

            era_reqs = self.controller.game_state.get_era_advancement_requirements(current_nation.era)
            era_reqs_dict = {k.value: v for k, v in era_reqs.items()} if era_reqs else {}

            from ..models.enums import LogType

            # ===== TRADING PHASE =====
            trades_completed = 0
            trade_summaries = []

            for trade_attempt in range(2):  # Up to 2 trades
                game_state_summary = self.controller._build_game_state_summary()

                self.status.set_action(f"{current_nation.name} is considering trading...")
                decision, prompt, response = self.controller.decision_maker.decide_trading_phase(
                    current_nation, game_state_summary, era_reqs_dict, trades_completed
                )

                # Log the trading phase decision
                log_details = {"phase": "trading", "attempt": trade_attempt + 1, "decision": decision}
                summary_parts = []

                if decision.get("trade"):
                    target_id = decision.get("target_nation_id")
                    target_nation = self.controller.game_state.get_nation(target_id) if target_id is not None else None

                    if target_nation:
                        summary_parts.append(f"proposes trade with {target_nation.name}")
                        self.status.set_action(f"{current_nation.name} is proposing a trade to {target_nation.name}...")

                        # Add decision to nation's memory
                        current_nation.add_decision_to_memory(
                            round_number=self.controller.game_state.round_number,
                            turn_number=self.controller.game_state.turn_number,
                            decision_type="TRADE_PROPOSAL",
                            decision=decision,
                            reasoning=decision.get("reasoning", "")
                        )

                        # Log the proposal BEFORE executing the trade
                        summary = f"{current_nation.name} {', '.join(summary_parts)}"
                        log_entry = self.controller.game_state.game_log.add_entry(
                            log_type=LogType.AI_DECISION,
                            turn_number=self.controller.game_state.turn_number,
                            round_number=self.controller.game_state.round_number,
                            summary=summary,
                            nations_involved=[current_nation.id, target_id],
                            details=log_details,
                        )
                        log_entry.add_ai_decision(current_nation.id, prompt, response)

                        # Execute the trade
                        trade_action = {
                            "type": "TRADE",
                            "target_nation_id": target_id,
                            "offering": decision.get("offering", {}),
                            "requesting": decision.get("requesting", {}),
                            "reasoning": decision.get("reasoning", "")
                        }

                        result = self.controller._execute_trade_action(current_nation, trade_action)

                        # Update memory with outcome
                        if current_nation.memory:
                            current_nation.memory[-1].outcome = f"Trade {result.lower()} - {target_nation.name}"

                        if result == "ACCEPTED":
                            trades_completed += 1
                            trade_summaries.append(f"traded with {target_nation.name}")
                        elif result == "INVALID":
                            # Invalid trade - could be initiator or target lacks resources
                            trade_summaries.append(f"trade failed: insufficient resources")
                            print(f"[WARNING] {current_nation.name} proposed invalid trade to {target_nation.name} (insufficient resources)")
                        elif result == "REJECTED":
                            trade_summaries.append(f"trade rejected by {target_nation.name}")

                            # Allow one retry with a different partner ONLY for rejected trades
                            self.status.set_action(f"{current_nation.name} seeking alternative trade partner...")
                            retry_trade = self.controller._request_alternative_trade(current_nation, trade_action)

                            if retry_trade:
                                retry_target_id = retry_trade.get("target_nation_id")
                                retry_target = self.controller.game_state.get_nation(retry_target_id) if retry_target_id is not None else None

                                if retry_target:
                                    self.status.set_action(f"{current_nation.name} proposing alternative trade to {retry_target.name}...")
                                    retry_result = self.controller._execute_trade_action(current_nation, retry_trade)

                                    if retry_result == "ACCEPTED":
                                        trades_completed += 1
                                        trade_summaries.append(f"then traded with {retry_target.name}")
                                    elif retry_result == "REJECTED":
                                        trade_summaries.append(f"retry rejected by {retry_target.name}")
                                    else:
                                        trade_summaries.append(f"retry {retry_result.lower()}")
                            else:
                                # Nation decided not to retry - skip remaining trade opportunities
                                trade_summaries.append(f"decides not to retry, trading phase ends")
                                break  # Exit trading loop
                        else:
                            trade_summaries.append(f"trade {result.lower()}")
                    else:
                        summary_parts.append("invalid trade target")
                else:
                    summary_parts.append("skips trading")
                    # Log skip decision and break out of trading loop
                    summary = f"{current_nation.name} {', '.join(summary_parts)}"
                    log_entry = self.controller.game_state.game_log.add_entry(
                        log_type=LogType.AI_DECISION,
                        turn_number=self.controller.game_state.turn_number,
                        round_number=self.controller.game_state.round_number,
                        summary=summary,
                        nations_involved=[current_nation.id],
                        details=log_details,
                    )
                    log_entry.add_ai_decision(current_nation.id, prompt, response)
                    break

            # ===== BUILD PHASE =====
            # Check if nation can afford ANY generator
            can_afford_anything = self.controller._can_afford_any_generator(current_nation)

            if not can_afford_anything:
                # Mandatory turn skip - nation cannot afford any generator
                summary = f"{current_nation.name} skipped Build Phase (cannot afford any generators)"
                self.controller.game_state.game_log.add_entry(
                    log_type=LogType.ACTION,
                    turn_number=self.controller.game_state.turn_number,
                    round_number=self.controller.game_state.round_number,
                    summary=summary,
                    nations_involved=[current_nation.id],
                    details={"phase": "build", "reason": "insufficient_resources"}
                )
                self.status.set_action(f"{current_nation.name} cannot afford any generators")
            else:
                # Nation can afford something, let them decide
                game_state_summary = self.controller._build_game_state_summary()

                self.status.set_action(f"{current_nation.name} is considering building...")
                decision, prompt, response = self.controller.decision_maker.decide_build_phase(
                    current_nation, game_state_summary, era_reqs_dict
                )

                if decision.get("build"):
                    gen_type = decision.get("generator_type")

                    # Add decision to nation's memory
                    current_nation.add_decision_to_memory(
                        round_number=self.controller.game_state.round_number,
                        turn_number=self.controller.game_state.turn_number,
                        decision_type="BUILD",
                        decision=decision,
                        reasoning=decision.get("reasoning", "")
                    )

                    # First, log the AI's decision to build
                    summary = f"{current_nation.name} attempting to build {gen_type}"
                    log_entry = self.controller.game_state.game_log.add_entry(
                        log_type=LogType.AI_DECISION,
                        turn_number=self.controller.game_state.turn_number,
                        round_number=self.controller.game_state.round_number,
                        summary=summary,
                        nations_involved=[current_nation.id],
                        details={"phase": "build", "decision": decision},
                    )
                    log_entry.add_ai_decision(current_nation.id, prompt, response)

                    self.status.set_action(f"{current_nation.name} is constructing {gen_type}...")

                    # Then execute the build - the build manager will log success or failure
                    build_action = {
                        "generator_type": gen_type,
                        "payment_resource": decision.get("payment_resource"),
                        "reasoning": decision.get("reasoning", "")
                    }
                    self.controller._execute_build_from_plan(current_nation, build_action)
                else:
                    # Log if they explicitly skip building
                    summary = f"{current_nation.name} skipped building"
                    log_entry = self.controller.game_state.game_log.add_entry(
                        log_type=LogType.AI_DECISION,
                        turn_number=self.controller.game_state.turn_number,
                        round_number=self.controller.game_state.round_number,
                        summary=summary,
                        nations_involved=[current_nation.id],
                        details={"phase": "build", "decision": decision},
                    )
                    log_entry.add_ai_decision(current_nation.id, prompt, response)

            # End turn
            self.controller.turn_manager.end_turn()
            self.status.set_action(f"{current_nation.name} completed their turn")

        except Exception as e:
            import traceback
            error_msg = f"Error: {str(e)}"
            self.status.set_error(error_msg)
            print(f"Turn execution error: {e}")
            traceback.print_exc()
        finally:
            self.status.set_processing(False)

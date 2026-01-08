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
        """Execute a turn with status updates."""
        try:
            self.status.set_processing(True)
            self.status.set_error(None)

            current_nation = self.controller.game_state.get_current_nation()
            if not current_nation:
                return

            # Start turn
            self.status.set_action(f"{current_nation.name} begins their turn")
            self.controller.turn_manager.start_turn(current_nation.id)

            # AI decision making
            self.status.set_action(f"{current_nation.name} is planning their turn strategy...")
            era_reqs = self.controller.game_state.get_era_advancement_requirements(current_nation.era)
            era_reqs_dict = {k.value: v for k, v in era_reqs.items()} if era_reqs else {}
            game_state_summary = self.controller._build_game_state_summary()

            decision, prompt, response = self.controller.decision_maker.decide_all_actions(
                current_nation, game_state_summary, era_reqs_dict
            )

            # Log the AI decision
            from ..models.enums import LogType
            log_entry = self.controller.game_state.game_log.add_entry(
                log_type=LogType.AI_DECISION,
                turn_number=self.controller.game_state.turn_number,
                summary=f"{current_nation.name} planning turn actions",
                nations_involved=[current_nation.id],
                details={"decision": decision},
            )
            log_entry.add_ai_decision(current_nation.id, prompt, response)

            # Execute the planned actions
            actions = decision.get("actions", [])

            # Execute TRADE actions first
            for action in actions:
                if action.get("type") == "TRADE":
                    self.status.set_action(f"{current_nation.name} is proposing a trade...")
                    self.controller._execute_trade_action(current_nation, action)

            # Then execute BUILD actions
            for action in actions:
                if action.get("type") == "BUILD":
                    self.status.set_action(f"{current_nation.name} is constructing a generator...")
                    self.controller._execute_build_from_plan(current_nation, action)

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

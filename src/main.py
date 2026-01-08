"""Main entry point for the AI Nations game."""

from .game.game_controller import GameController
from .ui.main_window import MainWindow


def main():
    """Initialize and run the game."""
    print("=" * 60)
    print("AI Nations: Strategic Resource Game")
    print("=" * 60)
    print()
    print("Initializing game...")

    # Create game controller
    controller = GameController()
    controller.initialize()

    print(f"Game initialized with {len(controller.game_state.nations)} nations")
    print()
    print("Starting game window...")
    print()

    # Create and run main window
    window = MainWindow(controller)
    window.run()

    print()
    print("Game ended. Thank you for playing!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify that all dependencies are installed correctly."""

import sys


def check_dependencies():
    """Check if all required packages are installed."""
    print("Checking dependencies...")
    print()

    dependencies = [
        ("pygame", "Pygame"),
        ("requests", "Requests"),
        ("pydantic", "Pydantic"),
        ("yaml", "PyYAML"),
    ]

    all_ok = True

    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"✓ {display_name} is installed")
        except ImportError:
            print(f"✗ {display_name} is NOT installed")
            all_ok = False

    print()

    if all_ok:
        print("All dependencies are installed correctly!")
        print()
        print("You can now run the game with:")
        print("  python -m src.main")
        return 0
    else:
        print("Some dependencies are missing.")
        print()
        print("Please install them with:")
        print("  pip install -r requirements.txt")
        return 1


def check_config():
    """Check if configuration file exists."""
    import os

    config_path = os.path.join("config", "game_config.yaml")

    if os.path.exists(config_path):
        print(f"✓ Configuration file found: {config_path}")
        return True
    else:
        print(f"✗ Configuration file not found: {config_path}")
        return False


def main():
    """Main verification function."""
    print("=" * 60)
    print("AI Nations: Setup Verification")
    print("=" * 60)
    print()

    # Check dependencies
    deps_ok = check_dependencies() == 0

    print()

    # Check config
    config_ok = check_config()

    print()

    if deps_ok and config_ok:
        print("=" * 60)
        print("Setup verification PASSED!")
        print("=" * 60)
        return 0
    else:
        print("=" * 60)
        print("Setup verification FAILED!")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

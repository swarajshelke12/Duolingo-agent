"""
Duolingo Agent -- CLI Entry Point
AI-powered autonomous language learning agent.

Usage:
    python main.py                     # Standard mode (infinite lessons, auto-continue)
    python main.py --max-lessons 5     # Stop after 5 lessons
    python main.py --headless          # Run without visible browser
    python main.py --no-auto-continue  # Wait for user input between lessons
"""

import argparse
import sys
from duolingo_agent.config import Config
from duolingo_agent.agent import DuolingoAgent


def main():
    parser = argparse.ArgumentParser(
        description="Duolingo Agent -- AI-powered autonomous language learning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                       Run in continuous mode\n"
            "  python main.py --max-lessons 5        Complete 5 lessons then stop\n"
            "  python main.py --headless             Run without visible browser\n"
            "  python main.py --no-auto-continue     Prompt between lessons\n"
        ),
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome in headless mode (no visible window).",
    )
    parser.add_argument(
        "--max-lessons",
        type=int,
        default=0,
        help="Maximum number of lessons to complete (0 = infinite). Default: 0",
    )
    parser.add_argument(
        "--no-auto-continue",
        action="store_true",
        help="Wait for user input between lessons instead of auto-continuing.",
    )
    parser.add_argument(
        "--browser-path",
        type=str,
        default=None,
        help="Path to a custom Chrome or Chromium binary.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress debug-level log messages.",
    )

    args = parser.parse_args()

    # Build config from CLI args + .env file
    config = Config(
        headless=args.headless,
        browser_path=args.browser_path,
        max_lessons=args.max_lessons,
        auto_continue=not args.no_auto_continue,
        verbose=not args.quiet,
    )

    # Create and run agent
    agent = DuolingoAgent(config)

    try:
        agent.run()
    except KeyboardInterrupt:
        print("\n  Interrupted. Shutting down...")
    finally:
        agent.shutdown()


if __name__ == "__main__":
    main()

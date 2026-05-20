"""
service.py

CLI wrapper around the CLI usage generator.
"""

import logging
import sys
from pathlib import Path

from .generator import CLIUsageGenerator


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate CLI usage documentation from config.yaml")
    parser.add_argument("config_path", type=Path, help="Path to config.yaml")
    parser.add_argument("--output", type=Path, default=None, help="Output markdown file (default: CLI_USAGE.md next to config)")
    parser.add_argument("--stdout", action="store_true", help="Print the generated markdown to stdout")

    args = parser.parse_args()

    if not args.config_path.exists():
        print(f"ERROR: {args.config_path} not found", file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.INFO)
    generator = CLIUsageGenerator()

    if args.stdout:
        print(generator.render(args.config_path))
        return 0

    output_path = generator.generate(args.config_path, args.output)
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
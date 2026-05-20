#!/usr/bin/env python3
"""
main.py - CLI entry point for the Study Planner Agent.
"""

import argparse
import json
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="study-planner",
        description="Study Planner Agent - turn a goal into a short plan",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --goal "Learn Python data structures"
  echo "Prepare for system design interview" | python main.py --stdin
  python main.py --health
        """,
    )
    parser.add_argument("--goal", "-g", metavar="TEXT", help="Goal or learning objective")
    parser.add_argument("--stdin", action="store_true", help="Read the goal from stdin")
    parser.add_argument("--json", action="store_true", dest="output_json", help="Output raw JSON")
    parser.add_argument("--health", action="store_true", help="Run a health check")
    return parser


def read_goal(args) -> str:
    if args.stdin:
        return sys.stdin.read().strip()
    if args.goal:
        return args.goal.strip()

    print("Paste your goal below and press Ctrl+D/Ctrl+Z to finish:\n")
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines).strip()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    app_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(app_dir, "..", ".."))
    sys.path.insert(0, repo_root)
    sys.path.insert(0, app_dir)

    try:
        from agents.study_planner_agent import StudyPlannerAgent
    except ImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Install dependencies or run from the app directory.", file=sys.stderr)
        return 1

    agent = StudyPlannerAgent()
    agent.initialize()

    if args.health:
        print(json.dumps(agent.health(), indent=2))
        return 0

    goal = read_goal(args)
    if not goal:
        print("ERROR: Empty goal supplied", file=sys.stderr)
        return 1

    response = agent.run(goal)
    if args.output_json:
        print(json.dumps(response.to_dict(), indent=2))
    else:
        print(response.output["summary"])
        print()
        print("Plan:")
        for index, step in enumerate(response.output["plan"], start=1):
            print(f"  {index}. {step}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

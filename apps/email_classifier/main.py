#!/usr/bin/env python3
"""
main.py — CLI Entry Point
Distributed Agentic AI Application Platform
App: Email Classifier Agent

Usage:
    python main.py --email <path-to-email.txt>
    python main.py --email <path-to-email.txt> --api-key <gemini-api-key>
    python main.py --health
    echo "your email text" | python main.py --stdin
"""

import argparse
import json
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="email-classifier",
        description="📧 Email Classifier Agent — Simplify, Categorize & Prioritize emails",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --email email.txt
  python main.py --email email.txt --json
  python main.py --health
  echo "Call me ASAP about the contract" | python main.py --stdin
        """,
    )
    parser.add_argument(
        "--email", "-e",
        metavar="FILE",
        help="Path to a .txt file containing the email",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read email text from stdin",
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="Gemini API key (overrides GEMINI_API_KEY or GOOGLE_API_KEY env var)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON instead of formatted summary",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Run agent health check and exit",
    )
    return parser


def load_email(args) -> str:
    if args.stdin:
        print("📥 Reading email from stdin (Ctrl+D to finish)...\n")
        return sys.stdin.read().strip()

    if args.email:
        path = args.email
        if not os.path.exists(path):
            print(f"❌ File not found: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    # Interactive fallback
    print("📧 Paste your email text below. Press Enter twice then Ctrl+D (Unix) or Ctrl+Z (Win):\n")
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines).strip()


def run_health(agent):
    status = agent.health()
    print(json.dumps(status, indent=2))


def main():
    parser = build_parser()
    args = parser.parse_args()

    # ── Import agent (after path is set) ──────────────────────────
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from agents.email_classifier_agent import EmailClassifierAgent
    except ImportError as e:
        print(f"❌ Import error: {e}", file=sys.stderr)
        print("   Make sure you've run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    # ── Build agent ───────────────────────────────────────────────
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print(
            "❌ No API key found.\n"
            "   Set GEMINI_API_KEY (or GOOGLE_API_KEY) env var or pass --api-key <key>",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        agent = EmailClassifierAgent(api_key=api_key)
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Health check ──────────────────────────────────────────────
    if args.health:
        run_health(agent)
        return

    # ── Load email ────────────────────────────────────────────────
    email_text = load_email(args)
    if not email_text:
        print("❌ Empty email — nothing to classify.", file=sys.stderr)
        sys.exit(1)

    # ── Classify ──────────────────────────────────────────────────
    print("\n⚙️  Running Email Classifier Agent...\n")
    try:
        result = agent.classify(email_text)
    except Exception as e:
        print(f"❌ Classification failed: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Output ────────────────────────────────────────────────────
    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.summary())


if __name__ == "__main__":
    main()

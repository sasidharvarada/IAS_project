"""
Platform Artifact: Tool (Microservice)
PriorityScorerTool - assigns priority level and score to an email.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from .text_simplifier import BaseTool


@dataclass
class PriorityScorerTool(BaseTool):
    """
    Microservice: Determines email urgency.
    Returns priority (HIGH/MEDIUM/LOW), numeric score (1-10), and reason.
    """

    tool_id: str = "priority-scorer"
    model: Any = None

    SYSTEM = (
        "You are an email priority scoring engine. "
        "Given a simplified email and its category, assess urgency and importance. "
        "Respond ONLY with valid JSON:\n"
        '{"priority": "HIGH|MEDIUM|LOW", "score": <1-10>, "reason": "<one sentence>"}'
    )

    def run(self, simplified_email: str, category: str) -> dict:
        prompt = (
            f"Category: {category}\n"
            f"Email: {simplified_email}\n\n"
            f"Priority JSON:"
        )
        raw = self.model.complete(prompt, system=self.SYSTEM)

        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}
            priority = data.get("priority", "MEDIUM").upper()
            if priority not in ("HIGH", "MEDIUM", "LOW"):
                priority = "MEDIUM"
            return {
                "priority": priority,
                "score": int(data.get("score", 5)),
                "reason": data.get("reason", ""),
            }
        except Exception:
            return {"priority": "MEDIUM", "score": 5, "reason": "Could not determine priority."}

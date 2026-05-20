"""
Platform Artifact: Tool (Microservice)
EmailCategorizerTool - assigns a category to the simplified email.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from .text_simplifier import BaseTool


CATEGORIES = [
    "Work / Task Request",
    "Meeting / Scheduling",
    "Billing / Finance",
    "Support / Issue Report",
    "Spam / Promotion",
    "Personal",
    "Newsletter / Announcement",
    "Legal / Compliance",
    "Feedback / Review",
    "Other",
]


@dataclass
class EmailCategorizerTool(BaseTool):
    """
    Microservice: Categorizes the simplified email into a predefined class.
    Returns category name and confidence score (0.0 – 1.0).
    """

    tool_id: str = "email-categorizer"
    model: Any = None

    SYSTEM = (
        "You are an email categorization engine. "
        "Given a simplified email message, assign it to exactly one category "
        "from the list provided. Respond ONLY with valid JSON: "
        '{"category": "<name>", "confidence": <0.0-1.0>}'
    )

    def run(self, simplified_email: str) -> dict:
        cats = "\n".join(f"- {c}" for c in CATEGORIES)
        prompt = (
            f"Categories:\n{cats}\n\n"
            f"Email:\n{simplified_email}\n\n"
            f"JSON response:"
        )
        raw = self.model.complete(prompt, system=self.SYSTEM)

        # Parse JSON safely
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}
            return {
                "category": data.get("category", "Other"),
                "confidence": float(data.get("confidence", 0.5)),
            }
        except Exception:
            return {"category": "Other", "confidence": 0.0}

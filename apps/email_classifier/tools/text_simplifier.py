"""
Platform Artifact: Tool (Microservice)
TextSimplifierTool - strips jargon, signatures, and noise from raw email text.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


# ─────────────────────────────────────────────
#  BaseTool  (Platform Abstract Class)
# ─────────────────────────────────────────────

class BaseTool(ABC):
    """
    Platform base class for all Tool (microservice) artifacts.
    Tools are stateless, single-responsibility processing units.
    """

    tool_id: str = ""

    @abstractmethod
    def run(self, **inputs) -> dict:
        """Execute the tool logic and return output dict."""
        ...

    def health(self) -> dict:
        return {"tool_id": self.tool_id, "status": "ok"}


# ─────────────────────────────────────────────
#  TextSimplifierTool
# ─────────────────────────────────────────────

@dataclass
class TextSimplifierTool(BaseTool):
    """
    Microservice: Simplifies raw email text.
    - Removes signatures, footers, disclaimers
    - Extracts the core message in plain language
    """

    tool_id: str = "text-simplifier"
    model: Any = None     # injected: EmailLLMModel instance

    SYSTEM = (
        "You are an email preprocessing assistant. "
        "Your job is to extract only the core message from an email — "
        "remove signatures, legal disclaimers, greetings, footers, and filler. "
        "Return a concise 2-4 sentence plain-English summary of what the sender wants or says."
    )

    def run(self, raw_email: str) -> dict:
        prompt = f"Email:\n\n{raw_email}\n\nSimplified core message:"
        simplified = self.model.complete(prompt, system=self.SYSTEM)
        return {"simplified": simplified.strip()}

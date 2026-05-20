"""
Platform Artifact: Orchestrator
EmailPipelineOrchestrator - sequences the tool calls for email classification.

Strategy: sequential
  Step 1 → TextSimplifierTool
  Step 2 → EmailCategorizerTool
  Step 3 → PriorityScorerTool

The orchestrator owns the data flow between steps and
produces a unified EmailClassificationResult.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List


# ─────────────────────────────────────────────
#  BaseOrchestrator  (Platform Abstract Class)
# ─────────────────────────────────────────────

class BaseOrchestrator(ABC):
    """
    Platform base class for all Orchestrator artifacts.
    Orchestrators coordinate sequences / DAGs of tool invocations.
    """

    orchestrator_id: str = ""
    strategy: str = "sequential"   # sequential | parallel | conditional

    @abstractmethod
    def run(self, **inputs) -> dict:
        """Execute the orchestration pipeline and return aggregated results."""
        ...

    def health(self) -> dict:
        return {"orchestrator_id": self.orchestrator_id, "strategy": self.strategy, "status": "ok"}


# ─────────────────────────────────────────────
#  EmailClassificationResult
# ─────────────────────────────────────────────

@dataclass
class EmailClassificationResult:
    """Unified output produced by the email classification pipeline."""

    original_email: str = ""
    simplified: str = ""
    category: str = ""
    confidence: float = 0.0
    priority: str = ""
    score: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def summary(self) -> str:
        bar = "█" * self.score + "░" * (10 - self.score)
        priority_icons = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
        icon = priority_icons.get(self.priority, "⚪")
        return (
            f"\n{'═'*60}\n"
            f"  EMAIL CLASSIFICATION RESULT\n"
            f"{'═'*60}\n"
            f"  📧 Simplified:\n"
            f"     {self.simplified}\n\n"
            f"  🏷️  Category  : {self.category}  (confidence: {self.confidence:.0%})\n"
            f"  {icon} Priority  : {self.priority}  [{bar}] {self.score}/10\n"
            f"  💡 Reason    : {self.reason}\n"
            f"{'═'*60}\n"
        )


# ─────────────────────────────────────────────
#  EmailPipelineOrchestrator
# ─────────────────────────────────────────────

@dataclass
class EmailPipelineOrchestrator(BaseOrchestrator):
    """
    Sequential orchestrator for the email classification pipeline.

    Wires together:
      simplifier → categorizer → scorer
    """

    orchestrator_id: str = "email-pipeline-orchestrator"
    strategy: str = "sequential"

    # Tool artifacts injected at construction
    simplifier: Any = None
    categorizer: Any = None
    scorer: Any = None

    def run(self, raw_email: str) -> EmailClassificationResult:
        result = EmailClassificationResult(original_email=raw_email)

        # Step 1 – Simplify
        step1 = self.simplifier.run(raw_email=raw_email)
        result.simplified = step1["simplified"]

        # Step 2 – Categorize
        step2 = self.categorizer.run(simplified_email=result.simplified)
        result.category = step2["category"]
        result.confidence = step2["confidence"]

        # Step 3 – Prioritize
        step3 = self.scorer.run(
            simplified_email=result.simplified,
            category=result.category,
        )
        result.priority = step3["priority"]
        result.score = step3["score"]
        result.reason = step3["reason"]

        return result

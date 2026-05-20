"""
Platform Artifact: Agent
EmailClassifierAgent - top-level agent that assembles model, tools,
and orchestrator then exposes a single `classify(email_text)` method.

An Agent on this platform is the unit of deployment. It:
  - Holds references to its Model and Tools
  - Delegates pipeline execution to its Orchestrator
  - Is the artifact registered in the App Registry
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import os

from models.email_model import EmailLLMModel
from tools.text_simplifier import TextSimplifierTool
from tools.email_categorizer import EmailCategorizerTool
from tools.priority_scorer import PriorityScorerTool
from orchestrators.email_pipeline import EmailPipelineOrchestrator, EmailClassificationResult


# ─────────────────────────────────────────────
#  BaseAgent  (Platform Abstract Class)
# ─────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Platform base class for all Agent artifacts.
    An agent is the top-level deployable unit that:
      - owns a model
      - uses one or more tools
      - delegates multi-step logic to an orchestrator
    """

    agent_id: str = ""

    @abstractmethod
    def run(self, **inputs) -> dict:
        """Main entrypoint for the agent."""
        ...

    def health(self) -> dict:
        return {"agent_id": self.agent_id, "status": "ok"}


# ─────────────────────────────────────────────
#  EmailClassifierAgent
# ─────────────────────────────────────────────

@dataclass
class EmailClassifierAgent(BaseAgent):
    """
    Fully assembled Email Classifier Agent.

    Dependency graph (assembled in __post_init__):

        EmailLLMModel
            ├─► TextSimplifierTool
            ├─► EmailCategorizerTool
            └─► PriorityScorerTool
                        │
                        ▼
            EmailPipelineOrchestrator
                        │
                        ▼
              EmailClassifierAgent  ◄── you are here
    """

    agent_id: str = "email-classifier-agent"
    api_key: Optional[str] = field(default=None, repr=False)

    # Internal wiring (set in __post_init__)
    _model: EmailLLMModel = field(default=None, init=False, repr=False)
    _orchestrator: EmailPipelineOrchestrator = field(default=None, init=False, repr=False)

    def __post_init__(self):
        key = self.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            raise EnvironmentError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. "
                "Export it or pass api_key= to EmailClassifierAgent()."
            )
        os.environ["GEMINI_API_KEY"] = key

        # Instantiate model
        self._model = EmailLLMModel()

        # Instantiate tools (inject shared model)
        simplifier  = TextSimplifierTool(model=self._model)
        categorizer = EmailCategorizerTool(model=self._model)
        scorer      = PriorityScorerTool(model=self._model)

        # Wire orchestrator
        self._orchestrator = EmailPipelineOrchestrator(
            simplifier=simplifier,
            categorizer=categorizer,
            scorer=scorer,
        )

    # ------------------------------------------------------------------

    def run(self, raw_email: str) -> dict:
        """Run the full classification pipeline. Returns result dict."""
        result: EmailClassificationResult = self._orchestrator.run(raw_email=raw_email)
        return result.to_dict()

    def classify(self, raw_email: str) -> EmailClassificationResult:
        """Convenience method — returns the rich result object directly."""
        return self._orchestrator.run(raw_email=raw_email)

    def health(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "model": self._model.health(),
            "orchestrator": self._orchestrator.health(),
            "status": "ok",
        }

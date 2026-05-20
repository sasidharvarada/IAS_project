"""
Platform Artifact: Model
Base class + EmailLLMModel implementation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import os


# ─────────────────────────────────────────────
#  Base Model (Platform Abstract Class)
# ─────────────────────────────────────────────

class BaseModel(ABC):
    """
    Platform base class for all Model artifacts.
    Every model in the platform must subclass this.
    """

    model_id: str = ""
    provider: str = ""

    @abstractmethod
    def complete(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """Send a completion request and return text response."""
        ...

    @abstractmethod
    def health(self) -> dict:
        """Return health/status of the model connection."""
        ...


# ─────────────────────────────────────────────
#  EmailLLMModel  (Concrete Implementation)
# ─────────────────────────────────────────────

@dataclass
class EmailLLMModel(BaseModel):
    """
    Gemini-backed LLM model artifact.
    Used by the Email Classifier Agent for all LLM calls.
    """

    model_id: str = "gemini-2.5-flash"
    provider: str = "google"
    max_tokens: int = 1024
    temperature: float = 0.3
    _client: Any = field(default=None, repr=False, init=False)

    def __post_init__(self):
        try:
            from google import genai
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
            self._client = genai.Client(api_key=api_key)
        except ImportError:
            raise RuntimeError(
                "google-genai package not installed. Run: pip install google-genai"
            )

    def complete(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """Call the LLM and return the text response."""
        config = {
            "temperature": kwargs.get("temperature", self.temperature),
            "max_output_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        if system:
            config["system_instruction"] = system

        response = self._client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=config,
        )
        return (response.text or "").strip()

    def health(self) -> dict:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "status": "ok" if self._client else "error",
        }

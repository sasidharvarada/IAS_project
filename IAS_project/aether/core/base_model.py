"""
aether/core/models/base_model.py

Base class for all Model artifacts on the Distributed Agentic AI Platform.

A Model artifact is responsible for:
  - Wrapping any LLM / embedding / vision / multimodal provider
  - Exposing a uniform completion / embedding interface to Tools, Agents, Orchestrators
  - Reporting health and metadata to the Platform's VM Health Checker and App Registry

Subclass this to integrate any provider (Anthropic, OpenAI, Ollama, HuggingFace, etc.)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Optional


# ══════════════════════════════════════════════════════════════════
#  Enums & Constants
# ══════════════════════════════════════════════════════════════════

class ModelType(str, Enum):
    LLM         = "llm"
    EMBEDDING   = "embedding"
    VISION      = "vision"
    MULTIMODAL  = "multimodal"
    RERANKER    = "reranker"


class ModelStatus(str, Enum):
    UNINITIALIZED = "uninitialized"
    READY         = "ready"
    DEGRADED      = "degraded"
    UNAVAILABLE   = "unavailable"


# ══════════════════════════════════════════════════════════════════
#  Data Containers
# ══════════════════════════════════════════════════════════════════

@dataclass
class ModelResponse:
    """Uniform response envelope returned by every Model.complete() call."""
    text: str
    model_id: str
    input_tokens: int  = 0
    output_tokens: int = 0
    latency_ms: float  = 0.0
    raw: Any           = field(default=None, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class EmbeddingResponse:
    """Uniform response envelope returned by every Model.embed() call."""
    vectors: list[list[float]]
    model_id: str
    input_tokens: int = 0
    latency_ms: float = 0.0


@dataclass
class ModelMeta:
    """Static metadata surfaced to the App Registry and Platform UI."""
    model_id: str
    provider: str
    model_type: ModelType
    max_context_tokens: int      = 0
    supports_streaming: bool     = False
    supports_function_calling: bool = False
    supports_vision: bool        = False
    description: str             = ""
    tags: list[str]              = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
#  BaseModel
# ══════════════════════════════════════════════════════════════════

class BaseModel(ABC):
    """
    Abstract base class for all Model artifacts.

    Platform contract
    -----------------
    Every concrete Model must implement:
      • meta()       → ModelMeta        (registry + introspection)
      • initialize() → None             (lazy setup: load weights, create client)
      • complete()   → ModelResponse    (text generation)
      • health()     → dict             (VM health checker probe)

    Optionally override:
      • embed()      → EmbeddingResponse
      • stream()     → Iterator[str]
      • shutdown()   → None

    Lifecycle managed by the platform
    ----------------------------------
        initialize() → complete() / embed() / stream() → shutdown()
    """

    # ── Identity ──────────────────────────────────────────────────
    artifact_type: str = "model"

    def __init__(self):
        self._status: ModelStatus = ModelStatus.UNINITIALIZED
        self._initialized: bool   = False
        self._init_error: str     = ""

    # ── Abstract: must implement ──────────────────────────────────

    @abstractmethod
    def meta(self) -> ModelMeta:
        """Return static metadata. Called once on registration."""
        ...

    @abstractmethod
    def initialize(self) -> None:
        """
        One-time setup: load model weights, create API client, warm up connections.
        Called by the platform after deployment, before any inference.
        Must set self._status = ModelStatus.READY on success.
        """
        ...

    @abstractmethod
    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """
        Generate a text completion.

        Parameters
        ----------
        prompt      : User / human turn text.
        system      : Optional system / instruction prompt.
        max_tokens  : Hard cap on output tokens.
        temperature : Sampling temperature (0 = deterministic).
        stop        : Stop sequences.

        Returns
        -------
        ModelResponse with text, token counts, and latency.
        """
        ...

    @abstractmethod
    def health(self) -> dict:
        """
        Lightweight health probe called by the VM Health Checker.

        Must return at minimum:
          { "artifact_type": "model",
            "model_id": str,
            "status": ModelStatus,
            "initialized": bool }
        """
        ...

    # ── Optional: override if supported ───────────────────────────

    def embed(
        self,
        texts: list[str],
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings for a list of texts."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support embeddings."
        )

    def stream(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        """
        Stream tokens as they are generated.
        Default: falls back to complete() and yields the full text as one chunk.
        Override for true streaming.
        """
        response = self.complete(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        yield response.text

    def shutdown(self) -> None:
        """
        Release resources (connections, GPU memory, etc.).
        Called by the platform on graceful shutdown / redeployment.
        """
        self._status = ModelStatus.UNAVAILABLE
        self._initialized = False

    # ── Platform helpers (not meant to be overridden) ─────────────

    def _ensure_initialized(self) -> None:
        """Guard: call at the start of complete() / embed() / stream()."""
        if not self._initialized:
            raise RuntimeError(
                f"Model '{self.meta().model_id}' has not been initialized. "
                "The platform must call initialize() before inference."
            )

    def _timed_complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> ModelResponse:
        """Convenience wrapper that auto-injects latency_ms."""
        t0 = time.monotonic()
        response = self.complete(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        response.latency_ms = (time.monotonic() - t0) * 1000
        return response

    def __repr__(self) -> str:
        m = self.meta()
        return (
            f"<{self.__class__.__name__} "
            f"model_id={m.model_id!r} "
            f"provider={m.provider!r} "
            f"status={self._status.value!r}>"
        )

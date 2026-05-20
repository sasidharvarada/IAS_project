"""
aether/core/tools/base_tool.py

Base class for all Tool artifacts on the Distributed Agentic AI Platform.

A Tool artifact is:
  - A single-responsibility, stateless microservice
  - The atomic unit of capability exposed to Agents and Orchestrators
  - Introspectable: it declares its own input/output schema
  - Deployable independently on any tool-node in the distribution topology

Tool categories (set via ToolCategory):
  FUNCTION    – pure computation (math, parsing, formatting)
  API         – wraps an external REST / gRPC API
  DATABASE    – queries / mutates a data store
  FILE_IO     – reads / writes files or object storage
  BROWSER     – web scraping / automation
  CODE        – executes or analyses code
  SEARCH      – retrieves documents or web results
  NOTIFICATION– sends messages (email, Slack, webhook)
  CUSTOM      – anything else

Subclass BaseTool to implement any capability.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Type


# ══════════════════════════════════════════════════════════════════
#  Enums
# ══════════════════════════════════════════════════════════════════

class ToolCategory(str, Enum):
    FUNCTION     = "function"
    API          = "api"
    DATABASE     = "database"
    FILE_IO      = "file_io"
    BROWSER      = "browser"
    CODE         = "code"
    SEARCH       = "search"
    NOTIFICATION = "notification"
    CUSTOM       = "custom"


class ToolStatus(str, Enum):
    UNINITIALIZED = "uninitialized"
    READY         = "ready"
    DEGRADED      = "degraded"
    UNAVAILABLE   = "unavailable"


# ══════════════════════════════════════════════════════════════════
#  Schema & Metadata
# ══════════════════════════════════════════════════════════════════

@dataclass
class ToolParam:
    """Describes a single input or output parameter of a Tool."""
    name: str
    type: str                       # "string" | "int" | "float" | "bool" | "dict" | "list"
    description: str                = ""
    required: bool                  = True
    default: Any                    = None
    enum: Optional[list[Any]]       = None   # allowed values


@dataclass
class ToolSchema:
    """Declarative input/output contract for a Tool."""
    inputs:  list[ToolParam] = field(default_factory=list)
    outputs: list[ToolParam] = field(default_factory=list)

    def input_names(self)  -> list[str]: return [p.name for p in self.inputs]
    def output_names(self) -> list[str]: return [p.name for p in self.outputs]
    def required_inputs(self) -> list[str]:
        return [p.name for p in self.inputs if p.required]


@dataclass
class ToolMeta:
    """Static metadata surfaced to the App Registry and Agent tool-picker."""
    tool_id: str
    name: str
    description: str
    category: ToolCategory
    schema: ToolSchema               = field(default_factory=ToolSchema)
    version: str                     = "1.0.0"
    author: str                      = ""
    tags: list[str]                  = field(default_factory=list)
    is_async: bool                   = False
    timeout_seconds: float           = 30.0


@dataclass
class ToolResult:
    """Uniform result envelope returned by every Tool.run() call."""
    success: bool
    data: dict[str, Any]
    tool_id: str
    latency_ms: float = 0.0
    error: str        = ""

    @classmethod
    def ok(cls, tool_id: str, latency_ms: float = 0.0, **data) -> "ToolResult":
        return cls(success=True, data=data, tool_id=tool_id, latency_ms=latency_ms)

    @classmethod
    def fail(cls, tool_id: str, error: str, latency_ms: float = 0.0) -> "ToolResult":
        return cls(success=False, data={}, tool_id=tool_id, error=error, latency_ms=latency_ms)


# ══════════════════════════════════════════════════════════════════
#  BaseTool
# ══════════════════════════════════════════════════════════════════

class BaseTool(ABC):
    """
    Abstract base class for all Tool artifacts.

    Platform contract
    -----------------
    Every concrete Tool must implement:
      • meta()       → ToolMeta     (registry + agent tool-picker)
      • initialize() → None         (setup: connections, auth, warm-up)
      • execute()    → ToolResult   (core logic)
      • health()     → dict         (VM health checker probe)

    Lifecycle managed by the platform
    ----------------------------------
        initialize() → execute() [called N times] → shutdown()

    Calling convention
    ------------------
    Orchestrators and Agents call tool.run(**kwargs), NOT execute() directly.
    run() handles validation, timing, error wrapping, and retries.
    """

    artifact_type: str = "tool"

    def __init__(self):
        self._status: ToolStatus = ToolStatus.UNINITIALIZED
        self._initialized: bool  = False
        self._call_count: int    = 0
        self._error_count: int   = 0

    # ── Abstract: must implement ──────────────────────────────────

    @abstractmethod
    def meta(self) -> ToolMeta:
        """Return static metadata. Called once on registration."""
        ...

    @abstractmethod
    def initialize(self) -> None:
        """
        One-time setup: open DB connections, authenticate APIs, warm up resources.
        Must set self._status = ToolStatus.READY on success.
        """
        ...

    @abstractmethod
    def execute(self, **inputs: Any) -> ToolResult:
        """
        Core tool logic. Receives validated keyword arguments matching ToolSchema.inputs.
        Must return a ToolResult — use ToolResult.ok(**data) or ToolResult.fail(error=...).
        Do NOT catch all exceptions here; let run() handle them.
        """
        ...

    @abstractmethod
    def health(self) -> dict:
        """
        Lightweight health probe for the VM Health Checker.

        Must return at minimum:
          { "artifact_type": "tool",
            "tool_id": str,
            "status": ToolStatus,
            "call_count": int,
            "error_count": int }
        """
        ...

    # ── Optional: override if needed ─────────────────────────────

    def validate_inputs(self, inputs: dict[str, Any]) -> None:
        """
        Validate inputs against ToolSchema before execute() is called.
        Raise ValueError with a descriptive message on failure.
        Default: checks required fields are present.
        Override to add type-checking or domain validation.
        """
        schema = self.meta().schema
        missing = [
            name for name in schema.required_inputs()
            if name not in inputs
        ]
        if missing:
            raise ValueError(
                f"Tool '{self.meta().tool_id}' missing required inputs: {missing}"
            )

    def shutdown(self) -> None:
        """Release connections and resources. Called on graceful shutdown."""
        self._status = ToolStatus.UNAVAILABLE
        self._initialized = False

    # ── Platform entrypoint (not meant to be overridden) ─────────

    def run(self, **inputs: Any) -> ToolResult:
        """
        Platform-managed entrypoint.

        1. Guards initialization
        2. Validates inputs against schema
        3. Times the execute() call
        4. Wraps any uncaught exception into ToolResult.fail()
        5. Updates internal counters

        Agents and Orchestrators always call this, never execute() directly.
        """
        if not self._initialized:
            raise RuntimeError(
                f"Tool '{self.meta().tool_id}' has not been initialized. "
                "The platform must call initialize() before run()."
            )

        self.validate_inputs(inputs)
        self._call_count += 1
        t0 = time.monotonic()

        try:
            result = self.execute(**inputs)
            result.latency_ms = (time.monotonic() - t0) * 1000
            if not result.success:
                self._error_count += 1
            return result
        except Exception as exc:
            self._error_count += 1
            latency_ms = (time.monotonic() - t0) * 1000
            return ToolResult.fail(
                tool_id=self.meta().tool_id,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=latency_ms,
            )

    def __repr__(self) -> str:
        m = self.meta()
        return (
            f"<{self.__class__.__name__} "
            f"tool_id={m.tool_id!r} "
            f"category={m.category.value!r} "
            f"status={self._status.value!r}>"
        )

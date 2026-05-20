"""
aether/core/orchestrators/base_orchestrator.py

Base class for all Orchestrator artifacts on the Distributed Agentic AI Platform.

An Orchestrator artifact is responsible for:
  - Defining and executing the multi-step pipeline between Tools (and optionally Models)
  - Owning the data-flow: how outputs of one step become inputs of the next
  - Enforcing execution strategy: sequential, parallel, conditional, or DAG-based
  - Providing observability: step-by-step execution trace surfaced to the platform

Execution strategies
--------------------
  SEQUENTIAL   – steps run one-by-one, output of step N feeds step N+1
  PARALLEL     – steps run concurrently (thread pool), results merged
  CONDITIONAL  – next step chosen at runtime based on previous output
  DAG          – arbitrary directed-acyclic-graph of steps

Each step in the pipeline is described by an OrchestratorStep, which holds a
reference to a BaseTool (or any callable), its input mapping, and retry policy.
"""

from __future__ import annotations

import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ══════════════════════════════════════════════════════════════════
#  Enums
# ══════════════════════════════════════════════════════════════════

class PipelineStrategy(str, Enum):
    SEQUENTIAL  = "sequential"
    PARALLEL    = "parallel"
    CONDITIONAL = "conditional"
    DAG         = "dag"


class StepStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"
    SKIPPED   = "skipped"


class OrchestratorStatus(str, Enum):
    UNINITIALIZED = "uninitialized"
    READY         = "ready"
    RUNNING       = "running"
    DEGRADED      = "degraded"
    UNAVAILABLE   = "unavailable"


# ══════════════════════════════════════════════════════════════════
#  Step Definitions
# ══════════════════════════════════════════════════════════════════

@dataclass
class RetryPolicy:
    max_attempts: int   = 1       # total attempts (1 = no retry)
    delay_seconds: float = 1.0   # wait between retries
    backoff: float       = 2.0   # multiply delay by this each retry


@dataclass
class OrchestratorStep:
    """
    Describes one step in the pipeline.

    tool        : A BaseTool instance (or any callable that accepts **kwargs → dict)
    input_map   : Maps pipeline context keys → tool input parameter names.
                  e.g. {"raw_email": "raw_email"} or {"step1.simplified": "text"}
                  If None, the full pipeline context dict is unpacked as **kwargs.
    output_key  : Key under which this step's output dict is stored in context.
                  Defaults to the tool's tool_id.
    condition   : Optional callable(context) → bool. Step is SKIPPED if False.
    retry       : Retry policy for this step.
    """
    tool: Any                                # BaseTool | Callable
    input_map: Optional[dict[str, str]] = None
    output_key: Optional[str]           = None
    condition: Optional[Callable]       = None
    retry: RetryPolicy                  = field(default_factory=RetryPolicy)
    description: str                    = ""


# ══════════════════════════════════════════════════════════════════
#  Execution Trace
# ══════════════════════════════════════════════════════════════════

@dataclass
class StepTrace:
    """Records what happened at a single pipeline step."""
    step_index: int
    tool_id: str
    status: StepStatus
    inputs: dict[str, Any]  = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    latency_ms: float       = 0.0
    attempts: int           = 1
    error: str              = ""


@dataclass
class PipelineTrace:
    """Full execution trace for one pipeline run — surfaced to the platform."""
    orchestrator_id: str
    strategy: PipelineStrategy
    steps: list[StepTrace]         = field(default_factory=list)
    total_latency_ms: float        = 0.0
    success: bool                  = False
    error: str                     = ""

    def failed_steps(self) -> list[StepTrace]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    def skipped_steps(self) -> list[StepTrace]:
        return [s for s in self.steps if s.status == StepStatus.SKIPPED]


@dataclass
class OrchestratorMeta:
    """Static metadata surfaced to the App Registry."""
    orchestrator_id: str
    name: str
    description: str
    strategy: PipelineStrategy
    step_count: int      = 0
    version: str         = "1.0.0"
    tags: list[str]      = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
#  BaseOrchestrator
# ══════════════════════════════════════════════════════════════════

class BaseOrchestrator(ABC):
    """
    Abstract base class for all Orchestrator artifacts.

    Platform contract
    -----------------
    Every concrete Orchestrator must implement:
      • meta()        → OrchestratorMeta   (registry + introspection)
      • initialize()  → None               (assemble steps, validate wiring)
      • run()         → dict               (execute the pipeline, return final context)
      • health()      → dict               (VM health checker probe)

    Optionally override:
      • build_steps() → list[OrchestratorStep]  (declarative step builder)
      • on_step_start / on_step_success / on_step_failure  (hooks)

    Lifecycle managed by the platform
    ----------------------------------
        initialize() → run() [called N times] → shutdown()

    Data flow
    ---------
    run() maintains a mutable `context: dict` across all steps.
    Each step reads from context (via input_map) and writes back to context
    (via output_key). The final context is returned as the pipeline result.
    Agents receive this dict and extract what they need.
    """

    artifact_type: str = "orchestrator"

    def __init__(self):
        self._status: OrchestratorStatus   = OrchestratorStatus.UNINITIALIZED
        self._initialized: bool            = False
        self._steps: list[OrchestratorStep] = []
        self._run_count: int               = 0
        self._last_trace: Optional[PipelineTrace] = None

    # ── Abstract: must implement ──────────────────────────────────

    @abstractmethod
    def meta(self) -> OrchestratorMeta:
        """Return static metadata. Called once on registration."""
        ...

    @abstractmethod
    def initialize(self) -> None:
        """
        Assemble pipeline steps, validate tool wiring, check all tools are initialized.
        Must populate self._steps and set self._status = OrchestratorStatus.READY.
        """
        ...

    @abstractmethod
    def run(self, **inputs: Any) -> dict:
        """
        Execute the full pipeline.

        Parameters
        ----------
        **inputs : Initial pipeline context (e.g. raw_email="...", user_id="...")

        Returns
        -------
        dict : Final merged pipeline context containing all step outputs.
               Also sets self._last_trace for observability.
        """
        ...

    @abstractmethod
    def health(self) -> dict:
        """
        VM Health Checker probe.

        Must return at minimum:
          { "artifact_type": "orchestrator",
            "orchestrator_id": str,
            "status": OrchestratorStatus,
            "step_count": int,
            "run_count": int }
        """
        ...

    # ── Optional hooks (override to add logging / metrics / alerts) ──

    def on_step_start(self, step: OrchestratorStep, step_index: int, context: dict) -> None:
        """Called just before a step executes. Override for logging/tracing."""
        pass

    def on_step_success(self, step: OrchestratorStep, step_index: int, result: dict) -> None:
        """Called after a step succeeds. Override for metrics."""
        pass

    def on_step_failure(self, step: OrchestratorStep, step_index: int, error: str) -> None:
        """Called after a step fails (all retries exhausted). Override for alerting."""
        pass

    def on_pipeline_complete(self, trace: PipelineTrace, context: dict) -> None:
        """Called after the full pipeline finishes (success or failure)."""
        pass

    # ── Optional: override to define steps declaratively ─────────

    def build_steps(self) -> list[OrchestratorStep]:
        """
        Override to define the pipeline steps declaratively.
        Called by initialize() when self._steps is empty.
        """
        return []

    # ── Platform helpers ──────────────────────────────────────────

    def _resolve_inputs(
        self,
        step: OrchestratorStep,
        context: dict,
    ) -> dict[str, Any]:
        """
        Build the kwargs dict to pass into step.tool.run().

        If step.input_map is None: pass the full context as **kwargs.
        If step.input_map is provided: map context keys → tool param names.
          Supports dotted paths: "step1.simplified" → context["step1"]["simplified"]
        """
        if step.input_map is None:
            return dict(context)

        resolved = {}
        for context_key, tool_param in step.input_map.items():
            value = context
            for part in context_key.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)
                if value is None:
                    break
            resolved[tool_param] = value
        return resolved

    def _run_step_with_retry(
        self,
        step: OrchestratorStep,
        inputs: dict[str, Any],
        step_index: int,
    ) -> tuple[dict[str, Any], StepTrace]:
        """Execute a single step with retry logic. Returns (output_dict, trace)."""
        tool_id = getattr(step.tool, "meta", lambda: None)()
        tool_id = tool_id.tool_id if tool_id else repr(step.tool)

        trace = StepTrace(
            step_index=step_index,
            tool_id=tool_id,
            status=StepStatus.RUNNING,
            inputs=inputs,
        )
        t0 = time.monotonic()

        for attempt in range(1, step.retry.max_attempts + 1):
            try:
                # Support both BaseTool.run(**kwargs) and plain callables
                if hasattr(step.tool, "run"):
                    raw = step.tool.run(**inputs)
                    # BaseTool returns ToolResult; extract .data dict
                    output = raw.data if hasattr(raw, "data") else raw
                else:
                    output = step.tool(**inputs)

                trace.status     = StepStatus.SUCCESS
                trace.outputs    = output if isinstance(output, dict) else {"result": output}
                trace.latency_ms = (time.monotonic() - t0) * 1000
                trace.attempts   = attempt
                return trace.outputs, trace

            except Exception as exc:
                trace.error    = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
                trace.attempts = attempt
                if attempt < step.retry.max_attempts:
                    time.sleep(step.retry.delay_seconds * (step.retry.backoff ** (attempt - 1)))

        trace.status     = StepStatus.FAILED
        trace.latency_ms = (time.monotonic() - t0) * 1000
        return {}, trace

    def last_trace(self) -> Optional[PipelineTrace]:
        """Return the execution trace from the most recent run()."""
        return self._last_trace

    def shutdown(self) -> None:
        """Release resources. Called on graceful shutdown."""
        self._status = OrchestratorStatus.UNAVAILABLE
        self._initialized = False

    def __repr__(self) -> str:
        m = self.meta()
        return (
            f"<{self.__class__.__name__} "
            f"orchestrator_id={m.orchestrator_id!r} "
            f"strategy={m.strategy.value!r} "
            f"steps={len(self._steps)} "
            f"status={self._status.value!r}>"
        )

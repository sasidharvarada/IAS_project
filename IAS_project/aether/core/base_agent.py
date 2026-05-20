"""
aether/core/agents/base_agent.py

Base class for all Agent artifacts on the Distributed Agentic AI Platform.

An Agent artifact is:
  - The top-level deployable unit registered in the App Registry
  - The only artifact the external world (CLI, API, other services) talks to
  - Responsible for: assembling its Model, Tools, and Orchestrator;
    managing the conversation / task loop; and returning a structured AgentResponse

Agent loop modes
----------------
  SINGLE_TURN   – one input → one response (stateless, simplest)
  MULTI_TURN    – maintains conversation history across calls
  AGENTIC       – autonomous: can call tools iteratively until task is complete
                  (ReAct-style: Reason → Act → Observe → Reason …)

Every Agent has:
  - A primary Model (for reasoning / generation)
  - Zero or more Tools (capabilities it can invoke)
  - Zero or one Orchestrator (delegates multi-step pipeline coordination)
  - A memory context (conversation history + working memory)
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ══════════════════════════════════════════════════════════════════
#  Enums
# ══════════════════════════════════════════════════════════════════

class AgentLoopMode(str, Enum):
    SINGLE_TURN = "single_turn"
    MULTI_TURN  = "multi_turn"
    AGENTIC     = "agentic"


class AgentStatus(str, Enum):
    UNINITIALIZED = "uninitialized"
    IDLE          = "idle"
    RUNNING       = "running"
    DEGRADED      = "degraded"
    UNAVAILABLE   = "unavailable"


class RunStatus(str, Enum):
    SUCCESS  = "success"
    FAILED   = "failed"
    PARTIAL  = "partial"      # some steps succeeded, some failed
    TIMEOUT  = "timeout"


# ══════════════════════════════════════════════════════════════════
#  Memory
# ══════════════════════════════════════════════════════════════════

@dataclass
class Message:
    """A single turn in the agent's conversation history."""
    role: str           # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: float    = field(default_factory=time.time)
    metadata: dict      = field(default_factory=dict)


@dataclass
class AgentMemory:
    """
    Holds the agent's working context for a session.

    conversation : ordered list of Message objects (full history)
    working_mem  : short-term key-value scratch pad (cleared each run or session)
    session_id   : unique identifier for this session
    """
    session_id: str               = field(default_factory=lambda: str(uuid.uuid4()))
    conversation: list[Message]   = field(default_factory=list)
    working_mem: dict[str, Any]   = field(default_factory=dict)

    def add(self, role: str, content: str, **meta) -> None:
        self.conversation.append(Message(role=role, content=content, metadata=meta))

    def history_text(self, max_turns: int = 20) -> str:
        """Render the last N turns as a plain-text block for LLM prompting."""
        turns = self.conversation[-max_turns:]
        return "\n".join(f"[{m.role.upper()}] {m.content}" for m in turns)

    def clear_working_mem(self) -> None:
        self.working_mem.clear()

    def reset(self) -> None:
        self.conversation.clear()
        self.working_mem.clear()
        self.session_id = str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════════
#  AgentResponse
# ══════════════════════════════════════════════════════════════════

@dataclass
class AgentResponse:
    """
    Uniform response envelope returned by every Agent.run() call.

    output      : The primary result (text, dict, structured object — agent decides)
    status      : Overall run outcome
    session_id  : Ties the response back to an AgentMemory session
    tool_calls  : List of tool invocations that happened during this run
    latency_ms  : Wall-clock time for the entire agent run
    error       : Human-readable error description if status != SUCCESS
    metadata    : Any extra data the agent wants to surface (e.g. token usage)
    """
    output: Any
    status: RunStatus
    session_id: str
    tool_calls: list[dict]    = field(default_factory=list)
    latency_ms: float         = 0.0
    error: str                = ""
    metadata: dict[str, Any]  = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == RunStatus.SUCCESS

    def to_dict(self) -> dict:
        return {
            "output":      self.output,
            "status":      self.status.value,
            "session_id":  self.session_id,
            "tool_calls":  self.tool_calls,
            "latency_ms":  self.latency_ms,
            "error":       self.error,
            "metadata":    self.metadata,
        }


# ══════════════════════════════════════════════════════════════════
#  AgentMeta
# ══════════════════════════════════════════════════════════════════

@dataclass
class AgentMeta:
    """Static metadata surfaced to the App Registry."""
    agent_id: str
    name: str
    description: str
    loop_mode: AgentLoopMode
    model_id: str
    tool_ids: list[str]          = field(default_factory=list)
    orchestrator_id: str         = ""
    version: str                 = "1.0.0"
    author: str                  = ""
    tags: list[str]              = field(default_factory=list)
    max_iterations: int          = 10        # for AGENTIC mode


# ══════════════════════════════════════════════════════════════════
#  BaseAgent
# ══════════════════════════════════════════════════════════════════

class BaseAgent(ABC):
    """
    Abstract base class for all Agent artifacts.

    Platform contract
    -----------------
    Every concrete Agent must implement:
      • meta()         → AgentMeta       (registry + introspection)
      • initialize()   → None            (wire model / tools / orchestrator)
      • run()          → AgentResponse   (main task entrypoint)
      • health()       → dict            (VM health checker probe)

    Optionally override:
      • on_run_start / on_run_end        (lifecycle hooks)
      • reset_memory()                   (clear session state)
      • tool_ids()                       (dynamic tool list)

    Lifecycle managed by the platform
    ----------------------------------
        initialize() → run() [called N times] → shutdown()

    Dependency injection
    --------------------
    The platform (or the Agent's own __init__ / initialize()) is responsible
    for injecting a concrete Model, Tools, and Orchestrator.
    BaseAgent does NOT instantiate dependencies — it only declares the
    interface through which they are accessed.

    Memory
    ------
    Each Agent owns an AgentMemory instance. In SINGLE_TURN mode the memory
    is reset after each run. In MULTI_TURN and AGENTIC modes it persists
    across calls within a session.
    """

    artifact_type: str = "agent"

    def __init__(self):
        self._status: AgentStatus         = AgentStatus.UNINITIALIZED
        self._initialized: bool           = False
        self._memory: AgentMemory         = AgentMemory()
        self._run_count: int              = 0
        self._last_response: Optional[AgentResponse] = None

    # ── Abstract: must implement ──────────────────────────────────

    @abstractmethod
    def meta(self) -> AgentMeta:
        """Return static metadata. Called once on registration."""
        ...

    @abstractmethod
    def initialize(self) -> None:
        """
        Wire together Model, Tools, and Orchestrator.
        Validate that all dependencies are initialized and reachable.
        Must set self._status = AgentStatus.IDLE on success.
        """
        ...

    @abstractmethod
    def run(self, user_input: str, **kwargs: Any) -> AgentResponse:
        """
        Main entrypoint. Receives a user message (or task description) and
        returns a structured AgentResponse.

        Implementations should:
          1. Add user_input to self._memory
          2. Invoke orchestrator / tools / model as needed
          3. Add assistant response to self._memory
          4. Return AgentResponse

        Use self._timed_run() if you want automatic latency tracking.
        """
        ...

    @abstractmethod
    def health(self) -> dict:
        """
        VM Health Checker probe.

        Must return at minimum:
          { "artifact_type": "agent",
            "agent_id": str,
            "status": AgentStatus,
            "loop_mode": str,
            "run_count": int }
        """
        ...

    # ── Optional hooks ─────────────────────────────────────────────

    def on_run_start(self, user_input: str, kwargs: dict) -> None:
        """Called at the start of run(). Override for logging / rate-limiting."""
        pass

    def on_run_end(self, response: AgentResponse) -> None:
        """Called after run() completes. Override for metrics / audit logging."""
        pass

    def on_tool_call(self, tool_id: str, inputs: dict, result: Any) -> None:
        """Called each time the agent invokes a tool. Override for tracing."""
        pass

    # ── Optional: override for custom behavior ─────────────────────

    def reset_memory(self) -> None:
        """Reset conversation history and working memory."""
        self._memory.reset()

    def get_memory(self) -> AgentMemory:
        """Return the agent's current memory (read-only intended)."""
        return self._memory

    def shutdown(self) -> None:
        """Release resources. Called on graceful shutdown."""
        self._status = AgentStatus.UNAVAILABLE
        self._initialized = False

    # ── Platform helpers ───────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        """Guard: call at the start of run()."""
        if not self._initialized:
            raise RuntimeError(
                f"Agent '{self.meta().agent_id}' has not been initialized. "
                "The platform must call initialize() before run()."
            )

    def _timed_run(
        self,
        user_input: str,
        **kwargs: Any,
    ) -> AgentResponse:
        """
        Wraps run() with timing, hooks, counter increments, and last-response storage.
        Concrete agents can call super()._timed_run(...) or implement their own timing.
        NOT meant to be called by external code — use run() instead.
        """
        self._ensure_initialized()
        self._status = AgentStatus.RUNNING
        self._run_count += 1
        self.on_run_start(user_input, kwargs)

        t0 = time.monotonic()
        try:
            response = self.run(user_input, **kwargs)
            response.latency_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:
            response = AgentResponse(
                output=None,
                status=RunStatus.FAILED,
                session_id=self._memory.session_id,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        finally:
            self._status = AgentStatus.IDLE

        self._last_response = response
        self.on_run_end(response)
        return response

    def last_response(self) -> Optional[AgentResponse]:
        """Return the AgentResponse from the most recent run()."""
        return self._last_response

    def __repr__(self) -> str:
        m = self.meta()
        return (
            f"<{self.__class__.__name__} "
            f"agent_id={m.agent_id!r} "
            f"loop_mode={m.loop_mode.value!r} "
            f"status={self._status.value!r}>"
        )

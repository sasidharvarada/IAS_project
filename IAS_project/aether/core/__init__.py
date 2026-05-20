"""
aether/core/__init__.py

Single import surface for the Distributed Agentic AI Application Platform
base classes. App developers import from here.

Usage
-----
    from aether.core import (
        BaseModel, ModelMeta, ModelResponse,
        BaseTool, ToolMeta, ToolResult, ToolSchema, ToolParam,
        BaseOrchestrator, OrchestratorMeta, OrchestratorStep, PipelineStrategy,
        BaseAgent, AgentMeta, AgentResponse, AgentMemory,
    )
"""

from .base_model import (
    BaseModel,
    ModelType,
    ModelStatus,
    ModelResponse,
    EmbeddingResponse,
    ModelMeta,
)

from .base_tool import (
    BaseTool,
    ToolCategory,
    ToolStatus,
    ToolParam,
    ToolSchema,
    ToolMeta,
    ToolResult,
)

from .base_orchestrator import (
    BaseOrchestrator,
    PipelineStrategy,
    StepStatus,
    OrchestratorStatus,
    RetryPolicy,
    OrchestratorStep,
    StepTrace,
    PipelineTrace,
    OrchestratorMeta,
)

from .base_agent import (
    BaseAgent,
    AgentLoopMode,
    AgentStatus,
    RunStatus,
    Message,
    AgentMemory,
    AgentResponse,
    AgentMeta,
)

__all__ = [
    # ── Model ──────────────────────────────────────
    "BaseModel",
    "ModelType",
    "ModelStatus",
    "ModelResponse",
    "EmbeddingResponse",
    "ModelMeta",
    # ── Tool ───────────────────────────────────────
    "BaseTool",
    "ToolCategory",
    "ToolStatus",
    "ToolParam",
    "ToolSchema",
    "ToolMeta",
    "ToolResult",
    # ── Orchestrator ───────────────────────────────
    "BaseOrchestrator",
    "PipelineStrategy",
    "StepStatus",
    "OrchestratorStatus",
    "RetryPolicy",
    "OrchestratorStep",
    "StepTrace",
    "PipelineTrace",
    "OrchestratorMeta",
    # ── Agent ──────────────────────────────────────
    "BaseAgent",
    "AgentLoopMode",
    "AgentStatus",
    "RunStatus",
    "Message",
    "AgentMemory",
    "AgentResponse",
    "AgentMeta",
]

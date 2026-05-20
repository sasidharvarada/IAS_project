from __future__ import annotations

import re
from typing import Any

from aether.core.base_tool import BaseTool, ToolCategory, ToolMeta, ToolParam, ToolResult, ToolSchema, ToolStatus


class GoalAnalyzerTool(BaseTool):
    def meta(self) -> ToolMeta:
        return ToolMeta(
            tool_id="goal-analyzer",
            name="Goal Analyzer",
            description="Extracts topics and difficulty from a learning goal",
            category=ToolCategory.FUNCTION,
            schema=ToolSchema(
                inputs=[ToolParam(name="raw_goal", type="string", description="Learning goal")],
                outputs=[
                    ToolParam(name="topics", type="list", description="Key topics"),
                    ToolParam(name="difficulty", type="string", description="Estimated difficulty"),
                ],
            ),
        )

    def initialize(self) -> None:
        self._initialized = True
        self._status = ToolStatus.READY

    def execute(self, **inputs: Any) -> ToolResult:
        raw_goal = str(inputs.get("raw_goal", "")).strip()
        words = [w for w in re.findall(r"[A-Za-z0-9]+", raw_goal.lower()) if len(w) > 2]
        stop_words = {"learn", "study", "understand", "about", "into", "with", "from", "this", "that"}
        topics = [word for word in words if word not in stop_words]
        topics = list(dict.fromkeys(topics))[:5]
        difficulty = "easy"
        if any(term in raw_goal.lower() for term in ("interview", "system design", "advanced", "deep")):
            difficulty = "hard"
        elif len(topics) >= 4:
            difficulty = "medium"
        return ToolResult.ok(self.meta().tool_id, topics=topics, difficulty=difficulty)

    def health(self) -> dict:
        return {"artifact_type": "tool", "tool_id": self.meta().tool_id, "status": self._status.value, "call_count": self._call_count, "error_count": self._error_count}

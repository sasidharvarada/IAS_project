from __future__ import annotations

from typing import Any

from aether.core.base_tool import BaseTool, ToolCategory, ToolMeta, ToolParam, ToolResult, ToolSchema, ToolStatus


class SessionPlannerTool(BaseTool):
    def meta(self) -> ToolMeta:
        return ToolMeta(
            tool_id="session-planner",
            name="Session Planner",
            description="Turns topics into a day-by-day study plan",
            category=ToolCategory.FUNCTION,
            schema=ToolSchema(
                inputs=[
                    ToolParam(name="topics", type="list", description="List of topics"),
                    ToolParam(name="difficulty", type="string", description="Difficulty estimate"),
                ],
                outputs=[
                    ToolParam(name="plan", type="list", description="Study sessions"),
                    ToolParam(name="estimated_days", type="int", description="Suggested duration"),
                ],
            ),
        )

    def initialize(self) -> None:
        self._initialized = True
        self._status = ToolStatus.READY

    def execute(self, **inputs: Any) -> ToolResult:
        topics = list(inputs.get("topics", []))
        difficulty = str(inputs.get("difficulty", "easy"))

        if not topics:
            topics = ["overview", "practice", "review"]

        day_count = 3 if difficulty == "easy" else 5 if difficulty == "medium" else 7
        plan = []
        for index, topic in enumerate(topics, start=1):
            plan.append(f"Day {index}: study {topic} and write 3 notes")
        while len(plan) < day_count:
            plan.append(f"Day {len(plan) + 1}: review notes and do one practice exercise")

        return ToolResult.ok(self.meta().tool_id, plan=plan, estimated_days=len(plan))

    def health(self) -> dict:
        return {"artifact_type": "tool", "tool_id": self.meta().tool_id, "status": self._status.value, "call_count": self._call_count, "error_count": self._error_count}

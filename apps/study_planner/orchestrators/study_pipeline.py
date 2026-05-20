from __future__ import annotations

from typing import Any

from aether.core.base_orchestrator import BaseOrchestrator, OrchestratorMeta, OrchestratorStep, PipelineStrategy, OrchestratorStatus

from tools.goal_analyzer import GoalAnalyzerTool
from tools.session_planner import SessionPlannerTool


class StudyPipelineOrchestrator(BaseOrchestrator):
    def meta(self) -> OrchestratorMeta:
        return OrchestratorMeta(
            orchestrator_id="study-pipeline-orchestrator",
            name="Study Pipeline Orchestrator",
            description="Analyzes a goal and turns it into a short study plan",
            strategy=PipelineStrategy.SEQUENTIAL,
            step_count=2,
        )

    def initialize(self) -> None:
        goal_analyzer = GoalAnalyzerTool()
        session_planner = SessionPlannerTool()
        goal_analyzer.initialize()
        session_planner.initialize()
        self._steps = [
            OrchestratorStep(tool=goal_analyzer, input_map={"raw_goal": "raw_goal"}, output_key="analysis"),
            OrchestratorStep(tool=session_planner, input_map={"topics": "analysis.topics", "difficulty": "analysis.difficulty"}, output_key="plan"),
        ]
        self._initialized = True
        self._status = OrchestratorStatus.READY

    def run(self, **inputs: Any) -> dict:
        context = dict(inputs)
        analysis = self._steps[0].tool.run(raw_goal=context.get("raw_goal", ""))
        context["analysis"] = analysis.data
        plan = self._steps[1].tool.run(topics=analysis.data["topics"], difficulty=analysis.data["difficulty"])
        context["plan"] = plan.data
        context["final_plan"] = plan.data["plan"]
        return context

    def health(self) -> dict:
        return {"artifact_type": "orchestrator", "orchestrator_id": self.meta().orchestrator_id, "status": self._status.value, "step_count": len(self._steps), "run_count": self._run_count}

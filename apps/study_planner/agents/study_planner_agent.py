from __future__ import annotations

import time
from typing import Any

from aether.core.base_agent import AgentLoopMode, AgentMeta, AgentResponse, AgentStatus, BaseAgent, RunStatus

from models.study_model import StudyPlanModel
from orchestrators.study_pipeline import StudyPipelineOrchestrator
from tools.goal_analyzer import GoalAnalyzerTool
from tools.session_planner import SessionPlannerTool


class StudyPlannerAgent(BaseAgent):
    def meta(self) -> AgentMeta:
        return AgentMeta(
            agent_id="study-planner-agent",
            name="Study Planner Agent",
            description="Turns a learning goal into a compact study plan",
            loop_mode=AgentLoopMode.AGENTIC,
            model_id="study-plan-model",
            tool_ids=["goal-analyzer", "session-planner"],
            orchestrator_id="study-pipeline-orchestrator",
            tags=["planner", "education", "productivity"],
        )

    def initialize(self) -> None:
        self.model = StudyPlanModel()
        self.goal_analyzer = GoalAnalyzerTool()
        self.session_planner = SessionPlannerTool()
        self.orchestrator = StudyPipelineOrchestrator()

        self.model.initialize()
        self.goal_analyzer.initialize()
        self.session_planner.initialize()
        self.orchestrator.initialize()

        self._initialized = True
        self._status = AgentStatus.IDLE

    def run(self, user_input: str, **kwargs: Any) -> AgentResponse:
        if not self._initialized:
            self.initialize()

        t0 = time.monotonic()
        self._run_count += 1
        self._memory.add("user", user_input)

        pipeline = self.orchestrator.run(raw_goal=user_input)
        prompt = pipeline["raw_goal"] if "raw_goal" in pipeline else user_input
        model_response = self.model.complete(prompt)

        summary = f"{model_response.text}\n\nSuggested sessions: {len(pipeline['final_plan'])}"
        output = {
            "goal": user_input,
            "analysis": pipeline["analysis"],
            "plan": pipeline["final_plan"],
            "summary": summary,
        }

        self._memory.add("assistant", summary)
        latency_ms = (time.monotonic() - t0) * 1000
        response = AgentResponse(
            output=output,
            status=RunStatus.SUCCESS,
            session_id=self._memory.session_id,
            tool_calls=[
                {"tool_id": "goal-analyzer", "status": "success"},
                {"tool_id": "session-planner", "status": "success"},
            ],
            latency_ms=latency_ms,
        )
        self._last_response = response
        return response

    def health(self) -> dict:
        return {
            "artifact_type": "agent",
            "agent_id": self.meta().agent_id,
            "status": self._status.value,
            "loop_mode": self.meta().loop_mode.value,
            "run_count": self._run_count,
        }

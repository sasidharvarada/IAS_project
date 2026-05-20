from __future__ import annotations

from typing import Any

from aether.core.base_model import BaseModel, ModelMeta, ModelResponse, ModelType, ModelStatus


class StudyPlanModel(BaseModel):
    def meta(self) -> ModelMeta:
        return ModelMeta(
            model_id="study-plan-model",
            provider="local",
            model_type=ModelType.LLM,
            description="Heuristic local planner model",
        )

    def initialize(self) -> None:
        self._initialized = True
        self._status = ModelStatus.READY

    def complete(self, prompt: str, **kwargs: Any) -> ModelResponse:
        goal = prompt.strip() or "study goal"
        text = f"Focus on {goal}. Break the work into short daily sessions, take notes, and do one practice task per day."
        return ModelResponse(text=text, model_id=self.meta().model_id)

    def health(self) -> dict:
        return {"artifact_type": "model", "model_id": self.meta().model_id, "status": self._status.value, "initialized": self._initialized}

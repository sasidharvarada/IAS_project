"""
routes.py

Lifecycle manager API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .controller import controller

router = APIRouter()


class RegisterDeploymentRequest(BaseModel):
    app_id: str
    app_version: str
    process_records: list[dict] = Field(default_factory=list)


class ActionRequest(BaseModel):
    app_version: str | None = None
    reason: str = ""


class ScaleRequest(BaseModel):
    replicas: int = Field(..., ge=1)


class RollbackRequest(BaseModel):
    target_version: str


@router.post("/{app_id}/register")
def register_deployment(app_id: str, request: RegisterDeploymentRequest) -> dict:
    payload = request.model_dump()
    payload["app_id"] = app_id
    controller.register_deployment_dict(payload)
    return {"status": "ok", "app_id": app_id}


@router.get("/{app_id}/status")
def app_status(app_id: str) -> dict:
    return controller.status(app_id)


@router.post("/{app_id}/start")
def start_app(app_id: str, request: ActionRequest) -> dict:
    try:
        return controller.start(app_id, app_version=request.app_version).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{app_id}/stop")
def stop_app(app_id: str, request: ActionRequest) -> dict:
    try:
        return controller.stop(app_id, app_version=request.app_version).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{app_id}/restart")
def restart_app(app_id: str, request: ActionRequest) -> dict:
    try:
        return controller.restart(app_id, app_version=request.app_version, reason=request.reason).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{app_id}/scale")
def scale_app(app_id: str, request: ScaleRequest) -> dict:
    try:
        return controller.scale(app_id, request.replicas).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{app_id}/rollback")
def rollback_app(app_id: str, request: RollbackRequest) -> dict:
    try:
        return controller.rollback(app_id, request.target_version).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

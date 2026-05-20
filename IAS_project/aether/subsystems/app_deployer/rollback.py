"""
rollback.py

Rollback helper stub for restoring a previous app version.

This module is present to match the documented platform architecture.
The full rollback workflow is not implemented yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class RollbackRequest:
    app_id: str
    current_version: str
    previous_version: str
    vm_ip: str = ""


class RollbackManager:
    """Stub rollback manager for future implementation."""

    def rollback(self, request: RollbackRequest) -> Dict[str, Any]:
        raise NotImplementedError(
            "Rollback is documented in the architecture but not implemented yet."
        )
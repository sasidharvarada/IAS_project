"""
platform/subsystems/user_management/rbac.py

Role-based access control.
Provides require_role(), a FastAPI dependency factory that enforces
that the current user holds one of the specified roles.

Roles (from architecture):
  developer  – can deploy and manage their own apps
  admin      – full platform access
  viewer     – read-only access
"""

from fastapi import Depends, HTTPException, status

from .auth import get_current_user
from .models import Role, User


def require_role(*roles: Role):
    """
    Dependency factory.  Usage:

        @router.get("/admin-only")
        def admin_endpoint(user: User = Depends(require_role(Role.admin))):
            ...

        @router.post("/deploy")
        def deploy(user: User = Depends(require_role(Role.developer, Role.admin))):
            ...
    """
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user

    return _check

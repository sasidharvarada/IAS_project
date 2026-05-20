from pydantic import BaseModel
from typing import List, Optional

class ValidationReport(BaseModel):
    passed: bool
    errors: List[str] = []
    warnings: List[str] = []
    app_name: Optional[str] = None
    app_version: Optional[str] = None

"""
service.py

HTTP + CLI entry point for the build packager.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .builder import BuildPackager


class BuildRequest(BaseModel):
    source: str = Field(..., description="Path to a local app directory, ZIP, or git repo URL")
    output: Optional[str] = Field(default=None, description="Optional output .aether.zip path")
    skip_dependency_check: bool = Field(default=False, description="Skip dependency dry-run")
    skip_syntax_check: bool = Field(default=False, description="Skip Python syntax validation")


class BuildResponse(BaseModel):
    output_path: str
    source_path: str
    manifest: dict[str, Any]
    build_messages: list[str]


app = FastAPI(title="Aether Build Packager", version="1.0.0")


@app.post("/apps/build", response_model=BuildResponse)
def build_app(request: BuildRequest) -> BuildResponse:
    packager = BuildPackager()

    try:
        result = packager.build(
            request.source,
            Path(request.output) if request.output else None,
            skip_dependency_check=request.skip_dependency_check,
            skip_syntax_check=request.skip_syntax_check,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BuildResponse(**result.to_dict())


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build and package Aether apps into .aether.zip archives")
    parser.add_argument("source", help="Path to app source directory, ZIP, or git repo URL")
    parser.add_argument("--output", type=Path, default=None, help="Output .aether.zip path")
    parser.add_argument("--skip-dependency-check", action="store_true", help="Skip pip dry-run dependency resolution")
    parser.add_argument("--skip-syntax-check", action="store_true", help="Skip Python syntax validation")
    parser.add_argument("--json", action="store_true", help="Print build result as JSON")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    packager = BuildPackager()

    try:
        result = packager.build(
            args.source,
            args.output,
            skip_dependency_check=args.skip_dependency_check,
            skip_syntax_check=args.skip_syntax_check,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
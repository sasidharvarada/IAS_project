"""
builder.py

Validate app source trees and package them into .aether.zip archives.
"""

from __future__ import annotations

import compileall
import dataclasses
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

logger = logging.getLogger("aether.subsystems.build_packager")


@dataclass
class BuildManifest:
    build_id: str
    app_name: str
    app_version: str
    source_type: str
    source_reference: str
    created_at: float
    python_version: str
    files_count: int
    py_files_count: int
    validated: bool = False
    dependency_check_passed: bool = False
    syntax_check_passed: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = dataclasses.asdict(self)
        data["created_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.created_at))
        return data


@dataclass
class BuildResult:
    output_path: Path
    manifest: BuildManifest
    source_path: Path
    build_messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "source_path": str(self.source_path),
            "manifest": self.manifest.to_dict(),
            "build_messages": self.build_messages,
        }


class BuildPackager:
    """Build, validate, and package apps into .aether.zip archives."""

    def __init__(self, python_executable: Optional[str] = None):
        self.python_executable = python_executable or sys.executable

    @staticmethod
    def _is_git_reference(source: Union[str, Path]) -> bool:
        if isinstance(source, Path):
            return False
        lowered = source.lower()
        return lowered.startswith(("http://", "https://", "git@")) or lowered.endswith(".git")

    def _resolve_source(self, source: Union[str, Path]) -> Tuple[Path, str, tempfile.TemporaryDirectory, Optional[Path]]:
        """Resolve a local folder, ZIP, or git reference into a source directory."""
        cleanup = tempfile.TemporaryDirectory(prefix="aether-build-")
        temp_root = Path(cleanup.name)

        source_ref = str(source)
        source_path = Path(source_ref) if not self._is_git_reference(source) else None

        if source_path is not None:
            if not source_path.exists():
                raise FileNotFoundError(f"Source path not found: {source_path}")

            if source_path.is_dir():
                return source_path.resolve(), "directory", cleanup, None

            if source_path.suffix.lower() == ".zip":
                extract_dir = temp_root / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(source_path, "r") as archive:
                    archive.extractall(extract_dir)
                return self._select_source_root(extract_dir), "zip", cleanup, source_path.resolve()

            raise ValueError("Source must be a directory, .zip file, or git reference")

        clone_dir = temp_root / "repo"
        clone_dir.mkdir(parents=True, exist_ok=True)
        command = ["git", "clone", "--depth", "1", source_ref, str(clone_dir)]
        logger.info("Cloning repository: %s", source_ref)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip() or result.stdout.strip()}")

        return self._select_source_root(clone_dir), "git", cleanup, None

    @staticmethod
    def _select_source_root(extracted_dir: Path) -> Path:
        children = [path for path in extracted_dir.iterdir() if path.name not in {"__MACOSX"}]
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return extracted_dir

    @staticmethod
    def _load_config(source_dir: Path) -> Dict[str, Any]:
        config_path = source_dir / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"config.yaml not found in {source_dir}")

        with open(config_path, "r", encoding="utf-8") as file_handle:
            return yaml.safe_load(file_handle) or {}

    @staticmethod
    def _validate_structure(source_dir: Path) -> None:
        required_files = ["main.py", "config.yaml", "requirements.txt"]
        missing = [name for name in required_files if not (source_dir / name).exists()]
        if missing:
            raise RuntimeError(f"Missing required files: {', '.join(missing)}")

        required_dirs = ["models", "tools", "orchestrators", "agents"]
        missing_dirs = [name for name in required_dirs if not (source_dir / name).is_dir()]
        if missing_dirs:
            raise RuntimeError(f"Missing required directories: {', '.join(missing_dirs)}")

        for directory_name in required_dirs:
            py_files = list((source_dir / directory_name).rglob("*.py"))
            if not py_files:
                raise RuntimeError(f"No Python files found in {directory_name}/")

    @staticmethod
    def _validate_metadata(config: Dict[str, Any]) -> None:
        app = config.get("app", {})
        app_name = app.get("name", "")
        app_version = app.get("version", "")
        author = app.get("author", "")

        if not app_name or " " in app_name:
            raise RuntimeError("app.name must be present and slug-safe")
        if not app_version or len(app_version.split(".")) != 3:
            raise RuntimeError("app.version must be semantic version style X.Y.Z")
        if not author:
            raise RuntimeError("app.author must be present")

    @staticmethod
    def _validate_config(config: Dict[str, Any]) -> None:
        distribution = config.get("distribution", {})
        nodes = distribution.get("nodes", [])
        if distribution.get("mode") not in {"local", "distributed", "containerized"}:
            raise RuntimeError("distribution.mode must be local, distributed, or containerized")
        if not nodes:
            raise RuntimeError("distribution.nodes must contain at least one node")

        artifacts = config.get("artifacts", {})
        for artifact_group in ("models", "tools", "orchestrators", "agents"):
            if not artifacts.get(artifact_group):
                raise RuntimeError(f"artifacts.{artifact_group} must contain at least one entry")

    def _run_syntax_check(self, source_dir: Path) -> None:
        ok = compileall.compile_dir(str(source_dir), quiet=1, force=True)
        if not ok:
            raise RuntimeError("Python syntax check failed")

    def _run_dependency_dry_run(self, source_dir: Path) -> None:
        requirements_path = source_dir / "requirements.txt"
        command = [
            self.python_executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--disable-pip-version-check",
            "--no-input",
            "-r",
            str(requirements_path),
        ]
        result = subprocess.run(command, cwd=str(source_dir), capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "Dependency dry-run failed: " + (result.stderr.strip() or result.stdout.strip())
            )

    @staticmethod
    def _iter_package_files(source_dir: Path) -> List[Path]:
        files: List[Path] = []
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            files.append(path)
        return files

    def build(
        self,
        source: Union[str, Path],
        output_path: Optional[Path] = None,
        *,
        skip_dependency_check: bool = False,
        skip_syntax_check: bool = False,
    ) -> BuildResult:
        source_dir, source_type, cleanup, source_reference_path = self._resolve_source(source)
        build_messages: List[str] = []

        try:
            self._validate_structure(source_dir)
            config = self._load_config(source_dir)
            self._validate_metadata(config)
            self._validate_config(config)

            if not skip_dependency_check:
                self._run_dependency_dry_run(source_dir)
                build_messages.append("Dependency dry-run passed")

            if not skip_syntax_check:
                self._run_syntax_check(source_dir)
                build_messages.append("Python syntax check passed")

            app = config.get("app", {})
            build_id = uuid.uuid4().hex
            files = self._iter_package_files(source_dir)
            py_files = [path for path in files if path.suffix == ".py"]

            manifest = BuildManifest(
                build_id=build_id,
                app_name=app.get("name", "unknown-app"),
                app_version=app.get("version", "0.0.0"),
                source_type=source_type,
                source_reference=str(source_reference_path or source),
                created_at=time.time(),
                python_version=sys.version.split()[0],
                files_count=len(files),
                py_files_count=len(py_files),
                validated=True,
                dependency_check_passed=not skip_dependency_check,
                syntax_check_passed=not skip_syntax_check,
                extra={
                    "distribution_mode": config.get("distribution", {}).get("mode", "local"),
                    "entry_point": config.get("entry_points", {}).get("cli", "main.py"),
                },
            )

            if output_path is None:
                if source_reference_path is not None:
                    output_root = source_reference_path.parent
                else:
                    output_root = Path.cwd()
                output_path = output_root / f"{manifest.app_name}-{manifest.app_version}.aether.zip"

            output_path = Path(output_path).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for file_path in files:
                    archive.write(file_path, file_path.relative_to(source_dir).as_posix())
                archive.writestr("manifest.json", json.dumps(manifest.to_dict(), indent=2))

            build_messages.append(f"Packaged {len(files)} files")
            logger.info("Built package: %s", output_path)
            return BuildResult(
                output_path=output_path,
                manifest=manifest,
                source_path=source_dir,
                build_messages=build_messages,
            )
        finally:
            cleanup.cleanup()
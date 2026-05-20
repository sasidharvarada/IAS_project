"""
generator.py

Read an app config and render CLI usage documentation.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger("aether.subsystems.cli_generator")


@dataclass
class CLIArtifactSummary:
    artifact_type: str
    artifact_id: str
    class_path: str
    entry_point: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CLIUsageDocument:
    app_name: str
    app_version: str
    app_description: str
    app_author: str
    runtime: str
    cli_entry_point: str
    distribution_mode: str
    topology: str
    transport: str
    artifacts: List[CLIArtifactSummary]
    examples: List[str]
    generated_from: str


class CLIUsageGenerator:
    """Generate markdown CLI usage docs from config.yaml."""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"

        self.templates_dir = Path(templates_dir)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def load_config(self, config_path: Path) -> Dict[str, Any]:
        with open(config_path, "r", encoding="utf-8") as file_handle:
            return yaml.safe_load(file_handle) or {}

    def _artifact_summaries(self, config: Dict[str, Any]) -> List[CLIArtifactSummary]:
        artifacts: List[CLIArtifactSummary] = []
        artifact_groups = config.get("artifacts", {})

        for artifact_type in ("models", "tools", "orchestrators", "agents"):
            for artifact in artifact_groups.get(artifact_type, []):
                artifacts.append(
                    CLIArtifactSummary(
                        artifact_type=artifact_type[:-1],
                        artifact_id=artifact.get("id", ""),
                        class_path=artifact.get("class", ""),
                        entry_point=artifact.get("entry_point", ""),
                        extra={k: v for k, v in artifact.items() if k not in {"id", "class", "entry_point"}},
                    )
                )

        return artifacts

    @staticmethod
    def _examples(config: Dict[str, Any]) -> List[str]:
        entry_points = config.get("entry_points", {})
        cli_entry = entry_points.get("cli", "main.py")
        app_name = config.get("app", {}).get("name", "app")
        return [
            f"python {cli_entry} --health",
            f"python {cli_entry} --email sample_email.txt",
            f"python {cli_entry} --email sample_email.txt --json",
            f"echo \"Call me ASAP about the contract\" | python {cli_entry} --stdin",
            f"python {cli_entry} --email sample_email.txt --api-key <API_KEY>",
            f"python {cli_entry}  # interactive fallback for {app_name}",
        ]

    def build_document(self, config_path: Path) -> CLIUsageDocument:
        config_path = Path(config_path).resolve()
        config = self.load_config(config_path)

        app = config.get("app", {})
        distribution = config.get("distribution", {})
        entry_points = config.get("entry_points", {})

        return CLIUsageDocument(
            app_name=app.get("name", "unknown-app"),
            app_version=app.get("version", "0.0.0"),
            app_description=app.get("description", ""),
            app_author=app.get("author", ""),
            runtime=app.get("runtime", "python3"),
            cli_entry_point=entry_points.get("cli", "main.py"),
            distribution_mode=distribution.get("mode", "local"),
            topology=distribution.get("topology", "monolithic"),
            transport=distribution.get("transport", "http"),
            artifacts=self._artifact_summaries(config),
            examples=self._examples(config),
            generated_from=str(config_path),
        )

    def render(self, config_path: Path) -> str:
        document = self.build_document(config_path)

        try:
            template = self.jinja_env.get_template("cli_usage.md.j2")
        except TemplateNotFound:
            logger.error("Template not found: cli_usage.md.j2")
            raise

        return template.render(document=document)

    def generate(self, config_path: Path, output_path: Optional[Path] = None) -> Path:
        rendered = self.render(config_path)
        config_path = Path(config_path).resolve()

        if output_path is None:
            output_path = config_path.parent / "CLI_USAGE.md"

        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(rendered)

        logger.info("Generated CLI usage doc at %s", output_path)
        return output_path
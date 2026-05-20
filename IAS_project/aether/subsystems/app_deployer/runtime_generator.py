"""
runtime_generator.py

Generates _aether_main.py from config.yaml.

Reads:
  - artifacts.agents[], .tools[], .orchestrators[], .models[] from config.yaml
  - Extracts class paths and import statements
  - Renders Jinja2 template to create the FastAPI wrapper

The generated main.py is deployed alongside the app source on VMs
and acts as the entry point for all artifact roles.
"""

import os
import sys
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger("aether.deployer.runtime_generator")


class RuntimeGenerator:
    """
    Generates platform runtime (_aether_main.py) from an app's config.yaml.
    """
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the Jinja2 environment.
        
        Args:
            templates_dir: Path to templates/ directory (default: ./templates)
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        
        self.templates_dir = Path(templates_dir)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load config.yaml and return as dict."""
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config
    
    @staticmethod
    def parse_class_path(class_str: str) -> Tuple[str, str]:
        """
        Parse 'module.path.ClassName' into ('module.path', 'ClassName').
        
        Examples:
            'agents.email_classifier_agent.EmailClassifierAgent' 
            -> ('agents.email_classifier_agent', 'EmailClassifierAgent')
        """
        parts = class_str.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid class path: {class_str}")
        return parts[0], parts[1]
    
    def extract_artifacts(self, config: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract all artifact definitions from config.
        
        Returns:
            {
                "agents": [{"id": "...", "class": "...", "module": "...", "classname": "..."}, ...],
                "tools": [...],
                "orchestrators": [...],
                "models": [...]
            }
        """
        artifacts = {"agents": [], "tools": [], "orchestrators": [], "models": []}
        
        # Extract agents
        for artifact in config.get("artifacts", {}).get("agents", []):
            artifact_id = artifact.get("id", "").lower().replace("_", "-")
            class_path = artifact.get("class", "")
            module, classname = self.parse_class_path(class_path)
            artifacts["agents"].append({
                "id": artifact_id,
                "class": class_path,
                "module": module,
                "classname": classname,
            })
        
        # Extract tools
        for artifact in config.get("artifacts", {}).get("tools", []):
            artifact_id = artifact.get("id", "").lower().replace("_", "-")
            class_path = artifact.get("class", "")
            module, classname = self.parse_class_path(class_path)
            artifacts["tools"].append({
                "id": artifact_id,
                "class": class_path,
                "module": module,
                "classname": classname,
            })
        
        # Extract orchestrators
        for artifact in config.get("artifacts", {}).get("orchestrators", []):
            artifact_id = artifact.get("id", "").lower().replace("_", "-")
            class_path = artifact.get("class", "")
            module, classname = self.parse_class_path(class_path)
            artifacts["orchestrators"].append({
                "id": artifact_id,
                "class": class_path,
                "module": module,
                "classname": classname,
            })
        
        # Extract models
        for artifact in config.get("artifacts", {}).get("models", []):
            artifact_id = artifact.get("id", "").lower().replace("_", "-")
            class_path = artifact.get("class", "")
            module, classname = self.parse_class_path(class_path)
            artifacts["models"].append({
                "id": artifact_id,
                "class": class_path,
                "module": module,
                "classname": classname,
            })
        
        return artifacts
    
    def generate_runtime(self, config_path: Path, output_path: Path) -> None:
        """
        Generate _aether_main.py from config.yaml.
        
        Args:
            config_path: Path to config.yaml
            output_path: Path to write _aether_main.py
        """
        config_path = Path(config_path).resolve()
        output_path = Path(output_path).resolve()
        
        logger.info(f"Generating runtime from {config_path}")
        
        # Load config
        config = self.load_config(config_path)
        
        # Extract metadata
        app_id = config.get("app", {}).get("id", "unknown")
        app_version = config.get("app", {}).get("version", "1.0.0")
        
        # Extract artifacts
        artifacts_dict = self.extract_artifacts(config)
        
        # Build combined list of all artifacts with import statements
        all_artifacts = []
        for artifact in artifacts_dict["agents"]:
            all_artifacts.append({
                **artifact,
                "type": "agent",
                "import": f"from {artifact['module']} import {artifact['classname']}",
            })
        for artifact in artifacts_dict["tools"]:
            all_artifacts.append({
                **artifact,
                "type": "tool",
                "import": f"from {artifact['module']} import {artifact['classname']}",
            })
        for artifact in artifacts_dict["orchestrators"]:
            all_artifacts.append({
                **artifact,
                "type": "orchestrator",
                "import": f"from {artifact['module']} import {artifact['classname']}",
            })
        for artifact in artifacts_dict["models"]:
            all_artifacts.append({
                **artifact,
                "type": "model",
                "import": f"from {artifact['module']} import {artifact['classname']}",
            })
        
        # Determine defaults (first of each type)
        default_agent_id = artifacts_dict["agents"][0]["id"] if artifacts_dict["agents"] else ""
        default_orchestrator_id = artifacts_dict["orchestrators"][0]["id"] if artifacts_dict["orchestrators"] else ""
        default_model_id = artifacts_dict["models"][0]["id"] if artifacts_dict["models"] else ""
        
        logger.info(f"  App: {app_id} v{app_version}")
        logger.info(f"  Agents: {len(artifacts_dict['agents'])}")
        logger.info(f"  Tools: {len(artifacts_dict['tools'])}")
        logger.info(f"  Orchestrators: {len(artifacts_dict['orchestrators'])}")
        logger.info(f"  Models: {len(artifacts_dict['models'])}")
        
        # Render template
        try:
            template = self.jinja_env.get_template("_aether_main.py.j2")
        except TemplateNotFound:
            logger.error(f"Template not found: _aether_main.py.j2")
            raise
        
        rendered = template.render(
            app_id=app_id,
            app_version=app_version,
            all_artifacts=all_artifacts,
            agents_artifacts=artifacts_dict["agents"],
            tools_artifacts=artifacts_dict["tools"],
            orchestrators_artifacts=artifacts_dict["orchestrators"],
            models_artifacts=artifacts_dict["models"],
            default_agent_id=default_agent_id,
            default_orchestrator_id=default_orchestrator_id,
            default_model_id=default_model_id,
        )
        
        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        
        # Make executable (skip on Windows)
        if os.name != "nt":
            os.chmod(output_path, 0o755)
        
        logger.info(f"✓ Generated runtime at {output_path}")


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate _aether_main.py from config.yaml"
    )
    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for _aether_main.py (default: same dir as config, named _aether_main.py)",
    )
    
    args = parser.parse_args()
    
    config_path = args.config_path.resolve()
    if not config_path.exists():
        print(f"ERROR: {config_path} not found", file=sys.stderr)
        return 1
    
    output_path = args.output or config_path.parent / "_aether_main.py"
    
    logging.basicConfig(level=logging.INFO)
    
    generator = RuntimeGenerator()
    generator.generate_runtime(config_path, output_path)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

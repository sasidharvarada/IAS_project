import os
import yaml

def validate_config(extract_dir: str):
    """
    Parses config.yaml to verify required keys: app block, artifacts block, etc.
    """
    errors = []
    app_name = None
    app_version = None

    config_path = os.path.join(extract_dir, "config.yaml")
    if not os.path.exists(config_path):
        # Structure validator catches missing file, just skip parsing
        return errors, app_name, app_version

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        if not config:
            errors.append("config.yaml is empty.")
            return errors, None, None

        # Check 'app' block
        app_block = config.get("app", {})
        if not app_block.get("name"): errors.append("config.yaml is missing 'app.name'")
        if not app_block.get("version"): errors.append("config.yaml is missing 'app.version'")
        
        app_name = app_block.get("name")
        app_version = str(app_block.get("version")) if app_block.get("version") else None

        # Check 'artifacts' block
        artifacts = config.get("artifacts", {})
        if not artifacts:
            errors.append("config.yaml is missing the 'artifacts' block.")

    except Exception as e:
        errors.append(f"Failed to parse config.yaml: {str(e)}")

    return errors, app_name, app_version

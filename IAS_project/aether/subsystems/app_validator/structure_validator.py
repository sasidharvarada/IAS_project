import os

def validate_structure(extract_dir: str):
    """
    Checks if the mandatory files and folders exist in the unzipped app.
    """
    errors = []
    warnings = []
    
    # Mandatory files
    required_files = ["main.py", "config.yaml", "requirements.txt"]
    for f in required_files:
        if not os.path.exists(os.path.join(extract_dir, f)):
            errors.append(f"Missing required file: {f}")

    # Mandatory directories
    required_dirs = ["models", "tools", "orchestrators", "agents"]
    for d in required_dirs:
        dir_path = os.path.join(extract_dir, d)
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            errors.append(f"Missing required directory: {d}/")
            continue
        
        # Check if dir has at least one python file (optional validation step)
        has_py_files = any(f.endswith('.py') for f in os.listdir(dir_path))
        if not has_py_files:
            warnings.append(f"Directory {d}/ is empty or has no .py files.")

    return errors, warnings

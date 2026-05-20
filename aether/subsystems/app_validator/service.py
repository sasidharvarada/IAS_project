import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .report import ValidationReport
from .structure_validator import validate_structure
from .config_validator import validate_config

app = FastAPI(
    title="AetherAgents App Validator",
    description="Validates uploaded AI apps (ZIP) before they go to the registry.",
    version="1.0.0"
)

allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mocked: You can expand these imports over time
def _select_source_root(extract_dir: Path) -> Path:
    children = [path for path in extract_dir.iterdir() if path.name not in {"__MACOSX"}]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extract_dir


def validate_metadata(app_name, app_version):
    """Mocks metadata validation (semver, slug checks)"""
    errors = []
    if app_name and " " in app_name:
        errors.append("'app.name' cannot contain spaces. Use a slug like 'my-app'.")
    if app_version and len(app_version.split(".")) < 2:
        errors.append("'app.version' should ideally be semver formatting (e.g. 1.0.0).")
    return errors

@app.post("/validate", response_model=ValidationReport)
async def validate_app_zip(file: UploadFile = File(...)):
    """
    Receives a .zip file, unzips it temporarily, runs all structure, config, 
    and metadata checks, then returns the Validation Report.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a .zip archive.")

    # 1. Setup a temporary directory for unzipping
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)
    extract_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        # Save the uploaded uploaded zip
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Unzip it
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except zipfile.BadZipFile:
            shutil.rmtree(temp_dir)
            return ValidationReport(passed=False, errors=["Uploaded file is not a valid zip archive."])

        source_root = _select_source_root(Path(extract_dir))

        # 2. Run validations
        all_errors = []
        all_warnings = []

        # A: Structure check
        struct_errs, struct_warns = validate_structure(str(source_root))
        all_errors.extend(struct_errs)
        all_warnings.extend(struct_warns)

        # B: Config check
        config_errs, app_name, app_version = validate_config(str(source_root))
        all_errors.extend(config_errs)

        # C: Metadata check
        all_errors.extend(validate_metadata(app_name, app_version))

        # D: In a complete pipeline we would push "app.validated" event to Kafka here
        #   producer.send("app.validated", {"app_id": app_name, "passed": passed, "temp_dir": temp_dir})
        
        # 3. Return the report
        passed = len(all_errors) == 0

        # Conditional clean-up: Keep the file if passing, delete if failing
        if not passed:
            shutil.rmtree(temp_dir)

        return ValidationReport(
            passed=passed,
            errors=all_errors,
            warnings=all_warnings,
            app_name=app_name,
            app_version=app_version
        )

    except Exception as e:
        # Always clean up on unexpected server error to prevent memory leaks
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise e

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "app_validator"}

import os
import shutil
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import zipfile
from pathlib import Path

app = FastAPI()

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = os.path.abspath(os.getenv("AETHER_APP_REGISTRY_STORAGE_DIR", str(REPO_ROOT / ".run" / "storage")))
APPS_DIR = os.path.join(BASE_DIR, "apps")
PLATFORM_DIR = os.path.join(BASE_DIR, "platform")

os.makedirs(APPS_DIR, exist_ok=True)
os.makedirs(PLATFORM_DIR, exist_ok=True)


def register_package(app_id: str, app_version: str, zip_path: Path) -> dict:
    """
    Register a built app package in registry storage.
    Stores ZIP under storage/apps/<app_id>/<app_version>/package.zip and extracts source/.
    """
    target_dir = safe_join(APPS_DIR, app_id, app_version)
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    package_path = safe_join(target_dir, "package.zip")
    shutil.copy2(zip_path, package_path)

    source_dir = safe_join(target_dir, "source")
    os.makedirs(source_dir, exist_ok=True)
    with zipfile.ZipFile(package_path, "r") as archive:
        archive.extractall(source_dir)

    return {
        "status": "registered",
        "app_id": app_id,
        "app_version": app_version,
        "package_path": package_path,
        "source_dir": source_dir,
    }


# ----------------------------
# Helper: safe path join
# ----------------------------
def safe_join(base, *paths):
    final_path = os.path.abspath(os.path.join(base, *paths))
    if not final_path.startswith(base):
        raise HTTPException(400, "Invalid path")
    return final_path


# ----------------------------
# Helper: read file
# ----------------------------
def read_file_content(path):
    with open(path, "rb") as f:
        return f.read().decode("latin1")


# ----------------------------
# Helper: recursive directory read
# ----------------------------
def read_directory(base_root, target_path):
    result = []

    for root, _, files in os.walk(target_path):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, base_root)

            result.append({
                "path": rel_path,
                "content": read_file_content(full_path)
            })

    return result


# ----------------------------
# 1. PUSH FULL APP
# ----------------------------
@app.post("/push/app")
async def push_app(
    app_name: str = Form(...),
    paths: List[str] = Form(...),
    files: List[UploadFile] = File(...)
):
    if len(paths) != len(files):
        raise HTTPException(400, "paths and files mismatch")

    app_path = safe_join(APPS_DIR, app_name)

    # overwrite existing app
    if os.path.exists(app_path):
        shutil.rmtree(app_path)

    for rel_path, file in zip(paths, files):
        target_path = safe_join(app_path, rel_path)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        content = await file.read()

        with open(target_path, "wb") as f:
            f.write(content)

    return {
        "status": "success",
        "app": app_name,
        "files_uploaded": len(files)
    }


# ----------------------------
# 2. CHECK APP EXISTS
# ----------------------------
@app.get("/app/{app_name}/exists")
def app_exists(app_name: str):
    app_path = safe_join(APPS_DIR, app_name)
    return {"exists": os.path.exists(app_path)}


# ----------------------------
# 3. PULL APP (FILE OR DIR)
# ----------------------------
@app.get("/pull/app")
def pull_app(app_name: str, path: str = ""):
    app_path = safe_join(APPS_DIR, app_name)

    if not os.path.exists(app_path):
        raise HTTPException(404, "App not found")

    target_path = safe_join(app_path, path)

    if not os.path.exists(target_path):
        raise HTTPException(404, "Path not found")

    # FILE
    if os.path.isfile(target_path):
        return JSONResponse({
            "type": "file",
            "path": path,
            "content": read_file_content(target_path)
        })

    # DIRECTORY
    return {
        "type": "directory",
        "base_path": path,
        "files": read_directory(app_path, target_path)
    }


# ----------------------------
# 4. PULL PLATFORM (FILE OR DIR)
# ----------------------------
@app.get("/pull/platform")
def pull_platform(path: str = ""):
    if not os.path.exists(PLATFORM_DIR):
        raise HTTPException(404, "Platform not found")

    target_path = safe_join(PLATFORM_DIR, path)

    if not os.path.exists(target_path):
        raise HTTPException(404, "Path not found")

    # FILE
    if os.path.isfile(target_path):
        return JSONResponse({
            "type": "file",
            "path": path,
            "content": read_file_content(target_path)
        })

    # DIRECTORY
    return {
        "type": "directory",
        "base_path": path,
        "files": read_directory(PLATFORM_DIR, target_path)
    }


@app.post("/register/package")
def register_package_endpoint(app_id: str = Form(...), app_version: str = Form(...), file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "File must be a .zip archive")

    temp_path = safe_join(BASE_DIR, f"tmp_{app_id}_{app_version}.zip")
    with open(temp_path, "wb") as handle:
        handle.write(file.file.read())

    try:
        result = register_package(app_id, app_version, Path(temp_path))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    return result

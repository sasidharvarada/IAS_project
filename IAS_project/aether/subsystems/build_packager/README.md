# Build Packager Subsystem

`build_packager` validates application source trees and packages them into `.aether.zip` archives with an injected `manifest.json`.

## What it does

- Validates app structure and metadata
- Runs a Python syntax check across all `.py` files
- Runs a pip dependency dry-run against `requirements.txt`
- Packages the app into a distributable `.aether.zip`
- Exposes an HTTP build endpoint at `POST /apps/build`

## Quick start

```bash
python -m aether.subsystems.build_packager.service apps/email_classifier --output dist/email_classifier.aether.zip
```

## HTTP API

```bash
POST /apps/build
{
	"source": "apps/email_classifier",
	"output": "dist/email_classifier.aether.zip"
}
```

## Input support

- Local app directory
- Local `.zip` archive
- Git repository URL

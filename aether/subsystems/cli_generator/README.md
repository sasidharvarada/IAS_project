# CLI Generator Subsystem

`cli_generator` reads an app's `config.yaml` and renders a markdown usage guide for the app's CLI entry point.

## What it generates

- App summary and metadata
- CLI entry-point name
- Common run examples
- Artifact inventory with class paths and entry points

## Quick start

```bash
python -m aether.subsystems.cli_generator.service apps/email_classifier/config.yaml --output apps/email_classifier/CLI_USAGE.md
```

## Output

By default, the generator writes `CLI_USAGE.md` next to the input `config.yaml`.

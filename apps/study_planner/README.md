# Study Planner Agent

`study_planner` is a simple agentic Aether app that turns a goal into a short study plan.

## What it does

- Accepts a topic or goal from the CLI
- Extracts key study themes
- Ranks them into a sequence of sessions
- Produces a concise plan with next actions

## Run locally

```bash
cd apps/study_planner
python main.py --goal "Learn Python data structures"
```

## CLI flags

- `--goal` or `--stdin` to provide input
- `--json` for machine-readable output
- `--health` to check the agent

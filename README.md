# Launchroom

Launchroom is a Devpost build for the Google Cloud Rapid Agent Hackathon.

It turns a messy product release into a launch-readiness room: repo facts, risk signals, blocker ranking, owner-safe next actions, evaluator checks, and an evidence-backed report.

Public support demo: https://voiddo.com/devpost/rapid-agent/
Public repository: https://github.com/voidd0/launchroom-rapid-agent

## Current Status

This repository contains a working browser demo and a local agent harness.

The partner path uses Fivetran. The local harness verifies the same account API path used by the official Fivetran MCP server and keeps writes disabled. If Fivetran credentials are missing or invalid, the run records the MCP probe as blocked instead of pretending it succeeded. Final Devpost submission still needs Google Cloud Agent Builder evidence and a clean demo video.

## Run Locally

```bash
cd /root/devpost-lab/rapid-agent/launchroom
python3 agent/launchroom_agent.py --input agent/sample_release.json
python3 -m http.server 8097
```

Open `http://localhost:8097`.

## Environment

Optional:

```bash
export GEMINI_API_KEY=...
export FIVETRAN_API_KEY=...
export FIVETRAN_API_SECRET=...
export FIVETRAN_ALLOW_WRITES=false
```

Without `GEMINI_API_KEY`, the harness uses deterministic local reasoning so QA remains free and repeatable.

Built by vøiddo — a small studio shipping AI-flavoured products, free dev tools, Chrome extensions and weird browser games.

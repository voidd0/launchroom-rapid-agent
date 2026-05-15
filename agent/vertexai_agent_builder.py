"""
Launchroom — Vertex AI Agent Builder deployment configuration.

This file shows how to deploy the Launchroom release-readiness agent
on Google Cloud Vertex AI Agent Builder (Vertex AI SDK / ADK pattern).

To deploy:
  1. Set GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION env vars
  2. Enable Vertex AI API: gcloud services enable aiplatform.googleapis.com
  3. Authenticate: gcloud auth application-default login
  4. Run: python3 vertexai_agent_builder.py

Without GCP credentials, the agent falls back to the Google AI Studio path
(GEMINI_API_KEY) which uses the same gemini-2.5-flash model through the
generativelanguage.googleapis.com endpoint.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Vertex AI SDK (install: pip install google-cloud-aiplatform)
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration, Part
    HAS_VERTEXAI = True
except ImportError:
    HAS_VERTEXAI = False

TOOLS = [
    {
        "function_declarations": [
            {
                "name": "check_preflight",
                "description": "Validate the release payload structure before full agent loop.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "payload": {"type": "OBJECT", "description": "Release JSON payload"}
                    },
                    "required": ["payload"]
                }
            },
            {
                "name": "scan_github_repo",
                "description": "Scan a GitHub repo for open issues, license, branch, and readme quality.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "repo_url": {"type": "STRING", "description": "Full GitHub repo URL"}
                    },
                    "required": ["repo_url"]
                }
            },
            {
                "name": "probe_partner_mcp",
                "description": "Probe a partner MCP integration (Fivetran, MongoDB, etc.) for authentication and health.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "partner": {"type": "STRING", "description": "Partner name (e.g. Fivetran)"},
                        "allow_writes": {"type": "BOOLEAN", "description": "Whether writes are allowed (false = safe probe only)"}
                    },
                    "required": ["partner"]
                }
            },
            {
                "name": "score_readiness",
                "description": "Compute a launch-readiness score 0-100 from blockers and strengths.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "blockers": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Remaining launch blockers"
                        },
                        "strengths": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Evidence of launch readiness"
                        }
                    },
                    "required": ["blockers", "strengths"]
                }
            }
        ]
    }
]

SYSTEM_INSTRUCTION = (
    "You are the Launchroom release-readiness agent. "
    "Your job is to check a software project for launch readiness by running "
    "preflight checks, scanning the repository, probing partner MCP integrations, "
    "and scoring the overall readiness. "
    "Use all available tools before returning a final evaluation. "
    "Never hallucinate evidence — only report what tool calls confirm."
)


def run_on_vertexai(release_json_path: str) -> dict:
    """Run Launchroom agent on Vertex AI Agent Builder."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if not project:
        return {
            "status": "blocked",
            "reason": "GOOGLE_CLOUD_PROJECT env var not set — falling back to Google AI Studio path",
            "fallback": "launchroom_agent.py uses GEMINI_API_KEY via generativelanguage.googleapis.com"
        }

    if not HAS_VERTEXAI:
        return {
            "status": "blocked",
            "reason": "google-cloud-aiplatform not installed — run: pip install google-cloud-aiplatform",
            "fallback": "launchroom_agent.py uses GEMINI_API_KEY via generativelanguage.googleapis.com"
        }

    vertexai.init(project=project, location=location)
    model = GenerativeModel(
        model_name="gemini-2.5-flash-001",
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
    )

    with open(release_json_path) as f:
        payload = json.load(f)

    chat = model.start_chat()
    prompt = (
        f"Evaluate this release for launch readiness. "
        f"Use check_preflight, scan_github_repo, probe_partner_mcp, and score_readiness in order. "
        f"Release payload: {json.dumps(payload)}"
    )
    response = chat.send_message(prompt)
    return {
        "status": "ok",
        "project": project,
        "location": location,
        "model": "gemini-2.5-flash-001",
        "path": "vertex_ai_agent_builder",
        "response_text": response.text[:500] if hasattr(response, "text") else str(response)[:500]
    }


if __name__ == "__main__":
    release_path = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent / "sample_release.json")
    result = run_on_vertexai(release_path)
    print(json.dumps(result, indent=2))
    if result["status"] != "ok":
        print(f"\nFallback: run launchroom_agent.py with GEMINI_API_KEY instead.", file=sys.stderr)

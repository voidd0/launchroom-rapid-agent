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
                "name": "check_gitlab_issues",
                "description": "Query GitLab REST API v4 for open issues, merge requests, and latest pipeline status. Demonstrates GitLab partner integration — no token required for public projects.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "project_path": {
                            "type": "STRING",
                            "description": "GitLab project path in namespace/project format, e.g. 'gitlab-org/gitlab'"
                        }
                    },
                    "required": ["project_path"]
                }
            },
            {
                "name": "check_fivetran_connectors",
                "description": "List all Fivetran connectors for the account and return count and sync state. Demonstrates connector-management scope beyond account-info.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "verify_live_surfaces",
                "description": "HEAD-check a list of public URLs and confirm HTTP 200 responses. Validates submission surfaces are publicly reachable.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "urls": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Public URLs to HEAD-check"
                        }
                    },
                    "required": ["urls"]
                }
            },
            {
                "name": "check_vertex_config",
                "description": "Read and validate the Vertex AI Agent Builder deployment configuration. Confirms cloud deployment artifacts are present.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "check_npm_package",
                "description": "Verify a package exists on the npm public registry and fetch its latest version, release count, and license. Confirms the release is actually published for users.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "package_name": {
                            "type": "STRING",
                            "description": "npm package name (scoped or unscoped), e.g. '@v0idd0/launchroom' or 'express'"
                        }
                    },
                    "required": ["package_name"]
                }
            },
            {
                "name": "check_pypi_package",
                "description": "Verify a Python package exists on PyPI and fetch its latest version and release count. Use this to confirm Python packages in the release are published.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "package_name": {
                            "type": "STRING",
                            "description": "PyPI package name, e.g. 'requests' or 'launchroom-agent'"
                        }
                    },
                    "required": ["package_name"]
                }
            },
            {
                "name": "check_osv_vulnerabilities",
                "description": "Query the Google OSV (Open Source Vulnerability) public API for known CVEs affecting a package. Use as a security gate before launch.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "ecosystem": {
                            "type": "STRING",
                            "description": "Package ecosystem: npm, PyPI, Go, Maven, NuGet, RubyGems, crates.io"
                        },
                        "package_name": {
                            "type": "STRING",
                            "description": "The package name within the ecosystem"
                        },
                        "version": {
                            "type": "STRING",
                            "description": "Optional specific version to check. If empty, checks for any known vulnerabilities."
                        }
                    },
                    "required": ["ecosystem", "package_name"]
                }
            },
            {
                "name": "suggest_cve_remediation",
                "description": "Given a list of CVE/GHSA IDs from check_osv_vulnerabilities, fetch each advisory from OSV and return a concrete fix plan with severity, fix version, and upgrade command. Call this after any OSV vulnerability finding to convert blockers into a managed risk.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "ecosystem": {
                            "type": "STRING",
                            "description": "Package ecosystem, e.g. npm or PyPI"
                        },
                        "vuln_ids": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "List of GHSA or CVE IDs to look up"
                        }
                    },
                    "required": ["ecosystem", "vuln_ids"]
                }
            },
            {
                "name": "check_github_actions",
                "description": "Fetch the latest GitHub Actions workflow run for the project repo and report its status, conclusion, and branch. A passing CI run confirms submission codebase integrity.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "repo": {
                            "type": "STRING",
                            "description": "GitHub repo in owner/repo or full URL format"
                        }
                    },
                    "required": ["repo"]
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

# Total tools declared in this deployment config — must match launchroom_agent.py TOOLS dict
LAUNCHROOM_TOOLS_DECLARED = 13

SYSTEM_INSTRUCTION = (
    "You are the Launchroom release-readiness agent. "
    "Your job is to check a software project for launch readiness by running "
    "13 tool calls in sequence: check_preflight → scan_github_repo → probe_partner_mcp "
    "→ check_gitlab_issues → check_fivetran_connectors → verify_live_surfaces → check_vertex_config "
    "→ check_npm_package → check_pypi_package → check_osv_vulnerabilities "
    "→ suggest_cve_remediation → check_github_actions → score_readiness. "
    "Use ALL available tools before returning a final evaluation. "
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

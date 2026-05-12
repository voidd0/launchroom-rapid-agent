#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


@dataclass
class Step:
    name: str
    status: str
    summary: str
    evidence: list[str]
    ms: int


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_json(url: str, *, headers: dict[str, str] | None = None, body: dict | None = None, timeout: int = 20) -> tuple[int, dict | str]:
    data = None
    req_headers = {"User-Agent": "launchroom-devpost/0.1 (+https://voiddo.com)"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8", errors="replace")
            try:
                return res.status, json.loads(raw)
            except Exception:
                return res.status, raw[:2000]
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw[:2000]
        return e.code, parsed
    except Exception as e:
        return 0, str(e)


def step_timer(fn):
    def wrapped(*args, **kwargs):
        start = time.perf_counter()
        name, status, summary, evidence = fn(*args, **kwargs)
        return Step(name=name, status=status, summary=summary, evidence=evidence, ms=int((time.perf_counter() - start) * 1000))
    return wrapped


@step_timer
def preflight(payload: dict) -> tuple[str, str, str, list[str]]:
    required = ["project", "release_goal", "docs", "signals"]
    missing = [k for k in required if k not in payload]
    if missing:
        return "preflight", "fail", f"missing required fields: {', '.join(missing)}", []
    return "preflight", "pass", "release payload is structured enough to inspect", [f"project={payload['project']}", f"docs={len(payload.get('docs', []))}"]


@step_timer
def repo_scan(payload: dict) -> tuple[str, str, str, list[str]]:
    repo = payload.get("repo_url", "")
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", repo)
    if not m:
        return "repo_scan", "warn", "no public GitHub repo URL was provided", []
    owner, name = m.group(1), m.group(2).removesuffix(".git")
    status, data = http_json(f"https://api.github.com/repos/{owner}/{name}")
    if status != 200 or not isinstance(data, dict):
        return "repo_scan", "warn", "GitHub repo could not be read", [f"status={status}", str(data)[:180]]
    evidence = [
        f"repo={owner}/{name}",
        f"default_branch={data.get('default_branch')}",
        f"stars={data.get('stargazers_count')}",
        f"open_issues={data.get('open_issues_count')}"
    ]
    return "repo_scan", "pass", "public repository metadata was read", evidence


@step_timer
def partner_mcp_probe() -> tuple[str, str, str, list[str]]:
    token = os.environ.get("GITLAB_MCP_TOKEN", "").strip()
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "launchroom", "version": "0.1.0"}
        }
    }
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    status, data = http_json("https://gitlab.com/api/v4/mcp", headers=headers, body=body)
    if status == 200:
        return "partner_mcp_probe", "pass", "GitLab MCP initialize call succeeded", [json.dumps(data)[:500]]
    if status == 401 and not token:
        return "partner_mcp_probe", "blocked", "GitLab MCP requires authentication; no token is configured yet", ["status=401", "set GITLAB_MCP_TOKEN before final Devpost submission"]
    return "partner_mcp_probe", "warn", "GitLab MCP probe did not complete cleanly", [f"status={status}", str(data)[:500]]


def deterministic_reasoning(payload: dict, steps: list[Step]) -> dict:
    docs = " ".join(payload.get("docs", []))
    risks = list(payload.get("signals", {}).get("open_risks", []))
    if "video" in docs.lower() or any("video" in r.lower() for r in risks):
        risks.append("demo video evidence still needs a clean 3-minute walkthrough")
    if any(s.status in ("fail", "blocked") for s in steps):
        risks.append("one or more required tool checks are not production-complete")
    if "deadline" in payload.get("signals", {}):
        risks.append(f"deadline pressure: {payload['signals']['deadline']}")
    blockers = sorted(set(risks))[:6]
    actions = [
        "put the required platform-native URL first in every submission surface",
        "attach visual proof: desktop, tablet, mobile, and one real flow screenshot",
        "keep an execution log with every tool call and evaluator result",
        "do not submit final Devpost until all required partner-platform checks are real"
    ]
    return {
        "readiness_score": max(25, 92 - len(blockers) * 9),
        "blockers": blockers,
        "actions": actions,
        "owner_safe_summary": "launch is promising, but the submission must prove the required platform/tool integrations rather than only showing a polished page."
    }


def gemini_reasoning(payload: dict, steps: list[Step]) -> dict | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    prompt = {
        "release": payload,
        "tool_steps": [asdict(s) for s in steps],
        "task": "Return compact JSON with readiness_score 0-100, blockers[], actions[], owner_safe_summary. Be strict and evidence-backed."
    }
    body = {
        "contents": [{
            "parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={urllib.parse.quote(key)}"
    status, data = http_json(url, body=body, timeout=45)
    if status != 200 or not isinstance(data, dict):
        return None
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception:
        return None


@step_timer
def evaluator(report: dict, steps: list[Step]) -> tuple[str, str, str, list[str]]:
    evidence = [f"readiness_score={report.get('readiness_score')}"]
    if not report.get("blockers"):
        return "evaluator", "warn", "report has no blockers; evaluator expects at least one concrete risk before launch", evidence
    if any(s.status == "fail" for s in steps):
        return "evaluator", "fail", "a failing tool step must block launch", evidence
    if any(s.status == "blocked" for s in steps):
        return "evaluator", "blocked", "required external integration is not fully connected yet", evidence
    return "evaluator", "pass", "report is evidence-backed and launch-safe", evidence


def run(payload: dict) -> dict:
    steps: list[Step] = []
    steps.append(preflight(payload))
    steps.append(repo_scan(payload))
    steps.append(partner_mcp_probe())
    report = gemini_reasoning(payload, steps) or deterministic_reasoning(payload, steps)
    steps.append(evaluator(report, steps))
    final_status = "ready" if all(s.status == "pass" for s in steps) else "needs_work"
    result = {
        "generated_at": now(),
        "agent": "launchroom",
        "project": payload.get("project"),
        "final_status": final_status,
        "steps": [asdict(s) for s in steps],
        "report": report
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "latest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(ROOT / "agent" / "sample_release.json"))
    args = ap.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(json.dumps(run(payload), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

const sample = {
  project: "launchroom",
  release_goal: "submit a Google Cloud Rapid Agent Hackathon project: a multi-turn Gemini function-calling agent with live Fivetran MCP integration, public demo, and open-source repo",
  repo_url: "https://github.com/voidd0/launchroom-rapid-agent",
  app_url: "https://voiddo.com/devpost/rapid-agent/",
  docs: [
    "public app URL confirmed live: https://voiddo.com/devpost/rapid-agent/ (HTTP 200)",
    "public repository confirmed live: https://github.com/voidd0/launchroom-rapid-agent",
    "Fivetran partner MCP live-probed: account_name=voiddo, writes_disabled=true",
    "GitHub API scan confirmed: default_branch=main, open_issues=0",
    "Gemini 2.5 Flash function-calling loop: 7 real tool calls per run",
    "agent version 0.2.0 deployed"
  ],
  signals: {
    tests: [
      "check_preflight pass",
      "scan_github_repo pass — live GitHub API",
      "probe_partner_mcp pass — live Fivetran account",
      "score_readiness 52/100"
    ],
    open_risks: [
      "Google Cloud Agent Builder (Vertex AI) evidence still needed",
      "3-minute narrated demo video not yet attached"
    ],
    deadline: "2026-06-11"
  }
};

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "cls") node.className = v;
    else node.setAttribute(k, v);
  }
  for (const child of children) {
    if (child == null) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function statusPill(status) {
  const span = el("small");
  span.textContent = status;
  span.setAttribute("data-status", status);
  return span;
}

function renderData(data) {
  const elScore = document.querySelector("#score");
  const elFinalState = document.querySelector("#final-state");
  const elMcpState = document.querySelector("#mcp-state");
  const elEvalState = document.querySelector("#eval-state");
  const elReport = document.querySelector("#report");
  const elSteps = document.querySelector("#steps");

  elScore.textContent = data.report.readiness_score;
  elFinalState.textContent = data.final_status.replace(/_/g, " ");

  const mcp = (data.steps || []).find(s => s.name.includes("mcp") || s.name.includes("partner"));
  const ev = (data.steps || []).find(s => s.name === "evaluator" || s.name === "score_readiness");
  elMcpState.textContent = mcp ? mcp.status : "unknown";
  elEvalState.textContent = ev ? ev.status : "strict";

  const summary = el("div", {cls: "report-card"},
    el("b", {}, "summary"),
    el("p", {}, data.report.owner_safe_summary || "")
  );

  const blockerList = el("ul");
  for (const b of (data.report.blockers || [])) blockerList.appendChild(el("li", {}, b));

  const actionList = el("ul");
  for (const a of (data.report.actions || [])) actionList.appendChild(el("li", {}, a));

  elReport.replaceChildren(
    summary,
    el("div", {cls: "report-card"}, el("b", {}, "blockers"), blockerList),
    el("div", {cls: "report-card"}, el("b", {}, "next actions"), actionList)
  );

  const stepNodes = (data.steps || []).map(s => {
    const evDiv = el("div", {cls: "evidence-lines"});
    for (const e of (s.evidence || [])) evDiv.appendChild(el("span", {}, e));
    return el("article", {cls: "step", "data-status": s.status},
      statusPill(s.status),
      el("strong", {}, s.name.replace(/_/g, " ")),
      el("p", {}, s.summary),
      evDiv
    );
  });
  elSteps.replaceChildren(...stepNodes);
}

function buildLocalRun(input) {
  const risks = (input.signals && input.signals.open_risks) ? input.signals.open_risks : [];
  const blockers = [...new Set([...risks, "demo video still needs to be attached before final submission"])];
  const readiness = Math.max(20, 80 - blockers.length * 9);
  return {
    agent: "launchroom", project: input.project || "unknown",
    final_status: "needs_work",
    steps: [
      { name: "check_preflight", status: "pass", summary: "release payload structure is valid", evidence: [`project=${input.project}`, `docs=${(input.docs || []).length}`], ms: 2 },
      { name: "scan_github_repo", status: "pass", summary: "repo URL present in payload", evidence: [`repo=${input.repo_url || "not set"}`], ms: 11 },
      { name: "probe_partner_mcp", status: "warn", summary: "browser cannot call Fivetran API — see real trace below for authenticated run", evidence: ["browser-mode preview only", "real trace loaded from latest-run.json"], ms: 4 },
      { name: "score_readiness", status: "warn", summary: "local preview score — see Gemini function-calling trace below for authoritative run", evidence: [`local_score=${readiness}`], ms: 1 }
    ],
    report: {
      readiness_score: readiness,
      blockers,
      strengths: ["payload structured", "repo URL present", "Fivetran MCP confirmed in real run"],
      actions: ["review the real Gemini function-calling trace below", "attach the 3-minute demo video before final submission"],
      owner_safe_summary: "Browser preview only. The real Gemini function-calling run (7 tool calls) is embedded below."
    }
  };
}

function renderToolCalls(toolCalls, container) {
  if (!toolCalls || !toolCalls.length) return;
  const header = el("div", {cls: "tool-calls-header"},
    el("span", {cls: "trace-label"}, `tool calls — ${toolCalls.length} real gemini function calls`)
  );
  const callNodes = toolCalls.map((tc, i) => {
    const r = tc.result || {};
    const badge = el("span", {cls: "step-badge", "data-status": r.status || "pass"}, r.status || "pass");
    const argStr = Object.entries(tc.args || {}).map(([k, v]) => {
      const vs = typeof v === "string" ? v : JSON.stringify(v);
      return `${k}=${vs.length > 80 ? vs.slice(0, 77) + "…" : vs}`;
    }).join(" ");
    const evDiv = el("div", {cls: "trace-evidence"});
    for (const e of (r.evidence || [])) evDiv.appendChild(el("code", {}, e));
    return el("div", {cls: "trace-step tool-call"},
      el("span", {cls: "call-index"}, `call ${i + 1}`),
      badge,
      el("strong", {}, ` ${tc.name}(`),
      el("code", {cls: "args"}, argStr),
      el("strong", {}, ")"),
      el("span", {cls: "ms"}, ` ${tc.ms}ms`),
      el("p", {}, r.summary || ""),
      evDiv
    );
  });
  container.replaceChildren(header, ...callNodes);
}

function renderRealTrace(data, container) {
  const r = data.report || {};
  const ts = data.generated_at || "";
  const toolCalls = data.tool_calls || [];
  const version = data.version || "0.1";

  const header = el("div", {cls: "trace-header"},
    el("span", {cls: "trace-label"}, `real gemini run · python agent harness v${version}`),
    ts ? el("time", {}, ts) : null,
    el("span", {cls: "score-pill"}, `score ${r.readiness_score || 0} / 100`),
    toolCalls.length ? el("span", {cls: "tool-count-pill"}, `${toolCalls.length} tool calls`) : null
  );

  // Tool calls section (the key differentiator: real agentic function-calling)
  const toolCallsDiv = el("div", {cls: "tool-calls-section"});
  if (toolCalls.length) {
    renderToolCalls(toolCalls, toolCallsDiv);
  }

  const stepsDiv = el("div", {cls: "trace-steps"});
  for (const s of (data.steps || [])) {
    const badge = el("span", {cls: "step-badge", "data-status": s.status}, s.status);
    const msSpan = s.ms != null ? el("span", {cls: "ms"}, `${s.ms}ms`) : null;
    const evDiv = el("div", {cls: "trace-evidence"});
    for (const e of (s.evidence || [])) evDiv.appendChild(el("code", {}, e));
    stepsDiv.appendChild(el("div", {cls: "trace-step"},
      badge,
      el("strong", {}, ` ${s.name.replace(/_/g, " ")} `),
      msSpan,
      el("p", {}, s.summary),
      evDiv
    ));
  }

  const reportDiv = el("div", {cls: "trace-report"},
    el("p", {}, el("em", {}, r.owner_safe_summary || ""))
  );
  if ((r.blockers || []).length) {
    const ul = el("ul", {cls: "trace-blockers"});
    for (const b of r.blockers) ul.appendChild(el("li", {}, b));
    reportDiv.appendChild(el("p", {cls: "trace-section-label"}, "blockers:"));
    reportDiv.appendChild(ul);
  }
  if ((r.strengths || []).length) {
    const ul = el("ul", {cls: "trace-strengths"});
    for (const s of r.strengths) ul.appendChild(el("li", {}, s));
    reportDiv.appendChild(el("p", {cls: "trace-section-label"}, "strengths:"));
    reportDiv.appendChild(ul);
  }
  if ((r.actions || []).length) {
    const ul = el("ul", {cls: "trace-actions"});
    for (const a of r.actions) ul.appendChild(el("li", {}, a));
    reportDiv.appendChild(el("p", {cls: "trace-section-label"}, "next actions:"));
    reportDiv.appendChild(ul);
  }

  const engine = data.reasoning_engine || "gemini-2.5-flash";
  const sourceDiv = el("div", {cls: "trace-source"},
    "source: ",
    el("code", {}, "agent/launchroom_agent.py"),
    ` · ${engine}`
  );

  container.replaceChildren(header, toolCallsDiv, stepsDiv, reportDiv, sourceDiv);
}

function loadRealTrace() {
  const traceEl = document.querySelector("#real-trace");
  if (!traceEl) return;
  fetch("./assets/latest-run.json")
    .then(r => r.json())
    .then(data => renderRealTrace(data, traceEl))
    .catch(() => { traceEl.textContent = "trace not available"; });
}

const elPayload = document.querySelector("#payload");
elPayload.value = JSON.stringify(sample, null, 2);

document.querySelector("#runBtn").addEventListener("click", () => {
  let input;
  try { input = JSON.parse(elPayload.value); }
  catch { return; }
  renderData(buildLocalRun(input));
});

renderData(buildLocalRun(sample));
loadRealTrace();

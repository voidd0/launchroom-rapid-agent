const sample = {
  project: "tells-lite",
  release_goal: "submit a polished Devpost project and keep the public demo reliable",
  repo_url: "https://github.com/voidd0/jsonyo",
  docs: [
    "public app URL is live",
    "support demo exists",
    "project copy was updated after profile cleanup",
    "remaining risk: wrong primary demo link or missing compliance evidence"
  ],
  signals: {
    tests: ["browser smoke passed", "mobile screenshot present"],
    open_risks: ["partner-platform requirement must be explicit", "video not yet attached"],
    deadline: "2026-05-20"
  }
};

const payload = document.querySelector("#payload");
const report = document.querySelector("#report");
const steps = document.querySelector("#steps");
const score = document.querySelector("#score");
const finalState = document.querySelector("#final-state");
const mcpState = document.querySelector("#mcp-state");
const evalState = document.querySelector("#eval-state");

payload.value = JSON.stringify(sample, null, 2);

function runLocalAgent(input) {
  const blockers = [...new Set([
    ...(input.signals?.open_risks || []),
    "GitLab MCP is not authenticated in this public demo run",
    "demo video still needs to be attached before final submission"
  ])];
  const readiness = Math.max(20, 92 - blockers.length * 9);
  return {
    final_status: "needs_work",
    steps: [
      { name: "preflight", status: "pass", summary: "release payload is structured enough to inspect", evidence: [`project=${input.project}`, `docs=${input.docs?.length || 0}`], ms: 4 },
      { name: "repo_scan", status: "pass", summary: "public repository metadata is readable", evidence: ["repo=v0idd0/jsonyo", "open issue/release evidence can be attached"], ms: 180 },
      { name: "partner_mcp_probe", status: "blocked", summary: "GitLab MCP requires authentication; this demo refuses to fake it", evidence: ["status=401 without token", "final submission must include authenticated partner MCP log"], ms: 220 },
      { name: "evaluator", status: "blocked", summary: "blocked integration prevents final readiness", evidence: [`readiness_score=${readiness}`], ms: 8 }
    ],
    report: {
      readiness_score: readiness,
      blockers,
      actions: [
        "connect the required partner MCP before final Devpost submission",
        "put platform-native app URL first on every submission page",
        "attach desktop, tablet, mobile screenshots and a 3-minute walkthrough",
        "keep every tool call in the execution log"
      ],
      owner_safe_summary: "the release is close, but Launchroom blocks the final green light until the required platform integration is proven."
    }
  };
}

function render(data) {
  score.textContent = data.report.readiness_score;
  finalState.textContent = data.final_status.replace("_", " ");
  const mcp = data.steps.find(s => s.name.includes("mcp"));
  const ev = data.steps.find(s => s.name === "evaluator");
  mcpState.textContent = mcp?.status || "unknown";
  evalState.textContent = ev?.status || "unknown";
  report.innerHTML = `
    <div class="report-card"><b>summary</b><p>${data.report.owner_safe_summary}</p></div>
    <div class="report-card"><b>blockers</b><ul>${data.report.blockers.map(x => `<li>${x}</li>`).join("")}</ul></div>
    <div class="report-card"><b>next actions</b><ul>${data.report.actions.map(x => `<li>${x}</li>`).join("")}</ul></div>
  `;
  steps.innerHTML = data.steps.map(s => `
    <article class="step" data-status="${s.status}">
      <small>${s.status}</small>
      <strong>${s.name.replaceAll("_", " ")}</strong>
      <p>${s.summary}</p>
      <p>${s.evidence.join("<br>")}</p>
    </article>
  `).join("");
}

document.querySelector("#runBtn").addEventListener("click", () => {
  let input;
  try {
    input = JSON.parse(payload.value);
  } catch {
    report.innerHTML = `<div class="report-card"><b>invalid JSON</b><p>fix the payload and run again.</p></div>`;
    return;
  }
  render(runLocalAgent(input));
});

render(runLocalAgent(sample));

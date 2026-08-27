# CloudOps Phase 0 — Repository and Architecture Audit

**Product:** CloudOps — AI-Powered Infrastructure Operations  
**Repo:** https://github.com/manjunath031984/Employment-Management  
**Branch:** `feature/AI-Infrastructure-Troubleshooting-Agent`  
**Audit date:** 2026-08-27  
**Scope:** Read-only inspection of source, tests, git history, and configuration. No backend rewrite.

This document is the Phase 0 deliverable. Later numbered phases in this file use the **product phase model (0–16)**. Git commit messages still use an older 1–13 backend numbering; both maps are recorded below so they are not confused.

---

## 1. Repository layout

| Path | Role |
|------|------|
| `ai-infrastructure-agent/` | CloudOps backend, agent, tools, frontend, tests |
| `src/` | Existing Java Employment Management application (**do not modify**) |
| `Kubernetes-manifests/` | GKE manifests for Employment Management (**do not modify**) |
| `Dockerfile` + `docker-compose.yml` (repo root) | Employment Management container only |
| `pom.xml` | Java build |

CloudOps is isolated under `ai-infrastructure-agent/`. Regression tests assert Java sources and root compose are untouched.

---

## 2. Architecture (as implemented)

```
Browser (frontend/index.html)
        |
        v
FastAPI (app/main.py)  — /health /ready /api/v1/troubleshoot /api/v1/approve
        |                 StaticFiles mount of frontend at /
        v
LangGraph (app/agent/graph.py)
  request_analyzer → investigation_planner → tool_executor
    → evidence_analyzer → root_cause_analyzer → remediation_planner
    → approval_gate → [remediation_executor | final_report]
    → verification → final_report
        |
        v
Allowlisted tools (read-only investigation)
  Kubernetes | Docker | GCP/gcloud | Terraform (fmt/validate/plan only)
```

**Safety invariants observed in code:**

- Investigation tools are allowlisted; `shell=False`; timeouts on subprocesses.
- Terraform `apply` / `destroy` and kubectl mutating verbs are blocked.
- Remediation requires an explicit human APPROVED record; fail-closed.
- Secrets are env-only; logger scrubs key/token patterns.
- Employment Management Java APIs are not duplicated.

---

## 3. Component findings

### Backend (FastAPI)

- Entry: `app/main.py`
- Routes: `app/api/routes.py` — health, ready, troubleshoot, approve
- Models: `app/api/models.py`
- Config: `app/config.py` (pydantic-settings, env vars)
- Errors: validation → 422; unhandled → 500 without stack traces
- Tests: health, API, models, config

**Status:** Implemented and tested. Do not rebuild.

### AI agent (LangGraph)

- Typed state: `app/agent/state.py` (`AgentState`, evidence, RCA, approval, report)
- Graph + node wrappers: `app/agent/graph.py`
- Nodes: `app/agent/nodes.py`
- Wired to `POST /api/v1/troubleshoot` via `run_investigation`

**Gaps (not Phase 0 work):**

- `investigation_planner` is a **deterministic mock plan** (pods/events/deployment/service). It does not call OpenAI.
- `langchain-openai` is a dependency and `OPENAI_API_KEY` gates `/ready`; there is no `ChatOpenAI` / prompt path in agent code.
- Unknown tool names still fall back to `_mock_tool_result`.

**Status:** Implemented and tested as a rule-based graph. LLM planning is not integrated.

### Infrastructure tools

| Domain | Implemented | Missing vs product checklist |
|--------|-------------|------------------------------|
| Kubernetes | pods, describe, logs, events, deployments, replicasets, services, EndpointSlices, Gateway, HTTPRoute | dedicated `get_namespaces` tool (namespace is a validated parameter, default `employment-management`) |
| Docker | `images`, `ps`, `inspect` | `docker logs` (logs is in the blocked-command set) |
| Terraform | `fmt -check`, `validate`, `plan` (`-lock=false`); apply/destroy blocked | — |
| GCP | project, list/describe GKE cluster, describe instance | — |

Allowlists, validation, timeouts, `ToolResult` output, and unit tests exist.

**Status:** Implemented and tested, with the Docker logs / namespace-list gaps above.

### Evidence

- Models: `EvidenceItem` (`source`, `resource`, `observation`, `timestamp`, `confidence`, `is_inference`)
- Engine: `app/analysis/evidence.py` — confirmed observation vs `is_inference=True`
- Conflicts and missing evidence are recorded, not silently merged
- Tests: `tests/unit/test_evidence_correlation.py`

**Status:** Implemented and tested.

### Root cause

- Engine: `app/analysis/root_cause.py`
- Output: incident, affected resource, root cause, evidence refs, confidence, alternatives, next investigation, risk
- HIGH confidence requires corroborating confirmed signals; insufficient evidence is explicit
- Tests: `tests/unit/test_root_cause.py`

**Status:** Implemented and tested.

### Remediation

Flow in graph: plan → approval_gate → executor (only if APPROVED) → verification → report.

- Planner: `app/analysis/remediation.py` — every action `approval_required=True`, rollback required, dangerous actions excluded
- Approval: `app/approval/service.py` — PENDING / APPROVED / REJECTED, named approver
- Executor: `app/remediation/executor.py` — allowlist + audit trail
- Verification: `app/verification/verifier.py` — does not trust exit code alone

**Status:** Implemented and tested. No automatic destructive execution.

### Frontend

- Single SPA: `frontend/index.html` (Preact + HTM), served at `/`
- Pages: Dashboard, AI Troubleshooter, Investigations, Infrastructure (K8s/Docker/GCP/Terraform catalog), Incidents, Audit Logs, Settings
- Calls existing `/health`, `/ready`, `/api/v1/troubleshoot`, `/api/v1/approve` only
- No frontend unit/e2e tests

**Status:** Implemented; not frontend-tested.

### Security

Present: env secrets, log redaction, prompt-injection blocking, privilege-escalation patterns, command-injection validation, rate limits, body size limit, security headers, human approval for remediation.

Absent: API authentication / authorization (CORS allows Authorization header; no auth dependency on routes).

**Status:** Partially implemented.

### Observability

JSON logs with `request_id`, `agent_node`, `tool_name`, `execution_time`, `status`; secret scrubbing. Tests in `tests/unit/test_logging.py`.

**Status:** Implemented and tested.

### Docker (CloudOps image)

- `ai-infrastructure-agent/Dockerfile`: multi-stage, `python:3.12-slim` (not `:latest`), non-root uid 1000, tini, `/health` HEALTHCHECK, `.dockerignore` excludes `.env`
- Does **not** `COPY frontend/`, so the production image will not serve the CloudOps UI
- No versioned image tag in Compose for this service (CloudOps Compose does not exist)

**Status:** Partially implemented.

### Docker Compose (CloudOps)

Repo-root `docker-compose.yml` runs **Employment Management only** (`employment-management:latest`). It is a protected regression file. There is **no** CloudOps compose (frontend + agent + env).

**Status:** Not started.

### Testing

848 pytest tests at audit time: unit, integration, security, regression, 20 mocked E2E scenarios. No frontend tests. Local live compose E2E is not in the suite.

**Status:** Implemented and tested for backend/agent; frontend and live local E2E incomplete.

### Employment Management regression

`tests/regression/test_existing_app.py` asserts Java sources, root Dockerfile, and root compose still exist and that agent Python is not inside `src/`. Java `mvn test` is the live app regression (run separately).

**Status:** Implemented and tested (pytest regression). Java suite is out of band but passing as of this audit window.

### Production readiness review

No signed production-readiness or security-review artifact existed before this Phase 0 document.

**Status:** Not started (Phases 13 and 16).

---

## 4. Git history (legacy backend phase numbers)

These commits are on this branch; names refer to the **old** 1–13 plan, not product phases 0–16:

| Commit | Legacy message |
|--------|----------------|
| `61f4bb6` | phase1 foundation |
| `775d9c9` | phase2 LangGraph |
| `2ae2321` | phase3 Kubernetes tools |
| `31e3a7e` | phase4 Docker/GCP/Terraform |
| `5ffadaa` | phase5 evidence |
| `4a059aa` | phase6 RCA |
| `ba0086a` | phase7 remediation planner |
| `0953958` | phase8 approval |
| `ba0d955` | phase9 executor |
| `167eece` | phase10 verification |
| `7973b72` | phase11 security |
| `14502b2` | phase12 Dockerfile |
| `55e4f39` | phase13 E2E tests |
| `46d7e68` | CloudOps frontend |

---

## 5. Product phase status (0–16)

| Phase | Name | Status |
|-------|------|--------|
| 0 | Repository and architecture audit | Implemented and tested (this document + `test_phase0_audit.py`) |
| 1 | CloudOps backend | Implemented and tested |
| 2 | AI agent validation/integration | Partially implemented (graph wired; no LLM planner) |
| 3 | Infrastructure tools | Implemented and tested (gaps: docker logs, get namespaces) |
| 4 | Evidence collection | Implemented and tested |
| 5 | Root cause analysis | Implemented and tested |
| 6 | Safe remediation | Implemented and tested |
| 7 | Professional CloudOps frontend | Implemented (no frontend tests) |
| 8 | Frontend/backend security | Partially implemented (no API authz) |
| 9 | Observability | Implemented and tested |
| 10 | Docker/containerization | Partially implemented (image omits frontend) |
| 11 | Local Docker Compose | Not started |
| 12 | Comprehensive testing | Partially implemented (no frontend tests) |
| 13 | Production security review | Not started |
| 14 | Local end-to-end testing | Partially implemented (mocked E2E only) |
| 15 | Employment Management regression | Implemented and tested |
| 16 | Final production readiness review | Not started |

---

## 6. Explicit non-goals of this audit

- Do not rewrite FastAPI, LangGraph, tools, or the frontend.
- Do not duplicate Employment Management APIs.
- Do not modify root `docker-compose.yml` as CloudOps compose (add a separate file in a later phase).
- Do not skip to Compose, LLM planning, or production review in this phase.

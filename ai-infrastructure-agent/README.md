# AI Infrastructure Troubleshooting Agent

A production-grade intelligent agent for diagnosing and remediating Kubernetes, Docker, GCP/GKE, and Terraform infrastructure incidents.

---

## Architecture

```
USER
 |
 v
FastAPI API (/api/v1/troubleshoot)
 |
 v
LangGraph Workflow
 ├── request_analyzer
 ├── investigation_planner
 ├── tool_executor
 │    ├── Kubernetes Tools (read-only)
 │    ├── Docker Tools (read-only)
 │    ├── GCP Tools (read-only)
 │    └── Terraform Tools (plan/validate only)
 ├── evidence_analyzer
 ├── root_cause_analyzer
 ├── remediation_planner
 ├── approval_gate  ← HUMAN APPROVAL REQUIRED
 ├── remediation_executor (allowlisted only)
 ├── verification
 └── final_report
```

## Design Principles

1. **Safety first** — read-only investigation by default
2. **No arbitrary shell execution** — all tools are deterministic and allowlisted
3. **LLM reasons, tools execute** — LLM never directly runs infrastructure commands
4. **Explicit typed state** — `AgentState` Pydantic model, no raw dicts
5. **Evidence ≠ Inference** — separated explicitly in all outputs
6. **Human approval before remediation** — fail closed
7. **Least privilege** — scoped to `employment-management` namespace
8. **Secrets never in source** — all credentials via environment variables
9. **Auditable** — every remediation logged with `request_id`, `approval_id`, timestamp
10. **Comprehensive testing** — unit, integration, security, regression

## Target Infrastructure

| Component | Value |
|-----------|-------|
| GCP Project | `gcp-dev-july-2026` |
| GKE Cluster | `employment-management-gke` |
| Region | `us-central1` |
| Namespace | `employment-management` |
| Image Registry | `us-central1-docker.pkg.dev/gcp-dev-july-2026/employment-management` |

## Getting Started

### Prerequisites

- Python 3.12+
- An OpenAI API key
- `kubectl` configured for the target cluster (Phase 3+)

### Setup

```bash
cd ai-infrastructure-agent

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY
```

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe (requires `OPENAI_API_KEY`) |
| `POST` | `/api/v1/troubleshoot` | Submit a troubleshooting request |
| `POST` | `/api/v1/approve` | Submit human approval / rejection |

### Example Request

```bash
curl -X POST http://localhost:8080/api/v1/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{"request": "Why is my employment management pod failing?"}'
```

### Example Response

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "INVESTIGATED",
  "root_cause": {
    "incident_status": "ACTIVE",
    "affected_resource": "pod/employment-management-xxx",
    "root_cause": "Invalid readiness probe configuration",
    "confidence": "HIGH",
    "reasoning_summary": "..."
  },
  "confidence": "HIGH",
  "evidence": [...],
  "remediation": [...],
  "approval_required": true,
  "approval_status": "PENDING"
}
```

## Running Tests

```bash
cd ai-infrastructure-agent

# All tests
python3 -m pytest tests/ -v

# By category
python3 -m pytest tests/unit/ -v -m unit
python3 -m pytest tests/integration/ -v -m integration
python3 -m pytest tests/security/ -v -m security
python3 -m pytest tests/regression/ -v -m regression
```

## Project Structure

```
ai-infrastructure-agent/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Pydantic settings (all from env vars)
│   ├── api/
│   │   ├── models.py        # Request/response Pydantic models
│   │   └── routes.py        # FastAPI route handlers
│   ├── agent/
│   │   ├── state.py         # Typed LangGraph state (AgentState)
│   │   ├── graph.py         # LangGraph workflow definition (Phase 2)
│   │   └── nodes.py         # Graph node implementations (Phase 2)
│   ├── tools/               # Infrastructure tool wrappers (Phase 3-4)
│   │   ├── base.py
│   │   ├── kubernetes/
│   │   ├── docker/
│   │   ├── gcp/
│   │   └── terraform/
│   ├── analysis/            # Evidence correlation & root cause (Phase 5-6)
│   ├── approval/            # Human approval workflow (Phase 8)
│   ├── remediation/         # Allowlisted remediation executor (Phase 9)
│   ├── verification/        # Post-remediation verification (Phase 10)
│   └── logging/             # Structured JSON logger with secret scrubbing
├── frontend/                # CloudOps operator UI (served at /)
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── regression/
├── .env.example             # Environment variable template (never commit .env)
├── requirements.txt
├── pytest.ini
└── Dockerfile               # Phase 12
```

## Security

- All secrets via environment variables — never hard-coded
- `OPENAI_API_KEY` redacted in all log output
- No `shell=True` subprocess calls
- All tool inputs validated before execution
- LLM cannot directly invoke infrastructure commands
- Remediation requires explicit human approval
- Command injection protection on all tool parameters

## Implementation Phases

Product phases (0–16) are defined in
[`docs/PHASE0_ARCHITECTURE_AUDIT.md`](docs/PHASE0_ARCHITECTURE_AUDIT.md).
Git commits still use an older 1–13 backend numbering; use the audit for status.

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | ✅ Complete | Repository and architecture audit |
| 1 | ✅ Complete | CloudOps FastAPI backend |
| 2 | ✅ Complete | LangGraph agent; request-aware allowlisted tool selection |
| 3 | ✅ Complete | Allowlisted K8s / Docker / GCP / Terraform tools (see audit gaps) |
| 4 | ✅ Complete | Evidence collection and correlation |
| 5 | ✅ Complete | Root cause analysis |
| 6 | ✅ Complete | Safe remediation (plan, approval, execute, verify) |
| 7 | ✅ Complete | CloudOps frontend (pages + UI tests) |
| 8 | Partial | Hardening present; no API authentication |
| 9 | ✅ Complete | Structured logging and request IDs |
| 10 | Partial | Production Dockerfile; image omits frontend |
| 11 | Not started | Local CloudOps Docker Compose |
| 12 | Partial | 848 backend tests; no frontend tests |
| 13 | Not started | Production security review |
| 14 | Partial | Mocked E2E; no live local compose E2E |
| 15 | ✅ Complete | Employment Management isolation regression |
| 16 | Not started | Final production readiness review |

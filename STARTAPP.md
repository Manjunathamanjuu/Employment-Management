# CloudOps — Local Application Startup Guide

This guide starts **CloudOps** (the AI Infrastructure Troubleshooting Agent and operator UI) on a laptop after shutdown or restart.

CloudOps lives in `ai-infrastructure-agent/`. The FastAPI process serves both the API and the UI.

**How CloudOps is actually started in this repository:** Python `uvicorn`, not Docker Compose.

The repository-root `docker-compose.yml` starts **Employment Management** (the Java Spring Boot app) on port **8080**. It does **not** start CloudOps and it does **not** publish port **8081**. There is no CloudOps Compose service in this project.

| Application | How it starts | Local URL |
| --- | --- | --- |
| CloudOps | `uvicorn` from `ai-infrastructure-agent/` | http://127.0.0.1:8081/ |
| Employment Management | `docker compose up -d` from the repo root | http://localhost:8080/ |

Use port **8081** for CloudOps so it does not collide with Employment Management on **8080**.

---

## 1. Prerequisites

Required to start CloudOps locally:

- **Git**
- **Python 3.12 or newer** (this workspace was verified with Python 3.13)
- **pip** (comes with Python)
- An **OpenAI API key** if you need the agent to be ready (`GET /ready`) and to run investigations. The UI and `GET /health` still work without a key.

Optional (only if you will investigate real infrastructure from the agent):

- **kubectl** configured for the target cluster
- **Docker Desktop / Docker CLI** (Docker investigation tools, or to run Employment Management)
- **gcloud** (GCP/GKE tools)
- **Terraform** (Terraform validate/plan tools)

**Docker Desktop is not required to start CloudOps.** The CloudOps UI and API run as a local Python process.

There is no `package.json` for CloudOps. Node.js is not required. The UI is static HTML served by FastAPI.

---

## 2. Clone / Navigate to Project

Repository: `https://github.com/manjunath031984/Employment-Management.git`

Branch used for CloudOps: `feature/AI-Infrastructure-Troubleshooting-Agent`

### First-time clone

```bash
git clone https://github.com/manjunath031984/Employment-Management.git
cd Employment-Management
git checkout feature/AI-Infrastructure-Troubleshooting-Agent
cd ai-infrastructure-agent
```

### Already cloned on this laptop (PowerShell)

```powershell
cd "D:\Employment Management\ai-infrastructure-agent"
```

### Already cloned (Git Bash)

```bash
cd "/d/Employment Management/ai-infrastructure-agent"
```

All CloudOps start, install, and `.env` commands below assume this directory (`ai-infrastructure-agent/`).

---

## 3. Verify Docker

Docker is optional for CloudOps. Verify it only if you will use Docker tools or start Employment Management.

```bash
docker --version
docker compose version
```

Verify Python (required for CloudOps):

```bash
python --version
```

Expect Python 3.12 or newer.

If `python` is not found, try `py --version` on Windows and use `py -m uvicorn` / `py -m pip` in the commands below.

---

## 4. Environment Configuration

CloudOps loads settings from environment variables and from a `.env` file in `ai-infrastructure-agent/` (`app/config.py`). **Never commit `.env`.**

There is currently **no** `.env.example` file in the tree. Create `.env` yourself in `ai-infrastructure-agent/`.

### Required for agent readiness and investigations

```env
OPENAI_API_KEY=<your-api-key>
```

Do not paste a real key into this document or into git.

Placeholder values such as `your-openai-api-key-here` or `sk-example` are treated as **not configured**.

### Optional (defaults already exist in code)

```env
OPENAI_MODEL=gpt-4o
GCP_PROJECT_ID=gcp-dev-july-2026
GKE_CLUSTER_NAME=employment-management-gke
GKE_REGION=us-central1
KUBERNETES_NAMESPACE=employment-management
KUBERNETES_CONTEXT=<your-kubectl-context>
TERRAFORM_WORKING_DIRECTORY=<path-to-terraform-workspace>
TOOL_TIMEOUT_SECONDS=30
LLM_TIMEOUT_SECONDS=60
MAX_INVESTIGATION_STEPS=20
REQUIRE_HUMAN_APPROVAL=true
```

`HOST` and `PORT` in settings default to `0.0.0.0` and `8080`. Local CloudOps is started with an explicit uvicorn `--port 8081` so it does not conflict with Employment Management. You do not need to set `PORT` in `.env` when using the uvicorn command in this guide.

### PowerShell: create `.env` without printing the key

```powershell
cd "D:\Employment Management\ai-infrastructure-agent"
@"
OPENAI_API_KEY=<your-api-key>
"@ | Set-Content -Path .env -Encoding utf8
```

Then edit `.env` in an editor and replace `<your-api-key>` with your real key. Do not run `type .env` or `Get-Content .env` in shared terminals.

---

## 5. Start the Application

### First time only — install Python dependencies

From `ai-infrastructure-agent/`:

```bash
python -m pip install -r requirements.txt
```

You do **not** need to reinstall every day.

### Start CloudOps (the command this project actually uses)

From `ai-infrastructure-agent/`:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
```

Leave this terminal open. You should see:

```text
Uvicorn running on http://127.0.0.1:8081
```

The `ai-infrastructure-agent/README.md` example uses port **8080**. Use **8081** on this machine so CloudOps does not collide with Employment Management.

### Docker Compose — what it actually starts

From the **repository root** (`Employment Management /`), not `ai-infrastructure-agent/`:

```bash
docker compose up -d
```

This starts **one** service:

| Compose service | Container name | Host port | Application |
| --- | --- | --- | --- |
| `employment-management` | `employment-management` | `8080` | Employment Management (Java) |

**No Compose service exposes port 8081.** `docker compose up -d` does not start CloudOps.

Use `docker compose up -d --build` only when you need to rebuild the **Employment Management** image (Java/Dockerfile/static UI changes). It is not part of daily CloudOps startup. See [section 13](#13-rebuild-instructions).

---

## 6. Verify Containers

### CloudOps (Python process)

CloudOps is not a Compose container. Confirm it from another terminal:

```bash
curl http://127.0.0.1:8081/health
```

PowerShell:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8081/health" -UseBasicParsing
```

Expect HTTP **200** and JSON including `"status":"ok"`.

### Employment Management (Compose) — optional

If you also started Compose from the repo root:

```bash
docker compose ps
```

You should see `employment-management` running and `0.0.0.0:8080->8080/tcp`. You will **not** see a CloudOps service.

---

## 7. Check Application

CloudOps UI:

**http://127.0.0.1:8081/**

Health (liveness — process is alive):

```bash
curl http://127.0.0.1:8081/health
```

Example successful body:

```json
{"status":"ok","version":"1.0.0","timestamp":"<iso-timestamp>"}
```

Readiness (OpenAI key configured):

```bash
curl http://127.0.0.1:8081/ready
```

- HTTP **200** and `"ready": true` — `OPENAI_API_KEY` is configured
- HTTP **503** — the UI can still load; investigations that need the LLM will not be ready

These endpoints are implemented in `ai-infrastructure-agent/app/api/routes.py` as `GET /health` and `GET /ready`.

---

## 8. View Logs

### CloudOps

Logs print in the terminal where uvicorn is running. There is no CloudOps Compose service to tail.

Stop following by using **Ctrl+C** in that terminal (that also stops the app). To keep the app running, leave the terminal open and watch it.

### Employment Management Compose (repo root only)

All Compose services (this repo has one):

```bash
docker compose logs -f
```

Specific service (actual name from `docker-compose.yml`):

```bash
docker compose logs -f employment-management
```

These logs are **not** CloudOps logs.

---

## 9. Restart Application

### CloudOps

In the uvicorn terminal press **Ctrl+C**, then start again:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
```

Use this after changing `.env` (the process reads env at startup) or after pulling new Python code.

### Employment Management Compose

From the repo root:

```bash
docker compose restart
```

This restarts the `employment-management` container without rebuilding. It does not restart CloudOps.

---

## 10. Stop Application

### CloudOps

In the uvicorn terminal press **Ctrl+C**.

That stops the Python process. It does **not** delete source code, `.env`, or git history.

### Employment Management Compose

From the repo root:

```bash
docker compose down
```

This stops and removes the Compose containers (and the default Compose network). It does **not** delete the source code, git history, or the CloudOps project files.

---

## 11. Start Application Tomorrow

### Starting CloudOps After Laptop Restart

1. **Start Docker Desktop** only if you need Docker investigation tools or Employment Management. Skip this step to run CloudOps alone.
2. **Open PowerShell or Git Bash.**
3. **Navigate to CloudOps:**

   ```powershell
   cd "D:\Employment Management\ai-infrastructure-agent"
   ```

4. **Confirm `.env` still exists** (do not print it). If this is a new clone, recreate it as in [section 4](#4-environment-configuration).
5. **Start CloudOps:**

   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
   ```

   First time on a new machine only: `python -m pip install -r requirements.txt` before uvicorn.
6. **Verify:**

   ```bash
   curl http://127.0.0.1:8081/health
   ```

7. **Open the UI:** [http://127.0.0.1:8081/](http://127.0.0.1:8081/)

You do not need any other document for this daily path.

---

## 12. Troubleshooting

### Port 8081 already in use

CloudOps is bound to **8081** in this guide. Employment Management Compose uses **8080**, not 8081.

PowerShell — see which process holds 8081:

```powershell
netstat -ano | findstr :8081
```

If an old uvicorn is still running, stop that process or close its terminal (**Ctrl+C**). Do not change `docker-compose.yml` to “fix” 8081; Compose does not map that port.

If **8080** is in use, that is Employment Management (or another app), not CloudOps.

### Container is not running

CloudOps is not a container. If you expected a CloudOps container, that is expected: none is defined.

For Employment Management:

```bash
docker compose ps
docker compose logs -f employment-management
```

Run those from the **repository root**.

### Application is not accessible

1. Confirm uvicorn is still running in its terminal (`Uvicorn running on http://127.0.0.1:8081`).
2. Open http://127.0.0.1:8081/ (not port 8080 — that is Employment Management).
3. Check liveness: `curl http://127.0.0.1:8081/health` — expect HTTP 200.
4. Check readiness: `curl http://127.0.0.1:8081/ready` — 503 means the key is missing; the UI should still load.
5. Confirm you started from `ai-infrastructure-agent/` so `app.main:app` and `frontend/` resolve.
6. `docker compose ps` will not explain a CloudOps outage. Compose port mapping is `8080:8080` for `employment-management` only.

### Environment variable / API key problem

Do **not** print the key.

PowerShell — is the variable set in this session?

```powershell
if ($env:OPENAI_API_KEY) { "OPENAI_API_KEY is set" } else { "OPENAI_API_KEY is not set in this session" }
```

Is `.env` present (without reading it)?

```powershell
Test-Path "D:\Employment Management\ai-infrastructure-agent\.env"
```

Then check readiness without exposing secrets:

```bash
curl http://127.0.0.1:8081/ready
```

- **200** — key is accepted as configured
- **503** — key missing, empty, or a rejected placeholder

Restart uvicorn after changing `.env`.

### Docker Desktop not running

Windows: open **Docker Desktop** from the Start menu and wait until it reports running.

Then:

```bash
docker --version
docker compose version
docker info
```

If `docker info` fails, Desktop is not ready. This does not block CloudOps uvicorn.

---

## 13. Rebuild Instructions

**Daily CloudOps start does not use `--build`.** Re-run uvicorn only.

| Situation | Command |
| --- | --- |
| Normal CloudOps start (code already installed) | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8081` |
| New machine / new venv / `requirements.txt` changed | `python -m pip install -r requirements.txt` then uvicorn |
| Rebuild Employment Management image | From repo root: `docker compose up -d --build` |
| Start Employment Management without rebuilding | From repo root: `docker compose up -d` |

`docker compose up -d --build` rebuilds **Employment Management** (`Dockerfile` at repo root). It does not build or start CloudOps.

`ai-infrastructure-agent/Dockerfile` is a production image for the agent API. It listens on container port **8080**, and the image does not copy `frontend/`, so it is **not** the local CloudOps UI path documented here.

---

# Quick Start

From an already-cloned repository, after Python dependencies have been installed once:

```powershell
cd "D:\Employment Management\ai-infrastructure-agent"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
```

In a second terminal:

```powershell
curl http://127.0.0.1:8081/health
```

Then open:

**http://127.0.0.1:8081/**

`docker compose up -d` is **not** in this Quick Start because it starts Employment Management on port 8080, not CloudOps.

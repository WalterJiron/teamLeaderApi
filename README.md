# TeamLeader Backend API and Services

Backend platform built with FastAPI (Python), PostgreSQL for relational data and state-hash caching, MongoDB for conversational agent memory, Redis for caching and rate-limiting, Mailpit for local email testing, and n8n for executive AI workflow orchestration.

---

## Architecture Overview

* **Core Backend:** FastAPI (Python 3.13) with asynchronous SQLAlchemy 2.0, asyncpg, Motor (MongoDB), Redis, and strict tenant isolation (ISO/IEC 27001).
* **AI Agent Module (`/api/v1/agent`):**
  * Executive assistance on repository integrations, area health, and project metrics.
  * **Deterministic State-Hash Caching:** Zero-token responses when repository and task state hash matches (`0` LLM tokens spent).
  * **Conversational Memory:** Multi-tenant chat history stored in MongoDB (`agent_memory_db.agent_memory`).
  * **Anti-Prompt Injection Guardrails:** XML delimiter isolation, strict instruction hierarchy, and leakage prevention.
* **Integrations & Metrics (`/api/v1/github-integrations`):**
  * GitHub issue and webhook synchronization with HMAC SHA-256 signature verification.
  * Encrypted credential storage (Fernet symmetric encryption).
  * Deterministic area snapshot calculations (`completed_tasks`, `total_tasks`, `blocked_tasks`, `remaining_days`, `deadline_probability`, `health_status`).
* **n8n Orchestration:** LangChain agent connected to OpenRouter (`google/gemini-2.0-flash-001` or compatible), MongoDB memory, and authorized HTTP tools querying FastAPI.

---

## Prerequisites

Before starting, make sure you have installed:

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Docker Compose v2 or higher)
* Git

---

## Installation and Setup

### 1. Configure Environment Variables

Copy the `.env.example` file to `.env`:

```bash
cp .env.example .env
```

Review the values in `.env` if you need custom settings (e.g. `N8N_AGENT_CHAT_URL`).

### 2. Start Services with Docker Compose

Run the following command in the project root folder:

```bash
docker compose up -d --build
```

Check the status of all containers:

```bash
docker compose ps
```

All services should be running and healthy.

### 3. Run Database Migrations

Apply the database migrations with Alembic:

```bash
docker compose exec api alembic upgrade head
```

---

## Services, Ports, and Default Credentials

| Service | Host / URL | Port | Default Credentials / Details |
| :--- | :--- | :--- | :--- |
| **FastAPI Backend** | [http://localhost:8000](http://localhost:8000) | `8000` | Swagger UI at `/docs` |
| **n8n (AI Agent)** | [http://localhost:5678](http://localhost:5678) | `5678` | **Email:** `develop@gmail.com`<br>**Password:** `Develop.123` |
| **pgAdmin 4** | [http://localhost:5050](http://localhost:5050) | `5050` | **Email:** `admin@example.com`<br>**Password:** `Admin.01` |
| **PostgreSQL** | `localhost` | `5432` | **User:** `admin`<br>**Password:** `Admin.01`<br>**Database:** `teamleader_db` |
| **MongoDB** | `localhost` | `27017` | **User:** `admin`<br>**Password:** `admin.123`<br>**Database:** `agent_memory_db` |
| **Mailpit (Web UI)** | [http://localhost:8025](http://localhost:8025) | `8025` | No authentication |
| **Mailpit (SMTP)** | `localhost` | `1025` | No authentication |
| **Redis** | `localhost` | `6379` | No authentication |

### AI Agent Service Account (API Login):
Used by the n8n agent workflow to authenticate and call protected backend tools:
* **Email:** `agent@example.com`
* **Password:** `AgentSecret123!`

---

## Key API Endpoints

### AI Agent (`/api/v1/agent`):
* `POST /api/v1/agent/chat`: Send prompt to AI agent. Supports optional `project_id` and `area_id` for deterministic zero-token caching.
* `GET /api/v1/agent/sessions`: List user's conversation sessions with message counts and last activity.
* `GET /api/v1/agent/sessions/{session_id}/messages`: Retrieve paginated message history for a session.
* `DELETE /api/v1/agent/sessions/{session_id}`: Delete a session and its associated memory turns.

### GitHub Integrations (`/api/v1/github-integrations`):
* `POST /api/v1/github-integrations`: Register a repository integration with encrypted credentials.
* `GET /api/v1/github-integrations`: List integrations for the current tenant.
* `POST /api/v1/github-integrations/{integration_id}/syncs`: Trigger a manual repository sync and recalculate area snapshots.
* `POST /api/v1/github-integrations/webhook`: Ingest GitHub webhook events (issues, labels).

---

## n8n Workflow Setup and Backup

The project maintains exported workflows in the [`local-files/`](./local-files) directory.

### Import the AI Agent Workflow:

To import the preconfigured AI Agent workflow into n8n:

```bash
# 1. Import workflow from local-files
docker exec n8n n8n import:workflow --input=/files/current_workflows.json

# 2. Publish workflow
docker exec n8n n8n publish:workflow --id=pjM7NRN14vlPZ1l2

# 3. Restart n8n container to apply changes
docker restart n8n
```

### Export Workflow Backup:

When you update workflows in n8n and want to sync your changes back to `local-files/`:

```bash
docker exec n8n n8n export:workflow --all --output=/files/current_workflows.json
```

For more details, see [`local-files/README.md`](./local-files/README.md).

---

## Health Checks and API Documentation

When the application is running:

* **Liveness Probe:** `GET http://localhost:8000/health` (Returns `{"status": "ok"}`)
* **Readiness Probe:** `GET http://localhost:8000/health/ready` (Verifies PostgreSQL and Redis connectivity)
* **Interactive API Documentation (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **OpenAPI Specification:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

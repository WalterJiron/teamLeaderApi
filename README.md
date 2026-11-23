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

### Jira Cloud Integration and Team Assessment

The API connects an internal TeamLeader project to a Jira Cloud project, verifies the credentials before saving, and synchronizes current issues and recent delivery history on demand. All endpoints require a TeamLeader bearer token.

#### Connect Jira

Create an Atlassian API token for the Jira account. The account must be able to browse the Jira project. To include project roles, it also needs permission to read the project's roles. Never commit or share the API token in source control or chat.

Register the integration as a team manager:

```http
POST /api/v1/jira-integrations
Authorization: Bearer <teamleader-access-token>
Content-Type: application/json
```

```json
{
  "project_id": 1,
  "jira_base_url": "https://your-tenant.atlassian.net",
  "jira_project_key": "TEAM",
  "jira_email": "jira-account@example.com",
  "api_token": "REPLACE_WITH_YOUR_ATLASSIAN_API_TOKEN",
  "project_deadline": "2026-12-31"
}
```

`project_deadline` is optional. Jira Cloud does not expose a standard project-level deadline; when omitted, synchronization uses the nearest due date among unresolved issues. If neither source has a deadline, the response warns that imminent-deadline risk could not be evaluated.

The API verifies access to the project before creating the tenant-scoped integration. It encrypts the API token at rest with `CREDENTIALS_ENCRYPTION_KEY`; responses only contain a masked token. Duplicate Jira projects and duplicate internal-project links are rejected.

List integrations with `GET /api/v1/jira-integrations`. A team manager can trigger a live synchronization and assessment with:

```http
POST /api/v1/jira-integrations/{integration_id}/syncs
Authorization: Bearer <teamleader-access-token>
```

The sync fetches project issues from Jira's REST API with token-based pagination, excludes subtasks, maps status/resolution, assignees, issue due dates and Jira project roles, then runs the assessment below. It reads the last 12 complete UTC weeks of resolution history and the current partial week directly from Jira on each sync; TeamLeader does not need a caller to resubmit that history. Page size is capped at 100 and a sync fails rather than returning partial results if the 100-page limit is exceeded.

If Jira does not allow access to project roles, the sync still returns issue metrics, labels members' role as unavailable, and includes a warning. Jira Cloud custom domains and Jira Server/Data Center URLs are not accepted by this version; the URL must be an HTTPS `*.atlassian.net` tenant.

#### Assessment rules and AI response

The sync response contains a structured `assessment` and any `warnings`. The authenticated `POST /api/v1/metrics/delay-risk-assessment` endpoint remains available for clients that already have normalized metrics. Both use the same deterministic assessment logic and include `agent_message`, a concise summary for an AI agent.

* **Delay risk:** `total_tasks`, `unresolved_tasks`, and `remaining_days` determine the tier. One to three unresolved tasks among more than eight is low risk; four to six among more than twelve is low-medium; exactly half unresolved is medium; more than half is medium-high, or high when fewer than two days remain. If no deadline is known, deadline-specific escalation is not inferred.
* **Member with the most tasks:** the assessment returns `member_with_most_tasks` and `member_with_most_pending`, each including the Jira member name and role. Total `assigned_tasks` are used when available for every member; otherwise unresolved-task count is used, explained by `member_task_count_basis`. When multiple Jira roles apply, they are returned together.
* **Productivity:** completed Jira issues are grouped by week. The assessment compares current tasks/day against the arithmetic mean of the per-day rates from the previous 12 complete UTC weeks. The `productivity` object includes `historical_periods`, `historical_average_tasks_per_day`, `historical_average_days_per_task`, `current_tasks_per_day`, `is_below_historical_average`, and a textual `comparison`. If there are no historical completions, no baseline is claimed.
* **Team recommendations:** unresolved workload greater than 1.5 times the team average produces a high-priority workload-imbalance recommendation, suggesting below-average teammates as possible redistribution candidates and advising a review of role, availability and task complexity. Productivity below the historical mean generates a recommendation to review blockers, scope and workload distribution before drawing conclusions about an individual.

The request validates project/member task counts, requires a role for supplied team members, and bounds the issue/member/history page sizes. The Jira sync reports missing due dates or role permissions as warnings rather than presenting them as known facts.

#### Verification

Run the API test suite in Docker:

```bash
docker compose exec -T api pytest -q /app/tests
```

The tests cover risk thresholds, roles and workload recommendations, productivity history, Jira authentication/error mapping, secure tenant URL validation, paginated issue fetching, Jira-to-assessment mapping, and incomplete Jira data.

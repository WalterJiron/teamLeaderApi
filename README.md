# TeamLeader Backend API and Services

Backend platform built with FastAPI (Python), PostgreSQL for relational data, MongoDB for agent memory, Redis for caching, Mailpit for local email testing, and n8n for AI workflow orchestration.

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

Review the values in `.env` if you need custom settings.

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

| Service | Host / URL | Port | Default Credentials |
| :--- | :--- | :--- | :--- |
| **FastAPI Backend** | [http://localhost:8000](http://localhost:8000) | `8000` | N/A (Swagger UI at `/docs`) |
| **n8n (AI Agent)** | [http://localhost:5678](http://localhost:5678) | `5678` | **Email:** `develop@gmail.com`<br>**Password:** `Develop.123` |
| **pgAdmin 4** | [http://localhost:5050](http://localhost:5050) | `5050` | **Email:** `admin@example.com`<br>**Password:** `Admin.01` |
| **PostgreSQL** | `localhost` | `5432` | **User:** `admin`<br>**Password:** `Admin.01`<br>**Database:** `teamleader_db` |
| **MongoDB** | `localhost` | `27017` | **User:** `admin`<br>**Password:** `admin.123`<br>**Database:** `agent_memory_db` |
| **Mailpit (Web UI)** | [http://localhost:8025](http://localhost:8025) | `8025` | No authentication |
| **Mailpit (SMTP)** | `localhost` | `1025` | No authentication |
| **Redis** | `localhost` | `6379` | No authentication |

---

## n8n Setup and Backup

The project includes an exported backup in the [`local-files/`](./local-files) directory.

### Owner Account Credentials (Development):

* **Email:** `develop@gmail.com`
* **First Name:** `dev`
* **Last Name:** `elop`
* **Password:** `Develop.123`

### Restore Workflows and Credentials:

To import the preconfigured AI Agent workflow and credentials into n8n:

```bash
# 1. Import MongoDB credentials
docker exec n8n n8n import:credentials --input=/files/credentials.json

# 2. Import the AI Agent workflow
docker exec n8n n8n import:workflow --input=/files/workflows.json
```

### Export a New Backup:

If you update workflows in n8n and want to save a new backup to `local-files/`:

```bash
# Export all workflows
docker exec n8n n8n export:workflow --all --output=/files/workflows.json

# Export credentials (decrypted)
docker exec n8n n8n export:credentials --all --decrypted --output=/files/credentials.json

# Copy the full SQLite database
docker exec n8n cp -r /home/node/.n8n /files/n8n_backup
```

For more details, see [`local-files/README.md`](./local-files/README.md).

---

## Health Checks and API Documentation

When the application is running, you can test the following endpoints:

* **Liveness Probe:** `GET http://localhost:8000/health` (Returns `{"status": "ok"}`)
* **Readiness Probe:** `GET http://localhost:8000/health/ready` (Verifies PostgreSQL and Redis connectivity)
* **Interactive API Documentation (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **OpenAPI Specification:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

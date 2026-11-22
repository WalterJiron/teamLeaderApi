# n8n Backup and Local Files

This directory (`local-files/`) contains the exported backup of n8n, including workflows and development credentials.

---

## Owner Account Credentials (Development)

* **Email:** `develop@gmail.com`
* **First Name:** `dev`
* **Last Name:** `elop`
* **Password:** `Develop.123`
* **Local URL:** [http://localhost:5678](http://localhost:5678)

---

## Backup Files Overview

| File / Folder | Description |
| :--- | :--- |
| **`workflows.json`** | JSON export of all n8n workflows (including the AI Agent workflow with chat trigger, LangChain agent, and MongoDB memory). |
| **`credentials.json`** | Decrypted credentials export in JSON format (MongoDB `agent_memory_db` connection). |
| **`n8n_backup/`** | Full copy of `/home/node/.n8n`, including the SQLite database (`database.sqlite`), configuration (`config`), and storage. |

---

## How to Restore n8n Data

### Option A: Import Workflows and Credentials (Recommended)

If the n8n container is already running:

```bash
# 1. Import credentials
docker exec n8n n8n import:credentials --input=/files/credentials.json

# 2. Import workflows
docker exec n8n n8n import:workflow --input=/files/workflows.json
```

### Option B: Full SQLite Database Restore

To restore the complete n8n state (users, credentials, history, and settings):

```bash
# 1. Stop the n8n container
docker compose stop n8n

# 2. Copy the backup files into the n8n volume
docker compose run --rm -v $(pwd)/local-files/n8n_backup:/backup -v n8n_data:/data alpine cp -a /backup/. /data/

# 3. Start the n8n container
docker compose start n8n
```

---

## How to Create a New Backup

If you make changes to workflows in n8n and want to update this directory:

```bash
# Export all workflows
docker exec n8n n8n export:workflow --all --output=/files/workflows.json

# Export credentials (decrypted)
docker exec n8n n8n export:credentials --all --decrypted --output=/files/credentials.json

# Backup the complete n8n data directory
docker exec n8n cp -r /home/node/.n8n /files/n8n_backup
```

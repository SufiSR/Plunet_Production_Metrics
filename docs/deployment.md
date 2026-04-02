# Deployment Guide

This document covers the production deployment of the DORA Metrics application using Docker Compose and Caddy as the host reverse proxy.

---

## Architecture overview

```
Internet
    │
    ▼
┌──────────────────────────────────────┐
│  Host machine                        │
│                                      │
│  ┌─────────────────────────────────┐ │
│  │  Caddy (on host, port 80/443)   │ │
│  │  – TLS termination              │ │
│  │  – Reverse proxy to containers  │ │
│  └──────┬───────────────┬──────────┘ │
│         │               │            │
│  Docker Compose network (dora_net)   │
│         │               │            │
│  ┌──────▼──────┐ ┌──────▼──────┐    │
│  │  frontend   │ │   backend   │    │
│  │  :3000      │ │   :8000     │    │
│  └─────────────┘ └──────┬──────┘    │
│                          │           │
│                   ┌──────▼──────┐   │
│                   │     db      │   │
│                   │  Postgres   │   │
│                   │  :5432      │   │
│                   └─────────────┘   │
└──────────────────────────────────────┘
```

**Key decision**: Caddy runs **on the host**, not inside the Docker Compose stack. This is per the project specification (`TLS / proxy: Caddy on host`). There is deliberately no nginx service in `docker-compose.yml`.

---

## Prerequisites

- Docker Engine ≥ 24 and Docker Compose v2
- [Caddy](https://caddyserver.com/docs/install) installed on the host
- A DNS A/AAAA record pointing `dora.example.com` to the host IP

---

## 1. Clone and configure

```bash
git clone https://gitlab.plunet.com/operations/dora-metrics.git
cd dora-metrics

# Create the .env file from the Docker-specific template
cp .env.docker.example .env
```

Edit `.env` and fill in all `replace-me` values:

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Strong password for the `dora` DB user |
| `GITLAB_API_TOKEN` | GitLab personal/project access token |
| `JIRA_API_TOKEN` | Jira API token |
| `DORA_ADMIN_PASSWORD` | Bootstrap admin password |
| `DORA_SESSION_SECRET` | Random string ≥ 16 characters for signed session cookies |
| `CONFIG_ENCRYPTION_KEY` | 32-byte base64 key for secrets stored in the DB |
| `DORA_CORS_ORIGINS` | Public frontend URL, e.g. `https://dora.example.com` |
| `NEXT_PUBLIC_API_URL` | Public backend API URL, e.g. `https://dora.example.com/api` |

> **Security**: never commit `.env` to version control. Rotate secrets if they are accidentally exposed.

---

## 2. Build and start containers

```bash
docker compose up --build -d
```

This will:

1. Build the backend image (installs Python deps; Alembic migrations run at container start).
2. Build the frontend image with `NEXT_PUBLIC_API_URL` baked into the static bundle.
3. Start `db`, then `backend` (after db is healthy), then `frontend` (after backend is healthy).

Check status:

```bash
docker compose ps
docker compose logs -f backend
```

---

## 3. Configure Caddy on the host

Create or edit `/etc/caddy/Caddyfile`:

```caddyfile
dora.example.com {
    # Frontend (Next.js) – serves all non-API routes
    handle /* {
        reverse_proxy localhost:3000
    }

    # Backend API – proxied under /api prefix
    handle /api/* {
        reverse_proxy localhost:8000
    }

    # Health endpoint (optional direct exposure)
    handle /health {
        reverse_proxy localhost:8000
    }

    # Standard TLS (Caddy auto-provisions Let's Encrypt certificates)
    tls your@email.com
}
```

Reload Caddy:

```bash
caddy reload --config /etc/caddy/Caddyfile
```

Caddy will obtain a TLS certificate automatically on first request.

---

## 4. Verify the deployment

```bash
# Backend health check
curl https://dora.example.com/health

# API smoke test
curl https://dora.example.com/api/health

# Frontend
open https://dora.example.com
```

---

## 5. Rebuilding after configuration changes

`NEXT_PUBLIC_API_URL` is baked into the Next.js bundle at **build time**. If you need to change the API URL:

```bash
# Update .env, then rebuild only the frontend
docker compose up --build -d frontend
```

For backend-only changes:

```bash
docker compose up --build -d backend
```

---

## 6. Backup

Back up the PostgreSQL data volume regularly:

```bash
docker exec dora-metrics-db-1 pg_dump -U dora dora_metrics \
  | gzip > backups/dora_metrics_$(date +%Y%m%d).sql.gz
```

Store backups off-host per your organisation's retention policy.

---

## 7. Updating

```bash
git pull
docker compose up --build -d
```

Alembic migrations run automatically when the backend container starts.

---

## Ports summary

| Service | Internal port | Host port (default) |
|---|---|---|
| PostgreSQL | 5432 | not exposed (internal only) |
| Backend (FastAPI) | 8000 | 8000 |
| Frontend (Next.js) | 3000 | 3000 |

Caddy binds to 80/443 on the host and proxies to these container ports.

The PostgreSQL port is **not published** to the host by default; it is only accessible within the `dora_net` Docker network.

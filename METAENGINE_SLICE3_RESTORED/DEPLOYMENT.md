# METAENGINE Phase 66 — Deployment Guide

## Quick Start

### Option 1: Docker Compose (recommended)

```bash
# Clone repository
git clone <repo-url>
cd METAENGINE_SLICE3_RESTORED

# Set environment variables
cp .env.example .env
# Edit .env with your TURSO_DB_TOKEN

# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f metaengine-api

# Stop
docker-compose down
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| metaengine-api | 8080 | MetaEngine REST API (11 endpoints) |
| llm-bridge | 3031 | LLM bridge (z-ai-web-dev-sdk) |
| dashboard | 3000 | Next.js web dashboard |
| gateway | 80 | Caddy reverse proxy |

### Option 2: Manual (without Docker)

```bash
# Terminal 1: Start LLM Bridge
cd mini-services/llm-bridge
bun run dev

# Terminal 2: Start MetaEngine API
cd METAENGINE_SLICE3_RESTORED
PYTHONPATH=. python -m metaengine.api_server --port 8080

# Terminal 3: Start Dashboard
cd /home/z/my-project
NODE_OPTIONS="--max-old-space-size=512" npx next dev -p 3000
```

### Option 3: API only (no dashboard)

```bash
cd METAENGINE_SLICE3_RESTORED
PYTHONPATH=. python -m metaengine.api_server --port 8080

# Test
curl http://localhost:8080/api/health
curl http://localhost:8080/api/constitution
curl http://localhost:8080/api/modules
```

## CI/CD Pipeline

GitHub Actions workflow at `.github/workflows/ci.yml`:

1. **Test**: Runs 1,517+ tests on push/PR
2. **Build**: Builds Docker images on version tags (v*)
3. **Deploy**: Deploys with docker-compose (production environment)

## Environment Variables

```env
# .env file
TURSO_DB_TOKEN=your_turso_token
TURSO_DB_HOST=metaengine-project-patrickfrome.aws-eu-west-1.turso.io
```

## Health Checks

All services have Docker health checks:

```bash
# API health
curl http://localhost:8080/api/health

# Bridge health
curl http://localhost:3031/health

# Dashboard health
curl http://localhost:3000
```

## Volumes

- `metaengine-storage`: Persistent storage for accumulated state, mechanism library, biographies

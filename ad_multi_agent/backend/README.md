# Film AD Multi-Agent (ADK)

Assistant Director orchestrator + 5 department agents backed by local Postgres.

## Architecture (Phase 1)

```text
User (adk web)
   → root_agent (resolve scene from DB)
      → production_workflow
         → parallel: weather | location | camera | stunt | cast
         → replan_agent (if any ready_for_shooting=false)
```

All department decisions are grounded in Postgres tools (ingested from `db/film_ad_dataset_v4.xlsx`).

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Docker Desktop (for local Postgres)
- GCP auth for Vertex AI (`gcloud auth application-default login`)

## 1. Start Postgres + ingest

```bash
cd backend/db
docker build -t film-ad-db .
docker run --name film-ad-db \
  -e POSTGRES_DB=film_ad \
  -e POSTGRES_USER=film_ad_user \
  -e POSTGRES_PASSWORD=film_ad_pass \
  -p 5432:5432 \
  -d film-ad-db

# wait a few seconds, then ingest from backend/
cd ..
uv sync
uv run python db/ingest.py
```

## 2. Configure Vertex AI

Edit `backend/.env` (see `.env.example`):

```bash
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_CLOUD_LOCATION=global
MODEL_NAME=gemini-2.5-flash
```

## 3. Run ADK Web

```bash
cd backend
uv sync
uv run adk web
```

Open the UI, select the **agents** app, then try:

- `Analyze SC01` — all 5 departments should pass
- `Analyze SC03` — camera blocked → replan agent runs
- `Analyze SC13` — weather blocked → replan agent runs

## Demo scenes

| Scene | Expected |
| --- | --- |
| SC01 | All READY |
| SC03 | Camera BLOCKED |
| SC05 | Cast BLOCKED |
| SC08 | Stunt BLOCKED |
| SC10 | Location BLOCKED |
| SC13 | Weather BLOCKED |

# 🎬 CineAI: Agentic Assistant Director & Production War Room

> **Zero Production Downtime: Multi-Agent Feasibility & Instant Replanning Grounded in Production Facts.**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK](https://img.shields.io/badge/Google-ADK%202.8+-orange.svg)](https://cloud.google.com/vertex-ai)
[![Gemini 2.5 Flash](https://img.shields.io/badge/Model-Gemini%202.5%20Flash-4285F4.svg)](https://deepmind.google/technologies/gemini/)
[![IBM Docling MCP](https://img.shields.io/badge/MCP-IBM%20Docling-black.svg)](https://github.com/DS4SD/docling)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-336791.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)

---

## 🌟 Overview

On a film set, every stalled hour costs tens of thousands of dollars. When weather turns, equipment fails inspection, or cast schedules clash, Assistant Directors (ADs) face the monumental task of manually cross-referencing permits, schedules, and gear to find an alternative shot.

**CineAI** is an autonomous **Agentic Assistant Director** that orchestrates production readiness in real-time. Grounded in a PostgreSQL production database, CineAI coordinates **five parallel department agents** and invokes an intelligent **Replan Agent** the moment a blocker is identified—computing viable contingency scenes and schedule swaps in milliseconds.

---

## 🏛️ System Architecture

```text
                                  ┌────────────────────────────────┐
                                  │   CineAI Production War Room   │
                                  │   (HTML5, Vanilla CSS, ES6)    │
                                  └───────────────┬────────────────┘
                                                  │ HTTP / Server-Sent Events (SSE)
                                                  ▼
                                  ┌────────────────────────────────┐
                                  │    FastAPI Bridge Server       │
                                  │     (`backend/server.py`)      │
                                  └───────┬────────────────┬───────┘
                                          │                │
                        ┌─────────────────┘                └─────────────────┐
                        ▼                                                    ▼
    ┌─────────────────────────────────────────┐            ┌─────────────────────────────────────────┐
    │          PostgreSQL Database            │            │       Google ADK Multi-Agent System      │
    │     (Docker: `film-ad-db` :5432)        │            │        (Vertex AI Gemini 2.5 Flash)      │
    ├─────────────────────────────────────────┤            ├─────────────────────────────────────────┤
    │ • scene_master                          │            │ • ad_multi_agent (Root Orchestrator)    │
    │ • scene_breakdown                       │            │   ├── IBM Docling MCP Toolset           │
    │ • location_master                       │            │   └── production_workflow               │
    │ • weather_readings & requirements       │            │       ├── Parallel Department Checks:   │
    │ • camera_schedule & plans               │            │       │   • weather_agent               │
    │ • stunt_catalog & safety_checklist      │            │       │   • location_agent              │
    │ • cast_directory & availability         │            │       │   • camera_agent                │
    │ • schedule & production_state           │            │       │   • stunt_agent                 │
    │                                         │            │       │   • cast_agent                  │
    └─────────────────────────────────────────┘            │       └── replan_agent (Contingency)    │
                                                           └─────────────────────────────────────────┘
```

---

## ✨ Key Features

### 1. 5 Parallel Department Agents
- 🌤️ **Weather Agent (`weather_agent`)**: Validates forecast rain probability, wind speed, and visibility against scene thresholds (e.g. golden hour exterior shoots).
- 📍 **Location Agent (`location_agent`)**: Verifies municipal permit approval status, operating hours, and access constraints.
- 🎥 **Camera Agent (`camera_agent`)**: Checks planned multi-camera and drone inventory availability and maintenance logs.
- 💥 **Stunt Agent (`stunt_agent`)**: Verifies required stunt safety checklist items (harnesses, crash mats, and medical team sign-offs).
- 👥 **Cast Agent (`cast_agent`)**: Confirms actor availability on scheduled shoot dates against call sheets.

### 2. Autonomous Replan Engine (`replan_agent`)
- When any department flags `ready_for_shooting: false`, the **Replan Agent** triggers automatically.
- Scans candidate scenes from the production DB avoiding the active blocker.
- Generates ranked alternative scenes with compatibility percentage scores (e.g. `90% Compatibility`), strategic rationale, and required schedule adjustments.
- Features an interactive **"Approve Swap"** action that updates call sheets and dispatches simulated crew notifications.

### 3. IBM Docling MCP Integration
- Connects **IBM Docling Document Understanding MCP Server** (`docling-mcp`) via Model Context Protocol stdio transport.
- Enables rich PDF parsing and structural understanding of multi-page screenplays, call sheets, and stunt safety riders.
- Optional **watsonx.data Document Library Retrieval MCP** for enterprise RAG.

### 4. Hollywood Production War Room Dashboard
- **Live 24 FPS SMPTE Timecode Ticker**: Digital timecode clock (`00:17:45:00`).
- **Interactive Multi-Agent Graph**: Visual execution graph showing live node states (`IDLE`, `RUNNING`, `PASS`, `FAIL`).
- **Department Telemetry Cards**: Gauges for weather, permit badges, gear inventory chips, and stunt checklist status.
- **Raw Agent JSON Drawer**: Toggleable inspection drawer on every department card showing the exact JSON schemas.
- **Live Agent Telemetry Console**: Slide-out drawer streaming real-time Gemini agent dialogs and function executions.
- **Dual Execution Engine**:
  - **⚡ Instant DB Ground Truth Mode**: Direct deterministic evaluation in `<50ms`.
  - **🤖 Live Multi-Agent Mode**: Server-Sent Events (SSE) streaming real Gemini 2.5 Flash agent reasoning.

---

## 🎯 Benchmark Demo Scenes

| Scene | Title | Location | Expected Result | Department Blocker |
| :--- | :--- | :--- | :--- | :--- |
| **SC01** | Beach Meet & Car Arrival | Marina Beach (EXT) | 🟢 **All READY** | None (All 5 departments pass) |
| **SC03** | Boss Office Meeting | Office Set (INT) | 🟡 **Replan Active** | 🎥 **Camera BLOCKED** (`CAM002` in maintenance) |
| **SC05** | Inspector Interrogation | Interrogation Room (INT) | 🟡 **Replan Active** | 👥 **Cast BLOCKED** (Actor unavailable) |
| **SC08** | Warehouse Fight | Abandoned Warehouse (INT) | 🔴 **Replan Active** | 💥 **Stunt BLOCKED** (Unconfirmed safety items) |
| **SC10** | Train Departure | Central Station (EXT) | 🔴 **Replan Active** | 📍 **Location BLOCKED** (Permit pending approval) |
| **SC13** | Rainy Street Goodbye | City Street Rain Rig (EXT) | 🔵 **Replan Active** | 🌤️ **Weather BLOCKED** (Wind/rain threshold exceeded) |

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.13+** with [`uv`](https://github.com/astral-sh/uv)
- **Docker** (for local PostgreSQL)
- **GCP Vertex AI credentials** (`gcloud auth application-default login`)

---

### Step 1: Clone Repository & Start Database

```bash
# 1. Clone repo
git clone https://github.com/your-username/ad_multi_agent.git
cd ad_multi_agent

# 2. Build & run the Postgres database container
cd backend/db
docker build -t film-ad-db .
docker run --name film-ad-db \
  -e POSTGRES_DB=film_ad \
  -e POSTGRES_USER=film_ad_user \
  -e POSTGRES_PASSWORD=film_ad_pass \
  -p 5432:5432 \
  -d film-ad-db

# 3. Ingest production dataset into Postgres
cd ..
uv sync
uv run python db/ingest.py
```

---

### Step 2: Configure Environment

Create or edit `backend/.env`:

```env
# Postgres Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=film_ad
POSTGRES_USER=film_ad_user
POSTGRES_PASSWORD=film_ad_pass

# Google Cloud Vertex AI
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=global
MODEL_NAME=gemini-2.5-flash

# Features
ENABLE_REPLAN_ON_FAILURE=true
USE_DOCLING_MCP=true
```

---

### Step 3: Launch CineAI Production Server

```bash
# From backend/ directory
PORT=8088 uv run python server.py
```

Open your browser and navigate to:
👉 **`http://localhost:8088/`**

---

## 📡 API Reference

### `GET /api/scenes`
Lists all scenes in the production database enriched with demo tags and current schedules.

### `GET /api/scenes/{scene_id}`
Returns complete scene bundle from PostgreSQL (location specs, camera plan, stunt catalog, cast mapping, and weather requirements).

### `POST /api/analyze`
Executes multi-department readiness assessment and contingency replanning.

**Request Body:**
```json
{
  "scene_id": "SC01",
  "mode": "fast" // "fast" (direct DB facts <50ms) or "agent" (streaming ADK agent)
}
```

**Response (Sample SC01 All Ready):**
```json
{
  "scene_id": "SC01",
  "all_departments_ready": true,
  "overall_status": "READY_TO_SHOOT",
  "failed_departments": [],
  "departments": {
    "weather": { "status": "READY", "ready_for_shooting": true, "reason": "Weather reading is within required thresholds." },
    "location": { "status": "READY", "ready_for_shooting": true, "reason": "Location 'Marina Beach' is feasible." },
    "camera": { "status": "READY", "ready_for_shooting": true, "reason": "All planned cameras are available." },
    "stunt": { "status": "READY", "ready_for_shooting": true, "reason": "No stunt requirements for this scene." },
    "cast": { "status": "READY", "ready_for_shooting": true, "reason": "All mapped cast members are available." }
  },
  "replan": null
}
```

### `POST /api/replan/apply`
Simulates approving an alternative scene swap and dispatching call sheet notices.

**Request Body:**
```json
{
  "blocked_scene_id": "SC03",
  "target_scene_id": "SC01",
  "reason": "Assistant Director approved schedule swap"
}
```

---

## 📁 Repository Structure

```text
ad_multi_agent/
├── README.md                           # Master project documentation
├── backend/
│   ├── server.py                       # FastAPI REST & SSE bridge server
│   ├── pyproject.toml                  # Python dependencies (uv)
│   ├── .env                            # Environment configuration
│   ├── agents/                         # Google ADK multi-agent package
│   │   ├── agent.py                    # Orchestrator & ProductionWorkflow definitions
│   │   ├── prompts/                    # Prompts for root, replan, and 5 departments
│   │   ├── tools/                      # Postgres DB query tools
│   │   └── mcp/                        # IBM Docling & watsonx MCP toolsets
│   ├── db/                             # Database initialization & dataset
│   │   ├── 001_schema.sql              # Relational production schema
│   │   ├── film_ad_dataset_v4.xlsx     # Ground truth production dataset
│   │   └── ingest.py                   # Excel to Postgres ingestion script
│   └── static/                         # Production War Room Frontend
│       ├── index.html                  # Mission Control HTML5 dashboard
│       ├── style.css                   # Dark glassmorphism design system
│       └── app.js                      # Reactive ES6 application controller
```

---

## 👥 Contributors & Acknowledgements
Built for the Agentic Hackathon utilizing:
- **Google DeepMind & Vertex AI** for Gemini 2.5 Flash and Google ADK
- **IBM Research** for the Docling Document Understanding MCP Server
- **PostgreSQL Global Development Group**

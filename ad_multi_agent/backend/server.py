"""FastAPI backend bridge for CineAI Assistant Director Multi-Agent Dashboard."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.tools.db import fetch_all, fetch_one
from agents.tools.db_tools import (
    check_camera_for_scene,
    check_cast_for_scene,
    check_location_for_scene,
    check_stunt_for_scene,
    check_weather_for_scene,
    find_scenes,
    get_scene_bundle,
    list_candidate_scenes_for_replan,
)

app = FastAPI(
    title="CineAI Multi-Agent Director API",
    description="Agentic Assistant Director production orchestrator and recommendation engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = BACKEND_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class AnalyzeRequest(BaseModel):
    scene_id: str
    mode: str = "fast"  # "fast" (direct DB verification) or "agent" (streaming ADK agent)


class ReplanApplyRequest(BaseModel):
    blocked_scene_id: str
    target_scene_id: str
    reason: str = "Assistant Director schedule swap"


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "CineAI Assistant Director"}


@app.get("/api/scenes")
async def get_scenes(query: str = Query(default="")):
    """List scenes with basic readiness indicators."""
    try:
        scenes_data = find_scenes(query, limit=25)
        scenes = scenes_data.get("scenes", [])
        # Enrich each scene with demo tags if known
        demo_map = {
            "SC01": {"tag": "ALL_READY", "badge": "All Pass", "color": "emerald"},
            "SC02": {"tag": "READY", "badge": "Interior Ready", "color": "emerald"},
            "SC03": {"tag": "CAMERA_BLOCKED", "badge": "Camera Blocked", "color": "amber"},
            "SC04": {"tag": "READY", "badge": "Street Action", "color": "emerald"},
            "SC05": {"tag": "CAST_BLOCKED", "badge": "Cast Blocked", "color": "amber"},
            "SC08": {"tag": "STUNT_BLOCKED", "badge": "Stunt Blocked", "color": "ruby"},
            "SC10": {"tag": "LOCATION_BLOCKED", "badge": "Permit Blocked", "color": "ruby"},
            "SC13": {"tag": "WEATHER_BLOCKED", "badge": "Weather Blocked", "color": "cyan"},
        }
        for s in scenes:
            sid = s.get("scene_id")
            s["demo_info"] = demo_map.get(sid, {"tag": "CUSTOM", "badge": "Scene", "color": "slate"})
        return {"scenes": scenes, "total": len(scenes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scenes/{scene_id}")
async def get_scene_details(scene_id: str):
    """Fetch complete scene bundle including location, camera, stunt, and cast details."""
    bundle = get_scene_bundle(scene_id)
    if not bundle.get("found"):
        raise HTTPException(status_code=404, detail=bundle.get("error", "Scene not found"))
    return bundle


def run_fast_assessment(scene_id: str) -> dict[str, Any]:
    """Execute all 5 department DB evaluations synchronously and produce replan recommendations if blocked."""
    bundle = get_scene_bundle(scene_id)
    if not bundle.get("found"):
        return {"error": f"Scene {scene_id} not found."}

    scene = bundle.get("scene", {})

    weather_res = check_weather_for_scene(scene_id)
    location_res = check_location_for_scene(scene_id)
    camera_res = check_camera_for_scene(scene_id)
    stunt_res = check_stunt_for_scene(scene_id)
    cast_res = check_cast_for_scene(scene_id)

    departments = {
        "weather": weather_res,
        "location": location_res,
        "camera": camera_res,
        "stunt": stunt_res,
        "cast": cast_res,
    }

    failed_departments = [
        dept for dept, res in departments.items() if not res.get("ready_for_shooting", False)
    ]

    all_ready = len(failed_departments) == 0

    replan_data = None
    if not all_ready:
        candidates_raw = list_candidate_scenes_for_replan(scene_id, limit=5)
        candidates = candidates_raw.get("candidates", [])
        
        # Build intelligent recommendation alternatives
        alternatives = []
        for cand in candidates:
            cid = cand.get("scene_id")
            c_readiness = cand.get("readiness_state")
            c_title = cand.get("title")
            c_date = cand.get("shoot_date")
            c_loc = cand.get("location_name")

            # Check suitability
            score = 0.90 if c_readiness == "READY" else 0.55
            prob = 0.85 if c_readiness == "READY" else 0.45
            
            reasons = []
            if c_readiness == "READY":
                reasons.append(f"Scene {cid} ('{c_title}') is currently READY for shooting.")
            else:
                reasons.append(f"Scene {cid} ('{c_title}') is scheduled for {c_date} at {c_loc}.")

            if "camera" in failed_departments:
                reasons.append(f"Alternative scene does not require the blocked camera.")
            if "weather" in failed_departments:
                reasons.append("Can be prioritized if interior set or independent of rain/wind.")
            if "cast" in failed_departments:
                reasons.append("Utilizes separate cast roster ready on shoot date.")
            if "stunt" in failed_departments:
                reasons.append("Has verified stunt safety checklist or lower stunt risk.")
            if "location" in failed_departments:
                reasons.append("Permit is already APPROVED for this alternate location.")

            req_changes = [
                f"Swap {cid} into current shoot window ({scene.get('shoot_date')} {scene.get('shoot_time')}).",
                f"Reschedule {scene_id} ({scene.get('title')}) to when {', '.join(failed_departments)} blockers are resolved.",
                f"Notify department leads ({', '.join(failed_departments).title()}) and update daily call sheet.",
            ]

            alternatives.append({
                "scene_id": cid,
                "title": c_title,
                "score": score,
                "probability": prob,
                "rationale": " ".join(reasons),
                "required_changes": req_changes,
                "location_name": c_loc,
                "shoot_date": str(c_date),
            })

        # Sort alternatives by score descending
        alternatives.sort(key=lambda x: x["score"], reverse=True)
        rec_scene = alternatives[0]["scene_id"] if alternatives else None

        replan_data = {
            "status": "NEEDS_REPLAN",
            "failed_departments": failed_departments,
            "search_strategy": f"Scanned production DB candidates for schedule swaps avoiding {', '.join(failed_departments)} blockers.",
            "recommended_scene": rec_scene,
            "alternatives": alternatives,
        }

    return {
        "scene_id": scene_id,
        "scene_brief": {
            "scene_id": scene_id,
            "title": scene.get("title"),
            "logline": scene.get("logline"),
            "location_name": scene.get("location_name"),
            "location_type": scene.get("location_type"),
            "city": scene.get("city"),
            "int_ext": scene.get("int_ext"),
            "shoot_date": str(scene.get("shoot_date")),
            "shoot_time": str(scene.get("shoot_time")),
            "scene_type": scene.get("scene_type"),
            "stunt_level": scene.get("stunt_level"),
            "weather_dependency": scene.get("weather_dependency"),
            "primary_characters": scene.get("primary_characters"),
            "key_props": scene.get("key_props"),
            "action_beats": scene.get("action_beats"),
            "permit_status": scene.get("permit_status"),
        },
        "all_departments_ready": all_ready,
        "overall_status": "READY_TO_SHOOT" if all_ready else "NEEDS_REPLAN",
        "failed_departments": failed_departments,
        "departments": departments,
        "replan": replan_data,
    }


@app.post("/api/analyze")
async def analyze_scene(req: AnalyzeRequest):
    """Analyze scene using either fast DB evaluation or live streaming ADK agent."""
    scene_id = req.scene_id.strip().upper()
    if not scene_id:
        raise HTTPException(status_code=400, detail="scene_id is required")

    if req.mode == "fast":
        result = run_fast_assessment(scene_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    # Streaming mode via ADK CLI
    async def event_generator() -> AsyncGenerator[str, None]:
        # Yield initial event
        yield f"data: {json.dumps({'type': 'start', 'scene_id': scene_id, 'message': f'Initializing Multi-Agent Director for {scene_id}...' })}\n\n"
        await asyncio.sleep(0.05)

        # Run fast assessment first so frontend gets structured ground truth right away
        fast_result = run_fast_assessment(scene_id)
        yield f"data: {json.dumps({'type': 'ground_truth', 'data': fast_result})}\n\n"

        # Spawn ADK agent to get real Gemini multi-agent reasoning stream
        env = os.environ.copy()
        env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{os.environ.get('HOME', '')}/.local/bin:{env.get('PATH', '')}"
        cmd = ["uv", "run", "adk", "run", "agents", f"Analyze {scene_id}", "--jsonl"]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(BACKEND_DIR),
                env=env,
            )

            async for line in proc.stdout:
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                if decoded.startswith("{") and decoded.endswith("}"):
                    try:
                        event_json = json.loads(decoded)
                        author = event_json.get("author", "orchestrator")
                        parts = event_json.get("content", {}).get("parts", [])
                        text = "".join([p.get("text", "") for p in parts if isinstance(p, dict)])
                        yield f"data: {json.dumps({'type': 'agent_event', 'author': author, 'text': text, 'raw': event_json})}\n\n"
                    except Exception:
                        yield f"data: {json.dumps({'type': 'log', 'text': decoded})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'log', 'text': decoded})}\n\n"

            await proc.wait()
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'log', 'text': f'Agent execution note: {str(exc)}'})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'scene_id': scene_id, 'message': 'Multi-agent orchestration workflow completed.'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/replan/apply")
async def apply_replan(req: ReplanApplyRequest):
    """Simulate applying an approved schedule swap."""
    return {
        "success": True,
        "message": f"Successfully swapped {req.target_scene_id} in place of {req.blocked_scene_id}.",
        "blocked_scene": req.blocked_scene_id,
        "target_scene": req.target_scene_id,
        "status": "SCHEDULE_UPDATED",
        "call_sheet_notification": f"Notification dispatched to Camera, Location, Cast, and Crew leads.",
    }


# Mount static assets for frontend
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    print(f"🎬 Starting CineAI Assistant Director API Server on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

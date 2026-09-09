"""Postgres-backed tools used by department agents.

Every tool returns a JSON-serializable dict so Gemini can reason over DB facts
without inventing inventory, permits, weather, or cast availability.
"""

from __future__ import annotations

from typing import Any

from .db import fetch_all, fetch_one


def _split_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _blocked(
    department: str,
    reason: str,
    *,
    missing_items: list[str] | None = None,
    expected_items: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "department": department,
        "status": "BLOCKED",
        "ready_for_shooting": False,
        "reason": reason,
        "missing_items": missing_items or [],
        "expected_items": expected_items or [],
        "metadata": metadata or {},
    }


def _ready(
    department: str,
    reason: str = "",
    *,
    expected_items: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "department": department,
        "status": "READY",
        "ready_for_shooting": True,
        "reason": reason,
        "missing_items": [],
        "expected_items": expected_items or [],
        "metadata": metadata or {},
    }


def get_scene_bundle(scene_id: str) -> dict[str, Any]:
    """Load scene master + breakdown + location for a scene_id (e.g. SC01)."""
    scene = fetch_one(
        """
        SELECT s.*, b.primary_characters, b.extras_estimate, b.vehicles, b.key_props,
               b.action_beats, b.stunt_level, b.camera_style, b.weather_dependency,
               b.department_notes_camera, b.department_notes_stunt, b.department_notes_art,
               l.location_type, l.city, l.permit_required, l.permit_status,
               l.operating_hours, l.noise_profile, l.access_constraints
        FROM scene_master s
        LEFT JOIN scene_breakdown b ON b.scene_id = s.scene_id
        LEFT JOIN location_master l ON l.location_id = s.location_id
        WHERE UPPER(s.scene_id) = UPPER(%s)
        """,
        (scene_id.strip(),),
    )
    if not scene:
        return {
            "found": False,
            "scene_id": scene_id,
            "error": f"Scene '{scene_id}' not found in production DB.",
        }
    return {"found": True, "scene": scene}


def find_scenes(query: str = "", limit: int = 10) -> dict[str, Any]:
    """Search scenes by id, title, location, or logline keywords."""
    limit = max(1, min(int(limit), 25))
    q = (query or "").strip()
    if not q:
        rows = fetch_all(
            """
            SELECT scene_id, title, location_name, shoot_date, shoot_time, int_ext, scene_type
            FROM scene_master
            ORDER BY shoot_date, shoot_time
            LIMIT %s
            """,
            (limit,),
        )
        return {"count": len(rows), "scenes": rows}

    like = f"%{q}%"
    rows = fetch_all(
        """
        SELECT scene_id, title, location_name, shoot_date, shoot_time, int_ext, scene_type, logline
        FROM scene_master
        WHERE scene_id ILIKE %s
           OR title ILIKE %s
           OR location_name ILIKE %s
           OR COALESCE(logline, '') ILIKE %s
        ORDER BY shoot_date, shoot_time
        LIMIT %s
        """,
        (like, like, like, like, limit),
    )
    return {"count": len(rows), "scenes": rows, "query": q}


def check_weather_for_scene(scene_id: str) -> dict[str, Any]:
    """Compare stored weather readings against scene weather requirements."""
    scene = fetch_one(
        "SELECT scene_id, int_ext, shoot_date, location_id FROM scene_master WHERE UPPER(scene_id)=UPPER(%s)",
        (scene_id,),
    )
    if not scene:
        return _blocked("weather", f"Scene '{scene_id}' not found.", metadata={"scene_id": scene_id})

    req = fetch_one(
        "SELECT * FROM weather_requirements WHERE UPPER(scene_id)=UPPER(%s)",
        (scene_id,),
    )
    reading = fetch_one(
        """
        SELECT * FROM weather_readings
        WHERE UPPER(scene_id)=UPPER(%s)
        ORDER BY \"timestamp\" DESC
        LIMIT 1
        """,
        (scene_id,),
    )

    if not req:
        return _ready(
            "weather",
            "No outdoor weather requirements for this scene.",
            expected_items=["weather_dependency=N/A"],
            metadata={"scene_id": scene["scene_id"], "int_ext": scene.get("int_ext")},
        )

    if not reading:
        return _blocked(
            "weather",
            "No weather reading found for the scheduled shoot window.",
            missing_items=["weather_reading"],
            expected_items=[
                f"rain_probability<={req.get('max_rain_probability')}",
                f"wind_speed<={req.get('max_wind_kmh')}kmh",
            ],
            metadata={"scene_id": scene["scene_id"], "requirements": req},
        )

    missing: list[str] = []
    max_rain = req.get("max_rain_probability")
    max_wind = req.get("max_wind_kmh")
    rain = reading.get("rain_probability")
    wind = reading.get("wind_speed_kmh")

    if max_rain is not None and rain is not None and float(rain) > float(max_rain):
        missing.append(f"rain_probability<={max_rain} (actual {rain})")
    if max_wind is not None and wind is not None and float(wind) > float(max_wind):
        missing.append(f"wind_speed<={max_wind}kmh (actual {wind})")

    meta = {
        "scene_id": scene["scene_id"],
        "rain_probability": rain,
        "wind_speed_kmh": wind,
        "visibility_km": reading.get("visibility_km"),
        "threshold_rain": max_rain,
        "threshold_wind": max_wind,
        "notes": req.get("notes"),
    }
    expected = [
        f"rain_probability<={max_rain}",
        f"wind_speed<={max_wind}kmh",
    ]
    if missing:
        return _blocked(
            "weather",
            "Weather conditions exceed safe thresholds for this scene.",
            missing_items=missing,
            expected_items=expected,
            metadata=meta,
        )
    return _ready(
        "weather",
        "Weather reading is within required thresholds.",
        expected_items=expected,
        metadata=meta,
    )


def check_location_for_scene(scene_id: str) -> dict[str, Any]:
    """Validate permit status and basic location feasibility from the DB."""
    scene = fetch_one(
        """
        SELECT s.scene_id, s.location_id, s.location_name, s.shoot_time,
               l.permit_required, l.permit_status, l.operating_hours,
               l.access_constraints, l.noise_profile, l.location_type, l.city
        FROM scene_master s
        JOIN location_master l ON l.location_id = s.location_id
        WHERE UPPER(s.scene_id)=UPPER(%s)
        """,
        (scene_id,),
    )
    if not scene:
        return _blocked("location", f"Scene or location for '{scene_id}' not found.")

    missing: list[str] = []
    expected = ["location resolved"]
    permit_required = bool(scene.get("permit_required"))
    permit_status = (scene.get("permit_status") or "").upper()

    if permit_required:
        expected.append("permit_status=APPROVED")
        if permit_status != "APPROVED":
            missing.append(f"Permit approved for {scene['location_id']}")

    meta = {
        "location_id": scene["location_id"],
        "location_name": scene.get("location_name"),
        "permit_required": permit_required,
        "permit_status": scene.get("permit_status"),
        "operating_hours": scene.get("operating_hours"),
        "shoot_time": scene.get("shoot_time"),
        "access_constraints": scene.get("access_constraints"),
    }
    if missing:
        return _blocked(
            "location",
            f"Location '{scene.get('location_name')}' is not production-ready.",
            missing_items=missing,
            expected_items=expected,
            metadata=meta,
        )
    return _ready(
        "location",
        f"Location '{scene.get('location_name')}' is feasible.",
        expected_items=expected + (["permit_status=APPROVED"] if permit_required else []),
        metadata=meta,
    )


def check_camera_for_scene(scene_id: str) -> dict[str, Any]:
    """Validate planned cameras are AVAILABLE on the scene shoot date."""
    scene = fetch_one(
        "SELECT scene_id, shoot_date FROM scene_master WHERE UPPER(scene_id)=UPPER(%s)",
        (scene_id,),
    )
    if not scene:
        return _blocked("camera", f"Scene '{scene_id}' not found.")

    plan = fetch_one(
        "SELECT * FROM scene_camera_plan WHERE UPPER(scene_id)=UPPER(%s)",
        (scene_id,),
    )
    if not plan or not plan.get("camera_ids"):
        return _blocked(
            "camera",
            "No camera plan found for this scene.",
            missing_items=["scene_camera_plan"],
            metadata={"scene_id": scene["scene_id"]},
        )

    camera_ids = _split_ids(plan.get("camera_ids"))
    shoot_date = scene["shoot_date"]
    missing: list[str] = []
    camera_statuses: list[dict[str, Any]] = []

    for cam_id in camera_ids:
        row = fetch_one(
            """
            SELECT camera_id, status, notes
            FROM camera_schedule
            WHERE camera_id = %s AND date = %s
            """,
            (cam_id, shoot_date),
        )
        if not row:
            missing.append(f"{cam_id} scheduled/available on {shoot_date}")
            camera_statuses.append({"camera_id": cam_id, "status": "MISSING_SCHEDULE"})
            continue
        camera_statuses.append(row)
        if (row.get("status") or "").upper() != "AVAILABLE":
            missing.append(f"{cam_id} available on {shoot_date}")

    meta = {
        "camera_setup_id": plan.get("camera_setup_id"),
        "cameras": camera_ids,
        "date": shoot_date,
        "camera_statuses": camera_statuses,
        "notes": plan.get("notes"),
    }
    expected = [f"{c} available" for c in camera_ids]
    if missing:
        return _blocked(
            "camera",
            "One or more required cameras are unavailable on the shoot date.",
            missing_items=missing,
            expected_items=expected,
            metadata=meta,
        )
    return _ready(
        "camera",
        "All planned cameras are available.",
        expected_items=expected,
        metadata=meta,
    )


def check_stunt_for_scene(scene_id: str) -> dict[str, Any]:
    """Validate stunt plan + required safety checklist confirmations."""
    scene = fetch_one(
        "SELECT scene_id FROM scene_master WHERE UPPER(scene_id)=UPPER(%s)",
        (scene_id,),
    )
    if not scene:
        return _blocked("stunt", f"Scene '{scene_id}' not found.")

    plan = fetch_one(
        """
        SELECT p.*, c.name, c.risk_level, c.requires_harness, c.requires_crash_mats,
               c.requires_medical, c.description
        FROM scene_stunt_plan p
        LEFT JOIN stunt_catalog c ON c.stunt_id = p.stunt_id
        WHERE UPPER(p.scene_id)=UPPER(%s)
        """,
        (scene_id,),
    )
    if not plan:
        return _ready(
            "stunt",
            "No stunt requirements for this scene.",
            expected_items=["stunt_level=NONE"],
            metadata={"scene_id": scene["scene_id"]},
        )

    checklist = fetch_all(
        """
        SELECT checklist_id, item, required, confirmed, confirmed_by, notes
        FROM stunt_safety_checklist
        WHERE UPPER(scene_id)=UPPER(%s)
        ORDER BY checklist_id
        """,
        (scene_id,),
    )
    missing = [
        f"{item['item']} confirmed"
        for item in checklist
        if item.get("required") and not item.get("confirmed")
    ]
    meta = {
        "stunt_id": plan.get("stunt_id"),
        "stunt_plan_id": plan.get("stunt_plan_id"),
        "risk_level": plan.get("risk_level"),
        "name": plan.get("name"),
        "checklist": checklist,
        "notes": plan.get("notes"),
    }
    expected = [f"{item['item']} confirmed" for item in checklist if item.get("required")]
    if missing:
        return _blocked(
            "stunt",
            "Required stunt safety items are not confirmed.",
            missing_items=missing,
            expected_items=expected,
            metadata=meta,
        )
    return _ready(
        "stunt",
        "Stunt plan and required safety checklist are confirmed.",
        expected_items=expected or ["safety checklist complete"],
        metadata=meta,
    )


def check_cast_for_scene(scene_id: str) -> dict[str, Any]:
    """Validate mapped cast members are available on the shoot date."""
    scene = fetch_one(
        "SELECT scene_id, shoot_date FROM scene_master WHERE UPPER(scene_id)=UPPER(%s)",
        (scene_id,),
    )
    if not scene:
        return _blocked("cast", f"Scene '{scene_id}' not found.")

    mapped = fetch_all(
        """
        SELECT m.cast_id, m.role_on_call_sheet, d.name, d.role_name,
               a.availability
        FROM scene_cast_map m
        JOIN cast_directory d ON d.cast_id = m.cast_id
        LEFT JOIN cast_availability a
          ON a.cast_id = m.cast_id AND a.date = %s
        WHERE UPPER(m.scene_id)=UPPER(%s)
        ORDER BY m.cast_id
        """,
        (scene["shoot_date"], scene_id),
    )
    if not mapped:
        return _blocked(
            "cast",
            "No cast mapped to this scene.",
            missing_items=["scene_cast_map"],
            metadata={"scene_id": scene["scene_id"]},
        )

    availability: dict[str, bool] = {}
    missing: list[str] = []
    for row in mapped:
        cast_id = row["cast_id"]
        status = (row.get("availability") or "").upper()
        ok = status in {"FULL_DAY", "HALF_DAY"}
        availability[cast_id] = ok
        label = f"{row.get('name') or cast_id} ({cast_id})"
        if not ok:
            missing.append(f"{label} available on {scene['shoot_date']}")

    meta = {
        "scene_id": scene["scene_id"],
        "date": scene["shoot_date"],
        "cast": mapped,
        "cast_members_availability": availability,
    }
    expected = [f"{row['cast_id']} available" for row in mapped]
    if missing:
        return _blocked(
            "cast",
            "One or more required cast members are unavailable.",
            missing_items=missing,
            expected_items=expected,
            metadata=meta,
        )
    return _ready(
        "cast",
        "All mapped cast members are available.",
        expected_items=expected,
        metadata=meta,
    )


def list_candidate_scenes_for_replan(
    blocked_scene_id: str,
    limit: int = 5,
) -> dict[str, Any]:
    """List other scheduled scenes that can be considered during replanning."""
    limit = max(1, min(int(limit), 10))
    blocked = fetch_one(
        """
        SELECT s.scene_id, s.title, s.shoot_date, s.location_id,
               p.readiness_state, p.overall_status, p.blocking_department
        FROM scene_master s
        LEFT JOIN production_state p ON p.scene_id = s.scene_id
        WHERE UPPER(s.scene_id)=UPPER(%s)
        """,
        (blocked_scene_id,),
    )
    candidates = fetch_all(
        """
        SELECT s.scene_id, s.title, s.shoot_date, s.shoot_time, s.location_name,
               p.readiness_state, p.overall_status, sch.slot_order, sch.status AS schedule_status
        FROM scene_master s
        LEFT JOIN production_state p ON p.scene_id = s.scene_id
        LEFT JOIN schedule sch ON sch.scene_id = s.scene_id
        WHERE UPPER(s.scene_id) <> UPPER(%s)
        ORDER BY
          CASE WHEN p.readiness_state = 'READY' THEN 0 ELSE 1 END,
          sch.slot_order NULLS LAST,
          s.shoot_date,
          s.shoot_time
        LIMIT %s
        """,
        (blocked_scene_id, limit),
    )
    return {
        "blocked_scene": blocked,
        "candidates": candidates,
        "count": len(candidates),
    }

#!/usr/bin/env python3
"""
ingest.py — Loads film_ad_dataset_v4.xlsx into PostgreSQL.

Run standalone:  python ingest.py
Run in Docker:   invoked by entrypoint.sh on container start, after
                 the DB is confirmed reachable and the schema is applied.

Idempotent: uses upsert (ON CONFLICT DO UPDATE) so re-running the
ingestion (e.g. container restart) does not create duplicates or fail.
"""

import os
import sys
import time
import json
import logging

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ingest] %(message)s")
log = logging.getLogger(__name__)

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "film_ad")
DB_USER = os.getenv("POSTGRES_USER", "film_ad_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "film_ad_pass")

_DEFAULT_DATASET = os.path.join(os.path.dirname(__file__), "film_ad_dataset_v4.xlsx")
DATASET_PATH = os.getenv("DATASET_PATH", _DEFAULT_DATASET)

CONN_KWARGS = dict(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS)


def wait_for_db(max_retries=30, delay=2):
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(**CONN_KWARGS)
            conn.close()
            log.info("Postgres is reachable (attempt %d).", attempt)
            return
        except psycopg2.OperationalError as e:
            log.info("Postgres not ready yet (attempt %d/%d): %s", attempt, max_retries, e)
            time.sleep(delay)
    raise RuntimeError(f"Postgres not reachable after {max_retries} retries")


def nz(v):
    """Normalize pandas NaN / NaT to None for psycopg2."""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def load_sheet(xl, sheet):
    df = xl.parse(sheet)
    return df.where(pd.notnull(df), None)


def upsert(cur, table, columns, rows, conflict_cols):
    if not rows:
        return
    update_cols = [c for c in columns if c not in conflict_cols]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols) or columns[0]
    sql = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES %s
        ON CONFLICT ({", ".join(conflict_cols)})
        DO UPDATE SET {set_clause}
    """
    execute_values(cur, sql, rows)


def ingest(xl_path=DATASET_PATH):
    xl = pd.ExcelFile(xl_path)
    conn = psycopg2.connect(**CONN_KWARGS)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # --- scene_master ---
        df = load_sheet(xl, "scene_master")
        rows = [tuple(nz(v) for v in r) for r in df[
            ["scene_id","project_id","title","logline","int_ext","location_id",
             "location_name","shoot_date","shoot_time","day_night","unit","scene_type"]
        ].itertuples(index=False, name=None)]
        upsert(cur, "scene_master",
               ["scene_id","project_id","title","logline","int_ext","location_id",
                "location_name","shoot_date","shoot_time","day_night","unit","scene_type"],
               rows, ["scene_id"])
        log.info("scene_master: %d rows", len(rows))

        # --- location_master (must precede scene_breakdown FK-free, but weather_readings FK needs it) ---
        df = load_sheet(xl, "location_master")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "location_master",
               ["location_id","location_name","location_type","city","permit_required",
                "permit_status","operating_hours","noise_profile","access_constraints"],
               rows, ["location_id"])
        log.info("location_master: %d rows", len(rows))

        # --- scene_breakdown ---
        df = load_sheet(xl, "scene_breakdown")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "scene_breakdown",
               ["scene_id","primary_characters","extras_estimate","vehicles","key_props",
                "action_beats","stunt_level","camera_style","weather_dependency",
                "department_notes_camera","department_notes_stunt","department_notes_art"],
               rows, ["scene_id"])
        log.info("scene_breakdown: %d rows", len(rows))

        # --- weather_requirements ---
        df = load_sheet(xl, "weather_requirements")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "weather_requirements",
               ["scene_id","max_rain_probability","max_wind_kmh","notes"],
               rows, ["scene_id"])
        log.info("weather_requirements: %d rows", len(rows))

        # --- weather_readings ---
        df = load_sheet(xl, "weather_readings")
        cur.execute("DELETE FROM weather_readings")  # simple table, full refresh
        rows = [tuple(nz(v) for v in r) for r in df[
            ["scene_id","timestamp","location_id","rain_probability","wind_speed_kmh","visibility_km"]
        ].itertuples(index=False, name=None)]
        if rows:
            execute_values(cur,
                "INSERT INTO weather_readings (scene_id, \"timestamp\", location_id, rain_probability, wind_speed_kmh, visibility_km) VALUES %s",
                rows)
        log.info("weather_readings: %d rows", len(rows))

        # --- camera_inventory ---
        df = load_sheet(xl, "camera_inventory")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "camera_inventory",
               ["camera_id","label","type","model","owner_department","notes"],
               rows, ["camera_id"])
        log.info("camera_inventory: %d rows", len(rows))

        # --- camera_schedule ---
        df = load_sheet(xl, "camera_schedule")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "camera_schedule",
               ["camera_id","date","status","notes"],
               rows, ["camera_id","date"])
        log.info("camera_schedule: %d rows", len(rows))

        # --- scene_camera_plan ---
        df = load_sheet(xl, "scene_camera_plan")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "scene_camera_plan",
               ["scene_id","camera_setup_id","camera_ids","notes"],
               rows, ["scene_id"])
        log.info("scene_camera_plan: %d rows", len(rows))

        # --- stunt_catalog ---
        df = load_sheet(xl, "stunt_catalog")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "stunt_catalog",
               ["stunt_id","name","risk_level","description","requires_harness",
                "requires_crash_mats","requires_medical"],
               rows, ["stunt_id"])
        log.info("stunt_catalog: %d rows", len(rows))

        # --- scene_stunt_plan ---
        df = load_sheet(xl, "scene_stunt_plan")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "scene_stunt_plan",
               ["scene_id","stunt_id","stunt_plan_id","notes"],
               rows, ["scene_id"])
        log.info("scene_stunt_plan: %d rows", len(rows))

        # --- stunt_safety_checklist ---
        df = load_sheet(xl, "stunt_safety_checklist")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "stunt_safety_checklist",
               ["checklist_id","scene_id","stunt_plan_id","item","required",
                "confirmed","confirmed_by","notes"],
               rows, ["checklist_id"])
        log.info("stunt_safety_checklist: %d rows", len(rows))

        # --- cast_directory ---
        df = load_sheet(xl, "cast_directory")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "cast_directory",
               ["cast_id","name","role_name","gender","union_status","primary_contact"],
               rows, ["cast_id"])
        log.info("cast_directory: %d rows", len(rows))

        # --- cast_availability ---
        df = load_sheet(xl, "cast_availability")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "cast_availability",
               ["cast_id","date","availability"],
               rows, ["cast_id","date"])
        log.info("cast_availability: %d rows", len(rows))

        # --- scene_cast_map ---
        df = load_sheet(xl, "scene_cast_map")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "scene_cast_map",
               ["scene_id","cast_id","role_on_call_sheet"],
               rows, ["scene_id","cast_id"])
        log.info("scene_cast_map: %d rows", len(rows))

        # --- crew_directory ---
        df = load_sheet(xl, "crew_directory")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "crew_directory",
               ["crew_id","name","role","department","email","shift"],
               rows, ["crew_id"])
        log.info("crew_directory: %d rows", len(rows))

        # --- schedule ---
        df = load_sheet(xl, "schedule")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "schedule",
               ["schedule_id","scene_id","shoot_date","planned_start","planned_end",
                "slot_order","location_id","status","notes"],
               rows, ["schedule_id"])
        log.info("schedule: %d rows", len(rows))

        # --- agent_results (reference snapshot; metadata column parsed to JSON) ---
        df = load_sheet(xl, "agent_results")
        rows = []
        for r in df.itertuples(index=False, name=None):
            (scene_id, department, status, ready, reason, missing, expected, metadata) = r
            try:
                meta_json = json.dumps(json.loads(metadata)) if metadata else "{}"
            except (json.JSONDecodeError, TypeError):
                meta_json = "{}"
            rows.append((nz(scene_id), nz(department), nz(status), bool(ready),
                         nz(reason) or "", nz(missing) or "", nz(expected) or "", meta_json))
        upsert(cur, "agent_results",
               ["scene_id","department","status","ready_for_shooting","reason",
                "missing_items","expected_items","metadata"],
               rows, ["scene_id","department"])
        log.info("agent_results: %d rows", len(rows))

        # --- production_state ---
        df = load_sheet(xl, "production_state")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "production_state",
               ["scene_id","readiness_state","overall_status","last_update_ts",
                "ready_to_shoot_flag","blocking_department"],
               rows, ["scene_id"])
        log.info("production_state: %d rows", len(rows))

        # --- issues_log ---
        df = load_sheet(xl, "issues_log")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "issues_log",
               ["issue_id","scene_id","type","severity","description",
                "detected_by_agent","status"],
               rows, ["issue_id"])
        log.info("issues_log: %d rows", len(rows))

        # --- escalation_rules ---
        df = load_sheet(xl, "escalation_rules")
        rows = [tuple(nz(v) for v in r) for r in df.itertuples(index=False, name=None)]
        upsert(cur, "escalation_rules",
               ["rule_id","department","condition","escalation_target","rationale"],
               rows, ["rule_id"])
        log.info("escalation_rules: %d rows", len(rows))

        conn.commit()
        log.info("Ingestion completed successfully.")
    except Exception:
        conn.rollback()
        log.exception("Ingestion failed, rolled back.")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    wait_for_db()
    ingest()

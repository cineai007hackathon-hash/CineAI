-- ============================================================
-- Film AD Orchestrator — Production DB schema (PostgreSQL)
-- Mirrors film_ad_dataset_v4.xlsx 1:1, table for table.
-- Every agent tool call reads from these tables; nothing is
-- hardcoded downstream of here.
-- ============================================================

CREATE TABLE IF NOT EXISTS scene_master (
    scene_id        TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    title           TEXT NOT NULL,
    logline         TEXT,
    int_ext         TEXT CHECK (int_ext IN ('INT','EXT')),
    location_id     TEXT NOT NULL,
    location_name   TEXT,
    shoot_date      DATE NOT NULL,
    shoot_time      TIME NOT NULL,
    day_night       TEXT,
    unit            TEXT,
    scene_type      TEXT
);

CREATE TABLE IF NOT EXISTS scene_breakdown (
    scene_id                TEXT PRIMARY KEY REFERENCES scene_master(scene_id),
    primary_characters      TEXT,
    extras_estimate         INTEGER DEFAULT 0,
    vehicles                TEXT,
    key_props               TEXT,
    action_beats            TEXT,
    stunt_level             TEXT,
    camera_style            TEXT,
    weather_dependency      TEXT,
    department_notes_camera TEXT,
    department_notes_stunt  TEXT,
    department_notes_art    TEXT
);

CREATE TABLE IF NOT EXISTS location_master (
    location_id       TEXT PRIMARY KEY,
    location_name     TEXT NOT NULL,
    location_type     TEXT,
    city              TEXT,
    permit_required   BOOLEAN DEFAULT FALSE,
    permit_status     TEXT,
    operating_hours   TEXT,
    noise_profile     TEXT,
    access_constraints TEXT
);

CREATE TABLE IF NOT EXISTS weather_requirements (
    scene_id            TEXT PRIMARY KEY REFERENCES scene_master(scene_id),
    max_rain_probability NUMERIC(3,2),
    max_wind_kmh        INTEGER,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS weather_readings (
    id                SERIAL PRIMARY KEY,
    scene_id          TEXT REFERENCES scene_master(scene_id),
    "timestamp"       TIMESTAMP NOT NULL,
    location_id       TEXT REFERENCES location_master(location_id),
    rain_probability  NUMERIC(3,2),
    wind_speed_kmh    INTEGER,
    visibility_km     INTEGER
);

CREATE TABLE IF NOT EXISTS camera_inventory (
    camera_id        TEXT PRIMARY KEY,
    label            TEXT,
    type             TEXT,
    model            TEXT,
    owner_department TEXT,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS camera_schedule (
    id         SERIAL PRIMARY KEY,
    camera_id  TEXT REFERENCES camera_inventory(camera_id),
    date       DATE NOT NULL,
    status     TEXT CHECK (status IN ('AVAILABLE','IN_MAINTENANCE','BOOKED')),
    notes      TEXT,
    UNIQUE (camera_id, date)
);

CREATE TABLE IF NOT EXISTS scene_camera_plan (
    scene_id        TEXT PRIMARY KEY REFERENCES scene_master(scene_id),
    camera_setup_id TEXT,
    camera_ids      TEXT NOT NULL,   -- comma-separated list of camera_id
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS stunt_catalog (
    stunt_id             TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    risk_level           TEXT CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
    description          TEXT,
    requires_harness     BOOLEAN DEFAULT FALSE,
    requires_crash_mats  BOOLEAN DEFAULT FALSE,
    requires_medical     BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS scene_stunt_plan (
    scene_id       TEXT PRIMARY KEY REFERENCES scene_master(scene_id),
    stunt_id       TEXT REFERENCES stunt_catalog(stunt_id),
    stunt_plan_id  TEXT NOT NULL,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS stunt_safety_checklist (
    checklist_id   TEXT PRIMARY KEY,
    scene_id       TEXT REFERENCES scene_master(scene_id),
    stunt_plan_id  TEXT,
    item           TEXT NOT NULL,
    required       BOOLEAN DEFAULT TRUE,
    confirmed      BOOLEAN DEFAULT FALSE,
    confirmed_by   TEXT,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS cast_directory (
    cast_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    role_name       TEXT,
    gender          TEXT,
    union_status    TEXT,
    primary_contact TEXT
);

CREATE TABLE IF NOT EXISTS cast_availability (
    id           SERIAL PRIMARY KEY,
    cast_id      TEXT REFERENCES cast_directory(cast_id),
    date         DATE NOT NULL,
    availability TEXT CHECK (availability IN ('FULL_DAY','HALF_DAY','UNAVAILABLE')),
    UNIQUE (cast_id, date)
);

CREATE TABLE IF NOT EXISTS scene_cast_map (
    scene_id           TEXT REFERENCES scene_master(scene_id),
    cast_id            TEXT REFERENCES cast_directory(cast_id),
    role_on_call_sheet TEXT,
    PRIMARY KEY (scene_id, cast_id)
);

CREATE TABLE IF NOT EXISTS crew_directory (
    crew_id    TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    role       TEXT,
    department TEXT,
    email      TEXT,
    shift      TEXT
);

CREATE TABLE IF NOT EXISTS schedule (
    schedule_id   TEXT PRIMARY KEY,
    scene_id      TEXT REFERENCES scene_master(scene_id),
    shoot_date    DATE NOT NULL,
    planned_start TIME,
    planned_end   TIME,
    slot_order    INTEGER,
    location_id   TEXT REFERENCES location_master(location_id),
    status        TEXT CHECK (status IN ('CONFIRMED','TENTATIVE','CANCELLED')),
    notes         TEXT
);

-- Reference snapshot of expected agent output (used for tests / seed comparisons)
CREATE TABLE IF NOT EXISTS agent_results (
    id                 SERIAL PRIMARY KEY,
    scene_id           TEXT REFERENCES scene_master(scene_id),
    department         TEXT CHECK (department IN ('weather','location','camera','stunt','cast')),
    status             TEXT CHECK (status IN ('READY','BLOCKED')),
    ready_for_shooting BOOLEAN,
    reason             TEXT DEFAULT '',
    missing_items      TEXT DEFAULT '',
    expected_items     TEXT DEFAULT '',
    metadata           JSONB DEFAULT '{}'::jsonb,
    created_at         TIMESTAMP DEFAULT now(),
    UNIQUE (scene_id, department)
);

CREATE TABLE IF NOT EXISTS production_state (
    scene_id            TEXT PRIMARY KEY REFERENCES scene_master(scene_id),
    readiness_state     TEXT CHECK (readiness_state IN ('READY','BLOCKED')),
    overall_status      TEXT CHECK (overall_status IN ('READY_TO_SHOOT','NEEDS_REPLAN','HUMAN_REVIEW')),
    last_update_ts      TIMESTAMP DEFAULT now(),
    ready_to_shoot_flag BOOLEAN DEFAULT FALSE,
    blocking_department TEXT
);

CREATE TABLE IF NOT EXISTS issues_log (
    issue_id         TEXT PRIMARY KEY,
    scene_id         TEXT REFERENCES scene_master(scene_id),
    type             TEXT,
    severity         TEXT CHECK (severity IN ('LOW','MEDIUM','HIGH')),
    description      TEXT,
    detected_by_agent TEXT,
    status           TEXT CHECK (status IN ('OPEN','RESOLVED')) DEFAULT 'OPEN',
    created_at       TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS escalation_rules (
    rule_id           TEXT PRIMARY KEY,
    department        TEXT NOT NULL,
    condition         TEXT NOT NULL,
    escalation_target TEXT NOT NULL,
    rationale         TEXT
);

CREATE INDEX IF NOT EXISTS idx_weather_readings_scene ON weather_readings(scene_id);
CREATE INDEX IF NOT EXISTS idx_camera_schedule_camera_date ON camera_schedule(camera_id, date);
CREATE INDEX IF NOT EXISTS idx_cast_availability_cast_date ON cast_availability(cast_id, date);
CREATE INDEX IF NOT EXISTS idx_agent_results_scene ON agent_results(scene_id);
CREATE INDEX IF NOT EXISTS idx_issues_log_scene ON issues_log(scene_id);

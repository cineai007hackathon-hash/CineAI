# Film AD Database Ingestion

This directory contains the PostgreSQL schema and the dataset ingestion script for `film_ad_dataset_v4.xlsx`.

## Prerequisites

- Docker Desktop, or a running PostgreSQL 16 database
- Python 3.10 or newer
- The dataset file `film_ad_dataset_v4.xlsx`

## Option 1: Run PostgreSQL with Docker

From this directory, build the PostgreSQL image:

```powershell
docker build -t film-ad-db .
```

Start a container. The schema in `001_schema.sql` is applied automatically when the database is initialized:

```powershell
docker run --name film-ad-db `
  -e POSTGRES_DB=film_ad `
  -e POSTGRES_USER=film_ad_user `
  -e POSTGRES_PASSWORD=film_ad_pass `
  -p 5432:5432 `
  -d film-ad-db
```

The database may take a few seconds to become ready. Check its status with:

```powershell
docker ps
```

If the container already exists, start it with:

```powershell
docker start film-ad-db
```

## Option 2: Use an Existing PostgreSQL Database

Apply the schema manually:

```powershell
psql -h localhost -U film_ad_user -d film_ad -f 001_schema.sql
```

Set the connection variables before running the ingestion script. Change these values to match your database:

```powershell
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_DB = "film_ad"
$env:POSTGRES_USER = "film_ad_user"
$env:POSTGRES_PASSWORD = "film_ad_pass"
```

## Install Ingestion Dependencies

Create and activate a virtual environment from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run the following once for the current user, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Ingest the Dataset

Make sure the current directory is `ad_multi_agent/backend/db`, then run:

```powershell
python ingest.py
```

The script will:

1. Wait for PostgreSQL to become reachable.
2. Read `film_ad_dataset_v4.xlsx`.
3. Insert or update rows in all dataset tables.
4. Commit the transaction only after all sheets are processed.

To use a different workbook, set `DATASET_PATH` before running the script:

```powershell
$env:DATASET_PATH = "C:\path\to\another_dataset.xlsx"
python ingest.py
```

## Verify the Ingestion

Check that the expected tables exist and contain data:

```powershell
psql -h localhost -U film_ad_user -d film_ad -c "SELECT 'scene_master' AS table_name, COUNT(*) FROM scene_master UNION ALL SELECT 'location_master', COUNT(*) FROM location_master UNION ALL SELECT 'schedule', COUNT(*) FROM schedule;"
```

You can also inspect the most recent ingestion output in the terminal. A successful run ends with:

```text
Ingestion completed successfully.
```

## Rerunning the Ingestion

The ingestion is idempotent for the upserted tables, so it can be run again after updating the workbook. The `weather_readings` table is fully deleted and reloaded on each run.

If ingestion fails, the transaction is rolled back. Fix the reported issue and run `python ingest.py` again.

## Connection Defaults

Unless overridden with environment variables, `ingest.py` uses:

| Variable | Default |
| --- | --- |
| `POSTGRES_HOST` | `localhost` |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | `film_ad` |
| `POSTGRES_USER` | `film_ad_user` |
| `POSTGRES_PASSWORD` | `film_ad_pass` |
| `DATASET_PATH` | `film_ad_dataset_v4.xlsx` |

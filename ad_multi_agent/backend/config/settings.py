# Key excerpts – full file is in /home/workdir/artifacts/settings.py

DB_HOST = settings.POSTGRES_HOST          # localhost
DB_PORT = settings.POSTGRES_PORT          # 5432
DB_NAME = settings.POSTGRES_DB            # film_ad
DB_USER = settings.POSTGRES_USER          # film_ad_user
DB_PASS = settings.POSTGRES_PASSWORD      # film_ad_pass

# Also provides:
#   settings.DATABASE_URL          → postgresql+asyncpg://...
#   settings.DATABASE_URL_SYNC     → postgresql+psycopg2://...
#   WEATHER_MCP_*, LOCATION_MCP_*, DOCLING_*, WATSONX_* toggles
#   ALLOW_INVENTED_FORECASTS = False   (hard constraint)
#   REQUIRE_HUMAN_APPROVAL_ON_BLOCKED = True
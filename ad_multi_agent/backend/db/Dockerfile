FROM postgres:16-alpine

ENV POSTGRES_DB=film_ad \
    POSTGRES_USER=film_ad_user \
    POSTGRES_PASSWORD=film_ad_pass

COPY 001_schema.sql /docker-entrypoint-initdb.d/001_schema.sql

EXPOSE 5432

HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
  CMD pg_isready -U film_ad_user -d film_ad || exit 1
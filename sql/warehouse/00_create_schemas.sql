-- Warehouse baseline schemas.
-- Business timestamps are stored as TIMESTAMP WITHOUT TIME ZONE using
-- America/New_York semantics; audit timestamps are stored as UTC TIMESTAMPTZ.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS dq;

COMMENT ON SCHEMA staging IS 'Raw source-aligned warehouse staging tables with shared lineage metadata.';
COMMENT ON SCHEMA audit IS 'ETL batch, source extract, checksum, and processing audit metadata.';
COMMENT ON SCHEMA dq IS 'Data quality results and quarantine placeholders.';

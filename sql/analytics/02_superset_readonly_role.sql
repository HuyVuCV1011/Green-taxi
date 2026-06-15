-- The login role is created and its password is managed by
-- scripts/setup_superset_warehouse.py. This file owns grants only.

REVOKE ALL ON SCHEMA public FROM superset_ro;

GRANT CONNECT ON DATABASE green_taxi_warehouse TO superset_ro;
GRANT USAGE ON SCHEMA analytics TO superset_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO superset_ro;

ALTER DEFAULT PRIVILEGES FOR ROLE green_taxi_warehouse_app IN SCHEMA analytics
GRANT SELECT ON TABLES TO superset_ro;

-- Defense in depth: do not expose implementation schemas to the BI login.
REVOKE ALL ON SCHEMA staging, audit, dq, nds, dds FROM superset_ro;
REVOKE ALL ON ALL TABLES IN SCHEMA staging, audit, dq, nds, dds FROM superset_ro;

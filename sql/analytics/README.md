# Analytics SQL

`01_certified_datasets.sql` tạo các PostgreSQL views read-only, deterministic:

| View | Grain | Purpose |
|---|---|---|
| `analytics.trip_pickup` | 1 row/trip | Default pickup date/location analysis |
| `analytics.trip_dropoff` | 1 row/trip | Explicit dropoff date/location analysis |
| `analytics.shift` | 1 row/completed shift | Shift metrics and start/end zone aliases |
| `analytics.shift_trip_aggregate` | 1 row/shift_id | Safe trip aggregate before any fact comparison |
| `analytics.dq_summary` | 1 row/DQ grouping | Issue/quarantine monitoring without fact joins |

Apply only through the project DDL/deployment process after review. The script
does not materialize data and does not modify warehouse rows. Superset should
receive `USAGE` on `analytics` and `SELECT` on these views only as a separate
security task; this workstream does not create users or secrets.

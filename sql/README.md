# SQL

```text
sql/
|-- ddl/             # Warehouse schemas, tables, constraints và indexes
|-- warehouse/       # PostgreSQL warehouse baseline: schemas, audit metadata, staging
|-- source_mysql_hr/ # MySQL Driver HR source DDL
|-- source_postgres_dispatch/ # PostgreSQL Dispatch/Assignment source DDL
|-- transformations/ # SQL chuyển đổi giữa các tầng
|-- tests/           # Reconciliation và DQ assertions
`-- analytics/       # Query phục vụ dashboard/report
```

MySQL/PostgreSQL source bootstrap SQL phải tách khỏi warehouse DDL. MongoDB
indexes/validation có thể nằm trong script seeding tương ứng.

Warehouse baseline hiện nằm trong `sql/warehouse/` và apply bằng:

```powershell
python scripts\apply_warehouse_ddl.py --mode docker
```

Xem chi tiết trong `docs/14-warehouse-ddl.md`.

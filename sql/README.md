# SQL

```text
sql/
|-- ddl/             # Placeholder reserved; DDL thực thi hiện nằm trong warehouse/
|-- warehouse/       # PostgreSQL warehouse schemas, audit, staging, DQ, NDS, DDS
|-- source_mysql_hr/ # MySQL Driver HR source DDL
|-- source_postgres_dispatch/ # PostgreSQL Dispatch/Assignment source DDL
|-- transformations/ # Placeholder reserved cho SQL chuyển đổi tách riêng
|-- tests/           # Placeholder reserved cho SQL assertions
`-- analytics/       # Query phục vụ dashboard/report
```

MySQL/PostgreSQL source bootstrap SQL phải tách khỏi warehouse DDL. MongoDB
indexes/validation có thể nằm trong script seeding tương ứng.

Warehouse baseline hiện nằm trong `sql/warehouse/` và apply bằng:

```powershell
python scripts\apply_warehouse_ddl.py --mode docker
```

Xem chi tiết trong `docs/warehouse/physical-model.md`.

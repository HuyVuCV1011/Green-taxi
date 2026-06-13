# SQL

```text
sql/
|-- ddl/             # Warehouse schemas, tables, constraints và indexes
|-- source/          # Source-system bootstrap DDL khi Milestone 2 được triển khai
|-- transformations/ # SQL chuyển đổi giữa các tầng
|-- tests/           # Reconciliation và DQ assertions
`-- analytics/       # Query phục vụ dashboard/report
```

MySQL/PostgreSQL source bootstrap SQL phải tách khỏi warehouse DDL. MongoDB
indexes/validation có thể nằm trong script seeding tương ứng.

# Source Code

```text
src/
|-- ingestion/    # File/MySQL/MongoDB/PostgreSQL adapters và staging load
|-- seeding/      # Seed source systems từ canonical release
|-- quality/      # Data-quality rules và quarantine
|-- warehouse/    # Load/upsert các tầng dữ liệu
|-- analytics/    # Measures và datasets phục vụ BI
`-- common/       # Config, logging và utilities dùng chung
```

Source adapters phải phát ra common staging records; business transformations
không nằm trong connector code.

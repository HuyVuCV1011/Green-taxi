# Source Code

```text
src/
|-- ingestion/      # File/MySQL/MongoDB/PostgreSQL adapters và staging load
|-- warehouse/      # NDS/DDS loaders và warehouse validation
|-- orchestration/  # PipelineRunner, step models và execution contract
`-- monitoring/     # Repository đọc trạng thái cho Streamlit và sanitization
```

Source adapters phải phát ra common staging records; business transformations
không nằm trong connector code.

Seed scripts hiện là entry point trong `scripts/`. Nếu sau này tách logic dùng lại
vào `src/seeding/`, cần cập nhật tài liệu và tests cùng lúc.

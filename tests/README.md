# Tests

Thư mục này là test suite hiện hành của repo, không phải nháp. Các file test ở
đây khóa hành vi code, SQL contract, Superset provisioning contract và chất
lượng tài liệu Markdown.

## Nhóm kiểm thử

| File | Vai trò |
|---|---|
| `test_analytics_contract.py` | Kiểm tra analytics views, OLAP/Data Mining tables, grain và metric contract |
| `test_superset_demo_contract.py` | Kiểm tra Superset compose, read-only role, 10 datasets, 88 metrics và 42 charts trong provisioning script |
| `test_markdown_docs.py` | Kiểm tra Markdown links, script references, stale docs và secret patterns |
| `test_warehouse_ddl_contract.py` | Kiểm tra schema warehouse, NDS/DDS/DQ order, SCD2 indexes và DQ enums |
| `test_dds_loader.py`, `test_nds_loader.py`, `test_load_staging.py` | Unit/contract tests cho staging, NDS, DDS loaders và DQ handling |
| `test_pipeline_runner.py`, `test_pipeline_validation.py` | Kiểm tra orchestration, dry-run, resume, fail-fast và validation result |
| `test_streamlit_control_panel.py` | Kiểm tra Control Panel structure, health cache, sanitization, DDS readiness và file-lock stale recovery |
| `test_monitoring_repository.py` | Kiểm tra repository đọc trạng thái, whitelist và redaction |
| `test_seed_mysql_hr.py`, `test_generator_shift_logic.py`, `test_sample_integrity.py` | Kiểm tra seed/generator logic và sample referential integrity |

## Cách chạy

```powershell
python -m unittest tests.test_monitoring_repository -v
python -m unittest tests.test_streamlit_control_panel -v
python -m unittest tests.test_pipeline_runner -v
python -m unittest discover -s tests -v
```

Full suite hiện tại chạy nhanh trên sample/static fixtures và không cần live
Docker, trừ các script smoke/benchmark Superset được chạy riêng theo runbook.
Không ghi cứng tổng số test trong tài liệu này vì con số thay đổi khi bổ sung
regression coverage; dùng output `unittest` làm nguồn sự thật.

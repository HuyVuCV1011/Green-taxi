# Tests

- Unit tests cho parser và transformation.
- Seed idempotency tests cho MySQL/MongoDB/PostgreSQL source.
- Connector contract tests cho file và database/document adapters.
- Data-quality tests cho schema, khóa, phạm vi và lookup.
- Integration tests từ sample raw đến bảng đích.
- Reconciliation tests cho release-to-source, source-to-staging và tổng measure.

Chạy sample test:

```powershell
python -m unittest tests.test_monitoring_repository -v
python -m unittest tests.test_streamlit_control_panel -v
python -m unittest tests.test_pipeline_runner -v
python -m unittest discover -s tests -v
```

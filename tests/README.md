# Tests

- Unit tests cho parser và transformation.
- Data-quality tests cho schema, khóa, phạm vi và lookup.
- Integration tests từ sample raw đến bảng đích.
- Reconciliation tests cho row count và tổng measure.

Chạy sample test:

```powershell
python -m unittest discover -s tests
```

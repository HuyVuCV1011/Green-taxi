# Scripts

## Sinh synthetic source systems

Chạy tại repository root:

```powershell
python scripts/generate_synthetic_sources.py
python scripts/validate_synthetic_sources.py
python scripts/create_repository_samples.py
```

Generator sử dụng `configs/synthetic_generation.json`, đọc TLC trip CSV hiện có
và tạo:

- `data/raw/synthetic/driver_hr/drivers.csv`
- `data/raw/synthetic/driver_hr/driver_changes.jsonl`
- `data/raw/synthetic/fleet/vehicles.jsonl`
- `data/raw/synthetic/dispatch/shifts.tsv`
- `data/raw/synthetic/trip_assignment/year=YYYY/month=MM/*.csv`
- `data/metadata/synthetic_generation_manifest.json`
- `data/metadata/synthetic_validation_report.json`

Raw synthetic data bị Git ignore; generator, config, manifest và validation
report được version-control để bảo đảm khả năng tái tạo.

Các entry point pipeline tiếp theo:

- `load_staging`
- `run_dq`
- `load_nds`
- `load_dds`
- `validate_pipeline`

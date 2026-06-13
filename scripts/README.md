# Scripts

## Công cụ dành cho data owner

Các lệnh dưới đây chỉ dùng khi data owner chủ động tạo một data release mới,
không phải bước setup dành cho thành viên:

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

Thành viên lấy full dataset đã được kiểm tra từ Google Drive theo
`docs/13-team-onboarding-and-data-setup.md` và không tự chạy generator.

Các entry point dự kiến cho Milestone 2 (chưa được triển khai):

- `seed_sources`
- `validate_source_seed`
- `load_staging`
- `run_dq`
- `load_nds`
- `load_dds`
- `validate_pipeline`

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

## Runtime dependencies

Seed/DDL scripts dùng một số thư viện database client:

```powershell
python -m pip install -r requirements.txt
```

## Seed MySQL Driver HR

Sau khi tải release vào `data/raw/` và dựng service `mysql_hr`, áp dụng DDL rồi
seed Driver HR:

```powershell
python scripts/seed_mysql_hr.py --release-id green-taxi-full-v1
```

Script đọc `MYSQL_HR_HOST`, `MYSQL_HR_PORT`, `MYSQL_HR_DATABASE`,
`MYSQL_HR_USER` và `MYSQL_HR_PASSWORD` từ environment. Mặc định script upsert theo
natural key (`driver_id`, `event_id`) nên chạy lại cùng release không tạo
duplicate. Chỉ dùng `--truncate` khi muốn reload có kiểm soát trên local source
disposable. Script tự apply `sql/source_mysql_hr/01_driver_tables.sql`; dùng
`--skip-ddl` chỉ khi muốn tự quản lý DDL bên ngoài script.

Entry point đã triển khai cho warehouse baseline:

- `apply_warehouse_ddl.py` tạo PostgreSQL warehouse schemas `staging`, `audit`,
  `dq`, audit metadata và staging tables ban đầu.
- `seed_mongodb_fleet.py` seed MongoDB Fleet từ `vehicles.jsonl`.
- `seed_postgres_dispatch.py` seed PostgreSQL Dispatch/Assignment từ release.

Các entry point dự kiến tiếp theo:

- `validate_source_seed`
- `load_staging`
- `run_dq`
- `load_nds`
- `load_dds`
- `validate_pipeline`

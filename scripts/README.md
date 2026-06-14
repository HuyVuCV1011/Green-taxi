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
`docs/00-team-onboarding-and-data-setup.md` và không tự chạy generator.

## Runtime dependencies

Seed/DDL scripts dùng một số thư viện database client:

```powershell
python -m pip install -r requirements.txt
```

## Source seed tools

Sau khi tải release vào `data/raw/` và dựng Docker services, seed source
systems bằng các entry point sau:

### MySQL Driver HR

```powershell
python scripts/seed_mysql_hr.py --release-id green-taxi-full-v1
```

Script đọc `MYSQL_HR_HOST`, `MYSQL_HR_PORT`, `MYSQL_HR_DATABASE`,
`MYSQL_HR_USER` và `MYSQL_HR_PASSWORD` từ environment. Mặc định script upsert theo
natural key (`driver_id`, `event_id`) nên chạy lại cùng release không tạo
duplicate. Chỉ dùng `--truncate` khi muốn reload có kiểm soát trên local source
disposable. Script tự apply `sql/source_mysql_hr/01_driver_tables.sql`; dùng
`--skip-ddl` chỉ khi muốn tự quản lý DDL bên ngoài script.

### MongoDB Fleet

```powershell
python scripts/seed_mongodb_fleet.py --release-id green-taxi-full-v1
```

### PostgreSQL Dispatch

```powershell
python scripts/seed_postgres_dispatch.py --release-id green-taxi-full-v1
```

## Warehouse DDL tool

`apply_warehouse_ddl.py` tạo PostgreSQL warehouse schemas `staging`, `audit`,
`dq`, audit metadata và staging tables ban đầu.

```powershell
python scripts/apply_warehouse_ddl.py --mode docker
```

## Load Warehouse Staging

Công cụ này thực hiện trích xuất dữ liệu từ các hệ thống nguồn (MySQL HR, MongoDB Fleet, PostgreSQL Dispatch) và tệp tin thô (TLC Green Trips, Lookup CSVs) để nạp vào tầng Staging của PostgreSQL Warehouse.

```powershell
# Chạy loader nạp toàn bộ các nguồn dữ liệu vào Staging
python scripts/load_staging.py --release-id green-taxi-full-v1 --source all
```

**Các tùy chọn chính:**
- `--source`: Chọn nguồn dữ liệu cần nạp (`hr`, `fleet`, `dispatch`, `tlc`, `lookup`, `all`). Mặc định là `all`.
- `--release-id`: Định danh phiên bản dữ liệu phát hành. Mặc định là `green-taxi-full-v1`.
- `--limit-files`: Giới hạn số lượng tệp tin TLC CSV được nạp (hữu ích khi chạy thử hoặc debug).
- `--limit-rows`: Giới hạn số lượng dòng được nạp trên mỗi tệp tin TLC CSV.
- `--data-root`: Đường dẫn tương đối hoặc tuyệt đối tới thư mục dữ liệu. Mặc định lấy từ biến môi trường `DATA_ROOT` hoặc thư mục `data`.

## Load NDS và DDS

```powershell
python scripts/load_nds.py --release-id green-taxi-full-v1
python scripts/load_dds.py --release-id green-taxi-full-v1
```

`load_nds.py` thực thi DQ Gate 1, quarantine và chuẩn hóa 3NF.
`load_dds.py` thực thi DQ Gate 2, SCD2 và upsert hai fact theo business key.

## Validate pipeline

```powershell
# Reconciliation cho full release
python scripts/validate_warehouse_pipeline.py --release-id green-taxi-full-v1

# DQ và idempotency fixture, chỉ chạy trên database test riêng
python scripts/validate_warehouse_pipeline.py --release-id dq-validation-v1 --dq-fixtures
```

Validator kiểm tra lineage Source/Staging/NDS/DDS, count và measure, duplicate
business key, current SCD2 row, shift duration, quarantine, WARN/ERROR và rerun
không sinh thêm fact hoặc SCD version.

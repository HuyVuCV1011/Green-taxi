# Full Pipeline Validation On Clean Warehouse

Ngày chạy: 2026-06-14

Vai trò: Pipeline Validation Owner

Release: `green-taxi-full-v1`

Base commit ghi nhận: `08fa0296206ab052f4b23c6512cffda9b2dcc315`

Database warehouse test: `green_taxi_warehouse_clean_validation`

Phạm vi: `Source Seed -> Staging -> DQ/Audit -> NDS -> DDS`

## Kết Luận

Pipeline end-to-end chạy xong trên database warehouse test sạch và các bước audit đều `SUCCEEDED`.

Validation reconciliation pass. Tuy nhiên workspace hiện không có file TLC full release tại `data/raw/tlc/**/*.csv`, nên `TLC_FILE/tlc_green_tripdata` được đánh dấu `SKIPPED` với `0` dòng. Pipeline vẫn tạo `NDS/DDS` trip từ `DISPATCH_POSTGRES.trip_assignments`; các metric tài chính/khoảng cách/duration từ TLC vì vậy bằng `0` và chưa thể xem là full TLC validation hoàn chỉnh.

Không sửa raw/full data. Không sửa code vì lỗi phát hiện là thiếu artifact dữ liệu cục bộ, không phải lỗi pipeline.

## Điều Kiện Môi Trường

Docker Compose config hợp lệ bằng lệnh `docker compose config`.

Docker services healthy bằng lệnh `docker compose ps`:

| Service | Container | Status |
|---|---|---|
| `mysql_hr` | `green_taxi_mysql_hr` | `Up (healthy)` |
| `mongodb_fleet` | `green_taxi_mongodb_fleet` | `Up (healthy)` |
| `postgres_dispatch` | `green_taxi_postgres_dispatch` | `Up (healthy)` |
| `postgres_warehouse` | `green_taxi_postgres_warehouse` | `Up (healthy)` |

Database validation chưa tồn tại trước khi chạy và được tạo mới bằng:

```powershell
docker compose exec -T postgres_warehouse createdb -U green_taxi_warehouse_app green_taxi_warehouse_clean_validation
```

## Log Lệnh Và Thời Gian

| Bước | Lệnh | Thời gian |
|---|---|---:|
| Docker config | `docker compose config` | Pass |
| Docker health | `docker compose ps` | Pass |
| Tạo validation DB | `createdb green_taxi_warehouse_clean_validation` | Pass |
| Apply DDL | `$env:POSTGRES_WAREHOUSE_DATABASE='green_taxi_warehouse_clean_validation'; python scripts/apply_warehouse_ddl.py --mode docker` | 1.105s |
| Seed MySQL HR | `python scripts/seed_mysql_hr.py --release-id green-taxi-full-v1` | 1.603s |
| Seed MongoDB Fleet | `python scripts/seed_mongodb_fleet.py --release-id green-taxi-full-v1` | 0.844s |
| Seed PostgreSQL Dispatch | `python scripts/seed_postgres_dispatch.py --release-id green-taxi-full-v1` | 1.647s |
| Run pipeline | `$env:POSTGRES_WAREHOUSE_DATABASE='green_taxi_warehouse_clean_validation'; python scripts/run_pipeline.py --release-id green-taxi-full-v1` | 857.686s |
| Warehouse validation | `$env:POSTGRES_WAREHOUSE_DATABASE='green_taxi_warehouse_clean_validation'; python scripts/validate_warehouse_pipeline.py --release-id green-taxi-full-v1` | 1.865s |
| Unit tests | `python -m unittest discover -s tests -v` | 117 tests pass |
| Diff whitespace | `git diff --check` | Pass |

Pipeline runtime theo audit timestamps:

| Batch | Batch ID | Status | Started UTC | Completed UTC | Approx duration |
|---|---|---|---|---|---:|
| Staging | `e54bbe90-dd95-4410-99df-fd1d758ced08` | `SUCCEEDED` | `2026-06-14 06:17:14.097313+00` | `2026-06-14 06:19:33.885946+00` | 139.789s |
| NDS | `3065e3e3-fc06-40cd-9c75-c0ecbbd34f0d` | `SUCCEEDED` | `2026-06-14 06:19:33.938727+00` | `2026-06-14 06:23:43.226960+00` | 249.288s |
| DDS | `f6b05b94-0c0d-4881-b7ae-7a05a1994c04` | `SUCCEEDED` | `2026-06-14 06:23:43.299978+00` | `2026-06-14 06:31:29.840081+00` | 466.540s |

## Source Seed Counts

| Source | Entity | Rows |
|---|---|---:|
| MySQL HR | `drivers` | 860 |
| MySQL HR | `driver_changes` | 77 |
| MongoDB Fleet | `vehicles` | 860 |
| PostgreSQL Dispatch | `shifts` | 157,379 |
| PostgreSQL Dispatch | `trip_assignments` | 2,304,276 |
| PostgreSQL Dispatch | `assignment_exceptions` | 241 |

Seed scripts được chạy ở chế độ idempotent, không dùng truncate/reset.

## Audit Row Counts

Batch summary:

| Batch | Expected rows | Loaded rows | Error message |
|---|---:|---:|---|
| `warehouse_staging` | 2,463,720 | 2,463,720 | None |
| `warehouse_nds` | 2,463,720 | 2,463,720 | None |
| `warehouse_dds` | 0 | 2,465,663 | None |

Source extract summary:

| Source system | Entity | Rows read | Rows loaded | Status |
|---|---|---:|---:|---|
| `HR_MYSQL` | `drivers` | 860 | 860 | `SUCCEEDED` |
| `HR_MYSQL` | `driver_changes` | 77 | 77 | `SUCCEEDED` |
| `FLEET_MONGODB` | `vehicles` | 860 | 860 | `SUCCEEDED` |
| `DISPATCH_POSTGRES` | `shifts` | 157,379 | 157,379 | `SUCCEEDED` |
| `DISPATCH_POSTGRES` | `trip_assignments` | 2,304,276 | 2,304,276 | `SUCCEEDED` |
| `LOOKUP_FILE` | `taxi_zone` | 265 | 265 | `SUCCEEDED` |
| `LOOKUP_FILE` | `vendor` | 3 | 3 | `SUCCEEDED` |
| `TLC_FILE` | `tlc_green_tripdata` | 0 | 0 | `SKIPPED` |

Warehouse table counts:

| Table | Rows |
|---|---:|
| `staging.stg_hr_drivers` | 860 |
| `staging.stg_hr_driver_changes` | 77 |
| `staging.stg_fleet_vehicles` | 860 |
| `staging.stg_dispatch_shifts` | 157,379 |
| `staging.stg_dispatch_trip_assignments` | 2,304,276 |
| `staging.stg_lookup_vendor` | 3 |
| `staging.stg_lookup_taxi_zone` | 265 |
| `staging.stg_tlc_green_trips` | 0 |
| `nds.nds_shift` | 157,379 |
| `nds.nds_trip` | 2,304,276 |
| `nds.nds_trip_assignment` | 2,304,276 |
| `dds.fact_driver_shift` | 157,379 |
| `dds.fact_driver_trip` | 2,304,276 |

## DQ Và Quarantine

| Metric | Rows |
|---|---:|
| `dq.quarantine_record` | 0 |
| `dq.dq_issue` | 2,340,347 |

DQ issue breakdown:

| Severity | Rule code | Rows |
|---|---|---:|
| `WARN` | `DQ_MISSING_MASTER` | 2,304,276 |
| `WARN` | `ANOM_TRIP_OUT_SHF` | 36,071 |

Không có quarantine `ERROR`. Các issue đều là `WARN` và không chặn NDS/DDS.

## Validation Output

`python scripts/validate_warehouse_pipeline.py --release-id green-taxi-full-v1` trên validation database trả về tất cả check `PASS`:

| Check | Actual | Expected | Status |
|---|---:|---:|---|
| `source_to_staging_audit` | `(2463720, 2463720)` | `(2463720, 2463720)` | `PASS` |
| `staging_assignments_to_nds_trips` | 2,304,276 | 2,304,276 | `PASS` |
| `staging_assignments_to_nds_assignments` | 2,304,276 | 2,304,276 | `PASS` |
| `nds_trips_to_dds_trips` | 2,304,276 | 2,304,276 | `PASS` |
| `completed_nds_shifts_to_dds_shifts` | 157,379 | 157,379 | `PASS` |
| `trip_revenue` | 0.00 | 0.00 | `PASS` |
| `trip_distance` | 0 | 0 | `PASS` |
| `trip_duration_rounded_per_row` | 0.00 | 0.00 | `PASS` |
| `duplicate_nds_trip_nk` | 0 | 0 | `PASS` |
| `duplicate_dds_trip_id` | 0 | 0 | `PASS` |
| `duplicate_dds_shift_id` | 0 | 0 | `PASS` |
| `driver_multiple_current` | 0 | 0 | `PASS` |
| `vehicle_multiple_current` | 0 | 0 | `PASS` |
| `invalid_shift_minutes` | 0 | 0 | `PASS` |

## Lỗi Và Warning Phát Hiện

| Loại | Nội dung | Cách xử lý |
|---|---|---|
| Warning dữ liệu | `data/raw/tlc/**/*.csv` không tồn tại, pipeline in `[!] Warning: TLC raw directory or CSV files not found. Skipped TLC load.` | Không sửa raw data. Ghi nhận blocker. Cần đồng bộ lại thư mục `data/raw/tlc` từ release chuẩn rồi chạy lại validation để xác nhận metric TLC/revenue/distance thực. |
| DQ warning | `DQ_MISSING_MASTER = 2,304,276` do trip/assignment phát sinh inferred master theo logic late-arriving | Không chặn pipeline. Cần xem xét thứ tự và coverage master nếu mục tiêu là giảm inferred members. |
| DQ warning | `ANOM_TRIP_OUT_SHF = 36,071` | Không chặn pipeline theo spec Gate 2. Cần phân tích nghiệp vụ riêng nếu dùng dashboard anomaly. |

## Kết Quả Kiểm Thử Bắt Buộc

| Lệnh | Kết quả |
|---|---|
| `python -m unittest discover -s tests -v` | Pass, 117 tests |
| `git diff --check` | Pass |
| `docker compose config` | Pass |
| `docker compose ps` | 4 services healthy |
| `python scripts/validate_warehouse_pipeline.py --release-id green-taxi-full-v1` | Pass |

## Ghi Chú Hoàn Thành

Không có code fix và không có regression test mới vì pipeline không phát hiện lỗi logic/code. Rủi ro còn lại là validation này chưa bao phủ TLC full raw files do artifact không có trong workspace tại thời điểm chạy.

# NDS/DDS Implementation Notes

Status: `IMPLEMENTED`

Tài liệu này ghi ngắn gọn các quyết định kỹ thuật của pipeline
`Staging -> DQ/Audit -> NDS -> DDS`. Contract chi tiết vẫn nằm tại
`10-source-to-target-plan.md`, `14-warehouse-ddl.md` và
`17-data-quality-and-etl-spec.md`.

## NDS loader

- NDS giữ mô hình 3NF và dùng natural key để upsert master/transaction.
- `trip_key` được lấy nguyên vẹn từ staging assignment và lưu bằng `TEXT`;
  TLC trip được ghép bằng `release_id + source_file + source_row_number`.
- Dữ liệu lớn dùng keyset pagination, mặc định 5.000 dòng mỗi batch, tránh chi
  phí tăng dần của `OFFSET`.
- Lookup surrogate key được cache trong memory; insert/update theo chunk bằng
  `execute_values`.
- DQ mức `ERROR` ghi đồng thời vào `dq.dq_issue` và
  `dq.quarantine_record.raw_payload`; record lỗi không đi vào NDS.
- Batch có quarantine vẫn thành công khi `loaded + quarantined = read`.

## DDS loader

- `dim_driver` và `dim_vehicle` dùng SCD2 với natural key, effective timestamp,
  `source_row_hash`, partial unique index cho một current row.
- Cùng hash là no-op về version; thuộc tính Type 1 và effective metadata vẫn
  được đồng bộ trên current row.
- Fact dùng set-based joins để resolve dimension key theo thời điểm nghiệp vụ,
  tránh N+1 lookup trên hàng triệu trip.
- `fact_driver_shift` tổng hợp trip count, occupied time, revenue, tip và cờ
  anomaly ngay trong query phân trang.
- `trip_id` và `shift_id` là unique business key của fact; rerun dùng upsert.
- `shift_id` là degenerate dimension; không có `dds.dim_shift`.

## Index và kiểu dữ liệu

- Unique index bảo vệ grain của NDS trip, trip assignment và hai fact.
- Partial unique index bảo đảm tối đa một current SCD2 row cho mỗi natural key.
- Index thời gian/hệ thống khóa hỗ trợ lookup shift, trip và dimension.
- `trip_distance` dùng `DECIMAL(12,4)` để bảo toàn outlier nguồn; các amount
  vẫn dùng decimal, không chuyển qua floating point.

## Full-load verification

Smoke test ngày 14/06/2026 trên database test riêng:

| Tầng | Kết quả |
|---|---:|
| Staging trip assignments | 2.304.276 |
| NDS trips | 2.304.276 |
| NDS trip assignments | 2.304.276 |
| DDS trip facts | 2.304.276 |
| NDS completed shifts | 157.379 |
| DDS shift facts | 157.379 |

Rerun DDS tạo `0` version SCD2 mới cho 860 drivers và 860 vehicles. Revenue
trip DDS khớp NDS; duplicate fact/natural key và multiple-current SCD2 đều bằng
`0`.

Reconciliation cũng xác nhận staging audit `4.768.237/4.768.237`, revenue
`48.535.884,47`, distance `87.426.352,1700` và duration làm tròn theo từng trip
`48.423.718,63` đều khớp giữa NDS và DDS. Không có shift có tổng
`occupied_minutes + idle_minutes` lệch `shift_duration_minutes`.

## DQ fixture verification

Fixture trên database test riêng được chạy hai lần:

| Kiểm tra | Kết quả |
|---|---:|
| Invalid enum mức ERROR bị quarantine và không vào NDS | PASS |
| WARN giá trị âm vẫn vào NDS | PASS |
| Inferred driver/vehicle được tạo | PASS |
| Driver overlap, vehicle overlap, trip ngoài shift | PASS |
| `dq_issue` ERROR đối soát với quarantine | 1/1 |
| SCD2 version mới ở lần chạy lại | 0 |
| Count NDS, DDS, DQ và quarantine sau rerun | Không đổi |

Chạy đối soát bằng `scripts/validate_warehouse_pipeline.py`; tùy chọn
`--dq-fixtures` chỉ được dùng trên database test riêng vì script chủ động chèn
fixture.

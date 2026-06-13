# Data Directory

## Quy tắc lưu trữ

GitHub không phải kho lưu full data. Repository chỉ giữ dữ liệu nhỏ cần thiết
để review và chạy automated tests. Full data phải nằm trong kho dữ liệu chung
của nhóm hoặc được tái tạo từ nguồn chính thức.

## Được commit vào Git

- `sample/`: mẫu nhỏ đủ chạy unit/integration test.
- `lookup/`: lookup nhỏ và không có hạn chế phân phối.
- `metadata/`: manifest, checksum và validation report.
- README, manifest và schema.

## Không được commit vào Git

- `raw/`: dữ liệu tải về nguyên bản.
- `interim/`: dữ liệu trung gian.
- `processed/`: dữ liệu pipeline sinh ra.
- Recording hoặc dữ liệu có thông tin nhạy cảm.

## Cấu trúc full data local

Sau khi clone repository và lấy data release, đặt file theo cấu trúc:

```text
data/
|-- raw/
|   |-- tlc/
|   `-- synthetic/
|       |-- driver_hr/
|       |-- fleet/
|       |-- dispatch/
|       `-- trip_assignment/
|-- interim/
`-- processed/
```

Tên và checksum chuẩn của synthetic outputs nằm trong
`metadata/synthetic_generation_manifest.json`. Không đổi tên hoặc sửa file raw
sau khi đã kiểm tra checksum.

Synthetic sources được tạo vào `raw/synthetic/` bằng
`scripts/generate_synthetic_sources.py`.

Hướng dẫn dành cho thành viên mới và quy trình data release:
`../docs/13-team-onboarding-and-data-setup.md`.

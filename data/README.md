# Data Directory

## Quy tắc lưu trữ

GitHub không phải kho lưu full data. Repository chỉ giữ dữ liệu nhỏ cần thiết
để review và chạy automated tests. Full data phải nằm trong kho dữ liệu chung
của nhóm trên Google Drive. Thành viên tải cùng một release, không tự sinh lại
dữ liệu.

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

Sau khi clone repository, thành viên tải release hiện hành từ Google Drive:

```text
green-taxi-full-v1.zip
green-taxi-full-v1.zip.sha256
```

Kiểm SHA-256 của file zip trước khi sử dụng. Hash chuẩn của release hiện hành:

```text
e916e88b2e67fa90d5a5b536c3ac7c82a4f6b21fbfb01735e8c5e5e254be7b01
```

Sau khi giải nén, copy hai thư mục chính vào repository:

```text
green-taxi-full-v1/tlc       -> data/raw/tlc
green-taxi-full-v1/synthetic -> data/raw/synthetic
```

Kết quả local cần có cấu trúc:

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

Không copy đè `data/metadata/` hoặc `data/lookup/` từ release nếu không có yêu
cầu từ data owner; các bản cần thiết cho repository đã được commit sẵn. Staging
loader hiện đọc lookup chuẩn từ `data/lookup/` đã version-control.

Tên và checksum chuẩn của synthetic outputs nằm trong
`metadata/synthetic_generation_manifest.json`. Không đổi tên hoặc sửa file raw
sau khi đã kiểm tra checksum.

Generator chỉ dành cho data owner khi tạo data release mới. Thành viên dự án
không chạy generator trong quy trình setup thông thường.

Trong kiến trúc triển khai:

- TLC và lookup tiếp tục được ingest từ file.
- `driver_hr/` là seed input cho MySQL.
- `fleet/` là seed input cho MongoDB.
- `dispatch/` và `trip_assignment/` là seed input cho PostgreSQL nguồn.

Các source database volumes và warehouse volumes không thuộc thư mục `data/`
và không được chia sẻ như một phần của data release.

Hướng dẫn dành cho thành viên mới và quy trình data release:
`../docs/13-team-onboarding-and-data-setup.md`.

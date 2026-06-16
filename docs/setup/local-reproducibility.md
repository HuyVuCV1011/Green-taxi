# Team Onboarding and Local Setup

Status: `CURRENT OPERATIONAL GUIDE`

Đây là **nguồn hướng dẫn chính** để thành viên mới tái lập dự án từ clone đến
dashboard Superset. README chỉ cung cấp Quick Start; chi tiết vận hành Superset
sau khi setup nằm tại [../analytics/superset-local-demo-runbook.md](../analytics/superset-local-demo-runbook.md).

## Prerequisites

- Git.
- Python 3.11 trở lên.
- Docker Desktop hoặc Docker Engine có Docker Compose v2.
- Khoảng 16 GB RAM được khuyến nghị khi chạy đồng thời source databases,
  warehouse, Streamlit và Superset.

## Standard onboarding flow

Thực hiện đúng thứ tự:

```text
clone -> dependencies -> .env -> data/checksum -> Docker up
      -> seed/load pipeline -> reconciliation -> Superset -> smoke test -> login
```

### 1. Clone và cài dependencies

```powershell
git clone https://github.com/HuyVuCV1011/Green-taxi.git
cd Green-taxi
python -m pip install -r requirements.txt
```

### 2. Tạo cấu hình local

```powershell
Copy-Item configs\.env.example .env
```

Mở `.env` và thay mọi giá trị `CHANGE_ME_*` bằng credential local của riêng
thành viên. Không dùng credential local của người khác.

`.env` và `.env.superset` đều bị `.gitignore` loại khỏi Git. Có thể xác nhận:

```powershell
git check-ignore -v .env .env.superset
```

### 3. Tải và kiểm tra full data release

| Thuộc tính | Giá trị |
|---|---|
| Release | `green-taxi-full-v1` |
| Folder | [Google Drive Release Folder](https://drive.google.com/drive/folders/1a9wjCly_R1c_sTSq89cONAE-rCWmwuiZ) |
| Files | `green-taxi-full-v1.zip`, `green-taxi-full-v1.zip.sha256` |
| SHA-256 | `e916e88b2e67fa90d5a5b536c3ac7c82a4f6b21fbfb01735e8c5e5e254be7b01` |

Kiểm tra checksum trước khi giải nén. Thay `<download_dir>` bằng thư mục tải file
thực tế trên máy của bạn:

```powershell
Get-FileHash "<download_dir>\green-taxi-full-v1.zip" -Algorithm SHA256
Get-Content "<download_dir>\green-taxi-full-v1.zip.sha256"
```

Hai giá trị phải khớp SHA-256 trong bảng. Sau đó giải nén và copy dữ liệu:

```powershell
Expand-Archive -LiteralPath "<download_dir>\green-taxi-full-v1.zip" `
  -DestinationPath "<download_dir>" -Force

New-Item -ItemType Directory -Force "data/raw" | Out-Null
Copy-Item -Recurse -Force "<download_dir>\green-taxi-full-v1\tlc" "data/raw\"
Copy-Item -Recurse -Force "<download_dir>\green-taxi-full-v1\synthetic" "data/raw\"
```

Expected structure:

```text
data/raw/
├── tlc/year=YYYY/month=MM/green_tripdata_YYYY-MM.csv
└── synthetic/
    ├── driver_hr/
    ├── fleet/
    ├── dispatch/
    └── trip_assignment/
```

Raw data là bất biến và bị Git ignore. Không sửa file nguồn để làm pipeline pass.

### 4. Dựng data services

```powershell
docker compose up -d
docker compose ps
```

Bốn service `mysql_hr`, `mongodb_fleet`, `postgres_dispatch` và
`postgres_warehouse` phải ở trạng thái healthy.

### 5. Seed source systems và chạy pipeline

```powershell
python scripts/seed_mysql_hr.py --release-id green-taxi-full-v1
python scripts/seed_mongodb_fleet.py --release-id green-taxi-full-v1
python scripts/seed_postgres_dispatch.py --release-id green-taxi-full-v1

python scripts/apply_warehouse_ddl.py --mode docker
python scripts/load_staging.py --release-id green-taxi-full-v1 --source all
python scripts/load_nds.py --release-id green-taxi-full-v1
python scripts/load_dds.py --release-id green-taxi-full-v1
python scripts/validate_warehouse_pipeline.py --release-id green-taxi-full-v1
```

Expected full-release evidence:

| Check | Expected |
|---|---:|
| Source-to-staging rows | `4.768.237` |
| DDS trips | `2.304.276` |
| DDS completed shifts | `157.379` |
| Total revenue | `48.535.884,47 USD` |
| Duplicate DDS trip/shift keys | `0 / 0` |

Chi tiết bằng chứng xem
[../evidence/full-release-reconciliation.md](../evidence/full-release-reconciliation.md).

### 6. Dựng Superset

Mỗi thành viên tự sinh credential local:

```powershell
python -m scripts.init_superset_env
python -m scripts.setup_superset_warehouse
docker compose --env-file .env.superset -f docker-compose.superset.yml up -d --build
```

Không tạo `.env.superset` bằng cách copy credential của người khác. Template
[configs/superset.env.example](../../configs/superset.env.example) chỉ mô tả tên
biến và chứa placeholder.

### 7. Chạy smoke tests

```powershell
python -m scripts.smoke_test_superset
python -m unittest discover -s tests -v
```

Smoke test xác nhận health, REST login, 6 datasets, 51 metric instances,
32 charts, dashboard, analytics queries, native time filter lỗi không được
provision trên Superset 6.1.0 và BI login bị từ chối khi đọc DDS hoặc thử ghi
dữ liệu.

### 8. Lấy login khi cần

```powershell
python -m scripts.show_superset_login
```

Không chụp, paste vào chat, issue, tài liệu hoặc commit output của lệnh này.
Dashboard local:

```text
http://localhost:8088/superset/dashboard/green-taxi-driver-operations/
```

## Credential rotation

Nếu credential Superset đã bị lộ hoặc chia sẻ, thực hiện full local rotation.
Quy trình này xóa metadata Superset local rồi bootstrap lại dashboard chuẩn:

```powershell
docker compose --env-file .env.superset -f docker-compose.superset.yml down
docker volume rm green_taxi_superset_metadata_data
Remove-Item -LiteralPath .env.superset
python -m scripts.init_superset_env
python -m scripts.setup_superset_warehouse
docker compose --env-file .env.superset -f docker-compose.superset.yml up -d --build
python -m scripts.smoke_test_superset
```

Không xóa volume nếu cần giữ dashboard edits chưa được đưa vào bootstrap.
Trường hợp đó phải backup metadata trước theo Superset runbook.

Nếu credential trong `.env` của source/warehouse bị lộ, đổi các giá trị local
và tái tạo các volume database liên quan theo kế hoạch reload của nhóm. Không
chỉ sửa file `.env` vì database volume hiện hữu vẫn có thể giữ credential cũ.

## Optional tools

Pipeline dry-run:

```powershell
python scripts/run_pipeline.py --release-id green-taxi-full-v1 --dry-run
```

Streamlit control panel:

```powershell
streamlit run app/streamlit_app.py
```

Control Panel phục vụ vận hành kỹ thuật; Superset là dashboard nghiệp vụ độc lập.

## Security rules

- Không commit `.env`, `.env.superset`, raw/full data, dump hoặc Docker volume.
- Không ghi credential thật vào README, runbook, report, screenshot hoặc log.
- Không chạy generator full release trong onboarding; generator chỉ dành cho
  Data Owner.
- Trước khi commit, chạy `git status` và `git check-ignore`.

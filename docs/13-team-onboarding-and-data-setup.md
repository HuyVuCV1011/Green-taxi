# Team Onboarding and Data Setup

## Mục đích

Tài liệu này giúp thành viên mới hiểu:

- Bài toán nghiệp vụ và kiến trúc hiện hành.
- Phần nào đã triển khai và phần nào mới được phê duyệt thiết kế.
- Cách lấy cùng một full dataset từ Google Drive.
- Vai trò của data release, source systems và PostgreSQL warehouse.
- Quy trình sample mode và full mode.
- Quy tắc seed, checksum, ownership và pull request.

## Bối cảnh ngắn

Dự án tích hợp NYC Green Taxi trips với các nguồn vận hành để xây dựng Driver
Operations DDS cho quản lý đội xe/tài xế. Phạm vi dữ liệu là 01/2020-07/2021.

- TLC trips và taxi-zone lookup là dữ liệu thật.
- Driver, vehicle, shift, assignment và HR changes là synthetic.
- Source interfaces dự kiến: file, MySQL, MongoDB và PostgreSQL nguồn.
- Warehouse đích: PostgreSQL `Staging -> DQ/Audit -> NDS -> DDS`.
- Không sử dụng ODS, MinIO, streaming hoặc CDC trong scope chính.

Synthetic data không mô tả tài xế hoặc phương tiện thật. Các phân tích chỉ có ý
nghĩa trong phạm vi case study.

## Trạng thái triển khai

Đã có:

- Canonical synthetic release, manifest, checksum và validation report.
- Repository sample và unit tests.
- Scope, contracts, architecture, ADR và implementation plan.

Chưa có:

- Docker Compose cho source systems/warehouse.
- MySQL, MongoDB và PostgreSQL source seed scripts.
- Source adapters và PostgreSQL staging pipeline.
- NDS, DDS và dashboard.

Không làm theo các command Docker/seed chưa xuất hiện trong repository. Khi
Milestone 2 được triển khai, README này phải được cập nhật bằng command thật đã
được test.

## Kiến trúc mà thành viên cần hiểu

```text
Google Drive canonical release
        |
        +--> seed Driver HR ----------> MySQL
        +--> seed Fleet -------------> MongoDB
        +--> seed Dispatch/Assignment -> PostgreSQL source
        `--> provide TLC/lookup files -> File batch source

Source adapters
        |
        v
PostgreSQL warehouse: Staging -> DQ/Audit -> NDS -> DDS
```

Google Drive release là bản phân phối dữ liệu chuẩn, không phải hệ thống nghiệp
vụ. MySQL/MongoDB/PostgreSQL nguồn là môi trường mô phỏng được seed lại từ
release. Không chia sẻ database volume giữa các thành viên.

## Repository chứa gì

GitHub là nguồn chuẩn cho:

- Python source code và SQL.
- Docker/config mẫu không chứa secret.
- Tài liệu thiết kế, ADR và source-to-target mapping.
- Seed/ingestion scripts khi Milestone 2 được triển khai.
- Sample data nhỏ dùng cho test và review.
- Lookup nhỏ được phép phân phối.
- Manifest, checksum và validation report.

GitHub không phải nguồn chuẩn cho:

- TLC raw files đầy đủ.
- Full synthetic outputs.
- Dữ liệu trung gian hoặc processed.
- MySQL/MongoDB/PostgreSQL data volumes.
- Secret, password hoặc file `.env`.

Các nhóm dữ liệu lớn đã bị loại khỏi Git bằng `.gitignore`.

## Thứ tự đọc dành cho thành viên mới

1. `README.md`: tổng quan, trạng thái và quy tắc repository.
2. `docs/03-scope.md`: mục tiêu, người dùng và giới hạn bài toán.
3. `docs/04-data-sources.md`: nguồn thật/synthetic và source interfaces.
4. `docs/05-architecture.md`: release, source systems và warehouse layers.
5. `docs/08-data-contracts.md`: release/operational/staging contracts.
6. `docs/10-source-to-target-plan.md`: mapping dữ liệu và lineage.
7. `docs/11-work-breakdown.md`: milestone và ownership.
8. `docs/12-synthetic-generation-report.md`: quy mô và validation hiện tại.
9. `docs/decisions/ADR-005-heterogeneous-source-simulation.md`: quyết định mô
   phỏng nguồn không đồng nhất.

## Hai chế độ làm việc

### Sample mode

Sample mode dành cho review code, CI và phát triển logic không cần full
infrastructure. Dữ liệu trong `data/sample/` được clone cùng repository.

```powershell
git clone https://github.com/HuyVuCV1011/Green-taxi.git
cd Green-taxi
python -m unittest discover -s tests -v
```

Sample mode phải chạy được mà không cần Google Drive, MySQL, MongoDB hoặc toàn
bộ source containers.

### Full mode

Full mode dùng để seed source systems, chạy ETL, đối soát và xây dashboard.
Team lead phát hành một dataset cố định trên Google Drive; mọi thành viên phải
tải đúng release này. Thành viên không tự sinh lại synthetic data.

Sau khi Milestone 2 hoàn tất, full mode dự kiến gồm:

1. Tải và kiểm checksum release.
2. Dựng source services và warehouse bằng Docker Compose.
3. Chạy idempotent source seed.
4. Reconcile release với source systems.
5. Chạy source adapters để load staging.
6. Reconcile source extract với staging.
7. Chạy DQ, NDS, DDS và analytics pipeline.

## Kho full data của nhóm

Google Drive là nguồn phân phối full dataset chính thức. Team lead cập nhật URL
sau khi upload và cấp quyền cho tài khoản từng thành viên:

| Thuộc tính | Giá trị |
|---|---|
| Storage provider | `Google Drive` |
| Folder hoặc URL | https://drive.google.com/drive/folders/1a9wjCly_R1c_sTSq89cONAE-rCWmwuiZ |
| Data release hiện hành | `green-taxi-full-v1` |
| File cần tải | `green-taxi-full-v1.zip`, `green-taxi-full-v1.zip.sha256` |
| SHA-256 của zip | `e916e88b2e67fa90d5a5b536c3ac7c82a4f6b21fbfb01735e8c5e5e254be7b01` |
| Phạm vi TLC | `2020-01 đến 2021-07` |
| Generator seed | `20260613` |
| Người quản lý release | `Team lead / data owner` |

Không ghi access token hoặc password vào Git. Quyền truy cập được cấp trực tiếp
qua tài khoản của từng thành viên.

## Cách tải, kiểm tra và giải nén full data

Thành viên chỉ cần tải hai file từ Google Drive:

```text
green-taxi-full-v1.zip
green-taxi-full-v1.zip.sha256
```

Không tải lẻ từng file CSV/JSONL/TSV nếu không có lý do đặc biệt. Tải nguyên
file zip giúp giữ đúng cấu trúc thư mục, tránh thiếu tháng dữ liệu và dễ kiểm
checksum.

Đề xuất đặt file zip tạm ở ngoài repository, ví dụ:

```text
D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1.zip
D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1.zip.sha256
```

Kiểm tra checksum trên Windows PowerShell:

```powershell
Get-FileHash "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1.zip" -Algorithm SHA256
Get-Content "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1.zip.sha256"
```

Hash trả về phải là:

```text
e916e88b2e67fa90d5a5b536c3ac7c82a4f6b21fbfb01735e8c5e5e254be7b01
```

Nếu checksum không khớp, xóa file zip vừa tải và tải lại từ Google Drive. Không
seed source systems hoặc chạy full pipeline bằng release bị sai checksum.

Giải nén zip:

```powershell
Expand-Archive -LiteralPath "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1.zip" -DestinationPath "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao" -Force
```

Sau khi giải nén sẽ có thư mục:

```text
D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1\
```

Copy dữ liệu vào repository theo đúng mapping:

```text
green-taxi-full-v1\tlc        -> green-taxi-bi-project\data\raw\tlc
green-taxi-full-v1\synthetic  -> green-taxi-bi-project\data\raw\synthetic
```

Có thể dùng File Explorer để copy thủ công, hoặc dùng PowerShell:

```powershell
New-Item -ItemType Directory -Force "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-bi-project\data\raw" | Out-Null
Copy-Item -Recurse -Force "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1\tlc" "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-bi-project\data\raw\"
Copy-Item -Recurse -Force "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-full-v1\synthetic" "D:\Master\Ứng dụng trí tuệ kinh doanh nâng cao\green-taxi-bi-project\data\raw\"
```

Không commit các file trong `data/raw/`. Thư mục này là dữ liệu local của từng
thành viên và đã được loại khỏi Git.

## Cấu trúc data release

```text
green-taxi-full-v1/
|-- README.txt
|-- SHA256SUMS.txt
|-- metadata/
|   |-- synthetic_generation_manifest.json
|   `-- synthetic_validation_report.json
|-- lookup/
|   |-- taxi_zone.csv
|   `-- vendor.csv
|-- tlc/
|   `-- year=YYYY/month=MM/green_tripdata_YYYY-MM.csv
`-- synthetic/
    |-- driver_hr/
    |   |-- drivers.csv
    |   `-- driver_changes.jsonl
    |-- fleet/
    |   `-- vehicles.jsonl
    |-- dispatch/
    |   `-- shifts.tsv
    `-- trip_assignment/
        |-- assignment_exceptions.csv
        `-- year=YYYY/month=MM/trip_assignment_YYYY-MM.csv
```

Các file synthetic là seed artifacts:

| Release artifact | Source system được seed |
|---|---|
| `drivers.csv`, `driver_changes.jsonl` | MySQL Driver HR |
| `vehicles.jsonl` | MongoDB Fleet |
| `shifts.tsv`, `trip_assignment/*.csv` | PostgreSQL Dispatch |
| `tlc/*.csv`, lookup | Giữ dạng file batch |

Sau khi tải và giải nén:

```text
green-taxi-bi-project/
`-- data/
    `-- raw/
        |-- tlc/
        `-- synthetic/
```

`metadata/`, `lookup/`, `README.txt` và `SHA256SUMS.txt` trong release dùng để
đối chiếu/audit. Các bản metadata và lookup cần thiết cho repository đã được
commit trong `data/metadata/` và `data/lookup/`; không cần copy đè nếu không có
hướng dẫn từ data owner.

Không đổi tên hoặc chỉnh sửa file trong release.

Checklist sau khi setup full data:

1. `data/raw/tlc/` tồn tại và có thư mục `year=2020` và `year=2021`.
2. `data/raw/synthetic/driver_hr/drivers.csv` tồn tại.
3. `data/raw/synthetic/fleet/vehicles.jsonl` tồn tại.
4. `data/raw/synthetic/dispatch/shifts.tsv` tồn tại.
5. `data/raw/synthetic/trip_assignment/` tồn tại và có dữ liệu theo tháng.
6. `git status` không hiển thị raw data để commit.

Quy ước thời gian cho implementation:

- Timestamp nghiệp vụ được hiểu theo `America/New_York`.
- Timestamp audit/load dùng UTC.
- Không cấu hình container timezone rồi dựa vào implicit conversion.
- Chi tiết nằm trong `docs/08-data-contracts.md`.

## Kiểm tra phiên bản dữ liệu

Nguồn chuẩn để đối chiếu:

- `data/metadata/synthetic_generation_manifest.json`
- `data/metadata/synthetic_validation_report.json`
- `docs/12-synthetic-generation-report.md`
- `SHA256SUMS.txt` trong Google Drive release

Thành viên không seed source systems nếu checksum không khớp. Sau seed, row
counts và content hashes phải reconcile với release trước khi ingestion chạy.

Chỉ data owner được tạo release mới. Mỗi release phải:

1. Có tên phiên bản mới, không ghi đè release cũ.
2. Ghi rõ phạm vi TLC và generator seed.
3. Có `SHA256SUMS.txt`.
4. Chạy full validator thành công.
5. Cập nhật manifest, validation report và generation report.
6. Được một thành viên khác kiểm tra trước khi công bố.

## Seed và database ownership

Source seeding phải idempotent: chạy lại cùng release không tạo duplicate hoặc
thay đổi business data. Release metadata được lưu riêng với source tables hoặc
collections.

- MySQL HR, MongoDB Fleet và PostgreSQL Dispatch là disposable local services.
- PostgreSQL warehouse là service đích riêng, không dùng chung database với
  Dispatch.
- Mỗi thành viên tự quản lý local volumes và có thể dựng lại từ release.
- Không upload database volume lên Drive hoặc GitHub.
- Không sửa hoặc xóa thư mục TLC/data gốc nằm ngoài repository.

## Quyền sử dụng generator

Generator được version-control để audit thuật toán và để data owner tạo release
mới khi cần. Nó không phải bước onboarding. Thành viên không chạy generator để
tạo bản full data riêng.

Data owner mới chạy:

```powershell
python scripts/generate_synthetic_sources.py
python scripts/validate_synthetic_sources.py
python scripts/create_repository_samples.py
python -m unittest discover -s tests -v
```

Sau đó data owner đóng gói, tạo checksums, upload Google Drive và cập nhật URL,
tên release cùng các báo cáo liên quan.

## Quy trình làm việc của thành viên

Trước khi bắt đầu:

1. Pull code mới nhất.
2. Đọc milestone/issue được giao.
3. Chạy sample tests.
4. Nếu cần full mode, xác nhận release ID và checksum.
5. Chỉ chạy source seed/ingestion bằng scripts đã được commit và review.

Trước khi tạo pull request:

1. Không có raw/processed data, database volume hoặc secret.
2. Tests liên quan đã pass.
3. Seed/ingestion change có idempotency test.
4. Connector change không làm thay đổi staging contract ngoài chủ đích.
5. Schema/data contract/source-to-target được cập nhật cùng nhau.
6. Pull request ghi rõ test bằng sample hay full mode và release ID đã dùng.

## Ownership

| Hạng mục | Owner |
|---|---|
| GitHub, branch policy và release docs | Team lead |
| Canonical data release và checksums | Data owner |
| Source seed scripts và adapters | Ingestion owner |
| Warehouse schema, DQ, NDS và DDS | Warehouse owner |
| Local `.env`, raw files và volumes | Mỗi thành viên |

Khi chưa biết file có được commit hay không, kiểm tra `.gitignore` và hỏi owner
trước khi dùng `git add -f`.

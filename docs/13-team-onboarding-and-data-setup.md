# Team Onboarding and Data Setup

## Mục đích

Tài liệu này giúp thành viên mới hiểu:

- Dự án đang giải quyết bài toán gì.
- Nên đọc tài liệu theo thứ tự nào.
- Thành phần nào được lưu trên GitHub.
- Full data được lưu ở đâu và đặt vào repository như thế nào.
- Cách xác nhận mọi thành viên đang dùng cùng một phiên bản dữ liệu.

## Bối cảnh ngắn

Dự án tích hợp NYC Green Taxi trips với các nguồn vận hành để xây dựng Driver
Operations DDS cho quản lý đội xe/tài xế. Phạm vi dữ liệu là 01/2020-07/2021.

- TLC trips và taxi-zone lookup là dữ liệu thật.
- Driver, vehicle, shift, assignment và HR changes là synthetic.
- Kiến trúc là `Staging -> DQ/Audit -> NDS -> DDS`.
- Không sử dụng ODS.

Synthetic data không mô tả tài xế hoặc phương tiện thật. Các phân tích chỉ có ý
nghĩa trong phạm vi case study.

## Repository chứa gì

GitHub là nguồn chuẩn cho:

- Python source code và SQL.
- Docker/config mẫu không chứa secret.
- Tài liệu thiết kế, ADR và source-to-target mapping.
- Sample data nhỏ dùng cho test và review.
- Lookup nhỏ được phép phân phối.
- Manifest, checksum và validation report.

GitHub không phải nguồn chuẩn cho:

- TLC raw files đầy đủ.
- Full synthetic outputs.
- Dữ liệu trung gian hoặc processed.
- PostgreSQL data volume.
- Secret, password hoặc file `.env`.

Các nhóm dữ liệu lớn đã bị loại khỏi Git bằng `.gitignore`.

## Thứ tự đọc dành cho thành viên mới

1. `README.md`: tổng quan và quy tắc repository.
2. `docs/03-scope.md`: mục tiêu, người dùng và giới hạn bài toán.
3. `docs/04-data-sources.md`: nguồn nào thật, nguồn nào synthetic.
4. `docs/05-architecture.md`: luồng Staging đến DDS.
5. `docs/08-data-contracts.md`: schema và quy tắc từng nguồn.
6. `docs/10-source-to-target-plan.md`: mapping dữ liệu.
7. `docs/11-work-breakdown.md`: trạng thái milestone và ownership.
8. `docs/12-synthetic-generation-report.md`: quy mô và validation hiện tại.

Khi có quyết định thiết kế mới, đọc thêm ADR tương ứng trong `docs/decisions/`.

## Hai chế độ làm việc

### Sample mode

Sample mode dành cho review code, phát triển logic nhỏ và CI. Dữ liệu trong
`data/sample/` được clone cùng repository.

```powershell
git clone <repository-url>
cd green-taxi-bi-project
python -m unittest discover -s tests -v
```

Sample mode phải chạy được mà không cần truy cập kho full data.

### Full-data mode

Full-data mode dùng để sinh synthetic sources, chạy toàn bộ ETL, đối soát và
xây dashboard. Thành viên cần lấy cùng một data release từ kho chung của nhóm
hoặc tái tạo nó từ đúng TLC source package.

Full data sau khi tải hoặc sinh phải nằm dưới `data/raw/`. Nội dung thư mục này
không xuất hiện trong `git status` và không được dùng `git add -f`.

## Kho full data của nhóm

Nhóm chọn một kho chung có phân quyền, ví dụ Google Drive, OneDrive hoặc object
storage. Team lead điền thông tin chính thức trước khi bàn giao:

| Thuộc tính | Giá trị |
|---|---|
| Storage provider | `TBD - Google Drive/OneDrive/object storage` |
| Folder hoặc URL | `TBD - chỉ chia sẻ trong nhóm` |
| Data release hiện hành | `synthetic-full-v1` |
| Phạm vi TLC | `2020-01 đến 2021-07` |
| Generator seed | `20260613` |
| Người quản lý release | `TBD - team lead/data owner` |

Không ghi access token hoặc password vào tài liệu này. Quyền truy cập được cấp
trực tiếp qua tài khoản của từng thành viên.

## Cấu trúc data release

Gói chia sẻ nên giữ nguyên cấu trúc thư mục, ví dụ:

```text
synthetic-full-v1/
|-- README.txt
|-- SHA256SUMS.txt
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

Sau khi tải và giải nén:

```text
green-taxi-bi-project/
`-- data/
    `-- raw/
        |-- tlc/
        `-- synthetic/
```

PostgreSQL database files không cần chia sẻ giữa các thành viên. Mỗi người tạo
database local bằng Docker Compose và load lại từ raw data để pipeline có thể
tái lập.

## Kiểm tra phiên bản dữ liệu

Nguồn chuẩn để đối chiếu full synthetic data:

- `data/metadata/synthetic_generation_manifest.json`
- `data/metadata/synthetic_validation_report.json`
- `docs/12-synthetic-generation-report.md`

Manifest ghi seed, số dòng và SHA-256 của source/assignment files. Thành viên
không tiếp tục chạy full pipeline nếu checksum hoặc row count không khớp.

Data release mới phải:

1. Có tên phiên bản mới, không ghi đè release cũ.
2. Ghi rõ phạm vi TLC và generator seed.
3. Có file checksum.
4. Chạy `validate_synthetic_sources.py` thành công.
5. Cập nhật manifest, validation report và tài liệu nếu số liệu thay đổi.
6. Được ít nhất một thành viên khác kiểm tra trước khi công bố.

## Tái tạo full synthetic data

Generator hiện đọc đường dẫn trong `configs/synthetic_generation.json`. Đường
dẫn mặc định trỏ đến TLC package nằm ngoài repository:

```text
../01_Datasets/raw_trip_data/
```

Thành viên tái tạo dữ liệu phải đặt TLC package tại đường dẫn đó hoặc tạo một
config local có các đường dẫn phù hợp. Không commit đường dẫn cá nhân hoặc dữ
liệu nguồn vào Git.

Chạy tại repository root:

```powershell
python scripts/generate_synthetic_sources.py
python scripts/validate_synthetic_sources.py
python scripts/create_repository_samples.py
python -m unittest discover -s tests -v
```

Không chạy `create_repository_samples.py` và commit sample mới nếu không có chủ
đích phát hành một data version mới, vì sample là fixture chung của cả nhóm.

## Quy trình làm việc của thành viên

Trước khi bắt đầu:

1. Pull code mới nhất.
2. Đọc milestone và issue được giao.
3. Chạy sample tests.
4. Xác nhận data release nếu công việc cần full data.

Trước khi tạo pull request:

1. Không có raw/processed data hoặc secret trong thay đổi.
2. Tests liên quan đã pass.
3. SQL/schema/data contract được cập nhật cùng nhau khi interface thay đổi.
4. Quyết định kiến trúc quan trọng có ADR hoặc note trong docs.
5. Pull request ghi rõ chạy bằng sample hay full data.

## Ownership

- GitHub repository: code owner/team lead quản lý branch và review.
- Data release: data owner tạo gói, checksum và validation report.
- Mỗi thành viên: tự quản lý `data/raw/`, `.env` và PostgreSQL volume local.
- Không sửa hoặc xóa thư mục dữ liệu gốc nằm ngoài repository.

Khi chưa biết một file có được commit hay không, kiểm tra `.gitignore` và hỏi
data owner trước khi dùng `git add -f`.

# Diagrams & Visualizations

Thư mục này quản lý các sơ đồ đã xuất bản của dự án. Kiến trúc runtime canonical
nằm trong [../docs/architecture/system-architecture.md](../docs/architecture/system-architecture.md); README này chỉ
là index artifact hiện có, không phải nguồn thiết kế độc lập.

> [!TIP]
> Bạn có thể lưu các file thiết kế gốc dạng `.drawio` cùng với các tệp ảnh định dạng `.png` hoặc `.svg` được xuất ra tại đây. Mỗi sơ đồ bắt buộc phải nhất quán với các quyết định kiến trúc đã chốt (ADR) và các tài liệu thiết kế liên quan.

---

## Artifact hiện có

| File | Vai trò |
|---|---|
| `nds_schema.dbml` / `nds_schema.png` | Mô hình NDS |
| `dds_schema.dbml` / `dds_schema.png` | Mô hình DDS |
| `analytics_semantic_model.mmd` | Semantic model analytics/Superset |

---

## Sơ đồ chưa tách thành artifact riêng

Các sơ đồ triển khai vật lý, runtime data flow, setup/reproducibility và source ERD
hiện được mô tả trong `README.md`, `docs/architecture/system-architecture.md`,
`docs/setup/local-reproducibility.md` và `docs/contracts/source-data-contracts.md`. Nếu
cần nộp riêng dạng ảnh, xuất artifact tại đây và cập nhật bảng trên.

---

## Reference Mermaid snippets

Các snippet dưới đây chỉ phục vụ tham khảo khi cần xuất sơ đồ mới. Nếu khác tài
liệu canonical, ưu tiên tài liệu canonical và cập nhật snippet sau.

### 1. Kiến trúc luồng dữ liệu runtime (Runtime Data Flow)
```mermaid
flowchart TD
    subgraph Sources["Môi trường nguồn mô phỏng (Source Systems)"]
        direction LR
        MySQL[("MySQL<br>(Driver HR Database)")]
        Mongo[("MongoDB<br>(Fleet Collection)")]
        PG_Src[("PostgreSQL Source<br>(Dispatch/Assignment)")]
        Files[("Local Directory<br>(TLC Trips & Lookup Files)")]
    end

    subgraph DWH["PostgreSQL Warehouse"]
        STG[("Staging Schema<br>(Raw Mirror Tables)")]

        subgraph Pipeline["Data Quality & Integration Engine"]
            direction TB
            DQ{"DQ & Audit Gate"}
            Q_Table[("Quarantine Schema<br>(Rejected Records)")]
            NDS[("NDS Schema<br>(Normalized Data Store)")]
            DDS[("DDS Schema<br>(Driver Operations Star Schema)")]
        end
    end

    subgraph Presentation["Tầng trình diễn & Phân tích (BI Layer)"]
        BI[("Apache Superset /<br>Approved BI Client")]
    end

    MySQL -->|"Extract"| STG
    Mongo -->|"Extract"| STG
    PG_Src -->|"Extract"| STG
    Files -->|"Ingest"| STG

    STG --> DQ
    DQ -->|"Lỗi (Schema, PK, FK, Range)"| Q_Table
    DQ -->|"Hợp lệ"| NDS
    NDS -->|"SCD Type 1/2"| DDS
    DDS -->|"Certified datasets"| BI
```

### 2. Luồng setup/reproducibility

```mermaid
flowchart LR
    GD[("Google Drive Release<br>green-taxi-full-v1.zip")]
    RAW["data/raw/"]
    MySQL[("mysql_hr")]
    Mongo[("mongodb_fleet")]
    Dispatch[("postgres_dispatch")]
    Warehouse[("postgres_warehouse")]

    GD -->|"Download, checksum, extract"| RAW
    RAW -->|"seed_mysql_hr.py"| MySQL
    RAW -->|"seed_mongodb_fleet.py"| Mongo
    RAW -->|"seed_postgres_dispatch.py"| Dispatch
    RAW -->|"TLC/lookup files"| Warehouse
    MySQL -->|"load_staging.py"| Warehouse
    Mongo -->|"load_staging.py"| Warehouse
    Dispatch -->|"load_staging.py"| Warehouse
```

### 3. Mô hình thực thể liên kết nguồn (Source ERD Schema)
Mô tả quan hệ nghiệp vụ thô trước khi nạp vào staging và kho dữ liệu:

```mermaid
erDiagram
    DRIVERS {
        string driver_id PK "DRV######"
        int vendor_id
        string driver_code
        string employment_status
        string license_status
        date license_expiry_date
    }
    DRIVER_CHANGES {
        string event_id PK "DRVCHG######"
        string driver_id FK
        string event_type
        timestamp effective_at
        timestamp delivered_at
        json changes
    }
    VEHICLES {
        string vehicle_id PK "VEH######"
        int vendor_id
        string plate_token UK
        int model_year
        string vehicle_type
        date service_start_date
        date last_inspection_date
    }
    SHIFTS {
        string shift_id PK "SHF##########"
        string driver_id FK "Join to MySQL HR"
        string vehicle_id FK "Join to MongoDB Fleet"
        int vendor_id
        timestamp shift_start
        timestamp shift_end
        int trip_count
    }
    TRIP_ASSIGNMENTS {
        string trip_key PK "SHA-256 truncated key"
        string source_file
        int source_row_number
        string shift_id FK
        string driver_id FK
        string vehicle_id FK
        timestamp assignment_timestamp
        string assignment_method
    }
    GREEN_TRIPS {
        string source_file PK "TLC CSV file"
        int source_row_number PK "CSV physical row"
        int vendor_id
        timestamp lpep_pickup_datetime
        timestamp lpep_dropoff_datetime
        decimal total_amount
    }

    DRIVERS ||--o{ DRIVER_CHANGES : "tracks historical changes"
    DRIVERS ||--o{ SHIFTS : "performs"
    VEHICLES ||--o{ SHIFTS : "allocated in"
    SHIFTS ||--o{ TRIP_ASSIGNMENTS : "contains"
    GREEN_TRIPS ||--o| TRIP_ASSIGNMENTS : "linked by source file and row"
```

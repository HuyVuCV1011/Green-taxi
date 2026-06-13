# Diagrams & Visualizations

Thư mục này quản lý các sơ đồ kiến trúc, luồng dữ liệu và mô hình thực thể liên kết (ERD) của dự án.

> [!TIP]
> Bạn có thể lưu các file thiết kế gốc dạng `.drawio` cùng với các tệp ảnh định dạng `.png` hoặc `.svg` được xuất ra tại đây. Mỗi sơ đồ bắt buộc phải nhất quán với các quyết định kiến trúc đã chốt (ADR) và các tài liệu thiết kế liên quan.

---

## Danh mục sơ đồ cần có (Diagram Catalog)

1. **Sơ đồ triển khai vật lý (Physical Deployment Diagram):** Mô tả các container Docker (`mysql_hr`, `mongodb_fleet`, `postgres_dispatch`, `postgres_warehouse`), ánh xạ cổng và mạng nội bộ `green_taxi_net`.
2. **Sơ đồ luồng dữ liệu logic (Logical Data Flow Diagram):** Mô tả các bước chuyển đổi dữ liệu từ gói seed Google Drive -> Nguồn mô phỏng -> Staging -> DQ -> NDS -> DDS -> Power BI.
3. **Mô hình thực thể liên kết nguồn (Source ERD):** Mô tả mối quan hệ giữa các bảng nghiệp vụ giả lập và dữ liệu chuyến đi thực tế.

---

## Các Mermaid Snippets mẫu

Dưới đây là mã Mermaid của các sơ đồ cốt lõi, bạn có thể sử dụng các extension hoặc github viewer để render trực tiếp:

### 1. Kiến trúc luồng dữ liệu logic (Logical Data Flow)
```mermaid
flowchart TD
    subgraph Distribution["Phân phối dữ liệu (Tái lập môi trường local)"]
        GD[("Google Drive Release Package<br>(green-taxi-full-v1)")]
    end

    subgraph Sources["Môi trường nguồn mô phỏng (Source Systems)"]
        direction LR
        MySQL[("MySQL<br>(Driver HR Database)")]
        Mongo[("MongoDB<br>(Fleet Collection)")]
        PG_Src[("PostgreSQL Source<br>(Dispatch/Assignment)")]
        Files[("Local Directory<br>(TLC Trips & Lookup Files)")]
    end

    subgraph DWH["PostgreSQL Warehouse (Kho dữ liệu tích hợp)"]
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
        PBI[("Power BI Dashboard /<br>Anomaly Analysis")]
    end

    %% Luồng liên kết
    GD -.->|"Seed HR Data"| MySQL
    GD -.->|"Seed Fleet Data"| Mongo
    GD -.->|"Seed Dispatch Data"| PG_Src
    GD -.->|"Unpack Raw Files"| Files

    MySQL -->|"Extract"| STG
    Mongo -->|"Extract"| STG
    PG_Src -->|"Extract"| STG
    Files -->|"Ingest"| STG

    STG --> DQ
    DQ -->|"Lỗi (Schema, PK, FK, Range)"| Q_Table
    DQ -->|"Hợp lệ"| NDS
    NDS -->|"SCD Type 1/2"| DDS
    DDS -->|"Analyze"| PBI
```

### 2. Mô hình thực thể liên kết nguồn (Source ERD Schema)
Mô tả quan hệ nghiệp vụ thô trước khi nạp vào staging và kho dữ liệu:

```mermaid
erDiagram
    DRIVERS {
        int driver_id PK "Natural Key (MySQL HR)"
        string name
        string license_no
        string status
    }
    DRIVER_CHANGES {
        int event_id PK "MySQL HR"
        int driver_id FK
        string change_type
        timestamp event_timestamp
    }
    VEHICLES {
        string vehicle_id PK "Natural Key (MongoDB Fleet)"
        string model
        string type
        date last_inspection_date
    }
    SHIFTS {
        string shift_id PK "Natural Key (PostgreSQL Dispatch)"
        int driver_id FK "Join to MySQL HR"
        string vehicle_id FK "Join to MongoDB Fleet"
        timestamp shift_start_at
        timestamp shift_end_at
    }
    TRIP_ASSIGNMENTS {
        string assignment_id PK "PostgreSQL Dispatch"
        string shift_id FK
        int trip_id FK "Join to TLC Trip"
        string assignment_method
    }
    GREEN_TRIPS {
        int trip_id PK "TLC LPEP Trip CSV File"
        int vendor_id
        timestamp lpep_pickup_datetime
        timestamp lpep_dropoff_datetime
        double fare_amount
    }

    DRIVERS ||--o{ DRIVER_CHANGES : "tracks historical changes"
    DRIVERS ||--o{ SHIFTS : "performs"
    VEHICLES ||--o{ SHIFTS : "allocated in"
    SHIFTS ||--o{ TRIP_ASSIGNMENTS : "contains"
    GREEN_TRIPS ||--o| TRIP_ASSIGNMENTS : "linked via"
```

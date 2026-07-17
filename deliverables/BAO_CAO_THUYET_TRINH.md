# Sổ tay báo cáo và bảo vệ code — NYC Green Taxi Driver Operations BI

> Mục đích: dùng khi thuyết trình, demo và trả lời phản biện. Tài liệu này không
> thay thế báo cáo học thuật; nó giúp tìm nhanh **nội dung cần nói**, **code nằm ở
> đâu**, **vì sao thiết kế như vậy**, **bằng chứng nào chứng minh**, và **giới hạn
> nào phải thừa nhận**.

## Cách dùng trong phòng báo cáo

1. Trước buổi báo cáo, đọc theo thứ tự từ [Phần I](#phần-i-lý-thuyết-và-quyết-định-thiết-kế) đến [Phần III](#phần-iii-bộ-câu-hỏi-phản-biện).
2. Khi giáo viên hỏi “code ở đâu?”, mở [bản đồ code 30 giây](#bản-đồ-code-30-giây).
3. Khi bị hỏi “tại sao?”, trả lời theo công thức: **yêu cầu nghiệp vụ → lựa chọn
   kỹ thuật → trade-off → bằng chứng**.
4. Không đọc nguyên văn toàn bộ tài liệu. Các khối **Nói ngắn gọn** là lời thoại;
   các khối **Đào sâu** và **Hỏi vặn** dùng để phản biện.
5. Link dạng `#L...` mở đúng vùng dòng trên GitHub/IDE hỗ trợ line anchor. Nếu số
   dòng thay đổi, tìm theo tên class/hàm/SQL object được ghi cạnh link.

## Mục lục nhanh

- [Tóm tắt đồ án trong 60 giây](#tóm-tắt-đồ-án-trong-60-giây)
- [Phần I: Lý thuyết và quyết định thiết kế](#phần-i-lý-thuyết-và-quyết-định-thiết-kế)
  - [1. Bài toán và phạm vi](#1-bài-toán-và-phạm-vi)
  - [2. Dữ liệu thật, dữ liệu synthetic và tích hợp đa nguồn](#2-dữ-liệu-thật-dữ-liệu-synthetic-và-tích-hợp-đa-nguồn)
  - [3. Kiến trúc dữ liệu nhiều tầng](#3-kiến-trúc-dữ-liệu-nhiều-tầng)
  - [4. Vì sao không có ODS](#4-vì-sao-không-có-ods)
  - [5. Grain, natural key và surrogate key](#5-grain-natural-key-và-surrogate-key)
  - [6. NDS và DDS khác nhau thế nào](#6-nds-và-dds-khác-nhau-thế-nào)
  - [7. Star schema, fact và dimension](#7-star-schema-fact-và-dimension)
  - [8. Slowly Changing Dimension Type 2](#8-slowly-changing-dimension-type-2)
  - [9. Data Quality, Audit, Quarantine và Anomaly](#9-data-quality-audit-quarantine-và-anomaly)
  - [10. Idempotency, lineage và reconciliation](#10-idempotency-lineage-và-reconciliation)
  - [11. KPI và semantic contract](#11-kpi-và-semantic-contract)
  - [12. OLAP và ROLAP](#12-olap-và-rolap)
  - [13. K-Means phân nhóm tài xế](#13-k-means-phân-nhóm-tài-xế)
  - [14. Apriori và association rules](#14-apriori-và-association-rules)
  - [15. Giới hạn và giá trị của đồ án](#15-giới-hạn-và-giá-trị-của-đồ-án)
- [Phần II: Bản đồ và bảo vệ code](#phần-ii-bản-đồ-và-bảo-vệ-code)
  - [Luồng thực thi end-to-end](#luồng-thực-thi-end-to-end)
  - [Cấu trúc code và ranh giới trách nhiệm](#cấu-trúc-code-và-ranh-giới-trách-nhiệm)
  - [Sinh và kiểm định dữ liệu synthetic](#sinh-và-kiểm-định-dữ-liệu-synthetic)
  - [Seed dữ liệu vào các source system](#seed-dữ-liệu-vào-các-source-system)
  - [Khởi tạo DDL và database contract](#khởi-tạo-ddl-và-database-contract)
  - [Hạ tầng local và các script phụ trợ](#hạ-tầng-local-và-các-script-phụ-trợ)
  - [Bản đồ code 30 giây](#bản-đồ-code-30-giây)
  - [1. Pipeline orchestration](#1-pipeline-orchestration)
  - [2. Staging và adapter đa nguồn](#2-staging-và-adapter-đa-nguồn)
  - [3. DQ Gate 1 và inferred member](#3-dq-gate-1-và-inferred-member)
  - [4. SCD2 và DDS dimensions](#4-scd2-và-dds-dimensions)
  - [5. DQ Gate 2: business anomaly](#5-dq-gate-2-business-anomaly)
  - [6. Fact trip và fact shift](#6-fact-trip-và-fact-shift)
  - [7. Analytics views, KPI và chống fan-out](#7-analytics-views-kpi-và-chống-fan-out)
  - [8. Data Mining](#8-data-mining)
  - [9. Superset và Streamlit](#9-superset-và-streamlit)
  - [10. Tests và bằng chứng](#10-tests-và-bằng-chứng)
- [Phần III: Bộ câu hỏi phản biện](#phần-iii-bộ-câu-hỏi-phản-biện)
- [Kịch bản trình bày gợi ý](#kịch-bản-trình-bày-gợi-ý)
- [Checklist trước khi vào phòng](#checklist-trước-khi-vào-phòng)

---

## Tóm tắt đồ án trong 60 giây

> Đề tài của nhóm là tích hợp dữ liệu đa nguồn để phân tích hiệu quả vận hành
> tài xế NYC Green Taxi giai đoạn 2020–2021. Dữ liệu TLC thật chỉ có thông tin
> chuyến đi và doanh thu, không có tài xế, phương tiện, ca làm việc hay phân công.
> Vì vậy nhóm sinh dữ liệu vận hành synthetic có ràng buộc, sau đó seed thành các
> hệ thống nguồn độc lập gồm MySQL HR, MongoDB Fleet và PostgreSQL Dispatch.
> Pipeline Python đưa các nguồn cùng TLC file batch vào PostgreSQL Staging, áp
> dụng DQ/Audit/Quarantine, chuẩn hóa tại NDS, rồi tạo Driver Operations DDS theo
> star schema với fact chuyến đi và fact ca làm. Lớp analytics cung cấp KPI được
> định nghĩa thống nhất, ROLAP trên PostgreSQL/Superset, và hai mô hình khám phá:
> K-Means phân nhóm tài xế và Apriori tìm pattern tuyến. Kết quả hỗ trợ quản lý
> vận hành ra quyết định lịch sử; hệ thống không điều phối thời gian thực và
> không dùng dữ liệu synthetic để kết luận về tài xế thật.

Nguồn phạm vi chính: [Project Scope](../docs/context/scope.md) và
[ADR-001](../docs/decisions/ADR-001-driver-operations-scope.md).

---

# Phần I: Lý thuyết và quyết định thiết kế

## 1. Bài toán và phạm vi

### Nói ngắn gọn

Dữ liệu TLC trả lời được “chuyến đi nào, ở đâu, lúc nào, doanh thu bao nhiêu”,
nhưng không trả lời được “tài xế nào, xe nào, thuộc ca nào và hiệu suất ca ra
sao”. Đồ án bổ sung ngữ cảnh vận hành để chuyển dữ liệu chuyến đi thành thông tin
hỗ trợ quản lý tài xế và đội xe.

### Đào sâu

- **Người dùng cuối:** quản lý vận hành tài xế/đội xe, không phải marketing hay
  kế toán.
- **Đơn vị quyết định:** khu vực–giờ, tài xế, phương tiện và ca làm việc.
- **Các quyết định chính:** bố trí năng lực theo khu vực/giờ; xem ca sử dụng thời
  gian hiệu quả; tìm tài xế/xe cần xem xét; điều tra anomaly; khám phá nhóm tài
  xế và pattern tuyến.
- **Một data mart duy nhất:** Driver Operations DDS. Việc thu hẹp scope giúp KPI,
  grain và dashboard nhất quán, thay vì tạo nhiều data mart nửa vời.
- **Không nằm trong scope:** realtime dispatch, GPS, payroll, lợi nhuận ròng,
  customer segmentation, dự báo realtime, CDC/streaming và production HA.

### Hỏi vặn

**Hỏi:** Tại sao đề tài gọi là BI nâng cao chứ không chỉ là dashboard?

**Đáp:** Vì dashboard chỉ là lớp trình bày cuối. Đồ án có data contract, tích hợp
đa interface, lineage, DQ/quarantine, NDS, dimensional model, semantic metrics,
ROLAP, Data Mining và kiểm thử reconciliation. Giá trị nằm ở chuỗi biến dữ liệu
nguồn thành thông tin đáng tin cậy, không chỉ ở biểu đồ.

**Hỏi:** Hệ thống có chứng minh nơi nào “thiếu taxi” không?

**Đáp:** Không. Dữ liệu chỉ quan sát các chuyến đã được phục vụ, nên dashboard
chỉ nói **observed/served activity**. Muốn kết luận unmet demand cần thêm request
bị từ chối, thời gian chờ hoặc dữ liệu nhu cầu ngoài hệ thống.

**Hỏi:** Revenue có phải profit không?

**Đáp:** Không. `total_amount` là tiền thanh toán theo dữ liệu TLC. Đồ án không có
chi phí nhiên liệu, lương, bảo trì và overhead nên không kết luận lợi nhuận.

Tham chiếu: [Scope — bài toán và quyết định](../docs/context/scope.md#bài-toán),
[Business Questions](../docs/analytics/business-questions.md#business-questions).

## 2. Dữ liệu thật, dữ liệu synthetic và tích hợp đa nguồn

### Phân loại nguồn

| Nguồn logic | Interface vật lý | Nội dung | Bản chất |
|---|---|---|---|
| TLC/LPEP | CSV/Parquet batch | Trip, fare, tip, location, time | Dữ liệu chuyến công khai thật |
| Driver HR | MySQL | Hồ sơ và thay đổi tài xế | Synthetic |
| Fleet | MongoDB | Phương tiện và trạng thái | Synthetic |
| Dispatch | PostgreSQL nguồn | Shift và trip assignment | Synthetic |
| Warehouse | PostgreSQL đích | Staging, Audit, DQ, NDS, DDS, Analytics | Dữ liệu tích hợp |

Google Drive/release ZIP chỉ là **kênh phân phối seed package**, không phải source
system nghiệp vụ. Source PostgreSQL Dispatch và PostgreSQL warehouse là hai
service/ràng giới khác nhau dù cùng công nghệ.

### Vì sao synthetic vẫn có ý nghĩa

TLC không phát hành định danh tài xế/xe phù hợp với bài toán. Nhóm không giả vờ
đó là dữ liệu thật mà tạo dữ liệu synthetic deterministic từ trip thật, công bố
ràng buộc, seed vào interface độc lập và giữ lineage. Điều chứng minh ở đây là
năng lực thiết kế tích hợp và BI; kết luận nhân sự chỉ áp dụng cho case study.

Chỉ đổi một file CSV thành JSON không đủ gọi là đa nguồn. Dự án dùng file,
relational database và document database, có connector/adapter và source
contract riêng nhưng hội tụ về staging contract chung.

### Hỏi vặn

**Hỏi:** Synthetic data có làm kết quả mất giá trị không?

**Đáp:** Nó giới hạn **external validity**, tức không được suy rộng thành kết luận
về tài xế thật. Tuy nhiên nó vẫn phù hợp để kiểm chứng pipeline, grain, SCD, DQ,
KPI và dashboard vì generator deterministic, có contract và validation. Nhóm
phân biệt rõ “đúng về kỹ thuật trên case study” với “đúng về thực tế dân số”.

**Hỏi:** Vì sao không để synthetic ở file cho đơn giản?

**Đáp:** Nếu chỉ đổi định dạng file thì chưa thể hiện ranh giới hệ thống nghiệp
vụ. MySQL, MongoDB và PostgreSQL nguồn buộc pipeline xử lý khác biệt về kết nối,
kiểu dữ liệu và temporal semantics, trong khi downstream vẫn nhận contract chung.

**Hỏi:** Có data leakage vì synthetic được sinh từ TLC không?

**Đáp:** Assignment/shift được tạo để khớp trip nhằm xây case study vận hành, nên
không được dùng để kiểm định một giả thuyết độc lập về hành vi thật. Mục tiêu là
tái tạo quan hệ vận hành có ràng buộc để kiểm thử tích hợp; đây không phải tập
nhãn ground truth cho prediction.

Tham chiếu: [ADR-002](../docs/decisions/ADR-002-synthetic-operational-sources.md),
[ADR-005](../docs/decisions/ADR-005-heterogeneous-source-simulation.md),
[Source contracts](../docs/contracts/source-data-contracts.md).

## 3. Kiến trúc dữ liệu nhiều tầng

```text
TLC/Lookup files + MySQL HR + MongoDB Fleet + PostgreSQL Dispatch
                              |
                              v
                     PostgreSQL Staging
                              |
                              v
                   DQ / Audit / Quarantine
                              |
                              v
                             NDS
                              |
                              v
              Driver Operations DDS → Analytics → Superset
                              |
                              +→ K-Means / Apriori (exploratory)
```

### Trách nhiệm từng tầng

| Tầng | Trả lời câu hỏi gì? | Không nên làm gì? |
|---|---|---|
| Source | Dữ liệu nghiệp vụ phát sinh ở đâu? | Không phụ thuộc warehouse schema |
| Staging | Ta đã nhận chính xác dữ liệu nào từ nguồn? | Không áp KPI hay business aggregation |
| Audit | Batch nào, release nào, checksum và row count nào? | Không dùng làm business fact |
| DQ/Quarantine | Bản ghi/rule nào vi phạm? | Không âm thầm sửa hoặc drop |
| NDS | Các thực thể đa nguồn được chuẩn hóa và liên kết ra sao? | Không tối ưu riêng cho một chart |
| DDS | Grain phân tích, fact và dimension là gì? | Không trộn nhiều grain trong một fact |
| Analytics | KPI/date role/BI boundary được công bố thế nào? | Không query trực tiếp staging cho dashboard nghiệp vụ |
| Superset | Người dùng quan sát và tương tác ra sao? | Không tự định nghĩa lại KPI khác SQL contract |

### Vì sao tách tầng

Tách tầng giúp cô lập thay đổi. Source adapter có thể đổi mà NDS/DDS không phải
biết chi tiết connector; KPI có thể đổi cách hiển thị mà raw lineage vẫn giữ.
Đổi lại, kiến trúc có nhiều bảng, cần quản trị metadata và đối soát giữa tầng.

Tham chiếu: [System Architecture](../docs/architecture/system-architecture.md).

## 4. Vì sao không có ODS

**ODS (Operational Data Store)** thường tích hợp dữ liệu hiện thời để hỗ trợ tác
nghiệp với độ trễ ngắn, cập nhật thường xuyên và trạng thái gần hiện tại. Dự án
này xử lý lịch sử 2020–2021 theo batch và phục vụ phân tích, không có SLA gần
realtime hoặc use case tác nghiệp cần ODS.

Do đó kiến trúc chọn `Staging → DQ/Audit → NDS → DDS`. NDS đảm nhiệm tích hợp và
chuẩn hóa lịch sử; DDS phục vụ phân tích.

### Hỏi vặn

**Hỏi:** Không có ODS có phải thiếu một tầng DWH chuẩn không?

**Đáp:** Không có kiến trúc bắt buộc mọi hệ thống phải có ODS. Tầng chỉ nên tồn
tại khi có trách nhiệm nghiệp vụ rõ. Thêm ODS vào batch historical case study sẽ
tăng duplication và vận hành nhưng chưa tạo giá trị. Nếu sau này có daily/current
operational SLA, nhóm sẽ xem lại ADR này.

Tham chiếu: [ADR-003 — Remove ODS](../docs/decisions/ADR-003-remove-ods.md).

## 5. Grain, natural key và surrogate key

### Grain

Grain là phát biểu “một dòng đại diện cho cái gì”. Phải chốt grain trước khi
chọn dimension và measure.

- `fact_driver_trip`: một dòng cho một trip đã được gán tài xế/xe/shift.
- `fact_driver_shift`: một dòng cho một ca `COMPLETED`, đã tổng hợp trip.
- `analytics.driver_segments`: một dòng cho một driver của model run hiện hành.
- `analytics.route_association_rules`: một dòng cho một luật được công bố.

### Natural key và surrogate key

- **Natural/business key:** có ý nghĩa từ nguồn, ví dụ `driver_id`, `vehicle_id`,
  `shift_id`, `trip_id`.
- **Surrogate key:** khóa kỹ thuật do warehouse sinh, ví dụ `driver_sk` tại NDS
  hoặc `driver_key` tại DDS.
- Surrogate key tách quan hệ warehouse khỏi biến động khóa nguồn và cho phép
  nhiều phiên bản SCD2 của cùng `driver_id` khi loader đã materialize các version.

### Hỏi vặn

**Hỏi:** Tại sao fact không chỉ lưu `driver_id`?

**Đáp:** Nếu chỉ lưu natural key, fact không xác định được phiên bản thuộc tính
tài xế tại thời điểm phát sinh. `driver_key` trỏ version SCD2 theo khoảng hiệu lực
đã có trong DDS; độ đúng còn phụ thuộc loader dựng các interval chính xác.

**Hỏi:** Có thể cộng `trip_count` của fact shift với số dòng fact trip không?

**Đáp:** Có thể dùng để reconciliation nếu cùng filter và phạm vi, nhưng không
join hai fact ở row-level rồi cộng vì sẽ fan-out. Hai fact có grain khác nhau.

Tham chiếu: [DDS DDL — fact trip](../sql/warehouse/04_dds_tables.sql#L121-L159),
[DDS DDL — fact shift](../sql/warehouse/04_dds_tables.sql#L161-L189).

## 6. NDS và DDS khác nhau thế nào

### NDS — Normalized Data Store

NDS tích hợp các thực thể chuẩn hóa: vendor, location, driver, vehicle, shift,
trip và assignment. Mục tiêu là giảm dư thừa, giữ quan hệ và lineage, xử lý
business key/late-arriving master. Mô hình gần 3NF thích hợp làm nền tích hợp.

### DDS — Dimensional Data Store

DDS tổ chức theo star schema cho truy vấn phân tích: dimension mô tả context,
fact lưu sự kiện và measure. DDS chấp nhận denormalization có kiểm soát để BI
đọc đơn giản và nhanh hơn.

### Hỏi vặn

**Hỏi:** Tại sao không đi thẳng Staging → DDS?

**Đáp:** Có thể với hệ thống nhỏ, nhưng sẽ trộn logic chuẩn hóa đa nguồn, xử lý
late-arriving, DQ và logic dimensional trong cùng bước. NDS tạo integration
boundary ổn định, giúp DDS thay đổi theo nhu cầu phân tích mà không phải đọc lại
từng connector nguồn. Trade-off là thêm storage và ETL step.

**Hỏi:** Tại sao không cho dashboard đọc NDS?

**Đáp:** NDS có nhiều bảng chuẩn hóa và quan hệ nghiệp vụ; người dùng BI dễ join
sai hoặc tạo fan-out. DDS/analytics công bố grain và KPI rõ hơn.

Tham chiếu: [NDS DDL](../sql/warehouse/03_nds_tables.sql),
[NDS/DDS implementation](../docs/warehouse/nds-dds-implementation.md).

## 7. Star schema, fact và dimension

### Hai fact chính

1. **Fact trip:** measure ở trip grain như distance, duration, fare, tip, total
   amount và assignment delay. Có role-playing date/time/location cho pickup và
   dropoff.
2. **Fact shift:** measure ở shift grain như duration, trip count, occupied,
   idle, utilization, revenue và tips.

### Các dimension

- Date/time: hỗ trợ hierarchy thời gian.
- Driver/vehicle: có SCD2 theo nhóm thuộc tính chọn lọc; backdated reconstruction
  còn giới hạn như trình bày ở mục SCD2.
- Vendor/location: context nghiệp vụ.
- Junk dimension: gom các thuộc tính low-cardinality như payment type, rate code,
  trip type, assignment method và anomaly flag.

### Tại sao có junk dimension

Nếu tạo dimension riêng cho từng cờ/enum nhỏ sẽ sinh nhiều bảng và join. Nếu để
tất cả trực tiếp trên fact sẽ làm fact rộng và semantics phân tán. Junk dimension
gom tổ hợp thuộc tính ít cardinality, nhưng không phù hợp cho thuộc tính cardinality
cao hoặc thay đổi độc lập phức tạp.

### Role-playing dimensions

Cùng `dim_date`, `dim_time`, `dim_location` đóng nhiều vai: pickup và dropoff.
Lớp analytics tách `trip_pickup`/`trip_dropoff` để BI tool không nhập nhằng date
role và location role.

Tham chiếu: [DDS tables](../sql/warehouse/04_dds_tables.sql),
[Analytics trip pickup](../sql/analytics/01_certified_datasets.sql#L100-L183),
[Analytics trip dropoff](../sql/analytics/01_certified_datasets.sql#L184-L247).

## 8. Slowly Changing Dimension Type 2

SCD Type 2 lưu lịch sử bằng cách đóng phiên bản cũ (`end_date`,
`is_current=false`) và tạo phiên bản mới khi thuộc tính theo dõi thay đổi. Cùng
một `driver_id` có thể có nhiều `driver_key`, nhưng tối đa một dòng current.

### Thuật toán lý thuyết và phần đã code

1. Tạo hash deterministic từ nhóm thuộc tính được chọn theo SCD2.
2. Tìm phiên bản current theo natural key.
3. Nếu hash không đổi: no-op, không tạo version.
4. Nếu hash đổi: đóng dòng current và insert version mới trong transaction.
5. Fact lookup dimension theo natural key **và thời điểm sự kiện**, không chỉ
   lấy current row.

Trong code hiện tại, hash driver chỉ gồm `home_borough` và
`employment_status`; hash vehicle chỉ gồm `vehicle_status`. Các thuộc tính driver
như `license_status`, `license_expiry_date`, `display_name` và
`experience_years` được cập nhật Type 1 trên current row khi hash SCD2 không đổi.
Không được trả lời rằng mọi thuộc tính của driver/vehicle đều được version hóa.

### Tại sao driver/vehicle dùng SCD2

`home_borough`, `employment_status` và `vehicle_status` có thể thay đổi và cần
xem hiệu suất trong bối cảnh lịch sử. Vendor/location/date/time hiện không dùng
cùng chiến lược SCD2 trong scope này.

### Giới hạn temporal rất quan trọng

`nds_driver_history` giữ `effective_at` và `delivered_at`, nhưng DDS loader hiện
đóng version cũ và mở version mới bằng **thời điểm chạy loader** (`now_ts`), không
dùng trực tiếp `effective_at` của change event. Hơn nữa, trong một full load,
`load_driver_changes()` áp các event lên NDS master trước khi `load_dim_driver()`
chạy; DDS vì vậy có thể chỉ nhìn trạng thái cuối thay vì tái dựng đầy đủ các
version backdated trong release.

Nói chính xác khi bảo vệ:

> Code đã có cơ chế SCD2 theo hash, current-row constraint, no-op rerun và lookup
> fact theo khoảng hiệu lực của những version đã tồn tại. Tuy nhiên việc tái dựng
> toàn bộ lịch sử từ change feed theo `effective_at`, đặc biệt late-arriving và
> backdated event trong cùng full release, chưa hoàn thiện như một temporal SCD2
> production-grade.

### Hỏi vặn

**Hỏi:** Vì sao không dùng SCD Type 1?

**Đáp:** Type 1 overwrite có thể khiến báo cáo lịch sử nhìn trip cũ bằng trạng
thái mới. Type 2 là mục tiêu phù hợp nhưng tốn thêm dòng và cần lookup theo
effective time. Implementation hiện mới version hóa nhóm thuộc tính được chọn và
chưa tái dựng đầy đủ backdated history từ change feed.

**Hỏi:** Hash có phải khóa bảo mật không?

**Đáp:** Không. SHA-256 ở đây là change fingerprint để so sánh payload
deterministic, không phải cơ chế mã hóa dữ liệu.

**Hỏi:** Làm sao tránh hai current row?

**Đáp:** Ngoài logic loader, DDL có partial unique index trên natural key khi
`is_current=true`, tạo ràng buộc ở database.

Code: [DDSLoader — driver SCD2](../src/warehouse/dds_loader.py#L525-L647),
[vehicle SCD2](../src/warehouse/dds_loader.py#L648-L763),
[DDL SCD constraints](../sql/warehouse/04_dds_tables.sql#L34-L85),
[tests SCD2](../tests/test_dds_loader.py#L88-L187).

## 9. Data Quality, Audit, Quarantine và Anomaly

### Bốn khái niệm không được trộn

| Khái niệm | Ý nghĩa | Ví dụ | Hành động |
|---|---|---|---|
| Validation/DQ ERROR | Không đủ điều kiện tích hợp | ID sai format, enum không hợp lệ | Quarantine, không vào NDS |
| DQ WARN | Đáng ngờ nhưng vẫn có giá trị | amount/distance âm theo contract hiện tại | Log và vẫn nạp |
| Business anomaly | Dữ liệu có thể đúng kỹ thuật nhưng bất thường vận hành | overlap ca, trip ngoài shift | Giữ dữ liệu, log; flag tùy rule đã triển khai |
| Audit metadata | Bằng chứng quá trình | batch, release, checksum, row counts | Truy vết và reconciliation |

### Hai DQ gate

- **Gate 1 — Staging → NDS:** kiểm tra cấu trúc/format/null/enum/date order.
  ERROR bị cách ly; WARN được ghi nhận.
- **Gate 2 — NDS → DDS:** kiểm tra quan hệ nghiệp vụ chéo nguồn: driver/vehicle
  overlap, trip ngoài shift, assignment delay âm. Chủ yếu WARN để không làm mất
  sự kiện tài chính.

### Vì sao giữ anomaly thay vì drop

Drop business anomaly có thể làm sai tổng doanh thu và che giấu vấn đề cần quản
lý. Hệ thống giữ sự kiện, log/flag để điều tra. Ngược lại, record không có key
hợp lệ hoặc enum sai có thể phá integrity nên bị quarantine.

### Mâu thuẫn code–spec hiện tại phải biết

Spec mô tả driver/vehicle shift overlap sẽ làm
`fact_driver_shift.is_anomaly=true`. Code Gate 2 hiện chỉ ghi `dq_issue` cho
overlap; câu query tạo fact shift tính `is_anomaly` bằng `BOOL_OR(trip nằm ngoài
shift)`. Vì vậy overlap có trong DQ rule summary nhưng chưa chắc xuất hiện trong
`anomaly_shift_count`/shift anomaly queue. Đây là gap cần sửa đồng bộ loader,
semantic test và tài liệu nếu muốn đúng spec; không được khẳng định đã propagate.

### Inferred member

Khi shift/assignment đến trước master driver/vehicle nhưng natural key hợp lệ,
NDS tạo skeleton row `is_inferred=true`. Khi master đến sau, cùng surrogate key
được bổ sung thông tin. `Unknown` chỉ dùng cho late-arriving master, không dùng
để che enum nguồn sai.

### Hỏi vặn

**Hỏi:** `dq_issue_count` và `quarantine_count` có bằng nhau không?

**Đáp:** Không bắt buộc. DQ issue gồm WARN/ERROR event; quarantine chỉ chứa record
ERROR bị loại khỏi luồng. Một record có thể liên quan rule khác nhau, nên phải
đọc theo grain và filter.

**Hỏi:** Trip anomaly lưu ở đâu?

**Đáp:** Trip-outside-shift flag được giữ ở NDS trip, sau đó truyền qua
`dim_junk_trip.is_anomaly` cho fact trip. Fact shift có cột `is_anomaly`, nhưng
code hiện tính nó từ trip-outside-shift; driver/vehicle overlap mới chỉ có DQ log.
Trip và shift anomaly khác grain, không cộng thành một count.

Tham chiếu: [DQ specification](../docs/warehouse/data-quality-etl-spec.md),
[quarantine DDL](../sql/warehouse/05_dq_quarantine.sql),
[NDS DQ logging](../src/warehouse/nds_loader.py#L431-L512),
[inferred driver](../src/warehouse/nds_loader.py#L557-L635),
[DQ Gate 2](../src/warehouse/dds_loader.py#L764-L943).

## 10. Idempotency, lineage và reconciliation

### Idempotency

Idempotent nghĩa là chạy lại cùng logical input không làm nhân đôi hoặc đổi sai
kết quả nghiệp vụ. Dự án áp dụng ở nhiều mức:

- Staging full refresh xóa rows cùng `release_id` rồi nạp lại.
- DQ/quarantine dùng `WHERE NOT EXISTS` theo source identity và rule.
- NDS natural key có unique constraint và loader upsert.
- Fact DDS `ON CONFLICT (trip_id/shift_id) DO UPDATE`.
- SCD2 cùng hash không tạo version mới.

Idempotency không có nghĩa mọi audit row đều phải giữ cùng `batch_id`; một rerun
có thể là execution mới, nhưng business result và source identity phải ổn định.

### Lineage

Lineage được nối bằng `release_id`, `batch_id`, source system/entity/locator,
source record ID, file/row number, file checksum và row hash. Checksum chứng minh
file-level integrity; row hash nhận diện payload business-level. Hai loại hash
không thay thế nhau.

### Reconciliation

Reconciliation kiểm tra giữa tầng thay vì chỉ kiểm “code không lỗi”:

- staging assignment ↔ NDS trip/assignment;
- NDS trip ↔ DDS trip fact;
- completed NDS shift ↔ DDS shift fact;
- revenue, distance, duration;
- duplicate business key, orphan FK, multiple-current SCD2;
- `occupied + idle = shift duration`.

### Trung thực về trạng thái triển khai

- Fact upsert, DQ identity, SCD no-op, audit và reconciliation đã triển khai.
- Mô hình **work tables rồi atomic publish** trong đặc tả là thiết kế mục tiêu,
  chưa được triển khai đầy đủ.
- `PipelineRunner` có result contract chung, nhưng loader hiện tự tạo audit
  `batch_id` nội bộ; không nên tuyên bố mọi tầng đang dùng duy nhất một UUID
  orchestration xuyên suốt nếu chưa sửa code.

### Hỏi vặn

**Hỏi:** Test pass có chứng minh dữ liệu đúng hoàn toàn không?

**Đáp:** Không. Test chứng minh các invariant đã định nghĩa trên fixture/sample
và reconciliation hiện có. Nó không chứng minh không còn rule nghiệp vụ bị bỏ
sót hoặc synthetic data đại diện hoàn hảo cho thực tế.

Code: [row/file hash](../src/ingestion/staging_loader.py#L33-L67),
[audit metadata](../src/ingestion/staging_loader.py#L181-L320),
[fact trip upsert](../src/warehouse/dds_loader.py#L1070-L1120),
[reconciliation](../src/warehouse/pipeline_validation.py#L32-L181).

## 11. KPI và semantic contract

### KPI cốt lõi

- `trip_count = COUNT(*)`
- `occupied_minutes = SUM(trip_duration_minutes)` ở shift aggregation.
- `idle_minutes = shift_minutes - occupied_minutes`.
- `utilization_rate = SUM(occupied_minutes) / SUM(shift_duration_minutes)`.
- `revenue_per_hour = SUM(total_revenue) × 60 / SUM(shift_duration_minutes)`.
- `average_fare = SUM(fare_amount) / COUNT(trip_id)`.

### Vì sao dùng ratio of sums

Không được lấy trung bình đơn giản các tỷ lệ cấp dòng khi mẫu số khác nhau. Ví dụ
ca A 1 giờ utilization 100%, ca B 9 giờ utilization 0%:

- Average của hai rate = 50% — sai về tổng thời gian.
- Ratio of sums = `60 / 600 = 10%` — đúng theo tổng phút.

### Additivity

- Revenue/trips/distance/minutes thường additive trong fact sở hữu.
- Average, utilization, revenue/hour và distinct active count non-additive; phải
  tính lại theo filter context.
- Không cộng doanh thu từ fact trip và fact shift vì cùng business event đã được
  biểu diễn ở hai grain.

### Date role và timezone

- Trip analysis mặc định theo pickup date/time; dropoff có view riêng.
- Shift theo shift start.
- Business time là `America/New_York`; audit/DQ time là UTC.
- `active_driver_count` nghĩa là driver distinct có trip activity trong kỳ,
  không phải số hồ sơ HR có status ACTIVE.

### Certified và exploratory

Certified metric có định nghĩa, owner/boundary, grain, date role, null handling
và reconciliation. K-Means/Apriori và vehicle peer threshold là exploratory,
không tự động quyết định nhân sự.

Tham chiếu: [Metric catalog](../docs/analytics/metric-catalog.md),
[Semantic contract](../docs/analytics/semantic-contract.md),
[ADR-006](../docs/decisions/ADR-006-dashboard-semantics-and-mining-status.md).

## 12. OLAP và ROLAP

OLAP hỗ trợ phân tích đa chiều:

- **Slice:** chọn một member, ví dụ năm 2021.
- **Dice:** chọn nhiều điều kiện, ví dụ 2021 + Brooklyn + evening.
- **Drill-down:** từ year → quarter → month → day.
- **Roll-up:** tổng hợp từ zone → borough hoặc day → month.
- **Pivot:** đổi dimension giữa hàng/cột để đổi góc nhìn.

Dự án dùng **ROLAP**: dữ liệu và aggregation nằm trên PostgreSQL, Superset sinh
SQL trên analytics views. Không có MOLAP cube vật lý, MDX hay precomputed cube
engine chuyên dụng.

### Vì sao ROLAP

ROLAP phù hợp stack hiện tại, tái sử dụng PostgreSQL/DDS, dễ audit SQL và không
thêm hạ tầng cube. Trade-off là truy vấn phức tạp có thể chậm hơn MOLAP và cần
index/materialization nếu scale lớn.

### Hỏi vặn

**Hỏi:** Chỉ có view thì có gọi là OLAP không?

**Đáp:** OLAP là khả năng phân tích đa chiều và operation; không bắt buộc MOLAP
cube. Hai view `olap_trip_cube` và `olap_shift_cube` cung cấp dimension hierarchy
và measure để Superset thực hiện slice/dice/drill/roll-up/pivot — đó là ROLAP.

Tham chiếu: [OLAP plan](../docs/analytics/olap-plan.md),
[trip cube](../sql/analytics/01_certified_datasets.sql#L340-L411),
[shift cube](../sql/analytics/01_certified_datasets.sql#L412-L471).

## 13. K-Means phân nhóm tài xế

### Mục đích

K-Means nhóm các driver có profile vận hành tương tự để hỗ trợ khám phá nhu cầu
đào tạo/điều phối, không dùng để tự động chấm điểm nhân sự.

### Feature hiện tại

`revenue_per_hour`, `utilization_rate`, `trips_per_shift`,
`average_trip_distance`, `tips_per_trip`, `idle_minutes_per_shift`,
`completed_shifts`.

### Thuật toán

1. Aggregate về một dòng mỗi driver, chỉ giữ driver có ít nhất 10 completed shifts.
2. Winsorize mỗi feature ở quantile 1%/99%, rồi dùng `RobustScaler`.
3. Thử K-Means với `k=2..8`, loại cụm quá nhỏ; chọn silhouette cao nhất, tie-break bằng Davies–Bouldin thấp hơn và `k` thấp hơn.
4. Fit baseline bằng seed 42; báo cáo silhouette, Davies–Bouldin,
   Calinski–Harabasz và mean ARI qua năm seed khác baseline.
5. Gắn nhãn trung tính theo thứ hạng revenue/hour centroid: `Revenue profile rank r of k`.
6. Append kết quả và provenance vào history; current view chỉ hiển thị run thành công hiện hành.

### Lý thuyết cần nhớ

K-Means tối thiểu hóa tổng bình phương khoảng cách từ điểm đến centroid trong
cụm. Nó nhạy với scale và outlier, ưu tiên cụm gần dạng cầu, và cần chọn `k`.
Silhouette nằm trong `[-1, 1]`: gần 1 tách cụm tốt; gần 0 chồng lấn; âm có thể
gán sai cụm.

### Hỏi vặn

**Hỏi:** Vì sao phải scale?

**Đáp:** Nếu không scale, feature có biên độ lớn như revenue/minutes có thể chi
phối Euclidean distance dù không quan trọng hơn feature tỷ lệ.

**Hỏi:** Vì sao chọn k này, có phải em tự đặt không?

**Đáp:** Không cố định k. Code thử từ 2 đến 8, loại nghiệm có cụm quá nhỏ, ưu
tiên silhouette lớn nhất; nếu hòa thì Davies–Bouldin thấp hơn, rồi k nhỏ hơn.
Sau đó đo mean ARI với năm seed khác seed baseline 42. Không đưa baseline vào
trung bình vì ARI của một partition với chính nó luôn bằng 1 và sẽ làm stability
tăng giả tạo. Em vẫn chỉ coi đó là lựa chọn exploratory, vì metric tốt không tự
đảm bảo segment có ý nghĩa nghiệp vụ.

**Hỏi:** “Revenue profile rank 1” có phải driver giỏi nhất không?

**Đáp:** Không. Nhãn là mô tả tương đối theo centroid của tập feature và kỳ dữ
liệu; không đo nhân quả, chất lượng phục vụ hay công bằng nhân sự.

Code: [K-Means constants](../src/analytics/data_mining.py#L32-L45),
[driver segmentation](../src/analytics/data_mining.py#L214-L294).

## 14. Apriori và association rules

### Mục đích

Tìm pattern dạng pickup/time/vendor → dropoff lặp lại đủ mạnh để hỗ trợ khám phá
bố trí năng lực.

### Ba chỉ số

- `support(A→B) = P(A ∪ B)`: tỷ lệ basket chứa cả A và B.
- `confidence(A→B) = P(B|A) = support(A∪B)/support(A)`.
- `lift(A→B) = confidence(A→B)/support(B)`.
  - lift > 1: đồng xuất hiện nhiều hơn baseline;
  - lift = 1: gần độc lập;
  - lift < 1: quan hệ âm.

Confidence cao chưa đủ; nếu B vốn rất phổ biến, rule có thể không cung cấp thêm
thông tin. Vì vậy cần xem cả support và lift.

### Triển khai hiện tại

- Mỗi trip là một basket gồm pickup/dropoff borough/zone, hour bucket, day type,
  day name và vendor.
- Ngưỡng: support `0.005`, confidence `0.2`, lift `1.1`.
- Antecedent không chứa dropoff; consequent là một dropoff item để giữ hướng
  diễn giải vận hành.
- Xét frequent itemset tối đa bậc 3.
- Dùng deterministic hash-stratified sample: tối đa 500 trip/tháng/pickup borough,
  công bố tối đa 100 rules. Luật còn phải vượt support, confidence, lift, tối thiểu
  50 antecedent observations và stability score 0,70.

### Hỏi vặn

**Hỏi:** Apriori có chứng minh pickup gây ra dropoff không?

**Đáp:** Không. Association không phải causation. Rule chỉ cho biết pattern đồng
xuất hiện trong dữ liệu quan sát.

**Hỏi:** Vì sao tự code Apriori?

**Đáp:** Scope chỉ cần itemset nhỏ và muốn tránh thêm dependency. Đổi lại, bản
hiện tại không tối ưu cho tập rất lớn và không đầy đủ như thư viện production.

**Hỏi:** Lấy 50.000 trip đầu có bias không?

**Đáp:** Sample hiện tại đã stratify theo tháng và pickup borough, với thứ tự
`md5(trip_id)` xác định để tái lập. Tuy nhiên đây vẫn là sample lịch sử, không
chứng minh pattern sẽ giữ nguyên ở kỳ tương lai; vì vậy output vẫn exploratory.

**Hỏi vặn cấp hai:** `rules_generated` là số trước hay sau stability filter?

**Đáp:** Là số rule đã qua support/confidence/lift, antecedent-count và redundancy
pruning nhưng **trước** stability filter. Run ledger ghi thêm
`rules_retained_after_stability`; `rules_published` là số cuối cùng sau stability
và cap 100. Tách ba mốc giúp biết rule giảm ở quality gate nào.

Code: [Apriori rule generation](../src/analytics/data_mining.py#L98-L172),
[stability filter](../src/analytics/data_mining.py#L181-L198),
[build basket và publish rules](../src/analytics/data_mining.py#L297-L361),
[provenance test](../tests/test_data_mining_provenance.py).

## 15. Giới hạn và giá trị của đồ án

### Trạng thái triển khai và mức bằng chứng

Các mục ETL/DDS bên dưới có runtime evidence đã lưu trong repository. Với phần
ML vừa nâng cấp, code và unit/static contract tests đã được kiểm tra; migration,
model run và Superset runtime **chưa được tái kiểm chứng sau nâng cấp** vì Docker
engine không chạy trong phiên thực hiện. Vì vậy không dùng test tĩnh để khẳng
định database/dashboard runtime đã PASS.

- Heterogeneous source simulation và source-specific ingestion.
- Staging metadata, checksum, row hash và audit.
- DQ Gate 1, quarantine, inferred member và DQ Gate 2.
- NDS, Driver Operations DDS, SCD2 theo hash/loader-observed change và fact upsert.
- Reconciliation và DQ fixtures.
- Analytics views, certified metrics, Superset dashboard và ROLAP lab.
- K-Means/Apriori với provenance và nhãn exploratory.
- Streamlit pipeline control panel.

### Giới hạn phải nói thẳng

- Driver/fleet/dispatch là synthetic; không suy rộng kết luận nhân sự thật.
- Batch historical, không realtime/CDC/streaming.
- Revenue không phải profit; observed trips không phải unmet demand.
- Không production HA, enterprise security hoặc orchestration engine chuyên dụng.
- Work-table atomic publish chưa hoàn thiện đầy đủ.
- DDS SCD2 chưa replay đầy đủ change feed theo `effective_at` cho late/backdated
  event trong cùng full release.
- Driver/vehicle shift-overlap hiện được log DQ nhưng chưa propagate vào
  `fact_driver_shift.is_anomaly`; shift anomaly metric chưa phủ đủ spec.
- Một số ngưỡng review/mining là provisional/exploratory.
- K-Means đã có selection/stability guardrail; Apriori đã stratify sample nhưng
  vẫn giới hạn itemset tối đa bậc 3 và không phải mô hình dự báo.
- Dashboard local Superset; native filter đang tắt theo quyết định tương thích
  phiên bản hiện tại.

### Cách biến giới hạn thành câu trả lời tốt

Không nói “nhóm chưa kịp”. Hãy nói: “Trong scope hiện tại nhóm ưu tiên tính tái
lập, lineage và semantic correctness. Phần X được ghi rõ là giới hạn; nếu đưa
vào production, bước tiếp theo là Y và cần thêm điều kiện Z.”

---

# Phần II: Bản đồ và bảo vệ code

## Luồng thực thi end-to-end

Để trả lời câu “hệ thống thực sự chạy từ đâu đến đâu?”, không bắt đầu từ một
class rời rạc. Hãy trình bày ba workflow khác nhau:

### Workflow A — data owner tạo canonical release

```text
TLC CSV + lookup
  → generate_synthetic_sources.py
  → drivers.csv + driver_changes.jsonl + vehicles.jsonl
  → shifts.tsv + trip_assignment CSV + exceptions
  → synthetic_generation_manifest.json
  → validate_synthetic_sources.py
  → canonical release được đóng gói và phân phối
```

Workflow này không phải bước mọi thành viên tự chạy mỗi lần. Cấu hình/seed phải
được cố định; các thành viên tải cùng release để tránh sinh nhiều “nguồn sự thật”.

### Workflow B — tái tạo source systems và warehouse

```text
Canonical release
  ├→ seed_mysql_hr.py          → MySQL HR
  ├→ seed_mongodb_fleet.py     → MongoDB Fleet
  ├→ seed_postgres_dispatch.py → PostgreSQL Dispatch
  └→ TLC/lookup vẫn là file batch

apply_warehouse_ddl.py
  → schemas Audit/Staging/NDS/DDS/DQ

run_pipeline.py hoặc Streamlit
  → source_health
  → load_staging
  → load_nds
  → load_dds
  → reconciliation
  → data_mining
  → mark_dds_ready
```

### Workflow C — công bố BI

```text
sql/analytics/01_certified_datasets.sql
  → analytics views + mining output tables
  → setup_superset_warehouse.py
  → read-only warehouse login
  → provision_superset.py
  → database + datasets + metrics + 35 charts + dashboard + viewer role
  → smoke_test_superset.py + benchmark_superset.py
```

### Input/output contract của từng bước

| Bước | Input chính | Output chính | Failure signal |
|---|---|---|---|
| Generate | TLC files, lookup, JSON config, seed | Synthetic files + manifest | Exception hoặc missing source |
| Validate synthetic | Release files + TLC source | JSON validation report | Exit code 1 khi invariant fail |
| Seed sources | Canonical release | MySQL/MongoDB/PostgreSQL source state + seed metadata | Row-count/checksum mismatch |
| Apply DDL | Ordered SQL files | Warehouse schemas/tables/indexes | `ON_ERROR_STOP`/exception |
| Staging | Bốn source interfaces | Staging rows + extract/checksum audit | Loader stats/batch FAILED |
| NDS | Staging theo release | Integrated entities + DQ/quarantine | Rejected count hoặc exception |
| DDS | NDS | Dimensions, facts, anomaly flags | DQ counts, loader failure |
| Reconcile | Warehouse layers | Danh sách `ValidationResult` | `actual != expected` |
| Mining | Analytics trip/shift | Current segmentation/rule output | Transaction rollback/exception |
| Superset provision | Analytics schema + env | Metadata objects/dashboard | ORM/API/smoke-test failure |

## Cấu trúc code và ranh giới trách nhiệm

| Thư mục | Trách nhiệm đúng | Ví dụ |
|---|---|---|
| `scripts/` | CLI, bootstrap, seed và operational entry point | `run_pipeline.py`, `seed_*`, `provision_superset.py` |
| `src/ingestion/` | Kết nối nguồn và nạp Staging | `StagingLoader` |
| `src/warehouse/` | DQ, NDS, DDS và reconciliation | `NDSLoader`, `DDSLoader` |
| `src/orchestration/` | Step ordering và result contract | `PipelineRunner`, dataclasses |
| `src/monitoring/` | Read-only monitoring repository, lock, sanitization | `MonitoringRepository`, `PipelineLock` |
| `src/analytics/` | Data Mining dùng lại | K-Means, Apriori |
| `sql/source_*` | Contract vật lý của source simulation | MySQL HR, PostgreSQL Dispatch |
| `sql/warehouse/` | DDL theo dependency order | Audit → Staging → NDS → DDS → DQ |
| `sql/analytics/` | BI boundary và least-privilege role | Certified datasets, read-only grant |
| `app/` | UI điều khiển/monitoring | Streamlit app |
| `tests/` | Contract/unit/integration-style checks | DDL, loader, semantic, UI, Superset |

### Câu trả lời “tại sao script và src tách nhau?”

`scripts/` chịu trách nhiệm nhận argument, đọc environment, in kết quả và trả exit
code. Logic dùng lại nằm trong `src/`, nhờ vậy CLI và Streamlit gọi cùng code,
tests có thể mock connection/handler, và không phải chạy subprocess từ UI.

### Điểm chưa tuyệt đối

`scripts/provision_superset.py` rất lớn và chứa cả dataset specs, metric specs,
chart specs, layout và CSS. Nó bảo đảm reproducibility nhưng coupling với Superset
ORM/version khá cao. Nếu mở rộng production nên tách declarative specs khỏi ORM
adapter và thêm migration/versioning cho dashboard metadata.

## Sinh và kiểm định dữ liệu synthetic

### Code ở đâu

- Cấu hình deterministic: [synthetic_generation.json](../configs/synthetic_generation.json).
- Resource/shift model: [generator lines 36–115](../scripts/generate_synthetic_sources.py#L36-L115).
- Driver/vehicle/change-feed writers: [generator lines 194–321](../scripts/generate_synthetic_sources.py#L194-L321).
- Shift idle calculation: [generator lines 324–368](../scripts/generate_synthetic_sources.py#L324-L368).
- Main assignment loop: [generator lines 371–699](../scripts/generate_synthetic_sources.py#L371-L699).
- Validator: [validate_synthetic_sources.py](../scripts/validate_synthetic_sources.py#L42-L273).
- Generator-specific tests: [test_generator_shift_logic.py](../tests/test_generator_shift_logic.py).

### Thuật toán phân công

1. `random.Random(seed)` làm nguồn ngẫu nhiên có thể tái tạo.
2. `build_resources()` tạo cặp 1–1 driver–vehicle theo pool size từng vendor.
3. Trip của từng file tháng được parse, loại invalid datetime, sai source period
   hoặc duration âm/quá 24 giờ, rồi sort theo pickup time.
4. `VendorPool.acquire()` ưu tiên resource idle ở pickup zone
   (`CONTINUITY`), sau đó lấy từ global idle pool (`AVAILABLE_POOL`).
5. Nếu không còn resource, trip vào `assignment_exceptions` với
   `NO_CAPACITY`; không tạo assignment giả.
6. Một trip nối tiếp shift hiện tại khi gap không quá 180 phút và tổng span
   không quá 12 giờ. Nếu không, shift cũ được finalize và mở shift mới.
7. Assignment timestamp được đặt trước pickup 1–15 phút.
8. Manifest lưu checksum nguồn, checksum output, row counts và seed.

### Tại sao dùng heap và token

`busy` là min-heap theo `available_at`, giúp release resource đã rảnh trước pickup
mà không quét toàn bộ pool. `idle_token` làm version token để bỏ qua entry cũ
trong các queue khi trạng thái resource đã đổi; đây là lazy invalidation.

### Idle time được tính thế nào

`idle_minutes` gồm buffer đầu ca, gap giữa các trip và buffer cuối ca. Khi mở ca
mới trước pickup, code bảo đảm không lùi trước end của ca trước. Vì vậy invariant
quan trọng là:

```text
occupied_minutes + idle_minutes ≈ shift_end - shift_start
```

Validator dùng tolerance 0,02 phút do output đã làm tròn hai chữ số.

### Validator thực sự kiểm gì

- ID uniqueness và referential integrity driver/vehicle/shift/trip key.
- Vendor consistency với lookup.
- Inspection date không trước service start.
- Shift time balance và không overlap driver/vehicle.
- Assignment khớp đúng TLC source file + source row + deterministic trip key.
- Trip nằm trong shift và assignment timestamp không sau pickup.
- Count/reason của exception.

### Điểm giáo viên có thể bắt

- Deterministic chỉ đúng khi input files, thứ tự sort, config và Python behavior
  liên quan không đổi; manifest/checksum là bằng chứng cần đi cùng seed.
- Home zone được random trong `1..265`; sự hợp lý cuối cùng phụ thuộc lookup và
  validator, không phải mô hình nhu cầu thật.
- Một driver luôn ghép với một vehicle trong resource pool; đây là đơn giản hóa
  case study, không mô hình hóa mọi lần đổi xe thực tế.
- File exception có thể chứa raw datetime invalid, trong khi source PostgreSQL
  khai báo cột timestamp NOT NULL. Canonical release hiện đã validate, nhưng edge
  case invalid-datetime cần staging/DDL riêng an toàn hơn nếu muốn seed mọi lỗi.

## Seed dữ liệu vào các source system

### MySQL Driver HR

Code: [seed_mysql_hr.py](../scripts/seed_mysql_hr.py#L141-L472) và
[MySQL DDL](../sql/source_mysql_hr/01_driver_tables.sql).

- Parser kiểm đủ cột CSV/JSONL và normalize timestamp.
- `INSERT ... ON DUPLICATE KEY UPDATE` upsert theo `driver_id`/`event_id`.
- Metadata lưu release, source file, SHA-256, row count và seed time.
- Có thể dùng MySQL CLI hoặc `docker compose exec`; password truyền qua environment,
  không ghép vào command line.
- Cuối cùng query lại ba table để bắt row-count mismatch.
- `--truncate` là thao tác snapshot có chủ đích; mặc định upsert không cần truncate.

**Trade-off:** script build SQL literal batches thay vì driver parameterized
`executemany`. Hàm escape quote/backslash và input là canonical release, nhưng
parameterized connector vẫn an toàn/dễ bảo trì hơn cho production.

### MongoDB Fleet

Code: [seed_mongodb_fleet.py](../scripts/seed_mongodb_fleet.py#L118-L279).

- Tạo unique index cho `vehicle_id`, `plate_token` và seed identity.
- Validate required fields/enums, chuyển business date/time sang UTC BSON datetime.
- `UpdateOne(..., upsert=True)` theo `vehicle_id`, flush theo batch với
  `ordered=False`.
- Ghi checksum/row count vào `seed_metadata`.
- Đối soát số dòng file với toàn bộ documents collection.

**Điểm yếu:** `file_row_count` tăng trước validation; dòng bị skip vẫn được tính
vào file count/metadata và làm reconciliation fail. Điều này giúp không silent
pass, nhưng message/metadata chưa tách rõ `read`, `valid`, `loaded`, `rejected`.
Ngoài ra collection không xóa document cũ không còn trong snapshot, nên row-count
check sẽ phát hiện lệch nhưng seed chưa tự reconcile deletion.

### PostgreSQL Dispatch

Code: [seed_postgres_dispatch.py](../scripts/seed_postgres_dispatch.py#L136-L361)
và [Dispatch DDL](../sql/source_postgres_dispatch/01_dispatch_tables.sql).

- `seed_metadata` quyết định skip khi cùng release/file/checksum.
- `shifts` và `assignment_exceptions` là snapshot: truncate trước COPY khi file
  thay đổi.
- Assignment partition theo tháng: xóa theo **business `source_file`** rồi COPY,
  nhờ vậy thay một tháng không phải reload toàn bộ.
- PostgreSQL `COPY FROM STDIN` phù hợp hàng triệu assignment.
- Row count của ba entity được đối soát cuối script.

**Trade-off:** source Dispatch không khai báo FK đến HR/Fleet vì đó là hệ thống
nguồn độc lập; cross-system integrity được kiểm sau khi tích hợp. `TRUNCATE` và
COPY commit theo từng file giúp thao tác rõ, nhưng không tạo một transaction
atomic cho toàn bộ release nhiều tháng.

### Phân biệt seed với ingest

Seed tạo lại trạng thái của **source simulation** từ release. Ingest là
`StagingLoader` kết nối vào source interface và đưa dữ liệu vào warehouse. Nếu
giáo viên hỏi “sao đã có file còn đưa vào database rồi lại đọc ra?”, câu trả lời
là file là canonical distribution artifact; database mới là interface mô phỏng
hệ thống nghiệp vụ mà ingestion phải tích hợp.

## Khởi tạo DDL và database contract

### Code ở đâu

- Apply/verify: [apply_warehouse_ddl.py](../scripts/apply_warehouse_ddl.py#L19-L240).
- Schemas: [00_create_schemas.sql](../sql/warehouse/00_create_schemas.sql).
- Audit: [01_audit_metadata.sql](../sql/warehouse/01_audit_metadata.sql).
- Staging: [02_staging_tables.sql](../sql/warehouse/02_staging_tables.sql).
- NDS: [03_nds_tables.sql](../sql/warehouse/03_nds_tables.sql).
- DDS: [04_dds_tables.sql](../sql/warehouse/04_dds_tables.sql).
- DQ/quarantine: [05_dq_quarantine.sql](../sql/warehouse/05_dq_quarantine.sql).
- DDL contract tests: [test_warehouse_ddl_contract.py](../tests/test_warehouse_ddl_contract.py).

### Vì sao thứ tự DDL cố định

`DEFAULT_FILES` đi theo dependency: schema → audit metadata → staging FK audit →
NDS/source reference → DDS FK audit/NDS-related contracts → DQ FK audit/source.
Đổi thứ tự có thể làm FK reference table chưa tồn tại.

### Hai chế độ apply

Script thử `psycopg` trực tiếp; nếu không có trong auto mode thì fallback sang
`docker compose exec psql`. `ON_ERROR_STOP=1` bảo đảm psql không tiếp tục khi một
statement lỗi. Sau apply, script query `information_schema` và yêu cầu mỗi schema
đích có table.

### Database là lớp bảo vệ thứ hai

Loader validation không đủ. DDL còn khóa:

- PK/unique grain của trip, shift, assignment.
- FK giữa fact và dimension.
- Check enum/time/range cơ bản.
- Partial unique index bảo đảm tối đa một current SCD2 row.
- Index cho business key/time lookup và pagination.

### Giới hạn verify

`verify_with_*()` chỉ xác nhận schema có table, không xác nhận mọi column/index/
constraint đúng. Phần sâu hơn được bù bởi `test_warehouse_ddl_contract.py` và
database-backed pipeline validation; production migration tool vẫn là hướng mở
rộng hợp lý.

## Hạ tầng local và các script phụ trợ

### Docker Compose không chỉ có một database

[docker-compose.yml](../docker-compose.yml) khai báo bốn service độc lập:
MySQL HR 8.4, MongoDB Fleet 7.0, PostgreSQL Dispatch 16 và PostgreSQL Warehouse
16; mỗi service có volume, port và health check riêng. Việc Dispatch và Warehouse
cùng PostgreSQL không làm chúng thành một hệ thống vì service/database/credential
và vai trò khác nhau.

[docker-compose.superset.yml](../docker-compose.superset.yml) tách Superset
metadata PostgreSQL, init job và web app; image Superset được pin 6.1.0. Metadata
dashboard không lưu trong warehouse nghiệp vụ.

### Script phụ trợ và phạm vi

| Script | Vai trò | Không nên mô tả thành |
|---|---|---|
| `init_superset_env.py` | Sinh credential local bằng `secrets`, không overwrite file đã có | Secret manager production |
| `setup_superset_warehouse.py` | Tạo/alter `superset_ro`, apply analytics views và grants | Migration framework tổng quát |
| `show_superset_login.py` | Hiển thị login local theo yêu cầu | Cơ chế phân phối credential an toàn enterprise |
| `create_repository_samples.py` | Tạo sample nhỏ, referentially complete cho Git/tests | Canonical full release generator |
| `validate_warehouse_pipeline.py` | CLI gọi reconciliation hoặc DQ fixture | Scheduler/orchestrator |
| `run_data_mining.py` | Chạy analytics SQL + mining trong transaction | Model registry |
| `benchmark_superset.py` | Đo chart API nhiều lần và p95 local | Production load test |
| `smoke_test_superset.py` | Kiểm health, dataset/chart/metric/grant contract | Full UI end-to-end browser test |

### Câu hỏi dễ bị bắt

**Hỏi:** Vì sao cần Superset metadata DB riêng?

**Đáp:** Warehouse giữ business data; metadata DB giữ user, dashboard, chart và
Superset state. Tách chúng tránh tool metadata trộn vào analytical warehouse và
cho phép rebuild BI app độc lập.

**Hỏi:** Docker volume có nằm trong Git/release không?

**Đáp:** Không. Volume là local runtime state. Source systems phải có thể xóa và
seed lại từ canonical release; commit volume/database dump sẽ phá tính tái lập và
có rủi ro secret/data lớn.

## Bản đồ code 30 giây

| Giáo viên hỏi | Mở ở đâu | Từ khóa cần tìm |
|---|---|---|
| Synthetic được sinh thế nào? | [generate_synthetic_sources.py](../scripts/generate_synthetic_sources.py#L371-L699) | `VendorPool`, `generate`, `finalize_shift` |
| Synthetic được kiểm định thế nào? | [validate_synthetic_sources.py](../scripts/validate_synthetic_sources.py#L42-L273) | `validate`, `compute_trip_key` |
| File được seed thành source system ra sao? | [seed scripts](../scripts/README.md) | `seed_mysql_hr`, `seed_fleet`, `seed_dispatch` |
| Warehouse DDL được áp theo thứ tự nào? | [apply_warehouse_ddl.py](../scripts/apply_warehouse_ddl.py#L19-L30) | `DEFAULT_FILES`, `VERIFY_SCHEMAS` |
| Luồng pipeline và thứ tự bước | [pipeline_runner.py](../src/orchestration/pipeline_runner.py#L71-L180) | `PipelineRunner`, `_default_handlers` |
| MySQL/MongoDB/PostgreSQL/file vào Staging | [staging_loader.py](../src/ingestion/staging_loader.py#L321-L1127) | `load_hr`, `load_fleet`, `load_dispatch`, `load_tlc` |
| Checksum và row hash | [staging_loader.py](../src/ingestion/staging_loader.py#L33-L67) | `calculate_file_checksum`, `make_row_hash` |
| Audit batch/source extract | [staging_loader.py](../src/ingestion/staging_loader.py#L181-L320) | `start_batch_log`, `write_source_extract_log` |
| DQ ERROR và quarantine | [nds_loader.py](../src/warehouse/nds_loader.py#L431-L512) | `log_dq_issue`, `write_quarantine` |
| Late-arriving driver/vehicle | [nds_loader.py](../src/warehouse/nds_loader.py#L557-L635) | `get_or_create_driver_sk`, `get_or_create_vehicle_sk` |
| Load NDS theo entity | [nds_loader.py](../src/warehouse/nds_loader.py#L715-L1665) | `load_drivers`, `load_shifts`, `load_trips` |
| SCD2 driver/vehicle | [dds_loader.py](../src/warehouse/dds_loader.py#L525-L763) | `load_dim_driver`, `load_dim_vehicle` |
| Business anomaly | [dds_loader.py](../src/warehouse/dds_loader.py#L764-L943) | `run_dq_gate2` |
| Fact trip | [dds_loader.py](../src/warehouse/dds_loader.py#L944-L1120) | `load_fact_driver_trip` |
| Fact shift và KPI thời gian | [dds_loader.py](../src/warehouse/dds_loader.py#L1158-L1309) | `load_fact_driver_shift` |
| Cấu trúc star schema | [04_dds_tables.sql](../sql/warehouse/04_dds_tables.sql) | `dim_driver`, `fact_driver_trip`, `fact_driver_shift` |
| Analytics views và KPI | [01_certified_datasets.sql](../sql/analytics/01_certified_datasets.sql) | `trip_pickup`, `shift`, `olap_*` |
| K-Means/Apriori | [data_mining.py](../src/analytics/data_mining.py) | `run_driver_segmentation`, `run_apriori` |
| Superset dataset/chart/dashboard | [provision_superset.py](../scripts/provision_superset.py#L529-L930) | `ensure_dataset`, `ensure_metrics`, `ensure_chart` |
| Streamlit control panel | [streamlit_app.py](../app/streamlit_app.py) | `PipelineRunner`, `PipelineLock` |
| Reconciliation | [pipeline_validation.py](../src/warehouse/pipeline_validation.py#L32-L181) | `validate_release_reconciliation` |
| Superset có đúng dataset/chart/quyền không? | [smoke_test_superset.py](../scripts/smoke_test_superset.py#L31-L283) | `database_smoke_tests`, `superset_smoke_tests` |
| Hiệu năng chart được đo thế nào? | [benchmark_superset.py](../scripts/benchmark_superset.py#L24-L226) | `calculate_p95`, 20 runs |

## 1. Pipeline orchestration

### Code ở đâu

- Entry point: [scripts/run_pipeline.py](../scripts/run_pipeline.py#L19-L44).
- Logic dùng lại: [PipelineRunner](../src/orchestration/pipeline_runner.py#L71-L180).
- Handler từng bước: [pipeline handlers](../src/orchestration/pipeline_runner.py#L183-L346).
- Thứ tự cấu hình: [basic_demo.yml](../configs/demo/basic_demo.yml).

### Code làm gì

`PipelineRunner.run()` chọn step, hỗ trợ dry-run/resume/fail-fast, tạo result
contract và gọi handler. `_default_handlers()` ánh xạ tên cấu hình sang source
health, staging, NDS, DDS, reconciliation, mining và readiness.

### Call flow cần thuộc

```text
scripts/run_pipeline.main()
  → PipelineRunner(release_id, data_root)
  → load_demo_steps(basic_demo.yml)
  → PipelineRunner.run()
      → PipelineRunResult.start()
      → _select_steps()
      → _execute_step()
          → handler(runner, batch_id)
          → PipelineStepResult(SUCCEEDED | FAILED)
      → PipelineRunResult.finish()
  → serialize result → exit code 0/1
```

`_execute_step()` bắt mọi exception của loader, chuyển thành `FAILED`, lưu
`error_code` theo class exception và sanitize message. Vì exception đã được đổi
thành result, caller phải kiểm `result.status`; không được chỉ dựa vào việc
`runner.run()` không raise.

### Trạng thái result

| Trạng thái | Điều kiện |
|---|---|
| `FAILED` | Có ít nhất một step FAILED |
| `DRY_RUN` | Có step và tất cả đều DRY_RUN |
| `SUCCEEDED` | Mọi step thuộc SUCCEEDED/SKIPPED/DRY_RUN |
| `UNKNOWN` | Không khớp các contract trên, ví dụ không có step |

Code contract: [models.py](../src/orchestration/models.py#L26-L84).

### Vì sao code như vậy

- Entry point chỉ parse CLI; business orchestration nằm trong `src/` để Streamlit
  và CLI dùng chung.
- Step handler mapping giúp unit test bằng fake handler, không cần database thật.
- Fail-fast tránh chạy DDS khi NDS đã thất bại.
- Result object chuẩn hóa rows read/loaded/rejected và lỗi đã sanitize.

### Điểm giáo viên có thể bắt

- `resume` dựa trên `previous_results`, không tự query durable orchestration state.
- CLI có cờ `--resume` nhưng không nhận file/DB previous results; chức năng resume
  thực tế hữu ích cho Python caller truyền `previous_results`, chưa phải resume
  durable sau khi process chết.
- Loader được tạo với `release_id` nhưng không nhận `batch_id` của runner; audit
  batch của mỗi loader hiện tách khỏi orchestration result batch.
- `_load_dds()` báo `rows_read = loaded + rejected`; số này không gồm SCD no-op và
  không phải raw source count. Đây là operational summary, không dùng thay
  reconciliation.
- `configs/pipeline/entities.yml` chỉ là registry phục vụ documentation/monitoring
  parser; ETL load order vẫn hard-code trong loader/runner, không phải metadata-
  driven pipeline hoàn chỉnh.
- `mark_dds_ready` chỉ là result marker, không ghi thêm warehouse table. Readiness
  chỉ true khi full run thành công và marker step SUCCEEDED.
- Đây là orchestration nhẹ phù hợp local demo, chưa thay Airflow/Dagster trong
  production.

### Bằng chứng

[Pipeline tests](../tests/test_pipeline_runner.py#L30-L108) kiểm tra step order,
fail-fast, resume, dry-run và sanitization.

## 2. Staging và adapter đa nguồn

### Code ở đâu

- MySQL HR: [load_hr](../src/ingestion/staging_loader.py#L321-L502).
- MongoDB Fleet: [load_fleet](../src/ingestion/staging_loader.py#L503-L604).
- PostgreSQL Dispatch: [load_dispatch](../src/ingestion/staging_loader.py#L605-L805).
- Lookup files: [load_lookup](../src/ingestion/staging_loader.py#L806-L973).
- TLC files: [load_tlc](../src/ingestion/staging_loader.py#L974-L1142).
- Staging DDL: [02_staging_tables.sql](../sql/warehouse/02_staging_tables.sql).

### Tại sao tách adapter

Mỗi nguồn có connection, datatype và extraction behavior khác nhau. Adapter
chuyển chúng về staging metadata chung: source system/entity/locator/record,
extract time, batch/release và row hash. Downstream không phụ thuộc connector.

### Chi tiết đáng nói

- Mongo timestamp UTC được chuyển về business timezone New York trước khi bỏ
  timezone info theo DWH contract.
- Dispatch dùng server-side cursor/fetch chunk để tránh giữ toàn bộ dữ liệu lớn
  trong RAM.
- TLC chèn theo chunk; fact loader dùng keyset pagination thay vì OFFSET lớn.
- Staging full refresh theo `release_id`, phù hợp canonical batch release.

### Contract chung của một staging row

Mỗi bảng có business columns riêng nhưng cố gắng giữ các cột lineage:

```text
batch_id, release_id, source_system, source_entity, source_locator,
source_record_id hoặc source_file + source_row_number,
source_extract_at, row_hash/checksum, load_timestamp
```

`source_locator` trả lời dữ liệu được đọc ở interface nào; `source_record_id`
hoặc file-row trả lời record nào; `release_id` trả lời gói dữ liệu logic nào;
`batch_id` trả lời execution nào.

### Transaction và memory behavior theo nguồn

| Nguồn | Cách đọc | Cách ghi/transaction | Điểm cần lưu ý |
|---|---|---|---|
| HR MySQL | `SELECT *` driver/change feed | `execute_values`, commit toàn HR source | Master nhỏ nên giữ list trong RAM chấp nhận được |
| Fleet MongoDB | Cursor `find({})` | Tạo list rồi bulk insert, một source transaction | Hiện vẫn giữ records list trong RAM |
| Dispatch PostgreSQL | Server-side cursor, `fetchmany(5000)` | Bulk insert theo chunk/source | Phù hợp assignment lớn hơn |
| TLC files | Đọc file/chunk | Delete và commit theo source file | Một file lỗi rollback file đó, các file trước đã commit |

Staging load vì vậy không atomic cho toàn bộ release. Audit/stats và
reconciliation phải phát hiện partial load; work-table atomic publish là hướng
mở rộng chứ chưa phải hành vi hiện tại.

### Hỏi vặn

**Hỏi:** Vì sao row hash phải normalize và sort key?

**Đáp:** Để cùng business payload tạo cùng hash bất kể thứ tự key hoặc representation
thông thường của date/decimal/bool; nhờ đó rerun/change detection deterministic.

**Hỏi:** Vì sao không query trực tiếp source khi load NDS?

**Đáp:** Staging là extraction boundary và bằng chứng “đã nhận gì”. Nếu downstream
đọc trực tiếp source, rerun khó tái lập khi nguồn thay đổi và DQ khó audit.

**Hỏi:** Tại sao dùng `DELETE ... WHERE release_id` thay vì append mọi batch?

**Đáp:** Staging hiện đại diện snapshot canonical của một release. Delete/reload
giúp rerun tạo cùng state. Nếu cần lưu raw history của mọi extract, phải tách
immutable landing khỏi current staging snapshot và có retention riêng.

**Hỏi:** Password mặc định `change_me_*` trong code có phải secret không?

**Đáp:** Đó là placeholder local, không phải credential thật. Runtime lấy từ
`.env`/environment. Production nên fail closed nếu vẫn là placeholder thay vì
fallback thuận tiện cho demo.

### Bằng chứng

[Staging utility tests](../tests/test_load_staging.py#L28-L107) kiểm tra convert,
checksum, row hash và timezone conversion.

## 3. DQ Gate 1 và inferred member

### Code ở đâu

- DQ log idempotent: [log_dq_issue](../src/warehouse/nds_loader.py#L431-L469).
- Quarantine payload: [write_quarantine](../src/warehouse/nds_loader.py#L470-L512).
- Inferred driver/vehicle: [get/create master](../src/warehouse/nds_loader.py#L557-L635).
- Entity loaders: [NDSLoader load methods](../src/warehouse/nds_loader.py#L715-L1665).
- NDS DDL: [03_nds_tables.sql](../sql/warehouse/03_nds_tables.sql).

### Vì sao `WHERE NOT EXISTS`

Identity gồm release, source system/entity/record và rule. Cùng lỗi nguồn chạy
lại không tạo vô hạn issue/quarantine. `batch_id` vẫn cho biết execution tạo
record đầu tiên, còn identity phản ánh lỗi logic của source record.

### Vì sao inferred member giữ surrogate key

Transaction đến trước master vẫn cần referential integrity. Skeleton row cho
phép FK hợp lệ; khi master đến, update cùng natural key/surrogate key tránh phải
rewrite toàn bộ transaction.

### Load order và call flow

```text
load_vendor → load_location
→ load_drivers → load_driver_changes → load_vehicles
→ load_shifts → load_trips → load_trip_assignments
```

- Lookup/master đi trước transaction để tăng cache hit và giữ FK.
- Trước shift/assignment, loader bulk-create inferred driver/vehicle hợp lệ còn
  thiếu, sau đó prepopulate cache natural-key → surrogate-key.
- Shift, trip và assignment dùng keyset pagination/batch 5.000 thay vì OFFSET.
- Mỗi chunk transaction được upsert và commit; lỗi sau một số chunk không rollback
  các chunk trước.

### Population boundary của NDS trip

`load_trips()` không nạp mọi TLC row. SQL dùng `INNER JOIN` giữa staging TLC và
staging trip assignment theo `release_id + source_file + source_row_number`.
Vì vậy NDS/DDS trip population là **các trip hợp lệ đã được synthetic dispatch
gán**, còn invalid/no-capacity nằm ở assignment exceptions hoặc ngoài population.
Đây là lý do reconciliation so NDS trip với staging assignment count, không so
với toàn bộ raw TLC count.

Code: [NDS trip population join](../src/warehouse/nds_loader.py#L1448-L1471).

### DQ Gate 1 trong code, không chỉ trong tài liệu

| Entity | ERROR đã code | WARN đã code | Hành động |
|---|---|---|---|
| Driver | null ID, sai regex, employment enum sai | missing master ở transaction | Quarantine ERROR; inferred cho missing hợp lệ |
| Vehicle | null ID, sai regex, vehicle status sai | missing master ở transaction | Quarantine ERROR; inferred cho missing hợp lệ |
| Shift | null key, driver/vehicle regex, date order | missing location/master | Quarantine hoặc skeleton lookup |
| Trip | null trip key | negative fare/total/distance | ERROR cách ly; negative vẫn nạp và log |
| Assignment | null key, driver/vehicle regex | missing transaction/master | Quarantine hoặc inferred skeleton |

### Điểm giáo viên có thể bắt

- `log_dq_issue()` và quarantine chống trùng bằng `WHERE NOT EXISTS`, nhưng DDL
  không có unique constraint đúng toàn bộ logical identity. Hai writer concurrent
  vẫn có race; local `PipelineLock` chỉ giảm concurrency trong một app host.
- `load_driver_changes()` giữ event trong `nds_driver_history` nhưng chỉ áp
  `home_borough` vào current master. JSON parse lỗi hiện rơi về dict rỗng và có
  thể ghi `Unknown` thay vì quarantine; đây là edge case cần rule/test bổ sung.
- Helper `get_or_create_trip_sk()`/`shift_sk()` có thể tạo skeleton transaction
  để giữ FK nếu assignment đến trước. Trong configured full flow, trip và shift
  được load trước assignment nên đây chủ yếu là resilience path.
- `loaded` là số row được xử lý/upsert, không phải chỉ số row mới insert. Muốn
  phân biệt inserted/updated/no-op cần dùng `RETURNING`/merge action telemetry.

### Hỏi vặn

**Hỏi:** Tại sao skeleton driver lại có status mặc định?

**Đáp:** Đó là placeholder kỹ thuật và phải đọc cùng `is_inferred=true`; không
được diễn giải là trạng thái HR thật. Thiết kế tốt hơn về sau có thể dùng enum
`UNKNOWN` rõ hơn nếu contract cho phép.

**Hỏi:** Vì sao invalid enum không đổi thành Unknown?

**Đáp:** Vì đó là master đã đến nhưng sai contract, khác với master chưa đến.
Tự sửa sẽ che lỗi nguồn và làm báo cáo có vẻ hợp lệ giả tạo.

**Hỏi:** Vì sao negative fare vẫn vào NDS?

**Đáp:** Contract coi đây là WARN vì có thể là adjustment/refund và cần giữ tổng
tài chính nguồn. Code log `DQ_NEGATIVE_VAL` nhưng vẫn append trip. Nếu business
owner đổi rule thành ERROR phải sửa đồng bộ contract, loader, fixture và KPI
reconciliation.

### Bằng chứng

[NDS tests](../tests/test_nds_loader.py#L91-L270) kiểm tra inferred member, DQ,
quarantine contract, WARN negative và issue idempotency.

## 4. SCD2 và DDS dimensions

### Code ở đâu

- Hash: [deterministic_row_hash](../src/warehouse/dds_loader.py#L49-L54).
- Lookup version theo thời gian: [dimension lookup](../src/warehouse/dds_loader.py#L251-L300).
- Driver/vehicle SCD2: [load_dim_driver/vehicle](../src/warehouse/dds_loader.py#L525-L763).
- DDL unique/current constraints: [dim_driver và dim_vehicle](../sql/warehouse/04_dds_tables.sql#L34-L85).

### Vì sao lookup theo event time

Ở fact trip, join dimension có điều kiện `start_date <= pickup_datetime` và
`pickup_datetime < end_date` (hoặc end null). Nhờ đó trip lịch sử trỏ version
đúng tại lúc pickup, không phải version current hôm nay.

Điều này mô tả đúng **lookup mechanism**, nhưng chất lượng lịch sử còn phụ thuộc
dimension đã có các khoảng hiệu lực đúng. Loader hiện tạo version thay đổi tại
`datetime.now()`, nên không được dùng câu này để khẳng định backdated change feed
đã được dựng hoàn chỉnh.

### Thuộc tính nào Type 2, thuộc tính nào Type 1

| Dimension | Type 2 hash | Type 1 update trên current row |
|---|---|---|
| Driver | `home_borough`, `employment_status` | code/name, license status/expiry, experience |
| Vehicle | `vehicle_status` | plate token, model year/type, inspection date |

Code hash: [SCD2 hash selection](../src/warehouse/dds_loader.py#L338-L346).

### Chi tiết transaction

Với một natural key thay đổi, `UPDATE` đóng row cũ và `INSERT` row mới dùng cùng
connection và chỉ commit sau khi toàn bộ dimension loop xong. Nếu exception xảy
ra trước commit, PostgreSQL transaction có thể rollback cả batch dimension khi
connection được xử lý phù hợp. Tuy nhiên code không explicit `try/rollback` ngay
trong hai method; error propagation/connection cleanup là lớp bảo vệ hiện có.

### Hỏi vặn

**Hỏi:** Nếu cùng hash chạy lại thì sao?

**Đáp:** Loader trả no-op; test xác nhận không sinh version mới. Unique change
identity và partial unique current index là lớp bảo vệ ở database.

**Hỏi:** Nếu change event đến trễ/out-of-order thì sao?

**Đáp:** NDS history giữ effective/delivered time, nhưng DDS hiện version theo
loader-observed time và full load có thể collapse nhiều event thành trạng thái
cuối. Backdated/out-of-order SCD2 chưa production-complete. Cần replay event theo
effective time, split interval đúng và retarget fact nếu áp dụng correction.

**Hỏi:** Vì sao `start_date` ban đầu lấy `LEAST(hire/service/created/first shift)`?

**Đáp:** Để dimension version đầu bao phủ event lịch sử sớm nhất và fact temporal
join không thất bại chỉ vì warehouse load sau thời gian nghiệp vụ. Đây là pragmatic
initial-boundary rule, không thay thế source-effective history.

## 5. DQ Gate 2: business anomaly

### Code ở đâu

- Driver overlap: [dds_loader.py](../src/warehouse/dds_loader.py#L764-L810).
- Vehicle overlap: [dds_loader.py](../src/warehouse/dds_loader.py#L811-L857).
- Trip ngoài shift: [dds_loader.py](../src/warehouse/dds_loader.py#L858-L904).
- Assignment delay âm: [dds_loader.py](../src/warehouse/dds_loader.py#L905-L932).
- Điều phối gate: [run_dq_gate2](../src/warehouse/dds_loader.py#L934-L943).

### Vì sao chạy trước facts

Gate 2 cập nhật trip anomaly tại NDS trước khi fact trip resolve junk dimension;
nhờ vậy fact nhận đúng anomaly state. WARN được log nhưng pipeline tiếp tục để
giữ reconciliation tài chính.

### SQL logic của bốn rule

| Rule | Điều kiện cốt lõi | Output state |
|---|---|---|
| Driver overlap | Cùng driver, hai shift khác nhau và interval giao nhau | DQ WARN; chưa propagate fact flag |
| Vehicle overlap | Cùng vehicle, hai shift khác nhau và interval giao nhau | DQ WARN; chưa propagate fact flag |
| Trip outside shift | pickup trước shift start hoặc dropoff sau shift end | DQ WARN, `nds_trip.is_anomaly=true` |
| Negative assignment delay | assignment timestamp sau pickup | DQ WARN, fact delay thành NULL |

Overlap detection là self-join/interval query trên NDS shift. Index
`driver_sk/vehicle_sk + time` hỗ trợ, nhưng complexity và duplicate pair handling
phải benchmark lại khi scale lớn hơn case study.

### Idempotency và concurrency

Rerun không muốn nhân DQ event, nên logger kiểm logical identity trước insert.
Đây là application-level idempotency; chưa có database unique index tương ứng,
vì vậy concurrent distributed runs vẫn là khoảng trống.

### Gap giữa DQ log và fact flag

Hai overlap checker chỉ gọi `log_dq_issue()`. `load_fact_driver_shift()` lại tạo
`is_anomaly` từ `BOOL_OR(trip pickup/dropoff ngoài shift)`. Do đó:

- DQ dashboard theo rule vẫn thấy overlap.
- `analytics.shift.is_shift_anomaly` chưa đại diện đầy đủ mọi shift anomaly spec.
- Test overlap hiện kiểm logger được gọi, chưa kiểm fact flag propagation.

Đây là finding của vòng rà code, không nên che giấu khi bảo vệ.

### Bằng chứng

[DQ Gate 2 tests](../tests/test_dds_loader.py#L349-L425) kiểm tra bốn loại anomaly.

## 6. Fact trip và fact shift

### Fact trip

Code: [load_fact_driver_trip](../src/warehouse/dds_loader.py#L944-L1120).

- Keyset pagination theo `trip_nk`, batch size 5.000.
- Join assignment, shift và các dimension.
- Resolve SCD2 driver/vehicle theo pickup time.
- Tính duration phút và assignment delay; delay âm thành null sau khi đã log.
- Dùng `Decimal` và `ROUND_HALF_UP` để tránh lỗi binary floating point với số
  tiền/thời lượng.
- Upsert theo `trip_id` để rerun không nhân dòng.

Call flow bên trong:

```text
NDS trip + assignment + shift
  → temporal join dim_driver/dim_vehicle
  → join vendor + pickup/dropoff location
  → resolve date/time keys
  → resolve junk combination
  → calculate duration/delay bằng Decimal
  → execute_values(page_size=1000)
  → ON CONFLICT(trip_id) UPDATE
  → commit mỗi batch 5.000
```

Fact chỉ được tạo khi mọi inner join dimension cần thiết resolve được. Đây là
fail-visible behavior: thiếu dimension làm mất row khỏi select và reconciliation
count sẽ fail, thay vì tự động map tất cả sang unknown mà không báo.

### Fact shift

Code: [load_fact_driver_shift](../src/warehouse/dds_loader.py#L1158-L1309).

- Chỉ lấy `shift_status='COMPLETED'` để giữ grain KPI nhất quán.
- Aggregate trip theo shift.
- `idle = duration - occupied`, clamp về 0 nếu dữ liệu làm occupied vượt duration.
- `utilization = occupied/duration`, bảo vệ mẫu số 0.
- Upsert theo `shift_id`.

`occupied_minutes` trong fact shift được tính lại từ NDS trips, không tin tuyệt
đối `occupied_minutes_source` của Dispatch. Source measure vẫn nằm ở NDS để đối
soát; DDS measure dùng trip truth cùng grain phân tích.

### Hỏi vặn

**Hỏi:** Clamp idle về 0 có che lỗi không?

**Đáp:** Nó bảo vệ measure không âm trong fact, nhưng trường hợp bất hợp lý phải
được phản ánh qua anomaly/reconciliation. Clamp không thay thế DQ; nếu xuất hiện
thường xuyên cần bổ sung rule rõ và điều tra nguồn.

Nếu occupied vượt duration, utilization vẫn có thể lớn hơn 1 vì DDL chỉ check
rate không âm. Tuy nhiên reconciliation `occupied + idle = duration` sẽ fail khi
idle đã clamp 0. Đây là lớp phát hiện hiện có, không phải bảo đảm constraint
`utilization <= 1` ở database.

**Hỏi:** Tại sao `utilization_rate` vẫn lưu ở fact nếu có thể tính lại?

**Đáp:** Lưu rate cấp shift tiện quan sát, nhưng KPI tổng phải tính ratio of sums
từ occupied và duration, không average cột rate. Hai measure gốc là nguồn đúng
cho aggregation.

**Hỏi:** Vì sao chỉ completed shift?

**Đáp:** Shift chưa hoàn tất chưa có duration/idle cuối cùng ổn định. Trộn open và
completed làm KPI utilization/revenue per hour không so sánh được.

**Hỏi:** Vì sao dùng `Decimal`, không dùng float?

**Đáp:** Float nhị phân có thể tạo sai số khó kiểm soát cho tiền và phép đối soát.
Code chuyển qua `Decimal`, quantize và `ROUND_HALF_UP`; SQL DDL cũng dùng NUMERIC/
DECIMAL. Duration reconciliation làm tròn từng trip trước khi SUM để khớp đúng
cách fact lưu.

**Hỏi:** Keyset pagination hơn OFFSET ở đâu?

**Đáp:** Query `WHERE business_key > last_key ORDER BY key LIMIT n` không phải
scan/bỏ qua ngày càng nhiều row như OFFSET lớn, đồng thời ổn định khi đọc dataset
immutable theo release. Nó yêu cầu key có thứ tự, unique và không đổi giữa run.

### Bằng chứng

[Fact calculation tests](../tests/test_dds_loader.py#L220-L267) kiểm tra duration,
delay, zero division, idle và utilization; [fact contract tests](../tests/test_dds_loader.py#L500-L518)
kiểm tra keyset pagination và completed grain.

## 7. Analytics views, KPI và chống fan-out

### Code ở đâu

- Trip pickup/dropoff: [SQL lines 100–247](../sql/analytics/01_certified_datasets.sql#L100-L247).
- Shift grain: [analytics.shift](../sql/analytics/01_certified_datasets.sql#L248-L324).
- Protected shift-trip aggregate: [SQL lines 325–339](../sql/analytics/01_certified_datasets.sql#L325-L339).
- OLAP views: [SQL lines 340–471](../sql/analytics/01_certified_datasets.sql#L340-L471).
- DQ views: [SQL lines 472–574](../sql/analytics/01_certified_datasets.sql#L472-L574).
- Action queues/peer views: [SQL lines 575–813](../sql/analytics/01_certified_datasets.sql#L575-L813).

### Fan-out là gì

Nếu một shift có 10 trip và join fact shift với 10 fact trip rồi SUM doanh thu
shift, doanh thu shift bị lặp 10 lần. Dự án tách dataset theo fact ownership và
dùng aggregate boundary khi thực sự cần kết hợp.

### Vì sao analytics view thay vì cho Superset tự join

View khóa date role, grain và field semantics; metric catalog khóa công thức.
Điều này giảm khả năng mỗi chart tự định nghĩa KPI khác nhau và tạo “nhiều sự
thật”.

### View nào sở hữu grain nào

| View | Grain | Điểm code quan trọng |
|---|---|---|
| `trip_pickup` | 1 trip | Pickup date/location role, trip anomaly qua junk dimension |
| `trip_dropoff` | 1 trip | Dropoff role tường minh, cùng trip measures |
| `shift` | 1 completed shift | Shift ratios cấp dòng và location lấy qua NDS source shift |
| `shift_trip_aggregate` | 1 shift | Aggregate trip trước khi kết hợp, chống fan-out |
| `dq_summary` | 1 nhóm event | `UNION ALL` issue và quarantine, không giả vờ cùng một count |
| `dq_batch_summary` | 1 successful NDS batch | LEFT JOIN để batch 0 issue vẫn xuất hiện |
| `driver_performance_monthly` | 1 driver-month | Giữ additive components để recompute ratio |
| `vehicle_performance_monthly` | 1 vehicle-month | Peer threshold provisional theo vehicle type |

### Logic review queue phải nói đúng

- Driver-month chỉ `needs_review` khi có ít nhất 10 completed shifts, revenue/hour
  percentile dưới 25% và idle/shift percentile từ 75% trở lên trong cùng tháng.
- Vehicle-month chỉ là exploratory candidate khi ít nhất 10 shifts và utilization
  percentile dưới 25% trong cùng month + vehicle type.
- `driver_performance_summary` all-history có rule percentile nhưng không có
  minimum sample; dashboard hành động ưu tiên monthly/latest view để có sample
  boundary rõ.

Code: [driver/vehicle peer logic](../sql/analytics/01_certified_datasets.sql#L647-L813).

### DQ batch zero-state

`dq_batch_summary` bắt đầu từ audit batch thành công rồi LEFT JOIN DQ rollup. Vì
vậy latest run không issue vẫn hiện số 0. Nếu bắt đầu từ `dq_issue`, “latest” sẽ
vô tình nghĩa là “latest run từng có lỗi”. Đây là một quyết định semantic quan
trọng, không chỉ là UI.

### Điểm giới hạn

`analytics.shift` phải join NDS để lấy assigned start/end location vì fact shift
không chứa location key. Dashboard vẫn chỉ query analytics boundary, nhưng view
chưa thuần DDS. Nếu muốn mart tự chứa hoàn toàn, cần thêm role-playing location
keys vào fact shift và migration/reconciliation tương ứng.

### Bằng chứng

[Analytics contract tests](../tests/test_analytics_contract.py#L25-L168) khóa
view, grain, read-only boundary, ratio/revenue decision và traceability.

## 8. Data Mining

### K-Means

Code: [run_driver_segmentation](../src/analytics/data_mining.py#L214-L294).

- SQL aggregate đúng driver grain.
- Chỉ dùng driver có ít nhất 10 ca; clip outlier 1%/99% rồi `RobustScaler`.
- So sánh `k=2..8`, loại cụm nhỏ, chọn bằng silhouette/DB tie-break.
- Mean ARI qua năm seed khác baseline kiểm tra stability; silhouette/DB/CH và provenance lưu theo run.

Feature query dùng ratio-of-sums ở driver grain, sau đó `COALESCE(..., 0)` cho
missing trip features. Điều này giúp model chạy ổn định nhưng giá trị 0 có thể
trộn “thật sự bằng 0” với “không quan sát được”; production nên có missingness
analysis/imputation contract riêng.

Label không đến từ K-Means: code xếp cluster theo `revenue_per_hour` trung bình
và xuất `Revenue profile rank r of k`. Đây là heuristic diễn giải trung tính,
không phải ground-truth class hoặc đánh giá nhân sự.

### Apriori

Code: [run_apriori](../src/analytics/data_mining.py#L136-L172) và
[run_route_association_rules](../src/analytics/data_mining.py#L297-L361).

- Tạo frequent 1/2/3-itemsets.
- Prune candidate 3-itemset nếu các subset 2-item không frequent — áp dụng tính
  chất downward closure của Apriori.
- Chỉ sinh rule có consequent dropoff để tăng khả năng diễn giải.
- Sort theo lift và cap publication.

Apriori code dùng tính chất downward closure khi tạo candidate bậc 3: chỉ đếm
candidate nếu cả ba subset bậc 2 đều frequent. Tuy nhiên nó dừng ở bậc 3, không
lặp tổng quát đến khi không còn frequent itemset.

### Điểm phải thừa nhận

Physical output tables append theo từng run; `analytics.model_runs` là ledger
provenance và `analytics.current_*` views chỉ expose một successful run hiện hành
cho dashboard. Vì vậy historical comparison không làm dashboard trộn nhiều run.

Các giới hạn code-level khác:

- Nhiều feature có tương quan (utilization, idle, revenue/hour); scaling không
  loại multicollinearity hay bảo đảm cluster có ý nghĩa nghiệp vụ.
- Apriori dùng sample stratified xác định, nhưng vẫn giới hạn frequent itemset
  bậc 3; production quy mô lớn nên dùng implementation tối ưu hơn.
- Publication top 100 theo lift có thể ưu tiên rule hiếm; dashboard vẫn phải hiển
  thị support/confidence/basket count.
- Kết quả append theo model run và current view chỉ đọc một successful run; failed
  run hiện chưa được ghi riêng vì transaction rollback toàn bộ khi lỗi.

## 9. Superset và Streamlit

### Superset

- Dataset/metric/chart helpers: [provision_superset.py](../scripts/provision_superset.py#L502-L712).
- Dashboard layout: [dashboard_layout](../scripts/provision_superset.py#L713-L858).
- Security roles: [ensure_security_roles](../scripts/provision_superset.py#L859-L910).
- Main provision flow: [main](../scripts/provision_superset.py#L911-L980).

Provisioning bằng code giúp dashboard có thể tái tạo, review và contract-test,
thay vì chỉ tồn tại trong thao tác UI khó truy vết. Read-only role chỉ expose
analytics boundary.

Provision flow cụ thể:

```text
ensure_database()
  → connection URI từ environment
  → allow_dml/ctas/cvas/file_upload = false
ensure_dataset() × 14
  → schema analytics, main time column, certification/exploratory metadata
ensure_metrics() × dataset
  → xóa metric stale, upsert expression/format/description
ensure_chart() × 35
  → params + query_context + certification + owner
dashboard_layout()
  → 6 tabs + context cards + chart positions
ensure_security_roles()
  → viewer/role/dataset access
commit
```

Code hiện provision 14 datasets, 109 metric instances và 35 charts theo contract
test. `ensure_metrics()` xóa metric không còn trong declarative definition, nên
script không chỉ thêm mới mà còn đồng bộ state.

### Defense in depth cho BI read-only

1. Superset database object tắt DML/CTAS/CVAS/upload.
2. Viewer role chỉ được datasource access đã provision.
3. PostgreSQL role `superset_ro` chỉ được SELECT schema `analytics` và bị revoke
   staging/audit/dq/nds/dds.
4. Smoke test chủ động thử các statement bị cấm.

Tham chiếu: [read-only grants](../sql/analytics/02_superset_readonly_role.sql) và
[Superset smoke tests](../scripts/smoke_test_superset.py#L31-L283).

### Streamlit

- UI: [app/streamlit_app.py](../app/streamlit_app.py).
- Monitoring repository và sanitization: [repository.py](../src/monitoring/repository.py).
- Pipeline lock: [PipelineLock](../src/monitoring/repository.py#L101-L275).

Streamlit gọi `PipelineRunner`, không dùng subprocess/raw SQL trong UI. Repository
tách data access khỏi view; lock tránh hai pipeline local chạy đồng thời và có
cơ chế stale-lock recovery.

### Streamlit call flow và an toàn

```text
User click
  → confirmation cho data-writing step
  → PipelineLock.acquire()
  → PipelineRunner.run()
  → lưu PipelineRunResult trong session_state
  → sanitize lỗi trước khi render
  → finally PipelineLock.release()
```

- Health check được cache để tránh mỗi rerun UI tạo nhiều connection.
- Source Explorer dùng allowlist system/entity và clamp limit 1–100; table name
  chỉ được lấy sau allowlist, limit parameterized.
- `sanitize_message()` thay secret environment value, key-value secret và
  credential trong URI trước khi hiển thị.
- `is_dds_ready()` yêu cầu full result SUCCEEDED và `mark_dds_ready` SUCCEEDED;
  dry-run không bao giờ được coi là ready.

### Điểm giáo viên có thể bắt

- `PipelineLock` là file lock local, không phải distributed lock giữa nhiều host.
- UI chạy pipeline đồng bộ trong request/session; tác vụ dài có thể làm UX timeout.
- Superset provision dùng ORM/query-context nội bộ, nên pin version và contract
  test là bắt buộc; upgrade Superset có thể cần sửa adapter.
- Copy toàn bộ Gamma permissions rồi cộng datasource access là thuận tiện cho
  local demo; production cần least-privilege review chi tiết từng permission.

### Hỏi vặn

**Hỏi:** Streamlit có phải BI dashboard chính không?

**Đáp:** Không. Streamlit là pipeline control/monitoring panel. Superset là lớp
dashboard phân tích nghiệp vụ.

**Hỏi:** Vì sao provision Superset bằng Python?

**Đáp:** Để idempotent setup, thống nhất metric/chart definition và tái tạo demo.
Nhược điểm là phụ thuộc API/model nội bộ của phiên bản Superset nên cần pin version
và contract test.

**Hỏi:** Benchmark chứng minh điều gì?

**Đáp:** Script gọi chart API nhiều lần, ghi latency và p95 cho đúng dashboard
provisioned. Nó chứng minh hiệu năng trong môi trường local/run cụ thể, không phải
SLA production. Smoke test còn kiểm benchmark artifact có khớp chart count hiện
hành để tránh dùng số cũ.

## 10. Tests và bằng chứng

| Điều cần chứng minh | Test/evidence |
|---|---|
| Staging conversion/hash/checksum | [test_load_staging.py](../tests/test_load_staging.py) |
| NDS DQ/inferred/quarantine | [test_nds_loader.py](../tests/test_nds_loader.py) |
| SCD2, fact calculations, anomaly | [test_dds_loader.py](../tests/test_dds_loader.py) |
| Pipeline order/failure/resume | [test_pipeline_runner.py](../tests/test_pipeline_runner.py) |
| Reconciliation logic | [test_pipeline_validation.py](../tests/test_pipeline_validation.py) |
| Analytics semantic boundary | [test_analytics_contract.py](../tests/test_analytics_contract.py) |
| Mining structured provenance | [test_data_mining_provenance.py](../tests/test_data_mining_provenance.py) |
| Superset security/demo contract | [test_superset_demo_contract.py](../tests/test_superset_demo_contract.py) |
| Streamlit architecture/lock | [test_streamlit_control_panel.py](../tests/test_streamlit_control_panel.py) |
| Full release numbers | [full-release reconciliation](../docs/evidence/full-release-reconciliation.md) |

### Test taxonomy thực tế

| Loại | Ví dụ | Chứng minh được | Không chứng minh được |
|---|---|---|---|
| Pure unit | hash, K-Means/Apriori helper, calculation | Logic nhỏ deterministic | DB/schema thật |
| Mocked loader test | NDS/DDS methods với mocked cursor | SQL branch/call contract | Query chạy đúng trên PostgreSQL mọi edge case |
| Static contract test | đọc SQL/Python text | Object/formula/boundary không bị sửa lệch | Runtime behavior |
| Database fixture validation | `validate_dq_fixture` | DQ, inferred, SCD rerun trên DB test | Full scale/performance |
| Full-release evidence | reconciliation report | Count/measure trên release/run ghi nhận | Mọi release tương lai |
| Superset smoke/benchmark | REST + DB permission checks | Metadata, quyền và latency local | Production concurrency/SLA |

141 tests chạy nhanh chủ yếu là unit/contract tests. Không được nói “141 tests
đều chạy full database”. Bằng chứng mạnh nhất cho end-to-end là database fixture,
full-release reconciliation và Superset smoke test, mỗi loại có phạm vi riêng.

### Số liệu bằng chứng full load hiện được tài liệu hóa

- Staging trip assignments, NDS trips, NDS assignments và DDS trip facts:
  `2.304.276` dòng tương ứng.
- NDS completed shifts và DDS shift facts: `157.379` dòng.
- Revenue: `48.535.884,47`; distance: `87.426.352,1700`;
  duration rounded per trip: `48.423.718,63` — khớp NDS/DDS theo evidence.
- Duplicate fact/natural key và multiple-current SCD2: `0`.
- Rerun DDS không tạo version mới cho cùng payload driver/vehicle.

Không nên học thuộc số mà không nói nguồn. Hãy mở evidence và giải thích đây là
kết quả của một release/run đã ghi nhận, không phải hằng số của mọi dữ liệu.

### Cách trả lời “test này test cái gì?”

Dùng bốn phần: **fixture/input → hành vi gọi → assertion → rủi ro chưa phủ**.
Ví dụ `test_new_version_when_hash_changed`: mock current dimension hash khác,
gọi `load_dim_driver`, assert có update đóng version và insert version mới. Test
này không chứng minh replay late-arriving event theo effective time; đó chính là
gap temporal đã nêu.

---

# Phần III: Bộ câu hỏi phản biện

## Nhóm A — Phạm vi và dữ liệu

### 1. Điểm mới của đề tài là gì?

Không khẳng định thuật toán mới. Điểm đóng góp là một case study end-to-end có
data contract, heterogeneous sources, lineage/DQ, NDS/DDS, semantic BI, ROLAP và
exploratory mining được nối với quyết định vận hành.

### 2. Tại sao chọn 2020–2021, có ảnh hưởng COVID không?

Có thể có structural break do COVID, nên trend không đại diện giai đoạn bình
thường. Đồ án phân tích đúng giai đoạn dữ liệu, không suy rộng thành baseline
vĩnh viễn. Nếu nghiên cứu nghiệp vụ sâu cần biến/segmentation theo pandemic phase.

### 3. Có PII thật không?

Không. Driver/fleet synthetic; identifier/token không đại diện danh tính thật.
Raw TLC công khai vẫn tuân data policy và không commit full data vào Git.

### 4. Google Drive có phải nguồn thứ năm?

Không. Đó là kênh phân phối canonical release. Nguồn nghiệp vụ logic là TLC,
HR, Fleet và Dispatch.

## Nhóm B — DWH và ETL

### 5. ETL hay ELT?

Pipeline là hybrid: Python extract/normalize metadata vào Staging; transformation
và load NDS/DDS dùng Python điều phối với SQL trong PostgreSQL. Có thể mô tả là
ETL/ELT-style warehouse pipeline, nhưng tránh tranh luận nhãn; hãy nêu rõ nơi
từng transformation chạy.

### 6. Vì sao PostgreSQL cho cả source Dispatch và warehouse?

Cùng engine không đồng nghĩa cùng hệ thống. Chúng là service/database và credential
boundary riêng. Mục tiêu heterogeneous vẫn có file, MySQL, MongoDB và PostgreSQL;
tách source/warehouse bảo vệ operational–analytical boundary.

### 7. Nếu schema nguồn đổi thì sao?

Source contract và staging loader là điểm phát hiện. Hiện có contract tests và
explicit columns; hướng production cần schema versioning, compatibility rule và
alert/quarantine cho drift thay vì silent coercion.

### 8. Nếu pipeline chết giữa chừng thì sao?

Loader dùng transaction/rollback theo source/entity và audit status; fact upsert
và SCD hash hỗ trợ rerun. Tuy nhiên atomic publish qua work tables chưa hoàn thiện,
nên không tuyên bố exactly-once production semantics.

### 9. Vì sao `DELETE staging WHERE release_id` vẫn gọi idempotent?

Với canonical full-release load, xóa rồi nạp lại cùng release tạo cùng staging
state và tránh duplicate. Đây là full refresh idempotency, không phải incremental
append/CDC strategy.

### 10. Hash collision thì sao?

SHA-256 collision về lý thuyết có thể nhưng xác suất cực nhỏ cho change detection
case study. Natural key/unique constraint và source lineage vẫn là ràng buộc chính;
hash không thay thế business key.

## Nhóm C — Mô hình dữ liệu và KPI

### 11. Fact trip và fact shift có dữ liệu trùng không?

Chúng biểu diễn cùng hoạt động ở hai grain. Measure shift là aggregation phục vụ
shift analysis; không cộng chéo hai fact. Reconciliation dùng sự trùng logic để
kiểm tra, không coi là hai nguồn doanh thu độc lập.

### 12. Semi-additive/non-additive là gì?

Additive cộng được qua mọi dimension phù hợp; semi-additive chỉ cộng qua một số
dimension (thường snapshot không cộng qua time); non-additive như ratio/average
phải tính lại từ numerator/denominator. Utilization và revenue/hour của dự án là
non-additive.

### 13. Tại sao có hai analytics view pickup/dropoff?

Cùng trip nhưng date/location role khác. Tách view giảm ambiguous join/filter ở
BI tool và làm chart nói rõ đang phân tích pickup hay dropoff.

### 14. `average_fare` dùng fare hay total amount?

Catalog định nghĩa average fare từ `fare_amount`; total payment revenue dùng
`total_amount`. Không tráo hai khái niệm vì total gồm thêm tip/tax/tolls/surcharge.

### 15. Null và denominator 0 xử lý thế nào?

Amount thường COALESCE 0 khi cộng theo contract; denominator 0 trả NULL để phân
biệt “không tính được” với giá trị thực bằng 0.

## Nhóm D — DQ và kiểm thử

### 16. Vì sao negative amount chỉ WARN?

Contract hiện ưu tiên giữ dữ liệu tài chính nguồn và đánh dấu để điều tra vì số
âm có thể liên quan adjustment/refund. Nếu business owner xác nhận không hợp lệ,
rule có thể nâng ERROR; thay đổi severity phải cập nhật contract và test.

### 17. Quarantine có sửa dữ liệu không?

Không. Nó giữ raw payload và rule để điều tra. Quy trình correction/replay đầy
đủ là bước vận hành tiếp theo, không âm thầm mutate raw.

### 18. Unit test, integration test và reconciliation khác nhau gì?

Unit test kiểm logic nhỏ cô lập; integration test kiểm thành phần/database cùng
nhau; reconciliation so expected invariant giữa tầng trên dữ liệu cụ thể. Cần cả
ba vì code chạy không lỗi vẫn có thể làm mất hoặc nhân dữ liệu.

## Nhóm E — BI, OLAP và Mining

### 19. Dashboard có bao nhiêu “sự thật” KPI?

Một semantic contract/certified catalog, nhưng metric được đặt trên dataset sở
hữu đúng grain. Không tạo một metric mơ hồ dùng đồng thời hai fact.

### 20. K-Means có supervised không?

Không. Đây là unsupervised clustering, không có nhãn ground truth. Segment label
được gán sau dựa trên centroid để diễn giải.

### 21. Silhouette tốt có nghĩa business segment tốt không?

Không hoàn toàn. Silhouette đo separation/cohesion hình học, không đảm bảo công
bằng, ổn định qua thời gian hoặc usefulness nghiệp vụ. Cần thêm stability test và
business validation.

### 22. Support thấp nhưng lift cao có dùng được không?

Có thể là pattern hiếm, dễ nhiễu và khó triển khai. Phải cân bằng support,
confidence, lift, số basket và ý nghĩa vận hành; không xếp hạng chỉ bằng lift.

### 23. Association rule có chiều nhân quả không?

Không. Ký hiệu antecedent → consequent là conditional association, không chứng
minh antecedent gây consequent.

### 24. Tại sao mining không certified?

Vì output phụ thuộc feature, hyperparameter, sample và model run; nó hỗ trợ khám
phá chứ không phải định nghĩa KPI ổn định. Provenance và training window giúp
người dùng biết kết quả được tạo thế nào.

## Nhóm F — Giáo viên chỉ trực tiếp vào code

### 25. Entry point thật của pipeline nằm đâu?

CLI bắt đầu ở `scripts/run_pipeline.py`, nhưng logic ở
`src/orchestration/pipeline_runner.py`. Streamlit cũng gọi `PipelineRunner`, nên
không có hai implementation pipeline khác nhau.

### 26. Vì sao `batch_id` của runner và audit loader có thể khác?

Runner tạo run/batch ID cho result contract, nhưng các handler hiện khởi tạo
loader chỉ với `release_id`; loader tự tạo UUID audit. Đây là gap lineage hiện
tại, không phải chủ ý nghiệp vụ. Cách sửa là truyền batch ID hoặc thiết kế
parent-run/child-batch relation rõ trong audit schema.

### 27. `loaded` có phải số insert mới không?

Không luôn đúng. NDS/fact dùng upsert và thường tăng `loaded` cho row đã xử lý,
kể cả update. DDS dimension riêng mới trả `new_versions` và `no_op`. Telemetry
muốn chính xác phải phân biệt inserted/updated/no-op/rejected.

### 28. Vì sao NDS trip ít hơn raw TLC?

`load_trips()` inner join TLC staging với assignment staging. Chỉ trip hợp lệ đã
được gán mới vào NDS population. Invalid/no-capacity được theo dõi ngoài population.
Đối soát đúng là assignment ↔ NDS trip, không phải raw TLC ↔ NDS trip.

### 29. Driver change feed đi qua code thế nào?

`load_driver_changes()` sort theo `delivered_at,event_id`, insert event vào
`nds_driver_history`, rồi update `home_borough` current master. DDS sau đó hash
current master. Vì vậy history event có ở NDS nhưng full historical SCD2 interval
chưa được materialize đầy đủ theo `effective_at`.

### 30. Những thuộc tính nào thực sự làm SCD2 đổi version?

Driver: `home_borough`, `employment_status`. Vehicle: `vehicle_status`. License,
display name, experience, plate/model/inspection hiện Type 1 trên current version.

### 31. Vì sao fact join dimension bằng khoảng thời gian?

Để natural key giống nhau vẫn resolve đúng surrogate version tại thời điểm trip/
shift. Điều kiện là start inclusive và end exclusive, tránh một event rơi vào cả
hai version tại boundary.

### 32. `row_hash` khác file checksum thế nào?

File checksum nhận diện toàn file/release artifact; row hash nhận diện normalized
business payload của một row. File đổi chưa chắc mọi row đổi; row hash không chứng
minh file bytes nguyên vẹn.

### 33. Vì sao `ON CONFLICT DO UPDATE` dù payload có thể giống hệt?

Nó bảo đảm final state idempotent đơn giản. Trade-off là có thể tạo write/update
không cần thiết và đổi `updated_at/batch_id`. SCD dimensions có hash/no-op riêng;
facts hiện ưu tiên deterministic upsert hơn change-minimizing merge.

### 34. Vì sao commit theo chunk thay vì một transaction toàn release?

Giảm transaction size, lock/WAL và memory cho hàng triệu trips. Trade-off là
partial commit khi chunk sau lỗi; audit/reconciliation phát hiện và rerun upsert.
Work-table publish sẽ mạnh hơn nhưng chưa triển khai đầy đủ.

### 35. Keyset pagination có bỏ sót row không?

Với immutable snapshot và unique stable ordered key, `key > last_key` không bỏ
sót. Nếu key bị update/chèn trong lúc scan hoặc không unique, có rủi ro; source
release/staging được coi là ổn định trong load.

### 36. Vì sao table name được f-string trong Source Explorer mà vẫn an toàn?

Vì `system` và `entity` phải qua fixed allowlist trước khi ghép; limit bị clamp
và parameterized. Nếu bỏ allowlist, f-string identifier từ user input sẽ nguy hiểm.

### 37. `mark_dds_ready` có kiểm database không?

Không trực tiếp. Nó là marker cuối config; bước reconciliation trước đó mới query
invariant. `is_dds_ready()` yêu cầu overall success và marker success. Nếu chạy
riêng marker step, contract có thể cho success mà không chứng minh warehouse;
UI readiness nên chỉ dùng full configured run.

### 38. Tại sao mining không còn `TRUNCATE` output?

Physical tables append kết quả theo `model_run_id`; `analytics.model_runs` lưu
provenance và chỉ đánh dấu một successful run hiện hành cho mỗi model type.
Dashboard đọc `analytics.current_driver_segments` và
`analytics.current_route_association_rules`, nên vừa có current-state boundary
đơn giản vừa giữ được lịch sử phục vụ audit/model monitoring. Việc đổi cờ
`is_current`, ghi run ledger và insert result cùng transaction bảo toàn run cũ
nếu publish mới thất bại.

**Hỏi vặn cấp hai:** Nếu hai model run chạy đồng thời thì cờ `is_current` có chắc
chỉ còn một dòng không?

**Đáp:** Database có unique partial index theo `model_type WHERE is_current`, nên
không thể commit hai current run cùng loại. Một transaction có thể bị conflict và
phải retry; đây là bảo vệ tính nhất quán, không phải cơ chế scheduler phân tán.

### 39. Superset “idempotent provision” nghĩa là gì?

Script lookup database/dataset/chart theo identity, update metadata nếu có, tạo
nếu thiếu; metric ngoài declarative spec bị xóa. Idempotent ở final metadata
state, không có nghĩa primary key/object timestamp không đổi.

### 40. Test 141 cases có phải end-to-end hết không?

Không. Phần lớn là unit/static contract; một số dùng mock cursor. End-to-end cần
database fixture, full-release reconciliation, Superset smoke và benchmark. Phải
nói đúng phạm vi từng bằng chứng.

### 41. Overlap shift có làm `is_shift_anomaly=true` chưa?

Chưa đầy đủ. Driver/vehicle overlap checker ghi DQ WARN; fact shift hiện lấy flag
từ trip-outside-shift. Đây là mismatch giữa spec và implementation. Cách sửa là
tạo tập shift ID vi phạm từ cả ba rule rồi join/update khi build fact, sau đó thêm
test fact propagation và cập nhật reconciliation/semantic evidence.

## Câu trả lời khi không chắc

Không đoán. Dùng mẫu:

> Trong phạm vi hiện tại, nhóm đã triển khai phần A và có test/evidence tại file
> B. Trường hợp thầy/cô hỏi là edge case C, hiện tài liệu chưa khẳng định đã xử
> lý đầy đủ. Nếu mở rộng, nhóm sẽ bổ sung rule D, transaction/test E và cập nhật
> contract trước khi coi là hoàn thành.

---

# Kịch bản trình bày gợi ý

## Bản 12–15 phút

| Thời lượng | Nội dung | Điều phải chốt |
|---:|---|---|
| 1 phút | Bài toán và người dùng | TLC thiếu driver/vehicle/shift context |
| 1,5 phút | Nguồn và scope | TLC thật; vận hành synthetic; bốn source interfaces |
| 2 phút | Kiến trúc | Trách nhiệm Staging, DQ/Audit, NDS, DDS |
| 2 phút | Mô hình dữ liệu | Hai fact grain; SCD2; role-playing/junk dimensions |
| 2 phút | DQ và lineage | ERROR vs WARN vs anomaly; quarantine; reconciliation |
| 2 phút | KPI và dashboard | Ratio of sums; fact ownership; decision-first tabs |
| 1,5 phút | OLAP và mining | ROLAP; K-Means/Apriori đều exploratory |
| 1 phút | Demo code/evidence | Mở runner → loader → test/reconciliation |
| 1 phút | Giới hạn/kết luận | Historical case study, không realtime/causal/HR scoring |

## Câu chuyển phần

- **Bài toán → kiến trúc:** “Từ khoảng trống dữ liệu đó, nhóm thiết kế bốn ranh
  giới nguồn và một pipeline tích hợp có truy vết.”
- **Kiến trúc → model:** “Sau khi chuẩn hóa tại NDS, nhóm không cho BI join trực
  tiếp mà công bố hai grain phân tích trong DDS.”
- **Model → KPI:** “Grain quyết định phép tính nào hợp lệ; vì vậy nhóm khóa công
  thức trong semantic contract.”
- **KPI → mining:** “Certified KPI mô tả điều đã quan sát; mining chỉ mở rộng góc
  khám phá và được tách nhãn để tránh biến mô hình thành sự thật nghiệp vụ.”
- **Kết:** “Đóng góp chính là tính nhất quán từ source contract đến dashboard và
  bằng chứng reconciliation, đồng thời công bố rõ giới hạn.”

## Demo code 3 phút

1. Mở [PipelineRunner](../src/orchestration/pipeline_runner.py#L88-L118) để chỉ
   thứ tự, resume/fail-fast.
2. Mở [Staging metadata/hash](../src/ingestion/staging_loader.py#L33-L67) để chỉ
   lineage và determinism.
3. Mở [DQ/quarantine](../src/warehouse/nds_loader.py#L431-L512) để phân biệt log
   với cách ly.
4. Mở [SCD2](../src/warehouse/dds_loader.py#L525-L647) và
   [fact temporal join](../src/warehouse/dds_loader.py#L965-L977).
5. Mở [ratio calculation](../src/warehouse/dds_loader.py#L1224-L1249), sau đó
   [test tương ứng](../tests/test_dds_loader.py#L241-L267).
6. Kết bằng [reconciliation](../src/warehouse/pipeline_validation.py#L32-L181),
   không kết bằng một ảnh dashboard đơn lẻ.

---

# Checklist trước khi vào phòng

## Nội dung

- [ ] Nói đúng TLC thật và driver/fleet/dispatch synthetic.
- [ ] Không gọi Google Drive là source system.
- [ ] Nói đúng không có ODS và lý do.
- [ ] Thuộc grain của hai fact.
- [ ] Phân biệt natural key, surrogate key và SCD2 key.
- [ ] Phân biệt ERROR, WARN, anomaly, audit và quarantine.
- [ ] Giải thích ratio of sums bằng ví dụ hai ca.
- [ ] Không gọi revenue là profit hoặc observed activity là unmet demand.
- [ ] Nói đúng ROLAP, không gọi MOLAP cube.
- [ ] Gắn nhãn K-Means/Apriori là exploratory, không causal/automatic decision.
- [ ] Thừa nhận work-table publish và shared orchestration batch lineage chưa
  hoàn thiện đầy đủ.

## Kỹ thuật

- [ ] Repository mở sẵn tại `green-taxi-bi-project`.
- [ ] File này mở ở mục [Bản đồ code](#bản-đồ-code-30-giây).
- [ ] Docker/services cần demo đã health check.
- [ ] Superset và Streamlit dùng đúng local URL/credential demo an toàn.
- [ ] Có phương án demo bằng screenshot/evidence nếu service lỗi.
- [ ] Không hiển thị `.env`, password, token hoặc dữ liệu riêng tư.
- [ ] Đã chạy test phù hợp gần thời điểm báo cáo.

## Lệnh kiểm tra

```powershell
python -m unittest discover -s tests -v
```

Tài liệu demo kỹ thuật hiện có:
[technical_demo_script.md](demo/technical_demo_script.md) và
[Superset runbook](../docs/analytics/superset-local-demo-runbook.md).

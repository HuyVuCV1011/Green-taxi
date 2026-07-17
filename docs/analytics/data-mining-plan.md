# Data Mining Plan

Status: `IMPLEMENTED`

## Business purpose

Data Mining extension phải tạo tri thức hỗ trợ vận hành, không chỉ chạy thuật
toán để minh họa. Hai bài toán được chọn vì phù hợp dữ liệu hiện có và trực tiếp
hỗ trợ quản lý tài xế/đội xe:

1. Phân nhóm tài xế theo hiệu suất vận hành.
2. Khám phá pattern tuyến/khu vực để hỗ trợ điều phối theo lịch sử nhu cầu.

Quy trình thực hiện theo tinh thần CRISP-DM/KDD: business understanding, data
understanding, preparation, modeling, evaluation và deployment vào analytics.

## DM01 - Driver segmentation

| Item | Decision |
|---|---|
| Business question | Driver nào nên được giữ làm benchmark, driver nào cần hỗ trợ hoặc điều phối lại? |
| Method | Clustering, ưu tiên K-Means |
| Learning type | Unsupervised |
| Input grain | Một dòng mỗi driver hoặc driver-month |
| Output | History `analytics.driver_segments`; dashboard `analytics.current_driver_segments` |

Candidate features:

- `revenue_per_hour`
- `utilization_rate`
- `trips_per_shift`
- `average_trip_distance`
- `tips_per_trip`
- `idle_minutes_per_shift`
- `completed_shifts`

Evaluation:

- Chỉ fit driver có ít nhất 10 completed shifts; metric trip thiếu được thay bằng
  0 theo policy đã lưu trong provenance.
- Winsorize từng feature ở quantile 1%/99%, sau đó dùng `RobustScaler`.
- Thử `k=2..8`, loại nghiệm có cụm nhỏ hơn
  `max(5, ceil(2% số driver))`; chọn silhouette lớn nhất, tie-break bằng
  Davies–Bouldin nhỏ nhất rồi `k` nhỏ hơn. Calinski–Harabasz là metric báo cáo.
- Fit baseline bằng seed 42; mean ARI chỉ so với năm seed khác baseline để không
  làm điểm stability tăng giả tạo bởi self-comparison.
- Không hard-code nhãn đánh giá nhân sự. Đọc centroid trên thang gốc và đặt nhãn
  trung tính `Revenue profile rank r of k`.

Business deployment:

- Superset table/scatter plot cho driver segment.
- Bộ lọc segment để xem doanh thu, utilization, idle time theo nhóm.
- Kết quả dùng để đề xuất coaching hoặc điều phối, không dùng để đánh giá nhân
  sự tuyệt đối.

## DM02 - Route and demand association rules

| Item | Decision |
|---|---|
| Business question | Những pattern pickup/dropoff theo thời gian nào lặp lại đủ mạnh để hỗ trợ bố trí xe? |
| Method | Association rules bằng Apriori |
| Learning type | Unsupervised |
| Input grain | Một basket theo trip hoặc zone-hour bucket |
| Output | History `analytics.route_association_rules`; dashboard `analytics.current_route_association_rules` |

Candidate basket items:

- `pickup_borough`
- `pickup_zone`
- `dropoff_borough`
- `dropoff_zone`
- `hour_bucket`
- `day_type` hoặc `day_name`
- `vendor`

Example rules:

- `{pickup_borough=Queens, hour_bucket=Morning} -> {dropoff_borough=Manhattan}`
- `{pickup_zone=A, day_type=Weekday} -> {dropoff_zone=B}`

Evaluation:

- Report `support`, `confidence` và `lift`.
- Không chọn luật chỉ vì confidence cao; lift/interest phải cho thấy luật có ý
  nghĩa hơn tần suất nền.
- Loại các luật có support quá thấp vì khó dùng cho điều phối.

Business deployment:

- Superset table cho top rules theo lift/support/confidence.
- Filter theo borough, hour bucket và weekday/weekend.
- Dùng rule như gợi ý bố trí xe theo pattern lịch sử, không phải dự báo real-time.

## Out of scope

- Deep learning.
- Real-time demand forecasting.
- Customer segmentation hoặc marketing.
- Payroll, net profit, maintenance cost vì dữ liệu hiện tại chưa hỗ trợ.
- Tự động ra quyết định điều phối tài xế.

## Acceptance criteria

- Có notebook hoặc script reproducible cho từng bài toán. (Đã có script `scripts/run_data_mining.py` và module `src/analytics/data_mining.py`)
- Có bảng/view kết quả trong `analytics`: history tables, `analytics.model_runs` ledger và current-run dashboard views.
- Có giải thích feature, thuật toán, tham số, metric đánh giá và giới hạn. (Xem chi tiết bên dưới)
- Kết quả hiển thị được trong Superset mà không query trực tiếp staging/NDS. (Tab 6: Exploratory models trên Superset dashboard)
- Kết luận gắn với quyết định vận hành cụ thể.

## Implementation details

### DM01 - Driver Segmentation (K-Means)

- **Eligibility và missing policy**: chỉ driver có ít nhất 10 completed shifts được fit. Metric trip bị thiếu do không có chuyến được thay bằng 0; vô cực được thay bằng 0 và policy này được lưu trong provenance.
- **Outlier và scaling**: mỗi feature bị winsorize ở quantile 1%/99%, sau đó dùng `RobustScaler`, giảm ảnh hưởng của outlier hơn `StandardScaler`.
- **Chọn mô hình**: thử `k=2..8`; loại nghiệm có cụm nhỏ hơn `max(5, ceil(2% số driver))`; chọn silhouette lớn nhất, tie-break bằng Davies–Bouldin nhỏ nhất rồi `k` nhỏ hơn. Báo cáo thêm Calinski–Harabasz.
- **Stability**: baseline dùng seed 42; fit lại với năm seed khác baseline và báo cáo mean Adjusted Rand Index (ARI). Không đưa chính baseline vào trung bình vì ARI tự so sánh luôn bằng 1. Đây là kiểm tra độ lặp của partition, không phải accuracy vì bài toán không có nhãn thật.
- **Labeling**: nhãn trung tính `Revenue profile rank r of k`, xếp theo revenue/hour centroid trên thang gốc. Không biến nhãn exploratory thành đánh giá nhân sự.
- **Database output**: `analytics.driver_segments` giữ lịch sử; `analytics.current_driver_segments` chỉ expose run thành công hiện hành. `analytics.model_runs` giữ parameters và evaluation metrics.

### DM02 - Route/Demand Association Rules (Apriori)
- **Sample**: tối đa 500 trip cho mỗi tổ hợp tháng pickup và pickup borough; thứ tự lấy mẫu theo `md5(trip_id)` nên pseudo-random nhưng xác định/reproducible, tránh bias của “50.000 trip đầu”.
- **Algorithm**: Apriori tự code, frequent itemset tối đa bậc 3 để kiểm soát chi phí.
- **Parameters**: `min_support = 0.005`, `min_confidence = 0.2`, `min_lift = 1.1`, tối thiểu 50 antecedent observations và stability score tối thiểu 0.70.
- **Item formatting**: Để đảm bảo tính nhân quả và giá trị vận hành thực tế, các luật được lọc sao cho:
  - Antecedent chỉ chứa các điều kiện đón và thời gian (`pickup_borough`, `pickup_zone`, `hour_bucket`, `day_name`, `day_type`, `vendor`).
  - Consequent chỉ chứa thông tin đến (`dropoff_borough`, `dropoff_zone`).
- **Quality**: loại luật redundant khi luật tổng quát hơn có confidence gần tương đương; stability là `1 - |confidence_nửa_đầu - confidence_nửa_sau|`; report rule coverage của các luật công bố. Telemetry phân biệt `rules_generated_before_stability`, `rules_retained_after_stability` và `rules_published`; cột `rules_generated` trên từng result row giữ số trước stability filter.
- **Database output**: `analytics.route_association_rules` giữ lịch sử; `analytics.current_route_association_rules` chỉ chứa run thành công hiện hành, tối đa 100 luật xếp theo lift rồi support.

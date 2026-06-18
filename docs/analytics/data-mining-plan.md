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
| Output | `analytics.driver_segments` hoặc bảng kết quả tương đương |

Candidate features:

- `revenue_per_hour`
- `utilization_rate`
- `trips_per_shift`
- `average_trip_distance`
- `tips_per_trip`
- `idle_minutes_per_shift`
- `completed_shifts`

Evaluation:

- Chuẩn hóa feature trước khi clustering.
- Kiểm tra phân phối feature và outlier trước khi fit.
- Chọn `k` bằng elbow/silhouette, sau đó đối chiếu với ý nghĩa nghiệp vụ.
- Không hard-code cluster label theo số cụm. Phải đọc centroid rồi đặt nhãn như
  `High productivity`, `High idle`, `Average stable`.

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
| Output | `analytics.route_association_rules` hoặc bảng kết quả tương đương |

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
- Có bảng/view kết quả trong `analytics` hoặc schema kết quả được phê duyệt. (Bảng `analytics.driver_segments` và `analytics.route_association_rules`)
- Có giải thích feature, thuật toán, tham số, metric đánh giá và giới hạn. (Xem chi tiết bên dưới)
- Kết quả hiển thị được trong Superset mà không query trực tiếp staging/NDS. (Tab 6: Data Mining Insights trên Superset dashboard)
- Kết luận gắn với quyết định vận hành cụ thể.

## Implementation details

### DM01 - Driver Segmentation (K-Means)
- **Features used**: `revenue_per_hour`, `utilization_rate`, `trips_per_shift`, `average_trip_distance`, `tips_per_trip`, `idle_minutes_per_shift`, `completed_shifts`.
- **Scaling**: StandardScaler được sử dụng để chuẩn hóa các thuộc tính trước khi clustering.
- **Algorithm**: K-Means với \(k = 3\) cụm.
- **Dynamic Labeling**: Thay vì hard-code nhãn, centroids thực tế của các cụm được so sánh trực tiếp sau khi huấn luyện:
  - Cụm có `revenue_per_hour` trung bình cao nhất được gán nhãn `High productivity`.
  - Cụm có `idle_minutes_per_shift` trung bình cao nhất trong các cụm còn lại được gán nhãn `High idle`.
  - Cụm cuối cùng được gán nhãn `Average stable`.
- **Database output**: Bảng `analytics.driver_segments` lưu thông tin tài xế kèm nhãn phân cụm nghiệp vụ.

### DM02 - Route/Demand Association Rules (Apriori)
- **Algorithm**: Thuật toán Apriori tự code bằng Python thuần để tránh thêm các dependencies bên ngoài.
- **Parameters**: `min_support = 0.005`, `min_confidence = 0.2`, `min_lift = 1.1`.
- **Item formatting**: Để đảm bảo tính nhân quả và giá trị vận hành thực tế, các luật được lọc sao cho:
  - Antecedent chỉ chứa các điều kiện đón và thời gian (`pickup_borough`, `pickup_zone`, `hour_bucket`, `day_name`, `day_type`, `vendor`).
  - Consequent chỉ chứa thông tin đến (`dropoff_borough`, `dropoff_zone`).
- **Database output**: Bảng `analytics.route_association_rules` chứa 100 luật hàng đầu sắp xếp theo chỉ số Lift giảm dần.

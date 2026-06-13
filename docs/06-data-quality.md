# Data Quality and Business Anomalies

## Data-quality rules

| Rule | Điều kiện | Xử lý |
|---|---|---|
| DQ01 | Không parse được pickup/dropoff | Quarantine |
| DQ02 | Dropoff trước pickup | Quarantine hoặc flag |
| DQ03 | Trip duration lớn hơn 24 giờ | Quarantine |
| DQ04 | Driver/vehicle/shift không tồn tại | Inferred member + missing-master log |
| DQ05 | Trip nằm ngoài shift | Reject assignment |
| DQ06 | Driver có hai trip chồng thời gian | Reject/duplicate log |
| DQ07 | Vehicle có hai trip chồng thời gian | Reject/duplicate log |
| DQ08 | Driver, vehicle và trip khác vendor | Reject assignment |
| DQ09 | License/vehicle không active tại thời điểm trip | Flag |
| DQ10 | Assignment hoặc source row trùng | Deduplicate bằng business key/row hash |
| DQ11 | Pickup/dropoff location không tồn tại | Unknown location |
| DQ12 | Fare/distance âm hoặc bất hợp lý | Flag, không mặc định xóa |

## Business anomalies

Các trường hợp sau được giữ lại để phân tích:

- Revenue per hour quá thấp hoặc cao so với nhóm tương đồng.
- Idle time cao bất thường.
- Shift duration hoặc trip count khác xa phân phối thông thường.
- Driver/vehicle utilization giảm mạnh.
- Khu vực hoạt động thay đổi đột biến.
- Trip distance hoặc duration là outlier nhưng vẫn hợp lệ về cấu trúc.

## Nguyên tắc

Data quality trả lời “record có đủ tin cậy để tích hợp không?”. Business anomaly
trả lời “hoạt động có khác thường và cần điều tra không?”. Không dùng hai khái
niệm thay thế cho nhau.


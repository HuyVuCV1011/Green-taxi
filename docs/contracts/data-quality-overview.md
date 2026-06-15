# Data Quality and Business Anomalies

## Data-quality rules

| Rule | Điều kiện | Xử lý |
|---|---|---|
| DQ01 | Không parse được pickup/dropoff | Quarantine |
| DQ02 | Dropoff trước pickup | Quarantine hoặc flag |
| DQ03 | Trip duration lớn hơn 24 giờ | Quarantine |
| DQ04 | Driver/vehicle/shift không tồn tại | Inferred member + missing-master log |
| DQ05 | Trip nằm ngoài shift | WARN anomaly; vẫn nạp để giữ lineage và đánh dấu `is_anomaly` |
| DQ06 | Driver có hai trip chồng thời gian | Reject/duplicate log |
| DQ07 | Vehicle có hai trip chồng thời gian | Reject/duplicate log |
| DQ08 | Driver, vehicle và trip khác vendor, trừ Legacy Pool `vendor_id = 0` | Log DQ/anomaly theo gate hiện hành; không tự sửa vendor |
| DQ09 | License/vehicle không active tại thời điểm trip | Flag |
| DQ10 | Assignment hoặc source row trùng | Deduplicate bằng business key/row hash |
| DQ11 | Pickup/dropoff location không tồn tại | Unknown location |
| DQ12 | Fare/distance âm hoặc bất hợp lý | Flag, không mặc định xóa |
| DQ13 | Release checksum hoặc seed row count không khớp | Dừng seed/ingestion |
| DQ14 | Source extract count không khớp staging accepted + rejected | Fail reconciliation |
| DQ15 | Cùng source identity có payload khác nhưng không có change event | Quarantine/flag |
| DQ16 | Vehicle inspection trước service start | Quarantine hoặc reject master |
| DQ17 | Required field null/rỗng hoặc enum ngoài contract | Quarantine/reject |
| DQ18 | Business timestamp bị parse như UTC hoặc sai timezone contract | Fail batch |
| DQ19 | Local timestamp rơi vào DST ambiguous/nonexistent interval | Quarantine/flag |
| DQ20 | Staging row thiếu `release_id` hoặc lineage bắt buộc | Fail batch |

## Source and ingestion controls

| Control | File source | Database/document source |
|---|---|---|
| Source identity | File path + row number | Table/collection + primary/natural key |
| Batch identity | File checksum + release ID | Release ID + extract timestamp/watermark |
| Duplicate control | Row hash/business key | Source key + row/document hash |
| Reconciliation | File rows = staged + rejected | Extracted rows = staged + rejected |
| Restart | Reload/skip theo checksum | Reload/skip theo source extract identity |

Seed validation và ingestion validation là hai bước khác nhau. Seed validation
chứng minh source containers khớp canonical release; ingestion validation chứng
minh staging khớp những gì adapters đã extract từ source systems.

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

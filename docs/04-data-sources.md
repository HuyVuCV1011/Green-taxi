# Data Sources

## Nguyên tắc

Nhiều nguồn trong dự án là nhiều **hệ thống nghiệp vụ**, không phải cùng một
dataset được lưu dưới nhiều định dạng.

## Source inventory

| Source system | Dữ liệu | Định dạng | Loại | Vai trò |
|---|---|---|---|---|
| TLC LPEP Trip System | Green Taxi trips | CSV hiện có; Parquet chính thức | Thật | Sự kiện chuyến đi |
| Driver HR System | Driver master | CSV | Synthetic | Hồ sơ và trạng thái tài xế |
| Fleet Management | Vehicle master | JSON Lines | Synthetic | Phương tiện và trạng thái khai thác |
| Dispatch System | Driver shifts | TSV | Synthetic | Ca làm việc |
| Trip Assignment | Trip-driver-vehicle mapping | CSV theo tháng | Synthetic | Liên kết trip với nguồn vận hành |
| HR Change Feed | Driver changes | JSON Lines | Synthetic | Upsert/SCD và late-arriving data |
| TLC Taxi Zone | Zone lookup | CSV | Thật | Master địa lý |
| Vendor lookup | Vendor lookup | CSV | Thật/chuẩn hóa | Nhà cung cấp LPEP |

## Dữ liệu TLC

Theo NYC TLC, Green Taxi trip records chứa pickup/dropoff date-time và location,
trip distance, itemized fares, rate/payment type và passenger count. Dữ liệu
không chứa định danh tài xế hoặc phương tiện, nên các quan hệ vận hành phải được
mô phỏng và công bố rõ.

Nguồn tham khảo:

- https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- https://www.nyc.gov/assets/tlc/downloads/pdf/trip_record_user_guide.pdf
- https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_green.pdf

## Phạm vi dữ liệu local

Dữ liệu trip hiện có gồm 19 tháng từ 01/2020 đến 07/2021 với khoảng 2,3 triệu
dòng CSV. Đây là phạm vi triển khai hiện tại. Không mô tả là đủ 24 tháng cho đến
khi bổ sung 08/2021-12/2021.

## Synthetic data policy

- Không sử dụng tên, license number hay danh tính tài xế thật.
- ID synthetic có prefix rõ ràng như `DRV`, `VEH`, `SHF`.
- Thuật toán sinh, seed và config được version-control.
- Các ràng buộc và giới hạn được ghi trong data contract.
- Kết luận chỉ áp dụng cho case study, không suy diễn về tài xế thật.

## Authoritative source

| Entity | Authoritative source |
|---|---|
| Trip | TLC LPEP Trip System |
| Driver | Driver HR System |
| Vehicle | Fleet Management |
| Shift | Dispatch System |
| Assignment | Trip Assignment |
| Location | TLC Taxi Zone |
| Vendor | Vendor lookup |


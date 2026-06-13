# Teacher Feedback - Mid Project

Nguồn: `[AdvancedBI] Feedback mid project.txt`.

## Các điểm chính

1. Nhiều định dạng không tự động đồng nghĩa với nhiều nguồn nghiệp vụ.
   Cần giải thích cùng thực thể như tài xế, khách hàng hoặc chuyến đi bị phân tán
   ở những hệ thống nào và vì sao cần tích hợp.
2. Phải xác định người dùng cuối cụ thể và quyết định mà hệ thống hỗ trợ.
3. Không nên đồng thời phục vụ giám đốc, marketing, vận hành và QA.
4. Doanh thu, nhu cầu khách hàng, vận hành và chất lượng là các chủ đề DDS khác
   nhau; gom tất cả vào một phạm vi sẽ quá lớn.
5. Nên chọn một nghiệp vụ hoặc một phòng ban có đủ dữ liệu để triển khai.
6. Business anomaly không đồng nghĩa với lỗi chất lượng dữ liệu.
7. ODS chỉ nên tồn tại nếu có nhu cầu quyết định ngắn hạn cụ thể cần nó.
8. Kiến trúc phải xuất phát từ yêu cầu nghiệp vụ, không chỉ từ mô hình lý thuyết.

## Tác động

Thiết kế cũ được giữ lại trong `archive/` để tham khảo. Thiết kế mới chỉ được
chốt sau khi hoàn thành `03-scope.md`, `04-data-sources.md` và ADR tương ứng.

Để phản hồi trực tiếp nhận xét “nhiều định dạng không đồng nghĩa với nhiều
nguồn”, project phân biệt:

- Data release dạng file dùng để phân phối và seed dữ liệu đồng nhất.
- Các hệ thống nguồn nghiệp vụ mô phỏng có storage/interface độc lập.
- Warehouse PostgreSQL đích không dùng chung database với PostgreSQL nguồn.

Thiết kế này tạo ra bài toán tích hợp file, relational database và document
database nhưng vẫn giữ một nguồn dữ liệu chuẩn để các máy có kết quả giống nhau.

# 📖 Documentation Index & Reading Map

Chào mừng bạn đến với thư mục tài liệu kỹ thuật của dự án **NYC Green Taxi Driver Operations BI**. Để thuận tiện cho việc tìm hiểu và tiếp cận hệ thống, tài liệu được tổ chức theo các nhóm chủ đề và được đề xuất lộ trình đọc riêng cho từng đối tượng.

---

## 🗺️ Lộ trình đọc tài liệu (Reading Paths)

Tùy thuộc vào vai trò của bạn khi tiếp cận repository này, hãy tham khảo thứ tự đọc được gợi ý dưới đây:

### 🚪 Dành cho Thành viên mới (New Team Member)
1. **[README.md](../README.md):** Tổng quan nhanh về dự án, cách khởi động local và trạng thái hiện tại.
2. **[docs/13-team-onboarding-and-data-setup.md](13-team-onboarding-and-data-setup.md):** Cẩm năng thiết lập môi trường phát triển local, tải, xác thực checksum và nạp dữ liệu nguồn.
3. **[docs/03-scope.md](03-scope.md):** Nắm vững các câu hỏi nghiệp vụ và phạm vi phân tích của đồ án.

### 🛠️ Dành cho Kỹ sư dữ liệu (Data Engineer / Developer)
1. **[docs/05-architecture.md](05-architecture.md):** Hiểu kiến trúc dữ liệu 4 tầng (Staging -> DQ/Audit -> NDS -> DDS).
2. **[docs/04-data-sources.md](04-data-sources.md):** Danh mục chi tiết các nguồn dữ liệu thật và dữ liệu mô phỏng.
3. **[docs/08-data-contracts.md](08-data-contracts.md):** Các cam kết về schema và kiểu dữ liệu đầu vào.
4. **[docs/10-source-to-target-plan.md](10-source-to-target-plan.md):** Logic ánh xạ, chuyển đổi dữ liệu và SCD Type 1/2.
5. **[docs/14-warehouse-ddl.md](14-warehouse-ddl.md):** Cấu trúc chi tiết các bảng trong PostgreSQL Warehouse.

### 🎓 Dành cho Giảng viên & Người đánh giá (Reviewer)
1. **[docs/01-project-context.md](01-project-context.md):** Bối cảnh và định hướng phân tích của đồ án.
2. **[docs/03-scope.md](03-scope.md):** Phạm vi nghiệp vụ và 5 nhóm câu hỏi quyết định.
3. **[docs/09-analytics-requirements.md](09-analytics-requirements.md):** Chi tiết các chỉ số đo lường (KPI) và công thức tính.
4. **[docs/07-implementation-plan.md](07-implementation-plan.md):** Kế hoạch triển khai mã nguồn, tiến độ các Milestone.
5. **[docs/02-teacher-feedback.md](02-teacher-feedback.md):** Tiếp thu ý kiến đóng góp của giáo viên hướng dẫn và các hành động khắc phục.

---

## 🗂️ Danh mục tài liệu đầy đủ (Documentation Map)

| Tên tài liệu | Phân loại | Nội dung chính |
|---|---|---|
| 📂 **Tổng quan & Bối cảnh** | | |
| 📄 [01-project-context.md](01-project-context.md) | Bối cảnh | Lý do lựa chọn đề tài và mục tiêu tổng quát của đồ án |
| 📄 [02-teacher-feedback.md](02-teacher-feedback.md) | Phản hồi | Nhật ký tiếp thu ý kiến của giáo viên và phương án điều chỉnh |
| 📄 [03-scope.md](03-scope.md) | Nghiệp vụ | Chi tiết 5 nhóm câu hỏi quyết định và ranh giới hệ thống |
| 📄 [09-analytics-requirements.md](09-analytics-requirements.md) | KPI | Định nghĩa chi tiết các độ đo, thứ chiều phân tích |
| 📂 **Kiến trúc & Đặc tả Dữ liệu** | | |
| 📄 [04-data-sources.md](04-data-sources.md) | Nguồn dữ liệu | Inventory chi tiết các hệ thống nguồn thật và giả lập |
| 📄 [05-architecture.md](05-architecture.md) | Kiến trúc | Thiết kế kiến trúc logic, vật lý, bootstrap và múi giờ |
| 📄 [08-data-contracts.md](08-data-contracts.md) | Hợp đồng dữ liệu | Quy định ràng buộc cấu trúc đầu vào cho từng nguồn |
| 📄 [10-source-to-target-plan.md](10-source-to-target-plan.md) | ETL Mapping | Ánh xạ chi tiết từ nguồn vào NDS và DDS |
| 📄 [14-warehouse-ddl.md](14-warehouse-ddl.md) | Schema DDL | Baseline cấu trúc bảng PostgreSQL Warehouse |
| 📂 **Quản lý & Hướng dẫn Vận hành** | | |
| 📄 [07-implementation-plan.md](07-implementation-plan.md) | Kế hoạch | Kế hoạch triển khai chi tiết mã nguồn và definition of done |
| 📄 [11-work-breakdown.md](11-work-breakdown.md) | Milestone | Phân chia công việc theo Work Breakdown Structure |
| 📄 [12-synthetic-generation-report.md](12-synthetic-generation-report.md) | Dữ liệu mô phỏng | Báo cáo chi tiết thuật toán sinh dữ liệu và validation |
| 📄 [13-team-onboarding-and-data-setup.md](13-team-onboarding-and-data-setup.md) | Hướng dẫn | Cách cấu hình môi trường local, seed nguồn và chạy unittest |
| 📂 **Thư mục mở rộng** | | |
| 📁 [decisions/](decisions/) | Kiến trúc (ADR) | Lưu trữ các quyết định thiết kế hệ thống quan trọng (Architecture Decision Records) |
| 📁 [meetings/](meetings/) | Biên bản | Nhật ký các buổi họp nhóm |
